#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""AASHTO LRFD-LTS Article 3.8 — design wind pressure.

Design pressure (Eq. 3.8.1-1, US customary — psf, mph, ft):

    Pz = 0.00256 * Kz * Kd * G * V**2 * Cd

Productionized from the validated ``Notebooks/Wind Load Calc.ipynb`` LTS-1
proof of concept.  LTS publishes Exposure C only, so no exposure parameter
is offered.  Basic wind speed ``V`` is the 3-second gust for the structure's
mean recurrence interval (Table 3.8-1 by risk category; map figures
3.8-1x / 3.8-4).
"""

from __future__ import annotations

# Table 3.8-1 — wind MRI (years) by risk category.  "roadside_sign" is the
# low-risk relief for roadside sign supports; it does NOT apply where a
# failed support could drop into the travelway.
MRI_YEARS = {
    "critical": 1700,
    "typical": 700,
    "low": 300,
    "roadside_sign": 10,
}

# Ohio basic wind speeds, mph 3-s gust (Figs. 3.8-1b and 3.8-4).
OHIO_WIND_SPEEDS = {700: 115.0, 10: 76.0}

# Table 3.8.5-1 — wind directionality factor.  Round supports take 0.95;
# 1.00 is the conservative ceiling for anything not listed here.
DIRECTIONALITY_FACTORS = {
    "round": 0.95,
    "default": 1.00,
}

# Art. 3.8.6 — gust effect factor, 1.14 minimum.
GUST_EFFECT_MIN = 1.14

# Table 3.8.7-1 — drag coefficient for traffic signals.  Verify against the
# governing spec edition before relying on it for final design.
CD_TRAFFIC_SIGNAL = 1.2

# Table 3.8.7-1 — sign panel Cd by aspect ratio (long side / short side).
_SIGN_PANEL_RATIOS = (1.0, 2.0, 5.0, 10.0, 15.0)
_SIGN_PANEL_CDS = (1.12, 1.19, 1.20, 1.23, 1.30)


def height_factor(z_ft: float) -> float:
    """Kz per Eq. 3.8.4-1, Exposure C (alpha = 9.5, zg = 900 ft).

    Heights below 16 ft ride the 16-ft floor.
    """
    z = max(z_ft, 16.0)
    return 2.01 * (z / 900.0) ** (2.0 / 9.5)


def directionality_factor(support_shape: str = "default") -> float:
    """Kd per Table 3.8.5-1 for the support structure shape."""
    return DIRECTIONALITY_FACTORS[support_shape]


def cd_cylinder(diameter_ft: float, wind_speed_mph: float, cv: float = 0.8) -> float:
    """Drag coefficient for a single cylindrical member (Table 3.8.7-1).

    Regime is set by ``Cv * V * d``; ``cv`` is 0.8 at the extreme limit
    state (1.0 at service).
    """
    cvvd = cv * wind_speed_mph * diameter_ft
    if cvvd <= 39.0:
        return 1.10
    if cvvd < 78.0:
        return 129.0 / cvvd**1.3
    return 0.45


def cd_sign_panel(length_ft: float, width_ft: float) -> float:
    """Drag coefficient for a flat sign panel (Table 3.8.7-1).

    Interpolated on aspect ratio (long side over short side); clamped to
    the table's 1.0–15.0 range.
    """
    if length_ft <= 0 or width_ft <= 0:
        raise ValueError("sign panel dimensions must be positive")
    ratio = max(length_ft, width_ft) / min(length_ft, width_ft)
    ratios, cds = _SIGN_PANEL_RATIOS, _SIGN_PANEL_CDS
    if ratio <= ratios[0]:
        return cds[0]
    if ratio >= ratios[-1]:
        return cds[-1]
    for (r0, c0), (r1, c1) in zip(zip(ratios, cds), zip(ratios[1:], cds[1:])):
        if ratio <= r1:
            return c0 + (c1 - c0) * (ratio - r0) / (r1 - r0)
    raise AssertionError("unreachable")  # pragma: no cover


def velocity_pressure(
    wind_speed_mph: float,
    z_ft: float,
    kd: float = DIRECTIONALITY_FACTORS["default"],
    g: float = GUST_EFFECT_MIN,
) -> float:
    """Pressure per unit Cd, psf: ``0.00256 * Kz * Kd * G * V**2``."""
    return 0.00256 * height_factor(z_ft) * kd * g * wind_speed_mph**2


def design_wind_pressure(
    wind_speed_mph: float,
    z_ft: float,
    cd: float,
    kd: float = DIRECTIONALITY_FACTORS["default"],
    g: float = GUST_EFFECT_MIN,
) -> float:
    """Pz per Eq. 3.8.1-1, psf."""
    return velocity_pressure(wind_speed_mph, z_ft, kd=kd, g=g) * cd


__all__ = [
    "MRI_YEARS",
    "OHIO_WIND_SPEEDS",
    "DIRECTIONALITY_FACTORS",
    "GUST_EFFECT_MIN",
    "CD_TRAFFIC_SIGNAL",
    "height_factor",
    "directionality_factor",
    "cd_cylinder",
    "cd_sign_panel",
    "velocity_pressure",
    "design_wind_pressure",
]
