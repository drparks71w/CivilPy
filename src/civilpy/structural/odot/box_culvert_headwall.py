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
