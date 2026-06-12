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

"""Notebook plotting helpers for the LRFD check results.

The check functions themselves stay pure (no matplotlib import on the
calculation path); these helpers render their outputs following the
package-wide convention (optional ``ax``, figure returned).
"""

import matplotlib.pyplot as plt


def plot_pm_interaction(points, ax=None, p_u: float | None = None,
                        m_u: float | None = None, units: str = "kip, kip-in"):
    """Plot a column interaction diagram from
    :func:`~civilpy.structural.aashto.lrfd.columns.rc_pm_interaction_diagram`
    output: the nominal curve dashed, the factored (phi-reduced) curve
    solid, and optionally the factored demand point (Pu, Mu).  Returns the
    figure."""
    if ax is None:
        ax = plt.figure(figsize=(6, 7)).add_subplot(1, 1, 1)
    ax.plot([pt.m_n for pt in points], [pt.p_n for pt in points],
            "b--", lw=1.2, label=r"nominal $(M_n, P_n)$")
    ax.plot([pt.phi_mn for pt in points], [pt.phi_pn for pt in points],
            "b-", lw=1.8, label=r"factored $(\phi M_n, \phi P_n)$")
    if p_u is not None and m_u is not None:
        ax.plot(m_u, p_u, "r*", markersize=14, label=r"$(M_u, P_u)$")
    ax.axhline(0.0, color="k", lw=0.8)
    ax.set_xlabel(f"Moment ({units.split(',')[-1].strip()})")
    ax.set_ylabel(f"Axial ({units.split(',')[0].strip()})")
    ax.set_title("Column P-M Interaction Diagram")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)
    return ax.get_figure()


def plot_mn_vs_lb(b_fc, t_fc, d_c, t_w, f_yc, f_yw, *, c_b: float = 1.0,
                  r_b: float = 1.0, r_h: float = 1.0,
                  s_xc: float | None = None, l_b: float | None = None,
                  f_bu: float | None = None, l_b_max: float | None = None,
                  show_flb: bool = True, ax=None):
    """Capacity-vs-unbraced-length chart: loop the 6.10.8.2.3 LTB check
    over Lb and draw the classic three-regime curve with the Lp/Lr
    anchor points.

    Inputs match
    :func:`~civilpy.structural.aashto.lrfd.steel.lateral_torsional_buckling_resistance`
    (inches and ksi).  The y-axis is flange stress Fnc (ksi) unless
    ``s_xc`` (in^3) is given, which converts to moment Mn = Fnc*Sxc in
    kip-ft.  ``show_flb`` overlays the 6.10.8.2.2 flange local buckling
    cap so the governing envelope is visible; an optional demand point
    (``l_b``, ``f_bu``) is starred.  Lengths plot in feet.  Returns the
    figure.
    """
    from civilpy.structural.aashto.lrfd.steel import (
        flange_local_buckling_resistance,
        lateral_torsional_buckling_resistance,
    )

    def ltb(lb_in):
        return lateral_torsional_buckling_resistance(
            lb_in, b_fc, t_fc, d_c, t_w, f_yc, f_yw,
            c_b=c_b, r_b=r_b, r_h=r_h)

    probe = ltb(1.0)
    l_p, l_r = probe.details["Lp"], probe.details["Lr"]
    lb_max = l_b_max or max(1.6 * l_r, (l_b or 0.0) * 1.1)
    lbs = [lb_max * i / 400.0 for i in range(1, 401)]

    def scale(f_ksi):
        return f_ksi * s_xc / 12.0 if s_xc else f_ksi

    if ax is None:
        ax = plt.figure(figsize=(8, 5)).add_subplot(1, 1, 1)
    ax.plot([lb / 12.0 for lb in lbs], [scale(ltb(lb).capacity) for lb in lbs],
            "b-", lw=2.0, label="LTB (6.10.8.2.3)")
    if show_flb:
        f_flb = flange_local_buckling_resistance(
            b_fc, t_fc, f_yc, f_yw, r_b=r_b, r_h=r_h).capacity
        ax.axhline(scale(f_flb), color="tab:orange", ls=":", lw=1.6,
                   label="FLB cap (6.10.8.2.2)")
    for x, name in ((l_p, "$L_p$"), (l_r, "$L_r$")):
        ax.axvline(x / 12.0, color="0.55", ls="--", lw=1.0)
        ax.annotate(f"{name} = {x / 12.0:.1f} ft", (x / 12.0, 0.0),
                    textcoords="offset points", xytext=(4, 6), fontsize=9,
                    color="0.35")
    if l_b is not None and f_bu is not None:
        ax.plot(l_b / 12.0, scale(f_bu), "r*", markersize=14,
                label=r"$(L_b, f_{bu})$")
    ax.set_xlabel("Unbraced length $L_b$ (ft)")
    ax.set_ylabel("$M_n$ (kip-ft)" if s_xc else "$F_{nc}$ (ksi)")
    ax.set_title(f"Flexural Capacity vs. Unbraced Length "
                 f"($C_b$ = {c_b:g})")
    ax.set_ylim(bottom=0.0)
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)
    return ax.get_figure()


def plot_column_curve(f_y, *, q_slender: float = 1.0,
                      design_year: int | None = None,
                      kl_over_r: float | None = None,
                      f_u_ksi: float | None = None,
                      max_kl_over_r: float = 200.0, ax=None):
    """Column curve: loop the 6.9.4.1.1 buckling check over KL/r and
    plot the nominal axial stress Pn/Ag, marking the inelastic/elastic
    transition at Pe = 0.44 Po.

    ``f_y`` may be a single yield strength (ksi) or an iterable to
    compare grades on one chart.  An optional demand point
    (``kl_over_r``, ``f_u_ksi`` = Pu/Ag) is starred.  Returns the
    figure.
    """
    import math

    from civilpy.structural.aashto.lrfd.steel import (
        E_STEEL, compression_member_resistance)

    grades = [f_y] if isinstance(f_y, (int, float)) else list(f_y)
    if ax is None:
        ax = plt.figure(figsize=(8, 5)).add_subplot(1, 1, 1)
    slenderness = [max_kl_over_r * i / 400.0 for i in range(1, 401)]
    for fy in grades:
        stresses = [compression_member_resistance(
            1.0, fy, s, q_slender=q_slender,
            design_year=design_year).capacity for s in slenderness]
        line, = ax.plot(slenderness, stresses, lw=2.0,
                        label=f"$F_y$ = {fy:g} ksi")
        transition = math.pi * math.sqrt(E_STEEL / (0.44 * q_slender * fy))
        if transition <= max_kl_over_r:
            ax.axvline(transition, color=line.get_color(), ls="--", lw=0.9,
                       alpha=0.6)
            ax.annotate(f"$P_e = 0.44P_o$\nKL/r = {transition:.0f}",
                        (transition, 0.877 * 0.44 * q_slender * fy),
                        textcoords="offset points", xytext=(6, 8),
                        fontsize=8, color=line.get_color())
    if kl_over_r is not None and f_u_ksi is not None:
        ax.plot(kl_over_r, f_u_ksi, "r*", markersize=14,
                label=r"$(KL/r, P_u/A_g)$")
    ax.set_xlabel("Slenderness $KL/r$")
    ax.set_ylabel("Nominal axial stress $P_n/A_g$ (ksi)")
    ax.set_title("Column Curve (6.9.4.1.1)")
    ax.set_xlim(0.0, max_kl_over_r)
    ax.set_ylim(bottom=0.0)
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)
    return ax.get_figure()


def plot_rc_strain_compatibility(b, h, d_s, a_s, f_c, f_y, *,
                                 a_s_prime: float = 0.0,
                                 d_s_prime: float = 0.0,
                                 result=None):
    """Three-panel strain-compatibility sketch for a rectangular RC
    section: cross-section with bars, the linear strain diagram (0.003
    crushing strain to eps_t through the neutral axis), and the Whitney
    stress block with the force resultants.

    Dimensions in inches, strengths in ksi — the same inputs as
    :func:`~civilpy.structural.aashto.lrfd.concrete.rc_rectangular_flexural_resistance`,
    which is called internally unless its ``result`` is passed in.
    Returns the figure (three shared-depth axes).
    """
    from civilpy.structural.aashto.lrfd.concrete import (
        rc_rectangular_flexural_resistance)

    if result is None:
        result = rc_rectangular_flexural_resistance(
            a_s, f_y, f_c, b, d_s,
            a_s_prime=a_s_prime, d_s_prime=d_s_prime)
    c = result.details["c"]
    a = result.details["a"]
    eps_t = result.details["eps_t"]
    comp_steel = result.details["compression_steel_active"]

    fig, (ax_sec, ax_eps, ax_sig) = plt.subplots(
        1, 3, figsize=(11, 5), sharey=True)

    # cross-section (depth measured from the top fiber, axis inverted)
    ax_sec.add_patch(plt.Rectangle((0, 0), b, h, fill=False, lw=1.8))
    ax_sec.plot([0.15 * b + i * 0.7 * b / 3 for i in range(4)], [d_s] * 4,
                "o", color="tab:red", ms=10)
    if comp_steel:
        ax_sec.plot([0.25 * b, 0.75 * b], [d_s_prime] * 2, "o",
                    color="tab:blue", ms=8)
    ax_sec.axhline(c, color="0.5", ls="-.", lw=1.0)
    ax_sec.annotate(f"c = {c:.2f} in", (b, c), textcoords="offset points",
                    xytext=(-58, -10), fontsize=9, color="0.35")
    ax_sec.annotate(f"$A_s$ = {a_s:g} in$^2$", (b / 2, d_s), ha="center",
                    textcoords="offset points", xytext=(0, -14), fontsize=9)
    ax_sec.set_xlim(-0.15 * b, 1.15 * b)
    ax_sec.set_ylim(h * 1.08, -0.08 * h)
    ax_sec.set_aspect("equal", adjustable="box")
    ax_sec.set_title(f"Section {b:g} x {h:g}")
    ax_sec.set_ylabel("Depth from top fiber (in)")

    # strain diagram: 0.003 at the top, zero at c, eps_t at d_s
    slope_pts_y = [0.0, c, d_s]
    slope_pts_x = [-0.003, 0.0, eps_t]
    ax_eps.plot(slope_pts_x, slope_pts_y, "k-", lw=2.0)
    ax_eps.axvline(0.0, color="0.6", lw=0.8)
    ax_eps.fill_betweenx([0.0, c], [-0.003, 0.0], 0.0, color="tab:blue",
                         alpha=0.2)
    ax_eps.fill_betweenx([c, d_s], 0.0, [0.0, eps_t], color="tab:red",
                         alpha=0.2)
    ax_eps.annotate(r"$\varepsilon_{cu}$ = 0.003", (-0.003, 0.0),
                    textcoords="offset points", xytext=(2, 6), fontsize=9)
    ax_eps.annotate(rf"$\varepsilon_t$ = {eps_t:.4f}", (eps_t, d_s),
                    textcoords="offset points", xytext=(-20, -14),
                    fontsize=9)
    ax_eps.annotate("N.A.", (0.0, c), textcoords="offset points",
                    xytext=(4, -4), fontsize=9, color="0.35")
    ax_eps.set_title("Strain (plane sections)")
    ax_eps.set_xlabel("Strain")

    # Whitney block and force resultants
    f_block = 0.85 * f_c
    ax_sig.add_patch(plt.Rectangle((-f_block, 0), f_block, a,
                                   color="tab:blue", alpha=0.35))
    ax_sig.axvline(0.0, color="0.6", lw=0.8)
    c_c = f_block * b * a
    t_force = a_s * f_y
    ax_sig.annotate("", xy=(-f_block - 0.4 * f_c, a / 2.0),
                    xytext=(-f_block + 0.1 * f_c, a / 2.0),
                    arrowprops=dict(arrowstyle="-|>", color="tab:blue",
                                    lw=2.5))
    ax_sig.annotate(rf"$C_c$ = {c_c:.0f} k  (0.85$f'_c$ over a = {a:.2f})",
                    (-f_block, a / 2.0), textcoords="offset points",
                    xytext=(6, 10), fontsize=9, color="tab:blue")
    ax_sig.annotate("", xy=(0.5 * f_c, d_s), xytext=(0.0, d_s),
                    arrowprops=dict(arrowstyle="-|>", color="tab:red",
                                    lw=2.5))
    ax_sig.annotate(rf"$T$ = {t_force:.0f} k", (0.5 * f_c, d_s),
                    textcoords="offset points", xytext=(4, -4), fontsize=9,
                    color="tab:red")
    ax_sig.annotate(
        rf"$M_n$ = {result.capacity / 12.0:.0f} kip-ft, "
        rf"$\phi$ = {result.phi:g}",
        (0.0, h), textcoords="offset points", xytext=(-40, -6), fontsize=10)
    ax_sig.set_title("Stress block & resultants")
    ax_sig.set_xlabel("Stress (ksi)")
    fig.suptitle("RC Strain Compatibility (5.6.3.2)")
    fig.tight_layout()
    return fig
