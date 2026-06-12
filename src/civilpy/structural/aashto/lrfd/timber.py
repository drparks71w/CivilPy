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

"""AASHTO LRFD Chapter 8 — wood structures.

The adjustment-factor chain (8.4.4) multiplies the reference design values:
F = Fo * CKF * CM * (CF or Cv) * Cfu * Ci * Cd * Clambda, then the member
resistances apply stability/bearing factors.  Units: ksi, inch.

Table-lookup factors that depend on species/grade (CM wet service, Cfu flat
use, Cd deck factor) are inputs rather than functions — take them from the
design tables for the material at hand.
"""

import math

from civilpy.structural.aashto.lrfd.core import CheckResult, article

# Resistance factors for wood (8.5.2.2)
TIMBER_PHI = {
    "flexure": 0.85,
    "shear": 0.75,
    "compression": 0.90,
    "bearing": 0.90,
    "tension": 0.80,
}

# KbE for beam stability (8.6.2) by grading method
KBE = {"visual": 0.76, "mel": 0.98, "msr": 1.06, "glulam": 1.06}


@article("8.4.4.2", "Format Conversion Factor CKF")
def format_conversion_ckf(phi: float, bearing: bool = False) -> float:
    """CKF (8.4.4.2): converts allowable-stress reference values to the
    LRFD format — 2.5/phi generally, 2.1/phi for compression perpendicular
    to grain (bearing)."""
    return (2.1 if bearing else 2.5) / phi


@article("8.4.4.4", "Size Factor CF for Sawn Lumber")
def size_factor_cf(d: float) -> float:
    """CF for sawn beams and stringers deeper than 12 in (8.4.4.4):
    (12/d)^(1/9), 1.0 otherwise."""
    return (12.0 / d) ** (1.0 / 9.0) if d > 12.0 else 1.0


@article("8.4.4.7", "Incising Factor Ci")
def incising_factor_ci(modulus: bool = False) -> float:
    """Ci for incised, preservative-treated dimension lumber (8.4.4.7):
    0.80 on strength values, 0.95 on modulus of elasticity."""
    return 0.95 if modulus else 0.80


# Time-effect factor (Table 8.4.4.9-1)
TIME_EFFECT_CLAMBDA = {
    "Strength I": 0.8,
    "Strength II": 1.0,
    "Strength III": 1.0,
    "Strength IV": 0.6,
    "Extreme Event I": 1.0,
    "Extreme Event II": 1.0,
}


@article("8.4.4.9", "Time Effect Factor Clambda")
def time_effect_clambda(limit_state: str = "Strength I") -> float:
    """Clambda (Table 8.4.4.9-1) by limit state."""
    return TIME_EFFECT_CLAMBDA[limit_state]


@article("8.6.2", "Beam Stability Factor CL")
def beam_stability_cl(
    f_b_star: float,
    e_adj: float,
    l_e: float,
    d: float,
    b: float,
    grading: str = "visual",
) -> CheckResult:
    """Beam stability factor (8.6.2-2):
    CL = (1+A)/1.9 - sqrt((1+A)^2/3.61 - A/0.95), with A = FbE/Fb*,
    FbE = KbE*E'/RB^2 and slenderness RB = sqrt(Le*d/b^2) <= 50.

    ``f_b_star`` is the adjusted bending strength with all factors except
    CL and Cv (ksi); ``e_adj`` the adjusted modulus (ksi); ``l_e`` the
    effective unbraced length (in).  ``capacity`` holds CL."""
    r_b = math.sqrt(l_e * d / b**2)
    f_be = KBE[grading] * e_adj / r_b**2
    a = f_be / f_b_star
    c_l = (1.0 + a) / 1.9 - math.sqrt((1.0 + a) ** 2 / 3.61 - a / 0.95)
    return CheckResult(
        article="8.6.2",
        name="Beam Stability Factor CL",
        capacity=c_l,
        demand=None if r_b <= 50.0 else 1.0,  # RB > 50 is not permitted
        details={"RB": r_b, "FbE": f_be, "A": a, "RB_ok": r_b <= 50.0},
    )


@article("8.8.3", "Bearing Adjustment Factor Cb")
def bearing_factor_cb(l_b: float, near_end: bool = False) -> float:
    """Cb (8.8.3): (lb + 0.375)/lb for bearings less than 6 in long and
    at least 3 in from the member end; 1.0 otherwise (``near_end`` or
    long bearings).  ``l_b`` is the bearing length (in)."""
    if near_end or l_b >= 6.0:
        return 1.0
    return (l_b + 0.375) / l_b


@article("8.6", "Timber Flexural Resistance")
def timber_flexural_resistance(
    f_b_adj: float,
    s_x: float,
    c_l: float = 1.0,
    m_u: float | None = None,
) -> CheckResult:
    """Flexural resistance of a wood beam (8.6): Mn = Fb_adj * Sx * CL,
    Mr = phi_f * Mn with phi_f = 0.85.

    ``f_b_adj`` is the fully adjusted bending strength (ksi, including
    CKF/CM/CF/Clambda etc.), ``s_x`` the section modulus (in^3)."""
    m_n = f_b_adj * s_x * c_l
    return CheckResult(
        article="8.6",
        name="Timber Flexural Resistance",
        capacity=m_n,
        demand=m_u,
        phi=TIMBER_PHI["flexure"],
        details={"CL": c_l},
    )
