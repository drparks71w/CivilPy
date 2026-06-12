"""Strut-and-tie modeling: build a truss idealization of a D-region, solve
member forces by the method of joints, and draw the classic STM diagram
(struts dashed, ties solid, forces labeled).

Conventions match :mod:`civilpy.structural.beam_bending`: kips and feet
(or any consistent unit pair), plot methods take an optional ``ax`` and
return the figure for Jupyter use.  Tension is positive, so positive
member forces are ties and negative are struts.

The AASHTO LRFD capacity side (tie strength 5.8.2.4, node crushing
5.8.2.5, crack-control reinforcement 5.8.2.6) lives in
:mod:`civilpy.structural.aashto.lrfd.stm` and takes the solved forces
directly.

Examples
--------
Deep beam idealized as a triangular truss — supports 8 ft apart, load at
midspan top, 4 ft deep:

>>> stm = StrutAndTieModel()
>>> stm.add_node("A", 0, 0)
>>> stm.add_node("B", 8, 0)
>>> stm.add_node("C", 4, 4)
>>> stm.add_member("A", "C")
>>> stm.add_member("B", "C")
>>> stm.add_member("A", "B")
>>> stm.add_support("A", fix_x=True, fix_y=True)
>>> stm.add_support("B", fix_y=True)
>>> stm.add_load("C", fy=-100)
>>> forces = stm.solve()
>>> round(forces[("A", "B")], 2)  # bottom chord is a tie (+)
50.0
>>> round(forces[("A", "C")], 2)  # diagonals are struts (-)
-70.71
"""

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

import math

import matplotlib.pyplot as plt
import numpy as np


class StrutAndTieModel:
    """A pin-jointed truss idealization of a disturbed region."""

    def __init__(self):
        self.nodes: dict[str, tuple[float, float]] = {}
        self.members: list[tuple[str, str]] = []
        self.loads: dict[str, list[float]] = {}
        self.supports: dict[str, tuple[bool, bool]] = {}
        self.forces: dict[tuple[str, str], float] | None = None
        self.reactions: dict[str, list[float]] | None = None

    # ── Model building ────────────────────────────────────────────────────

    def add_node(self, label: str, x: float, y: float):
        self.nodes[label] = (float(x), float(y))

    def add_member(self, node_a: str, node_b: str):
        for n in (node_a, node_b):
            if n not in self.nodes:
                raise KeyError(f"node {n!r} not defined")
        self.members.append((node_a, node_b))

    def add_load(self, node: str, fx: float = 0.0, fy: float = 0.0):
        """Applied joint load (kips); fy negative = downward."""
        load = self.loads.setdefault(node, [0.0, 0.0])
        load[0] += fx
        load[1] += fy

    def add_support(self, node: str, fix_x: bool = False, fix_y: bool = False):
        self.supports[node] = (fix_x, fix_y)

    # ── Analysis ──────────────────────────────────────────────────────────

    def _direction(self, a: str, b: str) -> tuple[float, float, float]:
        (xa, ya), (xb, yb) = self.nodes[a], self.nodes[b]
        length = math.hypot(xb - xa, yb - ya)
        return (xb - xa) / length, (yb - ya) / length, length

    def solve(self) -> dict[tuple[str, str], float]:
        """Solve member forces and reactions by the method of joints.

        The model must be statically determinate and stable:
        members + reactions = 2 * nodes.  Returns {(a, b): force} with
        tension positive (tie) and compression negative (strut); reactions
        land in ``self.reactions``.
        """
        node_index = {label: i for i, label in enumerate(self.nodes)}
        n_eq = 2 * len(self.nodes)
        reaction_cols = [
            (node, dof)
            for node, (fx, fy) in self.supports.items()
            for dof, fixed in enumerate((fx, fy)) if fixed
        ]
        n_unknowns = len(self.members) + len(reaction_cols)
        if n_unknowns != n_eq:
            raise ValueError(
                f"statically indeterminate or unstable model: "
                f"{len(self.members)} members + {len(reaction_cols)} "
                f"reactions != 2*{len(self.nodes)} equations"
            )

        a = np.zeros((n_eq, n_unknowns))
        rhs = np.zeros(n_eq)
        for m, (na, nb) in enumerate(self.members):
            cx, cy, _ = self._direction(na, nb)
            ia, ib = node_index[na], node_index[nb]
            # tension pulls each joint toward the other end
            a[2 * ia, m] += cx
            a[2 * ia + 1, m] += cy
            a[2 * ib, m] -= cx
            a[2 * ib + 1, m] -= cy
        for r, (node, dof) in enumerate(reaction_cols):
            a[2 * node_index[node] + dof, len(self.members) + r] = 1.0
        for node, (fx, fy) in self.loads.items():
            rhs[2 * node_index[node]] -= fx
            rhs[2 * node_index[node] + 1] -= fy

        try:
            solution = np.linalg.solve(a, rhs)
        except np.linalg.LinAlgError as exc:
            raise ValueError(f"unstable model geometry: {exc}") from exc

        self.forces = {mem: solution[i] for i, mem in enumerate(self.members)}
        self.reactions = {}
        for r, (node, dof) in enumerate(reaction_cols):
            self.reactions.setdefault(node, [0.0, 0.0])[dof] = (
                solution[len(self.members) + r]
            )
        return self.forces

    # ── Visualization ─────────────────────────────────────────────────────

    def plot(self, ax=None, force_units: str = "kips",
             show_reactions: bool = True):
        """Draw the strut-and-tie diagram: ties solid red, struts dashed
        blue with width scaled to force magnitude, joint loads as green
        arrows, supports as triangles.  Solves first if needed.  Returns
        the figure."""
        if self.forces is None:
            self.solve()
        if ax is None:
            ax = plt.figure(figsize=(8, 6)).add_subplot(1, 1, 1)

        f_max = max((abs(f) for f in self.forces.values()), default=1.0) or 1.0
        for (na, nb), force in self.forces.items():
            (xa, ya), (xb, yb) = self.nodes[na], self.nodes[nb]
            tie = force > 1e-9
            lw = 1.0 + 4.0 * abs(force) / f_max
            ax.plot([xa, xb], [ya, yb],
                    color="r" if tie else "b",
                    ls="-" if tie else (0, (6, 3)),
                    lw=lw, solid_capstyle="round", zorder=2)
            ax.annotate(f"{force:+.4g}",
                        ((xa + xb) / 2.0, (ya + yb) / 2.0),
                        textcoords="offset points", xytext=(4, 4),
                        color="r" if tie else "b", fontsize=9, zorder=4)

        span = max(
            max(x for x, _ in self.nodes.values())
            - min(x for x, _ in self.nodes.values()), 1.0
        )
        arrow_len = 0.18 * span
        for node, (fx, fy) in self.loads.items():
            x, y = self.nodes[node]
            mag = math.hypot(fx, fy)
            if mag == 0.0:
                continue
            dx, dy = fx / mag * arrow_len, fy / mag * arrow_len
            ax.annotate("", xy=(x, y), xytext=(x - dx, y - dy),
                        arrowprops=dict(arrowstyle="-|>", color="g", lw=2.0),
                        zorder=5)
            ax.annotate(f"{mag:.4g} {force_units}",
                        (x - dx, y - dy), textcoords="offset points",
                        xytext=(4, 4), color="g", zorder=5)

        for node, (fix_x, fix_y) in self.supports.items():
            x, y = self.nodes[node]
            marker = "^" if fix_y else "o"
            ax.plot(x, y - 0.03 * span, marker=marker, color="k",
                    markersize=14, zorder=3, clip_on=False)
            if show_reactions and self.reactions and node in self.reactions:
                rx, ry = self.reactions[node]
                label = ", ".join(
                    f"{v:+.4g}" for v, fixed in zip((rx, ry), (fix_x, fix_y))
                    if fixed
                )
                ax.annotate(f"R = {label}", (x, y),
                            textcoords="offset points", xytext=(6, -18),
                            fontsize=9)

        for label, (x, y) in self.nodes.items():
            ax.plot(x, y, "ko", markersize=5, zorder=6)
            ax.annotate(label, (x, y), textcoords="offset points",
                        xytext=(-10, 6), fontweight="bold", zorder=6)

        ax.plot([], [], "r-", label="tie (tension)")
        ax.plot([], [], "b--", label="strut (compression)")
        ax.legend(loc="best", fontsize=9)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_title("Strut-and-Tie Model")
        ax.grid(True, alpha=0.25)
        return ax.get_figure()
