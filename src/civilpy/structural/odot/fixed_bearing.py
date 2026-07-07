#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT fixed bearings for steel beam and girder bridges (FB-1-82).

Dimension and capacity table transcribed from Ohio DOT Standard Bridge
Drawing FB-1-82 (Office of Structural Engineering, rev. 05-10-1982, rev.
07-19-2024). The drawing remains the controlling document.

Each row is a pin-bearing assembly: a masonry (base) plate F x G, a
cylindrical bearing pin of diameter ``DIA``, and a top plate A x B under
the girder, overall height H. F-50/F-100 use only 2 anchor rods
(diagonally opposite corners, note 1); F-350/F-400 require bearing
stiffeners both sides of the girder web (note 2).

Design basis (General Notes): AASHTO Standard Specifications (1977 + 1978-
1981 interims) + Ohio supplement, masonry plates designed for 30,000 psi
allowable bending, uniform bearing distribution assumed. Anchor rods are
1-1/4 in dia x 1'-7 in long in 1-5/8 in dia holes. Lateral expansion
clearance is 1/8 in per end for superstructure widths up to 120 ft (1/4 in
for widths over 60 ft, per the note's own overlapping ranges -- see
:data:`LATERAL_CLEARANCE_IN`/:data:`LATERAL_CLEARANCE_WIDE_IN`).

Dimensions in inches, weight in pounds, load in pounds. Spot-checked
against the drawing in the test suite.
"""

from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) inches

SCD = "FB-1-82"
REVISION = "07-19-2024"

#: Dimension letters in FB-1-82 table column order.
DIM_LETTERS: tuple[str, ...] = (
    "A", "B", "C", "D", "E", "F", "G", "H", "K", "DIA",
)

ANCHOR_ROD_DIA_IN = 1.25
ANCHOR_ROD_LENGTH_IN = 1.0 * 12.0 + 7.0   # 1'-7"
ANCHOR_ROD_HOLE_DIA_IN = 1.0 + 5.0 / 8.0
BEARING_PAD_THICKNESS_IN = 1.0 / 8.0
ALLOWABLE_BEARING_STRESS_PSI = 30000.0
SURFACE_FINISH = "500 (or smoother where not otherwise noted)"

#: Lateral expansion clearance per end of the bearing pin, inches.
LATERAL_CLEARANCE_IN = 1.0 / 8.0        # superstructure width <= 60 ft
LATERAL_CLEARANCE_WIDE_IN = 1.0 / 4.0   # superstructure width 60-120 ft
LATERAL_CLEARANCE_MAX_WIDTH_FT = 120.0


@dataclass(frozen=True)
class FixedBearing:
    """One FB-1-82 fixed-bearing capacity line.

    ``two_anchor_rods`` (note 1) is true only for F-50/F-100; otherwise 4
    anchor rods are used (one per masonry-plate corner).
    ``stiffeners_required`` (note 2) is true only for F-350/F-400."""

    designation: str          # "F-50" .. "F-400"
    max_load_lb: float
    dims: dict[str, float]     # keyed by DIM_LETTERS, inches
    weight_lb: float
    two_anchor_rods: bool = False
    stiffeners_required: bool = False


def _row(designation, load, dim_values, wt, *, two_rods=False, stiff=False):
    return FixedBearing(
        designation=designation,
        max_load_lb=load,
        dims=dict(zip(DIM_LETTERS, dim_values)),
        weight_lb=wt,
        two_anchor_rods=two_rods,
        stiffeners_required=stiff,
    )


# Columns: A, B, C, D, E, F, G, H, K, DIA (inches)
_CATALOG: list[FixedBearing] = [
    _row("F-50", 50_000,
        (6, 6, 1.5, 3, 1.25, 8, 16, 1.5, 5 + 5 / 8.0, 2),
        100, two_rods=True),
    _row("F-100", 100_000,
        (7, 9, 1.75, 4, 1.5, 9, 18, 1.5, 5 + 5 / 8.0, 2),
        143, two_rods=True),
    _row("F-150", 150_000,
        (9, 9, 2.5, 5, 1.5, 11, 20, 2, 6 + 7 / 8.0, 2.5),
        244),
    _row("F-200", 200_000,
        (10, 10, 3, 6, 2, 11, 22, 2, 7 + 7 / 8.0, 2.5),
        300),
    _row("F-250", 250_000,
        (11, 10, 3.5, 7, 2, 12, 24, 2.5, 8 + 7 / 8.0, 3),
        400),
    _row("F-300", 300_000,
        (12, 11, 3.75, 8, 2.5, 14, 25, 2.5, 9 + 5 / 8.0, 3),
        502),
    _row("F-350", 350_000,
        (12, 11, 3.75, 8, 2.5, 16, 25, 2.5, 9 + 5 / 8.0, 3),
        540, stiff=True),
    _row("F-400", 400_000,
        (12, 12, 3.75, 8, 2.5, 18, 26, 2.5, 9 + 5 / 8.0, 3),
        610, stiff=True),
]

#: Fixed-bearing lines keyed by designation ("F-50" .. "F-400").
FIXED_BEARINGS: dict[str, FixedBearing] = {r.designation: r for r in _CATALOG}


def fixed_bearing(designation: str) -> FixedBearing:
    """Look up a FB-1-82 fixed-bearing line by designation ("F-50", ...,
    "F-400"). Raises ``ValueError`` naming the valid designations otherwise."""
    try:
        return FIXED_BEARINGS[designation]
    except KeyError:
        raise ValueError(
            f"FB-1-82 designations are {list(FIXED_BEARINGS)}, "
            f"not {designation!r}") from None


def smallest_for_load(load_lb: float) -> FixedBearing:
    """The lightest standard fixed bearing whose maximum load covers
    ``load_lb``; raises ``ValueError`` if the load exceeds the F-400 line."""
    for r in _CATALOG:
        if r.max_load_lb >= load_lb:
            return r
    raise ValueError(f"load {load_lb} lb exceeds the largest FB-1-82 line")


def lateral_clearance_in(superstructure_width_ft: float) -> float:
    """Lateral expansion clearance per end of the bearing pin (General
    Notes): 1/8 in normally, 1/4 in for a superstructure over 60 ft wide
    (up to the 120 ft this note addresses)."""
    return (LATERAL_CLEARANCE_WIDE_IN if superstructure_width_ft > 60.0
            else LATERAL_CLEARANCE_IN)


# ── layout (drawable subset) ──────────────────────────────────────────────
#
# Masonry (base) plate F x G x (a nominal thickness, not separately
# tabulated -- H is overall height instead), a cylindrical bearing pin of
# diameter DIA resting in a saddle, and a top plate A x B under the
# girder. Anchor rods, welds, and bearing seat reinforcing are cataloged
# (the dims/notes above) but not drawn.

@dataclass(frozen=True)
class FixedBearingLayout:
    fb: FixedBearing
    base_outline: tuple[Point, Point, Point, Point]
    base_thickness_in: float
    top_outline: tuple[Point, Point, Point, Point]
    top_z_in: float
    pin_diameter_in: float
    pin_center: Point
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_fixed_bearing(fb: FixedBearing) -> FixedBearingLayout:
    """Generate the drawable subset of one FB-1-82 line: the masonry
    plate, the top plate, and the bearing pin centerline.

    ``E`` is used as the masonry plate thickness (it is the smallest
    tabulated dimension, consistent with a base-plate thickness) and
    ``H`` as the clearance from the top of that plate to the pin center,
    so the stack (plate + pin + top plate) is self-consistent even though
    the sheet does not label a dimension "base plate thickness" outright
    -- see SCD_BUILD_QUESTIONS.md."""
    d = fb.dims
    F, G, H, E, A, B, DIA = (d["F"], d["G"], d["H"], d["E"], d["A"], d["B"],
                             d["DIA"])
    half_f, half_g = F / 2.0, G / 2.0
    half_a, half_b = A / 2.0, B / 2.0

    base_thickness = E
    base_outline = ((-half_f, -half_g, 0.0), (half_f, -half_g, 0.0),
                    (half_f, half_g, 0.0), (-half_f, half_g, 0.0))
    pin_z = E + H
    top_z = pin_z + DIA / 2.0
    top_outline = ((-half_a, -half_b, top_z), (half_a, -half_b, top_z),
                  (half_a, half_b, top_z), (-half_a, half_b, top_z))
    pin_center = (0.0, 0.0, pin_z)

    notes = (
        f"FB-1-82 {fb.designation}: max load {fb.max_load_lb:,.0f} lb, "
        f"base {F:g} x {G:g} in, pin dia {DIA:g} in, overall height "
        f"{H:g} in",
        f"Anchor rods: {'2 (diagonal corners)' if fb.two_anchor_rods else '4 (one per corner)'}, "
        f"{ANCHOR_ROD_DIA_IN:g} in dia x {ANCHOR_ROD_LENGTH_IN / 12.0:.2f} ft"
        + (" -- bearing stiffeners required both sides of web."
           if fb.stiffeners_required else "."),
        "Not modeled: anchor rods, welds, bearing seat reinforcing, "
        "preformed bearing pad.",
    )

    return FixedBearingLayout(
        fb=fb,
        base_outline=base_outline,
        base_thickness_in=base_thickness,
        top_outline=top_outline,
        top_z_in=top_z,
        pin_diameter_in=DIA,
        pin_center=pin_center,
        notes=notes,
    )
