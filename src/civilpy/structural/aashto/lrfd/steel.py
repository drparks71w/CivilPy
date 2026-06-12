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
Edition for these checks, per the edition-inheritance chains in BrR's spec
engine).  Units: kip, inch, ksi.
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
