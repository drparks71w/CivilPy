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

"""Structured-quad meshing for the topology optimizer.

A fixed grid of square Q4 plane-stress elements covers the region's bounding
box; elements whose centroid falls outside the boundary polygon (or inside a
``void``) are *passive empty*, elements inside a ``solid`` keep-in polygon are
*passive full*, and the rest are *active* (optimized).  This "fixed-grid FEM"
handles arbitrary polygons while keeping the regular grid that makes the density
filter and skeletonization trivial — the deliberate trade chosen in
``docs/Rhino Design Philosophy.md`` (structured quads, not a body-fitted mesh).

Conventions follow the classic ``top88`` topology-optimization code so its
element stiffness drops straight into :mod:`~civilpy.structural.stm_topology.simp`:

* grids are ``(nely, nelx)`` with **row 0 at the top**;
* nodes are numbered column-major, ``n = (nely+1)*col + row`` (node 0 top-left);
* element ``(row, col)`` has linear index ``el = row + nely*col`` (Fortran order),
  so ``active.ravel(order="F")`` lines up with :meth:`edof_matrix` rows.
"""

from __future__ import annotations

import numpy as np
from matplotlib.path import Path


class GroundMesh:
    """A structured grid of unit-topology square elements over a region."""

    def __init__(self, problem, nelx: int = 120):
        xmin, ymin, xmax, ymax = problem.bounds()
        width, height = xmax - xmin, ymax - ymin
        self.h = width / nelx
        self.nelx = int(nelx)
        self.nely = max(1, int(round(height / self.h)))
        self.x0, self.y0 = xmin, ymin
        self.width = width
        self.height = self.nely * self.h
        self.ytop = self.y0 + self.height
        self.problem = problem

        # element-centroid coordinates, shape (nely, nelx), row 0 at the top
        cols = (np.arange(self.nelx) + 0.5) * self.h + self.x0
        rows = self.ytop - (np.arange(self.nely) + 0.5) * self.h
        self.cx, self.cy = np.meshgrid(cols, rows)        # both (nely, nelx)
        pts = np.column_stack([self.cx.ravel(), self.cy.ravel()])

        outer = Path(_closed(problem.boundary))
        inside = (outer.contains_points(pts, radius=1e-9)
                  | outer.contains_points(pts, radius=-1e-9))
        inside = inside.reshape(self.nely, self.nelx)
        for hole in problem.voids:
            h_in = Path(_closed(hole)).contains_points(pts).reshape(self.nely, self.nelx)
            inside &= ~h_in
        self.passive_full = np.zeros((self.nely, self.nelx), dtype=bool)
        for blk in problem.solids:
            s_in = Path(_closed(blk)).contains_points(pts).reshape(self.nely, self.nelx)
            self.passive_full |= (s_in & inside)
        self.in_domain = inside
        self.active = inside & ~self.passive_full

    # ── node / DOF bookkeeping ────────────────────────────────────────────

    @property
    def n_nodes(self) -> int:
        return (self.nelx + 1) * (self.nely + 1)

    @property
    def n_dofs(self) -> int:
        return 2 * self.n_nodes

    def edof_matrix(self) -> np.ndarray:
        """``(nelx*nely, 8)`` DOF indices per element, row order ``el = row +
        nely*col``, DOF order (bottom-left, bottom-right, top-right, top-left)
        matching the ``top88`` element stiffness."""
        nely, nelx = self.nely, self.nelx
        ely, elx = np.meshgrid(np.arange(nely), np.arange(nelx), indexing="ij")
        n1 = (nely + 1) * elx + ely          # top-left node of the element
        n2 = (nely + 1) * (elx + 1) + ely     # top-right node
        edof = np.stack([2 * n1 + 2, 2 * n1 + 3, 2 * n2 + 2, 2 * n2 + 3,
                         2 * n2, 2 * n2 + 1, 2 * n1, 2 * n1 + 1], axis=-1)
        return edof.reshape(nely * nelx, 8, order="F")

    # ── map model points to grid nodes (boundary conditions) ──────────────

    def _col_row(self, x: float, y: float) -> tuple[int, int]:
        col = min(max(int(round((x - self.x0) / self.h)), 0), self.nelx)
        row = min(max(int(round((self.ytop - y) / self.h)), 0), self.nely)
        return col, row

    def node_id(self, col: int, row: int) -> int:
        return (self.nely + 1) * col + row

    def nearest_node(self, x: float, y: float) -> int:
        col, row = self._col_row(x, y)
        return self.node_id(col, row)

    def node_xy(self, node_id: int) -> tuple[float, float]:
        col = node_id // (self.nely + 1)
        row = node_id % (self.nely + 1)
        return self.x0 + col * self.h, self.ytop - row * self.h

    def nodes_within(self, x: float, y: float, bearing: float | None) -> list[int]:
        """Grid nodes within ``bearing/2`` of ``(x, y)`` — the set a support
        reaction or applied load is spread over.  Falls back to the single
        nearest node when ``bearing`` is unset or smaller than the mesh."""
        if not bearing or bearing < self.h:
            return [self.nearest_node(x, y)]
        r = bearing / 2.0
        ccol, crow = self._col_row(x, y)
        span = int(np.ceil(r / self.h)) + 1
        found = []
        for col in range(max(ccol - span, 0), min(ccol + span, self.nelx) + 1):
            for row in range(max(crow - span, 0), min(crow + span, self.nely) + 1):
                nx, ny = self.node_xy(self.node_id(col, row))
                if abs(nx - x) <= r + 1e-9 and abs(ny - y) <= r + 1e-9:
                    found.append(self.node_id(col, row))
        return found or [self.nearest_node(x, y)]


def _closed(poly):
    poly = list(poly)
    if poly[0] != poly[-1]:
        poly = poly + [poly[0]]
    return np.asarray(poly, dtype=float)
