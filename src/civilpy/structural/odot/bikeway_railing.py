#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT bikeway railing (SCD RM-5.2): a treated-wood post-and-rail
fence along bicycle paths.

Transcribed from Standard Roadway Construction Drawing RM-5.2, "Bikeway
Railing" (rev. 07-21-2023, 1 sheet).  A wood system — 6x6 posts with a
2x8 top rail and two 2x12 face rails — not a crashworthy barrier; it
pairs with the structures-side BR-2-15 sidewalk railing only in role,
not in section.  The drawing remains the controlling document.

Lengths in inches unless a name says otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

SCD = "RM-5.2"
REVISION = "07-21-2023"

# ── members (nominal lumber, treated per CMS 712.06) ─────────────────────
POST_SECTION = "6x6"
POST_LENGTH_IN = 78.0            #: 6 ft-6 in standard post
POST_SPACING_MAX_IN = 120.0      #: 10 ft-0 in max
POST_EMBEDMENT_MIN_IN = 36.0     #: 3 ft-0 in min (see LOW_SHOULDER note)
#: With less than 1 ft of graded shoulder beyond the rail face (10:1 or
#: flatter), use longer posts giving 5 ft-0 in embedment (note 4).
LOW_SHOULDER_EMBEDMENT_IN = 60.0
MIDSPAN_POST_SECTION = "6x6"
MIDSPAN_POST_LENGTH_IN = 18.0    #: 1 ft-6 in, 45 deg top cut, rails only
TOP_RAIL_SECTION = "2x8"
FACE_RAIL_SECTION = "2x12"
RAIL_LENGTH_MAX_FT = 20.0        #: max piece length, butt joints on posts
LOWER_FACE_RAIL_GAP_IN = 6.0     #: lower face rail clears grade by 6 in
POST_REVEAL_IN = 36.0            #: grade to underside of the top rail zone
#: Rail top height above grade (3 ft reveal + top-rail zone).
RAILING_HEIGHT_IN = 42.0

# ── placement ─────────────────────────────────────────────────────────────
OFFSET_PREFERRED_IN = 24.0       #: face of rail to edge of pavement
OFFSET_MIN_IN = 12.0
FLARED_END_LENGTH_FT = 20.0      #: each end, turned away from the path
FLARED_END_ANGLE_DEG = 30.0

# ── hardware (galvanized per CMS 711.02 / 711.10) ────────────────────────
TOP_RAIL_FASTENER = '9/16" x 6" lag bolt with washer'
FACE_RAIL_FASTENER = '1/2" carriage bolt with washer and nut'

PAY_ITEM = ("607", "FOOT", "FENCE, MISC.: WOOD FENCE")


@dataclass(frozen=True)
class BikewayRailingInput:
    """One straight bikeway railing run.  ``length_ft`` is the fence
    length between flares (as shown on plans); flared ends add
    :data:`FLARED_END_LENGTH_FT` each when ``flared_ends``."""

    length_ft: float
    flared_ends: bool = True
    low_shoulder: bool = False   #: < 1 ft graded shoulder (note 4)


@dataclass(frozen=True)
class BikewayRailingLayout:
    """Members of one bikeway railing run.

    ``post_stations_ft`` are full-post centers from the run start;
    ``midspan_stations_ft`` the 18 in rail-stiffener posts centered in
    each bay.  Rails run the full length in <= 20 ft pieces butt-
    jointed on posts (top rail and lower face rail staggered to
    alternate posts, note 6)."""

    inputs: BikewayRailingInput
    post_stations_ft: tuple[float, ...]
    midspan_stations_ft: tuple[float, ...]
    post_length_in: float
    embedment_in: float
    n_rail_pieces: int
    total_length_ft: float
    notes: tuple[str, ...] = ()


def layout_bikeway_railing(inp: BikewayRailingInput) -> BikewayRailingLayout:
    """Lay out posts and rails for one RM-5.2 bikeway railing run.

    Full posts at up to 10 ft centers with a mid-span stiffener post in
    each bay; each flared end (20 ft at 30 degrees away from the path)
    is treated as additional railing length with the same spacing.
    Raises ``ValueError`` for a non-positive length."""
    if inp.length_ft <= 0.0:
        raise ValueError("length_ft must be > 0")
    total = inp.length_ft + (2.0 * FLARED_END_LENGTH_FT
                             if inp.flared_ends else 0.0)
    spacing_ft = POST_SPACING_MAX_IN / 12.0
    n_bays = max(1, int(-(-total // spacing_ft)))   # ceil
    bay_ft = total / n_bays
    posts = tuple(round(i * bay_ft, 6) for i in range(n_bays + 1))
    midspans = tuple(round((i + 0.5) * bay_ft, 6) for i in range(n_bays))
    embed = (LOW_SHOULDER_EMBEDMENT_IN if inp.low_shoulder
             else POST_EMBEDMENT_MIN_IN)
    post_len = embed + POST_REVEAL_IN + (RAILING_HEIGHT_IN - POST_REVEAL_IN)
    # three rail lines (top + two face rails), pieces <= 20 ft
    pieces_per_line = int(-(-total // RAIL_LENGTH_MAX_FT))
    notes = (
        f"ODOT {SCD} bikeway railing (rev. {REVISION})",
        f"6x6 treated posts (CMS 712.06) at {bay_ft:.2f} ft centers, "
        f"{embed:g} in embedment; 18 in mid-span stiffener posts with "
        "45 deg top cut on the rails in each bay.",
        "2x8 top rail (9/16 x 6 lag bolts) and two 2x12 face rails "
        "(1/2 in carriage bolts, counterbored flush); stagger top/lower "
        "butt joints to alternate posts; lower face rail 6 in above "
        "grade; rail top 42 in above grade.",
        f"Offset {OFFSET_PREFERRED_IN:g} in preferred "
        f"({OFFSET_MIN_IN:g} in min) from edge of pavement"
        + ("; 20 ft flared ends at 30 deg each end."
           if inp.flared_ends else "."),
        f"Paid as Item {PAY_ITEM[0]} - {PAY_ITEM[2]} per {PAY_ITEM[1]}, "
        "all posts, rails, and hardware included.",
    )
    return BikewayRailingLayout(
        inputs=inp, post_stations_ft=posts, midspan_stations_ft=midspans,
        post_length_in=post_len, embedment_in=embed,
        n_rail_pieces=3 * pieces_per_line, total_length_ft=total,
        notes=notes)
