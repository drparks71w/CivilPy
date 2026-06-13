#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Catalog of Ohio DOT Standard Construction Drawings (SCDs).

This package transcribes the geometry, reinforcement, and design data
published on Ohio Department of Transportation standard bridge and roadway
drawings into structured, queryable Python objects.  Each catalog entry
cites its SCD number and revision date; the underlying drawings are
public-domain Ohio DOT documents.

Sub-modules:

``bridge_railing``
    Bridge railings and barriers (BR, SBR, TST, DBR, TBR, PCB series),
    each carrying its NCHRP 350 / MASH crash test level so it links to the
    Table A13.2-1 design forces in :mod:`civilpy.structural.aashto.lrfd`.

``guardrail``
    Midwest Guardrail System (MGS) roadway drawings: the standard system
    parameters (height, post spacing, blockouts, post sections) plus the
    series registry and the bridge terminal assemblies that tie a guardrail
    run into the cataloged bridge railings.

``box_beam``
    Prestressed concrete box beam construction details (PSBD-1-25): tie
    rods, anchor dowels, shear keys, diaphragm placement rules, and the
    standard elastomeric bearing pads.  The companion section/strand/load-
    rating sheet PSBDD-1-25 is referenced but not transcribed here.
"""

from civilpy.structural.odot.bridge_railing import (
    BRIDGE_RAILINGS,
    BridgeRailing,
    railing,
    railings_for_test_level,
)
from civilpy.structural.odot.guardrail import (
    MGS,
    MGS_DRAWINGS,
    MGS_POST_SPACINGS,
    MGS_STEEL_POSTS,
    MGSDrawing,
    MGSStandard,
    PostSpacing,
    SteelPost,
    bridge_terminal_assemblies,
    mgs_drawing,
    terminals_for_railing,
)
from civilpy.structural.odot.box_beam import (
    ANCHOR_DOWEL,
    BEARING_DESIGN_DATA,
    BEARING_PADS,
    BOX_BEAM_DEPTHS,
    DESIGN_DATA_SHEET,
    DESIGN_SPEC,
    SHEAR_KEY,
    TIE_ROD,
    AnchorDowelDetail,
    BearingDesignData,
    BearingPad,
    BoxBeamDesignSpec,
    ShearKeyDetail,
    TieRodDetail,
    bearing_pad,
    diaphragm_count,
    diaphragm_end_offset,
)

__all__ = [
    "BridgeRailing",
    "BRIDGE_RAILINGS",
    "railing",
    "railings_for_test_level",
    "MGS",
    "MGSStandard",
    "MGS_DRAWINGS",
    "MGSDrawing",
    "MGS_POST_SPACINGS",
    "PostSpacing",
    "MGS_STEEL_POSTS",
    "SteelPost",
    "mgs_drawing",
    "bridge_terminal_assemblies",
    "terminals_for_railing",
    "DESIGN_DATA_SHEET",
    "BOX_BEAM_DEPTHS",
    "BoxBeamDesignSpec",
    "DESIGN_SPEC",
    "TieRodDetail",
    "TIE_ROD",
    "AnchorDowelDetail",
    "ANCHOR_DOWEL",
    "ShearKeyDetail",
    "SHEAR_KEY",
    "BearingPad",
    "BEARING_PADS",
    "BearingDesignData",
    "BEARING_DESIGN_DATA",
    "bearing_pad",
    "diaphragm_count",
    "diaphragm_end_offset",
]
