"""
CivilPy
Copyright (C) 2019-2026 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

================================================================================
SNBI (Specifications for the National Bridge Inventory) data-validation models.

These Pydantic models implement the FHWA SNBI data validation rules as published
in the FHWA "SNBI Data Validation Rules" workbook. They are intentionally
*generic* (national) rather than Ohio-specific: any valid SNBI submission for any
State should validate.

Mapping of the workbook's severity levels onto Pydantic:

* ``Critical`` / ``Error`` objective data-quality checks (data type, length,
  numeric magnitude, character set, date format, enumerated value, and the
  cross-field consistency checks) are enforced and raise ``ValidationError``.
* Fields the workbook marks "must be reported for all bridges" are required;
  fields that are conditionally required ("...when B.F.01 begins with H...") or
  only ``Flag``-level when missing are optional but still range/format-checked
  when a value is present.
* ``Flag``-only advisories that depend on engineering judgement (e.g. latitude
  polarity hints, "FHWA prefers a name") are not raised.

Checks that reference external SNBI code tables not contained in the workbook
(owner codes, span material/type codes, element numbers in Table 22, railing
codes in Table 6, etc.) are enforced as data-type/length checks only; their
allowed-value lists are noted in comments. Enumerations the workbook spells out
inline ARE enforced. ``State Code`` (B.L.01) is validated against civilpy's
``NBIS_state_codes`` table.

Several items are FHWA-calculated and must NOT be reported (B.G.16 Calculated
Deck Area, B.C.12 Bridge Condition Classification, B.C.13 Lowest Condition
Rating, B.IE.06 Inspection Due Date) -- supplying a value for these raises.
"""

import re
from datetime import datetime
from typing import Optional, List, Annotated

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from civilpy.state.ohio.DOT.legacy import state_code_conversion

# ---------------------------------------------------------------------------
# Shared constants / helpers
# ---------------------------------------------------------------------------

# Condition-rating valid values (B.C.01-B.C.11, B.C.14, B.C.15): 0 through 9 and N
_COND_RATINGS = {str(n) for n in range(10)} | {"N"}

# Character sets defined inline in the workbook (data format checks)
_CHARSET_BID = r"^[A-Za-z0-9 .*&_()+\-]+$"          # B.ID.01 / B.ID.03 / B.H.18
_CHARSET_BORDER = r"^[A-Za-z0-9 .*&_()+/\-]+$"       # B.L.07 (adds /)
_CHARSET_ROUTE_NUM = r"^[A-Za-z0-9 .*&_()|+\-]+$"    # B.RT.02 (adds |)
_CHARSET_ALNUM = r"^[A-Za-z0-9]+$"                   # B.IE.04
_CHARSET_NOTE = r"^[A-Za-z0-9 .*&_()+/\-]+$"         # B.IE.11
_CHARSET_LOAD_CFG = r"^[A-Za-z0-9\-]+$"              # B.EP.01

# Strings that the workbook treats as "no value reported"
_EMPTY = {None, "", "0"}


def _require_date(value, item):
    """Validate an 8-digit YYYYMMDD value that is also a real calendar date."""
    if value is None:
        return value
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]{8}", text):
        raise ValueError(f"{item} must be numeric in YYYYMMDD format")
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError:
        raise ValueError(f"{item} is not a valid calendar date (YYYYMMDD)")
    return text


def _require_in(value, allowed, item):
    """Validate that a (stripped) value is within an enumerated set, if present."""
    if value is None:
        return value
    text = str(value).strip()
    if text not in allowed:
        raise ValueError(
            f"{item} value {text!r} is not valid; allowed values: "
            f"{', '.join(sorted(allowed))}"
        )
    return text


def _require_charset(value, pattern, item):
    if value is None:
        return value
    if not re.fullmatch(pattern, str(value)):
        raise ValueError(f"{item} contains invalid characters")
    return value


def _is_valid_state_or_country(text):
    """True if ``text`` is a valid SNBI State code or the border countries MX/CA."""
    upper = str(text).strip().upper()
    if upper in {"MX", "CA"}:
        return True
    try:
        state_code_conversion(f"{int(upper):02d}")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Child datasets
# ---------------------------------------------------------------------------
class Element(BaseModel):
    """SNBI element record (B.E / B.CS). Element numbers are validated against
    SNBI Table 22 by FHWA; here only length/range and the total-quantity
    reconciliation (B.E.03-3) are enforced."""

    BE01: Annotated[str, StringConstraints(max_length=4, min_length=1, strip_whitespace=True)]
    # B.E.02 (Element Parent Number) is only reported for child elements (defects,
    # protective systems) nested under a parent; top-level NBE elements have no
    # parent, so it is optional.
    BE02: Optional[Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)]] = None
    BE03: Optional[Annotated[int, Field(ge=0, le=99999999)]] = None
    BCS01: Optional[Annotated[int, Field(ge=0, le=99999999)]] = None
    BCS02: Optional[Annotated[int, Field(ge=0, le=99999999)]] = None
    BCS03: Optional[Annotated[int, Field(ge=0, le=99999999)]] = None
    BCS04: Optional[Annotated[int, Field(ge=0, le=99999999)]] = None

    @model_validator(mode="after")
    def _total_equals_condition_state_sum(self):
        # B.E.03-3 (Critical): total quantity must equal the sum of CS1-CS4
        states = [self.BCS01, self.BCS02, self.BCS03, self.BCS04]
        if self.BE03 is not None and all(s is not None for s in states):
            if self.BE03 != sum(states):
                raise ValueError(
                    "BE03 Element Total Quantity must equal the sum of "
                    "BCS01-BCS04"
                )
        return self


class Route(BaseModel):
    """SNBI route record (B.RT). Required for every 'highway' feature."""

    BRT01: Annotated[str, StringConstraints(max_length=3, min_length=1, strip_whitespace=True)]
    BRT02: Optional[Annotated[str, StringConstraints(max_length=15, strip_whitespace=True)]] = None
    BRT03: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BRT04: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BRT05: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None

    @field_validator("BRT01")
    @classmethod
    def _designation_starts_with_r(cls, v):
        # B.RT.01: valid route designations begin with "R"
        if not v.upper().startswith("R"):
            raise ValueError('BRT01 Route Designation must begin with "R"')
        return v

    @field_validator("BRT02")
    @classmethod
    def _route_number_charset(cls, v):
        return _require_charset(v, _CHARSET_ROUTE_NUM, "BRT02 Route Number")

    @field_validator("BRT04")
    @classmethod
    def _route_type(cls, v):
        # B.RT.04: 1 through 7 and X
        return _require_in(v, {str(n) for n in range(1, 8)} | {"X"}, "BRT04 Route Type")

    @field_validator("BRT05")
    @classmethod
    def _service_type(cls, v):
        # B.RT.05: 1 through 8 and X
        return _require_in(v, {str(n) for n in range(1, 9)} | {"X"}, "BRT05 Service Type")


class Feature(BaseModel):
    """SNBI feature record (B.F / B.H / B.RR / B.N).

    Conditional-required highway sub-items ("...when B.F.02 = C") are not forced
    here (they need the feature-location context and HPMS lookups); range and
    enumeration checks apply when a value is present.
    """

    BF01: Annotated[str, StringConstraints(max_length=3, min_length=1, strip_whitespace=True)]
    BF02: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BF03: Optional[Annotated[str, StringConstraints(max_length=300, strip_whitespace=True)]] = None

    # Highway sub-items
    BH01: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BH02: Optional[Annotated[str, StringConstraints(max_length=5, strip_whitespace=True)]] = None
    BH03: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BH04: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BH05: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BH06: Optional[Annotated[str, StringConstraints(max_length=120, strip_whitespace=True)]] = None
    BH07: Optional[Annotated[float, Field(ge=0, le=99999999)]] = None
    BH08: Optional[Annotated[int, Field(ge=0, le=99)]] = None
    BH09: Optional[Annotated[int, Field(ge=0, le=99999999)]] = None
    BH10: Optional[Annotated[int, Field(ge=0, le=99999999)]] = None
    BH11: Optional[Annotated[int, Field(ge=0, le=9999)]] = None
    BH12: Optional[Annotated[float, Field(ge=0, le=99.9)]] = None
    BH13: Optional[Annotated[float, Field(ge=0, le=99.9)]] = None
    BH14: Optional[Annotated[float, Field(ge=0, le=99.9)]] = None
    BH15: Optional[Annotated[float, Field(ge=0, le=99.9)]] = None
    BH16: Optional[Annotated[float, Field(ge=0, le=99.9)]] = None
    BH17: Optional[Annotated[int, Field(ge=0, le=999)]] = None
    BH18: Optional[Annotated[str, StringConstraints(max_length=15, strip_whitespace=True)]] = None

    # Railroad sub-items
    BRR01: Optional[Annotated[str, StringConstraints(max_length=2, strip_whitespace=True)]] = None
    BRR02: Optional[Annotated[float, Field(ge=0, le=99.9)]] = None
    BRR03: Optional[Annotated[float, Field(ge=0, le=99.9)]] = None

    # Navigable-waterway sub-items
    BN01: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BN02: Optional[Annotated[float, Field(ge=0, le=999.9)]] = None
    BN03: Optional[Annotated[float, Field(ge=0, le=999.9)]] = None
    BN04: Optional[Annotated[float, Field(ge=0, le=9999.9)]] = None
    BN05: Optional[Annotated[float, Field(ge=0, le=9999.9)]] = None
    BN06: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None

    Routes: Optional[List[Route]] = None

    @field_validator("BH03")
    @classmethod
    def _nhs(cls, v):
        return _require_in(v, {"Y", "N"}, "BH03 NHS Designation")

    @field_validator("BH04")
    @classmethod
    def _nhfn(cls, v):
        return _require_in(v, {"1", "2", "3", "4", "N", "1-T"}, "BH04 NHFN")

    @field_validator("BH05")
    @classmethod
    def _strahnet(cls, v):
        return _require_in(v, {"1", "2", "N"}, "BH05 STRAHNET Designation")

    @field_validator("BH18")
    @classmethod
    def _crossing_bridge_charset(cls, v):
        return _require_charset(v, _CHARSET_BID, "BH18 Crossing Bridge Number")

    @field_validator("BN01")
    @classmethod
    def _navigable(cls, v):
        return _require_in(v, {"Y", "N", "U"}, "BN01 Navigable Waterway")

    @field_validator("BN06")
    @classmethod
    def _nav_protection(cls, v):
        return _require_in(v, {str(n) for n in range(6)} | {"1-T"}, "BN06 Substructure Navigation Protection")

    @model_validator(mode="after")
    def _feature_type_conditionals(self):
        ftype = (self.BF01 or "").upper()
        # B.RT.01 (Critical): highway features must carry at least one route
        if ftype.startswith("H"):
            if not self.Routes or not any(r.BRT01 for r in self.Routes):
                raise ValueError(
                    "A highway feature (BF01 begins with 'H') must report at "
                    "least one Route dataset with BRT01"
                )
        # B.N (Critical): waterway features must report navigable-waterway code
        if ftype.startswith("W") and self.BN01 is None:
            raise ValueError(
                "A waterway feature (BF01 begins with 'W') must report BN01 "
                "Navigable Waterway (Y, N, or U)"
            )
        return self


class Inspection(BaseModel):
    """SNBI inspection event record (B.IE)."""

    BIE01: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]
    BIE02: str  # Inspection Begin Date - YYYYMMDD (required for each inspection)
    BIE03: Optional[str] = None  # Inspection Completion Date - YYYYMMDD
    BIE04: Optional[Annotated[str, StringConstraints(max_length=15, strip_whitespace=True)]] = None
    BIE05: Optional[Annotated[int, Field(ge=0, le=99)]] = None
    BIE06: Optional[str] = None  # Inspection Due Date - FHWA-CALCULATED, do not report
    BIE07: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BIE08: Optional[str] = None  # QC Date - YYYYMMDD
    BIE09: Optional[str] = None  # QA Date - YYYYMMDD
    BIE10: Optional[str] = None  # Data Update Date - YYYYMMDD
    BIE11: Optional[Annotated[str, StringConstraints(max_length=300, strip_whitespace=True)]] = None
    BIE12: Optional[Annotated[str, StringConstraints(max_length=120, strip_whitespace=True)]] = None

    @field_validator("BIE02", "BIE03", "BIE08", "BIE09", "BIE10")
    @classmethod
    def _dates(cls, v, info):
        return _require_date(v, info.field_name)

    @field_validator("BIE04")
    @classmethod
    def _inspector_charset(cls, v):
        return _require_charset(v, _CHARSET_ALNUM, "BIE04 Nationally Certified Bridge Inspector")

    @field_validator("BIE07")
    @classmethod
    def _risk_method(cls, v):
        return _require_in(v, {"1", "2", "N"}, "BIE07 Risk-Based Inspection Interval Method")

    @field_validator("BIE11")
    @classmethod
    def _note_charset(cls, v):
        return _require_charset(v, _CHARSET_NOTE, "BIE11 Inspection Note")

    @field_validator("BIE06")
    @classmethod
    def _due_date_not_reported(cls, v):
        # B.IE.06: FHWA WILL CALCULATE THIS VALUE - do not report
        if v is not None:
            raise ValueError("BIE06 Inspection Due Date is FHWA-calculated; do not report it")
        return v


class PostingEvaluation(BaseModel):
    """SNBI load evaluation & posting record (B.EP)."""

    BEP01: Annotated[str, StringConstraints(max_length=15, min_length=1, strip_whitespace=True)]
    BEP02: Optional[Annotated[float, Field(ge=0, le=99.99)]] = None
    BEP03: Optional[Annotated[str, StringConstraints(max_length=17, strip_whitespace=True)]] = None
    BEP04: Optional[Annotated[str, StringConstraints(max_length=15, strip_whitespace=True)]] = None

    @field_validator("BEP01")
    @classmethod
    def _legal_load_charset(cls, v):
        return _require_charset(v, _CHARSET_LOAD_CFG, "BEP01 Legal Load Configuration")


class PostingStatus(BaseModel):
    """SNBI load posting status record (B.PS)."""

    BPS01: Annotated[str, StringConstraints(max_length=4, min_length=1, strip_whitespace=True)]
    BPS02: Optional[str] = None  # Posting Status Change Date - YYYYMMDD

    @field_validator("BPS02")
    @classmethod
    def _change_date(cls, v):
        return _require_date(v, "BPS02 Posting Status Change Date")


class SpanSet(BaseModel):
    """SNBI span set record (B.SP)."""

    BSP01: Annotated[str, StringConstraints(max_length=3, min_length=1, strip_whitespace=True)]
    BSP02: Optional[Annotated[int, Field(ge=0, le=9999)]] = None
    BSP03: Optional[Annotated[int, Field(ge=0, le=999)]] = None
    BSP04: Optional[Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)]] = None
    BSP05: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BSP06: Optional[Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)]] = None
    BSP07: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BSP08: Optional[Annotated[str, StringConstraints(max_length=2, strip_whitespace=True)]] = None
    BSP09: Optional[Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)]] = None
    BSP10: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BSP11: Optional[Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)]] = None
    BSP12: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BSP13: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None

    @field_validator("BSP05")
    @classmethod
    def _span_continuity(cls, v):
        # B.SP.05: 1 through 7 (+ temporary codes valid 2026-2027)
        return _require_in(v, {str(n) for n in range(1, 8)} | {"C-T", "7-T"}, "BSP05 Span Continuity")


class SubstructureSet(BaseModel):
    """SNBI substructure set record (B.SB)."""

    BSB01: Annotated[str, StringConstraints(max_length=3, min_length=1, strip_whitespace=True)]
    BSB02: Optional[Annotated[int, Field(ge=1, le=999)]] = None  # must be > 0
    BSB03: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BSB04: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BSB05: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BSB06: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BSB07: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None


class Work(BaseModel):
    """SNBI work-event record (B.W.02 / B.W.03)."""

    BW02: Annotated[int, Field(ge=1000, le=9999)]  # Year Work Performed (YYYY)
    BW03: Optional[Annotated[str, StringConstraints(max_length=120, strip_whitespace=True)]] = None


# ---------------------------------------------------------------------------
# Root record
# ---------------------------------------------------------------------------
class Bridge(BaseModel):
    # --- Identification (B.ID) -------------------------------------------------
    BID01: Annotated[str, StringConstraints(max_length=15, min_length=1, strip_whitespace=True)]
    BID02: Optional[Annotated[str, StringConstraints(max_length=300, strip_whitespace=True)]] = None
    BID03: Optional[Annotated[str, StringConstraints(max_length=15, strip_whitespace=True)]] = "0"

    # --- Location (B.L) --------------------------------------------------------
    BL01: int  # State Code - validated against NBIS_state_codes below
    BL02: Optional[Annotated[int, Field(ge=1, le=999)]] = None
    BL03: Optional[Annotated[int, Field(ge=0, le=99999)]] = None
    BL04: Optional[Annotated[str, StringConstraints(max_length=2, strip_whitespace=True)]] = None
    BL05: Annotated[float, Field(ge=-90.0, le=90.0)]   # Latitude
    BL06: Annotated[float, Field(ge=-180.0, le=180.0)]  # Longitude
    BL07: Optional[Annotated[str, StringConstraints(max_length=15, strip_whitespace=True)]] = None
    BL08: Optional[Annotated[str, StringConstraints(max_length=2, strip_whitespace=True)]] = None
    BL09: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BL10: Optional[Annotated[str, StringConstraints(max_length=2, strip_whitespace=True)]] = None
    BL11: Optional[Annotated[str, StringConstraints(max_length=300, strip_whitespace=True)]] = None
    BL12: Optional[Annotated[str, StringConstraints(max_length=300, strip_whitespace=True)]] = None

    # --- Classification (B.CL) -------------------------------------------------
    BCL01: Annotated[str, StringConstraints(max_length=4, min_length=1, strip_whitespace=True)]
    BCL02: Annotated[str, StringConstraints(max_length=4, min_length=1, strip_whitespace=True)]
    BCL03: Optional[Annotated[str, StringConstraints(max_length=30, strip_whitespace=True)]] = None
    BCL04: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BCL05: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BCL06: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None

    # --- Railings (B.RH) -------------------------------------------------------
    BRH01: Optional[Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)]] = None
    BRH02: Optional[Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)]] = None

    # --- Geometry (B.G) --------------------------------------------------------
    BG01: Annotated[float, Field(ge=0, le=999999.9)]   # NBIS Bridge Length (> 20 ft to be NBIS)
    BG02: Annotated[float, Field(ge=0, le=999999.9)]   # Total Bridge Length
    BG03: Optional[Annotated[float, Field(ge=0, le=9999.9)]] = None
    BG04: Optional[Annotated[float, Field(ge=0, le=9999.9)]] = None
    BG05: Annotated[float, Field(gt=0, le=999.9)]      # Width Out-to-Out (> 0)
    BG06: Optional[Annotated[float, Field(ge=0, le=999.9)]] = None
    BG07: Optional[Annotated[float, Field(ge=0, le=99.9)]] = None
    BG08: Optional[Annotated[float, Field(ge=0, le=99.9)]] = None
    BG09: Annotated[float, Field(gt=0, le=999.9)]      # Approach Roadway Width (> 0)
    BG10: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BG11: Optional[Annotated[int, Field(ge=0, le=99)]] = None
    BG12: Optional[Annotated[str, StringConstraints(max_length=2, strip_whitespace=True)]] = None
    BG13: Optional[Annotated[int, Field(ge=0, le=9999)]] = None
    BG14: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BG15: Optional[Annotated[float, Field(ge=0, le=999999999.9)]] = None
    BG16: Optional[float] = None  # Calculated Deck Area - FHWA-CALCULATED, do not report

    # --- Load rating (B.LR) ----------------------------------------------------
    BLR01: Optional[Annotated[str, StringConstraints(max_length=8, strip_whitespace=True)]] = None
    BLR02: Optional[Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)]] = None
    BLR03: Optional[str] = None  # Load Rating Date - YYYYMMDD
    BLR04: Optional[Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)]] = None
    BLR05: Optional[Annotated[float, Field(ge=0, le=99.99)]] = None
    BLR06: Optional[Annotated[float, Field(ge=0, le=99.99)]] = None
    BLR07: Optional[Annotated[float, Field(ge=0, le=99.99)]] = None
    BLR08: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None

    # --- Inspection requirements (B.IR) ---------------------------------------
    BIR01: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BIR02: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BIR03: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BIR04: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None

    # --- Condition (B.C) -------------------------------------------------------
    BC01: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]
    BC02: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]
    BC03: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]
    BC04: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]
    BC05: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BC06: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BC07: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BC08: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BC09: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BC10: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BC11: Optional[Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)]] = None
    BC12: Optional[str] = None  # Bridge Condition Classification - FHWA-CALCULATED
    BC13: Optional[str] = None  # Lowest Condition Rating Code - FHWA-CALCULATED
    BC14: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BC15: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None

    # --- Appraisal (B.AP) ------------------------------------------------------
    BAP01: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None
    BAP02: Optional[Annotated[str, StringConstraints(max_length=5, strip_whitespace=True)]] = None
    BAP03: Optional[Annotated[str, StringConstraints(max_length=5, strip_whitespace=True)]] = None
    BAP04: Optional[Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)]] = None
    BAP05: Optional[Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)]] = None

    # --- Year built (B.W.01) ---------------------------------------------------
    BW01: Optional[Annotated[int, Field(ge=1000, le=9999)]] = None

    # --- One-to-many relationships --------------------------------------------
    Elements: Optional[List[Element]] = None
    Features: Optional[List[Feature]] = None
    Inspections: Optional[List[Inspection]] = None
    PostingEvaluations: Optional[List[PostingEvaluation]] = None
    PostingStatuses: Optional[List[PostingStatus]] = None
    SpanSets: Optional[List[SpanSet]] = None
    SubstructureSets: Optional[List[SubstructureSet]] = None
    Works: Optional[List[Work]] = None

    # === Field validators =====================================================
    @field_validator("BID01", "BID03")
    @classmethod
    def _bridge_number_charset(cls, v, info):
        return _require_charset(v, _CHARSET_BID, f"{info.field_name} Bridge Number")

    @field_validator("BL01")
    @classmethod
    def _valid_state_code(cls, v):
        # B.L.01-1 (Critical): must be a valid SNBI State code
        try:
            state_code_conversion(f"{int(v):02d}")
        except Exception:
            raise ValueError(f"BL01 State Code {v!r} is not a valid SNBI state code")
        return v

    @field_validator("BL04")
    @classmethod
    def _district_charset(cls, v):
        # B.L.04-3: alphanumeric (A-Z, a-z, 0-9) - NOT numeric-only
        return _require_charset(v, _CHARSET_ALNUM, "BL04 Highway Agency District")

    @field_validator("BL07")
    @classmethod
    def _border_number_charset(cls, v):
        return _require_charset(v, _CHARSET_BORDER, "BL07 Border Bridge Number")

    @field_validator("BL08", "BL10")
    @classmethod
    def _border_state(cls, v, info):
        if v is None:
            return v
        if not _is_valid_state_or_country(v):
            raise ValueError(
                f"{info.field_name} must be a valid SNBI State code or MX/CA"
            )
        return str(v).strip().upper()

    @field_validator("BL09")
    @classmethod
    def _border_insp_resp(cls, v):
        # B.L.09: 0 through 2
        return _require_in(v, {"0", "1", "2"}, "BL09 Border Bridge Inspection Responsibility")

    @field_validator("BCL04")
    @classmethod
    def _historic(cls, v):
        # B.CL.04: 1 through 7, N (T = temporary, valid 2026-2027)
        return _require_in(v, {str(n) for n in range(1, 8)} | {"N", "T"}, "BCL04 Historic Significance")

    @field_validator("BCL05")
    @classmethod
    def _toll(cls, v):
        # B.CL.05: 1 through 4 and N
        return _require_in(v, {str(n) for n in range(1, 5)} | {"N"}, "BCL05 Toll")

    @field_validator("BCL06")
    @classmethod
    def _emergency_evac(cls, v):
        return _require_in(v, {"Y", "N"}, "BCL06 Emergency Evacuation Designation")

    @field_validator("BG10")
    @classmethod
    def _median(cls, v):
        # B.G.10: 0 through 3
        return _require_in(v, {"0", "1", "2", "3"}, "BG10 Bridge Median")

    @field_validator("BG14")
    @classmethod
    def _sidehill(cls, v):
        return _require_in(v, {"Y", "N"}, "BG14 Sidehill Bridge")

    @field_validator("BG16")
    @classmethod
    def _calc_deck_area_not_reported(cls, v):
        if v is not None:
            raise ValueError("BG16 Calculated Deck Area is FHWA-calculated; do not report it")
        return v

    @field_validator("BLR03")
    @classmethod
    def _load_rating_date(cls, v):
        return _require_date(v, "BLR03 Load Rating Date")

    @field_validator("BLR08")
    @classmethod
    def _routine_permit(cls, v):
        # B.LR.08: A, B, C, or N
        return _require_in(v, {"A", "B", "C", "N"}, "BLR08 Routine Permit Loads")

    @field_validator("BIR02", "BIR04")
    @classmethod
    def _yes_no(cls, v, info):
        return _require_in(v, {"Y", "N"}, info.field_name)

    @field_validator("BC01", "BC02", "BC03", "BC04", "BC05", "BC06", "BC07",
                     "BC08", "BC09", "BC10", "BC14", "BC15")
    @classmethod
    def _condition_rating(cls, v, info):
        # 0 through 9 and N
        return _require_in(v, _COND_RATINGS, f"{info.field_name} Condition Rating")

    @field_validator("BC11")
    @classmethod
    def _scour_rating(cls, v):
        # B.C.11: 0-9, N (+ temporary codes valid 2026-2027)
        return _require_in(v, _COND_RATINGS | {"MA-T", "MI-T", "MO-T"}, "BC11 Scour Condition Rating")

    @field_validator("BC12", "BC13")
    @classmethod
    def _calculated_condition_not_reported(cls, v, info):
        if v is not None:
            raise ValueError(f"{info.field_name} is FHWA-calculated; do not report it")
        return v

    @field_validator("BAP01")
    @classmethod
    def _approach_alignment(cls, v):
        return _require_in(v, {"G", "F", "P"}, "BAP01 Approach Roadway Alignment")

    @field_validator("BAP02")
    @classmethod
    def _overtopping(cls, v):
        return _require_in(v, {str(n) for n in range(7)} | {"VLM-T", "HVH-T"}, "BAP02 Overtopping Likelihood")

    @field_validator("BAP04")
    @classmethod
    def _scour_poa(cls, v):
        return _require_in(v, {"0", "Y", "N"}, "BAP04 Scour Plan of Action")

    # === Cross-field model validators =========================================
    @model_validator(mode="after")
    def _required_datasets(self):
        # Critical "at least one ... dataset" rules
        if not self.Features:
            raise ValueError("At least one Features dataset (BF01) must be reported")
        if not self.PostingStatuses:
            raise ValueError("At least one Load Posting Status dataset (BPS01) must be reported")
        if not self.SpanSets:
            raise ValueError("At least one Span dataset (BSP01) must be reported")
        if not self.Works:
            raise ValueError("At least one Work dataset (BW02) must be reported")

        # B.SB (Critical): substructure required unless ALL spans are buried
        # pipe culverts (BSP06 = P01 or P02)
        all_culvert_pipe = bool(self.SpanSets) and all(
            (s.BSP06 or "").upper() in {"P01", "P02"} for s in self.SpanSets
        )
        if not all_culvert_pipe and not self.SubstructureSets:
            raise ValueError("At least one Substructure dataset (BSB01) must be reported")
        return self

    @model_validator(mode="after")
    def _length_consistency(self):
        # B.G.02-3 (Critical): NBIS length must not exceed total length
        if self.BG01 is not None and self.BG02 is not None and self.BG01 > self.BG02:
            raise ValueError("BG01 NBIS Bridge Length must not exceed BG02 Total Bridge Length")
        return self

    @model_validator(mode="after")
    def _previous_number_differs(self):
        # B.ID.03-4: previous bridge number must differ from current
        if self.BID03 not in _EMPTY and self.BID03 == self.BID01:
            raise ValueError("BID03 Previous Bridge Number must not equal BID01 Bridge Number")
        return self

    @model_validator(mode="after")
    def _calculated_condition_dependencies(self):
        # B.C.14-2 / B.C.15-2: do not report when the inspection is not required
        if (self.BIR01 or "").upper() != "Y" and self.BC14 is not None:
            raise ValueError("BC14 NSTM Inspection Condition must not be reported when BIR01 != 'Y'")
        if (self.BIR03 or "").upper() != "Y" and self.BC15 is not None:
            raise ValueError("BC15 Underwater Inspection Condition must not be reported when BIR03 != 'Y'")
        return self

    @model_validator(mode="after")
    def _posting_evaluation_required(self):
        # B.EP (Critical): when not closed and controlling legal rating < 1.0,
        # at least one Load Evaluation & Posting dataset must be reported
        open_to_traffic = any(
            (ps.BPS01 or "").upper() != "C" for ps in (self.PostingStatuses or [])
        )
        if open_to_traffic and self.BLR07 is not None and self.BLR07 < 1.0:
            if not self.PostingEvaluations:
                raise ValueError(
                    "A Load Evaluation and Posting dataset (BEP01) is required when "
                    "the bridge is open and BLR07 Controlling Legal Load Rating Factor < 1.0"
                )
        return self

    @model_validator(mode="after")
    def _safety_checks(self):
        statuses = {(ps.BPS01 or "").upper() for ps in (self.PostingStatuses or [])}
        closed = "C" in statuses

        # Safety - Closed Bridge: operating rating very low but not closed
        if self.BLR06 is not None and self.BLR06 < 0.1 and not closed:
            raise ValueError(
                "Safety check: BLR06 Operating Load Rating Factor < 0.1 but the "
                "bridge is not posted closed (BPS01 = 'C')"
            )
        # Safety - Closed Bridge: a controlling condition rating below 2 but not closed
        for item in ("BC01", "BC02", "BC03", "BC04"):
            value = getattr(self, item)
            if value is not None and value.isdigit() and int(value) < 2 and not closed:
                raise ValueError(
                    f"Safety check: {item} Condition Rating < 2 but the bridge is "
                    "not posted closed (BPS01 = 'C')"
                )
        # Safety - Posted Bridge: legal rating < 1.0 without an appropriate posting
        posted_or_closed = {"PP", "TP", "SP", "PR", "TR", "SR", "C"}
        if (
            self.BLR07 is not None
            and self.BLR07 < 1.0
            and not (statuses & posted_or_closed)
        ):
            raise ValueError(
                "Safety check: BLR07 Controlling Legal Load Rating Factor < 1.0 but "
                "the bridge is not posted/restricted/closed"
            )
        return self
