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

"""Laterally loaded piles: a shared p-y curve library, a finite-element
beam-on-nonlinear-foundation solver, Broms' closed-form ultimate-load
method, and the characteristic-length / subgrade-reaction hand methods.

The p-y curve classes (:class:`SoftClayPY`, :class:`StiffClayPY`,
:class:`SandPY`, :class:`LinearPY`) are the reusable core: they expose a
common ``p(y, z)`` (soil resistance per unit length) and ``pu(z)`` (ultimate
resistance) so the same soil models drive both the in-process solver here
and the LPILE input-file generator in :mod:`civilpy.geotech.lpile`.

Curve references: soft clay -- Matlock (1970); stiff clay without free
water -- Reese & Welch (1975); sand -- the API RP 2A / O'Neill & Murchison
hyperbolic-tangent form on Reese's (1974) ultimate resistance.

Units throughout this module are inches, pounds, and psi (so unit weights
are pci and the flexural stiffness EI is lb-in^2), matching the convention
LPILE uses.  Angles are in degrees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import matplotlib.pyplot as plt
import numpy as np

#: A small deflection floor (in) used to form a secant soil modulus near
#: y = 0 without dividing by zero.
_Y_FLOOR = 1.0e-6


# ============================================================ p-y curves


class PYCurve:
    """Base class for p-y curves.  Subclasses implement :meth:`p` and
    :meth:`pu`; the secant modulus used by the solver follows from them."""

    def pu(self, z: float) -> float:  # pragma: no cover - interface
        raise NotImplementedError

    def p(self, y: float, z: float) -> float:  # pragma: no cover - interface
        raise NotImplementedError

    def secant_modulus(self, y: float, z: float) -> float:
        """Secant soil modulus Es = p/y (psi) at deflection ``y`` and depth
        ``z``; uses a deflection floor so it stays finite at y = 0."""
        yy = max(abs(y), _Y_FLOOR)
        return self.p(yy, z) / yy


@dataclass
class LinearPY(PYCurve):
    """A constant-modulus Winkler spring ``p = k*y`` (k in psi).  Mostly for
    verifying the solver against the closed-form subgrade-reaction solution,
    but also a valid simple model."""

    k: float
    p_ult: float = float("inf")

    def pu(self, z: float) -> float:
        return self.p_ult

    def p(self, y: float, z: float) -> float:
        return math.copysign(min(self.k * abs(y), self.p_ult), y)


@dataclass
class SoftClayPY(PYCurve):
    """Matlock (1970) soft-clay p-y curve.

    ``cu`` undrained shear strength (psi), ``b`` pile diameter (in),
    ``gamma`` effective unit weight (pci), ``eps50`` strain at half the
    ultimate stress, ``J`` the empirical factor (0.5 soft / 0.25 stiffer
    field clays).  ``static`` selects the static backbone (the cyclic curve
    flattens at 0.72*pu below the critical depth)."""

    cu: float
    b: float
    gamma: float
    eps50: float = 0.02
    J: float = 0.5
    static: bool = True

    @property
    def y50(self) -> float:
        return 2.5 * self.eps50 * self.b

    def pu(self, z: float) -> float:
        np_ = 3.0 + self.gamma * z / self.cu + self.J * z / self.b
        return min(np_, 9.0) * self.cu * self.b

    def p(self, y: float, z: float) -> float:
        pu = self.pu(z)
        ya = abs(y)
        if ya >= 8.0 * self.y50:
            p = pu
        else:
            p = 0.5 * pu * (ya / self.y50) ** (1.0 / 3.0)
        p = min(p, pu)
        return math.copysign(p, y) if y else 0.0


@dataclass
class StiffClayPY(PYCurve):
    """Reese & Welch (1975) stiff clay *without* free water.

    Same ultimate resistance as Matlock but a flatter backbone
    ``p = 0.5*pu*(y/y50)^0.25`` reaching pu at 16*y50, with
    ``y50 = eps50*b``."""

    cu: float
    b: float
    gamma: float
    eps50: float = 0.007
    J: float = 0.5

    @property
    def y50(self) -> float:
        return self.eps50 * self.b

    def pu(self, z: float) -> float:
        np_ = 3.0 + self.gamma * z / self.cu + self.J * z / self.b
        return min(np_, 9.0) * self.cu * self.b

    def p(self, y: float, z: float) -> float:
        pu = self.pu(z)
        ya = abs(y)
        if ya >= 16.0 * self.y50:
            p = pu
        else:
            p = 0.5 * pu * (ya / self.y50) ** 0.25
        p = min(p, pu)
        return math.copysign(p, y) if y else 0.0


def reese_sand_pu(phi_deg: float, gamma: float, b: float, z: float) -> float:
    """Reese (1974) ultimate sand resistance per unit length (lb/in), the
    lesser of the wedge (shallow) and flow-around (deep) failure values.

    ``phi_deg`` friction angle, ``gamma`` effective unit weight (pci), ``b``
    diameter (in), ``z`` depth (in)."""
    phi = math.radians(phi_deg)
    alpha = phi / 2.0
    beta = math.radians(45.0 + phi_deg / 2.0)
    k0 = 0.4
    ka = math.tan(math.radians(45.0 - phi_deg / 2.0)) ** 2
    tan_bmp = math.tan(beta - phi)
    pst = gamma * z * (
        k0 * z * math.tan(phi) * math.sin(beta) / (tan_bmp * math.cos(alpha))
        + math.tan(beta) / tan_bmp * (b + z * math.tan(beta) * math.tan(alpha))
        + k0 * z * math.tan(beta) * (math.tan(phi) * math.sin(beta) - math.tan(alpha))
        - ka * b
    )
    psd = ka * b * gamma * z * (math.tan(beta) ** 8 - 1.0) + k0 * b * gamma * z * (
        math.tan(phi) * math.tan(beta) ** 4
    )
    return min(pst, psd)


def sand_subgrade_modulus(phi_deg: float, submerged: bool = False) -> float:
    """Typical initial modulus of subgrade reaction k (pci) for sand from
    the API RP 2A / Reese charts, interpolated on friction angle.  These are
    order-of-magnitude design values; use project-specific data when
    available."""
    phis = [28.0, 30.0, 32.0, 34.0, 36.0, 38.0, 40.0]
    above = [20.0, 25.0, 40.0, 60.0, 90.0, 130.0, 200.0]
    below = [15.0, 20.0, 30.0, 45.0, 65.0, 95.0, 140.0]
    table = below if submerged else above
    if phi_deg <= phis[0]:
        return table[0]
    if phi_deg >= phis[-1]:
        return table[-1]
    return float(np.interp(phi_deg, phis, table))


@dataclass
class SandPY(PYCurve):
    """API RP 2A / O'Neill & Murchison sand p-y curve on Reese's ultimate
    resistance: ``p = A*pu*tanh(k*z*y/(A*pu))``.

    ``phi_deg`` friction angle, ``gamma`` effective unit weight (pci), ``b``
    diameter (in), ``k`` initial subgrade modulus (pci; defaults from
    :func:`sand_subgrade_modulus`), ``submerged`` selects the k table, and
    ``static`` the A-factor (``max(3 - 0.8 z/b, 0.9)`` static, 0.9 cyclic).
    """

    phi_deg: float
    gamma: float
    b: float
    k: float | None = None
    submerged: bool = False
    static: bool = True

    def __post_init__(self):
        if self.k is None:
            self.k = sand_subgrade_modulus(self.phi_deg, self.submerged)

    def a_factor(self, z: float) -> float:
        if self.static:
            return max(3.0 - 0.8 * z / self.b, 0.9)
        return 0.9

    def pu(self, z: float) -> float:
        return reese_sand_pu(self.phi_deg, self.gamma, self.b, z)

    def p(self, y: float, z: float) -> float:
        if z <= 0.0:
            return 0.0
        pu = self.pu(z)
        a = self.a_factor(z)
        arg = self.k * z * abs(y) / (a * pu)
        p = a * pu * math.tanh(arg)
        return math.copysign(p, y) if y else 0.0


# ====================================================== FE p-y solver


@dataclass
class LateralPileResult:
    """Depth-wise response of a laterally loaded pile."""

    depth: np.ndarray         # in
    deflection: np.ndarray    # in
    moment: np.ndarray        # lb-in
    shear: np.ndarray         # lb
    soil_reaction: np.ndarray  # lb/in
    iterations: int
    converged: bool

    @property
    def head_deflection(self) -> float:
        return float(self.deflection[0])

    @property
    def max_moment(self) -> float:
        return float(np.max(np.abs(self.moment)))

    @property
    def max_moment_depth(self) -> float:
        return float(self.depth[int(np.argmax(np.abs(self.moment)))])

    @property
    def point_of_fixity(self) -> float | None:
        """Depth (in) of the first sign change in deflection below the head
        -- the classic 'point of fixity'.  None if the pile never reverses."""
        y = self.deflection
        for i in range(1, len(y)):
            if y[i - 1] == 0.0 or y[i] * y[i - 1] < 0.0:
                # linear interpolation to the zero crossing
                z0, z1 = self.depth[i - 1], self.depth[i]
                y0, y1 = y[i - 1], y[i]
                if y1 == y0:
                    return float(z0)
                return float(z0 - y0 * (z1 - z0) / (y1 - y0))
        return None

    def plot(self, ax=None):
        """Four-panel deflection / moment / shear / soil-reaction profile."""
        if ax is None:
            _, ax = plt.subplots(1, 4, figsize=(13, 6), sharey=True)
        d = -self.depth
        ax[0].plot(self.deflection, d, "b")
        ax[0].set_xlabel("Deflection (in)")
        ax[0].set_ylabel("Depth (in)")
        ax[1].plot(self.moment, d, "r")
        ax[1].set_xlabel("Moment (lb-in)")
        ax[2].plot(self.shear, d, "g")
        ax[2].set_xlabel("Shear (lb)")
        ax[3].plot(self.soil_reaction, d, "m")
        ax[3].set_xlabel("Soil reaction (lb/in)")
        for a in ax:
            a.grid(True, alpha=0.3)
            a.axvline(0.0, color="k", lw=0.6)
        return ax[0].get_figure()


def _beam_element_stiffness(ei: float, h: float) -> np.ndarray:
    """Euler-Bernoulli 2-node beam element stiffness (DOF [y_i, th_i, y_j,
    th_j])."""
    h2, h3 = h * h, h * h * h
    return ei / h3 * np.array([
        [12.0, 6.0 * h, -12.0, 6.0 * h],
        [6.0 * h, 4.0 * h2, -6.0 * h, 2.0 * h2],
        [-12.0, -6.0 * h, 12.0, -6.0 * h],
        [6.0 * h, 2.0 * h2, -6.0 * h, 4.0 * h2],
    ])


def solve_lateral_pile(
    curves,
    length: float,
    ei: float,
    shear: float,
    moment: float = 0.0,
    n_elem: int = 100,
    fixed_head: bool = False,
    max_iter: int = 100,
    tol: float = 1.0e-6,
    relax: float = 0.5,
) -> LateralPileResult:
    """Solve a laterally loaded pile by finite elements on nonlinear p-y
    springs (the in-process equivalent of an LPILE run).

    ``curves`` is one :class:`PYCurve` for the whole pile or a callable
    ``curve(z)`` returning the curve at depth ``z`` (in).  ``length`` is the
    embedded length (in), ``ei`` the flexural stiffness (lb-in^2), and
    ``shear``/``moment`` the load applied at the pile head (lb, lb-in).  A
    ``fixed_head`` pile has zero head rotation.  Soil springs use the secant
    modulus and are iterated with under-relaxation ``relax`` until the head
    deflection settles within ``tol``.
    """
    if length <= 0 or ei <= 0 or n_elem < 2:
        raise ValueError("length, ei must be positive and n_elem >= 2")
    curve_at = curves if callable(curves) else (lambda z: curves)

    n_node = n_elem + 1
    h = length / n_elem
    ndof = 2 * n_node
    depth = np.linspace(0.0, length, n_node)
    trib = np.full(n_node, h)
    trib[0] = trib[-1] = h / 2.0

    k_beam = np.zeros((ndof, ndof))
    ke = _beam_element_stiffness(ei, h)
    for e in range(n_elem):
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        k_beam[np.ix_(idx, idx)] += ke

    f = np.zeros(ndof)
    f[0] = shear
    f[1] = moment

    y = np.zeros(n_node)
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        k = k_beam.copy()
        for i in range(n_node):
            es = curve_at(depth[i]).secant_modulus(y[i], depth[i])
            k[2 * i, 2 * i] += es * trib[i]
        if fixed_head:
            # enforce zero rotation at the head (DOF 1)
            k[1, :] = 0.0
            k[:, 1] = 0.0
            k[1, 1] = 1.0
        u = np.linalg.solve(k, f)
        y_new = u[0::2]
        delta = abs(y_new[0] - y[0])
        y = relax * y_new + (1.0 - relax) * y if it > 1 else y_new
        if delta < tol * max(abs(y_new[0]), _Y_FLOOR):
            converged = True
            break

    rot = u[1::2]
    # Recover moments and shears element-by-element from nodal forces.
    moment_arr = np.zeros(n_node)
    shear_arr = np.zeros(n_node)
    counts = np.zeros(n_node)
    for e in range(n_elem):
        ue = np.array([y[e], rot[e], y[e + 1], rot[e + 1]])
        fe = ke @ ue  # [V_i, M_i, V_j, M_j] nodal forces
        moment_arr[e] += -fe[1]
        moment_arr[e + 1] += fe[3]
        shear_arr[e] += fe[0]
        shear_arr[e + 1] += -fe[2]
        counts[e] += 1
        counts[e + 1] += 1
    moment_arr /= np.maximum(counts, 1.0)
    shear_arr /= np.maximum(counts, 1.0)
    soil = np.array([
        curve_at(depth[i]).p(y[i], depth[i]) for i in range(n_node)
    ])

    return LateralPileResult(
        depth=depth, deflection=y, moment=moment_arr, shear=shear_arr,
        soil_reaction=soil, iterations=it, converged=converged,
    )


# ====================================================== Broms ultimate load


@dataclass
class BromsResult:
    """Ultimate lateral load by Broms' method and the governing mechanism."""

    h_ult: float           # lb
    mode: str              # 'short' or 'long'
    h_short: float
    h_long: float
    f_maxmoment: float | None = None   # depth to max moment (in), long mode


def broms_cohesive(
    cu: float,
    b: float,
    length: float,
    yield_moment: float,
    e: float = 0.0,
) -> BromsResult:
    """Broms (1964) ultimate lateral load of a free-headed pile in cohesive
    soil.  Resistance is neglected over the top ``1.5*b`` and taken as
    ``9*cu*b`` below it.

    ``cu`` undrained shear strength (psi), ``b`` diameter (in), ``length``
    embedded length (in), ``yield_moment`` plastic moment of the pile
    section (lb-in), ``e`` load height above ground (in).  The lesser of the
    short-pile (soil) and long-pile (yield) failures governs.
    """
    a = 1.5 * b
    nine = 9.0 * cu * b
    # Long pile: Mmax = Hu(e + 1.5b + 0.5 f) = My, f = Hu/(9 cu b).
    #   (0.5/(9 cu b)) Hu^2 + (e + 1.5b) Hu - My = 0
    qa = 0.5 / nine
    qb = e + a
    h_long = (-qb + math.sqrt(qb * qb + 4.0 * qa * yield_moment)) / (2.0 * qa)
    f = h_long / nine

    # Short pile: rigid rotation about zr, free head.
    #   zr = -e + sqrt(e^2 + e(L+a) + (L^2+a^2)/2);  Hu = 9 cu b (2 zr - a - L)
    # 2*zr >= L + a always (QM-AM on L, a), so h_short is non-negative.
    zr = -e + math.sqrt(e * e + e * (length + a) + (length * length + a * a) / 2.0)
    h_short = nine * (2.0 * zr - a - length)

    if h_short <= h_long:
        return BromsResult(h_short, "short", h_short, h_long)
    return BromsResult(h_long, "long", h_short, h_long, f_maxmoment=a + f)


def broms_cohesionless(
    phi_deg: float,
    gamma: float,
    b: float,
    length: float,
    yield_moment: float,
    e: float = 0.0,
) -> BromsResult:
    """Broms (1964) ultimate lateral load of a free-headed pile in
    cohesionless soil, using a passive resistance ``3*Kp*gamma*z*b``
    (Rankine ``Kp``).

    ``gamma`` effective unit weight (pci), other arguments as in
    :func:`broms_cohesive`.  Short pile: ``Hu = 0.5*Kp*gamma*b*L^3/(e+L)``;
    long pile: ``Mmax = Hu(e + 2f/3) = My`` with ``f = sqrt(Hu/(1.5 Kp gamma
    b))``.
    """
    kp = math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2
    c = 1.5 * kp * gamma * b  # so that shear zero at f: H = c f^2

    h_short = 0.5 * kp * gamma * b * length ** 3 / (e + length)

    # Long pile: solve H(e + 2/3 sqrt(H/c)) = My for H by bisection.
    def resid(h):
        f = math.sqrt(h / c)
        return h * (e + 2.0 * f / 3.0) - yield_moment

    lo, hi = 1.0e-9, max(h_short * 10.0, 1.0)
    while resid(hi) < 0.0:
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if resid(mid) > 0.0:
            hi = mid
        else:
            lo = mid
    h_long = 0.5 * (lo + hi)
    f = math.sqrt(h_long / c)

    if h_short <= h_long:
        return BromsResult(h_short, "short", h_short, h_long)
    return BromsResult(h_long, "long", h_short, h_long, f_maxmoment=f)


# ============================================ characteristic-length methods


@dataclass
class SubgradeResponse:
    """Pile-head response from a closed-form subgrade-reaction analysis."""

    head_deflection: float    # in
    head_slope: float         # rad
    max_moment: float         # lb-in
    characteristic_length: float  # in
    point_of_fixity: float    # in


def subgrade_constant_k(
    k: float, ei: float, shear: float, moment: float = 0.0
) -> SubgradeResponse:
    """Long pile in soil of constant modulus ``k`` (psi) -- the Hetenyi
    semi-infinite beam-on-elastic-foundation solution.

    ``beta = (k/(4 EI))^{1/4}``; head deflection
    ``y0 = 2 beta (P + beta M)/k`` and slope
    ``-2 beta^2 (P + 2 beta M)/k`` for head shear ``P`` and moment ``M``.
    The point of fixity is taken at the rule-of-thumb ``1.4/beta``.
    """
    if k <= 0 or ei <= 0:
        raise ValueError("k and ei must be positive")
    beta = (k / (4.0 * ei)) ** 0.25
    y0 = 2.0 * beta * (shear + beta * moment) / k
    slope = -2.0 * beta ** 2 * (shear + 2.0 * beta * moment) / k
    # Max moment: M0 at head plus the lateral-load contribution ~0.3224 P/beta.
    m_max = abs(moment) + 0.3224 * abs(shear) / beta
    r = 1.0 / beta
    return SubgradeResponse(
        head_deflection=y0, head_slope=slope, max_moment=m_max,
        characteristic_length=r, point_of_fixity=1.4 * r,
    )


#: Matlock-Reese non-dimensional coefficients at the ground surface (Z = 0)
#: for a long, free-headed pile in soil with linearly increasing modulus.
MATLOCK_REESE_AY = 2.435   # deflection from lateral load
MATLOCK_REESE_BY = 1.623   # deflection from moment
MATLOCK_REESE_AM = 0.772   # max moment coefficient from lateral load


def subgrade_linear_nh(
    nh: float, ei: float, shear: float, moment: float = 0.0
) -> SubgradeResponse:
    """Long pile in soil of linearly increasing modulus ``Es = nh*z``
    (``nh`` in pci) -- the Matlock-Reese non-dimensional solution for a
    free head.

    Relative stiffness ``T = (EI/nh)^{1/5}``; ground-line deflection
    ``y_g = Ay P T^3/EI + By M T^2/EI`` and maximum moment ``~Am P T``
    (plus the applied head moment).  Point of fixity is taken at the common
    ``1.8 T`` for sand."""
    if nh <= 0 or ei <= 0:
        raise ValueError("nh and ei must be positive")
    t = (ei / nh) ** 0.2
    y0 = MATLOCK_REESE_AY * shear * t ** 3 / ei + MATLOCK_REESE_BY * moment * t ** 2 / ei
    slope = -1.623 * shear * t ** 2 / ei - 1.75 * moment * t / ei
    m_max = MATLOCK_REESE_AM * abs(shear) * t + abs(moment)
    return SubgradeResponse(
        head_deflection=y0, head_slope=slope, max_moment=m_max,
        characteristic_length=t, point_of_fixity=1.8 * t,
    )
