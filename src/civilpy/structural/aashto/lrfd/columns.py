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

"""AASHTO LRFD 5.6.4 / 4.5.3.2.2 — reinforced concrete compression members.

Axial resistance, reinforcement limits, spiral steel, and the approximate
moment-magnification treatment of slenderness.  Units: kip, inch, ksi.
"""

from civilpy.structural.aashto.lrfd.core import CheckResult, article

PHI_COMPRESSION = 0.75  # compression-controlled sections (5.5.4.2)


@article("5.6.4.4", "Axial Resistance of Compression Members")
def rc_column_axial_resistance(
    a_g: float,
    a_st: float,
    f_c: float,
    f_y: float,
    p_u: float | None = None,
    spiral: bool = False,
) -> CheckResult:
    """Nominal axial resistance of a nonprestressed column (5.6.4.4):
    Po = 0.85*f'c*(Ag - Ast) + fy*Ast, with Pn = 0.85*Po for spiral columns
    and 0.80*Po for tied columns; phi = 0.75."""
    p_o = 0.85 * f_c * (a_g - a_st) + f_y * a_st
    factor = 0.85 if spiral else 0.80
    p_n = factor * p_o
    return CheckResult(
        article="5.6.4.4",
        name="Axial Resistance of Compression Members",
        capacity=p_n,
        demand=p_u,
        phi=PHI_COMPRESSION,
        details={"Po": p_o, "factor": factor,
                 "transverse": "spiral" if spiral else "tied"},
    )


@article("5.6.4.2", "Limits for Reinforcement of Compression Members")
def rc_column_reinforcement_limits(
    a_g: float,
    a_st: float,
    f_c: float,
    f_y: float,
) -> CheckResult:
    """Longitudinal reinforcement limits for columns (5.6.4.2):
    maximum Ast/Ag <= 0.08 and minimum Ast*fy/(Ag*f'c) >= 0.135.

    Pass/fail check — per-limit booleans in ``details``."""
    ratio = a_st / a_g
    strength_ratio = a_st * f_y / (a_g * f_c)
    checks = {
        "max_steel": ratio <= 0.08,
        "min_steel": strength_ratio >= 0.135,
    }
    all_ok = all(checks.values())
    return CheckResult(
        article="5.6.4.2",
        name="Limits for Reinforcement of Compression Members",
        capacity=1.0 if all_ok else 0.0,
        demand=1.0,
        details={**checks, "Ast/Ag": ratio,
                 "Ast*fy/(Ag*f'c)": strength_ratio},
    )


@article("5.6.4.6", "Spiral Reinforcement Ratio")
def rc_spiral_reinforcement(
    a_g: float,
    a_c: float,
    f_c: float,
    f_yh: float = 60.0,
    rho_s_provided: float | None = None,
) -> CheckResult:
    """Minimum volumetric spiral reinforcement ratio (5.6.4.6-1):
    rho_s >= 0.45*(Ag/Ac - 1)*f'c/fyh.

    ``a_c`` is the core area to the outside of the spiral (in^2); the
    provided ratio (4*Asp/(d_core*pitch)) is the capacity side."""
    required = 0.45 * (a_g / a_c - 1.0) * f_c / f_yh
    return CheckResult(
        article="5.6.4.6",
        name="Spiral Reinforcement Ratio",
        capacity=rho_s_provided if rho_s_provided is not None else required,
        demand=required if rho_s_provided is not None else None,
        details={"rho_s_min": required},
    )


@article("4.5.3.2.2b", "Moment Magnification — Beam Columns")
def moment_magnification(
    p_u: float,
    p_e: float,
    m_1: float = 0.0,
    m_2: float = 1.0,
    braced: bool = True,
    sum_p_u: float | None = None,
    sum_p_e: float | None = None,
    phi_k: float = 0.75,
) -> CheckResult:
    """Approximate slenderness treatment (4.5.3.2.2b): magnify the factored
    moment by delta_b = Cm/(1 - Pu/(phi_K*Pe)) >= 1.0 for the braced
    (no-sway) portion, with Cm = 0.6 + 0.4*(M1/M2) >= 0.4 for members
    without transverse loads; the sway portion uses
    delta_s = 1/(1 - sum(Pu)/(phi_K*sum(Pe))).

    ``m_1``/``m_2`` are the smaller/larger end moments (signed positive for
    single curvature).  ``capacity`` holds the governing magnifier."""
    c_m = max(0.6 + 0.4 * (m_1 / m_2), 0.4) if m_2 != 0 else 1.0
    delta_b = max(c_m / (1.0 - p_u / (phi_k * p_e)), 1.0)
    delta_s = None
    if not braced:
        if sum_p_u is None or sum_p_e is None:
            raise ValueError("sway frames need sum_p_u and sum_p_e")
        delta_s = 1.0 / (1.0 - sum_p_u / (phi_k * sum_p_e))
    return CheckResult(
        article="4.5.3.2.2b",
        name="Moment Magnification — Beam Columns",
        capacity=max(delta_b, delta_s or 0.0),
        details={"Cm": c_m, "delta_b": delta_b, "delta_s": delta_s},
    )
