"""
CivilPy
Copyright (C) 2019 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import sys
import pint
from pydantic import BaseModel, conint, constr, field_validator
from typing import Optional, List

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

units = pint.UnitRegistry()

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
    BL01: int  # 1-99 (State Code)
    BL02: Optional[int] = None  # 1-999 (County Code)
    BL03: Optional[int] = None  # 0-99999 (Place Code)
    BL04: Optional[int] = None  # MaxLength - 2 (Highway Agency District)
    BL05: Optional[float] = None  # -99.999999, 99.999999 (Latitude)

    # FIXED: Changed from int to float to accept coordinates like -82.148911
    BL06: Optional[float] = None  # -999.999999, 999.999999 (Longitude)

    BL07: Optional[str] = None  # MaxLength - 15 (Border Bridge Number)
    BL08: Optional[str] = None  # MaxLength - 2 (Border Bridge State or Country Code)
    BL09: Optional[str] = None  # MaxLength - 1 (Border Bridge Inspection Responsibility)
    BL10: Optional[str] = None  # MaxLength - 2 (Border Bridge Designated Lead State)
    BL11: Optional[str] = None  # MaxLength - 300 (Bridge Location)
    BL12: Optional[str] = None  # MaxLength - 300 (Metropolitan Planning Organization)

    BID01: str  # MaxLength - 15 (Bridge Number)
    BID02: Optional[str] = None  # MaxLength - 15 (Bridge Name)
    BID03: Optional[str] = None  # MaxLength - 120 (Previous Bridge Number)

    BCL01: Optional[str] = None  # MaxLength - 4 (Owner)
    BCL02: Optional[str] = None  # MaxLength - 4 (Maintenance Responsibility)
    BCL03: Optional[str] = None  # MaxLength - 30 (Federal or Tribal Land Access)
    BCL04: Optional[str] = None  # MaxLength - 1 (Historical Significance)
    BCL05: Optional[str] = None  # MaxLength - 1 (Toll)
    BCL06: Optional[str] = None  # MaxLength - 1 (Emergency Evacuation Designation)

    BRH01: Optional[str] = None  # MaxLength - 4 (Bridge Railings)
    BRH02: Optional[str] = None  # MaxLength - 4 (Transitions)

    BG01: Optional[float] = None  # 0-999999.9 (NBIS Bridge Length)
    BG02: Optional[float] = None  # 0-999999.9 (Total Bridge length)
    BG03: Optional[float] = None  # 0-9999.9 (Maximum Span Length)
    BG04: Optional[float] = None  # 0-9999.9 (Minimum Span Length)
    BG05: Optional[float] = None  # 0-999.9 (Bridge Width Out-to-Out)
    BG06: Optional[float] = None  # 0-999.9 (Bridge Width Curb-to-Curb)
    BG07: Optional[float] = None  # 0-99.9 (Left Curb or Sidewalk Width)
    BG08: Optional[float] = None  # 0-99.9 (Right Curb or Sidewalk Width)
    BG09: Optional[float] = None  # 0-999.9 (Approach Roadway Width)
    BG10: Optional[str] = None  # MaxLength - 1 (Bridge Median)
    BG11: Optional[int] = None  # 0-99 (Skew)
    BG12: Optional[str] = None  # MaxLength - 2 (Curved bridge)
    BG13: Optional[int] = None  # 0-9999 (Maximum Bridge Height)
    BG14: Optional[str] = None  # MaxLength - 1 (Sidehill Bridge)
    BG15: Optional[float] = None  # 0-999999999.9 (Irregular Deck Area)
    BG16: Optional[float] = None  # 0-999999999.9 (Calculated Deck Area)

    BLR01: Optional[str] = None  # MaxLength - 8 (Designed Load)
    BLR02: Optional[str] = None  # MaxLength - 4 (Designed Method)
    BLR03: Optional[str] = None  # Pattern = "^[0-9]{8}$" (Load Rating Date)
    BLR04: Optional[str] = None  # MaxLength - 4 (Load Rating Method)
    BLR05: Optional[float] = None  # 0-99.99 (Inventory Load Rating Factor)
    BLR06: Optional[float] = None  # 0-99.99 (Operating Load Rating Factor)
    BLR07: Optional[float] = None  # 0-99.99 (Controlling Legal Load Rating Factor)
    BLR08: Optional[str] = None  # MaxLength - 1 (Routine Permit Loads)

    BIR01: Optional[str] = None  # MaxLength - 1 (NSTM Inspection Required)
    BIR02: Optional[str] = None  # MaxLength - 1 (Fatigue Details)
    BIR03: Optional[str] = None  # MaxLength - 1 (Underwater Inspection Required)
    BIR04: Optional[str] = None  # MaxLength - 1 (Complex Feature)

    BC01: Optional[str] = None  # MaxLength - 1 (Deck Condition Rating)
    BC02: Optional[str] = None  # MaxLength - 1 (Superstructure Condition Rating)
    BC03: Optional[str] = None  # MaxLength - 1 (Substructure Condition Rating)
    BC04: Optional[str] = None  # MaxLength - 1 (Culvert Condition Rating)
    BC05: Optional[str] = None  # MaxLength - 1 (Bridge Railings Condition Rating)
    BC06: Optional[str] = None  # MaxLength - 1 (Bridge Railings Transitions Condition Rating)
    BC07: Optional[str] = None  # MaxLength - 1 (Bridge Bearings Condition Rating)
    BC08: Optional[str] = None  # MaxLength - 1 (Bridge Joints Condition Rating)
    BC09: Optional[str] = None  # MaxLength - 1 (Channel Condition Rating)
    BC10: Optional[str] = None  # MaxLength - 1 (Channel Protection Condition Rating)
    BC11: Optional[str] = None  # MaxLength - 4 (Scour Condition Rating)
    BC12: Optional[str] = None  # MaxLength - 1 (Bridge Condition Classification)
    BC13: Optional[str] = None  # MaxLength - 1 (Lowest Condition Rating Code)
    BC14: Optional[str] = None  # MaxLength - 1 (NSTM Inspection Condition)
    BC15: Optional[str] = None  # MaxLength - 1 (Underwater Inspection Condition)

    BAP01: Optional[str] = None  # MaxLength - 1 (Approach Roadway Alignment)
    BAP02: Optional[str] = None  # MaxLength - 5 (Overtopping Likelihood)
    BAP03: Optional[str] = None  # MaxLength - 5 (Scour Vulnerability)
    BAP04: Optional[str] = None  # MaxLength - 3 (Scour Plan of Action)
    BAP05: Optional[str] = None  # MaxLength - 1 (Seismic Vulnerability)

    BW01: Optional[int] = None  # 0-9999 (Year Built)

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