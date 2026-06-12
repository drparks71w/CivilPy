"""Soil profiles: boring-log style layer columns and the total/pore/
effective vertical stress diagram every soils course draws.

Units: ft and pcf in, psf out.

Examples
--------
>>> sp = SoilProfile([SoilLayer("Sand", 10, 115), SoilLayer("Clay", 15, 105)])
>>> sp.water_table = 10
>>> total, pore, eff = sp.stresses_at(25)
>>> round(total, 0), round(pore, 0), round(eff, 0)
(2725.0, 936.0, 1789.0)
"""

#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see other modules for the full notice)

from collections import namedtuple

import matplotlib.pyplot as plt
import numpy as np

GAMMA_WATER = 62.4  # pcf


class SoilLayer(namedtuple("SoilLayer", "name, thickness, gamma, color",
                           defaults=(None,))):
    """One stratum: ``thickness`` ft of soil at total unit weight
    ``gamma`` pcf; ``color`` optional for the log plot."""


_DEFAULT_COLORS = ["#e8d8a0", "#c9b18c", "#b0876b", "#9aa5b1", "#8a9a5b",
                   "#d4c4ab"]


class SoilProfile:
    def __init__(self, layers: list[SoilLayer],
                 water_table: float | None = None):
        self.layers = [SoilLayer(*l) for l in layers]
        self.water_table = water_table

    @property
    def depth(self) -> float:
        return sum(l.thickness for l in self.layers)

    def stresses_at(self, z: float) -> tuple[float, float, float]:
        """(total, pore, effective) vertical stress (psf) at depth ``z``."""
        total, top = 0.0, 0.0
        for layer in self.layers:
            dz = min(max(z - top, 0.0), layer.thickness)
            total += layer.gamma * dz
            top += layer.thickness
        pore = 0.0
        if self.water_table is not None and z > self.water_table:
            pore = GAMMA_WATER * (z - self.water_table)
        return total, pore, total - pore

    def plot(self, ax=None, spt=None):
        """Boring-log column with layer names; optional ``spt`` list of
        (depth, N) plotted alongside."""
        if ax is None:
            ax = plt.figure(figsize=(4.5, 7)).add_subplot(1, 1, 1)
        top = 0.0
        for i, layer in enumerate(self.layers):
            color = layer.color or _DEFAULT_COLORS[i % len(_DEFAULT_COLORS)]
            ax.add_patch(plt.Rectangle((0.0, -top - layer.thickness), 1.0,
                                       layer.thickness, facecolor=color,
                                       edgecolor="k"))
            ax.annotate(
                f"{layer.name}\n$\\gamma$={layer.gamma:g} pcf",
                (0.5, -top - layer.thickness / 2.0), ha="center",
                va="center", fontsize=9)
            top += layer.thickness
        if self.water_table is not None:
            ax.axhline(-self.water_table, color="c", lw=1.4, ls="--")
            ax.annotate("▽ GWT", (1.02, -self.water_table), color="c",
                        fontsize=10, va="center")
        if spt:
            depths, ns = zip(*spt)
            ax2 = ax.twiny()
            ax2.plot(ns, [-d for d in depths], "ko-", markersize=4, lw=0.8)
            ax2.set_xlabel("SPT N (blows/ft)")
        ax.set_xlim(0.0, 1.4)
        ax.set_ylim(-self.depth * 1.02, 0.5)
        ax.set_ylabel("Depth (ft)")
        ax.set_xticks([])
        ax.set_title("Soil Profile")
        return ax.get_figure()

    def plot_stress_profile(self, ax=None, n: int = 300):
        """Total stress, pore pressure, and effective stress vs depth."""
        if ax is None:
            ax = plt.figure(figsize=(6, 7)).add_subplot(1, 1, 1)
        zs = np.linspace(0.0, self.depth, n)
        data = np.array([self.stresses_at(z) for z in zs])
        for col, (label, style) in enumerate(
            (("total stress", "b-"), ("pore pressure", "c--"),
             ("effective stress", "r-"))):
            ax.plot(data[:, col], -zs, style, label=label, lw=1.6)
        if self.water_table is not None:
            ax.axhline(-self.water_table, color="c", lw=0.8, ls=":")
        ax.set_xlabel("Vertical stress (psf)")
        ax.set_ylabel("Depth (ft)")
        ax.set_title("Vertical Stress Profile")
        ax.legend(loc="best", fontsize=9)
        ax.grid(True, alpha=0.3)
        return ax.get_figure()
