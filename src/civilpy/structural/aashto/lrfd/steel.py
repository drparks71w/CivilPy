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

"""AASHTO LRFD Chapter 6 — steel I-girder design checks.

Articles follow the 9th/10th Edition numbering (unchanged since the 5th
Edition for these checks).  Units: kip, inch, ksi.
"""

import math

from civilpy.structural.aashto.lrfd.core import CheckResult, article

E_STEEL = 29000.0  # ksi, modulus of elasticity (6.4.1)
PHI_F = 1.0  # resistance factor for flexure (6.5.4.2)
PHI_V = 1.0  # resistance factor for shear (6.5.4.2)


def _fyr(f_yc: float, f_yw: float) -> float:
    """Fyr = min(0.7*Fyc, Fyw), floored at 0.5*Fyc — the stress level the
    buckling equations treat as the start of yielding in the compression
    flange once residual stresses are accounted for."""
    return max(min(0.7 * f_yc, f_yw), 0.5 * f_yc)


@article("6.10.8.2.2", "Local Buckling Resistance")
def flange_local_buckling_resistance(
    b_fc: float,
    t_fc: float,
    f_yc: float,
    f_yw: float,
    f_bu: float | None = None,
    r_b: float = 1.0,
    r_h: float = 1.0,
) -> CheckResult:
    """Compression-flange local buckling resistance Fnc (6.10.8.2.2).

    Parameters: flange width ``b_fc`` and thickness ``t_fc`` (in), yield
    strengths ``f_yc``/``f_yw`` (ksi), factored compression-flange stress
    ``f_bu`` (ksi, optional demand), web load-shedding factor ``r_b``
    (6.10.1.10.2) and hybrid factor ``r_h`` (6.10.1.10.1).
    """
    lam_f = b_fc / (2.0 * t_fc)  # 6.10.8.2.2-3
    lam_pf = 0.38 * math.sqrt(E_STEEL / f_yc)  # 6.10.8.2.2-4
    f_yr = _fyr(f_yc, f_yw)
    lam_rf = 0.56 * math.sqrt(E_STEEL / f_yr)  # 6.10.8.2.2-5

    if lam_f <= lam_pf:
        f_nc = r_b * r_h * f_yc  # 6.10.8.2.2-1
    else:
        f_nc = (
            1.0 - (1.0 - f_yr / (r_h * f_yc)) * (lam_f - lam_pf) / (lam_rf - lam_pf)
        ) * r_b * r_h * f_yc  # 6.10.8.2.2-2

    return CheckResult(
        article="6.10.8.2.2",
        name="Local Buckling Resistance",
        capacity=f_nc,
        demand=f_bu,
        phi=PHI_F,
        details={
            "lambda_f": lam_f,
            "lambda_pf": lam_pf,
            "lambda_rf": lam_rf,
            "Fyr": f_yr,
            "compact": lam_f <= lam_pf,
        },
    )


@article("6.10.8.2.3", "Lateral Torsional Buckling Resistance")
def lateral_torsional_buckling_resistance(
    l_b: float,
    b_fc: float,
    t_fc: float,
    d_c: float,
    t_w: float,
    f_yc: float,
    f_yw: float,
    c_b: float = 1.0,
    f_bu: float | None = None,
    r_b: float = 1.0,
    r_h: float = 1.0,
) -> CheckResult:
    """Compression-flange lateral torsional buckling resistance Fnc
    (6.10.8.2.3).

    Parameters: unbraced length ``l_b`` (in), compression flange ``b_fc`` x
    ``t_fc`` (in), depth of web in compression ``d_c`` (in), web thickness
    ``t_w`` (in), yield strengths (ksi), moment gradient modifier ``c_b``,
    optional factored flange stress demand ``f_bu`` (ksi).
    """
    # Effective radius of gyration for LTB (6.10.8.2.3-9)
    r_t = b_fc / math.sqrt(12.0 * (1.0 + d_c * t_w / (3.0 * b_fc * t_fc)))
    l_p = 1.0 * r_t * math.sqrt(E_STEEL / f_yc)  # 6.10.8.2.3-4
    f_yr = _fyr(f_yc, f_yw)
    l_r = math.pi * r_t * math.sqrt(E_STEEL / f_yr)  # 6.10.8.2.3-5

    f_max = r_b * r_h * f_yc
    if l_b <= l_p:
        f_nc = f_max  # 6.10.8.2.3-1
        regime = "inelastic-plateau"
    elif l_b <= l_r:
        f_nc = min(
            c_b
            * (1.0 - (1.0 - f_yr / (r_h * f_yc)) * (l_b - l_p) / (l_r - l_p))
            * f_max,
            f_max,
        )  # 6.10.8.2.3-2
        regime = "inelastic"
    else:
        f_cr = c_b * r_b * math.pi**2 * E_STEEL / (l_b / r_t) ** 2  # 6.10.8.2.3-8
        f_nc = min(f_cr, f_max)  # 6.10.8.2.3-3
        regime = "elastic"

    return CheckResult(
        article="6.10.8.2.3",
        name="Lateral Torsional Buckling Resistance",
        capacity=f_nc,
        demand=f_bu,
        phi=PHI_F,
        details={"rt": r_t, "Lp": l_p, "Lr": l_r, "Fyr": f_yr, "Cb": c_b,
                 "regime": regime},
    )


@article("6.10.8.1.2", "Discretely Braced Flanges in Tension")
def tension_flange_resistance(
    f_yt: float,
    f_bu: float | None = None,
    f_l: float = 0.0,
    r_h: float = 1.0,
) -> CheckResult:
    """Tension-flange nominal resistance Fnt = Rh*Fyt (6.10.8.3), checked as
    fbu + fl/3 <= phi_f*Fnt (6.10.8.1.2-1).  ``f_l`` is the flange lateral
    bending stress (ksi)."""
    f_nt = r_h * f_yt  # 6.10.8.3-1
    demand = None if f_bu is None else f_bu + f_l / 3.0
    return CheckResult(
        article="6.10.8.1.2",
        name="Discretely Braced Flanges in Tension",
        capacity=f_nt,
        demand=demand,
        phi=PHI_F,
        details={"fl": f_l},
    )


@article("6.10.1.10.1", "Hybrid Factor Rh")
def hybrid_factor(
    d_n: float,
    t_w: float,
    a_fn: float,
    f_yw: float,
    f_n: float,
) -> CheckResult:
    """Hybrid factor Rh (6.10.1.10.1-1) accounting for early web yielding
    when the web is a lower grade than the flanges:
    Rh = (12 + beta*(3*rho - rho^3)) / (12 + 2*beta), rho = min(Fyw/fn, 1),
    beta = 2*Dn*tw/Afn.

    ``d_n`` is the distance from the elastic NA to the inside of the
    controlling flange (in), ``a_fn`` that flange's area (in^2), ``f_n``
    its yield (or buckling) stress.  Homogeneous girders get Rh = 1.0.
    ``capacity`` holds Rh."""
    rho = min(f_yw / f_n, 1.0)
    beta = 2.0 * d_n * t_w / a_fn
    r_h = (12.0 + beta * (3.0 * rho - rho**3)) / (12.0 + 2.0 * beta)
    return CheckResult(
        article="6.10.1.10.1",
        name="Hybrid Factor Rh",
        capacity=r_h,
        details={"rho": rho, "beta": beta},
    )


@article("6.10.1.10.2", "Web Load-Shedding Factor Rb")
def web_load_shedding_factor(
    d_c: float,
    t_w: float,
    b_fc: float,
    t_fc: float,
    f_yc: float,
) -> CheckResult:
    """Web load-shedding factor Rb (6.10.1.10.2): 1.0 for compact and
    noncompact webs (2*Dc/tw <= lambda_rw = 5.7*sqrt(E/Fyc)); slender webs
    shed stress to the compression flange per -3:
    Rb = 1 - awc/(1200 + 300*awc) * (2*Dc/tw - lambda_rw) <= 1.0.
    ``capacity`` holds Rb."""
    lam_rw = 5.7 * math.sqrt(E_STEEL / f_yc)
    slenderness = 2.0 * d_c / t_w
    a_wc = 2.0 * d_c * t_w / (b_fc * t_fc)
    if slenderness <= lam_rw:
        r_b = 1.0
    else:
        r_b = min(
            1.0 - a_wc / (1200.0 + 300.0 * a_wc) * (slenderness - lam_rw), 1.0
        )
    return CheckResult(
        article="6.10.1.10.2",
        name="Web Load-Shedding Factor Rb",
        capacity=r_b,
        details={"lambda_rw": lam_rw, "2Dc/tw": slenderness, "awc": a_wc,
                 "slender_web": slenderness > lam_rw},
    )


@article("6.10.7.1.2", "Compact Composite Sections in Positive Flexure")
def compact_composite_positive_flexure(
    m_p: float,
    d_p: float,
    d_t: float,
    m_u: float | None = None,
    m_y: float | None = None,
    r_h: float = 1.0,
    continuous_span: bool = False,
) -> CheckResult:
    """Nominal flexural resistance of a compact composite section in
    positive flexure (6.10.7.1.2): Mn = Mp when Dp <= 0.1*Dt, else the
    penalty Mn = Mp*(1.07 - 0.7*Dp/Dt); continuous spans not meeting the
    B6 conditions cap Mn at 1.3*Rh*My.

    ``m_p`` is the plastic moment (kip-in, from a D6.1 PNA analysis),
    ``d_p`` the depth from the top of slab to the PNA, ``d_t`` the total
    composite depth.  The 6.10.7.3 ductility limit Dp <= 0.42*Dt is
    reported in details."""
    if d_p <= 0.1 * d_t:
        m_n = m_p
    else:
        m_n = m_p * (1.07 - 0.7 * d_p / d_t)
    capped = False
    if continuous_span and m_y is not None:
        cap = 1.3 * r_h * m_y
        capped = m_n > cap
        m_n = min(m_n, cap)
    return CheckResult(
        article="6.10.7.1.2",
        name="Compact Composite Sections in Positive Flexure",
        capacity=m_n,
        demand=m_u,
        phi=PHI_F,
        details={"Dp/Dt": d_p / d_t, "ductility_ok": d_p <= 0.42 * d_t,
                 "capped_13RhMy": capped},
    )


@article("6.10.2", "Cross-Section Proportion Limits")
def proportion_limits(
    d_web: float,
    t_w: float,
    b_fc: float,
    t_fc: float,
    b_ft: float,
    t_ft: float,
    i_yc: float | None = None,
    i_yt: float | None = None,
) -> CheckResult:
    """I-girder proportion limits (6.10.2): web D/tw <= 150 (without
    longitudinal stiffeners); each flange bf/2tf <= 12, bf >= D/6,
    tf >= 1.1*tw; and 0.1 <= Iyc/Iyt <= 10 when flange inertias are given.

    Pass/fail only — ``capacity`` is 1.0/0.0 against a ``demand`` of 1.0 so
    ``ok`` reflects all limits; per-limit booleans are in ``details``."""
    checks = {
        "web_slenderness": d_web / t_w <= 150.0,
        "comp_flange_slenderness": b_fc / (2.0 * t_fc) <= 12.0,
        "tens_flange_slenderness": b_ft / (2.0 * t_ft) <= 12.0,
        "comp_flange_width": b_fc >= d_web / 6.0,
        "tens_flange_width": b_ft >= d_web / 6.0,
        "comp_flange_thickness": t_fc >= 1.1 * t_w,
        "tens_flange_thickness": t_ft >= 1.1 * t_w,
    }
    if i_yc is not None and i_yt is not None:
        checks["flange_inertia_ratio"] = 0.1 <= i_yc / i_yt <= 10.0
    all_ok = all(checks.values())
    return CheckResult(
        article="6.10.2",
        name="Cross-Section Proportion Limits",
        capacity=1.0 if all_ok else 0.0,
        demand=1.0,
        details=checks,
    )


# Table 6.6.1.2.5-1 (detail category constant A, x10^8 ksi^3) and
# Table 6.6.1.2.5-3 (constant-amplitude fatigue thresholds, ksi)
FATIGUE_DETAIL_CATEGORIES = {
    "A": (250.0e8, 24.0),
    "B": (120.0e8, 16.0),
    "B'": (61.0e8, 12.0),
    "C": (44.0e8, 10.0),
    "C'": (44.0e8, 12.0),
    "D": (22.0e8, 7.0),
    "E": (11.0e8, 4.5),
    "E'": (3.9e8, 2.6),
}


@article("6.6.1.2.5", "Load-Induced Fatigue Resistance")
def fatigue_resistance(
    category: str,
    delta_f: float | None = None,
    fatigue_i: bool = True,
    adtt_sl: float = 1000.0,
    n_cycles_per_truck: float = 1.0,
    design_life_years: float = 75.0,
) -> CheckResult:
    """Nominal fatigue resistance (6.6.1.2.5): Fatigue I (infinite life)
    uses the constant-amplitude threshold (delta_F)TH; Fatigue II (finite
    life) uses (A/N)^(1/3) with N = 365 * years * n * ADTT_SL.

    ``category`` is the Table 6.6.1.2.3-1 detail category (A through E');
    ``delta_f`` the live-load stress range demand (ksi)."""
    a_const, threshold = FATIGUE_DETAIL_CATEGORIES[category]
    n = 365.0 * design_life_years * n_cycles_per_truck * adtt_sl
    if fatigue_i:
        resistance = threshold
    else:
        resistance = (a_const / n) ** (1.0 / 3.0)
    return CheckResult(
        article="6.6.1.2.5",
        name="Load-Induced Fatigue Resistance",
        capacity=resistance,
        demand=delta_f,
        details={"category": category, "N": n, "A": a_const,
                 "threshold": threshold,
                 "limit_state": "Fatigue I" if fatigue_i else "Fatigue II"},
    )


@article("6.8.2.1", "Tension Member Resistance")
def tension_member_resistance(
    a_g: float,
    f_y: float,
    a_n: float | None = None,
    f_u: float | None = None,
    u_shear_lag: float = 1.0,
    p_u: float | None = None,
) -> CheckResult:
    """Factored tensile resistance (6.8.2.1): lesser of yielding on the
    gross section (phi_y = 0.95) and rupture on the net section
    (phi_u = 0.80, with shear-lag factor U).  ``capacity`` holds the
    governing *factored* resistance (phi already applied — ``phi`` on the
    result is 1.0 to avoid double-counting)."""
    yield_r = 0.95 * f_y * a_g
    cases = {"yield": yield_r}
    if a_n is not None and f_u is not None:
        cases["rupture"] = 0.80 * f_u * a_n * u_shear_lag
    governing = min(cases, key=cases.get)
    return CheckResult(
        article="6.8.2.1",
        name="Tension Member Resistance",
        capacity=cases[governing],
        demand=p_u,
        details={**cases, "governing": governing},
    )


@article("6.9.4.1.1", "Compression Member Nominal Resistance")
def compression_member_resistance(
    a_g: float,
    f_y: float,
    kl_over_r: float,
    p_u: float | None = None,
    q_slender: float = 1.0,
    design_year: int | None = None,
) -> CheckResult:
    """Axial compressive resistance of a non-slender-element column
    (6.9.4.1.1): Pe = pi^2*E/(KL/r)^2 * Ag; Po = Q*Fy*Ag;
    Pn = 0.658^(Po/Pe)*Po when Pe >= 0.44*Po, else 0.877*Pe.

    ``q_slender`` is the slender-element reduction (6.9.4.2; 1.0 for
    nonslender plates).  phi_c is 0.95 (0.90 for designs before the 2015
    interim — pass ``design_year``)."""
    p_o = q_slender * f_y * a_g
    p_e = math.pi**2 * E_STEEL / kl_over_r**2 * a_g
    if p_e >= 0.44 * p_o:
        p_n = 0.658 ** (p_o / p_e) * p_o
        mode = "inelastic"
    else:
        p_n = 0.877 * p_e
        mode = "elastic"
    phi_c = 0.90 if design_year is not None and design_year < 2015 else 0.95
    return CheckResult(
        article="6.9.4.1.1",
        name="Compression Member Nominal Resistance",
        capacity=p_n,
        demand=p_u,
        phi=phi_c,
        details={"Pe": p_e, "Po": p_o, "mode": mode, "KL/r": kl_over_r},
    )


# Table 6.13.2.8-2 minimum bolt pretension Pt (kip)
BOLT_PRETENSION = {
    ("A325", 0.625): 19.0, ("A325", 0.75): 28.0, ("A325", 0.875): 39.0,
    ("A325", 1.0): 51.0, ("A325", 1.125): 56.0, ("A325", 1.25): 71.0,
    ("A490", 0.625): 24.0, ("A490", 0.75): 35.0, ("A490", 0.875): 49.0,
    ("A490", 1.0): 64.0, ("A490", 1.125): 80.0, ("A490", 1.25): 102.0,
}

# Kh (hole size) and Ks (surface class) factors of 6.13.2.8
SLIP_HOLE_FACTORS = {"standard": 1.0, "oversize": 0.85,
                     "long_slot_perp": 0.70, "long_slot_par": 0.60}
SLIP_SURFACE_FACTORS = {"A": 0.33, "B": 0.50, "C": 0.33}


@article("6.13.2.7", "Bolt Shear Resistance")
def bolt_shear_resistance(
    d_bolt: float,
    f_ub: float,
    n_planes: int = 1,
    threads_excluded: bool = True,
    v_u: float | None = None,
    long_joint: bool = False,
    design_year: int | None = None,
) -> CheckResult:
    """Shear resistance of a high-strength bolt (6.13.2.7):
    Rn = C*Ab*Fub*Ns; joints longer than 38 in between extreme bolts take a
    0.83 reduction.  phi_s = 0.80.

    The shear-strength coefficient C was raised in the 8th Edition (2017):
    ``design_year`` >= 2017 uses C = 0.56 (threads excluded) / 0.45 (threads
    included); earlier editions (the default) use 0.48 / 0.38."""
    a_b = math.pi * d_bolt**2 / 4.0
    if design_year is not None and design_year >= 2017:
        factor = 0.56 if threads_excluded else 0.45
    else:
        factor = 0.48 if threads_excluded else 0.38
    r_n = factor * a_b * f_ub * n_planes
    if long_joint:
        r_n *= 0.83
    return CheckResult(
        article="6.13.2.7",
        name="Bolt Shear Resistance",
        capacity=r_n,
        demand=v_u,
        phi=0.80,
        details={"Ab": a_b, "factor": factor, "Ns": n_planes},
    )


@article("6.13.2.8", "Bolt Slip Resistance")
def bolt_slip_resistance(
    bolt_grade: str,
    d_bolt: float,
    n_planes: int = 1,
    hole_type: str = "standard",
    surface_class: str = "B",
    v_serv: float | None = None,
) -> CheckResult:
    """Slip resistance of one bolt in a slip-critical connection
    (6.13.2.8-1): Rn = Kh*Ks*Ns*Pt, checked under Service II (phi = 1.0).
    Pretension Pt from Table 6.13.2.8-2."""
    p_t = BOLT_PRETENSION[(bolt_grade, d_bolt)]
    k_h = SLIP_HOLE_FACTORS[hole_type]
    k_s = SLIP_SURFACE_FACTORS[surface_class]
    r_n = k_h * k_s * n_planes * p_t
    return CheckResult(
        article="6.13.2.8",
        name="Bolt Slip Resistance",
        capacity=r_n,
        demand=v_serv,
        details={"Pt": p_t, "Kh": k_h, "Ks": k_s, "Ns": n_planes},
    )


@article("6.13.2.9", "Bearing Resistance at Bolt Holes")
def bolt_bearing_resistance(
    d_bolt: float,
    t_ply: float,
    f_u_ply: float,
    clear_distance: float,
    v_u: float | None = None,
) -> CheckResult:
    """Bearing on connected material at a bolt hole (6.13.2.9):
    Rn = 2.4*d*t*Fu when the clear distance to the next hole or end is at
    least 2.0*d, else Rn = 1.2*Lc*t*Fu.  phi_bb = 0.80."""
    if clear_distance >= 2.0 * d_bolt:
        r_n = 2.4 * d_bolt * t_ply * f_u_ply
        deformation_governed = True
    else:
        r_n = 1.2 * clear_distance * t_ply * f_u_ply
        deformation_governed = False
    return CheckResult(
        article="6.13.2.9",
        name="Bearing Resistance at Bolt Holes",
        capacity=r_n,
        demand=v_u,
        phi=0.80,
        details={"clear_distance": clear_distance,
                 "full_bearing": deformation_governed},
    )


@article("6.10.10.4", "Shear Connector Strength Limit State")
def shear_connector_strength(
    d_stud: float,
    f_c: float,
    e_c: float,
    nominal_force: float | None = None,
    f_u_stud: float = 60.0,
) -> CheckResult:
    """Nominal resistance of one stud shear connector (6.10.10.4.3-1):
    Qn = 0.5*Asc*sqrt(f'c*Ec) <= Asc*Fu, phi_sc = 0.85.

    Pass the interface force ``nominal_force`` P (6.10.10.4.2 — the lesser
    of the deck crushing and steel yielding forces, kip) to get the
    required connector count in ``details``."""
    a_sc = math.pi * d_stud**2 / 4.0
    q_n = min(0.5 * a_sc * math.sqrt(f_c * e_c), a_sc * f_u_stud)
    details = {"Asc": a_sc, "Qn": q_n}
    if nominal_force is not None:
        details["n_required"] = nominal_force / (0.85 * q_n)
    return CheckResult(
        article="6.10.10.4",
        name="Shear Connector Strength Limit State",
        capacity=q_n,
        phi=0.85,
        details=details,
    )


@article("6.10.10.1.2", "Shear Connector Fatigue Pitch")
def shear_connector_fatigue_pitch(
    d_stud: float,
    n_per_row: int,
    shear_flow: float,
    n_cycles: float | None = None,
    pitch: float | None = None,
) -> CheckResult:
    """Required stud pitch for fatigue (6.10.10.1.2): p <= n*Zr/Vsr, where
    the fatigue resistance of one stud is Zr = alpha*d^2 with
    alpha = 34.5 - 4.28*log10(N) (Fatigue II), or Zr = 5.5*d^2/2 for
    infinite life (Fatigue I, ``n_cycles`` omitted).

    ``shear_flow`` is the fatigue shear flow Vsr = Vf*Q/I (kip/in).
    ``capacity`` is the maximum permitted pitch (in); pass the actual
    ``pitch`` as demand — note larger-is-worse, so ok means pitch <= max."""
    if n_cycles is None:
        z_r = 5.5 * d_stud**2 / 2.0
    else:
        alpha = 34.5 - 4.28 * math.log10(n_cycles)
        z_r = max(alpha * d_stud**2, 5.5 * d_stud**2 / 2.0)
    p_max = n_per_row * z_r / shear_flow
    return CheckResult(
        article="6.10.10.1.2",
        name="Shear Connector Fatigue Pitch",
        capacity=p_max,
        demand=pitch,
        details={"Zr": z_r, "shear_flow": shear_flow},
    )


@article("6.13.4", "Block Shear Rupture Resistance")
def block_shear_resistance(
    a_vg: float,
    a_vn: float,
    a_tn: float,
    f_y: float,
    f_u: float,
    p_u: float | None = None,
    u_bs: float = 1.0,
    punched_holes: bool = False,
) -> CheckResult:
    """Block shear rupture (6.13.4-1):
    Rn = Rp*(0.58*Fu*Avn + Ubs*Fu*Atn), not to exceed
    Rp*(0.58*Fy*Avg + Ubs*Fu*Atn); phi_bs = 0.80.

    ``u_bs`` = 1.0 for uniform tension stress, 0.5 for nonuniform;
    Rp = 0.9 for punched holes, 1.0 drilled."""
    r_p = 0.9 if punched_holes else 1.0
    r_n = r_p * min(
        0.58 * f_u * a_vn + u_bs * f_u * a_tn,
        0.58 * f_y * a_vg + u_bs * f_u * a_tn,
    )
    return CheckResult(
        article="6.13.4",
        name="Block Shear Rupture Resistance",
        capacity=r_n,
        demand=p_u,
        phi=0.80,
        details={"Rp": r_p, "Ubs": u_bs},
    )


@article("6.13.3.2.4", "Fillet Weld Shear Resistance")
def fillet_weld_resistance(
    leg_size: float,
    f_exx: float = 70.0,
    length: float = 1.0,
    v_u: float | None = None,
) -> CheckResult:
    """Factored shear resistance of a fillet weld on its effective throat
    (6.13.3.2.4b): Rr = 0.6*phi_e2*Fexx with phi_e2 = 0.80, applied to the
    throat 0.707*leg.  ``capacity`` holds the factored resistance for the
    given ``length`` of weld (kip), so ``phi`` is 1.0 on the result."""
    throat = 0.707 * leg_size
    r_r = 0.6 * 0.80 * f_exx * throat * length
    return CheckResult(
        article="6.13.3.2.4",
        name="Fillet Weld Shear Resistance",
        capacity=r_r,
        demand=v_u,
        details={"throat": throat, "per_inch": 0.6 * 0.80 * f_exx * throat},
    )


@article("6.10.1.9.1", "Web Bend-Buckling Resistance")
def web_bend_buckling(
    d_web: float,
    t_w: float,
    d_c: float,
    f_yc: float,
    f_yw: float,
    r_h: float = 1.0,
) -> CheckResult:
    """Nominal web bend-buckling resistance (6.10.1.9.1-1):
    Fcrw = 0.9*E*k/(D/tw)^2 with k = 9/(Dc/D)^2, capped at
    min(Rh*Fyc, Fyw/0.7).  ``capacity`` holds Fcrw (ksi)."""
    k = 9.0 / (d_c / d_web) ** 2
    f_crw = min(
        0.9 * E_STEEL * k / (d_web / t_w) ** 2,
        r_h * f_yc,
        f_yw / 0.7,
    )
    return CheckResult(
        article="6.10.1.9.1",
        name="Web Bend-Buckling Resistance",
        capacity=f_crw,
        details={"k": k, "D/tw": d_web / t_w},
    )


@article("6.10.3.2.1", "Constructibility — Discretely Braced Compression Flange")
def constructibility_compression_flange(
    f_bu: float,
    f_l: float,
    f_yc: float,
    f_nc: float,
    f_crw: float | None = None,
    r_h: float = 1.0,
    slender_web: bool = False,
) -> CheckResult:
    """Constructibility checks on a discretely braced compression flange
    during deck placement (6.10.3.2.1): flange yielding
    fbu + fl <= phi*Rh*Fyc (skipped for slender webs), flange buckling
    fbu + fl/3 <= phi*Fnc, and web bend-buckling fbu <= phi*Fcrw.

    ``f_bu``/``f_l`` are the factored vertical-bending and lateral-bending
    flange stresses under the steel-plus-wet-concrete condition; ``f_nc``
    from the 6.10.8.2 functions and ``f_crw`` from
    :func:`web_bend_buckling`.  ``capacity``/``demand`` carry the governing
    case; all three appear in ``details``."""
    cases = {}
    if not slender_web:
        cases["yielding"] = (PHI_F * r_h * f_yc, f_bu + f_l)
    cases["buckling"] = (PHI_F * f_nc, f_bu + f_l / 3.0)
    if f_crw is not None:
        cases["web_bend_buckling"] = (PHI_F * f_crw, f_bu)
    governing = min(
        cases, key=lambda c: cases[c][0] / cases[c][1] if cases[c][1] else 1e9
    )
    cap, dem = cases[governing]
    return CheckResult(
        article="6.10.3.2.1",
        name="Constructibility — Discretely Braced Compression Flange",
        capacity=cap,
        demand=dem,
        phi=1.0,  # phi folded into each case above
        details={**{k: {"capacity": v[0], "demand": v[1]}
                    for k, v in cases.items()},
                 "governing": governing},
    )


@article("6.10.11.2.3", "Bearing Stiffener Bearing Resistance")
def bearing_stiffener_resistance(
    a_pn: float,
    f_ys: float,
    r_u: float | None = None,
) -> CheckResult:
    """Bearing resistance of fitted bearing-stiffener ends
    (6.10.11.2.3-1): Rn = 1.4*Apn*Fys with phi_b = 1.0.

    ``a_pn`` is the stiffener area in contact with the flange after the
    clip for the web-to-flange weld (in^2).  The companion axial check of
    the stiffener-plus-web effective column (6.10.11.2.4) composes with
    :func:`compression_member_resistance` using KL = 0.75*D and the
    effective-section properties."""
    r_n = 1.4 * a_pn * f_ys
    return CheckResult(
        article="6.10.11.2.3",
        name="Bearing Stiffener Bearing Resistance",
        capacity=r_n,
        demand=r_u,
        phi=1.0,
        details={"Apn": a_pn},
    )


@article("6.10.9", "Web Shear Resistance")
def web_shear_resistance(
    d_web: float,
    t_w: float,
    f_yw: float,
    v_u: float | None = None,
    d_o: float | None = None,
    tension_field: bool = False,
    b_fc: float | None = None,
    t_fc: float | None = None,
    b_ft: float | None = None,
    t_ft: float | None = None,
) -> CheckResult:
    """Nominal web shear resistance Vn (6.10.9).

    Unstiffened webs (``d_o`` is None): Vn = C*Vp (6.10.9.2-1).  Stiffened
    interior panels with ``tension_field=True`` use 6.10.9.3.2-2, downgraded
    to 6.10.9.3.2-8 when the panel fails the flange-proportion limit
    2*D*tw/(bfc*tfc + bft*tft) <= 2.5.  ``d_web`` is the web depth D (in),
    ``d_o`` the transverse stiffener spacing (in), ``v_u`` the factored
    shear demand (kip).
    """
    v_p = 0.58 * f_yw * d_web * t_w  # plastic shear force (6.10.9.2-2)
    k = 5.0 if d_o is None else 5.0 + 5.0 / (d_o / d_web) ** 2  # 6.10.9.3.2-7

    slenderness = d_web / t_w
    ek_fyw = math.sqrt(E_STEEL * k / f_yw)
    if slenderness <= 1.12 * ek_fyw:
        c = 1.0  # 6.10.9.3.2-4
    elif slenderness <= 1.40 * ek_fyw:
        c = 1.12 / slenderness * ek_fyw  # 6.10.9.3.2-5
    else:
        c = 1.57 / slenderness**2 * (E_STEEL * k / f_yw)  # 6.10.9.3.2-6

    details = {"Vp": v_p, "C": c, "k": k}
    if d_o is not None and tension_field:
        if None in (b_fc, t_fc, b_ft, t_ft):
            raise ValueError(
                "tension_field=True requires flange dimensions "
                "b_fc, t_fc, b_ft, t_ft for the 6.10.9.3.2 proportion check"
            )
        post_buckling = 0.87 * (1.0 - c)
        if 2.0 * d_web * t_w / (b_fc * t_fc + b_ft * t_ft) <= 2.5:
            v_n = v_p * (c + post_buckling / math.sqrt(1.0 + (d_o / d_web) ** 2))
            details["equation"] = "6.10.9.3.2-2"
        else:
            v_n = v_p * (
                c
                + post_buckling
                / (math.sqrt(1.0 + (d_o / d_web) ** 2) + d_o / d_web)
            )
            details["equation"] = "6.10.9.3.2-8"
    else:
        v_n = c * v_p
        details["equation"] = "6.10.9.2-1" if d_o is None else "6.10.9.3.2-1"

    return CheckResult(
        article="6.10.9",
        name="Web Shear Resistance",
        capacity=v_n,
        demand=v_u,
        phi=PHI_V,
        details=details,
    )
