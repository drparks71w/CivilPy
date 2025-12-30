"""
CivilPy
Copyright (C) 2019 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
from pydantic import BaseModel, conint, constr
from pydantic import ValidationError, StringConstraints, field_validator, Field
from typing import Optional, List, Annotated

from civilpy.state.ohio.DOT.legacy import (
    get_cty_from_code,
    state_code_conversion,
    get_3_digit_st_cd_from_2,
)
from civilpy.state.ohio.DOT.legacy import (
    ohio_counties,
    convert_latitudinal_values,
    convert_place_code,
)
from civilpy.state.ohio.DOT.legacy import (
    convert_longitudinal_values,
    TimsBridge,
    get_historic_bridge_data,
)

# SNBI Objects that need to be written to database tables
class Element(BaseModel):
    BE01: constr(max_length=4)              # maxLength 4 (Element Number)
    BE02: constr(max_length=4)              # maxLength 4 (Element Parent Number)
    BE03: Optional[conint(ge=0, le=99999999)] = None    # 0-99999999 (Element Total Quantity)
    BCS01: Optional[conint(ge=0, le=99999999)] = None   # 0-99999999 (Element Quantity CS1)
    BCS02: Optional[conint(ge=0, le=99999999)] = None   # 0-99999999 (Element Quantity CS2)
    BCS03: Optional[conint(ge=0, le=99999999)] = None   # 0-99999999 (Element Quantity CS3)
    BCS04: Optional[conint(ge=0, le=99999999)] = None   # 0-99999999 (Element Quantity CS4)

class Route(BaseModel):
    BRT01: str            # MaxLength - 3  (Route Designation)
    BRT02: Optional[str] = None  # MaxLength - 15 (Route Number)
    BRT03: Optional[str] = None  # MaxLength - 3  (Route Direction)
    BRT04: Optional[str] = None  # MaxLength - 1  (Route Type)
    BRT05: Optional[str] = None  # MaxLength - 1  (Service Type)

class Feature(BaseModel):
    # Attribute: type       # Additional Restrictions to implement
    BF01: Optional[str] = None               # Max length - 3 (Feature Type) - Made Optional
    BF02: Optional[str] = None     # Max Length - 1 (Feature Location)
    BF03: Optional[str] = None     # Max Length - 300 (Feature Name)
    BH01: Optional[str] = None     # Max Length - 3 (Functional Classification)
    BH02: Optional[str] = None     # Max Length - 5 (Urban Code)
    BH03: Optional[str] = None     # Max Length - 1 (NHS Designation)
    BH04: Optional[str] = None     # Max Length - 3 (National Highway Freight Network)
    BH05: Optional[str] = None     # Max Length - 1 (STRAHNET Designation)
    BH06: Optional[str] = None     # Max Length - 120 (LRS Route ID)
    BH07: Optional[float] = None   # 0 - 99999.9 (LRS Mile Point)
    BH08: Optional[int] = None     # 0 - 99 (Lanes on Highway)
    BH09: Optional[int] = None     # 0 - 99_999_999 (Annual Average Daily Traffic)
    BH10: Optional[int] = None     # 0 - 99_999_999 (Annual Average Daily Truck Traffic)
    BH11: Optional[int] = None     # 0 - 9999 (Year of Annual Average Daily Traffic)
    BH12: Optional[float] = None   # 0 - 99.9 (Highway Maximum Usable Vertical Clearance)
    BH13: Optional[float] = None   # 0 - 99.9 (Highway Minimum Vertical Clearance)
    BH14: Optional[float] = None   # 0 - 99.9 (Highway Minimum Horizontal Clearance, Left)
    BH15: Optional[float] = None   # 0 - 99.9 (Highway Minimum Horizontal Clearance, Right)
    BH16: Optional[float] = None   # 0 - 99.9 (Highway Maximum Usable Surface Width)
    BH17: Optional[int] = None     # 0 - 999 (Bypass Detour Length)
    BH18: Optional[str] = None     # Max Length 15 (Crossing Bridge Number)
    BRR01: Optional[str] = None    # Max Length 2 (Railroad Service Type)
    BRR02: Optional[float] = None  # 0 - 99.9 (Railroad Minimum Vertical Clearance)
    BRR03: Optional[float] = None  # 0 - 99.9 (Railroad Minimum Horizontal Offset)
    BN01: Optional[str] = None     # Max Length 1 (Navigable Waterway)
    BN02: Optional[float] = None   # 0 - 999.9 (Navigable Minimum Vertical Clearance)
    BN03: Optional[float] = None   # 0 - 999.9 (Movable Bridge Maximum Navigation Vertical Clearance)
    BN04: Optional[float] = None   # 0 - 9999.9 (Navigation Channel Width)
    BN05: Optional[float] = None   # 0 - 9999.9 (Navigation Channel Minimum Horizontal Clearance)
    BN06: Optional[str] = None     # Max Length - 3 (Substructure Navigation Protection)
    Routes: Optional[List[Route]] = None

class Inspection(BaseModel):
    BIE01: Optional[str] = None           # Max Length - 1 (Inspection Type)
    BIE02: Optional[str] = None           # Pattern = "^[0-9]{8}$" (Inspection Begin Date)
    BIE03: Optional[str] = None  # Pattern = "^[0-9]{8}$" (Inspection Completion Date)
    BIE04: Optional[str] = None  # Max Length - 15 (Nationally Certified Bridge Inspector)
    BIE05: Optional[int] = None  # 0-99 (Inspection Interval)
    BIE06: Optional[str] = None  # Pattern = "^[0-9]{8}$" (Inspection Due Date)
    BIE07: Optional[str] = None  # Max Length - 1 (Risk-Based Inspection Interval Method)
    BIE08: Optional[str] = None  # Pattern = "^[0-9]{8}$" (Inspection Quality Control Date)
    BIE09: Optional[str] = None  # Pattern = "^[0-9]{8}$" (Inspection Quality Assurance Date)
    BIE10: Optional[str] = None  # Pattern = "^[0-9]{8}$" (Inspection Data Update Date)
    BIE11: Optional[str] = None  # Max Length - 300 (Inspection Note)
    BIE12: Optional[str] = None  # Max Length - 120 (Inspection Equipment)

class PostingEvaluation(BaseModel):
    BEP01: Optional[str] = None    # Max Length - 15 (Legal Load Configuration)
    BEP02: Optional[float] = None  # 0-99.99 (Legal Load Rating Factor)
    BEP03: Optional[str] = None    # Max Length - 17 (Posting Type)
    BEP04: Optional[str] = None    # Max length - 15 (Posting Value)

class PostingStatus(BaseModel):
    BPS01: Optional[str] = None    # Max Length - 4 (Load Posting Status)
    BPS02: Optional[str] = None  # Pattern = "^[0-9]{8}$" (Posting Status Change Date)

class SpanSet(BaseModel):
    BSP01: Optional[str] = None            # Max Length - 3 (Span Configuration Designation)
    BSP02: Optional[int] = None  # 0-9999 (Number of Spans)
    BSP03: Optional[int] = None  # 0-999 (Number of Beam Lines)
    BSP04: Optional[str] = None  # Max Length - 4 (Span Material)
    BSP05: Optional[str] = None  # Max Length - 3 (Span Continuity)
    BSP06: Optional[str] = None  # Max Length - 4 (Span Type)
    BSP07: Optional[str] = None  # Max Length - 3 (Span Protective System)
    BSP08: Optional[str] = None  # Max Length - 2 (Deck Interaction)
    BSP09: Optional[str] = None  # Max Length - 4 (Deck Material and Type)
    BSP10: Optional[str] = None  # Max Length - 3 (Wearing Surface)
    BSP11: Optional[str] = None  # Max Length - 4 (Deck Protective System)
    BSP12: Optional[str] = None  # Max Length - 3 (Deck Reinforcing Protective System)
    BSP13: Optional[str] = None  # Max Length - 3 (Deck Stay-In-Place Forms)

class SubstructureSet(BaseModel):
    BSB01: Optional[str] = None            # Max Length - 3 (Substructure Configuration Designation)
    BSB02: Optional[int] = None  # 0-999 (Number of Substructure Units)
    BSB03: Optional[str] = None  # Max Length - 3 (Substructure Material)
    BSB04: Optional[str] = None  # Max Length - 3 (Substructure Type)
    BSB05: Optional[str] = None  # Max Length - 3 (Substructure Protective System)
    BSB06: Optional[str] = None  # Max Length - 3 (Foundation Type)
    BSB07: Optional[str] = None  # Max Length - 3 (Foundation Protective System)

class Work(BaseModel):
    BW02: Optional[int] = None   # 0-9999 (Year Work Performed)
    BW03: Optional[str] = None   # MaxLength - 120 (Work Performed)


class Bridge(BaseModel):
    BID01: Annotated[str, StringConstraints(max_length=15, min_length=1, strip_whitespace=True)]
    BID02: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    BID03: Annotated[str, StringConstraints(max_length=15, strip_whitespace=True)] = "0"

    @field_validator('BID02')
    @classmethod
    def validate_bid02_length(cls, v: str | None) -> str | None:
        if v and len(v) > 300:
            raise ValueError('BID02 (Bridge Name) must be <= 300 characters')
        return v

    BL01: Annotated[int, Field(eq=39)]                # B.L.01: State Code - Must be '39' for Ohio
    BL02: Annotated[int, Field(ge=1, le=999)]         # B.L.02: County Code - 1 to 999
    BL03: Annotated[int, Field(ge=0, le=99999)]       # B.L.03: Place Code - 0 to 99999
    BL04: Annotated[int, Field(ge=1, le=12)]          # B.L.04: Highway Agency District - 01 to 12
    BL05: Annotated[float, Field(ge=38.0, le=42.5)]   # B.L.05: Latitude - Ohio Bounding Box (Approx 38.0 to 42.5)
    BL06: Annotated[float, Field(ge=-85.0, le=-80.0)] # B.L.06: Longitude - Ohio Bounding Box (Approx -85.0 to -80.0)
    BL07: Annotated[str, StringConstraints(max_length=15, strip_whitespace=True)] | None = None # B.L.07: Border Bridge Number - Max length 15 (Optional but strict if present)
    BL08: Annotated[str, StringConstraints(max_length=2, strip_whitespace=True)] | None = None # B.L.08: Border Bridge State or Country Code - Max length 2
    BL09: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None # B.L.09: Border Bridge Inspection Responsibility - Max length 1
    BL10: Annotated[str, StringConstraints(max_length=2, strip_whitespace=True)] | None = None # B.L.10: Border Bridge Designated Lead State - Max length 2
    BL12: Annotated[str, StringConstraints(max_length=300, min_length=1, strip_whitespace=True)] # B.L.12: Metropolitan Planning Organization - Max length 300

    BCL01: Annotated[str, StringConstraints(max_length=4, min_length=1, strip_whitespace=True)] # Owner
    BCL02: Annotated[str, StringConstraints(max_length=4, min_length=1, strip_whitespace=True)] # Maint Resp
    BCL03: Annotated[str, StringConstraints(max_length=30, min_length=1, strip_whitespace=True)] # Fed./Tribal Land
    BCL04: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)] # Historic Significance
    BCL05: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)] # Toll
    BCL06: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)] # Emergency Evacuation

    BRH01: Annotated[str, StringConstraints(max_length=4, min_length=1, strip_whitespace=True)]  # MaxLength - 4 (Bridge Railings)
    BRH02: Annotated[str, StringConstraints(max_length=4, min_length=1, strip_whitespace=True)]  # MaxLength - 4 (Transitions)

    BG01: float  # NBIS Bridge Length (No strict max, could be huge)
    BG02: float  # Total Bridge Length
    BG03: float  # Maximum Span Length
    BG05: Annotated[float, Field(le=1000.0)]  # Bridge Width Out-to-Out - Max 1000 ft
    BG06: Annotated[float, Field(le=1000.0)]  # Bridge Width Curb-to-Curb - Max 1000 ft
    BG07: Annotated[float, Field(le=100.0)]  # Left Curb or Sidewalk Width - Max 100 ft
    BG08: Annotated[float, Field(le=100.0)]  # Right Curb or Sidewalk Width - Max 100 ft
    BG09: Annotated[float, Field(le=1000.0)]  # Approach Roadway Width - Max 1000 ft
    BG10: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]  # Bridge Median (Mandatory)
    BG11: Annotated[int, Field(ge=0, le=90)]  # Skew (0-90 degrees)
    BG12: Annotated[str, StringConstraints(max_length=2, strip_whitespace=True)] | None = None  # Curved Bridge
    BG13: int | None = None  # Maximum Bridge Height
    BG14: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None  # Sidehill Bridge
    BG15: float | None = None  # Irregular Deck Area
    BG16: float  # Calculated Deck Area

    BLR01: Annotated[str, StringConstraints(max_length=8, min_length=1, strip_whitespace=True)] # Design Load (Clean)
    BLR02: Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)] | None = None # Design Method (No Current Eqv)
    BLR03: Annotated[str, StringConstraints(max_length=8, strip_whitespace=True)] | None = None # Load Rating Date (No Current Eqv)
    BLR04: Annotated[str, StringConstraints(max_length=4, min_length=1, strip_whitespace=True)] # Load Rating Method (Clean)
    BLR05: float # Inventory Load Rating Factor (Clean)
    BLR06: float # Operating Load Rating Factor (Clean)
    BLR07: float | None = None # Controlling Legal Load Rating Factor (No Current Eqv)
    BLR08: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None # Routine Permit Loads (No Current Eqv)

    BIR01: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)] # NSTM Inspection Required (Clean)
    BIR02: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None # Fatigue Details (No Current Eqv)
    BIR03: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)] # Underwater Inspection Required (Clean)
    BIR04: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None # Complex Feature (No Current Eqv)

    BC01: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]  # Deck
    BC02: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]  # Super
    BC03: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]  # Sub
    BC04: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]  # Culvert
    BC09: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]  # Channel
    BC12: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]  # Condition Class
    BC13: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]  # Lowest Rating
    BC05: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None  # Railing
    BC06: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None  # Transitions
    BC07: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None  # Bearings
    BC08: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None  # Joints
    BC10: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None  # Channel Prot
    BC11: Annotated[str, StringConstraints(max_length=4, strip_whitespace=True)] | None = None  # Scour
    BC14: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None  # NSTM Cond
    BC15: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None  # Underwater Cond

    BAP01: Annotated[str, StringConstraints(max_length=1, min_length=1, strip_whitespace=True)]  # Approach Align
    BAP02: Annotated[str, StringConstraints(max_length=5, strip_whitespace=True)] | None = None  # Overtopping
    BAP03: Annotated[str, StringConstraints(max_length=5, strip_whitespace=True)] | None = None  # Scour Vuln
    BAP04: Annotated[str, StringConstraints(max_length=3, strip_whitespace=True)] | None = None  # Scour POA
    BAP05: Annotated[str, StringConstraints(max_length=1, strip_whitespace=True)] | None = None  # Seismic

    BW01: Annotated[int, Field(ge=1700, le=2030)] # Year Built (Range sanity check)

    # One to Many Relationships
    Elements: Optional[List[Element]] = None
    Routes: Optional[List[Route]] = None
    Features: Optional[List[Feature]] = None
    Inspections: Optional[List[Inspection]] = None
    PostingEvaluations: Optional[List[PostingEvaluation]] = None
    PostingStatuses: Optional[List[PostingStatus]] = None
    SpanSets: Optional[List[SpanSet]] = None
    SubstructureSets: Optional[List[SubstructureSet]] = None
    Works: Optional[List[Work]] = None