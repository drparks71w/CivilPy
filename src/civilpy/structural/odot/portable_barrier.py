#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ODOT PCB-91 Standard Portable Concrete Barrier Details.

Transcribed from Ohio DOT Standard Construction Drawing **PCB-91**
(revised 07-17-2020, 1 sheet).  The drawing remains the controlling
document.  Crash-test levels, materials, and the catalog listing live in
:mod:`civilpy.structural.odot.bridge_railing` (designations
``"PCB (portable, unanchored)"`` — NCHRP 350 TL-3 — and
``"PCB (portable, anchored)"`` — TL-4 fully anchored on the traffic
side); this module adds the drawable geometry: the New Jersey shape
section, segment/joint layout, anchor-hole stations, and the
drainage/lifting slot.

Segments are 10'-0" or 12'-0" long, connected by 3/4 in dia. galvanized
hinge-bar loops pinned with a vertical 1-1/4 in dia. H.S. bolt (plate
washers + hex nut): barriers are set closer together so the bolt drops
through the loops, and joints must be fully open (1-3/4 in max gap)
before the nut is tightened.  Anchors are 1 in dia. H.S. bolts through
1-1/4 in dia. holes — thru bolts or partial-depth bolts embedded a
minimum of 6-1/2 in and grouted (705.20).  Concrete f'c >= 4,000 psi;
all hardware per 711.09 (ASTM A325), galvanized per 711.02; reinforcing
(including hinge bars) per 509.02.  Segments are marked ``PCB-BXX-350``
(XX = year cast) in 2 in impressed lettering.

Units: section dimensions in inches, run stations in feet.
"""

from dataclasses import dataclass

SCD = "PCB-91"
REVISION = "07-17-2020"

# ── cross-section (view A-A / section B-B) ───────────────────────────────

HEIGHT_IN = 32.0
BASE_WIDTH_IN = 24.0
TOP_WIDTH_IN = 6.0
TOE_HEIGHT_IN = 3.0          # vertical face at the base
LOWER_FACE_RISE_IN = 10.0    # over a 7 in horizontal run each side
LOWER_FACE_RUN_IN = 7.0
UPPER_FACE_RISE_IN = 19.0    # over a 2 in horizontal run each side
UPPER_FACE_RUN_IN = 2.0
TOP_CHAMFER_IN = 0.75        # 1 in radius or 3/4 in chamfer, all top/end
PERMISSIBLE_BREAK_RADIUS_IN = 10.0   # at the slope break
PERMISSIBLE_TOE_RADIUS_IN = 1.0      # at the toe

# Drainage and lifting slot, centered along the segment (section B-B).
SLOT_WIDTH_IN = 14.0         # base shows 5" | 1'-2" | 5"
SLOT_HEIGHT_IN = 7.0
SLOT_LENGTH_IN = 48.0

# ── segments, joints, anchors ────────────────────────────────────────────

SEGMENT_LENGTHS_FT = (10.0, 12.0)
CLOSED_JOINT_GAP_IN = 0.25
OPEN_JOINT_MAX_GAP_IN = 1.75
HINGE_BAR_DIAMETER_IN = 0.75
JOINT_BOLT_DIAMETER_IN = 1.25   # H.S. bolt with plate washers + hex nut

ANCHOR_HOLE_DIAMETER_IN = 1.25
ANCHOR_BOLT_DIAMETER_IN = 1.0
ANCHOR_SPACING_IN = 24.0
ANCHOR_END_OFFSET_IN = 12.0
ANCHOR_MIN_EMBED_IN = 6.5       # partial-depth bolts, grouted per 705.20

REBAR_SIZE = 5
REBAR_SPACING_IN = 12.0         # loops equally spaced along the segment
REBAR_CLEAR_IN = 1.5            # faces (3 in at the bottom legs)
CONCRETE_MIN_FC_PSI = 4_000
MARK_FORMAT = "PCB-BXX-350"     # XX = year cast, 2 in impressed letters


def profile_points_in(chamfered: bool = True
                      ) -> tuple[tuple[float, float], ...]:
    """The closed New Jersey shape section, counterclockwise from the
    bottom-left corner, as (x, y) inches with x transverse from the
    barrier centerline and y up from the deck surface.

    ``chamfered`` includes the 3/4 in top chamfers (the sheet allows a
    1 in radius instead)."""
    h = BASE_WIDTH_IN / 2.0
    mid = h - LOWER_FACE_RUN_IN                     # 5 in at the break
    top = TOP_WIDTH_IN / 2.0                        # 3 in at the top
    z1 = TOE_HEIGHT_IN
    z2 = z1 + LOWER_FACE_RISE_IN
    z3 = z2 + UPPER_FACE_RISE_IN
    assert z3 == HEIGHT_IN
    c = TOP_CHAMFER_IN
    right = [(h, 0.0), (h, z1), (mid, z2)]
    if chamfered:
        right += [(top, z3 - c), (top - c, z3)]
        left = [(-(top - c), z3), (-top, z3 - c)]
    else:
        right += [(top, z3)]
        left = [(-top, z3)]
    left += [(-mid, z2), (-h, z1), (-h, 0.0)]
    return tuple(right + left)


def anchor_hole_stations_ft(segment_length_ft: float) -> tuple[float, ...]:
    """Anchor-hole stations along one segment (ft from its start): 1'-0"
    from each end, equally spaced at 2'-0" c/c (5 holes per row on a 10 ft
    segment, 6 on a 12 ft)."""
    if segment_length_ft not in SEGMENT_LENGTHS_FT:
        raise ValueError(
            f"PCB-91 segments are {SEGMENT_LENGTHS_FT} ft long, "
            f"not {segment_length_ft}")
    start = ANCHOR_END_OFFSET_IN / 12.0
    step = ANCHOR_SPACING_IN / 12.0
    n = int(round((segment_length_ft - 2.0 * start) / step)) + 1
    return tuple(start + i * step for i in range(n))


@dataclass(frozen=True)
class BarrierSegment:
    """One placed segment: stations (ft) along the run."""

    index: int
    start_ft: float
    end_ft: float

    @property
    def length_ft(self) -> float:
        return self.end_ft - self.start_ft


def barrier_run(n_segments: int, segment_length_ft: float = 10.0,
                joint_gap_in: float = CLOSED_JOINT_GAP_IN
                ) -> tuple[BarrierSegment, ...]:
    """Lay out ``n_segments`` along a straight run with the given joint
    gap (closed 1/4 in up to the fully-open 1-3/4 in max)."""
    if n_segments < 1:
        raise ValueError("at least one segment is required")
    if segment_length_ft not in SEGMENT_LENGTHS_FT:
        raise ValueError(
            f"PCB-91 segments are {SEGMENT_LENGTHS_FT} ft long, "
            f"not {segment_length_ft}")
    if not (0.0 <= joint_gap_in <= OPEN_JOINT_MAX_GAP_IN):
        raise ValueError(
            f"joint gap must be 0 to the {OPEN_JOINT_MAX_GAP_IN:g} in "
            "fully-open maximum")
    gap_ft = joint_gap_in / 12.0
    segs = []
    x = 0.0
    for i in range(n_segments):
        segs.append(BarrierSegment(i + 1, x, x + segment_length_ft))
        x += segment_length_ft + gap_ft
    return tuple(segs)


def run_length_ft(segments: tuple[BarrierSegment, ...]) -> float:
    """Overall length of a laid-out run (ft), including joint gaps."""
    return segments[-1].end_ft if segments else 0.0
