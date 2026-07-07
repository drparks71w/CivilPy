#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT strip seal expansion joints for concrete box beam structures
(EXJ-5-93).

Transcribed from Ohio DOT Standard Bridge Drawing EXJ-5-93, "Strip Seal
Expansion Joints, Concrete Box Beam Structures" (rev. 01-19-2024,
4 sheets). The drawing remains the controlling document. Same pattern
as EXJ-4-87 (:mod:`civilpy.structural.odot.strip_seal_joint`) but for box
beams instead of steel stringers: the strip-seal gland is again
manufacturer-generic, and the joint runs the skewed width of the
structure. What's cataloged here is the plate "A"/"B"/"C" spacing table
(keyed by beam width, END OF SUPERSTRUCTURE detail) and the joint-length
formula (sheet 1's own "LEGEND"):

    L = [(N - 1) * (1/2) + N * W] / (12 * cos(theta))

``L`` is the joint length edge-to-edge of deck (ft), ``N`` the number of
beams, ``W`` the nominal beam width (inches, 36 or 48), ``theta`` the
joint skew angle. The plates repeat A-B-B-C-B-B-C-... across the joint
width, one A/B/C group per beam-to-beam gap (see the sheet's "PLATE 'A'
SPACING" callout row).

Conventions match the rest of this package: X along stations, Y
transverse, Z up; feet in plan, inches for section dimensions. The
origin sits on the joint centerline (X = 0) at the top of deck (Z = 0),
Y = 0 at one deck edge.
"""

import math
from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "EXJ-5-93"
REVISION = "01-19-2024"

RETAINER_ANGLE = "L-7x4x1/2\""
JOINT_ANGLE = "7x4x1/2\""
THREADED_ROD_36IN_SPEC = "2 - 3/8 in dia threaded rods, two hex nuts, set during casting"
THREADED_ROD_48IN_SPEC = "5/8 in dia threaded rods, two hex nuts, set during casting"
STEEL_DRIP_STRIP_NOTE = "steel drip strip, not included with the joint for payment"


@dataclass(frozen=True)
class PlateSpacing:
    beam_width_in: float
    dim_a_in: float
    dim_b_in: float   # "allows for beam fit-up"
    dim_c_in: float


#: EXJ-5-93 plate "A"/"B"/"C" spacing table, keyed by beam width (inches).
PLATE_SPACING: dict[float, PlateSpacing] = {
    36.0: PlateSpacing(36.0, 6.0, 1.0 * 12.0 + 0.25, 1.0 * 12.0),
    48.0: PlateSpacing(48.0, 8.0, 1.0 * 12.0 + 4.25, 1.0 * 12.0 + 4.0),
}


def plate_spacing(beam_width_in: float) -> PlateSpacing:
    """Look up the EXJ-5-93 plate spacing for a beam width (36 or 48 in).

    Raises ``ValueError`` naming the valid widths otherwise."""
    try:
        return PLATE_SPACING[float(beam_width_in)]
    except KeyError:
        raise ValueError(
            f"EXJ-5-93 tabulates beam widths {sorted(PLATE_SPACING)} in, "
            f"not {beam_width_in!r}") from None


def joint_length_ft(n_beams: int, beam_width_in: float,
                    skew_deg: float = 0.0) -> float:
    """``L = [(N-1)*(1/2) + N*W] / (12*cos(theta))`` (sheet 1's LEGEND):
    joint length edge-to-edge of deck, feet."""
    return ((n_beams - 1) * 0.5 + n_beams * beam_width_in) / (
        12.0 * math.cos(math.radians(skew_deg)))


# ── layout ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BoxBeamJointInput:
    n_beams: int
    beam_width_in: float
    skew_deg: float = 0.0


@dataclass(frozen=True)
class BoxBeamJointLayout:
    """The generated joint: ``joint_line`` is the skewed gland centerline
    across the full deck width (z = 0, top of deck); ``beam_gap_stations``
    are the transverse (Y) positions of each beam-to-beam gap, where a
    plate "A"/"B"/"C" group sits."""

    inputs: BoxBeamJointInput
    joint_line: tuple[Point, Point]
    length_ft: float
    beam_gap_stations_ft: tuple[float, ...]
    spacing: PlateSpacing
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_box_beam_joint(inp: BoxBeamJointInput) -> BoxBeamJointLayout:
    """Generate a box-beam strip seal joint: the skewed joint line and the
    beam-to-beam gap stations where plate "A"/"B"/"C" groups sit.

    Raises ``ValueError`` for fewer than 2 beams or an untabulated beam
    width (:func:`plate_spacing`)."""
    if inp.n_beams < 2:
        raise ValueError("BoxBeamJointInput.n_beams must be >= 2")
    spacing = plate_spacing(inp.beam_width_in)

    L = joint_length_ft(inp.n_beams, inp.beam_width_in, inp.skew_deg)
    tan_skew = math.tan(math.radians(inp.skew_deg))

    def pt(u: float, y: float) -> Point:
        return (u + y * tan_skew, y, 0.0)

    joint_line = (pt(0.0, 0.0), pt(0.0, L))

    w_ft = inp.beam_width_in / 12.0
    gap_stations = tuple(w_ft * i for i in range(1, inp.n_beams))

    notes = (
        f"EXJ-5-93 box beam strip seal joint: {inp.n_beams} beams x "
        f"{inp.beam_width_in:g} in wide, skew {inp.skew_deg:g} deg, "
        f"joint length {L:.2f} ft",
        f"Plate group (per beam gap): A {spacing.dim_a_in:g} in, "
        f"B {spacing.dim_b_in:g} in, C {spacing.dim_c_in:g} in",
        "Not modeled: the strip seal gland (manufacturer-generic "
        "extrusion), retainer angles, plates 'A'/'B', threaded rods cast "
        "into the box beams, stainless steel deflector (EXJ-3-82), "
        "abutment backwall armor.",
    )

    return BoxBeamJointLayout(
        inputs=inp,
        joint_line=joint_line,
        length_ft=L,
        beam_gap_stations_ft=gap_stations,
        spacing=spacing,
        notes=notes,
    )
