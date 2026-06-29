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

"""SIMP topology optimization (Phase 2 of the strut-and-tie solver roadmap).

Solid Isotropic Material with Penalization on the structured quad grid: a
linear plane-stress FEA (the ``top88`` Q4 element) inside an optimality-criteria
loop with a density filter, driven by the region's supports and loads.  The
result is a ``(nely, nelx)`` density field — the picture of where concrete wants
to be — which :mod:`~civilpy.structural.stm_topology.extract` turns into a truss.

Pure NumPy/SciPy; no ``scikit-fem`` needed because the structured grid lets us
use the closed-form element stiffness directly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

from .mesh import GroundMesh


def element_stiffness(nu: float) -> np.ndarray:
    """8x8 plane-stress Q4 element stiffness for unit modulus and size
    (Andreassen et al. 2011, *Efficient topology optimization in MATLAB*)."""
    k = np.array([
        1 / 2 - nu / 6, 1 / 8 + nu / 8, -1 / 4 - nu / 12, -1 / 8 + 3 * nu / 8,
        -1 / 4 + nu / 12, -1 / 8 - nu / 8, nu / 6, 1 / 8 - 3 * nu / 8,
    ])
    ke = 1 / (1 - nu ** 2) * np.array([
        [k[0], k[1], k[2], k[3], k[4], k[5], k[6], k[7]],
        [k[1], k[0], k[7], k[6], k[5], k[4], k[3], k[2]],
        [k[2], k[7], k[0], k[5], k[6], k[3], k[4], k[1]],
        [k[3], k[6], k[5], k[0], k[7], k[2], k[1], k[4]],
        [k[4], k[5], k[6], k[7], k[0], k[1], k[2], k[3]],
        [k[5], k[4], k[3], k[2], k[1], k[0], k[7], k[6]],
        [k[6], k[3], k[4], k[1], k[2], k[7], k[0], k[5]],
        [k[7], k[2], k[1], k[4], k[3], k[6], k[5], k[0]],
    ])
    return ke


def _filter_matrix(nelx, nely, rmin):
    """Cone-weighted density-filter operator H (normalized rows)."""
    span = int(np.ceil(rmin)) - 1
    iH, jH, sH = [], [], []
    for i in range(nelx):
        for j in range(nely):
            e1 = j + i * nely
            for ii in range(max(i - span, 0), min(i + span + 1, nelx)):
                for jj in range(max(j - span, 0), min(j + span + 1, nely)):
                    e2 = jj + ii * nely
                    w = rmin - np.hypot(i - ii, j - jj)
                    if w > 0:
                        iH.append(e1); jH.append(e2); sH.append(w)
    H = sp.coo_matrix((sH, (iH, jH)), shape=(nelx * nely, nelx * nely)).tocsr()
    Hs = np.asarray(H.sum(axis=1)).ravel()
    return H, Hs


@dataclass
class DensityResult:
    """Output of the SIMP optimizer."""

    density: np.ndarray          # (nely, nelx), passive applied
    mesh: GroundMesh
    compliance: float
    iterations: int
    history: list                # compliance per iteration


def optimize_density(mesh: GroundMesh, *, vol_frac: float = 0.3, penal: float = 3.0,
                     rmin: float | None = None, max_iter: int = 120,
                     move: float = 0.2, tol: float = 0.01,
                     nu: float = 0.2, verbose: bool = False) -> DensityResult:
    """Run SIMP on ``mesh`` and return the optimized density field.

    ``vol_frac`` is the target solid fraction of the *active* (optimizable)
    region.  ``rmin`` (filter radius, element units) defaults to ~3% of the
    width.  Supports/loads come from ``mesh.problem``.
    """
    nelx, nely = mesh.nelx, mesh.nely
    n = nelx * nely
    if rmin is None:
        rmin = max(1.5, 0.04 * nelx)

    KE = element_stiffness(nu)
    edofMat = mesh.edof_matrix()
    iK = np.kron(edofMat, np.ones((8, 1))).flatten()
    jK = np.kron(edofMat, np.ones((1, 8))).flatten()
    ndof = mesh.n_dofs

    # loads → global force vector, spread over each load's bearing nodes
    F = np.zeros(ndof)
    for ld in mesh.problem.loads:
        nodes = mesh.nodes_within(ld.x, ld.y, ld.bearing)
        for nid in nodes:
            F[2 * nid] += ld.fx / len(nodes)
            F[2 * nid + 1] += ld.fy / len(nodes)
    # supports → fixed DOF
    fixed = []
    for sp_ in mesh.problem.supports:
        for nid in mesh.nodes_within(sp_.x, sp_.y, sp_.bearing):
            if sp_.fix_x:
                fixed.append(2 * nid)
            if sp_.fix_y:
                fixed.append(2 * nid + 1)
    fixed = np.unique(fixed)
    free = np.setdiff1d(np.arange(ndof), fixed)

    H, Hs = _filter_matrix(nelx, nely, rmin)

    active = mesh.active.ravel(order="F")
    passive_full = mesh.passive_full.ravel(order="F")
    n_active = int(active.sum())
    if n_active == 0:
        raise ValueError("no active elements — check the boundary polygon")
    if not F.any():
        raise ValueError("no loads applied — add at least one Load to the problem")
    if len(fixed) == 0:
        raise ValueError("no supports — add at least one fixed Support")

    Emin, E0 = 1e-9, 1.0
    x = np.zeros(n)
    x[active] = vol_frac
    x[passive_full] = 1.0
    xPhys = x.copy()

    history = []
    change = 1.0
    it = 0
    while change > tol and it < max_iter:
        it += 1
        sK = (KE.flatten()[:, None] *
              (Emin + xPhys ** penal * (E0 - Emin))[None, :]).flatten(order="F")
        K = sp.coo_matrix((sK, (iK, jK)), shape=(ndof, ndof)).tocsc()
        K = K[free, :][:, free]
        U = np.zeros(ndof)
        U[free] = spsolve(K, F[free])

        ce = np.einsum("ij,jk,ik->i", U[edofMat], KE, U[edofMat])
        c = float(((Emin + xPhys ** penal * (E0 - Emin)) * ce).sum())
        dc = -penal * xPhys ** (penal - 1) * (E0 - Emin) * ce
        dv = np.ones(n)

        # density filtering of sensitivities
        dc = np.asarray(H @ (dc / Hs))
        dv = np.asarray(H @ (dv / Hs))

        # optimality-criteria update on active elements only
        xnew = _oc_update(x, dc, dv, active, passive_full, vol_frac, move, n_active)
        xPhys = np.asarray(H @ xnew) / Hs
        xPhys[passive_full] = 1.0
        xPhys[~active & ~passive_full] = 0.0
        change = float(np.abs(xnew[active] - x[active]).max()) if n_active else 0.0
        x = xnew
        history.append(c)
        if verbose:
            print(f"it {it:3d}  c={c:11.4f}  vol={xPhys[active].mean():.3f}  ch={change:.3f}")

    density = xPhys.reshape(nely, nelx, order="F")
    return DensityResult(density=density, mesh=mesh, compliance=history[-1] if history else 0.0,
                         iterations=it, history=history)


def _oc_update(x, dc, dv, active, passive_full, vol_frac, move, n_active):
    """Bisection optimality-criteria update, constrained to active elements
    with the target volume measured over the active region."""
    l1, l2 = 1e-9, 1e9
    target = vol_frac * n_active
    xnew = x.copy()
    a = active
    while (l2 - l1) / (l1 + l2) > 1e-3:
        lmid = 0.5 * (l1 + l2)
        be = -dc[a] / (dv[a] * lmid + 1e-30)
        cand = x[a] * np.sqrt(np.clip(be, 0, None))
        step = np.clip(cand, x[a] - move, x[a] + move)
        xa = np.clip(step, 0.0, 1.0)
        xnew[a] = xa
        if xa.sum() > target:
            l1 = lmid
        else:
            l2 = lmid
    xnew[passive_full] = 1.0
    xnew[~active & ~passive_full] = 0.0
    return xnew
