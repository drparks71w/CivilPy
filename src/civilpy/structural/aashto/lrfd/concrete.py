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
5.6.3.3 minimum reinforcement, 5.7.3.3 shear).  Units: kip, inch, ksi.
"""

import math
from dataclasses import dataclass

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


@dataclass
class MCFTParams:
    """beta/theta from the 5.7.3.4.2 general procedure, ready to feed
    :func:`rc_shear_resistance`."""

    beta: float
    theta_deg: float
    eps_s: float
    s_xe: float | None = None


@article("5.7.3.4.2", "Shear Resistance Parameters — General (MCFT) Procedure")
def rc_mcft_beta_theta(
    m_u: float,
    v_u: float,
    d_v: float,
    e_s_a_s: float,
    n_u: float = 0.0,
    v_p: float = 0.0,
    a_ps: float = 0.0,
    f_po: float = 0.0,
    e_p_a_ps: float = 0.0,
    has_min_transverse_reinf: bool = True,
    s_x: float | None = None,
    a_g_agg: float = 0.75,
    e_c_a_ct: float = 0.0,
) -> MCFTParams:
    """Longitudinal strain, beta, and theta per the general (MCFT-based)
    procedure (5.7.3.4.2).

    ``e_s_a_s`` and ``e_p_a_ps`` are the stiffness products Es*As and
    Ep*Aps (kip) on the flexural tension side; ``f_po`` is normally
    0.7*fpu for bonded strand.  With minimum transverse reinforcement,
    beta = 4.8/(1 + 750*eps_s); without it the crack-spacing penalty
    51/(39 + sxe) applies, where ``s_x`` (in) and the max aggregate size
    ``a_g_agg`` (in) set sxe.  When eps_s comes out negative (section
    uncracked), the concrete stiffness ``e_c_a_ct`` = Ec*Act may be added
    to the denominator; eps_s is bounded to [-0.40e-3, 6.0e-3].
    """
    demand = abs(m_u) / d_v + 0.5 * n_u + abs(v_u - v_p) - a_ps * f_po
    eps_s = demand / (e_s_a_s + e_p_a_ps)
    if eps_s < 0.0:
        eps_s = demand / (e_s_a_s + e_p_a_ps + e_c_a_ct)
    eps_s = min(max(eps_s, -0.40e-3), 6.0e-3)

    beta = 4.8 / (1.0 + 750.0 * eps_s)
    s_xe = None
    if not has_min_transverse_reinf:
        if s_x is None:
            raise ValueError(
                "s_x (crack spacing parameter) is required when the section "
                "lacks minimum transverse reinforcement"
            )
        s_xe = min(max(s_x * 1.38 / (a_g_agg + 0.63), 12.0), 80.0)
        beta *= 51.0 / (39.0 + s_xe)
    theta = 29.0 + 3500.0 * eps_s
    return MCFTParams(beta=beta, theta_deg=theta, eps_s=eps_s, s_xe=s_xe)


@article("5.7.2.5", "Minimum Transverse Reinforcement")
def rc_min_transverse_reinforcement(
    b_v: float,
    s: float,
    f_c: float,
    f_y: float = 60.0,
    a_v: float | None = None,
    lam: float = 1.0,
) -> CheckResult:
    """Minimum transverse reinforcement where shear reinforcement is
    required (5.7.2.5-1): Av >= 0.0316*lam*sqrt(f'c)*bv*s/fy.

    ``capacity`` is the provided ``a_v`` (in^2) and ``demand`` the required
    minimum, so ratio >= 1 passes."""
    required = 0.0316 * lam * math.sqrt(f_c) * b_v * s / f_y
    return CheckResult(
        article="5.7.2.5",
        name="Minimum Transverse Reinforcement",
        capacity=a_v if a_v is not None else required,
        demand=required if a_v is not None else None,
        details={"Av_min": required},
    )


@article("5.7.2.6", "Maximum Spacing of Transverse Reinforcement")
def rc_max_stirrup_spacing(
    v_u: float,
    b_v: float,
    d_v: float,
    f_c: float,
    s: float | None = None,
    v_p: float = 0.0,
    phi_v: float = 0.9,
) -> CheckResult:
    """Maximum stirrup spacing (5.7.2.6): with the shear stress
    vu = |Vu - phi*Vp|/(phi*bv*dv), smax = min(0.8*dv, 24in) when
    vu < 0.125*f'c, else min(0.4*dv, 12in).  ``capacity`` is smax and
    ``demand`` the actual spacing ``s``."""
    v_stress = abs(v_u - phi_v * v_p) / (phi_v * b_v * d_v)
    if v_stress < 0.125 * f_c:
        s_max = min(0.8 * d_v, 24.0)
    else:
        s_max = min(0.4 * d_v, 12.0)
    return CheckResult(
        article="5.7.2.6",
        name="Maximum Spacing of Transverse Reinforcement",
        capacity=s_max,
        demand=s,
        details={"vu_stress": v_stress, "high_shear": v_stress >= 0.125 * f_c},
    )


@article("5.7.3.5", "Longitudinal Reinforcement")
def rc_longitudinal_reinforcement(
    m_u: float,
    v_u: float,
    d_v: float,
    theta_deg: float,
    a_s_f_y: float = 0.0,
    a_ps_f_ps: float = 0.0,
    n_u: float = 0.0,
    v_s: float = 0.0,
    v_p: float = 0.0,
    phi_f: float = 0.9,
    phi_v: float = 0.9,
    phi_c: float = 0.75,
) -> CheckResult:
    """Tension demand on longitudinal reinforcement from combined moment,
    axial, and shear (5.7.3.5-1):

    Aps*fps + As*fy >= |Mu|/(dv*phi_f) + 0.5*Nu/phi_c
                       + (|Vu/phi_v - Vp| - 0.5*Vs)*cot(theta)

    ``v_s`` is capped at Vu/phi_v per the article.  ``capacity`` is the
    tension the reinforcement can develop (pass the products As*fy and
    Aps*fps), ``demand`` the required tension."""
    v_s_used = min(v_s, v_u / phi_v)
    cot = 1.0 / math.tan(math.radians(theta_deg))
    required = (
        abs(m_u) / (d_v * phi_f)
        + 0.5 * n_u / phi_c
        + (abs(v_u / phi_v - v_p) - 0.5 * v_s_used) * cot
    )
    return CheckResult(
        article="5.7.3.5",
        name="Longitudinal Reinforcement",
        capacity=a_s_f_y + a_ps_f_ps,
        demand=required,
        details={"Vs_used": v_s_used, "cot_theta": cot},
    )


# Cohesion/friction cases of 5.7.4.4 (c ksi, mu, K1, K2 ksi) — normal-weight
# values; the lightweight K2 reductions are noted per case.
INTERFACE_SHEAR_CASES = {
    "monolithic": (0.40, 1.4, 0.25, 1.5),
    "roughened": (0.28, 1.0, 0.3, 1.8),       # CIP slab on roughened girder
    "not_roughened": (0.075, 0.6, 0.2, 0.8),  # clean, not roughened
    "steel": (0.025, 0.7, 0.2, 0.8),          # concrete on clean steel
}


@article("5.7.4", "Interface Shear Transfer")
def rc_interface_shear(
    a_cv: float,
    f_c: float,
    case: str = "roughened",
    v_ui: float | None = None,
    a_vf: float = 0.0,
    f_y: float = 60.0,
    p_c: float = 0.0,
) -> CheckResult:
    """Interface (horizontal) shear resistance (5.7.4.3-3):
    Vni = c*Acv + mu*(Avf*fy + Pc), capped at min(K1*f'c, K2)*Acv.

    ``case`` selects the 5.7.4.4 cohesion/friction set (see
    ``INTERFACE_SHEAR_CASES``); ``a_cv`` is the interface area (in^2),
    ``a_vf`` the reinforcement crossing it (in^2), ``p_c`` permanent net
    compressive force (kip); ``v_ui`` the factored interface shear demand
    (kip) checked against phi_v = 0.9 times Vni.  ``details`` includes the
    5.7.4.2 minimum Avf."""
    c, mu, k1, k2 = INTERFACE_SHEAR_CASES[case]
    v_ni = c * a_cv + mu * (a_vf * f_y + p_c)
    upper = min(k1 * f_c, k2) * a_cv
    return CheckResult(
        article="5.7.4",
        name="Interface Shear Transfer",
        capacity=min(v_ni, upper),
        demand=v_ui,
        phi=0.9,
        details={"c": c, "mu": mu, "upper_limit": upper,
                 "Avf_min": 0.05 * a_cv / f_y, "case": case},
    )


@article("5.7.2.1", "Torsion Threshold")
def rc_torsion_threshold(
    a_cp: float,
    p_c: float,
    f_c: float,
    t_u: float | None = None,
    f_pc: float = 0.0,
    lam: float = 1.0,
    phi_t: float = 0.9,
) -> CheckResult:
    """Whether torsion must be considered (5.7.2.1): Tu > 0.25*phi*Tcr with
    Tcr = 0.126*lam*sqrt(f'c)*(Acp^2/pc)*sqrt(1 + fpc/(0.126*lam*sqrt(f'c)))
    for solid sections.

    ``a_cp`` is the area enclosed by the outside perimeter (in^2), ``p_c``
    that perimeter (in), ``f_pc`` the prestress at the centroid (ksi).
    ``capacity`` is the 0.25*phi*Tcr threshold (kip-in); ``ok`` True means
    torsion may be neglected."""
    sqrt_term = 0.126 * lam * math.sqrt(f_c)
    t_cr = sqrt_term * a_cp**2 / p_c * math.sqrt(1.0 + f_pc / sqrt_term)
    return CheckResult(
        article="5.7.2.1",
        name="Torsion Threshold",
        capacity=0.25 * phi_t * t_cr,
        demand=t_u,
        details={"Tcr": t_cr},
    )


@article("5.10.8.2.1", "Tension Development Length")
def rebar_development_length(
    d_b: float,
    f_y: float = 60.0,
    f_c: float = 4.0,
    top_bar: bool = False,
    epoxy_coated: bool = False,
    cover_lt_3db: bool = False,
    lambda_rc: float = 1.0,
    lam: float = 1.0,
    available: float | None = None,
) -> CheckResult:
    """Tension development length of deformed bars (5.10.8.2.1, current
    edition): ld = ldb * modifiers, ldb = 2.4*db*fy/sqrt(f'c), >= 12 in.

    Modifiers: 1.3 for top bars (>12 in of fresh concrete below), epoxy
    coating 1.5 when cover < 3db or clear spacing < 6db else 1.2 (their
    product with the top-bar factor need not exceed 1.7), confinement
    reduction ``lambda_rc`` (0.4 <= lambda_rc <= 1.0) from 5.10.8.2.1c.
    ``capacity`` is the available embedment when given (ok means it
    exceeds ld); otherwise ld itself."""
    l_db = 2.4 * d_b * f_y / math.sqrt(f_c)
    cf = 1.3 if top_bar else 1.0
    if epoxy_coated:
        cf_epoxy = 1.5 if cover_lt_3db else 1.2
        cf = min(cf * cf_epoxy, 1.7)
    l_d = max(l_db * cf * max(min(lambda_rc, 1.0), 0.4) / lam, 12.0)
    return CheckResult(
        article="5.10.8.2.1",
        name="Tension Development Length",
        capacity=available if available is not None else l_d,
        demand=l_d if available is not None else None,
        details={"ldb": l_db, "modifier": cf, "lambda_rc": lambda_rc,
                 "ld": l_d},
    )


@article("5.6.3.5.2", "Effective Moment of Inertia")
def rc_effective_moment_of_inertia(
    i_g: float,
    i_cr: float,
    m_cr: float,
    m_a: float,
) -> float:
    """Branson effective moment of inertia for deflections (5.6.3.5.2):
    Ie = (Mcr/Ma)^3*Ig + (1 - (Mcr/Ma)^3)*Icr, capped at Ig and equal to
    Ig when the section is uncracked (Ma <= Mcr).  in^4."""
    if m_a <= m_cr:
        return i_g
    ratio = (m_cr / m_a) ** 3
    return min(ratio * i_g + (1.0 - ratio) * i_cr, i_g)


@article("2.5.2.6.2", "Optional Live Load Deflection Criteria")
def deflection_limit(
    span: float,
    deflection: float | None = None,
    pedestrian: bool = False,
    cantilever: bool = False,
) -> CheckResult:
    """Optional live-load deflection limits (2.5.2.6.2): span/800
    (vehicular), span/1000 (with pedestrian use); cantilevers span/300 and
    span/375 respectively.  Same length unit in and out."""
    if cantilever:
        divisor = 375.0 if pedestrian else 300.0
    else:
        divisor = 1000.0 if pedestrian else 800.0
    return CheckResult(
        article="2.5.2.6.2",
        name="Optional Live Load Deflection Criteria",
        capacity=span / divisor,
        demand=deflection,
        details={"divisor": divisor},
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


@article("5.12.7.3", "Shear in Slabs of Box Culverts")
def box_culvert_slab_shear(
    b: float,
    d_e: float,
    f_c: float,
    a_s: float,
    v_u: float,
    m_u: float,
    fill_ft: float = 2.0,
    single_cell: bool = False,
    monolithic: bool = True,
    lam: float = 1.0,
) -> CheckResult:
    """Concrete shear resistance of box-culvert slabs under 2.0 ft or
    more of fill (5.12.7.3; numbered 5.14.5.3 before the 8th Edition):

        Vc = (0.0676*lam*sqrt(f'c) + 4.6*(As/(b*de))*(Vu*de/Mu))*b*de

    with Vu*de/Mu taken <= 1.0 (5.12.7.3-1), capped at
    0.126*lam*sqrt(f'c)*b*de (5.12.7.3-2).  Slabs of single-cell boxes
    need not take Vc less than 0.0948*lam*sqrt(f'c)*b*de when
    monolithic with the walls, or 0.0791*lam*sqrt(f'c)*b*de when
    simply supported.

    ``a_s`` is the area of flexural reinforcement in the design width
    ``b`` (in^2, in); ``v_u``/``m_u`` the concurrent factored shear and
    moment (kip, kip-in); ``lam`` the lightweight-concrete factor.
    Slabs under less than 2.0 ft of fill are outside this article —
    use :func:`rc_shear_resistance` (``details["applicable"]`` flags
    it).  phi_v = 0.90.
    """
    moment_ratio = min(v_u * d_e / abs(m_u), 1.0) if m_u else 1.0
    sqrt_fc = lam * math.sqrt(f_c)
    v_c = (0.0676 * sqrt_fc + 4.6 * a_s / (b * d_e) * moment_ratio) * b * d_e
    v_c = min(v_c, 0.126 * sqrt_fc * b * d_e)
    floor = None
    if single_cell:
        floor = (0.0948 if monolithic else 0.0791) * sqrt_fc * b * d_e
        v_c = max(v_c, min(floor, 0.126 * sqrt_fc * b * d_e))
    return CheckResult(
        article="5.12.7.3",
        name="Shear in Slabs of Box Culverts",
        capacity=v_c,
        demand=v_u,
        phi=0.90,
        details={
            "Vu*de/Mu": moment_ratio,
            "cap": 0.126 * sqrt_fc * b * d_e,
            "single_cell_floor": floor,
            "applicable": fill_ft >= 2.0,
        },
    )


# ── Flexural reinforcement sizing ──────────────────────────────────────────────


@dataclass
class FlexuralRebarDesign:
    """Result of :func:`size_flexural_rebar`.

    ``a_s_required`` (in^2) is the tension-steel area that just reaches the
    governing target; ``a_s_provided`` is what the selected whole ``n_bars``
    of ``bar_size`` actually supply.  ``governing`` is ``"strength"`` or
    ``"minimum reinforcement"``.  ``check`` is the flexural
    :class:`CheckResult` evaluated with the provided steel against ``m_u``
    (so ``check.ratio >= 1`` confirms the selection works).
    """

    a_s_required: float
    a_s_provided: float
    n_bars: int
    bar_size: int
    governing: str
    check: CheckResult


def size_flexural_rebar(
    m_u: float,
    b: float,
    d_s: float,
    *,
    f_c: float = 4.0,
    f_y: float = 60.0,
    bar_size: int = 8,
    h: float | None = None,
    design_year: int | None = None,
    rho_max: float = 0.08,
) -> FlexuralRebarDesign:
    """Select tension reinforcement for a singly reinforced rectangular RC
    section to carry a factored moment ``m_u`` (kip-in).

    The area is found by bisecting
    :func:`rc_rectangular_flexural_resistance` until the factored resistance
    phi*Mn reaches the governing target, then the whole number of
    ``bar_size`` (ASTM #) bars that supplies it is chosen.  When the total
    depth ``h`` (in) is given, the minimum-reinforcement provision (5.6.3.3)
    can raise the target above the strength demand -- the lesser of
    ``Mcr`` and ``1.33*Mu`` -- and ``governing`` records which controlled.

    This stops at a *checked* design: it returns the bars and the governing
    :class:`CheckResult`; detailing (bar spacing, layers, development,
    crack control via :func:`rc_crack_control_spacing`) is the engineer's.
    ``b``, ``d_s``, ``h`` in inches; ``f_c``, ``f_y`` in ksi; ``m_u`` kip-in.
    """
    from civilpy.structural.steel import Rebar

    bar_area = float(Rebar(bar_size).area.magnitude)

    target = m_u
    governing = "strength"
    if h is not None:
        fr = modulus_of_rupture(f_c)
        if design_year is not None and design_year < 2012:
            gamma_1, gamma_3 = 1.2, 1.0
        else:
            gamma_1, gamma_3 = 1.6, 0.67
        s_c = b * h ** 2 / 6.0
        m_cr = gamma_3 * gamma_1 * fr * s_c
        min_target = min(m_cr, 1.33 * m_u)
        if min_target > target:
            target, governing = min_target, "minimum reinforcement"

    def factored_mn(a_s: float) -> float:
        return rc_rectangular_flexural_resistance(
            a_s=a_s, f_y=f_y, f_c=f_c, b=b, d_s=d_s
        ).factored_capacity

    # Grow an upper bound until it carries the target (capped at rho_max).
    cap = rho_max * b * d_s
    hi = min(0.05, cap)
    while factored_mn(hi) < target and hi < cap:
        hi = min(hi * 2.0, cap)
    lo = 0.0
    for _ in range(100):  # bisection to a tight A_s tolerance
        mid = 0.5 * (lo + hi)
        if factored_mn(mid) >= target:
            hi = mid
        else:
            lo = mid
    a_s_required = hi

    n_bars = max(1, math.ceil(a_s_required / bar_area))
    a_s_provided = n_bars * bar_area
    check = rc_rectangular_flexural_resistance(
        a_s=a_s_provided, f_y=f_y, f_c=f_c, b=b, d_s=d_s, m_u=m_u
    )
    return FlexuralRebarDesign(
        a_s_required=a_s_required,
        a_s_provided=a_s_provided,
        n_bars=n_bars,
        bar_size=bar_size,
        governing=governing,
        check=check,
    )
