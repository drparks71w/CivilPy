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

"""Pier-cap dimension design driven by girder reactions.

The everyday workflow this targets: an engineer pulls factored girder reactions
and their bearing locations out of a line-girder run (AASHTOWare BrR, Merlin
DASH, …), and wants the most economical cap *depth* that still produces a valid,
code-checkable strut-and-tie model for that specific layout.

:func:`optimize_pier_cap` sweeps the cap depth, runs the topology-optimization
pipeline (:func:`~civilpy.structural.stm_topology.pipeline.optimize_to_stm`) at
each depth, and returns the shallowest depth — i.e. the least concrete, which
dominates cost — that satisfies the design gates:

* the strut-and-tie model is a complete, solved load path (every girder and
  column present, global equilibrium satisfied);
* the flattest primary strut meets the AASHTO 5.8.2.5 / ACI 318 Ch. 23 nodal
  angle limit (default 25 deg), equivalently the deep-beam ``a/d`` limit; and
* every nodal zone has capacity.

The cap *length* is fixed by the girder layout plus an edge distance, and the
*width* by the columns/bearings, so depth is the free dimension.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .problem import DRegionProblem, Material
from .cost import resolve_prices


@dataclass
class DepthCandidate:
    """One depth evaluated in the sweep."""

    depth: float
    cost: float
    concrete_cost: float
    steel_lb: float
    strut_angle: float        # deg, flattest primary strut (a/d limit)
    node_ratio: float         # min nodal capacity/demand over the bearing zones
    max_tie: float            # kip, governing tie force at this depth
    complete: bool            # extraction is a full, equilibrated load path
    feasible: bool
    result: object            # the STMResult at this depth


@dataclass
class PierCapDesign:
    """Result of :func:`optimize_pier_cap`."""

    optimal: DepthCandidate | None
    candidates: list[DepthCandidate] = field(default_factory=list)
    span: float = 0.0
    thickness: float = 0.0
    min_strut_angle: float = 25.0

    # convenience pass-throughs to the optimal design
    @property
    def model(self):
        return self.optimal.result.model if self.optimal else None

    @property
    def report(self):
        return self.optimal.result.report if self.optimal else None

    def plot(self, ax=None):
        """Draw the optimal strut-and-tie model over its density field."""
        if self.optimal is None:
            raise ValueError("no feasible depth found; inspect .candidates")
        return self.optimal.result.plot(ax=ax)

    def plot_tradeoff(self, ax=None):
        """Cost and strut angle vs depth, with the infeasible band shaded and the
        optimum marked."""
        import matplotlib.pyplot as plt
        if ax is None:
            ax = plt.figure(figsize=(10, 5)).add_subplot(1, 1, 1)
        d = [c.depth for c in self.candidates]
        ax.plot(d, [c.cost / 1000 for c in self.candidates], "o-",
                color="tab:blue", label="cost")
        ax.set_xlabel("cap depth (ft)")
        ax.set_ylabel("total cost ($k)", color="tab:blue")
        ang = ax.twinx()
        ang.plot(d, [c.strut_angle for c in self.candidates], "s--",
                 color="tab:red")
        ang.axhline(self.min_strut_angle, color="tab:red", ls=":", lw=1)
        ang.set_ylabel("min strut angle (deg)", color="tab:red")
        for c in self.candidates:
            if not c.feasible:
                ax.axvspan(c.depth - 0.4, c.depth + 0.4, color="red", alpha=0.07)
        if self.optimal is not None:
            ax.axvline(self.optimal.depth, color="green", lw=2, alpha=0.6)
        return ax.get_figure()

    def summary(self) -> str:
        feas = [c for c in self.candidates if c.feasible]
        lines = [
            f"Pier-cap depth optimization (span {self.span:.0f} ft, "
            f"thickness {self.thickness:.0f} ft):"
        ]
        if self.optimal is None:
            lines.append("  no feasible depth in the swept range — widen the "
                         "bounds or relax min_strut_angle")
            return "\n".join(lines)
        o = self.optimal
        lines.append(
            f"  optimum depth = {o.depth:.1f} ft  ->  ${o.cost:,.0f}  "
            f"(concrete ${o.concrete_cost:,.0f} + {o.steel_lb:.0f} lb steel)")
        lines.append(
            f"  governing: strut angle {o.strut_angle:.1f} deg >= "
            f"{self.min_strut_angle:.0f} (a/d limit); nodal capacity/demand "
            f"{o.node_ratio:.2f}; governing tie {o.max_tie:.0f} kip")
        if feas:
            lines.append(f"  feasible depths: {min(c.depth for c in feas):.1f}"
                         f"-{max(c.depth for c in feas):.1f} ft")
        return "\n".join(lines)


def governing_strut_angle(load_xs, column_xs, depth) -> float:
    """Inclination (deg) of the flattest primary strut: the largest shear span
    ``a`` (girder-to-nearest-column distance) with ``theta = atan(depth / a)``.

    This geometric ``a/d`` measure is robust and monotonic in depth, unlike the
    angle read off whichever discrete truss the extractor produced at a given
    depth, so it is what gates the sweep."""
    a = max(min(abs(lx - cx) for cx in column_xs) for lx in load_xs)
    return 90.0 if a < 1e-6 else math.degrees(math.atan(depth / a))


def optimize_pier_cap(loads, load_xs, column_xs, *, f_c: float = 5.0,
                      f_y: float = 60.0, thickness: float = 4.0,
                      depth_bounds: tuple[float, float] = (4.0, 12.0),
                      n_depths: int = 9, edge: float = 2.5,
                      vol_frac: float = 0.30, nelx: int = 72,
                      column_bearing: float = 2.0, load_bearing: float = 1.0,
                      min_strut_angle: float = 25.0,
                      price_concrete_cy: float | None = None,
                      price_steel_lb: float | None = None, prices=None,
                      pin_column: int | None = None) -> PierCapDesign:
    """Find the most economical pier-cap depth for a set of girder reactions.

    Parameters
    ----------
    loads, load_xs:
        Factored girder reactions (kip, magnitudes) and their bearing locations
        (ft) along the cap — typically straight from a BrR / DASH run.
    column_xs:
        Column centreline locations (ft).
    thickness:
        Out-of-plane cap width ``b`` (ft).
    depth_bounds, n_depths:
        Range and sampling of cap depths to evaluate.
    edge:
        Cap overhang beyond the outermost girder/column (ft); sets the length.
    column_bearing, load_bearing:
        In-plane bearing widths (ft) for the nodal-zone checks.
    min_strut_angle:
        AASHTO 5.8.2.5 nodal angle limit (deg); raise it to force a stockier,
        more clearly deep-beam cap.
    pin_column:
        Index of the laterally-restrained (pinned) column; defaults to the one
        nearest mid-length, the rest acting as vertical rollers.

    Returns
    -------
    :class:`PierCapDesign` whose ``optimal`` is the shallowest feasible depth.
    """
    loads = [abs(P) for P in loads]
    # resolve unit prices once: explicit args > prices mapping > registered ODOT
    # provider > civilpy defaults (see civilpy...cost.set_price_provider)
    book = resolve_prices(prices)
    pcc = book["concrete_cy"] if price_concrete_cy is None else float(price_concrete_cy)
    psl = book["steel_lb"] if price_steel_lb is None else float(price_steel_lb)
    xs = list(load_xs) + list(column_xs)
    x_lo, x_hi = min(xs) - edge, max(xs) + edge
    span = x_hi - x_lo
    if pin_column is None:
        pin_column = min(range(len(column_xs)),
                         key=lambda i: abs(column_xs[i] - (x_lo + span / 2)))
    total_load = sum(loads)

    candidates: list[DepthCandidate] = []
    best: DepthCandidate | None = None
    for depth in np.linspace(*depth_bounds, n_depths):
        depth = float(depth)
        prob = DRegionProblem.rectangle(span, depth, thickness=thickness,
                                        origin=(x_lo, 0.0),
                                        material=Material(f_c=f_c),
                                        vol_frac=vol_frac)
        for i, cx in enumerate(column_xs):
            prob.add_support(cx, 0.0, fix_x=(i == pin_column), fix_y=True,
                             bearing=column_bearing)
        for lx, P in zip(load_xs, loads):
            prob.add_load(lx, depth, fy=-P, bearing=load_bearing)
        # a slender cap needs more columns to keep enough mesh rows for a
        # reliable extraction; cap it so the sweep stays quick
        nelx_d = min(150, max(nelx, int(math.ceil(16.0 * span / depth))))
        res = prob.solve(nelx=nelx_d, prices=book)

        concrete_cost = (span * depth * thickness / 27.0) * pcc
        steel_lb = res.report.cost.steel_lb if res.report.cost else 0.0
        cost = concrete_cost + steel_lb * psl
        angle = governing_strut_angle(load_xs, column_xs, depth)
        checks = res.report.node_checks or []
        node_ratio = min((c.ratio for c in checks), default=float("inf"))
        nodes_ok = all(c.ok for c in checks)
        max_tie = max((t.force for t in res.report.ties), default=0.0)
        m = res.model
        ry = sum(v[1] for v in (m.reactions or {}).values())
        complete = (len(m.loads) == len(loads)
                    and len(m.supports) == len(column_xs)
                    and abs(ry - total_load) < 0.02 * total_load)
        feasible = bool(res.stable and complete
                        and angle >= min_strut_angle and nodes_ok)
        cand = DepthCandidate(depth=depth, cost=cost, concrete_cost=concrete_cost,
                              steel_lb=steel_lb, strut_angle=angle,
                              node_ratio=node_ratio, max_tie=max_tie,
                              complete=complete, feasible=feasible, result=res)
        candidates.append(cand)
        if feasible and (best is None or cost < best.cost):
            best = cand

    return PierCapDesign(optimal=best, candidates=candidates, span=span,
                         thickness=thickness, min_strut_angle=min_strut_angle)
