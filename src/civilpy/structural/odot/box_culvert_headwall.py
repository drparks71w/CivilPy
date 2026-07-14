#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT precast box culvert headwall / wingwall plan insert (BCHW).

Transcribed from the Ohio DOT "BCHW" plan insert (rev. 01-21-2022,
8 sheets: culvert & wingwall layout, wingwall elevation + foreslope wall
+ footing plan + sections, and several "SUBSET" sheets of alternate
wingwall corner configurations). The drawing remains the controlling
document.

**BCHW is a detailing template, not a dimensioned standard.** Unlike every
other SCD this package catalogs, none of its geometry is tabulated: every
dimension on the sheet (wall height ``H``, footing offsets ``a``/``b``/``c``,
foreslope-wall height ``hf``, cutoff-wall height ``hcw``, footing width
``Wf``, box wall thickness ``t box``, wingwall length ``L``, bar spacings)
is drawn as ``*`` or a blank ``@ _ c/c`` for the project engineer to fill
in from the actual box culvert design -- the sheet says so explicitly
("INSERT ODOT BOX CULVERT REINFORCING DESIGN HERE IF SPAN > 12'."). There
is therefore no guarded catalog lookup here: :func:`layout_wingwall` takes
every dimension as a required input (no defaults, nothing to look up) and
only performs the geometry the sheet's own sections make unambiguous
(:mod:`civilpy.structural.odot`'s ASTM C1577 precast box section catalog,
if/when encoded, is a separate concern -- BCHW is the cast-in-place
wingwall/foreslope-wall wrap-around, not the precast box itself).

What *is* cataloged here: the general notes (payment items, waterproofing,
porous backfill, weepholes, PEJF, lap splice lengths, epoxy coating) and
the eight standard rebar bend shapes (``TYPE-1`` .. ``TYPE-8``) the bar
list (WW5xx wingwall, FS5xx foreslope wall, F6xx footing, Z/V/W/X/Y series)
references -- :func:`bend_shape` turns a type + the project-supplied leg
lengths into a bend polyline, the same "shape template, project-supplied
legs" split as the sheet itself.
"""

import math
from dataclasses import dataclass, field

Point = tuple[float, float]  # (x, y) inches, local to the bend shape

SCD = "BCHW"
REVISION = "01-21-2022"

# ── general notes ─────────────────────────────────────────────────────────

REBAR_SPEC = "ASTM A615/A616/A617 Grade 60, epoxy coated"
LAP_SPLICE_FT = {5: 2.0 + 5.0 / 12.0, 6: 2.0 + 11.0 / 12.0}  # #5: 2'-5", #6: 2'-11"

PEJF_THICKNESS_IN = 1.0            # CMS 705.03, at the box/wingwall interface
POROUS_BACKFILL_THICKNESS_IN = 18.0  # 1'-6" thick, behind wingwalls only
POROUS_BACKFILL_BELOW_GRADE_IN = 12.0  # extends to 12 in below embankment surface
WEEPHOLE_DIA_IN = 4.0
WEEPHOLE_MIN_SPACING_FT = 0.0        # "a minimum of one per wingwall" (no min spacing)
WEEPHOLE_MAX_SPACING_FT = 10.0
WEEPHOLE_MIN_ABOVE_WATER_IN = 6.0
WEEPHOLE_MAX_ABOVE_WATER_IN = 12.0
CLEAR_COVER_IN = 3.0

# Waterproofing (culvert top only, not modeled geometrically -- payment note).
WATERPROOFING_TYPE_2_SPEC = "CMS 512.09 / 711.25"  # no pavement directly on culvert
WATERPROOFING_TYPE_3_SPEC = "CMS 512.10 / 711.29"  # pavement directly on culvert
WATERPROOFING_SIDE_EXTENT_FT = 1.0  # extends down the sides this far

#: Payment items (note block, "TOTALS CARRIED TO GENERAL SUMMARY SHEET").
PAY_ITEMS = {
    "structure_removed": ("202", "11000", "LUMP"),
    "unclassified_excavation_wingwall_footing": ("503", "11100", "LUMP"),
    "unclassified_excavation": ("503", "21100", "LUMP"),
    "sealing_concrete_surfaces": ("512", "46000", "SQ. YD."),
}


# ── rebar bend-shape legend (TYPE-1 .. TYPE-8) ───────────────────────────
#
# Every leg length (A/B/C/D) and angle (theta) is project-supplied -- the
# sheet draws the shape only. Points are in the bar's own bend plane,
# starting at the origin, in inches (bar dimensions are "out to out" per
# the sheet's legend note); civilpy does not assign inches vs. feet here
# since these are always detailing dimensions.

def bend_shape(type_: str, **legs: float) -> tuple[Point, ...]:
    """The bend polyline for one of the BCHW legend shapes.

    ``type_`` is ``"TYPE-1"`` .. ``"TYPE-8"``; ``legs`` supplies the leg
    lengths the sheet leaves blank (``A``, ``B``, ``C``, ``D`` as
    applicable, ``theta_deg`` for TYPE-2, ``skew_deg`` for TYPE-8).
    Raises ``ValueError`` naming the valid types and required legs."""
    try:
        spec = _BEND_SHAPES[type_]
    except KeyError:
        raise ValueError(
            f"BCHW bend types are {sorted(_BEND_SHAPES)}, not {type_!r}"
        ) from None
    required = spec["legs"]
    missing = [k for k in required if k not in legs]
    if missing:
        raise ValueError(f"{type_} requires legs {required}; missing {missing}")
    return spec["shape"](**{k: legs[k] for k in required})


def _type_1(A: float, B: float) -> tuple[Point, ...]:
    """Right-angle hook: vertical leg B, horizontal leg A."""
    return ((0.0, 0.0), (0.0, -B), (A, -B))


def _type_2(A: float, C: float, D: float, theta_deg: float) -> tuple[Point, ...]:
    """Leg C, a diagonal of length D at ``theta_deg`` off vertical, leg A."""
    p0 = (0.0, 0.0)
    p1 = (0.0, -C)
    p2 = (p1[0] + D * math.sin(math.radians(theta_deg)),
          p1[1] - D * math.cos(math.radians(theta_deg)))
    p3 = (p2[0] + A, p2[1])
    return (p0, p1, p2, p3)


def _type_3(A: float, B: float, C: float) -> tuple[Point, ...]:
    """Horizontal run A, a step up, horizontal run B, vertical leg C."""
    p0 = (0.0, 0.0)
    p1 = (A, 0.0)
    p2 = (A + B, C / 2.0)   # the sloped step, drawn as a single diagonal
    p3 = (A + B, C)
    return (p0, p1, p2, p3)


def _type_4(A: float, B: float, hook_extension_in: float = 3.0) -> tuple[Point, ...]:
    """Two legs bent 134.98 deg (~135 deg) apart; far leg carries the
    sheet's ``B+3"`` hook extension."""
    interior_deg = 134.98
    p0 = (0.0, 0.0)
    p1 = (A, 0.0)
    turn = 180.0 - interior_deg
    p2 = (p1[0] + (B + hook_extension_in) * math.cos(math.radians(turn)),
          p1[1] + (B + hook_extension_in) * math.sin(math.radians(turn)))
    return (p0, p1, p2)


def _type_5(A: float, B: float) -> tuple[Point, ...]:
    """Symmetric U / hairpin: leg A down, base B, leg A up."""
    return ((0.0, 0.0), (0.0, -A), (B, -A), (B, 0.0))


def _type_6(A: float, B: float, C: float, bar_size: int = 5) -> tuple[Point, ...]:
    """Symmetric hat: leg A, leg B, top C, leg B, leg A, with a
    :data:`LAP_SPLICE_FT` lap at each end (informational, not a bend)."""
    x = 0.0
    pts = [(x, 0.0)]
    for d in (A, B, C, B, A):
        x += d
        pts.append((x, 0.0))
    return tuple(pts)


def _type_7(A: float, B: float, C: float) -> tuple[Point, ...]:
    """Asymmetric U: a short leg A, base C, a full-height leg B."""
    return ((0.0, -A), (0.0, 0.0), (C, 0.0), (C, -B))


def _type_8(A: float, B: float, skew_deg: float,
           hook_extension_in: float = 3.0) -> tuple[Point, ...]:
    """Corner bar bent ``135 - skew/2`` deg; far leg carries the sheet's
    ``B+3"`` hook extension (the wingwall-to-headwall corner bar,
    WW504-type)."""
    interior_deg = 135.0 - skew_deg / 2.0
    p0 = (0.0, 0.0)
    p1 = (A, 0.0)
    turn = 180.0 - interior_deg
    p2 = (p1[0] + (B + hook_extension_in) * math.cos(math.radians(turn)),
          p1[1] + (B + hook_extension_in) * math.sin(math.radians(turn)))
    return (p0, p1, p2)


_BEND_SHAPES = {
    "TYPE-1": {"legs": ("A", "B"), "shape": _type_1},
    "TYPE-2": {"legs": ("A", "C", "D", "theta_deg"), "shape": _type_2},
    "TYPE-3": {"legs": ("A", "B", "C"), "shape": _type_3},
    "TYPE-4": {"legs": ("A", "B"), "shape": _type_4},
    "TYPE-5": {"legs": ("A", "B"), "shape": _type_5},
    "TYPE-6": {"legs": ("A", "B", "C"), "shape": _type_6},
    "TYPE-7": {"legs": ("A", "B", "C"), "shape": _type_7},
    "TYPE-8": {"legs": ("A", "B", "skew_deg"), "shape": _type_8},
}


# ── wingwall / foreslope wall layout (all dimensions project-supplied) ───
#
# Section A-A (foreslope wall) and the wingwall elevation both key off the
# same footing datum (z = 0 at the top of footing) and a 2:1 embankment
# slope from the finished ground line down past the wall. Every length
# below is required -- there is no catalog to default from.

PointXYZ = tuple[float, float, float]  # (x, y, z) feet


@dataclass(frozen=True)
class WingwallInput:
    """Project-supplied dimensions for one wingwall + foreslope wall
    (sheet 2/8 "WINGWALL ELEVATION" + "SECTION A-A"). All in feet unless
    named ``_in``. Nothing here is cataloged -- see the module docstring."""

    length_ft: float          # L, wingwall length along its flare
    skew_deg: float           # box culvert skew, theta
    wall_height_ft: float     # H, foreslope wall height
    foreslope_height_ft: float  # hf
    cutoff_wall_height_ft: float  # hcw, below top of footing (extends to -hcw)
    footing_width_ft: float   # Wf, perpendicular to the wall face
    box_wall_thickness_in: float  # t box; also the foreslope stem thickness
    embankment_slope: float = 2.0  # 2:1 (H:V), per the sheet


@dataclass(frozen=True)
class WingwallLayout:
    """The generated wingwall + foreslope wall.

    ``wingwall_outline`` is the wingwall's flared elevation (top of
    footing at z = 0, box-face height H tapering to hf at y = L);
    ``foreslope_section`` is the Section A-A profile (cutoff wall,
    footing top, foreslope-wall stem with its ``t box`` thickness, 2:1
    embankment line off the back face) in the Y-Z plane;
    ``footing_outline`` is the footing plan rectangle drawn at the
    bottom-of-cutoff elevation ``-hcw``."""

    inputs: WingwallInput
    wingwall_outline: tuple[PointXYZ, PointXYZ, PointXYZ, PointXYZ]
    foreslope_section: tuple[PointXYZ, ...]
    footing_outline: tuple[PointXYZ, PointXYZ, PointXYZ, PointXYZ]
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_wingwall(inp: WingwallInput) -> WingwallLayout:
    """Generate one wingwall + foreslope wall from fully project-supplied
    dimensions (no catalog lookup -- see the module docstring).

    Raises ``ValueError`` for a non-positive length/height/width."""
    for name in ("length_ft", "wall_height_ft", "foreslope_height_ft",
                 "cutoff_wall_height_ft", "footing_width_ft"):
        if getattr(inp, name) <= 0.0:
            raise ValueError(f"WingwallInput.{name} must be positive")

    L = inp.length_ft
    H = inp.wall_height_ft
    hf = inp.foreslope_height_ft
    hcw = inp.cutoff_wall_height_ft
    Wf = inp.footing_width_ft
    tan_skew = math.tan(math.radians(inp.skew_deg))

    def pt(u: float, y: float, z: float) -> PointXYZ:
        return (u + y * tan_skew, y, z)

    # Wingwall footprint: flares from the box wall face (y = 0) out to the
    # far end (y = L), sheared by the skew like every other flared-wingwall
    # layout in this package (approach_slab, sleeper_slab, full_height_headwall).
    wingwall_outline = (pt(0.0, 0.0, 0.0), pt(0.0, 0.0, H),
                       pt(0.0, L, hf), pt(0.0, L, 0.0))

    # Section A-A: footing at z = 0, cutoff wall down to -hcw, foreslope
    # wall up to hf with its stem thickness (t box -- the wall wraps the
    # box, so the stem matches the box wall), then the 2:1 embankment
    # line continuing up from the top of the BACK face.
    t_wall = inp.box_wall_thickness_in / 12.0
    embank_run = hf * inp.embankment_slope
    foreslope_section = (
        (0.0, -Wf / 2.0, -hcw),
        (0.0, -Wf / 2.0, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, hf),
        (0.0, t_wall, hf),
        (0.0, t_wall + embank_run, hf * 2.0),
    )

    footing_outline = (pt(-Wf / 2.0, 0.0, -hcw), pt(-Wf / 2.0, L, -hcw),
                       pt(Wf / 2.0, L, -hcw), pt(Wf / 2.0, 0.0, -hcw))

    notes = (
        f"BCHW wingwall: L {L:g} ft, H {H:g} ft, skew {inp.skew_deg:g} deg, "
        f"box wall t {inp.box_wall_thickness_in:g} in",
        "All dimensions are project-supplied (no catalog) -- the box "
        "culvert reinforcing design itself (ASTM C1577 precast section or "
        "cast-in-place, span > 12 ft) is a separate design, not this "
        "sheet's content.",
        "Not modeled: rebar (WW5xx/FS5xx/F6xx/Z/V/W/X/Y series -- see "
        "bend_shape() for the TYPE-1..8 bend legend), weepholes, porous "
        "backfill, PEJF, waterproofing, the wingwall-type corner "
        "configurations (SUBSET sheets 3-8).",
    )

    return WingwallLayout(
        inputs=inp,
        wingwall_outline=wingwall_outline,
        foreslope_section=foreslope_section,
        footing_outline=footing_outline,
        notes=notes,
    )


# ══════════════════════════════════════════════════════════════════════════
# Design Data sheets 1/6-6/6 ("Concrete Headwalls for Precast Box
# Culverts", ODOT Office of Structural Engineering / Hydraulics).  Unlike
# the plan inserts above, these sheets ARE tabulated: pick the headwall
# type from the roadway skew, compute the design height H, and read every
# dimension, reinforcing callout, and quantity from the tables.
# ══════════════════════════════════════════════════════════════════════════

HEADWALL_TYPES = ("A", "B", "C")
TYPE_B_SKEWS = (0.0, 15.0, 30.0, 45.0)

#: Culvert size limits (sheet 1/6): precast spans 8-20 ft in 2 ft
#: increments, rises 4-10 ft in 1 ft increments; ASTM C1433 covers spans
#: to 12 ft, larger spans need an OSE box design.
BOX_SPAN_RANGE_FT = (8.0, 20.0)
BOX_RISE_RANGE_FT = (4.0, 10.0)

#: Foreslope wall height above the top of the culvert (sheet 1/6):
#: 6 in or 1'-6" only.
FORESLOPE_WALL_HEIGHTS_IN = (6.0, 18.0)

#: 2:1 backslope on Type A and Type B wingwall tops (sheet 6/6 note 8);
#: Type C wingwall tops are level (note 9).
WINGWALL_BACKSLOPE = 2.0
WINGWALL_TIP_MIN_FT = 2.0

FOOTING_EXTENSION_FT = 4.0     #: "4'-0" (MIN.)" footing run past the wall
CUTOFF_WALL_WIDTH_FT = 1.5     #: 1'-6" cutoff wall (Section B-B)


def box_wall_thickness_in(span_ft: float) -> float:
    """Precast box wall thickness ``t box, wall`` (sheet 6/6 note 11):
    8 in for 8 ft spans, 10 in for 10 ft spans, 12 in for spans of 12 ft
    and over."""
    if span_ft <= 8.0:
        return 8.0
    if span_ft <= 10.0:
        return 10.0
    return 12.0


@dataclass(frozen=True)
class HeadwallRow:
    """One design-height row of a Type A/B/C table (sheets 2/6-5/6).

    Lengths and heights in feet, bar spacings in inches, quantities as
    printed: wingwall/footing concrete in cy and reinforcing in lbs are
    **whole-assembly** (both wingwalls); culvert-footing values are per
    lineal foot, to be multiplied by ``box span + 2 (t box, wall)``."""

    H: float                   # design height, top of footing to top of
    footing_design: int        # foreslope wall
    L1: float                  # wingwall length (wall #1; both walls, A/C)
    L2: float                  # wall #2 length (Type B); == L1 for A / C
    h1: float                  # wingwall root height (wall #1)
    h2: float                  # wall #2 root height; == h1 for A / C
    footing_w: float           # #F, footing width
    footing_t: float           # hF, footing thickness
    hcw: float                 # cutoff wall height below the footing
    a: float                   # footing toe dimension (Section A-A)
    b: float                   # foreslope wall width (Section A-A)
    x_bar: int                 # "X" vertical bars, far face
    x_spa_in: float
    y_bar: int                 # "Y" footing dowels into the stem
    y_spa_in: float
    c: float                   # "Y" bar extension length above the footing
    wingwall_conc_cy: float
    wingwall_reinf_lbs: float
    footing_conc_cy: float
    footing_reinf_lbs: float
    culvert_footing_cy_per_ft: float
    culvert_footing_lbs_per_ft: float


def _row(H, fd, L1, L2, h1, h2, wf, hf, hcw, a, b, xb, xs, yb, ys, c,
         cy, lbs, fcy, flbs, ccy, clbs) -> HeadwallRow:
    return HeadwallRow(H=H, footing_design=fd, L1=L1, L2=L2, h1=h1, h2=h2,
                       footing_w=wf, footing_t=hf, hcw=hcw, a=a, b=b,
                       x_bar=xb, x_spa_in=xs, y_bar=yb, y_spa_in=ys, c=c,
                       wingwall_conc_cy=cy, wingwall_reinf_lbs=lbs,
                       footing_conc_cy=fcy, footing_reinf_lbs=flbs,
                       culvert_footing_cy_per_ft=ccy,
                       culvert_footing_lbs_per_ft=clbs)


def _ft(f, i=0.0):
    return f + i / 12.0


#: Type A headwall (sheet 2/6): culvert normal to the roadway, both
#: wingwalls skewed 45 degrees from the culvert centerline.
TYPE_A_TABLE = (
    _row(6.5, 1, _ft(7, 3), _ft(7, 3), 4.0, 4.0, 4.5, 1.5, 2.5,
         _ft(1, 2), 1.0, 5, 18.0, 5, 18.0, _ft(2, 5),
         3.02, 446, 6.00, 598, 0.43, 24.55),
    _row(7.5, 1, 8.5, 8.5, 4.5, 4.5, 5.0, 1.5, 2.5,
         1.5, 1.0, 5, 18.0, 5, 18.0, _ft(2, 5),
         4.01, 533, 7.38, 733, 0.48, 27.58),
    _row(8.5, 1, 10.0, 10.0, 5.0, 5.0, 5.5, 1.5, 2.5,
         _ft(1, 11), 1.0, 5, 16.5, 5, 16.5, _ft(2, 5),
         5.27, 726, 9.05, 830, 0.52, 28.61),
    _row(9.5, 1, 11.5, 11.5, 5.5, 5.5, _ft(6, 3), 1.5, 2.5,
         _ft(2, 3), 1.0, 5, 18.0, 5, 9.0, _ft(3, 10),
         6.69, 934, 11.35, 911, 0.57, 29.90),
    _row(10.5, 1, _ft(12, 9), _ft(12, 9), 6.0, 6.0, 7.0, 2.0, 2.0,
         _ft(2, 11), 1.25, 5, 18.0, 5, 9.0, _ft(4, 2),
         10.25, 1104, 16.19, 1087, 0.74, 33.95),
    _row(11.5, 1, _ft(14, 3), _ft(14, 3), 6.5, 6.5, 7.5, 2.0, 2.0,
         _ft(3, 5), 1.25, 5, 17.0, 5, 8.5, 5.0,
         12.43, 1404, 18.87, 1205, 0.80, 35.06),
    _row(12.5, 2, _ft(15, 9), _ft(15, 9), 7.0, 7.0, _ft(8, 9), 2.0, 2.0,
         3.5, 1.25, 5, 17.0, 5, 8.5, _ft(5, 3),
         14.82, 1580, 24.41, 1511, 0.89, 40.14),
    _row(13.5, 6, 17.0, 17.0, 7.5, 7.5, 9.5, 2.0, 2.0,
         _ft(3, 11), 1.25, 6, 18.0, 6, 9.0, _ft(6, 2),
         17.18, 2139, 28.17, 2024, 0.97, 50.56),
)

#: Type B headwall (sheets 3/6 & 4/6): wall #1 at 45 degrees from the
#: culvert centerline, wall #2 straight along the roadway line; tabulated
#: per roadway skew theta.  Dimensions/reinforcing shared "for all values
#: of theta"; lengths, heights, and quantities per skew.
_B_SHARED = (
    # H, ftg, #F, hF, hcw, a, b, X@x, Y@y, c
    (6.5, 1, _ft(4, 9), 1.5, 2.5, _ft(1, 8), 1.0, 5, 18.0, 5, 18.0, _ft(2, 5)),
    (7.5, 1, 5.5, 1.5, 2.5, _ft(2, 1), 1.0, 5, 15.0, 5, 15.0, _ft(2, 5)),
    (8.5, 1, _ft(6, 3), 1.5, 2.5, 2.5, 1.0, 5, 18.0, 5, 9.0, _ft(2, 10)),
    (9.5, 1, 7.0, 1.5, 2.5, _ft(2, 11), 1.0, 5, 18.0, 5, 9.0, _ft(3, 2)),
    (10.5, 1, 8.0, 2.0, 2.0, _ft(3, 9), 1.25, 5, 14.5, 5, 7.25, _ft(3, 7)),
    (11.5, 3, 9.0, 2.0, 2.0, _ft(4, 1), 1.25, 5, 14.5, 5, 7.25, _ft(3, 9)),
    (12.5, 7, 10.0, 2.0, 2.0, 4.5, 1.25, 6, 16.0, 6, 8.0, _ft(4, 9)),
    (13.5, 8, _ft(11, 3), 2.0, 2.0, _ft(4, 10), 1.25, 6, 12.5, 6, 6.25,
     _ft(4, 11)),
)

_B_PER_SKEW = {
    # theta: ((L1, L2, h1, h2, cy, lbs, fcy, flbs, ccy, clbs), ...)
    0.0: (
        (_ft(7, 1), 10.0, 4.0, 6.5, 3.89, 512, 6.94, 552, 0.47, 25.31),
        (8.5, 12.0, 4.5, 7.5, 5.34, 667, 9.13, 684, 0.53, 28.77),
        (_ft(9, 11), 14.0, 5.0, 8.5, 7.02, 921, 11.62, 819, 0.58, 30.15),
        (_ft(11, 4), 16.0, 5.5, 9.5, 8.93, 1118, 14.39, 1006, 0.64, 33.53),
        (_ft(12, 9), 18.0, 6.0, 10.5, 13.88, 1464, 21.52, 1222, 0.85, 38.09),
        (_ft(14, 2), 20.0, 6.5, 11.5, 16.83, 1787, 26.54, 1569, 0.93, 45.09),
        (_ft(15, 7), 22.0, 7.0, 12.5, 20.07, 2321, 32.04, 2213, 1.03, 57.50),
        (17.0, 24.0, 7.5, 13.5, 23.59, 2928, 38.97, 3149, 1.13, 77.35),
    ),
    15.0: (
        (_ft(8, 3), _ft(6, 4), 4.0, _ft(4, 9), 3.05, 422, 5.94, 493,
         0.47, 25.31),
        (_ft(9, 11), _ft(7, 11), 4.5, 5.5, 4.05, 582, 7.95, 631,
         0.53, 28.77),
        (11.5, 9.5, 5.0, _ft(6, 3), 5.63, 783, 10.20, 743, 0.58, 30.15),
        (_ft(13, 2), _ft(11, 1), 5.5, 7.0, 7.22, 960, 12.76, 914,
         0.64, 33.53),
        (_ft(14, 10), _ft(12, 8), 6.0, _ft(7, 9), 11.32, 1245, 19.23, 1119,
         0.85, 38.09),
        (16.5, _ft(14, 3), 6.5, 8.5, 13.89, 1535, 23.91, 1431, 0.93, 45.09),
        (_ft(18, 1), _ft(15, 10), 7.0, 9.5, 16.59, 2020, 28.96, 2019,
         1.03, 57.50),
        (_ft(19, 9), 17.5, 7.5, _ft(10, 3), 19.61, 2587, 35.52, 2902,
         1.13, 77.35),
    ),
    30.0: (
        (10.0, 4.0, 4.0, 3.5, 2.83, 407, 5.71, 468, 0.47, 25.31),
        (12.0, _ft(5, 4), 4.5, _ft(4, 3), 3.99, 531, 7.74, 625,
         0.53, 28.77),
        (14.0, _ft(6, 8), 5.0, 5.0, 5.35, 772, 10.05, 739, 0.58, 30.15),
        (16.0, 8.0, 5.5, 5.5, 6.87, 917, 12.64, 910, 0.64, 33.53),
        (18.0, _ft(9, 4), 6.0, _ft(6, 3), 10.85, 1189, 19.13, 1115,
         0.85, 38.09),
        (20.0, _ft(10, 8), 6.5, 7.0, 13.29, 1483, 23.89, 1402, 0.93, 45.09),
        (22.0, 12.0, 7.0, 7.5, 15.91, 1957, 29.11, 2019, 1.03, 57.50),
        (24.0, _ft(13, 4), 7.5, _ft(8, 3), 18.84, 2520, 35.74, 2906,
         1.13, 77.35),
    ),
    45.0: (
        (_ft(13, 1), 4.0, 4.0, _ft(2, 9), 3.40, 469, 6.97, 535,
         0.47, 25.31),
        (_ft(15, 9), 4.0, 4.5, 3.5, 4.51, 590, 8.82, 676, 0.53, 28.77),
        (_ft(18, 4), _ft(4, 11), 5.0, 4.0, 5.94, 825, 11.32, 793,
         0.58, 30.16),
        (_ft(20, 11), _ft(6, 1), 5.5, 4.5, 7.63, 983, 14.26, 978,
         0.64, 33.53),
        (_ft(23, 7), _ft(7, 3), 6.0, _ft(5, 3), 12.06, 1325, 21.66, 1196,
         0.85, 38.09),
        (_ft(26, 2), _ft(8, 5), 6.5, _ft(5, 9), 14.71, 1622, 27.05, 1575,
         0.93, 45.09),
        (_ft(28, 9), _ft(9, 7), 7.0, _ft(6, 3), 17.63, 2157, 32.96, 2226,
         1.03, 57.50),
        (_ft(31, 5), _ft(10, 9), 7.5, _ft(6, 9), 20.84, 2772, 40.55, 3223,
         1.13, 77.35),
    ),
}

TYPE_B_TABLES = {
    theta: tuple(
        _row(s[0], s[1], p[0], p[1], p[2], p[3], s[2], s[3], s[4], s[5],
             s[6], s[7], s[8], s[9], s[10], s[11],
             p[4], p[5], p[6], p[7], p[8], p[9])
        for s, p in zip(_B_SHARED, rows))
    for theta, rows in _B_PER_SKEW.items()
}

#: Type C headwall (sheet 5/6): both wingwalls parallel to the roadway
#: (straight extensions of the headwall line); level wall tops (note 9,
#: designed with a 2 ft live-load surcharge).
TYPE_C_TABLE = (
    _row(6.5, 1, 10.0, 10.0, 6.5, 6.5, _ft(5, 3), 1.5, 2.5,
         _ft(1, 5), 1.0, 5, 17.5, 5, 17.5, _ft(2, 5),
         4.82, 528, 8.62, 587, 0.49, 27.84),
    _row(7.5, 1, 12.0, 12.0, 7.5, 7.5, _ft(5, 9), 1.5, 2.5,
         2.0, 1.0, 5, 12.0, 5, 12.0, _ft(2, 5),
         6.67, 749, 11.00, 695, 0.55, 29.04),
    _row(8.5, 1, 14.0, 14.0, 8.5, 8.5, _ft(6, 3), 1.5, 2.5,
         _ft(2, 7), 1.0, 5, 17.5, 5, 8.75, 3.5,
         8.82, 1012, 13.62, 823, 0.59, 30.15),
    _row(9.5, 1, 16.0, 16.0, 9.5, 9.5, 7.0, 1.5, 2.5,
         _ft(2, 11), 1.0, 5, 17.5, 5, 8.75, _ft(3, 8),
         11.26, 1261, 16.89, 1044, 0.64, 33.53),
    _row(10.5, 1, 18.0, 18.0, 10.5, 10.5, 8.0, 2.0, 2.0,
         _ft(3, 3), 1.25, 5, 18.0, 5, 9.0, _ft(3, 11),
         17.50, 1485, 25.34, 1278, 0.85, 38.01),
    _row(11.5, 1, 20.0, 20.0, 11.5, 11.5, 9.0, 2.0, 2.0,
         _ft(3, 10), 1.25, 6, 18.0, 6, 9.0, 4.5,
         21.30, 2201, 31.12, 1478, 0.92, 39.56),
    _row(12.5, 4, 22.0, 22.0, 12.5, 12.5, _ft(9, 9), 2.0, 2.0,
         _ft(4, 3), 1.25, 6, 16.0, 6, 8.0, _ft(5, 2),
         25.47, 2775, 36.67, 2028, 1.0, 49.17),
    _row(13.5, 5, 24.0, 24.0, 13.5, 13.5, _ft(10, 6), 2.0, 2.0,
         _ft(4, 8), 1.25, 6, 13.0, 6, 6.5, _ft(5, 4),
         30.0, 3454, 42.67, 2635, 1.06, 58.62),
)

#: Footing reinforcing (sheet 6/6): "V" transverse bars and "W"/"Z"
#: longitudinal / cutoff bars per footing design number.
FOOTING_REINFORCING = {
    1: ((5, 18.0), (5, 18.0)),
    2: ((5, 15.0), (5, 18.0)),
    3: ((5, 12.0), (5, 18.0)),
    4: ((5, 18.0), (5, 12.0)),
    5: ((5, 15.0), (5, 9.0)),
    6: ((6, 18.0), (6, 18.0)),
    7: ((6, 18.0), (6, 18.0)),
    8: ((6, 9.0), (6, 12.0)),
}

#: Foreslope wall quantities (sheet 6/6): (width b ft, height in) ->
#: (reinf lbs/ft, conc cy/ft); multiply by box span + 2 (t box, wall).
FORESLOPE_WALL_QUANTITIES = {
    (1.0, 6.0): (6.70, 0.02),
    (1.0, 18.0): (10.87, 0.06),
    (1.25, 6.0): (7.22, 0.03),
    (1.25, 18.0): (11.39, 0.07),
}


@dataclass(frozen=True)
class HeadwallInput:
    """Design inputs for one culvert-end headwall assembly (Design Data
    sheets).  ``headwall_type`` per sheet 1/6: "A" when the culvert is
    normal to the roadway, "B" for roadway skews of 15/30/45 degrees (or
    0 with a straight wingwall), "C" only where site constraints keep the
    wingwalls parallel to the roadway."""

    headwall_type: str           # "A" | "B" | "C"
    box_span_ft: float
    box_rise_ft: float
    box_slab_thickness_in: float = 10.0   # box top/bottom slab, per design
    roadway_skew_deg: float = 0.0         # theta (Type B tables)
    foreslope_wall_height_in: float = 6.0  # 6 or 18


@dataclass(frozen=True)
class HeadwallDesign:
    """The resolved design: the table row plus the derived dimensions."""

    inputs: HeadwallInput
    H: float                     # design height actually used (table row)
    H_required: float            # rise + 2 t_slab + foreslope height
    t_wall_in: float             # box/wingwall/stem thickness
    row: HeadwallRow
    v_bar: "tuple[int, float]"   # footing "V" transverse (size, spa in)
    wz_bar: "tuple[int, float]"  # footing "W"/"Z" (size, spa in)
    foreslope_lbs_per_ft: float
    foreslope_cy_per_ft: float


def design_headwall(inp: HeadwallInput) -> HeadwallDesign:
    """Resolve a :class:`HeadwallInput` against the Design Data tables:
    compute H = box rise + 2 (box slab thickness) + foreslope wall height
    (sheet 1/6), round up to the next tabulated design height, and return
    the row with its footing reinforcing and foreslope quantities."""
    if inp.headwall_type not in HEADWALL_TYPES:
        raise ValueError(f"headwall_type must be one of {HEADWALL_TYPES}")
    lo, hi = BOX_SPAN_RANGE_FT
    if not lo <= inp.box_span_ft <= hi:
        raise ValueError(f"box_span_ft must be within {lo}-{hi} ft "
                         "(sheet 1/6 culvert size limitations)")
    lo, hi = BOX_RISE_RANGE_FT
    if not lo <= inp.box_rise_ft <= hi:
        raise ValueError(f"box_rise_ft must be within {lo}-{hi} ft")
    if inp.foreslope_wall_height_in not in FORESLOPE_WALL_HEIGHTS_IN:
        raise ValueError("foreslope_wall_height_in must be 6 or 18 "
                         "(sheet 1/6)")

    if inp.headwall_type == "B":
        if inp.roadway_skew_deg not in TYPE_B_SKEWS:
            raise ValueError(f"Type B is tabulated for skews "
                             f"{TYPE_B_SKEWS} only")
        table = TYPE_B_TABLES[inp.roadway_skew_deg]
    elif inp.headwall_type == "A":
        table = TYPE_A_TABLE
    else:
        table = TYPE_C_TABLE

    H_req = (inp.box_rise_ft + 2.0 * inp.box_slab_thickness_in / 12.0
             + inp.foreslope_wall_height_in / 12.0)
    row = next((r for r in table if r.H >= H_req - 1e-9), None)
    if row is None:
        raise ValueError(
            f"required design height {H_req:.2f} ft exceeds the table "
            f"maximum {table[-1].H:g} ft -- needs a special wall design")

    v, wz = FOOTING_REINFORCING[row.footing_design]
    fs_lbs, fs_cy = FORESLOPE_WALL_QUANTITIES[
        (row.b, inp.foreslope_wall_height_in)]
    return HeadwallDesign(
        inputs=inp, H=row.H, H_required=H_req,
        t_wall_in=box_wall_thickness_in(inp.box_span_ft), row=row,
        v_bar=v, wz_bar=wz,
        foreslope_lbs_per_ft=fs_lbs, foreslope_cy_per_ft=fs_cy)
