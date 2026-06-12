"""Pressure-pipe energy and hydraulic grade lines.

A :class:`PipeProfile` is a chain of pipe segments leaving a reservoir
(or any known energy elevation).  Each segment carries Darcy-Weisbach
friction (``h_f = f L/D * V^2/2g``) plus a lumped minor-loss coefficient
applied at its entrance, so fittings, bends, entrances, and expansions
land where they occur.  The EGL steps down at each minor loss and slopes
down along each run; the HGL hangs one velocity head below it — the
classic profile sketch, including the sub-atmospheric warning zone where
the HGL dips below the pipe.

US units: ft, cfs; diameters in inches.

Examples
--------
A 12-in line, 500 ft long, f = 0.02, square entrance (K = 0.5),
running 4 cfs out of a reservoir at El. 250:

>>> p = PipeProfile([PipeSegment(500.0, 12.0, f=0.02, k_minor=0.5)],
...                 node_elevations_ft=[200.0, 180.0],
...                 source_energy_ft=250.0, q_cfs=4.0)
>>> round(p.velocity_fps(0), 2)
5.09
>>> round(p.total_head_loss(), 2)              # friction + entrance
4.23
>>> round(p.egl_at_end(), 2)
245.77
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
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np

G = 32.2  # ft/s^2


@dataclass
class PipeSegment:
    """One run of pipe: ``k_minor`` is the lumped minor-loss
    coefficient applied at the segment's upstream end (entrance, bend,
    valve, ...)."""

    length_ft: float
    diameter_in: float
    f: float = 0.02
    k_minor: float = 0.0

    @property
    def area_ft2(self) -> float:
        return math.pi / 4.0 * (self.diameter_in / 12.0) ** 2


class PipeProfile:
    """A reservoir-fed pipe chain with its EGL/HGL profile.

    ``node_elevations_ft`` are the pipe centerline elevations at each
    segment end (``len(segments) + 1`` values); ``source_energy_ft`` is
    the starting energy elevation (reservoir water surface).
    """

    def __init__(self, segments, node_elevations_ft, source_energy_ft: float,
                 q_cfs: float):
        self.segments = list(segments)
        if len(node_elevations_ft) != len(self.segments) + 1:
            raise ValueError(f"need {len(self.segments) + 1} node "
                             f"elevations, got {len(node_elevations_ft)}")
        self.node_z = [float(z) for z in node_elevations_ft]
        self.source_energy = float(source_energy_ft)
        self.q = float(q_cfs)

    # ── Hydraulics ─────────────────────────────────────────────────────

    def velocity_fps(self, i: int) -> float:
        return self.q / self.segments[i].area_ft2

    def velocity_head_ft(self, i: int) -> float:
        return self.velocity_fps(i) ** 2 / (2.0 * G)

    def friction_loss_ft(self, i: int) -> float:
        seg = self.segments[i]
        return (seg.f * seg.length_ft / (seg.diameter_in / 12.0)
                * self.velocity_head_ft(i))

    def minor_loss_ft(self, i: int) -> float:
        return self.segments[i].k_minor * self.velocity_head_ft(i)

    def total_head_loss(self) -> float:
        return sum(self.friction_loss_ft(i) + self.minor_loss_ft(i)
                   for i in range(len(self.segments)))

    def egl_at_end(self) -> float:
        return self.source_energy - self.total_head_loss()

    def grade_lines(self):
        """Stations and grade-line elevations: ``(x, egl, hgl, z_pipe)``
        arrays with two points per segment so minor losses show as
        vertical EGL drops."""
        x, egl, hgl, z = [0.0], [self.source_energy], [self.source_energy], \
            [self.node_z[0]]
        station, energy = 0.0, self.source_energy
        for i, seg in enumerate(self.segments):
            energy -= self.minor_loss_ft(i)
            hv = self.velocity_head_ft(i)
            x.append(station)
            egl.append(energy)
            hgl.append(energy - hv)
            z.append(self.node_z[i])
            energy -= self.friction_loss_ft(i)
            station += seg.length_ft
            x.append(station)
            egl.append(energy)
            hgl.append(energy - hv)
            z.append(self.node_z[i + 1])
        return (np.array(x), np.array(egl), np.array(hgl), np.array(z))

    def low_pressure_stations(self):
        """(station, margin) pairs where the HGL falls below the pipe —
        sub-atmospheric pressure, the cavitation/air-binding warning."""
        x, _, hgl, z = self.grade_lines()
        return [(float(xi), float(h - zi))
                for xi, h, zi in zip(x, hgl, z) if h < zi]

    # ── Visualization ──────────────────────────────────────────────────

    def plot_egl_hgl(self, ax=None):
        """The profile sketch: pipe on its alignment, EGL solid red,
        HGL dashed blue, reservoir at the source, and any
        sub-atmospheric zone shaded.  Returns the figure."""
        x, egl, hgl, z = self.grade_lines()
        if ax is None:
            ax = plt.figure(figsize=(9, 5)).add_subplot(1, 1, 1)
        ax.plot(x, z, "k-", lw=3.0, label="pipe")
        ax.plot(x, egl, "r-", lw=1.6, label="EGL")
        ax.plot(x, hgl, "b--", lw=1.6, label="HGL")
        span = max(x[-1], 1.0)
        ax.fill_between([-0.06 * span, 0.0],
                        self.node_z[0] - 2.0, self.source_energy,
                        color="b", alpha=0.25, label="reservoir")
        ax.fill_between(x, z, hgl, where=hgl < z, color="r", alpha=0.2,
                        label="HGL below pipe (p < 0)")
        for i in range(len(self.segments)):
            xm = (x[2 * i + 1] + x[2 * i + 2]) / 2.0
            seg = self.segments[i]
            ax.annotate(f'{seg.diameter_in:g}" — '
                        f"V = {self.velocity_fps(i):.1f} fps",
                        (xm, (z[2 * i + 1] + z[2 * i + 2]) / 2.0),
                        textcoords="offset points", xytext=(0, -16),
                        fontsize=8, ha="center")
        ax.set_xlabel("Station (ft)")
        ax.set_ylabel("Elevation (ft)")
        ax.set_title(f"EGL / HGL Profile — Q = {self.q:g} cfs, "
                     f"$h_L$ = {self.total_head_loss():.2f} ft")
        ax.legend(loc="best", fontsize=9)
        ax.grid(True, alpha=0.3)
        return ax.get_figure()
