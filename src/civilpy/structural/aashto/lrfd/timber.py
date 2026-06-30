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

# //TODO - Implement timber_shear_resistance function to complete fundamental member checks

# //TODO - Add AASHTO LRFD interaction equations for combined axial and bending loading

# //TODO - Add Hankinson formula checks for timber bearing at an angle to the grain

# //TODO - Implement serviceability and long-term deflection limit checks (Note: Verify if deflections are handled in a broader global analysis module)

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


_CLAMBDA_BY_KEY = {key.lower(): value for key, value in TIME_EFFECT_CLAMBDA.items()}


@article("8.4.4.9", "Time Effect Factor Clambda")
def time_effect_clambda(limit_state: str = "Strength I") -> float:
    """Clambda (Table 8.4.4.9-1) by limit state."""
    # Case-insensitive lookup; ``str.title()`` can't be used because it
    # corrupts the Roman numerals (e.g. "Strength II" -> "Strength Ii").
    value = _CLAMBDA_BY_KEY.get(limit_state.strip().lower())
    if value is None:
        valid_states = ", ".join(TIME_EFFECT_CLAMBDA.keys())
        raise ValueError(f"Invalid limit_state. Must be one of: {valid_states}")

    return value


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
    if l_e <= 0.0 or d <= 0.0 or b <= 0.0:
        raise ValueError("Effective length, depth, and width must be strictly positive.")

    grade_key = grading.lower()
    if grade_key not in KBE:
        raise ValueError(f"Invalid grading '{grading}'. Must be 'visual', 'mel', 'msr', or 'glulam'.")

    r_b = math.sqrt(l_e * d / b ** 2)

    if r_b > 50.0:
        c_l, f_be, a = 0.0, 0.0, 0.0
    else:
        f_be = KBE[grade_key] * e_adj / r_b ** 2
        a = f_be / f_b_star
        c_l = (1.0 + a) / 1.9 - math.sqrt((1.0 + a) ** 2 / 3.61 - a / 0.95)

    return CheckResult(
        article="8.6.2",
        name="Beam Stability Factor CL",
        capacity=c_l,
        demand=None,  # Standardized back to None
        details={"RB": r_b, "FbE": f_be, "A": a, "RB_ok": r_b <= 50.0},
    )


@article("8.4.4.5", "Volume Factor Cv for Glulam")
def volume_factor_cv(
    d: float,
    b: float,
    l_ft: float,
    southern_pine: bool = False,
) -> float:
    """Cv for glued-laminated timber in flexure (8.4.4.5):
    [(12/d)*(5.125/b)*(21/L)]^a <= 1.0, a = 0.05 for Southern Pine and
    0.10 for all other species.  ``d``/``b`` in inches, ``l_ft`` in ft.
    Cv and CL are not applied simultaneously — use the smaller."""
    if d <= 0.0 or b <= 0.0 or l_ft <= 0.0:
        raise ValueError("Member dimensions (d, b, l_ft) must be strictly positive.")

    a = 0.05 if southern_pine else 0.10
    return min(
        ((12.0 / d) * (5.125 / b) * (21.0 / l_ft)) ** a, 1.0
    )


@article("8.7", "Column Stability Factor Cp")
def column_stability_cp(
    f_co_adj: float,
    e_adj: float,
    l_e: float,
    d: float,
    c: float = 0.8,
    k_ce: float = 0.76,
) -> CheckResult:
    """Column stability factor for wood compression members (8.7):
    Cp = (1+B)/(2c) - sqrt(((1+B)/(2c))^2 - B/c), with B = FcE/Fco' and
    FcE = KcE*E'/(Le/d)^2.

    ``f_co_adj`` is the adjusted compression strength with all factors
    except Cp (ksi); ``c`` = 0.8 sawn lumber, 0.85 round poles, 0.9
    glulam; the Euler coefficient ``k_ce`` defaults to the visually graded
    value.  Slenderness Le/d may not exceed 50.  ``capacity`` holds Cp."""
    if l_e <= 0.0 or d <= 0.0:
        raise ValueError("Effective length and depth must be strictly positive.")

    slenderness = l_e / d

    if slenderness > 50.0:
        c_p, f_ce, b_val = 0.0, 0.0, 0.0
    else:
        f_ce = k_ce * e_adj / slenderness ** 2
        b_val = f_ce / f_co_adj
        c_p = (1.0 + b_val) / (2.0 * c) - math.sqrt(
            ((1.0 + b_val) / (2.0 * c)) ** 2 - b_val / c
        )

    return CheckResult(
        article="8.7",
        name="Column Stability Factor Cp",
        capacity=c_p,
        demand=None,
        details={"FcE": f_ce, "B": b_val, "Le/d": slenderness,
                 "slenderness_ok": slenderness <= 50.0},
    )


@article("8.8.3", "Bearing Adjustment Factor Cb")
def bearing_factor_cb(l_b: float, near_end: bool = False) -> float:
    """Cb (8.8.3): (lb + 0.375)/lb for bearings less than 6 in long and
    at least 3 in from the member end; 1.0 otherwise (``near_end`` or
    long bearings).  ``l_b`` is the bearing length (in)."""
    if l_b <= 0.0:
        raise ValueError("Bearing length must be strictly positive.")
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


# Wet service factors CM (Tables 8.4.4.3-1 and 8.4.4.3-2), keyed by
# property.  Sawn lumber flexure rises to 1.0 when Fbo*CF <= 1.15 ksi
# and compression to 1.0 when Fco*CF <= 0.75 ksi (table footnotes) —
# handled in wet_service_cm.
_CM_SAWN = {"flexure": 0.85, "tension": 1.0, "shear": 0.97,
            "bearing": 0.67, "compression": 0.80, "modulus": 0.90}
_CM_GLULAM = {"flexure": 0.80, "tension": 0.80, "shear": 0.875,
              "bearing": 0.53, "compression": 0.73, "modulus": 0.833}


@article("8.4.4.3", "Wet Service Factor CM")
def wet_service_cm(
    prop: str,
    glulam: bool = False,
    wet: bool = True,
    f_o_cf: float | None = None,
) -> float:
    """Wet service factor CM (8.4.4.3) for a reference design value:
    ``prop`` is one of flexure / tension / shear / bearing /
    compression / modulus.  Dry use (sawn lumber <= 19% moisture,
    glulam < 16%) returns 1.0.

    For sawn lumber pass ``f_o_cf`` = Fbo*CF (flexure) or Fco*CF
    (compression) in ksi to apply the table footnotes that waive the
    reduction for low reference values."""
    if not wet:
        return 1.0
    table = _CM_GLULAM if glulam else _CM_SAWN
    if prop not in table:
        raise ValueError(f"prop must be one of {sorted(table)}")
    if not glulam and f_o_cf is not None:
        if prop == "flexure" and f_o_cf <= 1.15:
            return 1.0
        if prop == "compression" and f_o_cf <= 0.75:
            return 1.0
    return table[prop]


# Flat use factor for sawn dimension lumber (Table 8.4.4.6-1):
# {nominal width: (Cfu for 2-3 in thick, Cfu for 4 in thick)}
_CFU_SAWN = {
    2: (1.00, None), 3: (1.00, None), 4: (1.10, 1.00), 5: (1.10, 1.05),
    6: (1.15, 1.05), 8: (1.15, 1.05), 10: (1.20, 1.10),
}


@article("8.4.4.6", "Flat Use Factor Cfu")
def flat_use_cfu(
    width_nominal: float,
    thickness_nominal: float = 2.0,
    glulam: bool = False,
) -> float:
    """Flat-use factor for bending about the weak axis (8.4.4.6).

    Sawn dimension lumber uses Table 8.4.4.6-1 (nominal dimensions,
    widths above 10 in take the 10-in row).  Glulam loaded parallel to
    the wide laminations uses (12/d)^(1/9) with d the actual dimension
    parallel to the wide face (in), 1.0 at 12 in and wider."""
    if width_nominal <= 0.0 or thickness_nominal <= 0.0:
        raise ValueError("Nominal dimensions must be strictly positive.")
    if glulam:
        return (12.0 / width_nominal) ** (1.0 / 9.0) \
            if width_nominal < 12.0 else 1.0
    width = min(10.0, width_nominal)
    rows = [w for w in _CFU_SAWN if w <= width]
    if not rows:
        return 1.0
    two_three, four = _CFU_SAWN[max(rows)]
    if thickness_nominal >= 4.0:
        return four if four is not None else 1.0
    return two_three


@article("8.4.4.8", "Deck Factor Cd")
def deck_factor_cd(
    deck_type: str,
    thickness_nominal: float = 4.0,
) -> float:
    """Deck factor on Fbo (Table 8.4.4.8-1): 1.15 for stressed-wood,
    spike-laminated, and nail-laminated decks built from 2- to 4-in
    (nominal) thick lumber; 1.0 for plank decks and everything else."""
    laminated = deck_type.lower().replace("-", "_").replace(" ", "_") in (
        "stressed_wood", "spike_laminated", "nail_laminated")
    if laminated and 2.0 <= thickness_nominal <= 4.0:
        return 1.15
    return 1.0


@article("8.8.2", "Timber Tension Resistance")
def timber_tension_resistance(
    f_t_adj: float,
    a_n: float,
    p_u: float | None = None,
) -> CheckResult:
    """Tension parallel to grain (8.8.2): Pn = Ft_adj * An on the net
    section, Pr = phi * Pn with phi = 0.80.

    ``f_t_adj`` is the adjusted tension strength (ksi, including
    CKF/CM/CF/Ci/Clambda), ``a_n`` the net area (in^2)."""
    p_n = f_t_adj * a_n
    return CheckResult(
        article="8.8.2",
        name="Timber Tension Resistance",
        capacity=p_n,
        demand=p_u,
        phi=TIMBER_PHI["tension"],
        details={},
    )


@article("8.7-Pr", "Timber Compression Resistance")
def timber_compression_resistance(
    f_c_adj: float,
    a_g: float,
    c_p: float = 1.0,
    p_u: float | None = None,
) -> CheckResult:
    """Compression parallel to grain (8.7): Pn = Fc_adj * Ag * Cp,
    Pr = phi * Pn with phi = 0.90.

    ``f_c_adj`` is the adjusted compression strength (ksi) *without*
    Cp; pass the column stability factor from
    :func:`column_stability_cp` (1.0 for fully braced members)."""
    p_n = f_c_adj * a_g * c_p
    return CheckResult(
        article="8.7",
        name="Timber Compression Resistance",
        capacity=p_n,
        demand=p_u,
        phi=TIMBER_PHI["compression"],
        details={"Cp": c_p},
    )
