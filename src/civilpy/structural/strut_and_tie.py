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
import warnings

import matplotlib.pyplot as plt
import numpy as np


class StrutAndTieModel:
    """A pin-jointed truss idealization of a disturbed region."""

    def __init__(self, E: float = 1.0):
        self.nodes: dict[str, tuple[float, float]] = {}
        self.members: list[tuple[str, str]] = []
        # ``stm.member`` hints: member -> "tie"/"strut" override (auto members
        # are absent here -- classified from the solved sign).
        self.member_types: dict[tuple[str, str], str] = {}
        # member cross-sectional areas (relative stiffness for the DSM solver).
        self.areas: dict[tuple[str, str], float] = {}
        self.loads: dict[str, list[float]] = {}
        self.supports: dict[str, tuple[bool, bool]] = {}
        self.forces: dict[tuple[str, str], float] | None = None
        self.reactions: dict[str, list[float]] | None = None
        # Elastic modulus used only by the indeterminate (direct-stiffness)
        # solver; it cancels out for a statically determinate truss.  Member
        # axial stiffness is ``E * area / length``.
        self.E = float(E)

    # ── Rhino interchange ─────────────────────────────────────────────────

    @classmethod
    def from_3dm(cls, path, **kwargs):
        """Build a model from a tagged Rhino ``.3dm`` file.  Thin wrapper over
        :func:`civilpy.structural.rhino_stm.model_from_3dm` (needs the optional
        ``rhino3dm`` dependency)."""
        from civilpy.structural.rhino_stm import model_from_3dm
        return model_from_3dm(path, **kwargs)

    def to_3dm(self, path, **kwargs):
        """Write this model to a tagged ``.3dm`` file (members as lines,
        supports as symbol blocks, loads as arrows)."""
        from civilpy.structural.rhino_stm import model_to_3dm
        return model_to_3dm(self, path, **kwargs)

    # ── Canonical-hub interconversion ─────────────────────────────────────

    @classmethod
    def from_structural_model(cls, hub, *, plane="auto"):
        """Project a canonical :class:`~civilpy.structural.structural_model.
        StructuralModel` hub down to this 2D model (default elevation maps
        X->x, Z->y).  The inverse of :meth:`to_structural_model`.

        The hub's full 6-DOF restraints collapse to the in-plane
        ``(fix_x, fix_y)`` the truss solver consumes, and 3D load vectors are
        projected onto the plane.  ``plane="auto"`` infers the drawing plane
        from the node coordinates.  This is the reader half of stage S3 in
        ``docs/Rhino Design Philosophy.md`` -- it lets ``from_3dm`` parse once
        into the hub and project, instead of carrying a second parser.
        """
        from civilpy.structural.rhino_stm import _detect_plane, _project
        if plane == "auto":
            plane = _detect_plane([n.coords for n in hub.nodes.values()])
        m = cls()
        label_of = {}
        for node in hub.nodes.values():
            label = node.label or node.id
            label_of[node.id] = label
            x, y = _project(node.coords, plane)
            m.add_node(label, x, y)
        for elem in hub.elements.values():
            m.add_member(label_of[elem.node_a], label_of[elem.node_b],
                         member_type=elem.member_type)
        for restraint in hub.restraints.values():
            fix_x, fix_y = restraint.to_2d()
            m.add_support(label_of[restraint.node_id], fix_x=fix_x, fix_y=fix_y)
        for load in hub.loads:
            fx, fy = _project((load.fx, load.fy, load.fz), plane)
            m.add_load(label_of[load.node_id], fx=fx, fy=fy)
        return m

    def to_structural_model(self, *, plane="XZ"):
        """Lift this 2D model into the canonical
        :class:`~civilpy.structural.structural_model.StructuralModel` hub (the
        inverse of :meth:`from_structural_model`).

        In-plane coordinates and forces are placed in the chosen world
        ``plane``; the 2D ``(fix_x, fix_y)`` fixity widens to a 6-DOF restraint
        with the remaining DOF free.  Solved member forces and reactions, if
        present, are carried across into a :class:`Result`.
        """
        from civilpy.structural.structural_model import Result, StructuralModel
        from civilpy.structural.rhino_stm import _unproject
        hub = StructuralModel()
        ids = {}
        for label, (x, y) in self.nodes.items():
            X, Y, Z = _unproject((x, y), plane)
            ids[label] = hub.add_node(X, Y, Z, label=label).id
        member_ids = {}
        for a, b in self.members:
            member_ids[(a, b)] = hub.add_element(
                ids[a], ids[b],
                member_type=self.member_types.get((a, b), "auto")).id
        for node, (fix_x, fix_y) in self.supports.items():
            hub.add_restraint(ids[node], fix_x=fix_x, fix_y=fix_y)
        for node, (fx, fy) in self.loads.items():
            FX, FY, FZ = _unproject((fx, fy), plane)
            hub.add_load(ids[node], fx=FX, fy=FY, fz=FZ)
        if self.forces is not None:
            result = Result(case="default")
            for member, force in self.forces.items():
                result.element_forces[member_ids[member]] = force
            for node, (rx, ry) in (self.reactions or {}).items():
                RX, RY, RZ = _unproject((rx, ry), plane)
                result.reactions[ids[node]] = (RX, RY, RZ, 0.0, 0.0, 0.0)
            hub.results["default"] = result
        return hub

    # ── Model building ────────────────────────────────────────────────────

    def add_node(self, label: str, x: float, y: float):
        self.nodes[label] = (float(x), float(y))

    def add_member(self, node_a: str, node_b: str, area: float = 1.0,
                   member_type: str = "auto"):
        """Add a truss member.

        ``area`` (cross-sectional area) only affects the indeterminate
        direct-stiffness solver — it sets the relative member stiffness that
        picks the load path; the determinate method of joints ignores it.
        ``member_type`` is the ``stm.member`` hint: ``auto`` (classified by the
        solved sign) or a forced ``tie`` / ``strut``.
        """
        for n in (node_a, node_b):
            if n not in self.nodes:
                raise KeyError(f"node {n!r} not defined")
        self.members.append((node_a, node_b))
        self.areas[(node_a, node_b)] = float(area)
        if member_type and member_type != "auto":
            self.member_types[(node_a, node_b)] = member_type

    def classify(self, member: tuple[str, str]) -> str | None:
        """Classify a member as ``"tie"`` (tension) or ``"strut"``
        (compression).  A forced ``stm.member`` override wins; otherwise the
        solved sign decides (``None`` until :meth:`solve` has run)."""
        forced = self.member_types.get(member)
        if forced in ("tie", "strut"):
            return forced
        if self.forces is None or member not in self.forces:
            return None
        return "tie" if self.forces[member] > 1e-9 else "strut"

    def add_load(self, node: str, fx: float = 0.0, fy: float = 0.0):
        """Applied joint load (kips); fy negative = downward."""
        load = self.loads.setdefault(node, [0.0, 0.0])
        load[0] += fx
        load[1] += fy

    def add_support(self, node: str, fix_x: bool = False, fix_y: bool = False):
        self.supports[node] = (fix_x, fix_y)

    # ── Analysis ──────────────────────────────────────────────────────────

    def diagnose(self) -> list[str]:
        """Actionable pre-solve checks that **name** the offending node/member.

        These checks run before a solve and point at the fixable cause -- a
        dangling node, a load with no load path, a support on an undefined node,
        missing supports, and an under-constrained (mechanism) model.  A
        statically *indeterminate* model is reported informationally only: it is
        solved by the direct-stiffness method (:meth:`solve`), not an error.
        Returns an empty list for a clean, determinate model.
        """
        problems: list[str] = []
        touched = {n for member in self.members for n in member}

        for node in self.nodes:
            if node not in touched:
                problems.append(f"node {node!r}: not connected to any member")
        for node in self.supports:
            if node not in self.nodes:
                problems.append(f"support on undefined node {node!r}")
        for node, load in self.loads.items():
            if node not in self.nodes:
                problems.append(f"load on undefined node {node!r}")
            elif node not in touched and any(load):
                problems.append(
                    f"load on node {node!r}: no member reaches it (no load path)")
        if self.nodes and not self.supports:
            problems.append("model has no supports -- it is a mechanism")

        n_reactions = sum(int(fx) + int(fy) for fx, fy in self.supports.values())
        n_unknowns = len(self.members) + n_reactions
        n_eq = 2 * len(self.nodes)
        if n_unknowns < n_eq:
            problems.append(
                f"under-constrained (mechanism): {len(self.members)} members + "
                f"{n_reactions} reactions < {n_eq} equilibrium equations -- add "
                f"members or restraints")
        elif n_unknowns > n_eq:
            problems.append(
                f"statically indeterminate (degree {n_unknowns - n_eq}): "
                f"{len(self.members)} members + {n_reactions} reactions > {n_eq} "
                f"equilibrium equations -- solved by the direct-stiffness method "
                f"(solve(method='stiffness')), not the method of joints")
        return problems

    def _direction(self, a: str, b: str) -> tuple[float, float, float]:
        (xa, ya), (xb, yb) = self.nodes[a], self.nodes[b]
        length = math.hypot(xb - xa, yb - ya)
        return (xb - xa) / length, (yb - ya) / length, length

    def _reaction_cols(self) -> list[tuple[str, int]]:
        return [
            (node, dof)
            for node, (fx, fy) in self.supports.items()
            for dof, fixed in enumerate((fx, fy)) if fixed
        ]

    def degree_of_indeterminacy(self) -> int:
        """``members + reactions - 2*nodes``.  Zero = statically determinate,
        positive = indeterminate (needs the direct-stiffness solver),
        negative = a mechanism (unstable)."""
        return len(self.members) + len(self._reaction_cols()) - 2 * len(self.nodes)

    def solve(self, method: str = "auto") -> dict[tuple[str, str], float]:
        """Solve member forces and reactions.

        ``method="auto"`` uses the method of joints when the model is
        statically determinate and the direct-stiffness method (DSM) when it
        is indeterminate; pass ``"joints"`` or ``"stiffness"`` to force one.
        Returns ``{(a, b): force}`` with tension positive (tie) and
        compression negative (strut); reactions land in ``self.reactions``.

        The DSM result depends on the member ``areas`` (relative stiffness
        picks the load path among the redundant members).  Use
        :meth:`solve_fully_stressed` to converge areas onto the forces.
        """
        if method == "auto":
            method = "joints" if self.degree_of_indeterminacy() == 0 else "stiffness"
        if method == "joints":
            return self._solve_joints()
        if method == "stiffness":
            return self._solve_stiffness()
        raise ValueError(f"unknown method {method!r}; use auto/joints/stiffness")

    def _solve_joints(self) -> dict[tuple[str, str], float]:
        """Method of joints — requires a statically determinate, stable model
        (members + reactions = 2 * nodes)."""
        node_index = {label: i for i, label in enumerate(self.nodes)}
        n_eq = 2 * len(self.nodes)
        reaction_cols = self._reaction_cols()
        n_unknowns = len(self.members) + len(reaction_cols)
        if n_unknowns != n_eq:
            detail = "; ".join(self.diagnose())
            raise ValueError(
                f"statically indeterminate or unstable model: "
                f"{len(self.members)} members + {len(reaction_cols)} "
                f"reactions != 2*{len(self.nodes)} equations; "
                f"use solve(method='stiffness') for indeterminate trusses"
                + (f" [{detail}]" if detail else "")
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

        self.forces = {mem: float(solution[i])
                       for i, mem in enumerate(self.members)}
        self.reactions = {}
        for r, (node, dof) in enumerate(reaction_cols):
            self.reactions.setdefault(node, [0.0, 0.0])[dof] = float(
                solution[len(self.members) + r]
            )
        self._warn_member_type_mismatches()
        return self.forces

    def _warn_member_type_mismatches(self):
        """Warn when a member forced to ``tie``/``strut`` via ``stm.member``
        solves with the opposite sign -- a useful modeling signal (the author's
        detailing intent disagrees with the analysis), not an error."""
        for member, forced in self.member_types.items():
            force = self.forces.get(member)
            if force is None:
                continue
            if forced == "tie" and force < -1e-9:
                warnings.warn(
                    f"member {member} is tagged stm.member=tie but solves in "
                    f"compression ({force:+.1f}); check the model intent",
                    stacklevel=2,
                )
            elif forced == "strut" and force > 1e-9:
                warnings.warn(
                    f"member {member} is tagged stm.member=strut but solves in "
                    f"tension ({force:+.1f}); check the model intent",
                    stacklevel=2,
                )

    def _solve_stiffness(self) -> dict[tuple[str, str], float]:
        """Direct stiffness method — handles statically indeterminate trusses.

        Assembles the global stiffness matrix from each member's axial
        stiffness ``E*A/L``, applies the supported DOF as fixed, solves
        ``K u = f`` for the free displacements, then back-calculates each
        member's axial force and the support reactions.  Tension positive.
        """
        node_index = {label: i for i, label in enumerate(self.nodes)}
        ndof = 2 * len(self.nodes)
        k = np.zeros((ndof, ndof))
        # member local axial stiffness assembled into global K
        for (na, nb) in self.members:
            cx, cy, length = self._direction(na, nb)
            ea_l = self.E * self.areas.get((na, nb), 1.0) / length
            ia, ib = node_index[na], node_index[nb]
            dofs = [2 * ia, 2 * ia + 1, 2 * ib, 2 * ib + 1]
            c = np.array([cx, cy, -cx, -cy])
            ke = ea_l * np.outer(c, c)
            for p in range(4):
                for q in range(4):
                    k[dofs[p], dofs[q]] += ke[p, q]

        f = np.zeros(ndof)
        for node, (fx, fy) in self.loads.items():
            f[2 * node_index[node]] += fx
            f[2 * node_index[node] + 1] += fy

        fixed = np.zeros(ndof, dtype=bool)
        for node, dof in self._reaction_cols():
            fixed[2 * node_index[node] + dof] = True
        free = ~fixed
        if not free.any():
            raise ValueError("every DOF is restrained; nothing to solve")

        u = np.zeros(ndof)
        try:
            u[free] = np.linalg.solve(k[np.ix_(free, free)], f[free])
        except np.linalg.LinAlgError as exc:
            detail = "; ".join(self.diagnose())
            raise ValueError(
                f"singular stiffness matrix — the truss has a mechanism "
                f"(unstable / under-braced): {exc}"
                + (f" [{detail}]" if detail else "")
            ) from exc

        # reactions at the fixed DOF: r = K u - f
        r = k @ u - f
        self.reactions = {}
        for node, dof in self._reaction_cols():
            self.reactions.setdefault(node, [0.0, 0.0])[dof] = float(
                r[2 * node_index[node] + dof]
            )

        # member axial force = (EA/L) * relative axial displacement
        self.forces = {}
        for (na, nb) in self.members:
            cx, cy, length = self._direction(na, nb)
            ea_l = self.E * self.areas.get((na, nb), 1.0) / length
            ia, ib = node_index[na], node_index[nb]
            du = np.array([u[2 * ib] - u[2 * ia], u[2 * ib + 1] - u[2 * ia + 1]])
            self.forces[(na, nb)] = float(ea_l * (du[0] * cx + du[1] * cy))
        self._warn_member_type_mismatches()
        return self.forces

    def solve_fully_stressed(self, iterations: int = 25, tol: float = 1e-4,
                             min_ratio: float = 1e-3) -> dict[tuple[str, str], float]:
        """Resize members in proportion to their force and re-solve until the
        load path stabilizes (fully-stressed design).

        For an indeterminate truss the force distribution depends on the
        relative member areas; setting each area proportional to ``|force|``
        and iterating drives the truss toward a uniform-stress load path —
        the natural strut-and-tie idealization.  ``min_ratio`` floors the
        area (relative to the largest) so lightly loaded members keep the
        truss stable instead of vanishing.  Determinate models are returned
        unchanged after a single solve.
        """
        forces = self.solve(method="auto")
        if self.degree_of_indeterminacy() <= 0:
            return forces
        prev = np.array([forces[m] for m in self.members])
        for _ in range(iterations):
            saved = dict(self.areas)
            fmax = max(abs(v) for v in forces.values()) or 1.0
            for m in self.members:
                self.areas[m] = max(abs(forces[m]) / fmax, min_ratio)
            try:
                forces = self._solve_stiffness()
            except ValueError:
                # resizing pushed a member to the floor and singularized the
                # truss; keep the last stable solution.
                self.areas = saved
                forces = self._solve_stiffness()
                break
            cur = np.array([forces[m] for m in self.members])
            denom = max(np.abs(cur).max(), 1e-12)
            if np.abs(cur - prev).max() / denom < tol:
                break
            prev = cur
        return forces

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
