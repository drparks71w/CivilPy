#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT capped pile pier for continuous slab bridges (CPP-1-08).

Transcribed from Ohio DOT Standard Bridge Drawing **CPP-1-08**, "Capped
Pile Pier for Continuous Slab Bridges" (rev. 07-21-2017, 1 sheet). The
drawing remains the controlling document. CS-1-24's companion pier
(rated Wave 4, not yet encoded -- see ``ODOT_SCD_Feasibility.md``).

Unlike BCHW/CPA-1-08, this sheet is genuinely "clean and parametric": the
pier cap length is a literal formula in terms of the bridge slab width and
skew, and the cap cross-section (width, end radius) is fixed regardless
of span -- there is no "insert design here" blank. Pile count/spacing and
the reinforcing bar list quantities remain project-supplied (spacing has
a stated max, not a table), same as every capped-pile-cap sheet in this
package.

Design basis (General Notes / Design Instructions): AASHTO LRFD + 2008
interim revisions + 2007 ODOT BDM; HL-93; FWS 0.06 ksf; concrete f'c =
4.5 ksi; reinforcing/spiral steel min. yield 60 ksi; HP12X53 steel pile
min. yield 50 ksi. Limits of design (exceeding any of these means this
standard drawing does not apply): skew <= 30 deg, unsupported pile length
<= 20 ft, supports a standard continuous slab with individual span <=
57.50 ft (CS-1-24), sloped embankment/debris/ice-flow lateral force on
the pile bent, or piles not driven >= 10 ft into rock/firm material.

Conventions match the rest of this package: X along stations, Y
transverse, Z up; feet in plan, inches for section dimensions. The
origin sits on the pier centerline (X = 0) at the top-of-cap elevation
(Z = 0), Y = 0 on the roadway centerline.
"""

import math
from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "CPP-1-08"
REVISION = "07-21-2017"

# ── design data (General Notes) ───────────────────────────────────────────

DESIGN_METHOD = "LRFD"
DESIGN_SPEC = "AASHTO LRFD + 2008 interim revisions + 2007 ODOT BDM"
DESIGN_LOADING = "HL-93"
FUTURE_WEARING_SURFACE_KSF = 0.06
CONCRETE_STRENGTH_KSI = 4.5
REBAR_YIELD_KSI = 60.0
SPIRAL_STEEL_YIELD_KSI = 60.0
STEEL_PILE_SHAPE = "HP12X53"
STEEL_PILE_YIELD_KSI = 50.0
CONCRETE_PILE_MIN_DIAMETER_IN = 16.0   # 16 in CIP reinforced concrete pile

# ── limits of design (sheet's own "DESIGN INSTRUCTIONS (CONTINUED)") ──────

MAX_SKEW_DEG = 30.0
MAX_UNSUPPORTED_PILE_LENGTH_FT = 20.0
MAX_SPAN_FT = 57.5   # standard continuous slab, individual span (CS-1-24)
MIN_PILE_EMBED_IN_ROCK_FT = 10.0

# ── fixed cap geometry (PLAN OF SKEWED PIER / SECTION A-A/B-B) ───────────

CAP_WIDTH_FT = 3.0            # cap cross-section width; end radius = W/2
CAP_END_RADIUS_FT = 1.5       # R = 1'-6" rounded cap ends
CAP_DEPTH_FT = 2.0            # HALF ELEVATION overall cap depth
MAX_PILE_SPACING_FT = 7.5     # 7'-6" max
PILE_END_DISTANCE_MIN_FT = 1.5     # 1'-6" min (1'-8" min for 16" CIP piles)
PILE_END_DISTANCE_MIN_CIP_FT = 1.0 + 8.0 / 12.0
PILE_END_DISTANCE_MAX_FT = 1.75    # 1'-9" max
CAP_TO_SLAB_EDGE_IN = 8.0      # "8"" dimension, cap end past the slab edge

#: PIER LENGTH = 3'-0" + (BRIDGE SLAB WIDTH - 4'-4") / COS(skew) (sheet's
#: own formula, "PLAN OF SKEWED PIER").
def pier_length_ft(slab_width_ft: float, skew_deg: float = 0.0) -> float:
    return 3.0 + (slab_width_ft - (4.0 + 4.0 / 12.0)) / math.cos(
        math.radians(skew_deg))


#: Q = T + 1'-4" (bending-diagram formula shared by P501/P502/P503, T = slab
#: thickness).  ``slab_thickness_in`` is the companion slab standard's "T".
def q_bend_height_ft(slab_thickness_in: float) -> float:
    return slab_thickness_in / 12.0 + 1.0 + 4.0 / 12.0


# ── reinforcing bar list (BENDING DIAGRAMS) ───────────────────────────────
#
# P501/P502/P503 are closed U-shapes whose height is the Q formula above;
# P504 is a diagonal corner bar with an inside radius. Widths below are
# "out to out" per the sheet's own legend ("% = OUT TO OUT").

@dataclass(frozen=True)
class PierBarMark:
    mark: str
    width_ft: float | None       # None where the sheet uses Q% for width too
    height_is_q: bool
    inside_radius_ft: float | None = None
    note: str = ""


PIER_REBAR: tuple[PierBarMark, ...] = (
    PierBarMark("P501", 2.0 + 8.0 / 12.0, True, note="at equal spacing between piles"),
    PierBarMark("P502", 1.0 + 9.0 / 12.0, True),
    PierBarMark("P503", None, True, note="width = Q% too; end-pile corner stirrup"),
    PierBarMark("P504", 2.0 + 6.0 / 12.0, False,
               inside_radius_ft=1.0 + (2 + 3 / 8.0) / 12.0,
               note="diagonal end-pile corner bar"),
)

_PIER_REBAR_BY_MARK = {b.mark: b for b in PIER_REBAR}


def pier_bar(mark: str) -> PierBarMark:
    """Look up a CPP-1-08 bar mark (P501-P504).

    Raises ``ValueError`` naming the valid marks otherwise."""
    try:
        return _PIER_REBAR_BY_MARK[mark]
    except KeyError:
        raise ValueError(
            f"CPP-1-08 bar marks are {sorted(_PIER_REBAR_BY_MARK)}, "
            f"not {mark!r}") from None


# ── layout ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PierInput:
    """Inputs for a capped pile pier.

    ``slab_width_ft`` is the bridge slab width (drives :func:`pier_length_ft`);
    ``n_piles``/``pile_spacing_ft`` lay out the pile line (spacing must not
    exceed :data:`MAX_PILE_SPACING_FT`); ``cap_depth_ft`` defaults to the
    sheet's fixed :data:`CAP_DEPTH_FT`."""

    slab_width_ft: float
    skew_deg: float
    n_piles: int
    pile_spacing_ft: float
    cap_depth_ft: float = CAP_DEPTH_FT


@dataclass(frozen=True)
class PierLayout:
    """The generated pier.  ``cap_outline`` is the rounded-end cap plan
    footprint (top of cap, z = 0) extending down ``cap_depth_ft``;
    ``pile_points`` are the pile centerlines (top of pile, at the cap
    underside)."""

    inputs: PierInput
    cap_outline: tuple[Point, ...]
    pile_points: tuple[Point, ...]
    length_ft: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_capped_pile_pier(inp: PierInput, *, n_arc_segments: int = 8) -> PierLayout:
    """Generate a capped pile pier: the rounded-end cap solid outline and
    the pile line, from the sheet's own pier-length formula.

    Raises ``ValueError`` for a non-positive slab width/pile spacing, fewer
    than 2 piles, a pile spacing beyond :data:`MAX_PILE_SPACING_FT`, or a
    skew beyond :data:`MAX_SKEW_DEG`."""
    if inp.slab_width_ft <= 0.0:
        raise ValueError("PierInput.slab_width_ft must be positive")
    if inp.pile_spacing_ft <= 0.0:
        raise ValueError("PierInput.pile_spacing_ft must be positive")
    if inp.n_piles < 2:
        raise ValueError("PierInput.n_piles must be >= 2")
    if inp.pile_spacing_ft > MAX_PILE_SPACING_FT + 1e-9:
        raise ValueError(
            f"CPP-1-08 pile spacing is {MAX_PILE_SPACING_FT:g} ft max; "
            f"{inp.pile_spacing_ft:g} ft exceeds it")
    if abs(inp.skew_deg) > MAX_SKEW_DEG + 1e-9:
        raise ValueError(
            f"CPP-1-08 is limited to {MAX_SKEW_DEG:g} deg skew; "
            f"{inp.skew_deg:g} deg exceeds it")

    L = pier_length_ft(inp.slab_width_ft, inp.skew_deg)
    tan_skew = math.tan(math.radians(inp.skew_deg))
    half_w = CAP_WIDTH_FT / 2.0
    R = CAP_END_RADIUS_FT

    def pt(u: float, y: float, z: float) -> Point:
        return (u + y * tan_skew, y, z)

    # Straight run between the two rounded ends, plus a semicircular arc at
    # each end (R = W/2) so the outline reads as a stadium/obround shape.
    straight = L - 2.0 * R
    pts = [pt(0.0, -half_w, 0.0), pt(straight, -half_w, 0.0)]
    for i in range(1, n_arc_segments):   # far-end semicircle, centered (straight, 0)
        a = -math.pi / 2.0 + math.pi * i / n_arc_segments
        pts.append(pt(straight + R * math.cos(a), R * math.sin(a), 0.0))
    pts.append(pt(straight, half_w, 0.0))
    pts.append(pt(0.0, half_w, 0.0))
    for i in range(1, n_arc_segments):   # near-end semicircle, centered (0, 0)
        a = math.pi / 2.0 + math.pi * i / n_arc_segments
        pts.append(pt(R * math.cos(a), R * math.sin(a), 0.0))
    cap_outline = tuple(pts)

    pile_start = R + (L - 2.0 * R - (inp.n_piles - 1) * inp.pile_spacing_ft) / 2.0
    pile_points = tuple(
        pt(pile_start + i * inp.pile_spacing_ft, 0.0, -inp.cap_depth_ft)
        for i in range(inp.n_piles)
    )

    notes = (
        f"CPP-1-08 capped pile pier: length {L:.2f} ft "
        f"(3'-0\" + (slab width - 4'-4\")/cos(skew)), {inp.n_piles} piles @ "
        f"{inp.pile_spacing_ft:g} ft, skew {inp.skew_deg:g} deg",
        f"Limits: skew <= {MAX_SKEW_DEG:g} deg, unsupported pile length "
        f"<= {MAX_UNSUPPORTED_PILE_LENGTH_FT:g} ft, span <= {MAX_SPAN_FT:g} ft "
        "(CS-1-24). Piles: 16 in min CIP concrete or HP12X53 steel.",
        "Not modeled: reinforcing bar layout (see pier_bar() for the "
        "P501-P504 bend data), pile encasement, pile sections themselves, "
        "shear keys / slab edge beam.",
    )

    return PierLayout(
        inputs=inp,
        cap_outline=cap_outline,
        pile_points=pile_points,
        length_ft=L,
        notes=notes,
    )
