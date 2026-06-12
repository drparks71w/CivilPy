"""Transverse shear stress distribution tau = VQ/(I*b) over a built-up
section of stacked rectangles, with the classic distribution plot.

Examples
--------
>>> sec = ShearSection([Plate(width=12, height=2, y_bottom=0),
...                     Plate(width=1, height=20, y_bottom=2),
...                     Plate(width=12, height=2, y_bottom=22)])
>>> round(sec.y_bar, 2)
12.0
>>> tau_max = sec.tau(50, sec.y_bar)   # web stress at the NA
>>> tau_web_top = sec.tau(50, 21.99)
>>> tau_max > tau_web_top
True
"""

#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see other modules for the full notice)

from collections import namedtuple

import matplotlib.pyplot as plt
import numpy as np


class Plate(namedtuple("Plate", "width, height, y_bottom")):
    """A rectangle in the cross-section: ``width`` x ``height`` with its
    bottom edge at ``y_bottom`` (in)."""


class ShearSection:
    """Stacked-rectangle section for VQ/(I*b) shear stress."""

    def __init__(self, plates: list[Plate]):
        self.plates = [Plate(*p) for p in plates]
        self.area = sum(p.width * p.height for p in self.plates)
        self.y_bar = sum(
            p.width * p.height * (p.y_bottom + p.height / 2.0)
            for p in self.plates
        ) / self.area
        self.i_x = sum(
            p.width * p.height**3 / 12.0
            + p.width * p.height
            * (p.y_bottom + p.height / 2.0 - self.y_bar) ** 2
            for p in self.plates
        )

    def width_at(self, y: float) -> float:
        """Total section width crossing elevation ``y``."""
        return sum(p.width for p in self.plates
                   if p.y_bottom < y < p.y_bottom + p.height)

    def q_at(self, y: float) -> float:
        """First moment of the area above ``y`` about the neutral axis."""
        q = 0.0
        for p in self.plates:
            top = p.y_bottom + p.height
            lo = max(p.y_bottom, y)
            if lo >= top:
                continue
            a = p.width * (top - lo)
            q += a * ((top + lo) / 2.0 - self.y_bar)
        return q

    def tau(self, v: float, y: float) -> float:
        """Shear stress at elevation ``y`` for shear force ``v`` (ksi for
        kips and inches)."""
        b = self.width_at(y)
        return v * self.q_at(y) / (self.i_x * b) if b > 0.0 else 0.0

    def plot(self, v: float, ax=None, n: int = 400):
        """Plot tau(y) beside the section outline; flange/web jumps from
        the width change show as the textbook discontinuities."""
        if ax is None:
            fig, axes = plt.subplots(1, 2, figsize=(9, 5), sharey=True)
            ax_sec, ax_tau = axes
        else:
            ax_sec, ax_tau = None, ax
        y_lo = min(p.y_bottom for p in self.plates)
        y_hi = max(p.y_bottom + p.height for p in self.plates)
        ys = np.linspace(y_lo + 1e-9, y_hi - 1e-9, n)
        taus = np.array([self.tau(v, y) for y in ys])

        if ax_sec is not None:
            for p in self.plates:
                ax_sec.add_patch(plt.Rectangle(
                    (-p.width / 2.0, p.y_bottom), p.width, p.height,
                    facecolor="0.85", edgecolor="k"))
            ax_sec.axhline(self.y_bar, color="r", ls="--", lw=0.9)
            ax_sec.annotate("N.A.", (0, self.y_bar),
                            textcoords="offset points", xytext=(4, 3),
                            color="r")
            ax_sec.set_xlim(-max(p.width for p in self.plates) * 0.75,
                            max(p.width for p in self.plates) * 0.75)
            ax_sec.set_aspect("equal", adjustable="datalim")
            ax_sec.set_title("Section")
            ax_sec.set_ylabel("y (in)")

        ax_tau.plot(taus, ys, "b", lw=1.5)
        ax_tau.fill_betweenx(ys, taus, 0.0, color="b", alpha=0.15)
        i_peak = int(np.argmax(taus))
        ax_tau.annotate(rf"$\tau_{{max}}$ = {taus[i_peak]:.4g} ksi",
                        (taus[i_peak], ys[i_peak]),
                        textcoords="offset points", xytext=(6, 0))
        ax_tau.axhline(self.y_bar, color="r", ls="--", lw=0.9)
        ax_tau.set_xlabel(r"$\tau = VQ/Ib$ (ksi)")
        ax_tau.set_title(f"Shear stress, V = {v:g} kips")
        ax_tau.grid(True, alpha=0.3)
        return ax_tau.get_figure()
