#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT strip seal expansion joints for steel stringer structures
(EXJ-4-87).

Transcribed from Ohio DOT Standard Bridge Drawing EXJ-4-87, "Strip Seal
Expansion Joints, Steel Stringer Structures" (rev. 01-19-2024, 4 sheets).
The drawing remains the controlling document.

Like BCHW/CPA-1-08, most of this sheet is a detailing template: the
strip-seal gland itself is a manufacturer-generic elastomeric extrusion
(not tabulated here), and the joint runs the full skewed width of the
structure with project-specific stringer spacing. What **is** a genuine
parametric formula (sheet 1, SECTION C-C) is the support-angle segment
length at each stringer, which depends on the stringer top flange width
and the skew angle:

    a1 = top_flange_width / cos(theta) - 2 * (1" / cos(theta)) - 4" * tan(theta)
    a2 = 1" + 0.5 * top_flange_width / cos(theta)
    a3 = 1" + top_flange_width / cos(theta) + 4" * tan(theta) + 1"
    a4 = a3 - a2

(a1 is the clear gap the support angle must span between plate "A"
retainers; a2/a3 lay out the angle relative to the stringer centerline;
a4 = a3 - a2 is used directly in Sections B-B/C-C.) These mirror image
for a left-forward skew (sheet's own note).

Conventions match the rest of this package: X along stations, Y
transverse, Z up; feet in plan, inches for section dimensions. The
origin sits on the joint centerline (X = 0) at the top of deck (Z = 0),
Y = 0 at one deck edge.
"""

import math
from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "EXJ-4-87"
REVISION = "01-19-2024"

# ── fixed hardware constants (sheet 1) ───────────────────────────────────

RETAINER_ANGLE = "L-7x4x1/2\""          # plate "A"/"B" retainer angle
SUPPORT_CHANNEL = "MC 12x45"            # transverse support channel
SUPPORT_ANGLE = "6x4x3/4\" (long leg vertical)"
ANCHOR_BAR = "1/2 x 2 x 1'-6\""
BOLT_SPEC = "3/4 in dia ASTM A325 Type 1 hex head bolts with hex nut"
SHEAR_STUD_SPEC = "1/2 in dia x 4 in welded shear studs"
PLATE_MAX_SPACING_FT = 1.5              # 1'-6" max between plates "A"/"B"
JOINT_GAP_60F_IN = 3.0                  # nominal gap "@ 60 deg F"
MIN_SUPPORT_ANGLE_LENGTH_FT = 2.5       # note 1: verify flange width for 2'-6" min


def support_angle_lengths_in(top_flange_width_in: float,
                             skew_deg: float) -> tuple[float, float, float, float]:
    """The a1/a2/a3/a4 support-angle formulas (sheet 1, SECTION C-C).

    Returns ``(a1, a2, a3, a4)`` in inches; mirror the sign convention for
    a left-forward skew per the sheet's own note (use the same magnitude,
    mirrored in plan by the caller)."""
    theta = math.radians(skew_deg)
    cos_t, tan_t = math.cos(theta), math.tan(theta)
    w = top_flange_width_in
    a1 = w / cos_t - 2.0 * (1.0 / cos_t) - 4.0 * tan_t
    a2 = 1.0 + 0.5 * w / cos_t
    a3 = 1.0 + w / cos_t + 4.0 * tan_t + 1.0
    a4 = a3 - a2
    return (a1, a2, a3, a4)


# ── layout ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StripSealJointInput:
    """Inputs for one strip seal joint run.

    ``stringer_stations_ft`` are the transverse stringer positions (Y, ft)
    across the deck width; ``top_flange_width_in`` is the (uniform,
    assumed) stringer top flange width used in the support-angle
    formulas."""

    width_ft: float
    skew_deg: float
    stringer_stations_ft: tuple[float, ...]
    top_flange_width_in: float = 12.0


@dataclass(frozen=True)
class SupportAngleRun:
    station_ft: float
    points: tuple[Point, Point]
    a1_in: float
    a2_in: float
    a3_in: float
    a4_in: float


@dataclass(frozen=True)
class StripSealJointLayout:
    """The generated joint: ``joint_line`` is the skewed gland centerline
    across the full deck width (z = 0, top of deck); ``support_angles`` is
    one short transverse segment per stringer station, sized by
    :func:`support_angle_lengths_in`."""

    inputs: StripSealJointInput
    joint_line: tuple[Point, Point]
    support_angles: tuple[SupportAngleRun, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_strip_seal_joint(inp: StripSealJointInput) -> StripSealJointLayout:
    """Generate a strip seal joint: the skewed joint line and one
    support-angle run per stringer station.

    Raises ``ValueError`` for a non-positive width or an empty
    ``stringer_stations_ft``."""
    if inp.width_ft <= 0.0:
        raise ValueError("StripSealJointInput.width_ft must be positive")
    if not inp.stringer_stations_ft:
        raise ValueError(
            "StripSealJointInput.stringer_stations_ft must not be empty")

    tan_skew = math.tan(math.radians(inp.skew_deg))

    def pt(u: float, y: float) -> Point:
        return (u + y * tan_skew, y, 0.0)

    joint_line = (pt(0.0, 0.0), pt(0.0, inp.width_ft))

    a1, a2, a3, a4 = support_angle_lengths_in(
        inp.top_flange_width_in, inp.skew_deg)
    a1_ft = a1 / 12.0

    support_angles = tuple(
        SupportAngleRun(
            station_ft=y,
            points=(pt(-a1_ft / 2.0, y), pt(a1_ft / 2.0, y)),
            a1_in=a1, a2_in=a2, a3_in=a3, a4_in=a4,
        )
        for y in inp.stringer_stations_ft
    )

    notes = (
        f"EXJ-4-87 strip seal joint: width {inp.width_ft:g} ft, skew "
        f"{inp.skew_deg:g} deg, {len(inp.stringer_stations_ft)} stringers, "
        f"top flange {inp.top_flange_width_in:g} in",
        f"Support angle: a1 {a1:.2f} in, a2 {a2:.2f} in, a3 {a3:.2f} in, "
        f"a4 {a4:.2f} in ({SUPPORT_ANGLE})",
        "Not modeled: the strip seal gland (manufacturer-generic "
        "extrusion), retainer plates 'A'/'B', anchor bars, shear studs, "
        "abutment backwall armor, end cross-frames (see GSD-1-19).",
    )

    return StripSealJointLayout(
        inputs=inp,
        joint_line=joint_line,
        support_angles=support_angles,
        notes=notes,
    )
