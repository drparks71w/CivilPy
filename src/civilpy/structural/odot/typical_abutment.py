#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT typical abutment detail for bridges with expansion joints
(A-1-20).

Transcribed from Ohio DOT Standard Bridge Drawing **A-1-20**, "Typical
Abutment Detail for Bridges with Expansion Joints" (rev. 01-19-2024,
5 sheets). The drawing remains the controlling document. Steel girders
are shown; PSID-1-13 covers the modifications for prestressed concrete
I-beams.

**This sheet is explicitly guidance, not a standalone standard** (General
note, sheet 1, verbatim): "Treat the abutment dimensions, construction
joints and reinforcing shown in this drawing as MINIMUM VALUES and
perform a complete design for the abutment. Do not reference these
drawings in the contract plans and do not use as standalone construction
drawings." That is a stronger disclaimer than BCHW/CPA-1-08's "insert
design here" blanks -- every dimension here is a floor, not a value to
build to, and this module's ``layout_typical_abutment`` should be read
the same way: a reasonable visual check, never a substitute for the
abutment design.

What's fixed: two literal formulas (the bearing-seat dimension and the
wingwall unsupported-length limit) plus a handful of section minimums
(cover, bar spacing, backwall/footing minimum widths). Concrete f'c =
4.0 ksi, reinforcing steel min. yield 60 ksi; bars are #5 unless noted.

Conventions match the rest of this package: X along stations, Y
transverse, Z up; feet in plan, inches for section dimensions. The
origin sits on the abutment centerline at the low beam seat elevation
(Z = 0), Y = 0 at the backwall centerline.
"""

import math
from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "A-1-20"
REVISION = "01-19-2024"

# ── design data ───────────────────────────────────────────────────────────

CONCRETE_STRENGTH_KSI = 4.0
REBAR_YIELD_KSI = 60.0
DEFAULT_BAR_SIZE = 5           # "unless noted otherwise, all bars are #5"
MAX_BAR_SPACING_FT = 1.5       # 1'-6" max, all bars
MAX_PILE_BAR_SPACING_FT = 1.5  # vertical bars max 1'-6" between piles
CLEAR_COVER_IN = 2.0           # "unless otherwise noted"
FOOTING_CLEAR_COVER_IN = 3.0   # footing bottom, per SECTION A-A

BEAM_SEAT_SLOPE_IN_PER_SEAT = 0.75   # 3/4 in slope between beam seats
BEAM_SEAT_BARS = "5-#8 bars in beam seat"

PEJF_THICKNESS_IN = 1.0
NPCPP_SPEC = "6 in non-perforated corrugated polyethylene pipe (C&MS 707.33 Type S)"
PCPP_SPEC = "6 in perforated corrugated polyethylene pipe (C&MS 707.33 Type SP)"
DRAINAGE_SLOPE = 1.0 / 96.0    # 1/8 in per ft

WINGWALL_MIN_HEIGHT_FT = 3.0
WINGWALL_ROUNDING_FT = 4.0     # 2'-0" + 2'-0"
WINGWALL_UNSUPPORTED_MAX_FT = 8.0   # "extend footing to limit..."
WINGWALL_FILLET_NOT_REQUIRED_DEG = 120.0  # "no fillet required when >= 120 deg"

BACKWALL_TOP_WIDTH_FT = 1.0 + 8.0 / 12.0   # SECTION A-A, with piles


def bearing_seat_dim_a_ft(skew_deg: float = 0.0) -> float:
    """``DIM. A = 2'-0" / COS(skew)`` (sheet 2's skewed part-plan)."""
    return 2.0 / math.cos(math.radians(skew_deg))


# ── layout (all overall dimensions project-supplied; see module docstring) ─

@dataclass(frozen=True)
class AbutmentInput:
    """Project-supplied dimensions for a typical (girder-bridge) abutment.

    ``wingwall_length_ft`` should not exceed
    :data:`WINGWALL_UNSUPPORTED_MAX_FT` without an extended footing (the
    sheet's own limit, not enforced here since "extend the footing" is
    itself a valid design response, not a hard cap on the wingwall)."""

    width_ft: float
    skew_deg: float
    wingwall_length_ft: float
    footing_depth_ft: float
    backwall_height_ft: float


@dataclass(frozen=True)
class AbutmentLayout:
    """The generated abutment.  ``backwall_outline`` is the backwall's
    plan footprint (top of footing, z = 0) extending up
    ``backwall_height_ft``; ``footing_outline`` is the footing plan
    rectangle (extending down ``footing_depth_ft``); ``wingwall_outline``
    is one flared wingwall plane, per :data:`WINGWALL_MIN_HEIGHT_FT`."""

    inputs: AbutmentInput
    backwall_outline: tuple[Point, Point, Point, Point]
    footing_outline: tuple[Point, Point, Point, Point]
    wingwall_outline: tuple[Point, Point, Point, Point]
    dim_a_ft: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_typical_abutment(inp: AbutmentInput) -> AbutmentLayout:
    """Generate a typical abutment backwall + footing + one flared
    wingwall from fully project-supplied dimensions.

    Raises ``ValueError`` for a non-positive width/wingwall length/footing
    depth/backwall height."""
    for name in ("width_ft", "wingwall_length_ft", "footing_depth_ft",
                 "backwall_height_ft"):
        if getattr(inp, name) <= 0.0:
            raise ValueError(f"AbutmentInput.{name} must be positive")

    tan_skew = math.tan(math.radians(inp.skew_deg))
    dim_a = bearing_seat_dim_a_ft(inp.skew_deg)
    W = inp.width_ft
    half_t = BACKWALL_TOP_WIDTH_FT / 2.0

    def pt(u: float, y: float, z: float) -> Point:
        return (u + y * tan_skew, y, z)

    backwall_outline = (pt(-half_t, 0.0, 0.0), pt(-half_t, W, 0.0),
                       pt(half_t, W, 0.0), pt(half_t, 0.0, 0.0))

    footing_outline = (pt(-half_t - 2.0, 0.0, -inp.footing_depth_ft),
                      pt(-half_t - 2.0, W, -inp.footing_depth_ft),
                      pt(half_t + 2.0, W, -inp.footing_depth_ft),
                      pt(half_t + 2.0, 0.0, -inp.footing_depth_ft))

    # Wingwall flares 45 deg from the abutment end, per the same convention
    # as capped_pile_abutment / full_height_headwall.
    L = inp.wingwall_length_ft
    wing_dx = L * math.sin(math.radians(45.0))
    wing_dy = L * math.cos(math.radians(45.0))
    wingwall_outline = (
        pt(half_t, W, 0.0),
        pt(half_t, W, WINGWALL_MIN_HEIGHT_FT),
        pt(half_t + wing_dx, W + wing_dy, WINGWALL_MIN_HEIGHT_FT),
        pt(half_t + wing_dx, W + wing_dy, 0.0),
    )

    notes = (
        f"A-1-20 typical abutment: width {W:g} ft, skew {inp.skew_deg:g} "
        f"deg (DIM.A = {dim_a:.2f} ft), wingwall {L:g} ft",
        "GUIDANCE ONLY -- sheet 1's own note: treat these dimensions as "
        "MINIMUM VALUES, perform a complete design, do not use as a "
        "standalone construction drawing.",
        f"Wingwall unsupported length should not exceed "
        f"{WINGWALL_UNSUPPORTED_MAX_FT:g} ft without extending the "
        "footing. Not modeled: backwall/footing reinforcing (bars are #5 "
        "unless noted, max 1'-6\" spacing), drainage (PGD/NPCPP/PCPP), "
        "PEJF joints, beam seat bars, rock channel protection.",
    )

    return AbutmentLayout(
        inputs=inp,
        backwall_outline=backwall_outline,
        footing_outline=footing_outline,
        wingwall_outline=wingwall_outline,
        dim_a_ft=dim_a,
        notes=notes,
    )
