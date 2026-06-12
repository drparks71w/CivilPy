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

"""AASHTO LRFD Chapter 5 — reinforced concrete design checks.

Article numbers follow the 8th Edition reorganization (5.6.3.2 flexure,
5.6.3.3 minimum reinforcement, 5.7.3.3 shear), the numbering BrR uses for
its 8th/9th/10th Edition spec engines.  Units: kip, inch, ksi.
"""

import math

from civilpy.structural.aashto.lrfd.core import CheckResult, article


def beta1(f_c: float) -> float:
    """Stress-block factor beta1 (5.6.2.2)."""
    return min(max(0.85 - 0.05 * (f_c - 4.0), 0.65), 0.85)


def modulus_of_rupture(f_c: float) -> float:
    """fr = 0.24*sqrt(f'c), normal-weight concrete (5.4.2.6), ksi."""
    return 0.24 * math.sqrt(f_c)


def phi_flexure(eps_t: float, eps_cl: float = 0.002, eps_tl: float = 0.005) -> float:
    """Resistance factor for flexure from net tensile strain (5.5.4.2).

    Varies linearly from 0.75 (compression-controlled, eps_t <= eps_cl) to
    0.90 (tension-controlled, eps_t >= eps_tl) for nonprestressed sections.
    """
    return min(max(0.75 + 0.15 * (eps_t - eps_cl) / (eps_tl - eps_cl), 0.75), 0.90)


@article("5.6.3.2", "Flexural Resistance (Reinforced Concrete)")
def rc_rectangular_flexural_resistance(
    a_s: float,
    f_y: float,
    f_c: float,
    b: float,
    d_s: float,
    m_u: float | None = None,
    a_s_prime: float = 0.0,
    d_s_prime: float = 0.0,
    f_y_prime: float | None = None,
) -> CheckResult:
    """Nominal flexural resistance of a rectangular (or rectangular-behaving)
    reinforced section (5.6.3.2.3), with phi per 5.5.4.2.

    Parameters: tension steel ``a_s`` (in^2) at depth ``d_s`` (in),
    compression steel ``a_s_prime`` at ``d_s_prime``, section width ``b``
    (in), ``f_y``/``f_c`` (ksi), optional factored moment demand ``m_u``
    (kip-in).  Compression steel is assumed yielding only if the computed
    strain supports it; otherwise it is ignored (conservative).
    """
    b1 = beta1(f_c)
    f_yp = f_y if f_y_prime is None else f_y_prime

    # Try with compression steel at yield first (5.6.3.1.1-4 reduced form).
    a_s_p = a_s_prime
    c = (a_s * f_y - a_s_p * f_yp) / (0.85 * f_c * b1 * b) if a_s_p else None
    if a_s_p and c is not None:
        eps_sp = 0.003 * (c - d_s_prime) / c if c > 0 else -1.0
        if c <= 0 or eps_sp < f_yp / 29000.0:
            a_s_p = 0.0  # compression steel not yielding — neglect it
    if not a_s_p:
        c = a_s * f_y / (0.85 * f_c * b1 * b)
    a = b1 * c  # depth of equivalent stress block

    if a_s_p:
        # 5.6.3.2.2-1 terms rearranged for a rectangular section
        m_n = (a_s * f_y - a_s_p * f_yp) * (d_s - a / 2.0) + a_s_p * f_yp * (
            d_s - d_s_prime
        )
    else:
        m_n = a_s * f_y * (d_s - a / 2.0)

    eps_t = 0.003 * (d_s - c) / c  # net tensile strain at extreme steel
    phi = phi_flexure(eps_t)

    return CheckResult(
        article="5.6.3.2",
        name="Flexural Resistance (Reinforced Concrete)",
        capacity=m_n,
        demand=m_u,
        phi=phi,
        details={
            "a": a,
            "c": c,
            "beta1": b1,
            "eps_t": eps_t,
            "tension_controlled": eps_t >= 0.005,
            "compression_steel_active": bool(a_s_p),
        },
    )


@article("5.6.3.3", "Minimum Reinforcement")
def rc_minimum_reinforcement(
    m_n: float,
    phi: float,
    f_c: float,
    s_c: float,
    m_u: float | None = None,
    gamma_1: float = 1.6,
    gamma_3: float = 0.67,
    design_year: int | None = None,
) -> CheckResult:
    """Minimum flexural reinforcement check (5.6.3.3): Mr = phi*Mn must
    exceed the lesser of Mcr = gamma_3*gamma_1*fr*Sc and 1.33*Mu.

    ``s_c`` is the section modulus of the extreme tension fiber (in^3),
    ``gamma_1`` = 1.6 flexural cracking variability (1.2 precast segmental),
    ``gamma_3`` = 0.67 for A615 Grade 60 (0.75 for A706).  Designs before
    the 2012 6th Edition used 1.2*Mcr instead of the gamma factors — pass
    ``design_year`` for historical designs (gamma overrides are ignored in
    that case).
    """
    fr = modulus_of_rupture(f_c)
    if design_year is not None and design_year < 2012:
        gamma_1, gamma_3 = 1.2, 1.0  # pre-6E form: 1.2*Mcr
    m_cr = gamma_3 * gamma_1 * fr * s_c  # 5.6.3.3-1 (nonprestressed)
    target = m_cr if m_u is None else min(m_cr, 1.33 * m_u)
    return CheckResult(
        article="5.6.3.3",
        name="Minimum Reinforcement",
        capacity=phi * m_n,
        demand=target,
        phi=1.0,  # phi already applied to Mn
        details={"fr": fr, "Mcr": m_cr, "governing_target": target,
                 "gamma_1": gamma_1, "gamma_3": gamma_3},
    )


@article("5.6.7", "Control of Cracking by Distribution of Reinforcement")
def rc_crack_control_spacing(
    d_c: float,
    h: float,
    f_ss: float,
    f_y: float = 60.0,
    spacing: float | None = None,
    exposure_class_2: bool = False,
) -> CheckResult:
    """Maximum bar spacing for crack control (5.6.7, 2005 interim onward):
    s <= 700*gamma_e/(beta_s*fss) - 2*dc, the standard deck and tension-face
    check.

    ``d_c`` is cover to center of nearest bar (in), ``h`` overall thickness
    (in), ``f_ss`` service-level steel stress (ksi, capped at 0.6*fy per the
    article), ``spacing`` the actual bar spacing (demand).  Class 2 exposure
    (gamma_e = 0.75) is for decks/substructure exposed to chlorides; Class 1
    (1.00) otherwise.
    """
    gamma_e = 0.75 if exposure_class_2 else 1.00
    beta_s = 1.0 + d_c / (0.7 * (h - d_c))
    f_ss_used = min(f_ss, 0.6 * f_y)
    s_max = 700.0 * gamma_e / (beta_s * f_ss_used) - 2.0 * d_c
    return CheckResult(
        article="5.6.7",
        name="Control of Cracking by Distribution of Reinforcement",
        capacity=s_max,
        demand=spacing,
        details={"gamma_e": gamma_e, "beta_s": beta_s, "fss_used": f_ss_used},
    )


@article("5.6.7 (pre-2005)", "Crack Control — z-Factor Method")
def rc_crack_control_z_factor(
    d_c: float,
    a_bar: float,
    f_ss: float | None = None,
    f_y: float = 60.0,
    z: float = 170.0,
) -> CheckResult:
    """Crack control for designs before the 2005 interim revisions, when
    the article (then 5.7.3.4) limited steel stress to z/(dc*A)^(1/3)
    rather than limiting bar spacing.

    ``a_bar`` is the concrete tension area per bar A = 2*dc*s/n (in^2),
    ``z`` the crack-width parameter (kip/in): 170 moderate exposure, 130
    severe, 100 buried.  ``f_ss`` is the service steel stress (demand,
    ksi); the allowable is also capped at 0.6*fy.
    """
    f_sa = min(z / (d_c * a_bar) ** (1.0 / 3.0), 0.6 * f_y)
    return CheckResult(
        article="5.6.7 (pre-2005)",
        name="Crack Control — z-Factor Method",
        capacity=f_sa,
        demand=f_ss,
        details={"z": z, "A": a_bar},
    )


@article("5.7.3.3", "Shear Resistance (Reinforced Concrete)")
def rc_shear_resistance(
    b_v: float,
    d_v: float,
    f_c: float,
    v_u: float | None = None,
    a_v: float = 0.0,
    s: float = 1.0,
    f_y: float = 60.0,
    beta: float = 2.0,
    theta_deg: float = 45.0,
    v_p: float = 0.0,
    lam: float = 1.0,
) -> CheckResult:
    """Nominal shear resistance Vn (5.7.3.3) with phi_v = 0.9 (5.5.4.2).

    Vc = 0.0316*lam*beta*sqrt(f'c)*bv*dv (5.7.3.3-3) and Vs per 5.7.3.3-4
    with vertical stirrups ``a_v`` (in^2) at spacing ``s`` (in).  Defaults
    beta = 2.0 / theta = 45 deg correspond to the 5.7.3.4.1 simplified
    procedure; pass values from the 5.7.3.4.2 general (MCFT) procedure for
    sections that qualify for it.
    """
    v_c = 0.0316 * lam * beta * math.sqrt(f_c) * b_v * d_v
    v_s = a_v * f_y * d_v / (s * math.tan(math.radians(theta_deg))) if a_v else 0.0
    v_n = min(v_c + v_s + v_p, 0.25 * f_c * b_v * d_v + v_p)  # 5.7.3.3-1,-2
    return CheckResult(
        article="5.7.3.3",
        name="Shear Resistance (Reinforced Concrete)",
        capacity=v_n,
        demand=v_u,
        phi=0.9,
        details={
            "Vc": v_c,
            "Vs": v_s,
            "Vp": v_p,
            "upper_limit": 0.25 * f_c * b_v * d_v + v_p,
            "beta": beta,
            "theta_deg": theta_deg,
        },
    )
