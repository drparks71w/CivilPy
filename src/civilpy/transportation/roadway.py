"""AASHTO roadway geometric and roadside design functions.

Sight distance, vertical-curve length, superelevation transition, and
roadside-barrier length-of-need calculations from AASHTO *A Policy on
Geometric Design of Highways and Streets* (the "Green Book") and the
*Roadside Design Guide* (RDG).  These complement the curve geometry in
:mod:`civilpy.transportation.curves`.

Only equations and the standard design-control tables are reproduced here
(no policy prose).  The design tables (SSD, crest/sag K) are cross-checked
against their generating equations in the test suite.

US customary units throughout: speeds in mph, distances in feet, grades as
a decimal (0.04 = 4%) unless a name says ``_pct``, cross slopes / relative
gradients as a decimal.
"""

#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import math

#: Standard gravitational acceleration, ft/s^2.
G_FT_S2 = 32.2

#: AASHTO default deceleration for sight-distance braking, ft/s^2 (Green
#: Book): a comfortable deceleration most drivers can achieve.
DEFAULT_DECELERATION = 11.2

#: AASHTO default brake-reaction time for SSD, seconds.
DEFAULT_REACTION_TIME = 2.5

#: Driver eye height and object heights for crest curves, feet (Green Book).
DRIVER_EYE_HEIGHT = 3.5
STOPPING_OBJECT_HEIGHT = 2.0

# ----------------------------------------------------------------- sight distance


def braking_distance(
    speed_mph: float,
    friction: float | None = None,
    grade: float = 0.0,
    deceleration: float = DEFAULT_DECELERATION,
) -> float:
    """Braking distance (ft) from ``speed_mph``.

    With ``friction`` given, uses d = V^2 / (30 (f +/- G)); otherwise uses
    the AASHTO deceleration form d = V^2 / (30 (a/g +/- G)).  ``grade`` is a
    decimal, positive uphill (which shortens braking).
    """
    drag = friction if friction is not None else deceleration / G_FT_S2
    return speed_mph**2 / (30.0 * (drag + grade))


def stopping_sight_distance(
    speed_mph: float,
    grade: float = 0.0,
    reaction_time: float = DEFAULT_REACTION_TIME,
    deceleration: float = DEFAULT_DECELERATION,
) -> float:
    """Stopping sight distance (ft), Green Book Eq. 3-1/3-2.

    SSD = 1.47 V t + V^2 / (30 (a/g +/- G)).  ``grade`` decimal, positive
    uphill.
    """
    reaction = 1.47 * speed_mph * reaction_time
    return reaction + braking_distance(
        speed_mph, grade=grade, deceleration=deceleration
    )


#: Design stopping sight distance on level grade, ft (Green Book Table 3-1).
SSD_DESIGN = {
    15: 80, 20: 115, 25: 155, 30: 200, 35: 250, 40: 305, 45: 360,
    50: 425, 55: 495, 60: 570, 65: 645, 70: 730, 75: 820, 80: 910,
}


def decision_sight_distance(speed_mph: float, maneuver: str) -> float:
    """Decision sight distance (ft), Green Book Eq. 3-3/3-4.

    ``maneuver`` is one of the five avoidance maneuvers:

    ``"A"`` stop on rural road, ``"B"`` stop on urban road (both
    DSD = 1.47 V t + braking); ``"C"`` / ``"D"`` / ``"E"`` speed/path/
    direction change on rural / suburban / urban roads (DSD = 1.47 V t,
    pre-maneuver + maneuver time).
    """
    pre = {"A": 3.0, "B": 9.1, "C": 10.2, "D": 12.1, "E": 14.5}
    if maneuver not in pre:
        raise ValueError(f"maneuver must be one of {sorted(pre)}")
    t = pre[maneuver]
    if maneuver in ("A", "B"):
        return 1.47 * speed_mph * t + braking_distance(speed_mph)
    return 1.47 * speed_mph * t


def intersection_sight_distance(speed_mph_major: float, time_gap: float) -> float:
    """Intersection sight distance along the major road (ft), Green Book
    Eq. 9-1: ISD = 1.47 V_major t_g.  ``time_gap`` (s) is the critical gap
    for the maneuver (e.g. 7.5 s left turn from stop, passenger car)."""
    return 1.47 * speed_mph_major * time_gap


#: Design passing sight distance for two-lane highways, ft (Green Book
#: Table 3-4, 2011/2018).
PSD_DESIGN = {
    20: 400, 25: 450, 30: 500, 35: 550, 40: 600, 45: 700, 50: 800,
    55: 900, 60: 1000, 65: 1100, 70: 1200, 75: 1300, 80: 1400,
}

# ------------------------------------------------------------- vertical curves


def crest_curve_length(
    a_pct: float,
    sight_distance: float,
    h1: float = DRIVER_EYE_HEIGHT,
    h2: float = STOPPING_OBJECT_HEIGHT,
) -> float:
    """Minimum crest vertical-curve length (ft), Green Book Eq. 3-43/3-44.

    ``a_pct`` is the algebraic grade difference |G2 - G1| in percent.  Uses
    the larger of the two branches so the result is valid whether the sight
    distance is shorter or longer than the curve.
    """
    a = abs(a_pct)
    if a == 0:
        return 0.0
    denom = 100.0 * (math.sqrt(2.0 * h1) + math.sqrt(2.0 * h2)) ** 2
    l_s_less = a * sight_distance**2 / denom          # S < L
    l_s_more = 2.0 * sight_distance - denom / a       # S > L
    # Use whichever branch is self-consistent; fall back to the controlling
    # (longer) length.
    if l_s_less >= sight_distance:
        return l_s_less
    if l_s_more <= sight_distance and l_s_more > 0:
        return l_s_more
    return max(l_s_less, l_s_more)


def sag_curve_length(a_pct: float, sight_distance: float) -> float:
    """Minimum sag vertical-curve length (ft) by the headlight-sight-
    distance criterion, Green Book Eq. 3-47/3-48 (headlight height 2.0 ft,
    1-degree upward beam): denominator 400 + 3.5 S."""
    a = abs(a_pct)
    if a == 0:
        return 0.0
    l_s_less = a * sight_distance**2 / (400.0 + 3.5 * sight_distance)  # S < L
    l_s_more = 2.0 * sight_distance - (400.0 + 3.5 * sight_distance) / a  # S>L
    if l_s_less >= sight_distance:
        return l_s_less
    if l_s_more <= sight_distance and l_s_more > 0:
        return l_s_more
    return max(l_s_less, l_s_more)


#: Design crest-curve rate of vertical curvature K = L/A for SSD, ft per
#: percent (Green Book Table 3-34, rounded).
K_CREST = {
    15: 3, 20: 7, 25: 12, 30: 19, 35: 29, 40: 44, 45: 61, 50: 84,
    55: 114, 60: 151, 65: 193, 70: 247, 75: 312, 80: 384,
}

#: Design sag-curve rate of vertical curvature K = L/A for SSD, ft per
#: percent (Green Book Table 3-36, rounded).
K_SAG = {
    15: 10, 20: 17, 25: 26, 30: 37, 35: 49, 40: 64, 45: 79, 50: 96,
    55: 115, 60: 136, 65: 157, 70: 181, 75: 206, 80: 231,
}


def vertical_curve_length_from_k(k: float, a_pct: float) -> float:
    """Curve length L = K |A| (ft) from a design K value and the grade
    difference in percent."""
    return k * abs(a_pct)

# ------------------------------------------------------------ superelevation


#: Maximum relative gradient between profile of edge and centerline, percent,
#: by design speed (Green Book Table 3-15).
MAX_RELATIVE_GRADIENT_PCT = {
    15: 0.78, 20: 0.74, 25: 0.70, 30: 0.66, 35: 0.62, 40: 0.58, 45: 0.54,
    50: 0.50, 55: 0.47, 60: 0.45, 65: 0.43, 70: 0.40, 75: 0.38, 80: 0.35,
}


def superelevation_runoff_length(
    superelevation: float,
    lane_width: float,
    lanes_rotated: float,
    max_relative_gradient: float,
    adjustment_factor: float = 1.0,
) -> float:
    """Superelevation runoff length Lr (ft), Green Book Eq. 3-23.

    Lr = (w n1 ed / Delta) bw, where ``superelevation`` ed and the
    ``max_relative_gradient`` Delta are decimals (use the Table 3-15 value
    divided by 100), ``lane_width`` w in feet, ``lanes_rotated`` n1, and
    ``adjustment_factor`` bw (Table 3-16, = (1 + 0.5(n1-1))/n1 for the
    common case)."""
    return (
        lane_width * lanes_rotated * superelevation / max_relative_gradient
    ) * adjustment_factor


def runoff_adjustment_factor(lanes_rotated: float) -> float:
    """Adjustment factor bw for multilane rotation (Green Book Table 3-16):
    bw = (1 + 0.5 (n1 - 1)) / n1."""
    return (1.0 + 0.5 * (lanes_rotated - 1.0)) / lanes_rotated


def tangent_runout_length(
    runoff_length: float, superelevation: float, normal_cross_slope: float
) -> float:
    """Tangent runout length Lt (ft), Green Book Eq. 3-24:
    Lt = (eNC / ed) Lr."""
    return (normal_cross_slope / superelevation) * runoff_length


def min_radius(speed_mph: float, e_max: float, f_max: float) -> float:
    """Minimum horizontal curve radius (ft), Green Book Eq. 3-8:
    R = V^2 / (15 (e_max + f_max)).  ``e_max``/``f_max`` are decimals."""
    return speed_mph**2 / (15.0 * (e_max + f_max))

# --------------------------------------------------------- roadside design


def barrier_length_of_need(
    runout_length: float,
    lateral_extent: float,
    barrier_offset: float,
    flare_rate: float | None = None,
    back_offset: float | None = None,
) -> float:
    """Length of need X (ft) of a roadside barrier upstream of a hazard
    (Roadside Design Guide length-of-need method).

    ``runout_length`` LR is the runout length for the design speed/volume
    (RDG Table 5-39), ``lateral_extent`` LA the distance from the edge of
    the travelled way to the far side of the area of concern, and
    ``barrier_offset`` L1 the lateral offset of the barrier at the hazard.

    For a barrier parallel to the road (``flare_rate=None``):
    X = LR (LA - L1) / LA.

    For a flared barrier give ``flare_rate`` as the longitudinal:lateral
    run b/a and ``back_offset`` L2 (lateral offset where the barrier meets
    the length of need): X = (LA + (b/a) L2 - L1) / ((b/a) + LA/LR).
    """
    if lateral_extent <= 0:
        raise ValueError("lateral_extent must be positive")
    if flare_rate is None:
        return runout_length * (lateral_extent - barrier_offset) / lateral_extent
    l2 = back_offset if back_offset is not None else barrier_offset
    return (lateral_extent + flare_rate * l2 - barrier_offset) / (
        flare_rate + lateral_extent / runout_length
    )


#: Suggested barrier flare rates (longitudinal:lateral) inside the shy line
#: by design speed (Roadside Design Guide Table 5-7), rigid barriers.
FLARE_RATE_RIGID = {
    40: 13, 45: 16, 50: 18, 55: 18, 60: 20, 65: 22, 70: 24, 75: 26, 80: 26,
}
