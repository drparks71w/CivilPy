"""Open-channel flow for rectangular channels: critical/normal depth,
Froude number, and the specific-energy curve with alternate depths —
the diagram from every hydraulics course.

US units: ft, cfs; Manning with the 1.486 conversion.

Examples
--------
>>> ch = RectangularChannel(width=10, n=0.013, slope=0.002)
>>> round(ch.critical_depth(q=200), 3)
2.316
>>> yn = ch.normal_depth(q=200)
>>> ch.froude(q=200, y=yn) < 1.0   # mild slope -> subcritical
True
"""

#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see other modules for the full notice)

import math

import matplotlib.pyplot as plt
import numpy as np

G = 32.2  # ft/s^2


class RectangularChannel:
    def __init__(self, width: float, n: float = 0.013,
                 slope: float = 0.001):
        self.b = width
        self.n = n
        self.s = slope

    def critical_depth(self, q: float) -> float:
        """yc = (q_unit^2/g)^(1/3) for discharge ``q`` (cfs)."""
        q_unit = q / self.b
        return (q_unit**2 / G) ** (1.0 / 3.0)

    def manning_q(self, y: float) -> float:
        """Discharge at depth ``y`` by Manning's equation (cfs)."""
        a = self.b * y
        r = a / (self.b + 2.0 * y)
        return 1.486 / self.n * a * r ** (2.0 / 3.0) * math.sqrt(self.s)

    def normal_depth(self, q: float, tol: float = 1e-8) -> float:
        """Solve Manning for the uniform-flow depth by bisection."""
        lo, hi = tol, 1.0
        while self.manning_q(hi) < q:
            hi *= 2.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if self.manning_q(mid) < q:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return (lo + hi) / 2.0

    def specific_energy(self, q: float, y: float) -> float:
        """E = y + v^2/2g (ft)."""
        v = q / (self.b * y)
        return y + v**2 / (2.0 * G)

    def froude(self, q: float, y: float) -> float:
        v = q / (self.b * y)
        return v / math.sqrt(G * y)

    def alternate_depths(self, q: float, energy: float,
                         tol: float = 1e-8) -> tuple[float, float]:
        """The sub- and supercritical depths sharing the given specific
        energy (raises if E is below the critical minimum)."""
        yc = self.critical_depth(q)
        e_min = self.specific_energy(q, yc)
        if energy < e_min:
            raise ValueError(f"E = {energy:g} ft < Emin = {e_min:.4g} ft")

        def solve(lo, hi):
            for _ in range(200):
                mid = (lo + hi) / 2.0
                if self.specific_energy(q, mid) > energy:
                    # branch direction differs above/below critical
                    if mid < yc:
                        lo = mid
                    else:
                        hi = mid
                else:
                    if mid < yc:
                        hi = mid
                    else:
                        lo = mid
                if hi - lo < tol:
                    break
            return (lo + hi) / 2.0

        return solve(tol, yc), solve(yc, energy * 1.5)

    def plot_specific_energy(self, q: float, ax=None,
                             energy: float | None = None,
                             y_max: float | None = None):
        """The E-y curve with the critical point marked and, optionally,
        the alternate depths for a given energy."""
        if ax is None:
            ax = plt.figure(figsize=(6.5, 6)).add_subplot(1, 1, 1)
        yc = self.critical_depth(q)
        top = y_max or 4.0 * yc
        ys = np.linspace(0.05 * yc, top, 400)
        es = [self.specific_energy(q, y) for y in ys]
        ax.plot(es, ys, "b", lw=1.6)
        ax.plot(es, es, "k:", lw=0.8)  # E = y asymptote
        e_c = self.specific_energy(q, yc)
        ax.plot(e_c, yc, "rs")
        ax.annotate(rf"critical ($y_c$={yc:.3g} ft)", (e_c, yc),
                    textcoords="offset points", xytext=(8, -4), color="r")
        if energy is not None:
            y1, y2 = self.alternate_depths(q, energy)
            ax.axvline(energy, color="g", ls="--", lw=0.9)
            for y_alt in (y1, y2):
                ax.plot(energy, y_alt, "g^")
                ax.annotate(f"{y_alt:.3g} ft", (energy, y_alt),
                            textcoords="offset points", xytext=(6, 0),
                            color="g")
        ax.set_xlabel("Specific energy E (ft)")
        ax.set_ylabel("Depth y (ft)")
        ax.set_title(f"Specific Energy — q = {q:g} cfs, b = {self.b:g} ft")
        ax.grid(True, alpha=0.3)
        return ax.get_figure()
