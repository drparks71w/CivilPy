#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT three-span continuous slab bridges (CS-1-24).

Transcribed from Ohio DOT Standard Bridge Drawing **CS-1-24**, "Continuous
Slab Bridge" (rev. 01-16-2026, 4 sheets). The drawing remains the
controlling document. SB-1-24's continuous-span sibling; CPP-1-08 is its
pier (``civilpy.structural.odot.capped_pile_pier``).

Sheet 2's ``SLAB DATA`` table gives, for 33 tabulated **end spans** (14 to
46 ft), the slab thickness and the full longitudinal (A/B bottom, C/D top,
E top-at-pier) and transverse (N bottom, M top, U lap) reinforcing
schedule -- 779 numeric entries, the largest table in the SCD program.
The **interior span is always 1.25x the end span** (a fixed ratio baked
into the "SPANS (FEET)" column, e.g. "14 - 17.50 - 14"), not a separately
tabulated value -- see :func:`interior_span_ft`. Sheet 1 also gives the Y
offset formula for the first M-bar (:func:`m_bar_offset_in`).

Design basis (sheet 2 notes): same as SB-1-24 -- AASHTO LRFD 9th Ed. +
ODOT BDM (July 2023); HL-93; FWS 60 lb/ft^2; 1 in monolithic wearing
surface; concrete f'c = 4500 psi; reinforcing steel min. yield 60,000
psi, epoxy coated. Applicable for roadway widths >= 24 ft and skew <=
25 deg (identical applicability notes to SB-1-24). Additional interior
spans (same length as the middle span) may be added without changing
slab thickness or area of reinforcing steel (sheet 2 General note).

Conventions match :mod:`civilpy.structural.odot.slab_bridge`: X along
stations, Y transverse, Z up; feet in plan, inches for section
dimensions. The layout origin sits at the first (upstream) abutment
bearing line, y = 0 at one slab edge, z = 0 at the top of slab.
"""

import math
from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "CS-1-24"
REVISION = "01-16-2026"

# ── design data (sheet 2 notes, shared with SB-1-24) ─────────────────────

ROADWAY_WIDTH_MIN_FT = 24.0
SKEW_MAX_DEG = 25.0
DESIGN_METHOD = "LRFD"
DESIGN_SPEC = "AASHTO LRFD Bridge Design Specifications, 9th Ed. + ODOT BDM (July 2023)"
DESIGN_LOADING = "HL-93"
FUTURE_WEARING_SURFACE_PSF = 60.0
WEARING_SURFACE_THICKNESS_IN = 1.0
CONCRETE_STRENGTH_PSI = 4500.0
REBAR_YIELD_PSI = 60000.0

#: Interior span = end span * this ratio (fixed on every tabulated row).
INTERIOR_SPAN_RATIO = 1.25

#: Lap splice lengths by bar size, feet ("TOP"/"BOT" where the sheet gives
#: both; #4/#5/#6 give a single length).
LAP_SPLICE_FT = {
    4: {"single": 3.0},
    5: {"single": 3.0 + 10.0 / 12.0},
    6: {"single": 4.0 + 4.0 / 12.0},
    8: {"top": 6.0 + 7.0 / 12.0, "bot": 7.0 + 3.0 / 12.0},
    9: {"top": 7.0 + 4.0 / 12.0, "bot": 8.0 + 11.0 / 12.0},
    10: {"top": 8.0 + 9.0 / 12.0, "bot": 10.0 + 11.0 / 12.0},
}


def interior_span_ft(end_span_ft: float) -> float:
    """Interior span = end span * 1.25 (fixed ratio, sheet 2's SLAB DATA
    "SPANS" column, e.g. 14 ft end -> 17.50 ft interior)."""
    return end_span_ft * INTERIOR_SPAN_RATIO


def m_bar_offset_in(bridge_limits_ft: float, n_m_bars: int,
                    m_bar_spacing_ft: float) -> float:
    """Sheet 1's ``Y`` formula: the offset from the bearing line to the
    first M-bar, ``Y = 1/2 * [bridge limits - (n_m_bars - 1) * spacing] * 12``
    (inches)."""
    return 0.5 * (bridge_limits_ft
                  - (n_m_bars - 1) * m_bar_spacing_ft) * 12.0


# ── SLAB DATA (sheet 2) ───────────────────────────────────────────────────

@dataclass(frozen=True)
class BarSpec:
    spacing_in: float
    size: int


@dataclass(frozen=True)
class ABarSpec(BarSpec):
    a_ft: float
    length_ft: float


@dataclass(frozen=True)
class LenBarSpec(BarSpec):
    length_ft: float


@dataclass(frozen=True)
class CountBarSpec(BarSpec):
    count: int


@dataclass(frozen=True)
class CSSlabDesign:
    """One ``SLAB DATA`` table row (sheet 2), keyed by end span (ft)."""

    end_span_ft: int
    thickness_in: float
    a_bar: ABarSpec     # bottom, end span (with "a" -- see bending diagram note)
    b_bar: LenBarSpec   # bottom, interior span
    c_bar: LenBarSpec   # top, over the abutment
    d_bar: LenBarSpec   # top, centered over the pier
    e_bar: LenBarSpec | None   # top, additional bar near the pier (spans >= 22 ft)
    n_bar: CountBarSpec  # transverse bottom
    m_bar: CountBarSpec  # transverse top
    u_bar_count: int      # laps with the additional N-bars at abutments/piers


def _row(span, t, a_spa, a_a, a_len, b_spa, b_len, c_spa, c_len,
         d_spa, d_size, d_len, e, n_no, m_no, u) -> CSSlabDesign:
    # e = (size, spacing_in, length_ft) as transcribed from the sheet's own
    # SIZE/SPA/LENGTH column order; LenBarSpec's fields are (spacing_in,
    # size, length_ft), so the first two must be swapped here.
    e_bar = LenBarSpec(e[1], e[0], e[2]) if e is not None else None
    return CSSlabDesign(
        end_span_ft=span, thickness_in=t,
        a_bar=ABarSpec(a_spa, 8 if t < 21.5 else (9 if t < 26.5 else 10),
                      a_a, a_len),
        b_bar=LenBarSpec(b_spa, 8 if t < 21.5 else (9 if t < 26.5 else 10), b_len),
        c_bar=LenBarSpec(c_spa, 5, c_len),
        d_bar=LenBarSpec(d_spa, d_size, d_len),
        e_bar=e_bar,
        n_bar=CountBarSpec(15.0, 6, n_no),
        m_bar=CountBarSpec(12.0, 4 if t < 20 else 5, m_no),
        u_bar_count=u,
    )


#: CS-1-24 ``SLAB DATA``, keyed by end span (ft). D-bar SIZE is transcribed
#: explicitly per row (it steps 8->9 at span 30 and 9->10 at span 38, which
#: does *not* line up with the A/B/M-bar thickness thresholds below -- do
#: not infer it from ``t``). A/B-bar size steps 8->9 at span 35 (T=21.5)
#: and 9->10 at span 45 (T=26.5); M-bar size steps 4->5 at span 32 (T=20).
CS_SLAB_DESIGNS: dict[int, CSSlabDesign] = {
    d.end_span_ft: d for d in (
        _row(14, 11, 7, "16'-7\"", 17.500000, 7, 21.500000, 7, 7.500000, 7, 8, 21.166667, None, 47, 47, 78),
        _row(15, 11.5, 7, "17'-7\"", 18.500000, 7, 22.750000, 7, 7.833333, 7, 8, 22.500000, None, 49, 50, 82),
        _row(16, 12, 7, "18'-7\"", 19.500000, 7, 24.000000, 7, 8.250000, 7, 8, 23.666667, None, 52, 53, 88),
        _row(17, 12.5, 7, "19'-7\"", 20.500000, 7, 25.250000, 7, 8.583333, 7, 8, 25.000000, None, 54, 56, 92),
        _row(18, 13, 7, "20'-7\"", 21.500000, 7, 26.500000, 7, 9.000000, 7, 8, 26.166667, None, 57, 60, 98),
        _row(19, 13.5, 7, "21'-7\"", 22.500000, 7, 27.750000, 7, 9.333333, 7, 8, 27.500000, None, 60, 63, 104),
        _row(20, 14, 7, "22'-7\"", 23.500000, 7, 29.000000, 7, 9.750000, 7, 8, 28.666667, None, 62, 66, 108),
        _row(21, 14.5, 7, "23'-7\"", 24.500000, 7, 30.250000, 7, 10.083333, 7, 8, 30.000000, None, 65, 69, 114),
        _row(22, 15, 7, "24'-7\"", 25.500000, 7, 31.500000, 7, 13.666667, 7, 8, 24.833333, (5, 7, 9.916667), 67, 73, 118),
        _row(23, 15.5, 7, "25'-7\"", 26.500000, 7, 32.750000, 7, 14.250000, 7, 8, 25.666667, (5, 7, 10.333333), 70, 76, 124),
        _row(24, 16, 7, "26'-7\"", 27.500000, 7, 34.000000, 6, 14.833333, 6, 8, 26.583333, (5, 6, 10.833333), 73, 79, 130),
        _row(25, 16.5, 7, "27'-7\"", 28.500000, 7, 35.250000, 6, 15.416667, 6, 8, 27.333333, (5, 6, 11.250000), 75, 82, 134),
        _row(26, 17, 7, "28'-7\"", 29.500000, 7, 36.500000, 6, 16.083333, 6, 8, 28.083333, (5, 6, 11.666667), 78, 86, 140),
        _row(27, 17.5, 7, "29'-7\"", 30.500000, 7, 37.750000, 6, 16.666667, 6, 8, 28.833333, (5, 6, 12.166667), 80, 89, 144),
        _row(28, 18, 6, "30'-7\"", 31.500000, 6, 39.000000, 6, 17.250000, 6, 8, 29.666667, (5, 6, 12.583333), 83, 92, 150),
        _row(29, 18.5, 6, "31'-7\"", 32.500000, 6, 40.250000, 6, 17.833333, 6, 8, 30.583333, (5, 6, 13.000000), 86, 95, 156),
        _row(30, 19, 6, "32'-7\"", 33.500000, 6, 41.500000, 7, 18.416667, 7, 9, 33.000000, (5, 7, 13.500000), 88, 99, 160),
        _row(31, 19.5, 6, "33'-7\"", 34.500000, 6, 42.750000, 7, 19.000000, 7, 9, 33.833333, (5, 7, 13.916667), 91, 102, 166),
        _row(32, 20, 6, "34'-7\"", 35.500000, 6, 44.000000, 7, 19.666667, 7, 9, 34.500000, (5, 7, 14.333333), 93, 105, 170),
        _row(33, 20.5, 6, "35'-7\"", 36.500000, 6, 45.250000, 6, 20.250000, 6, 9, 35.333333, (5, 6, 14.750000), 96, 108, 176),
        _row(34, 21, 6, "36'-7\"", 37.500000, 6, 46.500000, 6, 20.833333, 6, 9, 36.250000, (5, 6, 15.166667), 99, 112, 182),
        _row(35, 21.5, 7, "37'-10\"", 39.083333, 7, 48.250000, 6, 21.416667, 6, 9, 37.000000, (5, 6, 15.666667), 101, 115, 186),
        _row(36, 22, 7, "38'-10\"", 40.083333, 7, 49.500000, 6, 22.000000, 6, 9, 37.833333, (5, 6, 16.083333), 104, 118, 192),
        _row(37, 22.5, 7, "39'-10\"", 41.083333, 7, 50.750000, 6, 22.583333, 6, 9, 38.750000, (5, 6, 16.583333), 106, 121, 196),
        _row(38, 23, 7, "40'-10\"", 42.083333, 7, 52.000000, 7, 23.250000, 7, 10, 41.333333, (5, 7, 17.000000), 109, 125, 202),
        _row(39, 23.5, 7, "41'-10\"", 43.083333, 7, 53.250000, 7, 23.833333, 7, 10, 42.250000, (5, 7, 17.500000), 112, 128, 208),
        _row(40, 24, 7, "42'-10\"", 44.083333, 7, 54.500000, 7, 24.416667, 7, 10, 43.000000, (5, 7, 17.916667), 114, 131, 212),
        _row(41, 24.5, 6, "43'-10\"", 45.083333, 6, 55.750000, 6, 25.000000, 6, 10, 43.833333, (5, 6, 18.416667), 117, 134, 218),
        _row(42, 25, 6, "44'-10\"", 46.083333, 6, 57.000000, 6, 25.666667, 6, 10, 44.500000, (5, 6, 18.833333), 119, 138, 222),
        _row(43, 25.5, 6, "45'-10\"", 47.083333, 6, 58.250000, 6, 26.250000, 6, 10, 45.333333, (5, 6, 19.250000), 122, 141, 228),
        _row(44, 26, 6, "46'-10\"", 48.083333, 6, 59.500000, 6, 26.833333, 6, 10, 46.250000, (5, 6, 19.666667), 125, 144, 234),
        _row(45, 26.5, 7, "48'-1\"", 49.500000, 7, 61.250000, 6, 27.416667, 6, 10, 47.000000, (5, 6, 20.166667), 127, 147, 238),
        _row(46, 27, 7, "49'-1\"", 50.500000, 7, 62.500000, 6, 28.083333, 6, 10, 47.750000, (5, 6, 20.666667), 130, 151, 244),
    )
}


def cs_slab_design(end_span_ft: int) -> CSSlabDesign:
    """Look up the CS-1-24 slab design for an end span (feet, 14-46
    tabulated; interior span is always 1.25x, see :func:`interior_span_ft`).

    Raises ``ValueError`` naming the valid spans otherwise."""
    try:
        return CS_SLAB_DESIGNS[int(end_span_ft)]
    except (KeyError, ValueError):
        raise ValueError(
            f"CS-1-24 tabulates end spans 14-46 ft, not {end_span_ft!r}"
        ) from None


# ── layout ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ContinuousSlabInput:
    end_span_ft: int
    width_ft: float
    skew_deg: float = 0.0


@dataclass(frozen=True)
class BarRun:
    mark: str
    size: int
    points: tuple[Point, ...]


@dataclass(frozen=True)
class ContinuousSlabLayout:
    """The generated three-span continuous slab bridge. ``outline`` is the
    skewed plan parallelogram at z = 0 (top of slab, uniform thickness --
    haunches over the piers are not modeled); ``pier_stations`` are the
    two pier centerline X coordinates."""

    inputs: ContinuousSlabInput
    outline: tuple[Point, Point, Point, Point]
    thickness_in: float
    total_length_ft: float
    pier_stations: tuple[float, float]
    bars: tuple[BarRun, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)


def _distributed_bars(mark: str, size: int, count: int, width_ft: float,
                      x0: float, x1: float, z_ft: float, tan_skew: float,
                      edge_clear_ft: float = 0.25) -> tuple[BarRun, ...]:
    usable = width_ft - 2.0 * edge_clear_ft
    n = max(2, count)
    runs = []
    for i in range(n):
        y = edge_clear_ft + usable * i / (n - 1)
        u_shift = y * tan_skew
        runs.append(BarRun(mark, size,
                           ((x0 + u_shift, y, z_ft), (x1 + u_shift, y, z_ft))))
    return tuple(runs)


def layout_continuous_slab(inp: ContinuousSlabInput) -> ContinuousSlabLayout:
    """Generate a three-span continuous slab bridge: plan outline,
    thickness, pier stations, and the A/B/C/D/E longitudinal bar mats
    (transverse N/M bars are cataloged by count, not separately drawn).

    Raises ``ValueError`` for an untabulated end span or a skew beyond the
    sheet's 25 deg limit."""
    design = cs_slab_design(inp.end_span_ft)
    if abs(inp.skew_deg) > SKEW_MAX_DEG + 1e-9:
        raise ValueError(
            f"CS-1-24 is applicable for skew <= {SKEW_MAX_DEG:g} deg; "
            f"{inp.skew_deg:g} deg exceeds it")

    W = inp.width_ft
    end = inp.end_span_ft
    interior = interior_span_ft(end)
    L = 2.0 * end + interior
    tan_skew = math.tan(math.radians(inp.skew_deg))
    T = design.thickness_in
    pier_stations = (end, end + interior)

    def pt(u: float, y: float) -> Point:
        return (u + y * tan_skew, y, 0.0)

    outline = (pt(0.0, 0.0), pt(0.0, W), pt(L, W), pt(L, 0.0))

    z_bot = -(T - 2.5) / 12.0
    z_top = -2.5 / 12.0

    bars: list[BarRun] = []
    bars += _distributed_bars("A", design.a_bar.size, design.n_bar.count // 2,
                              W, 0.0, design.a_bar.length_ft, z_bot, tan_skew)
    bars += _distributed_bars("B", design.b_bar.size, design.n_bar.count // 2,
                              W, end, end + design.b_bar.length_ft,
                              z_bot, tan_skew)
    bars += _distributed_bars("C", design.c_bar.size, design.m_bar.count // 2,
                              W, 0.0, design.c_bar.length_ft, z_top, tan_skew)
    bars += _distributed_bars(
        "D", design.d_bar.size, design.m_bar.count // 2, W,
        pier_stations[0] - design.d_bar.length_ft / 2.0,
        pier_stations[0] + design.d_bar.length_ft / 2.0, z_top, tan_skew)
    if design.e_bar is not None:
        bars += _distributed_bars(
            "E", design.e_bar.size, design.m_bar.count // 4, W,
            pier_stations[0] - design.e_bar.length_ft / 2.0,
            pier_stations[0] + design.e_bar.length_ft / 2.0, z_top, tan_skew)

    notes = (
        f"CS-1-24 continuous slab bridge: end span {end:g} ft, interior "
        f"span {interior:g} ft (= 1.25x end span), T {T:g} in, width "
        f"{W:g} ft, skew {inp.skew_deg:g} deg, total length {L:.2f} ft",
        f"Transverse: {design.n_bar.count} x #{design.n_bar.size} N-bars "
        f"(bottom) @ {design.n_bar.spacing_in:g} in, "
        f"{design.m_bar.count} x #{design.m_bar.size} M-bars (top) @ "
        f"{design.m_bar.spacing_in:g} in, {design.u_bar_count} U-bars",
        "Not modeled: haunches/thickness transition over piers (uniform T "
        "assumed), edge beam, bent A/B-bar ends, transverse N/M bars "
        "(cataloged by count only, not drawn), camber, abutment "
        "diaphragm (CPA-1-08), pier (CPP-1-08).",
    )

    return ContinuousSlabLayout(
        inputs=inp,
        outline=outline,
        thickness_in=T,
        total_length_ft=L,
        pier_stations=pier_stations,
        bars=tuple(bars),
        notes=notes,
    )
