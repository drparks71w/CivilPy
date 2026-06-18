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

"""SPT blow-count correlations: the derived-parameter engine that turns a
Standard Penetration Test N value into the soil properties the downstream
libraries need.

These are published, widely used empirical correlations.  They are
estimates only -- approximate and scatter-prone -- and should never
replace laboratory testing where it is available; they exist so a boring
log with nothing but blow counts can still seed a calculation.

Units are US customary: stresses in psf, unit weights in pcf, moduli in
psi, angles in degrees.  ``N`` arguments are field blow counts unless the
name says ``n60`` (energy-corrected) or ``n1_60`` (energy- and
overburden-corrected).

References
----------
* Liao & Whitman (1986) -- overburden correction CN.
* Skempton (1986) -- N60 corrections and relative density.
* Hatanaka & Uchida (1996) -- friction angle from (N1)60.
* Stroud (1974) -- undrained shear strength from N.
* Bowles, *Foundation Analysis and Design*, 5th ed. (1996) -- elastic
  modulus from N.
"""

from __future__ import annotations

import math

#: Atmospheric pressure used to normalise overburden, psf (~1 tsf).
PATM_PSF = 2000.0


def overburden_correction(sigma_v_eff_psf: float, cap: float = 1.7) -> float:
    """Overburden normalisation factor CN (Liao & Whitman 1986):
    CN = sqrt(Pa / sigma'_v), capped at ``cap`` (1.7 typical, 2.0 sometimes
    used).  ``sigma_v_eff_psf`` is the effective vertical stress at the test
    depth."""
    if sigma_v_eff_psf <= 0:
        return cap
    return min(cap, math.sqrt(PATM_PSF / sigma_v_eff_psf))


def n1_60(n60: float, sigma_v_eff_psf: float, cap: float = 1.7) -> float:
    """Energy- and overburden-corrected blow count (N1)60 = CN * N60."""
    return overburden_correction(sigma_v_eff_psf, cap) * n60


def friction_angle_from_n(n1_60_value: float) -> float:
    """Effective friction angle phi' (degrees) of a sand from (N1)60
    (Hatanaka & Uchida 1996): phi' = sqrt(20 (N1)60) + 20."""
    if n1_60_value < 0:
        raise ValueError("(N1)60 must be non-negative")
    return math.sqrt(20.0 * n1_60_value) + 20.0


def relative_density_from_n(n1_60_value: float, constant: float = 60.0) -> float:
    """Relative density Dr (fraction 0-1) of a sand from (N1)60
    (Skempton 1986): Dr = sqrt((N1)60 / ``constant``), clamped to 1.0."""
    if n1_60_value < 0:
        raise ValueError("(N1)60 must be non-negative")
    return min(1.0, math.sqrt(n1_60_value / constant))


def undrained_shear_strength_from_n(
    n60: float, factor_psf: float = 92.0
) -> float:
    """Undrained shear strength Su (psf) of a fine-grained soil from N60
    (Stroud 1974): Su = f1 * N60.  ``factor_psf`` f1 ~ 92 psf (4.4 kPa) is a
    representative value for insensitive clays; it ranges roughly 75-150 psf
    (3.5-7 kPa) with plasticity."""
    return factor_psf * n60


#: Bowles (1996) Es = a (N + b) coefficients, stress in kPa, by soil type.
_BOWLES_ES_KPA = {
    "sand": (500.0, 15.0),
    "sand_saturated": (250.0, 15.0),
    "gravelly_sand": (1200.0, 6.0),
    "silty_sand": (300.0, 6.0),
    "clayey_sand": (320.0, 15.0),
}

_KPA_TO_PSI = 0.1450377


def elastic_modulus_from_spt(n: float, soil_type: str = "sand") -> float:
    """Drained Young's modulus Es (psi) from N (Bowles 1996,
    Es = a (N + b) in kPa).  ``soil_type`` selects the coefficients:
    ``"sand"``, ``"sand_saturated"``, ``"gravelly_sand"``, ``"silty_sand"``,
    or ``"clayey_sand"``."""
    if soil_type not in _BOWLES_ES_KPA:
        raise ValueError(
            f"unknown soil_type {soil_type!r}; choose from "
            f"{sorted(_BOWLES_ES_KPA)}"
        )
    a, b = _BOWLES_ES_KPA[soil_type]
    return a * (n + b) * _KPA_TO_PSI


def elastic_modulus_from_su(su_psf: float, modulus_ratio: float = 300.0) -> float:
    """Undrained Young's modulus Eu (psi) of a clay as ``modulus_ratio``
    times the undrained shear strength: Eu = beta * Su.  ``modulus_ratio``
    beta ~ 150 (soft) to 600 (stiff, OC) clays; 300 is a common default."""
    return modulus_ratio * su_psf / 144.0  # psf -> psi


def unit_weight_from_n(n: float, coarse: bool = True) -> float:
    """Rough total unit weight (pcf) from N when no laboratory value is
    available, after the Terzaghi-Peck consistency/density descriptions.

    ``coarse`` True for sands/gravels (by relative density), False for
    clays/silts (by consistency).  These are mid-range representative
    values, not a substitute for measured unit weights.
    """
    if coarse:
        table = [(4, 100.0), (10, 110.0), (30, 120.0), (50, 130.0)]
        default = 140.0
    else:
        table = [(2, 100.0), (4, 110.0), (8, 120.0), (15, 125.0), (30, 130.0)]
        default = 135.0
    for threshold, gamma in table:
        if n < threshold:
            return gamma
    return default
