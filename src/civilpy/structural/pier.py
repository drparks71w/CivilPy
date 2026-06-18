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

"""Multi-column pier (bent) substructure.

A :class:`PierCap` is the cap beam spanning the columns: it carries the
girder bearing reactions as point loads plus its own self weight and is
analyzed as a continuous beam on the columns (rigid vertical supports) with
a direct-stiffness solver, giving the design shear / moment envelope and the
axial load delivered to each column.  Its flexural and shear design reuse
the AASHTO LRFD reinforced-concrete resistance functions.

A :class:`MultiColumnBent` puts the cap on top of :class:`PierColumn`
columns, distributes the vertical reactions and a lateral force among the
columns, and checks each column with the P-M interaction and
moment-magnification routines already in
:mod:`civilpy.structural.aashto.lrfd.columns` -- a native build, not an
RC-Pier automation.

Units: kip, inch, ksi (matching the LRFD column/concrete checks).  Seismic
demand is out of scope here; supply the lateral force from the governing
non-seismic combination.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from civilpy.structural.aashto.lrfd.columns import (
    RebarLayer,
    moment_magnification,
    rc_column_axial_resistance,
    rc_pm_capacity_check,
)
from civilpy.structural.aashto.lrfd.concrete import (
    rc_rectangular_flexural_resistance,
    rc_shear_resistance,
)
from civilpy.structural.aashto.lrfd.core import CheckResult


@dataclass
class PointLoad:
    """A downward point load ``p`` (kip) at position ``x`` (in) along the
    cap, measured from the left end."""

    x: float
    p: float


def _beam_element_stiffness(ei: float, h: float) -> np.ndarray:
    h2, h3 = h * h, h * h * h
    return ei / h3 * np.array([
        [12.0, 6.0 * h, -12.0, 6.0 * h],
        [6.0 * h, 4.0 * h2, -6.0 * h, 2.0 * h2],
        [-12.0, -6.0 * h, 12.0, -6.0 * h],
        [6.0 * h, 2.0 * h2, -6.0 * h, 4.0 * h2],
    ])


@dataclass
class BeamSolution:
    """Continuous-beam results: nodal coordinates and the moment / shear
    diagrams plus the support reactions."""

    x: np.ndarray
    moment: np.ndarray   # kip-in (sagging positive)
    shear: np.ndarray    # kip
    reactions: dict       # {support_x: reaction kip}

    @property
    def max_moment(self) -> float:
        return float(np.max(np.abs(self.moment)))

    @property
    def max_shear(self) -> float:
        return float(np.max(np.abs(self.shear)))


def solve_continuous_beam(
    length: float,
    ei: float,
    supports: list[float],
    point_loads: list[PointLoad] | None = None,
    udl: float = 0.0,
    n_per_span: int = 12,
) -> BeamSolution:
    """Solve a continuous beam of span ``length`` (in) and stiffness ``ei``
    (kip-in^2) on rigid vertical ``supports`` (x positions, in), under
    downward ``point_loads`` (kip) and a uniform load ``udl`` (kip/in).

    The beam is discretized between breakpoints (supports, load points,
    ends), every segment subdivided into ``n_per_span`` elements so nodal
    moments capture the in-span peaks.  Returns the moment / shear diagrams
    and the support reactions."""
    if length <= 0 or ei <= 0:
        raise ValueError("length and ei must be positive")
    if not supports:
        raise ValueError("at least one support is required")
    point_loads = point_loads or []

    breaks = {0.0, length}
    breaks.update(supports)
    breaks.update(pl.x for pl in point_loads)
    breaks = sorted(b for b in breaks if 0.0 <= b <= length)

    nodes = []
    for a, b in zip(breaks, breaks[1:]):
        seg = np.linspace(a, b, n_per_span + 1)
        nodes.extend(seg[:-1])
    nodes.append(breaks[-1])
    nodes = np.array(sorted(set(np.round(nodes, 6))))
    n = len(nodes)
    ndof = 2 * n

    k = np.zeros((ndof, ndof))
    f = np.zeros(ndof)
    for e in range(n - 1):
        h = nodes[e + 1] - nodes[e]
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        k[np.ix_(idx, idx)] += _beam_element_stiffness(ei, h)
        # consistent nodal loads from the UDL on this element
        f[idx] += udl * np.array([h / 2.0, h * h / 12.0, h / 2.0, -h * h / 12.0])

    def node_of(x):
        return int(np.argmin(np.abs(nodes - x)))

    for pl in point_loads:
        f[2 * node_of(pl.x)] += pl.p

    support_dofs = [2 * node_of(sx) for sx in supports]
    free = [d for d in range(ndof) if d not in support_dofs]
    u = np.zeros(ndof)
    u[free] = np.linalg.solve(k[np.ix_(free, free)], f[free])

    # Reactions at the constrained vertical DOFs.  Reported as the upward
    # support force (= downward load carried), so a column sees positive
    # compression under gravity load.
    full_force = k @ u
    reactions = {}
    for sx, sd in zip(supports, support_dofs):
        reactions[sx] = float(f[sd] - full_force[sd])

    # Recover element-end moments and shears.
    moment = np.zeros(n)
    shear = np.zeros(n)
    counts = np.zeros(n)
    for e in range(n - 1):
        h = nodes[e + 1] - nodes[e]
        ue = u[[2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]]
        fe = _beam_element_stiffness(ei, h) @ ue
        moment[e] += -fe[1]
        moment[e + 1] += fe[3]
        shear[e] += fe[0]
        shear[e + 1] += -fe[2]
        counts[e] += 1
        counts[e + 1] += 1
    moment /= np.maximum(counts, 1.0)
    shear /= np.maximum(counts, 1.0)
    return BeamSolution(x=nodes, moment=moment, shear=shear, reactions=reactions)


@dataclass
class PierCap:
    """Pier cap beam.  ``length`` (in), ``width``/``depth`` the cross
    section (in), ``f_c``/``f_y`` (ksi).  ``column_positions`` are the
    support x-locations; ``loads`` the girder bearing reactions; ``unit_
    weight`` the concrete weight (kci, kip/in^3) for self weight."""

    length: float
    width: float
    depth: float
    column_positions: list[float]
    loads: list[PointLoad] = field(default_factory=list)
    f_c: float = 4.0
    f_y: float = 60.0
    unit_weight: float = 150.0 / 1728.0 / 1000.0  # kci
    e_concrete: float | None = None

    def __post_init__(self):
        if self.e_concrete is None:
            self.e_concrete = 57000.0 * (self.f_c * 1000.0) ** 0.5 / 1000.0  # ksi

    @property
    def self_weight_udl(self) -> float:
        """Self weight as a uniform load (kip/in)."""
        return self.unit_weight * self.width * self.depth

    @property
    def ei(self) -> float:
        return self.e_concrete * self.width * self.depth ** 3 / 12.0

    def analyze(self, n_per_span: int = 12) -> BeamSolution:
        """Continuous-beam analysis for the design force envelope and the
        column reactions."""
        return solve_continuous_beam(
            self.length, self.ei, self.column_positions,
            point_loads=self.loads, udl=self.self_weight_udl,
            n_per_span=n_per_span,
        )

    def column_reactions(self) -> dict:
        """Axial load delivered to each column top (kip)."""
        return self.analyze().reactions

    def flexure_check(
        self, a_s: float, cover: float = 3.0, bar_dia: float = 1.128,
        solution: BeamSolution | None = None,
    ) -> CheckResult:
        """Flexural check at the maximum cap moment, reusing
        :func:`rc_rectangular_flexural_resistance`.  ``a_s`` is the tension
        steel (in^2)."""
        sol = solution or self.analyze()
        d_s = self.depth - cover - bar_dia / 2.0
        return rc_rectangular_flexural_resistance(
            a_s=a_s, f_y=self.f_y, f_c=self.f_c, b=self.width, d_s=d_s,
            m_u=sol.max_moment,
        )

    def shear_check(
        self, a_v: float = 0.0, s: float = 12.0, cover: float = 3.0,
        bar_dia: float = 1.128, solution: BeamSolution | None = None,
    ) -> CheckResult:
        """Shear check at the maximum cap shear, reusing
        :func:`rc_shear_resistance`."""
        sol = solution or self.analyze()
        d_s = self.depth - cover - bar_dia / 2.0
        d_v = max(0.9 * d_s, 0.72 * self.depth)
        return rc_shear_resistance(
            b_v=self.width, d_v=d_v, f_c=self.f_c, v_u=sol.max_shear,
            a_v=a_v, s=s, f_y=self.f_y,
        )


@dataclass
class PierColumn:
    """One bent column.  ``height`` (in) is the clear height; the section is
    rectangular ``b`` x ``h`` or circular ``diameter`` (in) with ``layers``
    of longitudinal bars; ``f_c``/``f_y`` (ksi).  ``fixity`` is
    ``"fixed-fixed"`` (cap restrains the top against rotation) or
    ``"fixed-free"`` (cantilever)."""

    height: float
    layers: list[RebarLayer]
    f_c: float = 4.0
    f_y: float = 60.0
    b: float | None = None
    h: float | None = None
    diameter: float | None = None
    spiral: bool = False
    fixity: str = "fixed-fixed"

    def __post_init__(self):
        if self.diameter is None and (self.b is None or self.h is None):
            raise ValueError("give a diameter or both b and h")
        if self.fixity not in ("fixed-fixed", "fixed-free"):
            raise ValueError("fixity must be 'fixed-fixed' or 'fixed-free'")

    @property
    def gross_area(self) -> float:
        if self.diameter is not None:
            return 3.141592653589793 * self.diameter ** 2 / 4.0
        return self.b * self.h

    @property
    def moment_of_inertia(self) -> float:
        if self.diameter is not None:
            return 3.141592653589793 * self.diameter ** 4 / 64.0
        return self.b * self.h ** 3 / 12.0

    def lateral_stiffness(self, e_concrete: float) -> float:
        """Translational stiffness of the column top (kip/in): 12EI/L^3 for
        a fixed-fixed column, 3EI/L^3 for a cantilever."""
        coeff = 12.0 if self.fixity == "fixed-fixed" else 3.0
        return coeff * e_concrete * self.moment_of_inertia / self.height ** 3

    def lateral_moment(self, shear: float) -> float:
        """Column moment (kip-in) from a column shear ``shear`` (kip):
        V*L/2 fixed-fixed, V*L cantilever."""
        if self.fixity == "fixed-fixed":
            return shear * self.height / 2.0
        return shear * self.height

    def axial_resistance(self, p_u: float | None = None) -> CheckResult:
        a_st = sum(layer.area for layer in self.layers)
        return rc_column_axial_resistance(
            a_g=self.gross_area, a_st=a_st, f_c=self.f_c, f_y=self.f_y,
            p_u=p_u, spiral=self.spiral,
        )

    def pm_check(self, p_u: float, m_u: float) -> CheckResult:
        """P-M interaction adequacy at factored ``p_u`` (kip) and ``m_u``
        (kip-in), via the strain-compatibility diagram."""
        return rc_pm_capacity_check(
            p_u=p_u, m_u=m_u, layers=self.layers, f_c=self.f_c, f_y=self.f_y,
            h=self.h, b=self.b, diameter=self.diameter, spiral=self.spiral,
        )

    def magnified_moment(
        self, p_u: float, m_u: float, k_factor: float = 1.2,
        e_concrete: float | None = None,
    ) -> tuple[float, CheckResult]:
        """Slenderness-magnified moment (kip-in).  The critical buckling
        load uses the cracked-section ``EI = 0.25*Ec*Ig`` (5.6.4.3) and the
        effective length ``k_factor*height``.  Returns the magnified moment
        and the magnifier CheckResult."""
        ec = e_concrete if e_concrete is not None else 57000.0 * (
            self.f_c * 1000.0
        ) ** 0.5 / 1000.0
        ei = 0.25 * ec * self.moment_of_inertia
        klu = k_factor * self.height
        p_e = 3.141592653589793 ** 2 * ei / klu ** 2
        mag = moment_magnification(p_u=p_u, p_e=p_e, m_2=m_u if m_u else 1.0)
        return mag.capacity * m_u, mag


@dataclass
class BentResult:
    """Per-column demands and checks for a multi-column bent."""

    column_axials: list[float]
    column_shears: list[float]
    column_moments: list[float]
    cap_solution: BeamSolution
    pm_checks: list[CheckResult]

    @property
    def all_columns_ok(self) -> bool:
        return all(c.ok for c in self.pm_checks)


class MultiColumnBent:
    """A pier cap on multiple columns, with vertical girder reactions and a
    lateral force distributed to the columns by their stiffness."""

    def __init__(
        self,
        cap: PierCap,
        columns: list[PierColumn],
        lateral_force: float = 0.0,
        column_dead_load: float | list[float] = 0.0,
    ):
        if len(columns) != len(cap.column_positions):
            raise ValueError("need one column per cap support position")
        self.cap = cap
        self.columns = columns
        self.lateral_force = lateral_force
        if isinstance(column_dead_load, (int, float)):
            self.column_dead_load = [float(column_dead_load)] * len(columns)
        else:
            if len(column_dead_load) != len(columns):
                raise ValueError("column_dead_load list must match the columns")
            self.column_dead_load = [float(v) for v in column_dead_load]

    def lateral_distribution(self) -> list[float]:
        """Lateral shear in each column (kip), in proportion to its
        translational stiffness."""
        ks = [c.lateral_stiffness(self.cap.e_concrete) for c in self.columns]
        total = sum(ks)
        return [self.lateral_force * ki / total for ki in ks]

    def analyze(self) -> BentResult:
        """Distribute loads to the columns and run each column's P-M check
        (with the moment magnified for slenderness)."""
        sol = self.cap.analyze()
        shears = self.lateral_distribution()
        axials, moments, checks = [], [], []
        for i, (col, pos, dead) in enumerate(zip(
            self.columns, self.cap.column_positions, self.column_dead_load
        )):
            p_u = sol.reactions[pos] + dead
            m_lat = col.lateral_moment(shears[i])
            m_mag, _ = col.magnified_moment(p_u, m_lat, e_concrete=self.cap.e_concrete)
            axials.append(p_u)
            moments.append(m_mag)
            checks.append(col.pm_check(p_u, m_mag))
        return BentResult(
            column_axials=axials, column_shears=shears,
            column_moments=moments, cap_solution=sol, pm_checks=checks,
        )
