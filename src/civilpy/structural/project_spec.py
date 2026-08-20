#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Storable project records — the project-object schema authority.

The historical-record system stores one "project object" per construction
contract: a thin :class:`ProjectRecord` parent (PID, the SFNs it touches,
where and when it sold) composed with fat, per-discipline component
records.  The keystone component is :class:`EraStandardsRecord` — the
standards in force when the plan was sold (CMS spec year, the SCD/plan-
insert/standard-bridge-drawing sheets listed on the title sheet, and the
design-manual editions) — because a sparse historic bridge resolves any
field it does not explicitly know through the era registry, and is
*marked as such* via :class:`~civilpy.structural.bim_spec.Provenance`.

Everything follows :mod:`civilpy.structural.bim_spec` exactly: plain
dataclasses of JSON-safe primitives, per-field engineering metadata via
:func:`~civilpy.structural.bim_spec.spec_field`, strict
:meth:`~civilpy.structural.bim_spec.SpecRecord.validate` in front of the
schema-free JSONB store, and :func:`~civilpy.structural.bim_spec
.record_to_dict` round-trips.  The application side (snbi_ui) stores the
flattened document plus a few promoted, indexed columns — the same
``Bridge``/``OhioBridge`` split the BIM phases use.

The similarity pipeline consumes :meth:`ProjectRecord.features` — a flat
dict of JSON scalars (numbers + categorical strings) versioned by
:data:`FEATURES_VERSION`, fed to the EllisPCA-pattern engine whose
``OneHotEncoder`` handles the categoricals.  Stored vectors are
reproducible: same record + same version → same features.

MOT / real-estate / survey start deliberately thin (the fields a title
sheet, MOT notes, and an RE summary reliably yield) and sharpen as the
plan-corpus extractors populate them; adding a field is an additive JSON
key, never a migration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from civilpy.structural.bim_spec import (
    ElementRecord,
    Provenance,
    SpecRecord,
    spec_field,
)

#: Bump when the meaning of a stored feature changes (not when one is
#: added) — consumers persist vectors keyed by this.
FEATURES_VERSION = 1

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _bad_date(name: str, value: str | None) -> list[str]:
    """ISO ``YYYY-MM-DD`` or None; the JSON substrate carries dates as
    strings, so the record is the format guarantor."""
    if value is None or _ISO_DATE.match(value):
        return []
    return [f"{name}: {value!r} is not an ISO date (YYYY-MM-DD)"]


# ── era standards: the keystone component ─────────────────────────────────

@dataclass(frozen=True)
class StandardRef(SpecRecord):
    """One standard sheet in force on the project: the drawing code as
    printed on the title sheet (``CSB-1-55``, ``PSID-1-99``…) and the
    revision date printed beside it.  ``date=None`` means the title sheet
    listed the code without a date (or it has not been read yet) — the
    catalog join resolves it."""

    code: str = spec_field(desc="drawing number as printed, e.g. RB-1-55")
    date: str | None = spec_field(None, desc="revision date, ISO YYYY-MM-DD")

    def _cross_validate(self):
        problems = [] if self.code.strip() else ["code: blank"]
        return problems + _bad_date("date", self.date)


@dataclass(frozen=True)
class EraStandardsRecord(SpecRecord):
    """The standards regime a project was designed and sold under.

    For plan-holding projects this is **read off the title sheet**, not
    inferred: the sheet lists the SCDs with revision dates and the CMS
    spec year.  For plan-less historic bridges the era registry supplies
    the set in force at ``spec_year`` / the letting date, and every field
    resolved that way is provenance-marked ``standard-default``.

    Manual editions are free-text labels validated against the
    hand-curated edition registry on the application side (a dozen rows
    per manual, not a schema concern here).
    """

    spec_year: int | None = spec_field(
        None, ge=1900, desc="CMS construction-spec year off the title sheet")
    scds: tuple[StandardRef, ...] = spec_field(
        (), desc="standard construction drawings listed on the title sheet")
    plan_inserts: tuple[StandardRef, ...] = spec_field(
        (), desc="plan insert sheets (PIS collection)")
    sbd_set: tuple[StandardRef, ...] = spec_field(
        (), desc="standard bridge drawings in force")
    bdm_edition: str | None = spec_field(
        None, desc="Bridge Design Manual edition label")
    ld_vol1_edition: str | None = spec_field(
        None, desc="L&D Manual Volume 1 edition label")
    ld_vol2_edition: str | None = spec_field(None)
    ld_vol3_edition: str | None = spec_field(None)

    def _cross_validate(self):
        problems: list[str] = []
        for group in ("scds", "plan_inserts", "sbd_set"):
            for i, ref in enumerate(getattr(self, group)):
                problems += [f"{group}[{i}].{p}" for p in ref.validate()]
        return problems

    def standard_date(self, code: str) -> str | None:
        """The revision date recorded for ``code`` (searched across all
        three collections), or None."""
        want = code.strip().upper()
        for ref in (*self.scds, *self.plan_inserts, *self.sbd_set):
            if ref.code.strip().upper() == want:
                return ref.date
        return None


# ── thin component records ────────────────────────────────────────────────

@dataclass(frozen=True)
class MOTRecord(SpecRecord):
    """Maintenance-of-traffic, at the complexity level MOT notes yield:
    the scheme, phase count, and what is maintained through the work."""

    scheme: str | None = spec_field(
        None, enum=("detour", "part_width", "phased", "runaround",
                    "closure", "night_work", "other"),
        desc="governing traffic-control scheme")
    n_phases: int | None = spec_field(None, ge=1)
    detour_length_mi: float | None = spec_field(None, unit="mi", ge=0.0)
    temp_structure: bool = spec_field(
        False, desc="temporary runaround structure in the MOT plan")
    barrier_types: tuple[str, ...] = spec_field(
        (), desc="temporary barrier designations, e.g. PCB-91")
    lanes_maintained: int | None = spec_field(None, ge=0)
    min_lane_width_ft: float | None = spec_field(None, unit="ft", gt=0.0)

    def _cross_validate(self):
        if any(not isinstance(b, str) or not b.strip()
               for b in self.barrier_types):
            return ["barrier_types: entries must be non-blank strings"]
        return []


@dataclass(frozen=True)
class RERecord(SpecRecord):
    """Real estate, as the RE summary tabulates it: parcel counts by
    take type and the utility-relocation load."""

    n_parcels: int | None = spec_field(None, ge=0,
                                       desc="total parcels touched")
    n_takes_fee: int | None = spec_field(None, ge=0, desc="fee-simple takes")
    n_takes_permanent_easement: int | None = spec_field(None, ge=0)
    n_takes_temporary_easement: int | None = spec_field(None, ge=0)
    n_utility_relocations: int | None = spec_field(None, ge=0)
    n_relocations_residential: int | None = spec_field(
        None, ge=0, desc="displaced residences/businesses")


@dataclass(frozen=True)
class SurveyRecord(SpecRecord):
    """Survey control as the title/schematic sheets state it — the datum
    era matters for georeferencing old plans."""

    horizontal_datum: str | None = spec_field(
        None, desc="e.g. NAD27, NAD83(1986), NAD83(2011)")
    vertical_datum: str | None = spec_field(
        None, desc="e.g. NGVD29, NAVD88")
    n_control_monuments: int | None = spec_field(None, ge=0)
    row_monumented: bool | None = spec_field(
        None, desc="ROW monumentation shown in the plan")


# ── the project container ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ProjectRecord(ElementRecord):
    """One construction project (a PID / contract sale): the thin parent
    over the era-standards keystone and the per-discipline components.
    Bridge components live as the existing per-SFN element records
    (:class:`~civilpy.structural.bim_spec.BridgeLayoutRecord` and
    friends), joined to this record through :attr:`sfns` — a project does
    not restate them."""

    pid: str = spec_field(desc="ODOT project id (ELLIS PID)")
    sfns: tuple[str, ...] = spec_field(
        (), desc="structure file numbers the contract touches")
    district: int | None = spec_field(None, ge=1)
    county: str | None = spec_field(None, desc="3-letter county code")
    route: str | None = spec_field(None, desc="e.g. SR-7, IR-70")
    letting_date: str | None = spec_field(
        None, desc="plan sale/letting date, ISO YYYY-MM-DD")
    work_category: str | None = spec_field(
        None, desc="e.g. bridge replacement, rehabilitation")
    era: EraStandardsRecord | None = spec_field(None)
    mot: MOTRecord | None = spec_field(None)
    real_estate: RERecord | None = spec_field(None)
    survey: SurveyRecord | None = spec_field(None)
    provenance: Provenance | None = spec_field(None)

    BIM_TYPE = "project"
    SUBTYPE = "record"

    def __post_init__(self):
        if self.provenance is None:
            object.__setattr__(self, "provenance", Provenance())

    def _cross_validate(self):
        problems = [] if self.pid.strip() else ["pid: blank"]
        if any(not isinstance(s, str) or not s.strip() for s in self.sfns):
            problems.append("sfns: entries must be non-blank strings")
        return problems + _bad_date("letting_date", self.letting_date)

    # ── similarity export ────────────────────────────────────────────
    def features(self) -> dict:
        """The flat feature dict the PCA→kNN similarity pipeline
        consumes: JSON scalars only — numbers for numerics, strings for
        categoricals (the pipeline's ``OneHotEncoder`` expands them),
        None for genuinely unknown.  Keyed by :data:`FEATURES_VERSION`
        so persisted vectors are reproducible."""
        era = self.era
        mot = self.mot
        re_ = self.real_estate
        year = None
        if self.letting_date:
            year = int(self.letting_date[:4])
        elif era is not None and era.spec_year is not None:
            year = era.spec_year
        return {
            "features_version": FEATURES_VERSION,
            # scope
            "n_bridges": len(self.sfns),
            "district": str(self.district) if self.district else None,
            "county": self.county,
            "work_category": self.work_category,
            "letting_year": year,
            # era
            "spec_year": era.spec_year if era else None,
            "n_scds": len(era.scds) if era else None,
            "n_plan_inserts": len(era.plan_inserts) if era else None,
            # MOT complexity
            "mot_scheme": mot.scheme if mot else None,
            "mot_phases": mot.n_phases if mot else None,
            "mot_detour_mi": mot.detour_length_mi if mot else None,
            "mot_temp_structure": (int(mot.temp_structure)
                                   if mot else None),
            # RE load
            "re_parcels": re_.n_parcels if re_ else None,
            "re_utility_relocations": (re_.n_utility_relocations
                                       if re_ else None),
        }
