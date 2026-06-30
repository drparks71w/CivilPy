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

"""The D-region optimization problem — the data contract between the front end
(manual Python *or* a tagged Rhino ``.3dm``) and the topology-optimization
pipeline.

The same object drives both authoring workflows described in
``docs/Rhino Design Philosophy.md``: *geometry carries what is spatial, tags
carry what is scalar*.  A :class:`DRegionProblem` is the boundary polygon of the
concrete region plus its thickness/material and the supports and loads, and it is
consumed by :mod:`civilpy.structural.stm_topology.simp` (the SIMP optimizer) and
:mod:`~civilpy.structural.stm_topology.extract` (truss extraction).

Units follow the Rhino contract: lengths (boundary, ``thickness``, ``bearing``)
in **feet**, forces in **kips**, ``f_c``/``E`` in **ksi**.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Material:
    """Concrete material for the optimization and the capacity checks."""

    f_c: float = 5.0          # ksi, compressive strength
    E: float | None = None    # ksi, elastic modulus (defaulted from f_c)
    nu: float = 0.2           # Poisson's ratio
    unit_weight: float = 0.145  # kcf, for the AASHTO 5.4.2.4 modulus default

    def __post_init__(self):
        if self.E is None:
            # AASHTO LRFD 5.4.2.4-1: Ec = 120000 K1 wc^2.0 f'c^0.33 (ksi)
            self.E = 120000.0 * (self.unit_weight ** 2.0) * (self.f_c ** 0.33)


@dataclass
class Support:
    """A restrained point on the region boundary (becomes an FEA boundary
    condition and an STM support).  ``bearing`` is the in-plane loaded width
    (feet) over which the reaction is spread; ``None`` defaults to the mesh
    size at solve time."""

    x: float
    y: float
    fix_x: bool = True
    fix_y: bool = True
    bearing: float | None = None


@dataclass
class Load:
    """A factored point load (kips) applied on the region.  Direction is the
    ``(fx, fy)`` vector; ``bearing`` is the in-plane bearing width (feet)."""

    x: float
    y: float
    fx: float = 0.0
    fy: float = 0.0
    bearing: float | None = None

    @property
    def magnitude(self) -> float:
        return math.hypot(self.fx, self.fy)


@dataclass
class DRegionProblem:
    """A concrete D-region to be filled with an optimized strut-and-tie truss.

    Parameters
    ----------
    boundary:
        Outer polygon as ``[(x, y), ...]`` in feet (closed automatically).
    thickness:
        Out-of-plane thickness ``b`` in feet (plane-stress depth).
    material:
        :class:`Material`.
    supports, loads:
        Boundary conditions, shared with the drawn-truss workflow.
    voids, solids:
        Optional inner polygons: ``voids`` are mandatory holes (passive empty),
        ``solids`` are keep-in zones (passive full).
    vol_frac:
        Target fraction of the region to keep as concrete (SIMP constraint).
    """

    boundary: list[tuple[float, float]]
    thickness: float
    material: Material = field(default_factory=Material)
    supports: list[Support] = field(default_factory=list)
    loads: list[Load] = field(default_factory=list)
    voids: list[list[tuple[float, float]]] = field(default_factory=list)
    solids: list[list[tuple[float, float]]] = field(default_factory=list)
    vol_frac: float = 0.3

    # ── convenience builders ──────────────────────────────────────────────

    def add_support(self, x, y, fix_x=True, fix_y=True, bearing=None):
        self.supports.append(Support(x, y, fix_x, fix_y, bearing))
        return self

    def add_load(self, x, y, fx=0.0, fy=0.0, bearing=None):
        self.loads.append(Load(x, y, fx, fy, bearing))
        return self

    @classmethod
    def rectangle(cls, width, height, thickness, origin=(0.0, 0.0), **kwargs):
        """A rectangular region with its lower-left corner at ``origin``."""
        x0, y0 = origin
        boundary = [(x0, y0), (x0 + width, y0),
                    (x0 + width, y0 + height), (x0, y0 + height)]
        return cls(boundary=boundary, thickness=thickness, **kwargs)

    # ── geometry helpers ──────────────────────────────────────────────────

    def bounds(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.boundary]
        ys = [p[1] for p in self.boundary]
        return min(xs), min(ys), max(xs), max(ys)

    # ── Rhino front end ───────────────────────────────────────────────────

    @classmethod
    def from_3dm(cls, path, **kwargs):
        """Read a tagged Rhino ``.3dm`` authored with the *region* workflow
        (a ``stm.kind=region`` closed curve plus supports and loads).  Thin
        wrapper over :func:`civilpy.structural.rhino_stm.problem_from_3dm`
        (needs the optional ``rhino3dm`` dependency)."""
        from civilpy.structural.rhino_stm import problem_from_3dm
        return problem_from_3dm(path, **kwargs)

    # ── pipeline entry point ──────────────────────────────────────────────

    def solve(self, **kwargs):
        """Run the full pipeline: mesh → SIMP → extract truss → solve → check.
        Returns a :class:`civilpy.structural.stm_topology.pipeline.STMResult`."""
        from civilpy.structural.stm_topology.pipeline import optimize_to_stm
        return optimize_to_stm(self, **kwargs)
