"""Influence lines for statically determinate beams (overhangs allowed),
with axle-train stepping for moving-load maxima — the classic line-girder
approach, so ordinates can be compared against any rating software.

Conventions follow :mod:`civilpy.structural.beam_bending`: kips/ft, plots
accept ``ax=None`` and return the figure.  Unit load is 1 kip downward;
sign conventions are the usual ones (positive reaction up, positive
moment sagging, shear by the left-segment rule).

Examples
--------
>>> il = InfluenceLine.moment(span=20, section=10)   # midspan moment
>>> round(il.eta(10), 4)                             # peak = L/4
5.0
>>> peak = il.maximize_axle_train([32, 32, 8], [0, 14, 28])
>>> round(peak.value, 1)                             # one axle fits the peak
160.0
>>> round(il.uniform_load_effect(0.64), 1)           # 0.64 klf lane load
32.0
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

from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np


@dataclass
class TrainResult:
    """Extreme effect of an axle train on an influence line."""

    value: float
    position: float  # location of the train's first axle (ft)
    reversed_train: bool


class InfluenceLine:
    """Influence line for one effect (reaction, shear, or moment at a
    section) on a beam with a pin at ``support_a`` and roller at
    ``support_b``; the beam runs from 0 to ``length`` (defaults to
    ``support_b``), so overhangs come from supports inside the ends."""

    def __init__(self, eta, length: float, label: str = ""):
        self._eta = np.vectorize(eta, otypes=[float])
        self.length = float(length)
        self.label = label

    def eta(self, x):
        """Ordinate(s) at unit-load position(s) ``x``: a float for scalar
        input, an array for array input."""
        out = self._eta(x)
        return float(out) if np.ndim(x) == 0 else out

    # ── Constructors for the classic effects ─────────────────────────────

    @classmethod
    def reaction(cls, span: float, support: str = "A",
                 support_a: float = 0.0, support_b: float | None = None,
                 length: float | None = None):
        """IL for a vertical reaction.  ``span`` is shorthand for supports
        at 0 and ``span``; or place them with ``support_a``/``support_b``."""
        a, b = support_a, span if support_b is None else support_b
        total = b if length is None else length

        def eta(x):
            r_a = (b - x) / (b - a)
            return r_a if support.upper() == "A" else 1.0 - r_a

        return cls(eta, total, f"Reaction {support.upper()}")

    @classmethod
    def shear(cls, span: float, section: float,
              support_a: float = 0.0, support_b: float | None = None,
              length: float | None = None):
        """IL for shear at ``section`` (left-segment sign convention)."""
        a, b = support_a, span if support_b is None else support_b
        total = b if length is None else length
        c = section

        def eta(x):
            r_a = (b - x) / (b - a)
            v = (r_a if a < c else 0.0) - (1.0 if x < c else 0.0)
            return v

        return cls(eta, total, f"Shear at x={section:g}")

    @classmethod
    def moment(cls, span: float, section: float,
               support_a: float = 0.0, support_b: float | None = None,
               length: float | None = None):
        """IL for bending moment at ``section``."""
        a, b = support_a, span if support_b is None else support_b
        total = b if length is None else length
        c = section

        def eta(x):
            r_a = (b - x) / (b - a)
            m = r_a * (c - a) - (c - x if x < c else 0.0)
            return m

        return cls(eta, total, f"Moment at x={section:g}")

    # ── Two-span continuous beams (Müller-Breslau) ───────────────────────

    @staticmethod
    def _two_span_redundant(spans):
        """Middle-reaction influence function for a prismatic two-span
        continuous beam by the force method (the exact Müller-Breslau
        shape: the deflected shape of the released simple beam scaled by
        the deflection at B).

        Releasing the middle support leaves a simple beam of length
        L1 + L2; eta_RB(u) = delta(B, u) / delta(B, B), with the
        simple-beam deflection formula (EI cancels).
        """
        l1, l2 = (float(s) for s in spans)
        total = l1 + l2

        def deflection_at(v, u):
            # simple beam 0..total, deflection at v due to unit load at u
            if v > u:
                v, u = total - v, total - u
            b = total - u
            return b * v * (total**2 - b**2 - v**2) / (6.0 * total)

        d_bb = deflection_at(l1, l1)

        def r_b(u):
            return deflection_at(l1, u) / d_bb

        return l1, l2, total, r_b

    @classmethod
    def two_span_reaction(cls, spans, support: str = "B"):
        """IL for a reaction of a two-span continuous beam with supports
        A-B-C and (possibly unequal) ``spans`` = (L1, L2).  The middle
        reaction's IL is the Müller-Breslau deflected shape of the
        beam with support B released."""
        l1, l2, total, r_b = cls._two_span_redundant(spans)

        def eta(u):
            if support.upper() == "B":
                return r_b(u)
            r_a = ((total - u) - r_b(u) * l2) / total
            if support.upper() == "A":
                return r_a
            return 1.0 - r_a - r_b(u)

        return cls(eta, total,
                   f"Reaction {support.upper()} (2-span {l1:g}+{l2:g})")

    @classmethod
    def two_span_shear(cls, spans, section: float):
        """IL for shear at ``section`` (ft from A) of a two-span
        continuous beam, left-segment sign convention."""
        l1, l2, total, r_b = cls._two_span_redundant(spans)
        c = float(section)

        def eta(u):
            r_a = ((total - u) - r_b(u) * l2) / total
            v = r_a
            if l1 < c:
                v += r_b(u)
            if u < c:
                v -= 1.0
            return v

        return cls(eta, total, f"Shear at x={section:g} (2-span)")

    @classmethod
    def two_span_moment(cls, spans, section: float):
        """IL for bending moment at ``section`` (ft from A) of a
        two-span continuous beam.  ``section = L1`` gives the classic
        negative-moment IL over the middle support."""
        l1, l2, total, r_b = cls._two_span_redundant(spans)
        c = float(section)

        def eta(u):
            r_a = ((total - u) - r_b(u) * l2) / total
            m = r_a * c
            if c > l1:
                m += r_b(u) * (c - l1)
            if u < c:
                m -= c - u
            return m

        return cls(eta, total, f"Moment at x={section:g} (2-span)")

    # ── Load effects ──────────────────────────────────────────────────────

    def ordinates(self, n: int = 1001):
        x = np.linspace(0.0, self.length, n)
        return x, self.eta(x)

    def uniform_load_effect(self, w: float, positive_only: bool = True,
                            n: int = 2001) -> float:
        """Effect of a uniform load ``w`` (klf): w times the influence-line
        area — positive regions only by default, the way lane load is
        placed to maximize."""
        x, y = self.ordinates(n)
        if positive_only:
            y = np.clip(y, 0.0, None)
        return w * float(np.trapezoid(y, x))

    def maximize_axle_train(self, loads, positions, step: float = 0.05,
                            both_directions: bool = True,
                            sign: float = 1.0) -> TrainResult:
        """Step an axle train across the beam and return the extreme
        effect.  ``loads`` (kips) sit at ``positions`` (ft, from the first
        axle); axles off the beam contribute nothing.  ``sign=-1`` finds
        the most negative effect instead."""
        loads = np.asarray(loads, dtype=float)
        offsets = np.asarray(positions, dtype=float)
        candidates = [(offsets, False)]
        if both_directions:
            candidates.append((offsets.max() - offsets[::-1], True))

        best = TrainResult(value=-np.inf, position=0.0, reversed_train=False)
        starts = np.arange(-offsets.max(), self.length + step, step)
        for offs, rev in candidates:
            ld = loads[::-1] if rev else loads
            for s in starts:
                xs = s + offs
                mask = (xs >= 0.0) & (xs <= self.length)
                if not mask.any():
                    continue
                effect = sign * float(np.sum(ld[mask] * self.eta(xs[mask])))
                if effect > best.value:
                    best = TrainResult(effect, float(s), rev)
        return TrainResult(sign * best.value, best.position,
                           best.reversed_train)

    def hl93_effect(self, im: float = 0.33, lane_klf: float = 0.64,
                    rear_spacings=(14.0, 30.0)) -> dict:
        """Governing HL-93 effect on this line (3.6.1.3): design truck
        (rear-axle spacing swept) with dynamic load allowance, plus lane
        load on the positive regions.  Returns the pieces and the total."""
        best_truck = max(
            (self.maximize_axle_train([8.0, 32.0, 32.0], [0.0, 14.0, 14.0 + s])
             for s in rear_spacings),
            key=lambda r: r.value,
        )
        tandem = self.maximize_axle_train([25.0, 25.0], [0.0, 4.0])
        truck = max(best_truck, tandem, key=lambda r: r.value)
        lane = self.uniform_load_effect(lane_klf)
        return {
            "truck": truck.value,
            "tandem_governs": truck is tandem,
            "lane": lane,
            "total": truck.value * (1.0 + im) + lane,
            "position": truck.position,
        }

    # ── Visualization ─────────────────────────────────────────────────────

    def plot(self, ax=None, n: int = 1001, axle_train=None):
        """Plot the influence line (positive area shaded), optionally with
        an axle train drawn at its governing position."""
        if ax is None:
            ax = plt.figure(figsize=(8, 3.2)).add_subplot(1, 1, 1)
        x, y = self.ordinates(n)
        ax.plot(x, y, "b", lw=1.6)
        ax.fill_between(x, y, 0.0, where=y > 0, color="b", alpha=0.15)
        ax.fill_between(x, y, 0.0, where=y < 0, color="r", alpha=0.15)
        ax.axhline(0.0, color="k", lw=0.8)
        peak_i = int(np.argmax(np.abs(y)))
        ax.annotate(f"{y[peak_i]:.4g}", (x[peak_i], y[peak_i]),
                    textcoords="offset points", xytext=(5, 5))
        if axle_train is not None:
            loads, positions = axle_train
            res = self.maximize_axle_train(loads, positions)
            offs = np.asarray(positions, dtype=float)
            if res.reversed_train:
                offs = offs.max() - offs[::-1]
                loads = list(loads)[::-1]
            top = max(y.max(), 0.0) * 1.35 + 1e-9
            for p, off in zip(loads, offs):
                xa = res.position + off
                if 0.0 <= xa <= self.length:
                    ax.annotate("", xy=(xa, 0.0), xytext=(xa, top),
                                arrowprops=dict(arrowstyle="-|>", color="g"))
                    ax.annotate(f"{p:g}", (xa, top),
                                textcoords="offset points", xytext=(2, 2),
                                color="g", fontsize=8)
        ax.set_xlabel("Unit load position (ft)")
        ax.set_ylabel(r"$\eta$")
        ax.set_title(f"Influence line — {self.label}")
        ax.grid(True, alpha=0.3)
        return ax.get_figure()
