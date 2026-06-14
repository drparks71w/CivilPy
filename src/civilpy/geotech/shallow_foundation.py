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

"""Shallow (spread) foundation analysis and design.

Three families of routines, all pure functions or small dataclasses:

* **Bearing capacity** -- the general (Terzaghi / Meyerhof / Vesic) bearing
  capacity equation with shape, embedment-depth, and load-inclination
  modifiers, and Meyerhof's effective-area reduction for eccentric loads.
  AASHTO LRFD 10.6.3.1; allowable-stress (factor of safety) and factored
  (resistance-factor) forms both fall out of one result object.
* **Contact pressure** -- the soil bearing-pressure distribution under a
  combined vertical load and moment (full-contact trapezoid, triangular
  with partial uplift) used to check the bearing demand and to load the
  footing as a structural element.
* **Settlement** -- Schmertmann strain-influence elastic settlement and
  one-dimensional primary consolidation, both able to source soil layering
  and effective stresses from :class:`~civilpy.geotech.soil_profile.SoilProfile`.

The footing's own structural design (one-way shear, two-way punching shear,
flexural reinforcement) reuses the reinforced-concrete resistance functions
in :mod:`civilpy.structural.aashto.lrfd.concrete` rather than re-deriving
them here.

Units: feet, pounds-force, and pcf for the geotechnical side (pressures in
psf, capacities reported in both psf and ksf); the structural helpers
convert to the kip-inch-ksi convention the LRFD module expects.  Angles in
degrees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.geotech.soil_profile import SoilProfile
from civilpy.structural.aashto.lrfd.concrete import (
    rc_rectangular_flexural_resistance,
    rc_shear_resistance,
)
from civilpy.structural.aashto.lrfd.core import CheckResult, article

#: Unit weight of water, pcf.
GAMMA_WATER = 62.4

#: Recognised bearing-capacity-factor methods.
_BC_METHODS = ("terzaghi", "meyerhof", "hansen", "vesic")


# ----------------------------------------------------------- bearing factors


@dataclass
class BearingCapacityFactors:
    """Dimensionless bearing-capacity factors Nc, Nq, Ngamma for a given
    friction angle and method."""

    nc: float
    nq: float
    ngamma: float
    method: str


def bearing_capacity_factors(
    phi_deg: float, method: str = "vesic"
) -> BearingCapacityFactors:
    """Bearing-capacity factors for friction angle ``phi_deg``.

    ``Nq`` and ``Nc`` for Meyerhof/Hansen/Vesic are the Prandtl-Reissner
    forms ``Nq = e^(pi*tan phi)*tan^2(45 + phi/2)`` and
    ``Nc = (Nq - 1)*cot phi`` (5.14 at phi = 0).  Terzaghi uses his own
    ``Nq = a^2/(2 cos^2(45 + phi/2))`` with ``a = e^((3pi/4 - phi/2) tan phi)``
    and ``Nc = 5.7`` at phi = 0.  ``Ngamma`` differs by method:

    * Terzaghi -- ``2 (Nq + 1) tan phi / (1 + 0.4 sin 4phi)`` (approximation)
    * Meyerhof -- ``(Nq - 1) tan(1.4 phi)``
    * Hansen   -- ``1.5 (Nq - 1) tan phi``
    * Vesic    -- ``2 (Nq + 1) tan phi``
    """
    if method not in _BC_METHODS:
        raise ValueError(f"unknown method {method!r}; choose from {_BC_METHODS}")
    phi = math.radians(phi_deg)
    if phi_deg <= 0.0:
        nc = 5.7 if method == "terzaghi" else 5.14
        return BearingCapacityFactors(nc=nc, nq=1.0, ngamma=0.0, method=method)

    t = math.tan(phi)
    if method == "terzaghi":
        a = math.exp((0.75 * math.pi - phi / 2.0) * t)
        nq = a * a / (2.0 * math.cos(math.pi / 4.0 + phi / 2.0) ** 2)
    else:
        nq = math.exp(math.pi * t) * math.tan(math.pi / 4.0 + phi / 2.0) ** 2
    nc = (nq - 1.0) / t

    if method == "terzaghi":
        ngamma = 2.0 * (nq + 1.0) * t / (1.0 + 0.4 * math.sin(4.0 * phi))
    elif method == "meyerhof":
        ngamma = (nq - 1.0) * math.tan(1.4 * phi)
    elif method == "hansen":
        ngamma = 1.5 * (nq - 1.0) * t
    else:  # vesic
        ngamma = 2.0 * (nq + 1.0) * t
    return BearingCapacityFactors(nc=nc, nq=nq, ngamma=ngamma, method=method)


# ------------------------------------------------------------- modifier sets


def shape_factors(
    b: float, l: float, phi_deg: float, nq: float, nc: float
) -> tuple[float, float, float]:
    """De Beer / Vesic shape factors (sc, sq, sgamma) for an effective
    footing ``b`` by ``l`` (b is the smaller plan dimension).  ``nq``/``nc``
    are the bearing-capacity factors."""
    bl = b / l
    sc = 1.0 + bl * nq / nc
    sq = 1.0 + bl * math.tan(math.radians(phi_deg))
    sgamma = max(0.6, 1.0 - 0.4 * bl)
    return sc, sq, sgamma


def depth_factors(
    d: float, b: float, phi_deg: float
) -> tuple[float, float, float]:
    """Hansen embedment-depth factors (dc, dq, dgamma).  For ``d/b <= 1`` the
    factor ``k = d/b``; for deeper footings ``k = arctan(d/b)`` (radians) so
    the modifier stays bounded.  ``dgamma = 1``."""
    ratio = d / b
    k = ratio if ratio <= 1.0 else math.atan(ratio)
    phi = math.radians(phi_deg)
    dc = 1.0 + 0.4 * k
    dq = 1.0 + 2.0 * math.tan(phi) * (1.0 - math.sin(phi)) ** 2 * k
    return dc, dq, 1.0


def inclination_factors(
    h: float, v: float, b: float, l: float, phi_deg: float, c: float, area: float
) -> tuple[float, float, float]:
    """Vesic load-inclination factors (ic, iq, igamma) for a horizontal
    load ``h`` and vertical load ``v`` (consistent force units).  ``area``
    is the effective bearing area, ``c`` the cohesion (same pressure unit as
    used elsewhere).  For frictionless soil (phi = 0) only the cohesion term
    is reduced.  Raises if ``h`` exceeds the available sliding resistance."""
    if h <= 0.0:
        return 1.0, 1.0, 1.0
    m = (2.0 + b / l) / (1.0 + b / l)
    phi = math.radians(phi_deg)
    if phi_deg <= 0.0:
        ic = 1.0 - m * h / (area * c * 5.14)
        return ic, 1.0, 1.0
    denom = v + area * c / math.tan(phi)
    base = 1.0 - h / denom
    if base <= 0.0:
        raise ValueError("horizontal load exceeds shear resistance (i-factor)")
    iq = base ** m
    igamma = base ** (m + 1.0)
    ic = iq - (1.0 - iq) / ((nq_from_phi(phi_deg)) * math.tan(phi))
    return ic, iq, igamma


def nq_from_phi(phi_deg: float) -> float:
    """Reissner ``Nq`` (used by the inclination factor's cohesion term)."""
    phi = math.radians(phi_deg)
    return math.exp(math.pi * math.tan(phi)) * math.tan(
        math.pi / 4.0 + phi / 2.0
    ) ** 2


# --------------------------------------------------------- water-table effect


def bearing_water_table(
    gamma: float, gamma_sat: float, d: float, b: float, water_table: float
) -> tuple[float, float]:
    """Surcharge ``q`` at footing level and the unit weight to use in the
    ``0.5*gamma*B*Ngamma`` term, accounting for a water table at depth
    ``water_table`` (ft below ground).  ``gamma`` is the moist weight above
    the table, ``gamma_sat`` the saturated weight below it.  Three cases per
    Das: table below the failure wedge (``d + b``), within the wedge, and
    above footing level."""
    gamma_b = gamma_sat - GAMMA_WATER  # buoyant
    if water_table >= d + b:
        return gamma * d, gamma
    if water_table >= d:
        q = gamma * d
        gamma_term = gamma_b + (water_table - d) / b * (gamma - gamma_b)
        return q, gamma_term
    q = gamma * water_table + gamma_b * (d - water_table)
    return q, gamma_b


# --------------------------------------------------------- bearing capacity


@dataclass
class BearingCapacityResult:
    """Ultimate bearing capacity and the pieces an engineer would tabulate.

    ``q_ult`` is the gross ultimate unit bearing pressure (psf); ``terms``
    holds the cohesion, surcharge, and self-weight contributions.
    """

    q_ult: float
    factors: BearingCapacityFactors
    b_eff: float
    l_eff: float
    terms: dict = field(default_factory=dict)
    modifiers: dict = field(default_factory=dict)

    @property
    def q_ult_ksf(self) -> float:
        return self.q_ult / 1000.0

    @property
    def area_eff(self) -> float:
        """Effective (Meyerhof) bearing area, ft^2."""
        return self.b_eff * self.l_eff

    def allowable(self, fs: float = 3.0) -> float:
        """Allowable bearing pressure (psf) = q_ult / FS (ASD)."""
        return self.q_ult / fs

    def nominal_load(self) -> float:
        """Nominal bearing resistance as a force (lb) = q_ult * effective
        area."""
        return self.q_ult * self.area_eff

    def factored_load(self, phi_b: float = 0.45) -> float:
        """Factored bearing resistance (lb), AASHTO LRFD 10.5.5.2.2;
        ``phi_b`` defaults to 0.45 (theoretical/semi-empirical methods)."""
        return phi_b * self.nominal_load()


def ultimate_bearing_capacity(
    b: float,
    l: float,
    d: float,
    gamma: float,
    phi_deg: float,
    c: float = 0.0,
    method: str = "vesic",
    shape: bool = True,
    depth: bool = True,
    ecc_b: float = 0.0,
    ecc_l: float = 0.0,
    h: float = 0.0,
    v: float | None = None,
    water_table: float | None = None,
    gamma_sat: float | None = None,
) -> BearingCapacityResult:
    """General bearing-capacity equation (AASHTO LRFD 10.6.3.1.2):

        q_ult = c*Nc*sc*dc*ic + q*Nq*sq*dq*iq + 0.5*gamma*B'*Ngamma*sg*dg*ig

    ``b`` and ``l`` are the plan dimensions (ft, ``b <= l``), ``d`` the
    embedment depth, ``gamma`` the soil unit weight (pcf), ``c`` the cohesion
    (psf).  Eccentricities ``ecc_b``/``ecc_l`` (ft) trigger Meyerhof's
    effective-width reduction ``B' = B - 2e``.  A horizontal load ``h`` with
    vertical ``v`` (lb) brings in the inclination factors.  ``water_table``
    (ft) with ``gamma_sat`` (pcf) adjusts the surcharge and self-weight
    terms.
    """
    if b <= 0.0 or l <= 0.0 or d < 0.0:
        raise ValueError("b and l must be positive and d non-negative")
    b_eff = b - 2.0 * ecc_b
    l_eff = l - 2.0 * ecc_l
    if b_eff <= 0.0 or l_eff <= 0.0:
        raise ValueError("eccentricity too large: effective dimension <= 0")
    # Work with the smaller effective dimension as B'.
    b_eff, l_eff = min(b_eff, l_eff), max(b_eff, l_eff)

    f = bearing_capacity_factors(phi_deg, method)

    if water_table is not None:
        gs = gamma_sat if gamma_sat is not None else gamma + GAMMA_WATER
        q_surcharge, gamma_term = bearing_water_table(gamma, gs, d, b_eff, water_table)
    else:
        q_surcharge, gamma_term = gamma * d, gamma

    if shape:
        sc, sq, sg = shape_factors(b_eff, l_eff, phi_deg, f.nq, f.nc)
    else:
        sc = sq = sg = 1.0
    if depth:
        dc, dq, dg = depth_factors(d, b_eff, phi_deg)
    else:
        dc = dq = dg = 1.0
    if h > 0.0:
        vv = v if v is not None else 0.0
        ic, iq, ig = inclination_factors(
            h, vv, b_eff, l_eff, phi_deg, c, b_eff * l_eff
        )
    else:
        ic = iq = ig = 1.0

    c_term = c * f.nc * sc * dc * ic
    q_term = q_surcharge * f.nq * sq * dq * iq
    g_term = 0.5 * gamma_term * b_eff * f.ngamma * sg * dg * ig
    q_ult = c_term + q_term + g_term

    return BearingCapacityResult(
        q_ult=q_ult,
        factors=f,
        b_eff=b_eff,
        l_eff=l_eff,
        terms={"cohesion": c_term, "surcharge": q_term, "self_weight": g_term},
        modifiers={
            "shape": (sc, sq, sg),
            "depth": (dc, dq, dg),
            "inclination": (ic, iq, ig),
            "q_surcharge": q_surcharge,
            "gamma_term": gamma_term,
        },
    )


# ------------------------------------------------------- contact pressure


@dataclass
class ContactPressure:
    """Soil contact-pressure distribution under axial load ``p`` (lb) at
    eccentricity ``e`` (ft) on a footing of width ``width`` (ft, in the
    direction of the moment) and length ``length`` (ft)."""

    q_max: float
    q_min: float
    width: float
    length: float
    eccentricity: float
    contact_length: float
    uplift: bool

    @property
    def full_contact(self) -> bool:
        return not self.uplift


def contact_pressure(
    p: float, m: float, width: float, length: float
) -> ContactPressure:
    """Bearing-pressure distribution from a vertical load ``p`` (lb) and
    moment ``m`` (lb-ft) on a rectangular footing.

    With eccentricity ``e = M/P`` inside the middle third (``e <= L/6``) the
    pressure is trapezoidal, ``q = P/A * (1 +/- 6e/width)``.  Outside the
    kern the heel lifts off and a triangular distribution develops over a
    contact length ``3*(width/2 - e)`` with peak ``2P/(length*contact)``
    (the resultant must pass through the centroid of the triangle).
    """
    if p <= 0.0:
        raise ValueError("vertical load p must be positive")
    area = width * length
    e = abs(m) / p
    kern = width / 6.0
    if e <= kern:
        q_avg = p / area
        q_max = q_avg * (1.0 + 6.0 * e / width)
        q_min = q_avg * (1.0 - 6.0 * e / width)
        return ContactPressure(
            q_max=q_max, q_min=q_min, width=width, length=length,
            eccentricity=e, contact_length=width, uplift=False,
        )
    contact = 3.0 * (width / 2.0 - e)
    if contact <= 0.0:
        raise ValueError("resultant outside footing: no stable bearing")
    q_max = 2.0 * p / (length * contact)
    return ContactPressure(
        q_max=q_max, q_min=0.0, width=width, length=length,
        eccentricity=e, contact_length=contact, uplift=True,
    )


# --------------------------------------------------- footing structural design


def one_way_shear_demand(
    q_net: float, width: float, length: float, col_width: float, d_in: float
) -> float:
    """Factored one-way (beam) shear ``Vu`` (kip) at distance ``d`` from the
    column face on a footing carrying uniform net pressure ``q_net`` (psf).

    The critical section is at ``d_in`` (in) from the face; the cantilever
    length is ``(length - col_width)/2 - d`` (ft).  ``width`` is the footing
    dimension perpendicular to the span.  Returns 0 if the section falls
    outside the footing.
    """
    cantilever = (length - col_width) / 2.0 - d_in / 12.0
    if cantilever <= 0.0:
        return 0.0
    v_lb = q_net * width * cantilever
    return v_lb / 1000.0


def footing_one_way_shear(
    q_net: float,
    width: float,
    length: float,
    col_width: float,
    thickness_in: float,
    cover_in: float,
    f_c: float,
    bar_dia_in: float = 1.0,
) -> CheckResult:
    """One-way shear check of a spread footing, reusing
    :func:`~civilpy.structural.aashto.lrfd.concrete.rc_shear_resistance`.

    ``thickness_in`` is the footing depth; ``d = thickness - cover - db/2``.
    The full footing ``width`` (ft) is the shear width ``bv``.  Returns the
    LRFD CheckResult (capacity phi*Vn vs demand Vu).
    """
    d_in = thickness_in - cover_in - bar_dia_in / 2.0
    bv = width * 12.0
    dv = max(0.9 * d_in, 0.72 * thickness_in)
    v_u = one_way_shear_demand(q_net, width, length, col_width, d_in)
    return rc_shear_resistance(b_v=bv, d_v=dv, f_c=f_c, v_u=v_u)


@article("5.12.8.6.3", "Two-Way (Punching) Shear at Footings")
def footing_punching_shear(
    p_u: float,
    col_b_in: float,
    col_l_in: float,
    thickness_in: float,
    cover_in: float,
    f_c: float,
    beta_c: float | None = None,
    bar_dia_in: float = 1.0,
    q_net: float = 0.0,
    lam: float = 1.0,
    phi_v: float = 0.9,
) -> CheckResult:
    """Two-way (punching) shear resistance at a footing (AASHTO 5.12.8.6.3):

        Vn = (0.063 + 0.126/beta_c)*lam*sqrt(f'c)*b0*dv <= 0.126*lam*sqrt(f'c)*b0*dv

    ``p_u`` is the factored column load (kip); the critical perimeter ``b0``
    is taken ``d/2`` outside a rectangular column ``col_b`` x ``col_l`` (in).
    ``beta_c`` is the column aspect ratio (defaults to the long/short side).
    The net upward pressure within the critical perimeter (``q_net`` psf) is
    credited back, so the demand is ``Pu`` minus that relief.  Result is in
    kip; phi_v = 0.9.
    """
    d_in = thickness_in - cover_in - bar_dia_in / 2.0
    dv = max(0.9 * d_in, 0.72 * thickness_in)
    b0 = 2.0 * (col_b_in + d_in) + 2.0 * (col_l_in + d_in)  # in
    bc = beta_c if beta_c is not None else max(col_b_in, col_l_in) / min(
        col_b_in, col_l_in
    )
    sqrt_fc = lam * math.sqrt(f_c)
    v_n = min(0.063 + 0.126 / bc, 0.126) * sqrt_fc * b0 * dv
    # Relief from soil pressure inside the punched area (kip).
    crit_area_ft2 = ((col_b_in + d_in) * (col_l_in + d_in)) / 144.0
    relief = q_net * crit_area_ft2 / 1000.0
    return CheckResult(
        article="5.12.8.6.3",
        name="Two-Way (Punching) Shear at Footings",
        capacity=v_n,
        demand=max(p_u - relief, 0.0),
        phi=phi_v,
        details={"b0": b0, "dv": dv, "beta_c": bc, "relief": relief},
    )


def footing_flexure_demand(
    q_net: float, length: float, col_width: float
) -> float:
    """Factored cantilever moment ``Mu`` (kip-in per foot of width) at the
    column face on a footing under net pressure ``q_net`` (psf).  Span is
    ``(length - col_width)/2`` (ft)."""
    arm = (length - col_width) / 2.0
    m_lb_ft = q_net * arm * arm / 2.0  # per ft of width, lb-ft
    return m_lb_ft * 12.0 / 1000.0  # kip-in per ft


def footing_flexure(
    q_net: float,
    length: float,
    col_width: float,
    a_s: float,
    thickness_in: float,
    cover_in: float,
    f_c: float,
    f_y: float = 60.0,
    bar_dia_in: float = 1.0,
) -> CheckResult:
    """Flexural check of the footing cantilever, reusing
    :func:`~civilpy.structural.aashto.lrfd.concrete.rc_rectangular_flexural_resistance`.

    ``a_s`` is the reinforcement area in a 12-in design strip (in^2/ft);
    ``length``/``col_width`` (ft) set the cantilever moment.  Effective
    depth ``d = thickness - cover - db/2``.
    """
    d_s = thickness_in - cover_in - bar_dia_in / 2.0
    m_u = footing_flexure_demand(q_net, length, col_width)
    return rc_rectangular_flexural_resistance(
        a_s=a_s, f_y=f_y, f_c=f_c, b=12.0, d_s=d_s, m_u=m_u
    )


# ----------------------------------------------------------- settlement


def stress_increase_2to1(q: float, b: float, l: float, z: float) -> float:
    """Vertical stress increase (same unit as ``q``) at depth ``z`` below a
    ``b`` x ``l`` loaded area by the 2:1 (2 vertical : 1 horizontal) method:
    ``dsigma = q*B*L/((B+z)(L+z))``."""
    return q * b * l / ((b + z) * (l + z))


def _schmertmann_profile(l_over_b: float) -> tuple[float, float, float]:
    """(Iz at z=0, depth-to-peak / B, influence-depth / B) interpolated
    between Schmertmann's axisymmetric (L/B = 1) and plane-strain
    (L/B >= 10) limits."""
    if l_over_b <= 1.0:
        return 0.1, 0.5, 2.0
    if l_over_b >= 10.0:
        return 0.2, 1.0, 4.0
    frac = (l_over_b - 1.0) / 9.0
    return 0.1 + 0.1 * frac, 0.5 + 0.5 * frac, 2.0 + 2.0 * frac


@dataclass
class SettlementResult:
    """Total settlement (in) and the correction factors / per-sublayer
    contributions that produced it."""

    settlement_in: float
    c1: float = 1.0
    c2: float = 1.0
    contributions: list = field(default_factory=list)


def schmertmann_settlement(
    net_pressure: float,
    b: float,
    l: float,
    d: float,
    es_profile,
    gamma: float = 120.0,
    years: float = 1.0,
    n_sublayers: int = 20,
) -> SettlementResult:
    """Schmertmann (1978) strain-influence elastic settlement (in).

        S = C1*C2*dq * sum( Iz/Es * dz )

    ``net_pressure`` is the net applied pressure dq (psf); ``b``/``l`` the
    footing plan dimensions and ``d`` the embedment (ft).  ``es_profile`` is
    either a constant Young's modulus (psf) or a callable ``Es(depth_below_
    footing_ft)``.  C1 is the embedment correction ``1 - 0.5*(q'/dq) >= 0.5``
    with ``q' = gamma*d`` the overburden at footing level; C2 the creep
    factor ``1 + 0.2*log10(years/0.1)``.  The strain-influence diagram peaks
    at ``Izp = 0.5 + 0.1*sqrt(dq/sigma'_vp)``.
    """
    if net_pressure <= 0.0:
        raise ValueError("net_pressure must be positive")
    l_over_b = max(l, b) / min(l, b)
    iz0, zp_ratio, zmax_ratio = _schmertmann_profile(l_over_b)
    zp = zp_ratio * b
    zmax = zmax_ratio * b

    q_prime = gamma * d
    c1 = max(0.5, 1.0 - 0.5 * q_prime / net_pressure)
    c2 = 1.0 + 0.2 * math.log10(max(years, 0.1) / 0.1)

    sigma_vp = gamma * (d + zp)  # effective overburden at peak depth
    izp = 0.5 + 0.1 * math.sqrt(net_pressure / sigma_vp)

    es_func = es_profile if callable(es_profile) else (lambda z: es_profile)

    dz = zmax / n_sublayers
    total = 0.0
    contributions = []
    for i in range(n_sublayers):
        z_mid = (i + 0.5) * dz
        if z_mid <= zp:
            iz = iz0 + (izp - iz0) * z_mid / zp
        else:
            iz = izp * (zmax - z_mid) / (zmax - zp)
        es = es_func(z_mid)
        strain = iz / es * dz  # ft (per unit dq)
        total += strain
        contributions.append((z_mid, iz, es))
    settlement_ft = c1 * c2 * net_pressure * total
    return SettlementResult(
        settlement_in=settlement_ft * 12.0,
        c1=c1, c2=c2, contributions=contributions,
    )


@dataclass
class ConsolidationLayer:
    """Consolidation parameters for one compressible stratum (by index into
    a :class:`SoilProfile`)."""

    layer_index: int
    cc: float          # compression index
    e0: float          # initial void ratio
    cr: float = 0.0    # recompression index
    sigma_pc: float | None = None  # preconsolidation pressure (psf)


def consolidation_settlement(
    profile: SoilProfile,
    layers: list[ConsolidationLayer],
    delta_sigma,
    n_slices: int = 1,
) -> SettlementResult:
    """One-dimensional primary consolidation settlement (in) of the
    compressible ``layers`` within ``profile``.

    For each layer the initial effective stress ``sigma'0`` is read at the
    layer midpoint from ``profile`` and the stress increase ``delta_sigma``
    (a constant psf or a callable ``dsigma(depth_ft)``) is added.  Normally
    consolidated soil (or no preconsolidation given) uses the virgin curve
    ``Cc/(1+e0)*H*log10((s0+ds)/s0)``; over-consolidated soil uses the
    recompression index ``Cr`` while the final stress stays below
    ``sigma_pc`` and splits across ``sigma_pc`` when it is exceeded.
    ``n_slices`` sub-divides each layer for a better midpoint stress.
    """
    ds_func = delta_sigma if callable(delta_sigma) else (lambda z: delta_sigma)
    tops = []
    top = 0.0
    for layer in profile.layers:
        tops.append(top)
        top += layer.thickness

    total_ft = 0.0
    contributions = []
    for cl in layers:
        layer = profile.layers[cl.layer_index]
        layer_top = tops[cl.layer_index]
        h_slice = layer.thickness / n_slices
        for j in range(n_slices):
            z_mid = layer_top + (j + 0.5) * h_slice
            _, _, sigma0 = profile.stresses_at(z_mid)
            if sigma0 <= 0.0:
                raise ValueError(
                    f"non-positive effective stress at depth {z_mid} ft"
                )
            ds = ds_func(z_mid)
            sigma_f = sigma0 + ds
            sigma_pc = cl.sigma_pc if cl.sigma_pc is not None else sigma0
            if sigma_f <= sigma_pc:
                dh = cl.cr / (1.0 + cl.e0) * h_slice * math.log10(sigma_f / sigma0)
            elif sigma0 >= sigma_pc:
                dh = cl.cc / (1.0 + cl.e0) * h_slice * math.log10(sigma_f / sigma0)
            else:
                dh = (
                    cl.cr / (1.0 + cl.e0) * h_slice * math.log10(sigma_pc / sigma0)
                    + cl.cc / (1.0 + cl.e0) * h_slice * math.log10(sigma_f / sigma_pc)
                )
            total_ft += dh
            contributions.append((z_mid, sigma0, sigma_f, dh))
    return SettlementResult(settlement_in=total_ft * 12.0, contributions=contributions)
