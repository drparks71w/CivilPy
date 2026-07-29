#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT prestressed concrete box beam construction details (PSBD-1-25).

Transcribed from the Ohio DOT Standard Bridge Drawing PSBD-1-25,
"Prestressed Concrete Box Beam Details" (Office of Structural Engineering,
2025-07-18, rev. 2026-01-16, 6 sheets).  Captured here: design-stress and
material specs, transverse tie rod and anchor dowel details, shear-key
grouting, intermediate-diaphragm placement rules, the available beam
depths, and the standard steel-reinforced elastomeric bearing pads (B1/B2)
with their design data.

The standard box-beam *strand patterns*, eccentricities, camber, and *load
ratings* live on the companion design data sheet PSBDD-1-25
(:data:`DESIGN_DATA_SHEET`); those are carried in
:mod:`civilpy.structural.odot.box_beam_design`.

Lengths are in inches, forces in kips, stresses/moduli in ksi unless a
field name says otherwise.  Values are spot-checked against the drawing in
the test suite; the drawing remains the controlling document.
"""

import math
from dataclasses import dataclass

#: Companion design data sheet (strand tables, camber, load ratings),
#: transcribed in :mod:`civilpy.structural.odot.box_beam_design`.
DESIGN_DATA_SHEET = "PSBDD-1-25"

#: Standard box-beam depths, inches (PSBD-1-25 sheet 4/6).
BOX_BEAM_DEPTHS: tuple[int, ...] = (17, 21, 27, 33, 42)

#: Standard (and only current) box-beam width, inches. Earlier editions of
#: this drawing (PSBD-2-07) also cataloged a 36 in wide beam; PSBD-1-25
#: carries 48 in wide adjacent box beams only.
BOX_WIDTH_IN = 48.0

#: Maximum structure skew this standard applies to, degrees.
MAX_SKEW_DEG = 30.0

# ---------------------------------------------------------- cross section
# Void / flange geometry (PSBD-1-25 sheet 3/6, "36 in" and "48 in wide
# beams" section views). The top flange, bottom flange, and both webs share
# one wall thickness across every depth and width; the void corners carry a
# uniform fillet. Both values are confirmed self-consistent against the
# drawing's own callouts: void width = width - 2*wall (48 - 11 = 37 in;
# checked against the drawn "37"" void width) and void height = depth -
# 2*wall (e.g. 27 - 11 = 16 in, matching the drawn "16"" void height).

#: Top/bottom flange thickness, inches -- PSBD-1-25 sheet 2/6 LEFT
#: dimension chain (5 1/2" | void | 5 1/2"), identical at every depth, so
#: the void is centred on the beam.  Verified: this geometry reproduces
#: the sheet 4/6 published Ab, Yb and Ib to 0.2% at all five depths.
BOX_FLANGE_THICKNESS_IN = 5.5
#: Side web thickness, inches (sheet 2/6: 6" | 3'-0" | 6" bottom chain).
BOX_WEB_THICKNESS_IN = 6.0
#: Void corner fillet, inches (square).  Only the 17 in beam uses
#: 1 1/2" x 1 1/2"; every deeper beam uses 3" x 3".
BOX_VOID_FILLET_IN = 3.0
BOX_VOID_FILLET_SHALLOW_IN = 1.5

# Exterior side-face (shear key) profile, PSBD-1-25 sheet 2/6 RIGHT
# dimension chain -- 5" | (D - 10) | 5" -- read off the drawing:
#   0 .. 5              full width (48 in), the bearing band
#   5 .. 6.25           1 1/4" x 1 1/4" chamfer inward
#   6.25 .. D-5.5       keyway recess, 1 1/4" deep each side
#   D-5.5 .. D-5        1/2" x 1/2" chamfer outward
#   D-5 .. D            top band, recessed 3/4" each side (46 1/2" wide)
#: Height of the full-width band at the soffit, inches.
KEYWAY_BOTTOM_BAND_IN = 5.0
#: Lower chamfer leg into the keyway recess, inches.
KEYWAY_LOWER_CHAMFER_IN = 1.25
#: Depth of the keyway recess from the nominal face, inches.
KEYWAY_RECESS_DEPTH_IN = 1.25
#: Upper chamfer leg out of the keyway recess, inches.
KEYWAY_UPPER_CHAMFER_IN = 0.5
#: Height of the top band, inches, and how far it is set in per side.
KEYWAY_TOP_BAND_IN = 5.0
KEYWAY_TOP_SETBACK_IN = 0.75
#: 3/4 in x 3/4 in chamfer at each bottom (soffit) corner (ODOT's standard
#: chamfer), so the soffit is 46.5 in wide on a 48 in beam.  The top
#: corners are square.  Not dimensioned on sheet 2/6 -- recovered from the
#: published areas, which it reproduces to +-0.01% at all five depths
#: (1 in gives -0.07%, 1 1/2 in gives -0.25%).
BOX_BOTTOM_CHAMFER_IN = 0.75

#: Composite (CIP) topping: structural thickness carried in the composite
#: section properties, plus a non-structural monolithic wearing surface on
#: top of it (PSBD-1-25 sheet 4/6 section-properties note).
COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN = 5.0
COMPOSITE_SLAB_WEARING_SURFACE_IN = 1.0
#: E_slab / E_beam used to compute the tabulated composite section
#: properties (PSBD-1-25 sheet 4/6 note).
COMPOSITE_MODULAR_RATIO = 0.90

# ── solid (voidless) blocks ──────────────────────────────────────────────
# The void does not run the full length: the beam is cast solid at each end
# and through each intermediate diaphragm (PSBD-1-25 sheets 3 and 4).  The
# end block houses the end diaphragm, the anchor dowels and the lifting
# inserts; the intermediate block is the diaphragm itself.  A model that
# runs the voided section end to end understates the end reaction by ~30%.

#: Length of the solid block at each beam end, inches: 3'-3" on the 27/33/42
#: in beams, 2'-9" on the 17/21 in beams (PSBD-1-25 sheet 3).
SOLID_END_BLOCK_IN = 39.0
SOLID_END_BLOCK_SHALLOW_IN = 33.0

#: Longitudinal length of the solid block at an intermediate diaphragm,
#: inches, at zero skew (PSBD-1-25 sheet 4).  Skewed beams widen it to
#: ``X/2 + 6`` where ``X = width * tan(theta)``.
SOLID_DIAPHRAGM_BLOCK_IN = 18.0


def solid_end_block_in(depth_in: int) -> float:
    """Length of the solid end block for a beam of ``depth_in``."""
    if depth_in not in BOX_BEAM_DEPTHS:
        raise ValueError(f"non-standard beam depth {depth_in} in")
    return (SOLID_END_BLOCK_SHALLOW_IN if depth_in <= 21
            else SOLID_END_BLOCK_IN)


def solid_diaphragm_block_in(skew_deg: float = 0.0,
                             width_in: float = BOX_WIDTH_IN) -> float:
    """Longitudinal length of an intermediate diaphragm's solid block.

    Zero skew gives :data:`SOLID_DIAPHRAGM_BLOCK_IN`; a skewed beam needs
    ``X/2 + 6`` inches, ``X = width * tan(skew)``, so the block still
    contains the full diaphragm once it runs on the bias.
    """
    if not skew_deg:
        return SOLID_DIAPHRAGM_BLOCK_IN
    x = width_in * math.tan(math.radians(float(skew_deg)))
    return max(SOLID_DIAPHRAGM_BLOCK_IN, x / 2.0 + 6.0)


# ── BDM dead-load rules ──────────────────────────────────────────────────
# The wearing surface a box beam carries is decided by BDM 309.1, and it
# is NOT a free choice -- it follows from composite vs. non-composite:
#
#   309.1.A  1 in monolithic concrete wearing surface: "the top 1-in of a
#            concrete deck slab.  Do not include the top 1-in thickness in
#            the structural design of the deck slab or as part of the
#            composite section."   -> composite (CB) beams
#   309.1.B  3 in asphalt concrete: "the minimum asphaltic concrete
#            wearing surface on non-composite prestressed box beams.  Use
#            ... only on non-composite prestressed box beams."
#            -> non-composite (B) beams, 8 in max per BDM 308.2.3.3
#
# so :data:`COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN` +
# :data:`COMPOSITE_SLAB_WEARING_SURFACE_IN` = 6 in is exactly the
# BDM 308.2.3.3.c minimum composite deck, split at the 309.1.A line.

#: Future wearing surface allowance, ksf.  BDM 303.1.2: "Design all new
#: bridges that carry highway traffic for a future wearing surface (FWS)
#: of 0.060-ksf."  Unqualified -- it applies whether or not the bridge
#: also carries an asphalt wearing surface today.  Two exceptions in the
#: manual: temporary structures take 0.0 ksf (BDM 501), and FWS is
#: excluded from the dead load used for shop camber (BDM 308.2.2.1.f).
BDM_FUTURE_WEARING_SURFACE_KSF = 0.060

#: Minimum composite deck slab on prestressed box beams, inches
#: (BDM 308.2.3.3.c, "#6 bars, longitudinal at 18-in max, transverse at
#: 9-in max").
BDM_COMPOSITE_DECK_MIN_IN = 6.0

#: Asphalt concrete wearing surface on NON-composite box beams, inches:
#: 3 in minimum (BDM 309.1.B, two 1.5 in lifts of Item 441), 8 in maximum
#: (BDM 308.2.3.3).  The first lift is placed at variable thickness to
#: take up camber and grade, so the mean is often thicker than 3 in --
#: use the computed topping depth (BDM 308.2.3.3.e) for a real design.
BDM_ASPHALT_MIN_IN = 3.0
BDM_ASPHALT_MAX_IN = 8.0

#: Unit weights, pcf, from BDM 909 ("assumptions ... while performing the
#: load rating analysis unless more accurate site information is
#: available").  Note asphalt is **145 pcf**, not the 140 pcf of LRFD
#: Table 3.5.1-1.
BDM_ASPHALT_PCF = 145.0
BDM_CONCRETE_PCF = 150.0
BDM_LATEX_MODIFIED_CONCRETE_PCF = 150.0
BDM_SOIL_PCF = 120.0
BDM_STEEL_PCF = 490.0


def box_void_dimensions(depth_in: float, width_in: float = BOX_WIDTH_IN
                         ) -> tuple[float, float]:
    """Void ``(width, height)`` in inches for a box beam of ``depth_in`` /
    ``width_in``: :data:`BOX_WEB_THICKNESS_IN` webs each side,
    :data:`BOX_FLANGE_THICKNESS_IN` flanges top and bottom (PSBD-1-25
    sheet 2/6 dimension chains)."""
    return (width_in - 2.0 * BOX_WEB_THICKNESS_IN,
            depth_in - 2.0 * BOX_FLANGE_THICKNESS_IN)


@dataclass(frozen=True)
class BoxSectionProperties:
    """Non-composite ("beam only") and composite section properties for one
    standard box-beam depth (PSBD-1-25 sheet 4/6 tables). Lengths in inches;
    ``area`` in in^2, ``i``/``ic`` in in^4, ``zt``/``zb``/``ztc``/``zbc`` in
    in^3. The composite values assume the standard
    :data:`COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN` topping at
    :data:`COMPOSITE_MODULAR_RATIO`; they apply to any beam of this depth
    when a CIP composite slab is cast, independent of which design table
    (composite vs. non-composite strand pattern) governs the beam itself.
    """

    depth: int              # in
    width: float = BOX_WIDTH_IN   # in
    area: float = 0.0        # Ab, in^2 (beam only)
    i: float = 0.0            # Ib, in^4 (beam only)
    yb: float = 0.0           # in, beam-only centroid above soffit
    zt: float = 0.0           # in^3
    zb: float = 0.0           # in^3
    ic: float = 0.0           # in^4 (composite)
    ybc: float = 0.0          # in, composite centroid above soffit
    ztc: float = 0.0          # in^3 (composite)
    zbc: float = 0.0          # in^3 (composite)


#: 48 in wide box-beam section properties by depth, as published on
#: PSBD-1-25 sheet 4/6.
#:
#: VERIFIED (2026-07-28) against the section dimensioned on sheet 2/6:
#: recomputing Ab, Yb and Ib from that geometry reproduces every value in
#: this table to within 0.2% (the residual is the small exterior corner
#: chamfers, which the polygon does not draw).  The table is internally
#: self-consistent as well -- S = I/c closes both beam-only and composite.
BOX_SECTION_PROPERTIES: dict[int, BoxSectionProperties] = {
    17: BoxSectionProperties(17, area=580.8, i=18652, yb=8.42, zt=2175, zb=2214,
                              ic=39506, ybc=11.59, ztc=7302, zbc=3409),
    21: BoxSectionProperties(21, area=632.3, i=33551, yb=10.40, zt=3165, zb=3226,
                              ic=63190, ybc=13.92, ztc=8925, zbc=4540),
    27: BoxSectionProperties(27, area=689.3, i=65398, yb=13.38, zt=4802, zb=4888,
                              ic=111083, ybc=17.44, ztc=11620, zbc=6369),
    33: BoxSectionProperties(33, area=746.2, i=109652, yb=16.50, zt=6646, zb=6646,
                              ic=175131, ybc=20.90, ztc=14474, zbc=8379),
    42: BoxSectionProperties(42, area=831.8, i=201537, yb=20.82, zt=9515, zb=9680,
                              ic=303890, ybc=26.00, ztc=18993, zbc=11688),
}

#: The superseded PSBD-2-07 (2007) sheet 4/4 "48 in wide box beam" table.
#: That standard's section is geometrically DIFFERENT from PSBD-1-25:
#: 5 1/2 in uniform walls and a 37 in wide void.  Use these when rating
#: existing bridges built under PSBD-2-07 and earlier; the 12 in depth of
#: that table is omitted because PSBD-1-25 dropped it.
PSBD_2_07_SECTION_PROPERTIES: dict[int, BoxSectionProperties] = {
    17: BoxSectionProperties(17, area=590.3, i=18819, yb=8.44, zt=2198, zb=2230,
                              ic=38620, ybc=11.40, ztc=6898, zbc=3387),
    21: BoxSectionProperties(21, area=647.8, i=33884, yb=10.42, zt=3202, zb=3253,
                              ic=62057, ybc=13.69, ztc=8489, zbc=4533),
    27: BoxSectionProperties(27, area=713.8, i=66222, yb=13.39, zt=4866, zb=4945,
                              ic=109704, ybc=17.13, ztc=11119, zbc=6403),
    33: BoxSectionProperties(33, area=774.5, i=111342, yb=16.33, zt=6681, zb=6816,
                              ic=173831, ybc=20.51, ztc=13922, zbc=8474),
    42: BoxSectionProperties(42, area=873.5, i=205459, yb=20.78, zt=9684, zb=9886,
                              ic=303315, ybc=25.49, ztc=18367, zbc=11901),
}


def box_section_properties(depth_in: int) -> BoxSectionProperties:
    """Look up the 48 in wide box-beam section properties for a standard
    depth (17/21/27/33/42 in)."""
    try:
        return BOX_SECTION_PROPERTIES[int(depth_in)]
    except KeyError:
        raise ValueError(
            f"non-standard beam depth {depth_in} in; choose one of "
            f"{BOX_BEAM_DEPTHS}")


@dataclass(frozen=True)
class BoxBeamDesignSpec:
    """Design-stress and material specifications (PSBD-1-25 sheet 1/6).

    Concrete strengths are designer-selected ranges; the strand and
    reinforcing values are fixed by the standard.  Stresses in ksi.
    """

    #: Designer-selected 28-day concrete strength range, ksi.
    fc_28day_range: tuple[float, float] = (5.5, 7.0)
    #: Designer-selected release strength range, ksi.
    fci_release_range: tuple[float, float] = (4.0, 5.0)
    #: Cast-in-place (composite topping) concrete strength, ksi.
    fc_cast_in_place: float = 4.5
    #: Reinforcing steel minimum yield, ksi (C&MS 709.00).
    fy_reinforcing: float = 60.0
    #: Prestressing strand grade (ASTM A416, C&MS 711.27).
    strand_grade: int = 270
    #: Strand diameter, inches (0.5 in, 7-wire low-relaxation).
    strand_diameter: float = 0.5
    #: Nominal strand cross-sectional area options, in^2.
    strand_area_options: tuple[float, ...] = (0.153, 0.167)


#: Box-beam design/material specification (PSBD-1-25 sheet 1/6).
DESIGN_SPEC = BoxBeamDesignSpec()


@dataclass(frozen=True)
class TieRodDetail:
    """Transverse tie rod details (PSBD-1-25 sheets 1 & 4)."""

    diameter: float = 1.0           # in, ASTM A307 Grade 307A
    thread_root_min_diameter: float = 0.838  # in (rolled threads)
    torque_ft_lb: float = 250.0
    plate_washer: str = "4 x 4 x 1/2"
    hole_min_diameter: float = 2.0  # in
    hole_max_diameter: float = 3.0  # in
    max_beams_per_rod: int = 3

    def vertical_position(self, beam_depth: int) -> float:
        """Tie-rod height above the beam soffit, inches: 9 in for 17-27 in
        deep beams, 14 in for 33-42 in deep beams (sheet 4/6)."""
        if beam_depth not in BOX_BEAM_DEPTHS:
            raise ValueError(f"non-standard beam depth {beam_depth} in")
        return 9.0 if beam_depth <= 27 else 14.0


#: Transverse tie rod detail (PSBD-1-25).
TIE_ROD = TieRodDetail()


@dataclass(frozen=True)
class AnchorDowelDetail:
    """Anchor dowel details (PSBD-1-25 sheets 1 & 5)."""

    diameter: float = 1.0           # in, ASTM A311 Grade 1018 smooth rod
    beam_hole_diameter: float = 2.0  # in (2.5 in with compression seal joint)
    beam_hole_diameter_compression_seal: float = 2.5  # in (per EXJ-3-82)
    fixed_substructure_hole_min: float = 1.0625   # in (1-1/16)
    expansion_substructure_hole_min: float = 1.25  # in (1-1/4)


#: Anchor dowel detail (PSBD-1-25).
ANCHOR_DOWEL = AnchorDowelDetail()


@dataclass(frozen=True)
class ShearKeyDetail:
    """Shear-key details between adjacent box beams (PSBD-1-25 sheets 1 & 5)."""

    #: Grout fill depth from top of beam to bottom of throat, inches.
    grout_depth_from_top: float = 5.0
    #: Backer rod diameter for composite beams, inches (min).
    composite_backer_rod_min: float = 2.0
    #: End shear key depth at integral/semi-integral abutments, inches.
    end_shear_key_depth: float = 1.0
    #: End shear key width at integral/semi-integral abutments, inches.
    end_shear_key_width: float = 38.0


#: Shear-key detail (PSBD-1-25).
SHEAR_KEY = ShearKeyDetail()


def diaphragm_count(span_ft: float) -> int:
    """Number of intermediate diaphragms for a span, per PSBD-1-25 sheet 4/6:
    1 for spans <= 50 ft, 2 for 50 ft < span <= 75 ft, 3 for spans > 75 ft."""
    if span_ft <= 50.0:
        return 1
    if span_ft <= 75.0:
        return 2
    return 3


def diaphragm_end_offset(beam_depth: int) -> float:
    """Distance from beam end to the end diaphragm, inches (PSBD-1-25 sheet
    4/6): 24 in for 17/21 in deep beams, 30 in for 27/33/42 in deep beams."""
    if beam_depth not in BOX_BEAM_DEPTHS:
        raise ValueError(f"non-standard beam depth {beam_depth} in")
    return 24.0 if beam_depth <= 21 else 30.0


def diaphragm_stations_ft(span_ft: float, beam_depth: int) -> tuple[float, ...]:
    """Longitudinal station (ft, from the beam start) of each intermediate
    diaphragm: :func:`diaphragm_count` of them, evenly spaced between the
    :func:`diaphragm_end_offset` inset from each end (a single diaphragm sits
    at midspan). The drawing (sheet 4/6) states the count and the end offset
    but not an explicit multi-diaphragm spacing rule; even spacing between
    the end-offset points is the standard detailing assumption.
    """
    n = diaphragm_count(span_ft)
    offset_ft = diaphragm_end_offset(beam_depth) / 12.0
    if n == 1:
        return (span_ft / 2.0,)
    lo, hi = offset_ft, span_ft - offset_ft
    return tuple(lo + (hi - lo) * k / (n - 1) for k in range(n))


@dataclass(frozen=True)
class BearingPad:
    """A standard steel-reinforced elastomeric bearing pad (PSBD-1-25 sheet
    6/6 table).  Lengths in inches, load in kips, expansion length in feet."""

    name: str
    length: float           # L, in
    width: float            # W, in
    total_thickness: float  # T, in
    t_external: float       # te, in (external elastomer layer)
    t_internal: float       # ti, in (internal elastomer layer)
    t_steel: float          # ts, in (12 gage internal laminate)
    n_laminates: int        # N
    max_total_load: float   # kips
    max_expansion_length: float  # ft
    max_movement: float     # in (one direction)
    rotation_capacity: float = 0.024  # radians


#: Standard elastomeric bearing pads B1 and B2 (PSBD-1-25 sheet 6/6).
BEARING_PADS: dict[str, BearingPad] = {
    "B1": BearingPad("B1", 7.0, 11.0, 1.409, 0.35, 0.50, 0.1046, 2, 36.0,
                     92.0, 0.530),
    "B2": BearingPad("B2", 9.0, 14.0, 2.014, 0.35, 0.50, 0.1046, 3, 74.0,
                     147.0, 0.847),
}


@dataclass(frozen=True)
class BearingDesignData:
    """Elastomeric bearing design data (PSBD-1-25 sheet 6/6)."""

    durometer: int = 50
    #: Allowable compressive stress, ksi.
    allowable_compressive_stress: float = 1.25
    #: Shear modulus at 73 F for maximum compressive strength, ksi.
    shear_modulus_compressive: float = 0.095
    #: Shear modulus at 73 F for horizontal forces, ksi.
    shear_modulus_horizontal: float = 0.130
    #: 25-year creep deflection / instantaneous deflection, percent.
    creep_deflection_percent: float = 25.0
    #: Bearings required per beam.
    bearings_per_beam: int = 4
    #: Governing spec edition.
    spec_edition: str = "AASHTO LRFD BDS 10th Edition (2024)"


#: Elastomeric bearing design data (PSBD-1-25 sheet 6/6).
BEARING_DESIGN_DATA = BearingDesignData()


def bearing_pad(name: str) -> BearingPad:
    """Look up a standard bearing pad by name (``"B1"`` or ``"B2"``)."""
    return BEARING_PADS[name]


# ---------------------------------------------------------------- BD-1-11
# Beveled steel load plate used under box-beam bearings to take out roadway-
# grade rotation (Bearing Details for Box Beam Bridges, BD-1-11, rev.
# 2018-07-20).  Used when the elastomeric bearing alone cannot accommodate
# the grade rotation.


@dataclass(frozen=True)
class BeveledLoadPlate:
    """Beveled steel load plate detail (BD-1-11)."""

    min_thickness: float = 1.5          # in
    plate_grade: str = "ASTM A709 Gr 50"
    anchor_rod_diameter: float = 0.75   # in, ASTM A449
    plate_washer: str = "3 x 3 x 1/2"   # ASTM A36
    expansion_anchor_hole: float = 1.25  # in dia
    stud_yield: float = 50.0            # ksi (ASTM A108 end-welded stud)


#: Beveled load plate detail (BD-1-11).
BEVELED_LOAD_PLATE = BeveledLoadPlate()


def load_plate_bevel(
    longitudinal_grade: float, skew_deg: float
) -> tuple[float, float]:
    """Transverse and longitudinal bevels of the BD-1-11 load plate.

    The plate top is beveled to match the roadway grade resolved into the
    bearing's local axes (BD-1-11 bevel notes): the component across the
    bearing width is ``grade * sin(skew)`` and the component along the
    bearing length is ``grade * cos(skew)``.  ``longitudinal_grade`` is the
    roadway grade (rise/run, e.g. 0.04 for 4%); ``skew_deg`` is the
    structure skew angle in degrees.  Returns ``(transverse, longitudinal)``
    bevel slopes in the same rise/run units as the grade.
    """
    theta = math.radians(skew_deg)
    return (
        longitudinal_grade * math.sin(theta),
        longitudinal_grade * math.cos(theta),
    )


PointXYZ = tuple[float, float, float]  # (x, y, z) inches


@dataclass(frozen=True)
class LoadPlateLayout:
    """The generated BD-1-11 beveled load plate, sized to a bearing pad's
    plan footprint (``bearing_pad(name).length`` x ``.width``).

    ``top_face`` carries the bevel: each corner's Z is offset by its (x, y)
    distance from plate center times the transverse/longitudinal bevel
    slope, so the plate top is a single tilted plane (not warped)."""

    bevel_plate: BeveledLoadPlate
    bottom_face: tuple[PointXYZ, PointXYZ, PointXYZ, PointXYZ]
    top_face: tuple[PointXYZ, PointXYZ, PointXYZ, PointXYZ]
    notes: tuple[str, ...] = ()


def layout_load_plate(
    bearing_pad_name: str, longitudinal_grade: float = 0.0,
    skew_deg: float = 0.0, plate: BeveledLoadPlate = BEVELED_LOAD_PLATE,
) -> "LoadPlateLayout":
    """Generate the BD-1-11 beveled load plate sized to ``bearing_pad_name``
    (``"B1"`` or ``"B2"``, :func:`bearing_pad`), tilted per
    :func:`load_plate_bevel`. Origin at plate-bottom center, z = 0 at the
    bottom face; x = bearing length (beam axis), y = bearing width."""
    pad = bearing_pad(bearing_pad_name)
    half_l, half_w = pad.length / 2.0, pad.width / 2.0
    trans_bevel, long_bevel = load_plate_bevel(longitudinal_grade, skew_deg)
    t = plate.min_thickness

    bottom_face = ((-half_l, -half_w, 0.0), (half_l, -half_w, 0.0),
                   (half_l, half_w, 0.0), (-half_l, half_w, 0.0))

    def top_z(x: float, y: float) -> float:
        return t + x * long_bevel + y * trans_bevel

    top_face = tuple((x, y, top_z(x, y)) for (x, y, _) in bottom_face)

    notes = (
        f"BD-1-11 beveled load plate on a {bearing_pad_name} bearing pad "
        f"({pad.length:g} x {pad.width:g} in), grade {longitudinal_grade:.3f}, "
        f"skew {skew_deg:g} deg: transverse bevel {trans_bevel:.4f}, "
        f"longitudinal bevel {long_bevel:.4f}",
        "Not modeled: anchor rods/recesses, plate washers, preformed "
        "bearing pad, bearing markings, box-beam anchor hole spacing "
        "(varies by 36 in vs 48 in box width -- not tabulated here).",
    )

    return LoadPlateLayout(
        bevel_plate=plate, bottom_face=bottom_face, top_face=top_face,
        notes=notes,
    )
