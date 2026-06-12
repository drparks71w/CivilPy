"""Hardy Cross moment distribution for prismatic continuous beams, with
the iteration table (the part they make you do by hand) and the final
moment diagram.

Sign convention: counterclockwise end moments positive (the standard
moment-distribution convention); the plotted bending-moment diagram is
converted to the sagging-positive beam convention.

Examples
--------
Two equal 20-ft spans, 2 klf everywhere, pinned ends:

>>> md = MomentDistribution()
>>> md.add_span(length=20, w=2.0)
>>> md.add_span(length=20, w=2.0)
>>> moments = md.solve()
>>> round(-moments[1][0], 1)    # support moment = wL^2/8 = 100 (hogging)
100.0
"""

#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see other modules for the full notice)

import matplotlib.pyplot as plt
import numpy as np


class MomentDistribution:
    """Continuous prismatic beam on simple supports (ends optionally
    fixed), loaded with a uniform load and/or one point load per span."""

    def __init__(self, left_fixed: bool = False, right_fixed: bool = False):
        self.spans: list[dict] = []
        self.left_fixed = left_fixed
        self.right_fixed = right_fixed
        self.history: list[list[float]] = []
        self.end_moments: list[tuple[float, float]] | None = None

    def add_span(self, length: float, ei: float = 1.0, w: float = 0.0,
                 point_load: tuple[float, float] | None = None):
        """``w`` is a uniform load (klf, downward positive);
        ``point_load`` = (P kips, a ft from the span's left end)."""
        self.spans.append(dict(length=length, ei=ei, w=w, point=point_load))

    # ── Fixed-end moments (counterclockwise positive) ─────────────────────

    @staticmethod
    def _fem(span) -> tuple[float, float]:
        length, w, point = span["length"], span["w"], span["point"]
        m_left = -w * length**2 / 12.0
        m_right = w * length**2 / 12.0
        if point is not None:
            p, a = point
            b = length - a
            m_left -= p * a * b**2 / length**2
            m_right += p * a**2 * b / length**2
        return m_left, m_right

    def solve(self, tolerance: float = 1e-6, max_cycles: int = 100):
        """Iterate balance/carry-over to convergence.  Returns the end
        moments per span [(M_left, M_right), ...] (CCW positive) and
        stores the cycle-by-cycle ``history`` for the classic table."""
        n = len(self.spans)
        joints = n + 1
        # joint stiffness terms: 4EI/L, reduced to 3EI/L at pinned ends
        stiff = []
        for i, s in enumerate(self.spans):
            k = 4.0 * s["ei"] / s["length"]
            stiff.append(k)
        moments = [list(self._fem(s)) for s in self.spans]

        def df(joint):
            members = []
            if joint > 0:
                members.append(("right", joint - 1, stiff[joint - 1]))
            if joint < n:
                members.append(("left", joint, stiff[joint]))
            total = sum(m[2] for m in members)
            return [(side, idx, k / total) for side, idx, k in members]

        free_joints = [
            j for j in range(joints)
            if not (j == 0 and self.left_fixed)
            and not (j == joints - 1 and self.right_fixed)
        ]
        self.history = []
        for _ in range(max_cycles):
            worst = 0.0
            row = []
            for j in free_joints:
                unbalanced = 0.0
                if j > 0:
                    unbalanced += moments[j - 1][1]
                if j < n:
                    unbalanced += moments[j][0]
                worst = max(worst, abs(unbalanced))
                for side, idx, factor in df(j):
                    corr = -unbalanced * factor
                    if side == "right":
                        moments[idx][1] += corr
                        moments[idx][0] += corr / 2.0  # carry-over
                    else:
                        moments[idx][0] += corr
                        moments[idx][1] += corr / 2.0
                row.append(unbalanced)
            self.history.append(row)
            if worst < tolerance:
                break
        self.end_moments = [tuple(m) for m in moments]
        return self.end_moments

    # ── Diagram ───────────────────────────────────────────────────────────

    def moment_at(self, span_index: int, x: float) -> float:
        """Sagging-positive bending moment at ``x`` ft along a span,
        superposing the simple-span moment and the end-moment gradient."""
        if self.end_moments is None:
            self.solve()
        s = self.spans[span_index]
        length = s["length"]
        m_l, m_r = self.end_moments[span_index]
        # convert CCW end moments to beam-convention boundary moments
        m_left_beam, m_right_beam = m_l, -m_r
        m_simple = s["w"] * x * (length - x) / 2.0
        if s["point"] is not None:
            p, a = s["point"]
            m_simple += (p * (length - a) * x / length if x <= a
                         else p * a * (length - x) / length)
        return (m_simple + m_left_beam * (1.0 - x / length)
                + m_right_beam * (x / length))

    def plot(self, ax=None, n_per_span: int = 120):
        """Plot the final bending-moment diagram across all spans with
        supports marked.  Returns the figure."""
        if self.end_moments is None:
            self.solve()
        if ax is None:
            ax = plt.figure(figsize=(9, 3.5)).add_subplot(1, 1, 1)
        x0 = 0.0
        for i, s in enumerate(self.spans):
            xs = np.linspace(0.0, s["length"], n_per_span)
            ms = np.array([self.moment_at(i, x) for x in xs])
            ax.plot(x0 + xs, ms, "b", lw=1.5)
            ax.fill_between(x0 + xs, ms, 0.0, color="b", alpha=0.12)
            ax.plot(x0, 0.0, "k^", markersize=10, clip_on=False)
            x0 += s["length"]
        ax.plot(x0, 0.0, "k^", markersize=10, clip_on=False)
        ax.axhline(0.0, color="k", lw=0.8)
        ax.set_xlabel("Position (ft)")
        ax.set_ylabel("Moment (kip·ft)")
        ax.set_title("Continuous Beam — Moment Distribution Result")
        ax.grid(True, alpha=0.3)
        return ax.get_figure()
