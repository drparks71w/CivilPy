#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ODOT AS-1-15 Reinforced Concrete Approach Slab.

Transcribed from Ohio DOT Standard Construction Drawing **AS-1-15**
(revised 01-20-2023, 2 sheets).  The drawing remains the controlling
document; this module encodes its reinforcing-steel table, bar-count and
bar-length formulas, section geometry, and the sheet-2 joint/seat detail
catalog so the Grasshopper component (``Notebooks/Rhino Components/AS-1-15.py``) and
downstream quantity takeoffs can be driven from tested Python.

Design basis printed on the sheet: AASHTO LRFD Bridge Design
Specifications (2014) and ODOT BDM (2007); dead load 60 lb/ft^2 (FWS),
live load HL-93; concrete f'c = 4,500 psi; reinforcing steel fy = 60,000
psi (pay item: ITEM 526 - REINFORCED CONCRETE APPROACH SLABS, anchor bars
paid separately under ITEM 509).

Conventions match :mod:`civilpy.structural.bridge_layout`: plan frame with
X along stations (increasing away from the bridge), Y transverse, Z up,
Z = 0 at the top of the approach slab; plan lengths in feet, section
dimensions in inches (``_in`` suffixes).  Positive skew rotates the
support (bridge-limit) line counterclockwise in plan, so points at +Y
shift toward +X.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "AS-1-15"
REVISION = "01-20-2023"

# ── design data (sheet 1, DESIGN DATA block) ─────────────────────────────

CONCRETE_STRENGTH_PSI = 4_500
REBAR_YIELD_PSI = 60_000
FUTURE_WEARING_SURFACE_PSF = 60.0
LIVE_LOAD = "HL-93"
PAY_ITEM = "ITEM 526 - REINFORCED CONCRETE APPROACH SLABS"

# Covers and edge clearances (sheet 1, sections A-A and B-B).
TOP_COVER_IN = 3.0            # "3 in clear" to the top mat
BOTTOM_COVER_IN = 3.0         # "3 in clear" to the bottom mat
SIDE_COVER_TOTAL_FT = 0.5     # B/C/D counts and B lengths use (W - 0.5)
END_CLEARANCE_FT = 0.25       # 3 in from each skewed end to the first bar

# Standing spacings not in the table (sheet 1).
C_BAR_SPACING_IN = 6.0        # C bars @ 6 in +/- c/c, top
B501_TOP_SPACING_IN = 6.0     # B501 top @ 6 in +/- c/c
B501_END_SPACES = 5           # bottom B501: 5 spaces @ 6 in at bridge end
B501_END_SPACING_IN = 6.0
D_BAR_SPACING_IN = 18.0       # D801/D802 @ 1'-6" c/c perp. to CL roadway

# Bridge-end (seat) geometry, section B-B.
SEAT_LENGTH_MIN_IN = 6.0      # "6 in TO 1'-0"" bearing on seat/backwall
SEAT_LENGTH_MAX_IN = 12.0
END_TAPER_RUN_PER_RISE = 2.0  # bottom transitions at 2 horizontal : 1 vertical
D_BAR_EDGE_OFFSET_IN = 2.5    # D bar crosses slab bottom 2.5 in from limit
D_BAR_CLEARANCE_IN = 2.25     # 2-1/4 +/- 1/4 in clear along the seat
EXPANSION_JOINT_FILLER_IN = 1.0   # 1 in preformed filler, 705.03 (typ.)
EDGE_JOINT_FILLER_IN = 2.5        # 2-1/2 in at each slab edge (section A-A)

# D801/D802 anchor-bar usage limits (sheet 1, note **).
D801_MIN_BACKWALL_IN = 14.0   # D801 cannot be used on backwalls < 14 in
D802_BACKWALL_IN = 11.0       # D802 for PS box beam bridges, 11 in backwall

# Bar sizes implied by the marks (A1001 -> #10, B501 -> #5, ...).
A_BAR_SIZE = 10
B_BAR_SIZE = 5
C_BAR_SIZE = 5
D_BAR_SIZE = 8


# ── the reinforcing steel table (sheet 1, FOR ONE APPROACH SLAB) ─────────

@dataclass(frozen=True)
class ApproachSlabDesign:
    """One row of the AS-1-15 reinforcing steel table.

    Lengths in feet, spacings/thicknesses in inches.  Bar counts that
    depend on the slab width W are computed by the module-level functions,
    matching the tabulated formulas (e.g. ``12(W-0.5)/K + 1``).
    """

    length_ft: float               # L, out-to-out along the roadway
    thickness_in: float            # T, uniform depth away from the seat
    a_bar_spacing_in: float        # K
    a_bar_mark: str
    a_bar_length_ft: float         # total bar length incl. end bends
    a_bar_dimension_ft: float      # DIMENSION A, out-to-out in plan
    b501_bottom_spacing_in: float  # N
    b501_bottom_count: int
    b501_top_count: int
    c_bar_mark: str
    c_bar_length_ft: float


APPROACH_SLAB_DESIGNS: dict[float, ApproachSlabDesign] = {
    15.0: ApproachSlabDesign(15.0, 12.0, 10.0, "A1001", 15.0 + 11 / 12,
                             14.5, 9.0, 22, 30, "C501", 14.5),
    20.0: ApproachSlabDesign(20.0, 13.0, 7.5, "A1002", 20.0 + 11 / 12,
                             19.5, 8.0, 31, 40, "C502", 19.5),
    25.0: ApproachSlabDesign(25.0, 15.0, 7.0, "A1003", 25.0 + 11 / 12,
                             24.5, 8.0, 39, 50, "C503", 24.5),
    30.0: ApproachSlabDesign(30.0, 17.0, 6.5, "A1004", 30.0 + 11 / 12,
                             29.5, 8.5, 44, 60, "C504", 29.5),
}


def approach_slab_design(length_ft: float) -> ApproachSlabDesign:
    """The standard design for an approach slab length L (ft)."""
    try:
        return APPROACH_SLAB_DESIGNS[float(length_ft)]
    except KeyError:
        raise ValueError(
            f"AS-1-15 tabulates approach slab lengths "
            f"{sorted(APPROACH_SLAB_DESIGNS)} ft only, not {length_ft}"
        ) from None


# ── width-dependent counts and lengths (tabulated formulas) ──────────────

def _count_across(width_ft: float, spacing_in: float) -> int:
    """The sheet's bracketed count ``[12(W - 0.5)/spacing] + 1``: the
    number of spaces is rounded up so the placed spacing never exceeds the
    tabulated one."""
    if width_ft <= SIDE_COVER_TOTAL_FT:
        raise ValueError(f"approach slab width {width_ft} ft is too small")
    spaces = 12.0 * (width_ft - SIDE_COVER_TOTAL_FT) / spacing_in
    return int(math.ceil(spaces - 1e-9)) + 1


def a_bar_count(width_ft: float, design: ApproachSlabDesign) -> int:
    """A-bar count per slab: ``[12(W-0.5)/K] + 1``."""
    return _count_across(width_ft, design.a_bar_spacing_in)


def c_bar_count(width_ft: float) -> int:
    """C-bar count per slab: ``[12(W-0.5)/6] + 1``."""
    return _count_across(width_ft, C_BAR_SPACING_IN)


def d_bar_count(width_ft: float) -> int:
    """D801/D802 anchor-bar count: ``[12(W-0.5)/18] + 1``."""
    return _count_across(width_ft, D_BAR_SPACING_IN)


def b501_length_ft(width_ft: float, skew_deg: float = 0.0) -> float:
    """B501 bar length ``(W - 0.5) sec(theta)`` (ft)."""
    return ((width_ft - SIDE_COVER_TOTAL_FT)
            / math.cos(math.radians(skew_deg)))


def d801_length_ft(end_thickness_ft: float, skew_deg: float = 0.0) -> float:
    """D801 anchor bar length (ft): 1'-0" leg + ``(1.414X + 0.823)sec
    (theta)`` diagonal (X = slab thickness at the abutment end, ft).  The
    180-degree hook at the free end is included in the diagonal term as
    tabulated."""
    sec = 1.0 / math.cos(math.radians(skew_deg))
    return 1.0 + (1.414 * end_thickness_ft + 0.823) * sec


def d802_length_ft(end_thickness_ft: float, skew_deg: float = 0.0) -> float:
    """D802 anchor bar length (ft): 1'-0" + ``(1.414X + 0.202)sec(theta)``
    + 1'-0"."""
    sec = 1.0 / math.cos(math.radians(skew_deg))
    return 2.0 + (1.414 * end_thickness_ft + 0.202) * sec


def anchor_bar_mark(backwall_thickness_in: float) -> str:
    """Which anchor bar the sheet permits for a given backwall thickness.

    D801 cannot be used on backwalls less than 14 in thick; D802 is for
    prestressed box beam bridges with 11 in backwalls."""
    if backwall_thickness_in >= D801_MIN_BACKWALL_IN:
        return "D801"
    if backwall_thickness_in >= D802_BACKWALL_IN:
        return "D802"
    raise ValueError(
        f"AS-1-15 anchor bars require a backwall at least "
        f"{D802_BACKWALL_IN:g} in thick (got {backwall_thickness_in:g} in)"
    )


def pay_area_sy(length_ft: float, width_ft: float) -> float:
    """Estimated ITEM 526 quantity (square yards): plan area L x W."""
    return length_ft * width_ft / 9.0


# ── sheet 2: seat configurations and joint details ───────────────────────

JOINT_NOTES: dict[int, str] = {
    1: "Preformed elastomeric compression joint seal, 705.11 (1-1/4 in "
       "wide for a 1/2 in wide groove) placed in 1/2 in x 2-1/4 in groove.",
    2: "2 in deep x 1 in wide hot applied joint sealer, 705.04.",
    3: "1 in preformed expansion joint filler, 705.03.",
    4: 'Type "A" or Type "E" waterproofing.',
    5: "See C&MS Item 409 - sawing and sealing asphalt concrete pavement "
       "joints.",
    6: 'See Supplemental Specification 846, "Polymer Modified Asphalt '
       'Expansion Joint System".',
}


@dataclass(frozen=True)
class SeatConfiguration:
    """One sheet-2 configuration: which joint details apply at the bridge
    limit for a support type + wearing surface combination."""

    support: str          # "slab bridge" | "abutment backwall" |
                          # "ps box beam" | "integral"
    wearing_surface: str  # "concrete both" | "asphalt both" |
                          # "concrete deck only"
    details: tuple[str, ...]


SEAT_CONFIGURATIONS: tuple[SeatConfiguration, ...] = (
    SeatConfiguration("slab bridge", "concrete both", ("B",)),
    SeatConfiguration("ps box beam", "asphalt both", ("A", "E")),
    SeatConfiguration("abutment backwall", "asphalt both", ("A", "E")),
    SeatConfiguration("integral", "concrete both", ("B",)),
    SeatConfiguration("ps box beam", "concrete both", ("D",)),
    SeatConfiguration("abutment backwall", "concrete both", ("B",)),
    SeatConfiguration("abutment backwall", "concrete deck only", ("C",)),
    SeatConfiguration("ps box beam", "concrete deck only", ("F",)),
)

JOINT_DETAILS: dict[str, tuple[int, ...]] = {
    # detail letter -> sheet-2 note numbers it references
    "A": (2, 3, 5),
    "B": (1, 4),
    "C": (2, 4),
    "D": (3, 6),
    "E": (3, 6),
    "F": (3, 6),
}


# ── layout ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ApproachSlabInput:
    """The design choices an engineer makes on the project plans.

    ``length_ft`` must be one of the tabulated L values.  ``width_ft`` is
    the approach slab width W per the sheet's width-dimension figure
    (out-to-out without curbs, toe-to-toe of curbs, or toe-to-toe of
    barrier).  ``end_thickness_in`` is X (thickness at the abutment end);
    the sheet requires X >= T and expresses X in feet in its formulas.
    ``seat_length_in`` is the bearing length on the seat/backwall (6 in to
    1'-0" per section B-B).  ``backwall_thickness_in`` selects the anchor
    bar (D801 needs >= 14 in; D802 covers the 11 in PS box beam case).
    """

    length_ft: float
    width_ft: float
    skew_deg: float = 0.0
    end_thickness_in: float | None = None   # default: T
    seat_length_in: float = 9.0
    backwall_thickness_in: float = 14.0


@dataclass(frozen=True)
class BarRun:
    """One physical bar as a polyline of plan-frame points (feet)."""

    mark: str
    size: int
    points: tuple[Point, ...]


@dataclass(frozen=True)
class ApproachSlabLayout:
    """Everything the Grasshopper component draws.

    ``outline`` is the counterclockwise plan parallelogram at z = 0 (top
    of slab), starting at the bridge-limit / y = 0 corner.  ``profile``
    is the longitudinal section polyline in (u, z) feet, u measured from
    the bridge limit along the roadway; it is swept transversely (with the
    skew shear) to form the solid.
    """

    inputs: ApproachSlabInput
    design: ApproachSlabDesign
    outline: tuple[Point, Point, Point, Point]
    profile: tuple[tuple[float, float], ...]
    bars: tuple[BarRun, ...]
    anchor_mark: str
    anchor_length_ft: float
    pay_area_sy: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def _bar_z(*, top: bool, layer: int, bar_dia_in: float, stack_dia_in: float,
           thickness_in: float) -> float:
    """Centerline z (ft, top of slab = 0) for a bar on the given face.

    ``layer`` 0 sits on the cover; layer 1 stacks inside it on top of a
    bar of ``stack_dia_in``."""
    inset = (TOP_COVER_IN if top else BOTTOM_COVER_IN) \
        + layer * stack_dia_in + bar_dia_in / 2.0
    return -inset / 12.0 if top else -(thickness_in - inset) / 12.0


def layout_approach_slab(inp: ApproachSlabInput) -> ApproachSlabLayout:
    """Generate the AS-1-15 approach slab layout.

    Raises ``ValueError`` when inputs leave the drawing's assumptions
    (untabulated length, X < T, seat length outside 6-12 in, skew >= 60
    degrees, or a backwall too thin for either anchor bar).
    """
    from civilpy.structural.steel import Rebar

    design = approach_slab_design(inp.length_ft)
    if inp.width_ft <= SIDE_COVER_TOTAL_FT:
        raise ValueError("approach slab width must exceed 0.5 ft")
    if abs(inp.skew_deg) >= 60.0:
        raise ValueError("skew beyond 60 degrees is not supported")
    if not (SEAT_LENGTH_MIN_IN <= inp.seat_length_in <= SEAT_LENGTH_MAX_IN):
        raise ValueError(
            f"seat length must be {SEAT_LENGTH_MIN_IN:g}-"
            f"{SEAT_LENGTH_MAX_IN:g} in per AS-1-15 section B-B"
        )

    t_in = design.thickness_in
    x_in = t_in if inp.end_thickness_in is None else inp.end_thickness_in
    if x_in < t_in - 1e-9:
        raise ValueError(
            f"X (thickness at abutment end, {x_in:g} in) shall never be "
            f"less than T ({t_in:g} in)"
        )
    anchor = anchor_bar_mark(inp.backwall_thickness_in)

    L, W = inp.length_ft, inp.width_ft
    tan_skew = math.tan(math.radians(inp.skew_deg))

    def pt(u: float, y: float, z: float) -> Point:
        """Plan point from longitudinal coordinate u (measured from the
        skewed bridge-limit line along the roadway) and transverse y."""
        return (u + y * tan_skew, y, z)

    outline = (pt(0.0, 0.0, 0.0), pt(0.0, W, 0.0),
               pt(L, W, 0.0), pt(L, 0.0, 0.0))

    # Longitudinal section profile (u, z), section B-B: full depth X at
    # the bridge limit, bearing flat on the seat, then a 1:2 rise to the
    # uniform thickness T which runs to the approach end.
    seat_ft = inp.seat_length_in / 12.0
    t_ft, x_ft = t_in / 12.0, x_in / 12.0
    taper_ft = END_TAPER_RUN_PER_RISE * (x_ft - t_ft)
    raw = ((0.0, 0.0), (L, 0.0), (L, -t_ft),
           (seat_ft + taper_ft, -t_ft), (seat_ft, -x_ft), (0.0, -x_ft))
    profile = tuple(p for i, p in enumerate(raw)
                    if i == 0 or abs(p[0] - raw[i - 1][0]) > 1e-9
                    or abs(p[1] - raw[i - 1][1]) > 1e-9)

    def dia(size: int) -> float:
        return float(Rebar(size).diameter.magnitude)

    d_a, d_b, d_c = dia(A_BAR_SIZE), dia(B_BAR_SIZE), dia(C_BAR_SIZE)

    # Layer stacking: A bars (primary) on the bottom cover with B501
    # above them (section B-B dimensions the 3 in clear to the A bars);
    # B501 on the top cover with C bars below (section A-A dimensions the
    # 3 in clear to the B501).
    z_a = _bar_z(top=False, layer=0, bar_dia_in=d_a, stack_dia_in=0.0,
                 thickness_in=t_in)
    z_b_bot = _bar_z(top=False, layer=1, bar_dia_in=d_b, stack_dia_in=d_a,
                     thickness_in=t_in)
    z_b_top = _bar_z(top=True, layer=0, bar_dia_in=d_b, stack_dia_in=0.0,
                     thickness_in=t_in)
    z_c = _bar_z(top=True, layer=1, bar_dia_in=d_c, stack_dia_in=d_b,
                 thickness_in=t_in)

    bars: list[BarRun] = []

    # A bars: bottom, parallel to CL roadway, spaced K across the width.
    n_a = a_bar_count(W, design)
    u0, u1 = END_CLEARANCE_FT, L - END_CLEARANCE_FT
    for i in range(n_a):
        frac = i / (n_a - 1) if n_a > 1 else 0.5
        y = END_CLEARANCE_FT + frac * (W - SIDE_COVER_TOTAL_FT)
        bars.append(BarRun(design.a_bar_mark, A_BAR_SIZE,
                           (pt(u0, y, z_a), pt(u1, y, z_a))))

    # C bars: top, parallel to CL roadway, @ 6 in c/c.
    n_c = c_bar_count(W)
    for i in range(n_c):
        frac = i / (n_c - 1) if n_c > 1 else 0.5
        y = END_CLEARANCE_FT + frac * (W - SIDE_COVER_TOTAL_FT)
        bars.append(BarRun(design.c_bar_mark, C_BAR_SIZE,
                           (pt(u0, y, z_c), pt(u1, y, z_c))))

    # B501: parallel to the abutment (skewed), y from 0.25 to W - 0.25.
    ya, yb = END_CLEARANCE_FT, W - END_CLEARANCE_FT

    def b501(u: float, z: float) -> BarRun:
        return BarRun("B501", B_BAR_SIZE, (pt(u, ya, z), pt(u, yb, z)))

    # bottom: 5 spaces @ 6 in from the bridge end, remainder ~N to the
    # far end (the tabulated counts anchor both ends at 3 in clear).
    n_bot = design.b501_bottom_count
    u_bot = [u0 + i * B501_END_SPACING_IN / 12.0
             for i in range(B501_END_SPACES + 1)]
    rest = n_bot - len(u_bot)
    u_last = u_bot[-1]
    for i in range(1, rest + 1):
        u_bot.append(u_last + (u1 - u_last) * i / rest)
    for u in u_bot:
        bars.append(b501(u, z_b_bot))
    # top: evenly @ ~6 in between the 3 in end clearances.
    n_top = design.b501_top_count
    for i in range(n_top):
        frac = i / (n_top - 1) if n_top > 1 else 0.5
        bars.append(b501(u0 + frac * (u1 - u0), z_b_top))

    # D801/D802 anchor bars: in vertical planes parallel to CL roadway,
    # spaced 18 in c/c measured perpendicular to the CL.  Modeled as the
    # 1'-0" backwall leg plus the 45-degree diagonal rising from below the
    # seat through the slab (the D801 terminal hook is not drawn).
    anchor_len = (d801_length_ft(x_ft, inp.skew_deg) if anchor == "D801"
                  else d802_length_ft(x_ft, inp.skew_deg))
    sec = 1.0 / math.cos(math.radians(inp.skew_deg))
    diag = (1.414 * x_ft + (0.823 if anchor == "D801" else 0.202)) * sec
    rise = diag / math.sqrt(2.0)             # total vertical extent, 45 deg
    u_cross = D_BAR_EDGE_OFFSET_IN / 12.0    # crosses the slab bottom here
    z_stop = -TOP_COVER_IN / 12.0            # diagonal stops at top cover
    z_low = z_stop - rise                    # low end, embedded in backwall
    p2 = (u_cross - (-x_ft - z_low), z_low)  # 45 deg below the crossing
    p1 = (p2[0] - 1.0, p2[1])                # 1'-0" backwall leg
    p3 = (u_cross + (z_stop + x_ft), z_stop)  # 45 deg up to the cover plane
    n_d = d_bar_count(W)
    step_y = (W - SIDE_COVER_TOTAL_FT) / (n_d - 1) if n_d > 1 else 0.0
    for i in range(n_d):
        y = END_CLEARANCE_FT + i * step_y
        bars.append(BarRun(anchor, D_BAR_SIZE, (
            pt(p1[0], y, p1[1]), pt(p2[0], y, p2[1]), pt(p3[0], y, p3[1]))))

    notes = (
        f"Design: L = {L:g} ft, T = {t_in:g} in, X = {x_in:g} in, "
        f"W = {W:g} ft, skew = {inp.skew_deg:g} deg",
        f"Anchor bars: {anchor} @ 1'-6\" c/c perp. to CL roadway, "
        f"{n_d} bars x {anchor_len:.2f} ft",
        "Not modeled: A-bar end bends, D801 terminal hook, optional "
        "widened edge portion for integral curb/barrier, curb-height "
        "transitions, deck crown/cross slope, joint seal grooves "
        "(see sheet 2 details A-F).",
    )

    return ApproachSlabLayout(
        inputs=inp,
        design=design,
        outline=outline,
        profile=profile,
        bars=tuple(bars),
        anchor_mark=anchor,
        anchor_length_ft=anchor_len,
        pay_area_sy=pay_area_sy(L, W),
        notes=notes,
    )
