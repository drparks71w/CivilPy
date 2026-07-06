#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

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
    standard elastomeric bearing pads.

``box_beam_design``
    Prestressed box beam standard designs and LRFR load ratings (PSBDD-1-25):
    strand patterns, eccentricities, camber, and rating factors for the
    composite (CB) and non-composite (B) families at five depths.

``deck_design``
    ODOT BDM 309.3 reinforced concrete deck design: the minimum-thickness
    formula, the mandatory design policy (LRFD 9.7.3 strip method, HL-93),
    and the BDM Figure 309-3 standard deck designs by effective span.

``rocker_bolster``
    Structural steel rocker and bolster bearing dimensions and capacities
    (RB-1-55).

``headwall``
    Cast-in-place half-height headwall dimension tables (HW-2.1 corrugated-
    metal/plastic, HW-2.2 concrete) plus the ``layout_headwall`` generator
    behind the HW-2.1 Grasshopper component: the rectangular circular-pipe
    headwall solid (end treatment "A"), battered back face, pipe opening.

``approach_slab``
    Reinforced concrete approach slab (AS-1-15): the reinforcing steel
    table, bar count/length formulas, seat and joint details, and the
    pure-Python layout generator behind the AS-1-15 Grasshopper component.

``drip_strip``
    Stainless steel drip strips for over-the-side drainage (DS-1-92):
    section profile, perforation pattern, railing-dependent placement,
    and the fascia run generator behind the DS-1-92 component.

``portable_barrier``
    Portable concrete barrier geometry (PCB-91): the New Jersey shape
    section, segment/joint/anchor layout behind the PCB-91 component
    (crash test levels stay in ``bridge_railing``).
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
    BOX_SECTION_PROPERTIES,
    BOX_VOID_FILLET_IN,
    BOX_WALL_THICKNESS_IN,
    BOX_WIDTH_IN,
    COMPOSITE_MODULAR_RATIO,
    COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN,
    COMPOSITE_SLAB_WEARING_SURFACE_IN,
    DESIGN_DATA_SHEET,
    DESIGN_SPEC,
    SHEAR_KEY,
    TIE_ROD,
    AnchorDowelDetail,
    BearingDesignData,
    BearingPad,
    BoxBeamDesignSpec,
    BoxSectionProperties,
    ShearKeyDetail,
    TieRodDetail,
    bearing_pad,
    box_section_properties,
    box_void_dimensions,
    diaphragm_count,
    diaphragm_end_offset,
    diaphragm_stations_ft,
    BEVELED_LOAD_PLATE,
    BeveledLoadPlate,
    load_plate_bevel,
)
from civilpy.structural.odot.rocker_bolster import (
    MAX_MOVEMENT,
    ROCKER_BOLSTERS,
    RockerBolster,
    rocker_bolster,
    smallest_for_load,
)
from civilpy.structural.odot.headwall import (
    HEADWALLS_BY_DIAMETER,
    HEADWALLS_CIRCULAR,
    HEADWALLS_CONCRETE_BY_DIAMETER,
    HEADWALLS_CONCRETE_CIRCULAR,
    HEADWALLS_CONCRETE_ELLIPTICAL,
    EllipticalHeadwall,
    Headwall,
    elliptical_headwall_for_rise,
    headwall_for_diameter,
)
from civilpy.structural.odot.box_beam_design import (
    BOX_BEAM_DESIGNS,
    BOX_BEAM_RATINGS,
    BOX_DESIGNATIONS,
    RATING_VEHICLES,
    STRAND_ROW_HEIGHTS_IN,
    BoxBeamDesign,
    BoxBeamRating,
    box_beam_design,
    box_beam_rating,
    designs_for_box,
    strand_group_height_in,
)
from civilpy.structural.odot.approach_slab import (
    APPROACH_SLAB_DESIGNS,
    ApproachSlabDesign,
    ApproachSlabInput,
    ApproachSlabLayout,
    anchor_bar_mark,
    approach_slab_design,
    layout_approach_slab,
)
from civilpy.structural.odot.drip_strip import (
    PLACEMENTS as DRIP_STRIP_PLACEMENTS,
    DripStripPlacement,
    StripRun,
    drip_strip_runs,
    strip_profile_in,
)
from civilpy.structural.odot.portable_barrier import (
    BarrierSegment,
    anchor_hole_stations_ft,
    barrier_run,
    profile_points_in as pcb_profile_points_in,
)
from civilpy.structural.odot.deck_design import (
    DESIGN_METHOD,
    MIN_DESIGN_HAUNCH,
    Haunch,
    haunch_depth_at,
    MAX_BEAM_SPACING_FT,
    MAX_OVERHANG_FT,
    MIN_BEAM_LINES,
    MIN_OVERHANG_THICKNESS,
    POLICY,
    PROHIBITED_METHODS,
    STANDARD_DECK_DESIGNS,
    VALID_RAILINGS,
    BarMat,
    DeckDesignPolicy,
    StandardDeckDesign,
    minimum_deck_thickness,
    overhang_thickness,
    secondary_longitudinal_reinforcement,
    standard_deck_design,
    structural_design_thickness,
)

__all__ = [
    "APPROACH_SLAB_DESIGNS",
    "ApproachSlabDesign",
    "ApproachSlabInput",
    "ApproachSlabLayout",
    "anchor_bar_mark",
    "approach_slab_design",
    "layout_approach_slab",
    "DRIP_STRIP_PLACEMENTS",
    "DripStripPlacement",
    "StripRun",
    "drip_strip_runs",
    "strip_profile_in",
    "BarrierSegment",
    "anchor_hole_stations_ft",
    "barrier_run",
    "pcb_profile_points_in",
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
    "BOX_WIDTH_IN",
    "BOX_WALL_THICKNESS_IN",
    "BOX_VOID_FILLET_IN",
    "COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN",
    "COMPOSITE_SLAB_WEARING_SURFACE_IN",
    "COMPOSITE_MODULAR_RATIO",
    "BoxSectionProperties",
    "BOX_SECTION_PROPERTIES",
    "box_section_properties",
    "box_void_dimensions",
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
    "diaphragm_stations_ft",
    "BeveledLoadPlate",
    "BEVELED_LOAD_PLATE",
    "load_plate_bevel",
    "RockerBolster",
    "ROCKER_BOLSTERS",
    "MAX_MOVEMENT",
    "rocker_bolster",
    "smallest_for_load",
    "Headwall",
    "HEADWALLS_CIRCULAR",
    "HEADWALLS_BY_DIAMETER",
    "headwall_for_diameter",
    "EllipticalHeadwall",
    "HEADWALLS_CONCRETE_CIRCULAR",
    "HEADWALLS_CONCRETE_BY_DIAMETER",
    "HEADWALLS_CONCRETE_ELLIPTICAL",
    "elliptical_headwall_for_rise",
    "BoxBeamDesign",
    "BoxBeamRating",
    "BOX_BEAM_DESIGNS",
    "BOX_BEAM_RATINGS",
    "BOX_DESIGNATIONS",
    "RATING_VEHICLES",
    "box_beam_design",
    "designs_for_box",
    "box_beam_rating",
    "STRAND_ROW_HEIGHTS_IN",
    "strand_group_height_in",
    "DESIGN_METHOD",
    "PROHIBITED_METHODS",
    "DeckDesignPolicy",
    "POLICY",
    "minimum_deck_thickness",
    "structural_design_thickness",
    "BarMat",
    "StandardDeckDesign",
    "STANDARD_DECK_DESIGNS",
    "MIN_BEAM_LINES",
    "MAX_BEAM_SPACING_FT",
    "MAX_OVERHANG_FT",
    "VALID_RAILINGS",
    "MIN_OVERHANG_THICKNESS",
    "standard_deck_design",
    "overhang_thickness",
    "secondary_longitudinal_reinforcement",
    "MIN_DESIGN_HAUNCH",
    "Haunch",
    "haunch_depth_at",
]
