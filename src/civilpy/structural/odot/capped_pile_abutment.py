#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT capped pile abutment for slab bridges (CPA-1-08).

Transcribed from Ohio DOT Standard Bridge Drawing **CPA-1-08**, "Capped
Pile Abutment for Slab Bridges" (rev. 01-19-2024, 6 sheets: three
railing-variant pairs -- SBR-1 deflector parapet, three steel tube, twin
steel tube -- of part-plan/elevation views, all referencing one shared
cap cross-section (Section C-C/D-D, sheet 2) and one reinforcing steel
table (sheet 4)). SB-1-24's companion, referenced from its slab elevation
as "ABUT. DIAPHRAGM SEE STANDARD DRAWING CPA-1-08".

Like BCHW (:mod:`civilpy.structural.odot.box_culvert_headwall`), this
sheet mixes a handful of **fixed** dimensions (cap width 3'-0", the
1'-6"/1'-6" pile-zone split, max bar spacings) with **project-variable**
ones the reinforcing steel table itself marks with an asterisk ("DIMENSION
MAY VARY WITH EACH INDIVIDUAL STRUCTURE") -- wingwall length, pile count
and spacing, footing depth, and every skew-dependent bar length (the
S501/S502/S503 bars carry a literal ``sec(theta)`` term in their tabulated
length, ``1'-5"/COS(theta)`` etc.). ``layout_capped_pile_abutment`` takes
those as required inputs; there is no discrete catalog to look them up
from.

The D801 bar (sheet 4's bending diagram legend, "TYPE 6 -- SEE STANDARD
BRIDGE DRAWING AS-1-15") is the *same* bar as
:mod:`civilpy.structural.odot.approach_slab`'s D801/D802 anchor bar --
this sheet does not redefine it, so this module doesn't either; see
:func:`~civilpy.structural.odot.approach_slab.d801_length_ft`.

Conventions match the rest of this package: X along stations, Y
transverse, Z up; feet in plan, inches for section dimensions. The
origin sits on the abutment centerline at the bridge-seat elevation
(z = 0), y = 0 at the cap centerline.
"""

import math
from dataclasses import dataclass, field

Point = tuple[float, float]     # (x, y) feet, in-plane bend shape
PointXYZ = tuple[float, float, float]

SCD = "CPA-1-08"
REVISION = "01-19-2024"

# ── fixed geometric constants (Section C-C/D-D, sheet 2) ────────────────

CAP_WIDTH_FT = 3.0                 # SECTION C-C/D-D "3'-0""
CAP_HALF_ZONE_FT = 1.5             # "1'-6" | 1'-6"" split about the pile line
APPROACH_SLAB_SEAT_IN = 6.0
PARAPET_TRANSITION_FT = 14.0
PEJF_THICKNESS_IN = 1.0
PEJF_THIN_IN = 0.5
NEOPRENE_SHEET_WIDTH_FT = 3.0
VERTICAL_NEOPRENE_FT = 3.0
EMBANKMENT_SLOPE = 2.0             # 2:1, shoulder break point line
MAX_A_BAR_SPACING_FT = 1.5         # A501/A502/A503 max 1'-6" c/c between piles
MAX_S_BAR_SPACING_FT = 1.0         # 2-S501, S502, A801 max 1'-0" c/c along abutment

DRAINAGE_PIPE_NONPERFORATED_SPEC = "6 in non-perforated corrugated plastic pipe (707.33 Type S)"
DRAINAGE_PIPE_PERFORATED_SPEC = "6 in perforated corrugated plastic pipe (707.33 Type SP)"
DRAINAGE_PIPE_MIN_SLOPE = 1.0 / 8.0  # in/ft


# ── reinforcing steel table (sheet 4) ─────────────────────────────────────
#
# Bend types 1-5 are this sheet's own legend; Type 6 (D801) is not
# redefined here -- it's approach_slab's D801/D802 shape (see module
# docstring). "*" marks in the sheet's own LENGTH/A/B/C columns become
# None below (project-variable, not a missing transcription).

@dataclass(frozen=True)
class RebarMark:
    mark: str
    length_ft: float | None   # None where the sheet marks "*"
    bend_type: int
    a_ft: float | None = None
    b_ft: float | None = None
    c_ft: float | None = None
    note: str = ""


REBAR_TABLE: tuple[RebarMark, ...] = (
    RebarMark("A401", 8 + 10 / 12.0, 2, 1 + 9 / 12.0, 2 + 6 / 12.0),
    RebarMark("A501", 10 + 7 / 12.0, 2, 2 + 8 / 12.0, 2 + 7 / 12.0),
    RebarMark("A502", None, 2, 1 + 11 / 12.0, None),
    RebarMark("A503", None, 2, 1 + 11 / 12.0, None, note="series bar"),
    RebarMark("A504", None, 0, note="straight (STR)"),
    RebarMark("A505", None, 0, note="straight (STR)"),
    RebarMark("A506", None, 0, note="straight (STR)"),
    RebarMark("A507", None, 0, note="straight (STR)"),
    RebarMark("A508", None, 0, note="straight (STR)"),
    RebarMark("A509", None, 5),
    RebarMark("A510", None, 5),
    RebarMark("A801", 3 + 10 / 12.0, 3, 2.0),
    RebarMark("A801", 2 + 11 / 12.0, 4, 2.0, note="optional hooked dowel bar"),
    RebarMark("A802", None, 0, note="straight (STR)"),
    RebarMark("S501", None, 1, note="A = 1'-5\"/cos(skew)"),
    RebarMark("S502", None, 2, b_ft=1 + 1 / 12.0, note="A = 1'-11\"/cos(skew)"),
    RebarMark("S503", None, 2, note="A = 1'-11\"/cos(skew)"),
    RebarMark("S801", None, 0, note="straight (STR)"),
    RebarMark("S802", None, 0, note="straight (STR)"),
    RebarMark("D801", None, 6, note="see civilpy.structural.odot.approach_slab"),
)

_REBAR_BY_MARK = {}
for _r in REBAR_TABLE:
    _REBAR_BY_MARK.setdefault(_r.mark, []).append(_r)


def rebar_mark(mark: str) -> tuple[RebarMark, ...]:
    """All ``REBAR_TABLE`` rows for a bar mark (usually one; ``A801`` has
    two -- the standard anchor bar and the optional hooked-dowel alternate).

    Raises ``ValueError`` naming the valid marks otherwise."""
    try:
        return tuple(_REBAR_BY_MARK[mark])
    except KeyError:
        raise ValueError(
            f"CPA-1-08 reinforcing marks are {sorted(_REBAR_BY_MARK)}, "
            f"not {mark!r}") from None


def s_bar_length_ft(base_ft: float, skew_deg: float) -> float:
    """S501/S502/S503's tabulated ``base/COS(theta)`` length formula."""
    return base_ft / math.cos(math.radians(skew_deg))


# ── bend-shape legend (TYPE 1-5; TYPE 6 is approach_slab's D801) ────────

def bend_shape(bend_type: int, **legs: float) -> tuple[Point, ...]:
    """The bend polyline for one of CPA-1-08's own legend shapes (1-5).

    ``legs`` supplies whatever the sheet leaves blank (``A``, ``B``, ``C``
    as applicable). Raises ``ValueError`` naming the valid types (1-5;
    call into ``approach_slab`` for Type 6/D801) and required legs."""
    try:
        spec = _BEND_SHAPES[bend_type]
    except KeyError:
        raise ValueError(
            "CPA-1-08 bend types are 1-5 (Type 6/D801 is "
            "civilpy.structural.odot.approach_slab's D801/D802), "
            f"not {bend_type!r}") from None
    required = spec["legs"]
    missing = [k for k in required if k not in legs]
    if missing:
        raise ValueError(f"TYPE {bend_type} requires legs {required}; "
                         f"missing {missing}")
    return spec["shape"](**{k: legs[k] for k in required})


def _type_1(A: float, B: float) -> tuple[Point, ...]:
    """Closed rectangular stirrup, width A, height B."""
    return ((0.0, 0.0), (A, 0.0), (A, B), (0.0, B), (0.0, 0.0))


def _type_2(A: float, B: float) -> tuple[Point, ...]:
    """U-shape with a standard hook: leg B, base A, leg B."""
    return ((0.0, 0.0), (0.0, B), (A, B), (A, 0.0))


def _type_3(A: float) -> tuple[Point, ...]:
    """Straight bar, length A, with a standard hook one end."""
    return ((0.0, 0.0), (A, 0.0))


def _type_4(A: float) -> tuple[Point, ...]:
    """Optional hooked dowel bar: straight length A with a standard hook
    (grouted into a drilled hole in lieu of the A801 anchor bar)."""
    return ((0.0, 0.0), (A, 0.0))


def _type_5(A: float, B: float, C: float) -> tuple[Point, ...]:
    """Diagonal bar of length A with a short end kick of length B, offset C."""
    p0 = (0.0, 0.0)
    p1 = (A, 0.0)
    p2 = (A + B, C)
    return (p0, p1, p2)


_BEND_SHAPES = {
    1: {"legs": ("A", "B"), "shape": _type_1},
    2: {"legs": ("A", "B"), "shape": _type_2},
    3: {"legs": ("A",), "shape": _type_3},
    4: {"legs": ("A",), "shape": _type_4},
    5: {"legs": ("A", "B", "C"), "shape": _type_5},
}


# ── layout (all overall dimensions project-supplied) ────────────────────

@dataclass(frozen=True)
class AbutmentInput:
    """Project-supplied dimensions for one capped pile abutment.

    ``wingwall_length_ft`` is the "W" dimension (Section B-B/F-F);
    ``n_piles``/``pile_spacing_ft`` lay out the cap's pile line;
    ``footing_depth_ft`` is the cap/footing depth below the bridge seat.
    Nothing here is cataloged -- see the module docstring."""

    wingwall_length_ft: float
    skew_deg: float
    n_piles: int
    pile_spacing_ft: float
    footing_depth_ft: float
    cap_width_ft: float = CAP_WIDTH_FT


@dataclass(frozen=True)
class AbutmentLayout:
    """The generated abutment.  ``cap_outline`` is the cap's plan footprint
    (top of cap, z = 0, the bridge seat) extending down
    ``footing_depth_ft``; ``pile_points`` are the pile centerlines along
    the cap; ``wingwall_outline`` is one flared wingwall plane (mirrors
    :func:`~civilpy.structural.odot.full_height_headwall.layout_full_height_headwall`'s
    convention)."""

    inputs: AbutmentInput
    cap_outline: tuple[PointXYZ, PointXYZ, PointXYZ, PointXYZ]
    pile_points: tuple[PointXYZ, ...]
    wingwall_outline: tuple[PointXYZ, PointXYZ, PointXYZ, PointXYZ]
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_capped_pile_abutment(inp: AbutmentInput) -> AbutmentLayout:
    """Generate one capped pile abutment from fully project-supplied
    dimensions (no catalog lookup -- see the module docstring).

    Raises ``ValueError`` for a non-positive length/spacing/depth or
    fewer than 2 piles."""
    for name in ("wingwall_length_ft", "pile_spacing_ft", "footing_depth_ft"):
        if getattr(inp, name) <= 0.0:
            raise ValueError(f"AbutmentInput.{name} must be positive")
    if inp.n_piles < 2:
        raise ValueError("AbutmentInput.n_piles must be >= 2")

    tan_skew = math.tan(math.radians(inp.skew_deg))
    cap_len = (inp.n_piles - 1) * inp.pile_spacing_ft + 2.0 * CAP_HALF_ZONE_FT

    def pt(x: float, y: float, z: float) -> PointXYZ:
        return (x + y * tan_skew, y, z)

    half_w = inp.cap_width_ft / 2.0
    cap_outline = (pt(-cap_len / 2.0, -half_w, 0.0),
                  pt(-cap_len / 2.0, half_w, 0.0),
                  pt(cap_len / 2.0, half_w, 0.0),
                  pt(cap_len / 2.0, -half_w, 0.0))

    pile_start = -cap_len / 2.0 + CAP_HALF_ZONE_FT
    pile_points = tuple(
        pt(pile_start + i * inp.pile_spacing_ft, 0.0, -inp.footing_depth_ft)
        for i in range(inp.n_piles)
    )

    # Wingwall: springs from the cap's +x end, flares out at 45 deg over
    # the project-supplied length W, following the 2:1 embankment slope
    # down from the bridge seat (same convention as full_height_headwall).
    W = inp.wingwall_length_ft
    wing_dx = W * math.sin(math.radians(45.0))
    wing_dy = W * math.cos(math.radians(45.0))
    wingwall_outline = (
        pt(cap_len / 2.0, half_w, 0.0),
        pt(cap_len / 2.0, half_w, -inp.footing_depth_ft),
        pt(cap_len / 2.0 + wing_dx, half_w + wing_dy,
           -inp.footing_depth_ft + W / EMBANKMENT_SLOPE),
        pt(cap_len / 2.0 + wing_dx, half_w + wing_dy,
           W / EMBANKMENT_SLOPE),
    )

    notes = (
        f"CPA-1-08 capped pile abutment: {inp.n_piles} piles @ "
        f"{inp.pile_spacing_ft:g} ft, cap {cap_len:.2f} ft long x "
        f"{inp.cap_width_ft:g} ft wide, skew {inp.skew_deg:g} deg, "
        f"wingwall W {W:g} ft",
        "All overall dimensions (wingwall length, pile count/spacing, "
        "footing depth) are project-supplied -- no catalog. Skew-dependent "
        "bar lengths (S501/S502/S503) use base/cos(skew); see "
        "s_bar_length_ft().",
        "Not modeled: pile sections themselves, reinforcing bar layout "
        "(see rebar_mark()/bend_shape() for the table), drainage pipes, "
        "neoprene sheeting/PEJF joints, the parapet/steel-tube railing "
        "transition details (sheets 1/3/5), and D801 (approach_slab's "
        "bar, not redrawn here).",
    )

    return AbutmentLayout(
        inputs=inp,
        cap_outline=cap_outline,
        pile_points=pile_points,
        wingwall_outline=wingwall_outline,
        notes=notes,
    )
