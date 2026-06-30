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

"""End-to-end strut-and-tie solver pipeline: region → mesh → SIMP → truss →
solve → design report (Phases 1–5 of ``docs/StrutAndTieSolver.md``).

``optimize_to_stm`` is the one call the notebooks (manual or Rhino) use.  It is
also reachable as :meth:`DRegionProblem.solve`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .mesh import GroundMesh
from .simp import optimize_density, DensityResult
from .extract import extract_truss, refine_truss, is_stable
from . import cost as _cost


@dataclass
class STMResult:
    """Everything the pipeline produces, ready for review or write-back."""

    problem: object
    density: DensityResult
    model: object               # solved StrutAndTieModel
    forces: dict
    report: _cost.DesignReport
    merge_used: float
    stable: bool

    # convenience pass-throughs
    @property
    def mesh(self):
        return self.density.mesh

    def summary(self) -> str:
        m = self.model
        lines = [
            f"Strut-and-Tie result: {len(m.nodes)} nodes, {len(m.members)} members "
            f"(DoI={m.degree_of_indeterminacy()}, {'stable' if self.stable else 'UNSTABLE'})",
            f"  mesh {self.mesh.nelx}x{self.mesh.nely}, vol_frac="
            f"{self.problem.vol_frac:.2f}",
        ]
        ties = [t for t in self.report.ties]
        if ties:
            tmax = max(ties, key=lambda t: t.force)
            lines.append(
                f"  governing tie {tmax.member}: {tmax.force:.1f} kip → "
                f"{tmax.bar_count}x #{tmax.bar_size} (As={tmax.a_st_provided:.2f} in^2, "
                f"ratio={tmax.check.ratio:.2f})")
        if self.report.cost:
            c = self.report.cost
            lines.append(
                f"  take-off: {c.concrete_cy:.1f} cy concrete + {c.steel_lb:.0f} lb steel "
                f"→ ${c.total:,.0f}")
        return "\n".join(lines)

    def plot(self, ax=None):
        """Density field with the extracted truss overlaid."""
        import matplotlib.pyplot as plt
        if ax is None:
            ax = plt.figure(figsize=(10, 6)).add_subplot(1, 1, 1)
        mesh = self.mesh
        ax.imshow(self.density.density, cmap="Greys", origin="upper",
                  extent=[mesh.x0, mesh.x0 + mesh.width, mesh.y0, mesh.ytop],
                  alpha=0.85, vmin=0, vmax=1)
        self.model.plot(ax=ax)
        ax.set_title("SIMP density + extracted strut-and-tie truss")
        return ax.get_figure()


def optimize_to_stm(problem, *, nelx: int = 120, threshold: float = 0.3,
                    merge: float | None = None, penal: float = 3.0,
                    rmin: float | None = None, max_iter: int = 120,
                    fully_stressed: bool = True, verbose: bool = False,
                    **price_kwargs) -> STMResult:
    """Run the full pipeline and return an :class:`STMResult`.

    The extraction merge tolerance is escalated automatically until the truss
    is stable (statically determinate or solvable indeterminate) so the caller
    gets a usable model without hand-tuning.
    """
    mesh = GroundMesh(problem, nelx=nelx)
    density = optimize_density(mesh, vol_frac=problem.vol_frac, penal=penal,
                               rmin=rmin, max_iter=max_iter, nu=problem.material.nu,
                               verbose=verbose)

    model, used, stable = _extract_stable(density, threshold, merge, verbose)

    forces = {}
    report = _cost.DesignReport()
    try:
        if fully_stressed:
            forces = model.solve_fully_stressed()
        else:
            forces = model.solve(method="auto")
        report = _cost.design_report(model, problem, density, threshold=threshold,
                                     **price_kwargs)
    except ValueError as exc:
        # extraction produced a mechanism we could not stabilize; return the
        # geometry and density for review rather than crashing.
        stable = False
        if verbose:
            print(f"  could not solve extracted truss: {exc}")

    return STMResult(problem=problem, density=density, model=model, forces=forces,
                     report=report, merge_used=used, stable=stable)


def _extract_stable(density, threshold, merge, verbose):
    """Extract a skeleton truss and complete it into a stable strut-and-tie
    model with the ground-structure refinement.

    Skeleton tracing finds the struts but misses the tension chords, so the raw
    truss is usually a mechanism.  Instead of merging joints until it collapses,
    :func:`~civilpy.structural.stm_topology.extract.refine_truss` lays in the
    members that run through solid material and prunes the dead ones.  A couple
    of coarser merges are tried only as a fallback if that still leaves a
    mechanism.
    """
    base = merge if merge is not None else max(3.0, 0.05 * density.mesh.nelx)
    candidates = [base] if merge is not None else [base * f for f in (1.0, 1.5, 2.0)]
    last = None
    for mg in candidates:
        model = extract_truss(density, threshold=threshold, merge=mg)
        if len(model.nodes) >= 3:
            refine_truss(model, density)
        last = (model, mg)
        if is_stable(model):
            if verbose:
                print(f"  merge={mg:.1f}: refined to {len(model.nodes)} nodes, "
                      f"{len(model.members)} members (stable)")
            return model, mg, True
        if verbose:
            print(f"  merge={mg:.1f}: still a mechanism, escalating")
    model, mg = last
    return model, mg, False
