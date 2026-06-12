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

"""AASHTO LRFD Chapter 5 — prestressed concrete design checks.

Article numbers follow the 8th Edition renumbering (5.6.3.1 strand stress,
5.9.2.3 stress limits, 5.9.3 losses; pre-8th these were 5.7.3.1, 5.9.4, and
5.9.5 respectively).  Units: kip, inch, ksi.  Stress sign convention for the
limit checks: pass magnitudes — compression checks take compressive stress
as positive, tension checks take tensile stress as positive.
"""

import math

from civilpy.structural.aashto.lrfd.core import CheckResult, article
from civilpy.structural.aashto.lrfd.concrete import beta1

E_STRAND = 28500.0  # ksi, prestressing strand (5.4.4.2)

# k factor (5.6.3.1.1) by strand type: k = 2*(1.04 - fpy/fpu)
K_LOW_RELAXATION = 0.28  # fpy/fpu = 0.90
K_STRESS_RELIEVED = 0.38  # fpy/fpu = 0.85


def phi_flexure_ps(eps_t: float, eps_cl: float = 0.002, eps_tl: float = 0.005) -> float:
    """Resistance factor for prestressed flexure from net tensile strain
    (5.5.4.2): 0.75 compression-controlled up to 1.0 tension-controlled."""
    return min(max(0.75 + 0.25 * (eps_t - eps_cl) / (eps_tl - eps_cl), 0.75), 1.0)


@article("5.6.3.1.1", "Stress in Bonded Strands at Nominal Flexural Resistance")
def ps_strand_stress_at_nominal(
    a_ps: float,
    f_pu: float,
    d_p: float,
    f_c: float,
    b: float,
    b_w: float | None = None,
    h_f: float = 0.0,
    a_s: float = 0.0,
    f_y: float = 60.0,
    d_s: float = 0.0,
    a_s_prime: float = 0.0,
    f_y_prime: float | None = None,
    k: float = K_LOW_RELAXATION,
) -> CheckResult:
    """Average stress fps in bonded prestressing strands when the section
    reaches its nominal flexural resistance (5.6.3.1.1), with the neutral
    axis found for rectangular or flanged behavior.

    ``capacity`` holds fps (ksi).  ``a_ps`` is strand area (in^2) at depth
    ``d_p``; ``b`` is the compression-face width, ``b_w``/``h_f`` the web
    width and flange thickness for T-shaped behavior; mild steel ``a_s`` /
    ``a_s_prime`` may be included.  ``k`` is 0.28 for low-relaxation strand,
    0.38 for stress-relieved.
    """
    b1 = beta1(f_c)
    f_yp = f_y if f_y_prime is None else f_y_prime
    tension = a_ps * f_pu + a_s * f_y - a_s_prime * f_yp

    # Rectangular behavior first (5.6.3.1.1 with flange width b)
    c = tension / (0.85 * f_c * b1 * b + k * a_ps * f_pu / d_p)
    behavior = "rectangular"
    if b_w is not None and c > h_f:
        # Neutral axis below the flange — flanged behavior with web width bw
        c = (tension - 0.85 * f_c * (b - b_w) * h_f) / (
            0.85 * f_c * b1 * b_w + k * a_ps * f_pu / d_p
        )
        behavior = "flanged"

    f_ps = f_pu * (1.0 - k * c / d_p)
    return CheckResult(
        article="5.6.3.1.1",
        name="Stress in Bonded Strands at Nominal Flexural Resistance",
        capacity=f_ps,
        details={"c": c, "k": k, "beta1": b1, "behavior": behavior},
    )


@article("5.6.3.2.2", "Flexural Resistance (Prestressed Concrete)")
def ps_flexural_resistance(
    a_ps: float,
    f_pu: float,
    d_p: float,
    f_c: float,
    b: float,
    m_u: float | None = None,
    b_w: float | None = None,
    h_f: float = 0.0,
    a_s: float = 0.0,
    f_y: float = 60.0,
    d_s: float = 0.0,
    a_s_prime: float = 0.0,
    d_s_prime: float = 0.0,
    f_y_prime: float | None = None,
    k: float = K_LOW_RELAXATION,
    d_t: float | None = None,
) -> CheckResult:
    """Nominal flexural resistance Mn of a bonded prestressed section
    (5.6.3.2.2 flanged / 5.6.3.2.3 rectangular), kip-in.

    Strand stress comes from :func:`ps_strand_stress_at_nominal`; phi varies
    with net tensile strain per 5.5.4.2 (1.0 when tension-controlled).
    ``d_t`` is the depth to the extreme tension steel for the strain check
    (defaults to ``d_p``).
    """
    strand = ps_strand_stress_at_nominal(
        a_ps=a_ps, f_pu=f_pu, d_p=d_p, f_c=f_c, b=b, b_w=b_w, h_f=h_f,
        a_s=a_s, f_y=f_y, d_s=d_s, a_s_prime=a_s_prime,
        f_y_prime=f_y_prime, k=k,
    )
    c = strand.details["c"]
    b1 = strand.details["beta1"]
    f_ps = strand.capacity
    f_yp = f_y if f_y_prime is None else f_y_prime
    a = b1 * c

    m_n = a_ps * f_ps * (d_p - a / 2.0)
    if a_s:
        m_n += a_s * f_y * (d_s - a / 2.0)
    if a_s_prime:
        m_n -= a_s_prime * f_yp * (d_s_prime - a / 2.0)
    if strand.details["behavior"] == "flanged":
        m_n += 0.85 * f_c * (b - b_w) * h_f * (a / 2.0 - h_f / 2.0)

    depth_t = d_p if d_t is None else d_t
    eps_t = 0.003 * (depth_t - c) / c
    phi = phi_flexure_ps(eps_t)

    return CheckResult(
        article="5.6.3.2.2",
        name="Flexural Resistance (Prestressed Concrete)",
        capacity=m_n,
        demand=m_u,
        phi=phi,
        details={
            "fps": f_ps,
            "c": c,
            "a": a,
            "beta1": b1,
            "eps_t": eps_t,
            "tension_controlled": eps_t >= 0.005,
            "behavior": strand.details["behavior"],
        },
    )


@article("5.9.2.3.1a", "Compression Stress Limit at Transfer")
def ps_transfer_compression_check(
    f_ci: float,
    stress: float | None = None,
    design_year: int | None = None,
) -> CheckResult:
    """Compressive stress limit at transfer (5.9.2.3.1a): 0.65*f'ci, or
    0.60*f'ci for designs before the 2016 interim revisions (pass
    ``design_year`` for historical designs).  ``stress`` is the computed
    compressive stress magnitude (ksi, positive)."""
    factor = 0.60 if design_year is not None and design_year < 2016 else 0.65
    limit = factor * f_ci
    return CheckResult(
        article="5.9.2.3.1a",
        name="Compression Stress Limit at Transfer",
        capacity=limit,
        demand=stress,
        details={"f_ci": f_ci, "factor": factor},
    )


@article("5.9.2.3.1b", "Tension Stress Limit at Transfer")
def ps_transfer_tension_check(
    f_ci: float,
    stress: float | None = None,
    bonded_reinforcement: bool = False,
    lam: float = 1.0,
) -> CheckResult:
    """Tensile stress limit at transfer (5.9.2.3.1b): 0.0948*lam*sqrt(f'ci)
    capped at 0.2 ksi without bonded reinforcement sized for the tensile
    force, or 0.24*lam*sqrt(f'ci) with it.  ``stress`` is tensile stress
    magnitude (ksi, positive)."""
    if bonded_reinforcement:
        limit = 0.24 * lam * math.sqrt(f_ci)
    else:
        limit = min(0.0948 * lam * math.sqrt(f_ci), 0.2)
    return CheckResult(
        article="5.9.2.3.1b",
        name="Tension Stress Limit at Transfer",
        capacity=limit,
        demand=stress,
        details={"f_ci": f_ci, "bonded_reinforcement": bonded_reinforcement},
    )


@article("5.9.2.3.2a", "Compression Stress Limit at Service")
def ps_service_compression_check(
    f_c: float,
    stress_permanent: float | None = None,
    stress_total: float | None = None,
    phi_w: float = 1.0,
) -> CheckResult:
    """Service-level compressive stress limits after losses (5.9.2.3.2a):
    0.45*f'c under effective prestress plus permanent loads, and
    0.60*phi_w*f'c under the full Service I combination (``phi_w`` is the
    slenderness reduction for thin-walled sections; 1.0 for solid beams).

    The governing case (lowest margin) populates capacity/demand; both are
    reported in ``details``.
    """
    limit_perm = 0.45 * f_c
    limit_total = 0.60 * phi_w * f_c
    cases = []
    if stress_permanent is not None:
        cases.append((limit_perm, stress_permanent, "permanent"))
    if stress_total is not None:
        cases.append((limit_total, stress_total, "total"))
    if cases:
        capacity, demand, governing = min(
            cases, key=lambda t: float("inf") if t[1] == 0 else t[0] / t[1]
        )
    else:
        capacity, demand, governing = limit_total, None, "total"
    return CheckResult(
        article="5.9.2.3.2a",
        name="Compression Stress Limit at Service",
        capacity=capacity,
        demand=demand,
        details={
            "limit_permanent": limit_perm,
            "limit_total": limit_total,
            "governing": governing,
            "phi_w": phi_w,
        },
    )


@article("5.9.2.3.2b", "Tension Stress Limit at Service")
def ps_service_tension_check(
    f_c: float,
    stress: float | None = None,
    severe_corrosion: bool = False,
    lam: float = 1.0,
) -> CheckResult:
    """Service III tensile stress limit after losses for components with
    bonded tendons (5.9.2.3.2b): 0.19*lam*sqrt(f'c) <= 0.6 ksi, halved in
    effect for severe corrosion conditions (0.0948*lam*sqrt(f'c) <= 0.3
    ksi).  ``stress`` is tensile stress magnitude (ksi, positive)."""
    if severe_corrosion:
        limit = min(0.0948 * lam * math.sqrt(f_c), 0.3)
    else:
        limit = min(0.19 * lam * math.sqrt(f_c), 0.6)
    return CheckResult(
        article="5.9.2.3.2b",
        name="Tension Stress Limit at Service",
        capacity=limit,
        demand=stress,
        details={"severe_corrosion": severe_corrosion},
    )


@article("5.9.3.2.3a", "Elastic Shortening Loss")
def ps_elastic_shortening_loss(
    f_cgp: float,
    e_ct: float,
    e_p: float = E_STRAND,
) -> CheckResult:
    """Prestress loss from elastic shortening in pretensioned members
    (5.9.3.2.3a): the strand sheds stress in proportion to the modular
    ratio times the concrete stress at the strand centroid at transfer.

    ``capacity`` holds the loss (ksi).  ``f_cgp`` is the concrete stress at
    the centroid of the prestressing at transfer (ksi); ``e_ct`` the
    concrete modulus at transfer (ksi).
    """
    loss = e_p / e_ct * f_cgp
    return CheckResult(
        article="5.9.3.2.3a",
        name="Elastic Shortening Loss",
        capacity=loss,
        details={"f_cgp": f_cgp, "modular_ratio": e_p / e_ct},
    )


def ps_section_age_adjustment(
    a_ps: float,
    a_g: float,
    i_g: float,
    e_pg: float,
    psi_final: float,
    e_ci: float,
    e_p: float = E_STRAND,
) -> float:
    """Transformed-section/age-adjusted coefficient Kid (5.9.3.4.2a-2) — or
    Kdf with composite-section properties (5.9.3.4.3a-2).

    ``e_pg`` is the strand eccentricity from the section centroid (in),
    ``psi_final`` the creep coefficient psi(tf, ti), ``e_ci`` the concrete
    modulus at transfer (ksi).
    """
    return 1.0 / (
        1.0
        + e_p / e_ci
        * a_ps / a_g
        * (1.0 + a_g * e_pg**2 / i_g)
        * (1.0 + 0.7 * psi_final)
    )


@article("5.9.3.4.2a", "Refined Loss — Girder Shrinkage, Transfer to Deck")
def ps_refined_loss_shrinkage_girder(
    eps_bid: float,
    k_id: float,
    e_p: float = E_STRAND,
) -> CheckResult:
    """Prestress loss from girder shrinkage between transfer and deck
    placement (5.9.3.4.2a-1): eps_bid * Ep * Kid.

    ``eps_bid`` is the girder shrinkage strain over that interval (from
    :func:`~civilpy.structural.aashto.lrfd.creep_shrinkage.shrinkage_strain`),
    ``k_id`` from :func:`ps_section_age_adjustment`.  ``capacity`` holds the
    loss (ksi).
    """
    loss = eps_bid * e_p * k_id
    return CheckResult(
        article="5.9.3.4.2a",
        name="Refined Loss — Girder Shrinkage, Transfer to Deck",
        capacity=loss,
        details={"eps_bid": eps_bid, "Kid": k_id},
    )


@article("5.9.3.4.2b", "Refined Loss — Girder Creep, Transfer to Deck")
def ps_refined_loss_creep_girder(
    f_cgp: float,
    psi_td_ti: float,
    k_id: float,
    e_ci: float,
    e_p: float = E_STRAND,
) -> CheckResult:
    """Prestress loss from girder creep between transfer and deck placement
    (5.9.3.4.2b-1): (Ep/Eci) * fcgp * psi(td, ti) * Kid."""
    loss = e_p / e_ci * f_cgp * psi_td_ti * k_id
    return CheckResult(
        article="5.9.3.4.2b",
        name="Refined Loss — Girder Creep, Transfer to Deck",
        capacity=loss,
        details={"f_cgp": f_cgp, "psi_td_ti": psi_td_ti, "Kid": k_id},
    )


@article("5.9.3.4.2c", "Refined Loss — Strand Relaxation")
def ps_refined_loss_relaxation(
    f_pt: float,
    f_py: float,
    k_l: float = 30.0,
) -> CheckResult:
    """Strand relaxation loss per stage (5.9.3.4.2c-1):
    (fpt/KL) * (fpt/fpy - 0.55), taken as zero if fpt/fpy < 0.55.

    ``f_pt`` is the strand stress immediately after transfer (ksi);
    ``k_l`` = 30 for low-relaxation strand, 7 for stress-relieved.  The same
    value applies again for the deck-to-final stage (5.9.3.4.3c).
    """
    loss = max(f_pt / k_l * (f_pt / f_py - 0.55), 0.0)
    return CheckResult(
        article="5.9.3.4.2c",
        name="Refined Loss — Strand Relaxation",
        capacity=loss,
        details={"f_pt": f_pt, "f_py": f_py, "KL": k_l},
    )


@article("5.9.3.4.3a", "Refined Loss — Girder Shrinkage, Deck to Final")
def ps_refined_loss_shrinkage_deck_stage(
    eps_bdf: float,
    k_df: float,
    e_p: float = E_STRAND,
) -> CheckResult:
    """Prestress loss from girder shrinkage between deck placement and
    final time (5.9.3.4.3a-1): eps_bdf * Ep * Kdf, with Kdf computed on
    the composite section."""
    loss = eps_bdf * e_p * k_df
    return CheckResult(
        article="5.9.3.4.3a",
        name="Refined Loss — Girder Shrinkage, Deck to Final",
        capacity=loss,
        details={"eps_bdf": eps_bdf, "Kdf": k_df},
    )


@article("5.9.3.4.3b", "Refined Loss — Girder Creep, Deck to Final")
def ps_refined_loss_creep_deck_stage(
    f_cgp: float,
    psi_tf_ti: float,
    psi_td_ti: float,
    psi_tf_td: float,
    delta_f_cd: float,
    k_df: float,
    e_ci: float,
    e_c: float,
    e_p: float = E_STRAND,
) -> CheckResult:
    """Prestress loss from girder creep between deck placement and final
    time (5.9.3.4.3b-1):

    (Ep/Eci)*fcgp*(psi(tf,ti) - psi(td,ti))*Kdf
        + (Ep/Ec)*delta_fcd*psi(tf,td)*Kdf,  taken >= 0.

    ``delta_f_cd`` is the change in concrete stress at the strand centroid
    from deck weight and superimposed loads (ksi, negative when it relieves
    compression).
    """
    loss = (
        e_p / e_ci * f_cgp * (psi_tf_ti - psi_td_ti) * k_df
        + e_p / e_c * delta_f_cd * psi_tf_td * k_df
    )
    loss = max(loss, 0.0)
    return CheckResult(
        article="5.9.3.4.3b",
        name="Refined Loss — Girder Creep, Deck to Final",
        capacity=loss,
        details={"psi_tf_ti": psi_tf_ti, "psi_td_ti": psi_td_ti,
                 "psi_tf_td": psi_tf_td, "delta_f_cd": delta_f_cd,
                 "Kdf": k_df},
    )


@article("5.9.3.4.3d", "Prestress Gain — Deck Shrinkage")
def ps_deck_shrinkage_gain(
    delta_f_cdf: float,
    k_df: float,
    psi_tf_td: float,
    e_c: float,
    e_p: float = E_STRAND,
) -> CheckResult:
    """Prestress *gain* from deck shrinkage (5.9.3.4.3d-1):
    (Ep/Ec) * delta_fcdf * Kdf * (1 + 0.7*psi(tf, td)).

    ``delta_f_cdf`` is the change in concrete stress at the strand centroid
    caused by deck shrinkage (ksi, compressive positive — the deck shrinks,
    cambering the girder and compressing the bottom flange).  ``capacity``
    holds the gain; subtract it from the total loss.
    """
    gain = e_p / e_c * delta_f_cdf * k_df * (1.0 + 0.7 * psi_tf_td)
    return CheckResult(
        article="5.9.3.4.3d",
        name="Prestress Gain — Deck Shrinkage",
        capacity=gain,
        details={"delta_f_cdf": delta_f_cdf, "Kdf": k_df,
                 "psi_tf_td": psi_tf_td},
    )


@article("5.9.3.2.2", "Friction Loss (Post-Tensioning)")
def ps_friction_loss(
    f_pj: float,
    x: float,
    alpha: float,
    mu: float = 0.25,
    k: float = 0.0002,
) -> CheckResult:
    """Friction loss in a post-tensioned tendon (5.9.3.2.2b-1):
    fpj * (1 - e^(-(K*x + mu*alpha))).

    ``x`` is the tendon length from the jacking end (ft), ``alpha`` the sum
    of angular changes (radians), ``mu`` the curvature friction coefficient
    and ``k`` the wobble coefficient (per ft) — defaults are typical of
    strand in rigid galvanized ducts; use the duct manufacturer's values
    when known.
    """
    loss = f_pj * (1.0 - math.exp(-(k * x + mu * alpha)))
    return CheckResult(
        article="5.9.3.2.2",
        name="Friction Loss (Post-Tensioning)",
        capacity=loss,
        details={"mu": mu, "K": k, "x": x, "alpha": alpha},
    )


@article("5.9.4.3.2", "Pretensioned Strand Development Length")
def ps_strand_development(
    f_ps: float,
    f_pe: float,
    d_b: float,
    kappa: float = 1.6,
    embedment: float | None = None,
) -> CheckResult:
    """Development length of bonded pretensioned strand (5.9.4.3.2-1):
    ld >= kappa * (fps - 2/3*fpe) * db, with transfer length 60*db.

    ``kappa`` = 1.6 for members deeper than 24 in, 1.0 otherwise.
    ``capacity`` holds the required ld (in); pass the available
    ``embedment`` as the demand side — note this check is inverted
    (embedment must *exceed* ld), so ``ok`` is computed accordingly.
    """
    l_d = kappa * (f_ps - 2.0 / 3.0 * f_pe) * d_b
    result = CheckResult(
        article="5.9.4.3.2",
        name="Pretensioned Strand Development Length",
        capacity=embedment if embedment is not None else l_d,
        demand=l_d if embedment is not None else None,
        details={"ld_required": l_d, "transfer_length": 60.0 * d_b,
                 "kappa": kappa},
    )
    return result


@article("5.9.4.4.1", "Splitting Resistance at Member Ends")
def ps_splitting_resistance(
    a_s_end: float,
    p_r_demand: float | None = None,
    f_s: float = 20.0,
) -> CheckResult:
    """Splitting (bursting) resistance at pretensioned member ends
    (5.9.4.4.1-1): Pr = fs * As, where As is the reinforcement within h/4
    of the end and fs is limited to 20 ksi.  Pr must resist at least 4% of
    the total prestress force at transfer — pass 0.04*Ppt as the demand."""
    p_r = min(f_s, 20.0) * a_s_end
    return CheckResult(
        article="5.9.4.4.1",
        name="Splitting Resistance at Member Ends",
        capacity=p_r,
        demand=p_r_demand,
        details={"fs": min(f_s, 20.0), "As_end": a_s_end},
    )


@article("5.9.3.3", "Approximate Estimate of Time-Dependent Losses")
def ps_approximate_longterm_loss(
    f_pi: float,
    a_ps: float,
    a_g: float,
    f_ci: float,
    humidity_pct: float = 70.0,
    delta_f_pr: float = 2.4,
) -> CheckResult:
    """Lump-sum long-term loss for standard precast pretensioned members
    (5.9.3.3): creep + shrinkage + relaxation combined.

    ``capacity`` holds the total loss (ksi).  ``f_pi`` is the strand stress
    immediately prior to transfer (ksi), ``a_g`` the gross section area
    (in^2), ``humidity_pct`` the average annual ambient relative humidity,
    ``delta_f_pr`` the relaxation estimate (2.4 ksi low-relaxation strand).
    """
    gamma_h = 1.7 - 0.01 * humidity_pct
    gamma_st = 5.0 / (1.0 + f_ci)
    creep_term = 10.0 * f_pi * a_ps / a_g * gamma_h * gamma_st
    shrinkage_term = 12.0 * gamma_h * gamma_st
    loss = creep_term + shrinkage_term + delta_f_pr
    return CheckResult(
        article="5.9.3.3",
        name="Approximate Estimate of Time-Dependent Losses",
        capacity=loss,
        details={
            "gamma_h": gamma_h,
            "gamma_st": gamma_st,
            "creep_term": creep_term,
            "shrinkage_term": shrinkage_term,
            "relaxation": delta_f_pr,
        },
    )
