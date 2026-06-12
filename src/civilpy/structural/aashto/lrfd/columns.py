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

Axial resistance, reinforcement limits, spiral steel, strain-compatibility
P-M interaction (uniaxial and Bresler biaxial), and the approximate
moment-magnification treatment of slenderness.  Units: kip, inch, ksi.
"""

import math
from dataclasses import dataclass

from civilpy.structural.aashto.lrfd.core import CheckResult, article
from civilpy.structural.aashto.lrfd.concrete import beta1, phi_flexure

PHI_COMPRESSION = 0.75  # compression-controlled sections (5.5.4.2)
EPS_CU = 0.003  # crushing strain at the extreme compression fiber (5.6.2.1)
E_REBAR = 29000.0  # ksi


@dataclass(frozen=True)
class RebarLayer:
    """One layer of longitudinal bars: total ``area`` (in^2) at ``depth``
    from the extreme compression fiber (in)."""

    area: float
    depth: float


def _circular_segment(radius: float, depth: float) -> tuple[float, float]:
    """Area and centroid (measured from the top of the circle) of a
    circular segment of the given depth cut by a horizontal chord."""
    depth = min(max(depth, 0.0), 2.0 * radius)
    if depth <= 0.0:
        return 0.0, 0.0
    theta = math.acos((radius - depth) / radius)  # half-angle
    area = radius**2 * (theta - math.sin(theta) * math.cos(theta))
    if area == 0.0:
        return 0.0, 0.0
    # centroid distance from circle center toward the chord side
    y_bar = 2.0 * radius * math.sin(theta) ** 3 / (
        3.0 * (theta - math.sin(theta) * math.cos(theta))
    )
    return area, radius - y_bar


@dataclass
class PMPoint:
    """One point on the nominal interaction diagram."""

    p_n: float
    m_n: float
    eps_t: float
    phi: float
    c: float

    @property
    def phi_pn(self) -> float:
        return self.phi * self.p_n

    @property
    def phi_mn(self) -> float:
        return self.phi * self.m_n


def _pm_point(
    c: float,
    layers: list[RebarLayer],
    f_c: float,
    f_y: float,
    h: float,
    b: float | None,
    diameter: float | None,
) -> PMPoint:
    """Strain-compatibility forces for one neutral-axis depth ``c``:
    Whitney block concrete force plus elastic-perfectly-plastic steel,
    moments about the section mid-depth (compression positive)."""
    b1 = beta1(f_c)
    a = min(b1 * c, h)
    if diameter is not None:
        r = diameter / 2.0
        area_c, y_c = _circular_segment(r, a)
    else:
        area_c, y_c = a * b, a / 2.0
    p = 0.85 * f_c * area_c
    m = p * (h / 2.0 - y_c)

    d_t = max(layer.depth for layer in layers)
    for layer in layers:
        eps = EPS_CU * (c - layer.depth) / c
        f_s = min(max(eps * E_REBAR, -f_y), f_y)
        if eps > 0:
            f_s -= 0.85 * f_c  # bar displaces stressed concrete
        force = f_s * layer.area
        p += force
        m += force * (h / 2.0 - layer.depth)

    eps_t = EPS_CU * (d_t - c) / c  # tension positive at extreme steel
    phi = phi_flexure(eps_t)  # clamps to 0.75 when compression-controlled
    return PMPoint(p_n=p, m_n=m, eps_t=eps_t, phi=phi, c=c)


@article("5.6.4.5 P-M", "Column P-M Interaction Diagram")
def rc_pm_interaction_diagram(
    layers: list[RebarLayer],
    f_c: float,
    f_y: float,
    h: float | None = None,
    b: float | None = None,
    diameter: float | None = None,
    spiral: bool = False,
    n_points: int = 60,
) -> list[PMPoint]:
    """Nominal P-M interaction diagram for a rectangular (``b`` x ``h``) or
    circular (``diameter``) reinforced section by strain compatibility,
    sweeping the neutral axis from pure tension to pure compression.

    Returns points ordered from pure tension (negative Pn) to the maximum
    axial point, with phi per 5.5.4.2 attached; Pn is capped at the
    5.6.4.4 tied/spiral maximum.  Moments are about the section mid-depth
    (symmetric sections assumed for the axial-load point of application).
    """
    if diameter is not None:
        h = diameter
        a_g = math.pi * diameter**2 / 4.0
    else:
        if b is None or h is None:
            raise ValueError("rectangular sections need b and h")
        a_g = b * h
    a_st = sum(layer.area for layer in layers)
    d_t = max(layer.depth for layer in layers)

    # 5.6.4.4 cap on usable axial resistance
    p_o = 0.85 * f_c * (a_g - a_st) + f_y * a_st
    p_n_max = (0.85 if spiral else 0.80) * p_o

    points: list[PMPoint] = []
    # pure tension anchor
    p_t = -f_y * a_st
    points.append(PMPoint(p_n=p_t, m_n=0.0, eps_t=10.0 * EPS_CU,
                          phi=phi_flexure(0.005), c=0.0))
    # sweep c geometrically from very shallow to beyond the section
    c_values = [d_t * (i + 1) / n_points * 1.5 for i in range(n_points)]
    c_values += [h * 1.5, h * 2.5, h * 10.0]
    for c in sorted(set(c_values)):
        pt = _pm_point(c, layers, f_c, f_y, h, b, diameter)
        pt = PMPoint(p_n=min(pt.p_n, p_n_max), m_n=pt.m_n,
                     eps_t=pt.eps_t, phi=pt.phi, c=pt.c)
        points.append(pt)
    return points


@article("5.6.4.5 check", "Column P-M Capacity Check")
def rc_pm_capacity_check(
    p_u: float,
    m_u: float,
    layers: list[RebarLayer],
    f_c: float,
    f_y: float,
    h: float | None = None,
    b: float | None = None,
    diameter: float | None = None,
    spiral: bool = False,
) -> CheckResult:
    """Uniaxial column adequacy: interpolate the factored interaction
    diagram at the factored axial load ``p_u`` (kip, compression positive)
    and compare the available phi*Mn against ``m_u`` (kip-in).

    ``capacity`` holds the factored moment resistance at Pu; ``phi`` on
    the result is 1.0 because phi is baked into the diagram point by
    point (it varies with eps_t along the curve)."""
    diagram = rc_pm_interaction_diagram(
        layers=layers, f_c=f_c, f_y=f_y, h=h, b=b, diameter=diameter,
        spiral=spiral,
    )
    # walk the curve (phi_pn is monotonically increasing along the sweep)
    m_r = None
    for low, high in zip(diagram, diagram[1:]):
        if low.phi_pn <= p_u <= high.phi_pn:
            frac = ((p_u - low.phi_pn) / (high.phi_pn - low.phi_pn)
                    if high.phi_pn != low.phi_pn else 0.0)
            m_r = low.phi_mn + frac * (high.phi_mn - low.phi_mn)
            break
    if m_r is None:
        m_r = 0.0  # Pu outside the diagram: no moment capacity remains
    return CheckResult(
        article="5.6.4.5 check",
        name="Column P-M Capacity Check",
        capacity=m_r,
        demand=m_u,
        details={"Pu": p_u,
                 "phi_Pn_max": max(pt.phi_pn for pt in diagram),
                 "within_axial_range": m_r > 0.0 or m_u == 0.0},
    )


@article("5.6.4.5", "Biaxial Flexure")
def rc_biaxial_check(
    p_u: float,
    m_ux: float,
    m_uy: float,
    m_rx: float,
    m_ry: float,
    p_rx: float | None = None,
    p_ry: float | None = None,
    phi_p_o: float | None = None,
    f_c: float | None = None,
    a_g: float | None = None,
) -> CheckResult:
    """Biaxial flexure (5.6.4.5).  Below the low-axial threshold
    0.10*phi*f'c*Ag the moment-contour form applies:
    Mux/Mrx + Muy/Mry <= 1.0.  Above it, the reciprocal (Bresler) load
    method: 1/Prxy = 1/Prx + 1/Pry - 1/(phi*Po) and Prxy >= Pu.

    ``m_rx``/``m_ry`` are the factored uniaxial moment resistances at Pu
    (from :func:`rc_pm_capacity_check`); ``p_rx``/``p_ry`` the factored
    axial resistances at eccentricities ey and ex.  ``capacity``/``demand``
    carry the governing pair (resistance/applied)."""
    low_axial = (f_c is not None and a_g is not None
                 and p_u < 0.10 * PHI_COMPRESSION * f_c * a_g)
    if low_axial:
        utilization = m_ux / m_rx + m_uy / m_ry
        return CheckResult(
            article="5.6.4.5",
            name="Biaxial Flexure",
            capacity=1.0,
            demand=utilization,
            details={"method": "moment-contour", "utilization": utilization},
        )
    if None in (p_rx, p_ry, phi_p_o):
        raise ValueError(
            "reciprocal-load method needs p_rx, p_ry, and phi_p_o "
            "(or pass f_c and a_g for the low-axial moment-contour form)"
        )
    p_rxy = 1.0 / (1.0 / p_rx + 1.0 / p_ry - 1.0 / phi_p_o)
    return CheckResult(
        article="5.6.4.5",
        name="Biaxial Flexure",
        capacity=p_rxy,
        demand=p_u,
        details={"method": "reciprocal-load", "Prx": p_rx, "Pry": p_ry},
    )


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
