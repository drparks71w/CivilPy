#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Combinations — two span-wire configurations sharing a strain pole.

Legacy SWISS lets any two sequences share a pole; each sequence is
analyzed independently, and the combination output is the **resultant
base moment** at the shared pole plus its **line of action**.  The two
stringing tensions pull horizontally along their span directions,
separated by the plan angle entered by the designer; each contributes a
base-moment vector along its pull direction.

Since the two wires' attachment elevations generally differ, the pole
height must be based on the higher attachment (the manual's rule) — both
elevations are carried in the result.

Units: lb, ft, degrees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CombinedPoleResult:
    """Resultant of two span pulls on one pole.

    ``line_of_action_deg`` is measured from the first span's pull
    direction toward the second (counterclockwise positive).
    """

    resultant_tension_lb: float
    resultant_moment_ftlb: float
    line_of_action_deg: float
    governing_attachment_elevation_ft: float
    moment_1_ftlb: float
    moment_2_ftlb: float


def combine_pole(
    tension_1_lb: float,
    attachment_height_1_ft: float,
    tension_2_lb: float,
    attachment_height_2_ft: float,
    angle_deg: float,
    factor: float = 1.0,
    attachment_elevation_1_ft: float | None = None,
    attachment_elevation_2_ft: float | None = None,
) -> CombinedPoleResult:
    """Combine two span pulls at a shared pole.

    ``angle_deg`` is the plan angle between the two span directions
    (SWISS's combination "Angle (Degrees)" entry).  ``factor`` is the
    amplification applied to both moments — the legacy design factor for
    ASD parity, or 1.0 when the tensions are already factored loads.
    """
    if tension_1_lb < 0 or tension_2_lb < 0:
        raise ValueError("tensions cannot be negative")
    theta = math.radians(angle_deg)
    m1 = tension_1_lb * attachment_height_1_ft * factor
    m2 = tension_2_lb * attachment_height_2_ft * factor

    resultant_m = math.sqrt(m1 * m1 + m2 * m2 + 2 * m1 * m2 * math.cos(theta))
    resultant_t = math.sqrt(
        tension_1_lb**2 + tension_2_lb**2
        + 2 * tension_1_lb * tension_2_lb * math.cos(theta)
    )
    line = math.degrees(
        math.atan2(m2 * math.sin(theta), m1 + m2 * math.cos(theta))
    )
    elevations = [
        e for e in (attachment_elevation_1_ft, attachment_elevation_2_ft)
        if e is not None
    ]
    governing = max(elevations) if elevations else max(
        attachment_height_1_ft, attachment_height_2_ft
    )
    return CombinedPoleResult(
        resultant_tension_lb=resultant_t,
        resultant_moment_ftlb=resultant_m,
        line_of_action_deg=line,
        governing_attachment_elevation_ft=governing,
        moment_1_ftlb=m1,
        moment_2_ftlb=m2,
    )


__all__ = ["CombinedPoleResult", "combine_pole"]
