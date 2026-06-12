"""Elastic flexural stress distribution over a beam cross-section.

The classic sigma = M*y/I diagram: linear stress through the depth,
zero at the neutral axis, extreme-fiber values labeled.  Works for any
section once its depth, neutral-axis location, and moment of inertia
are known (e.g. from :mod:`civilpy.structural.section_properties`).

Sagging (positive) moment puts the top fiber in compression, drawn to
the left of the zero line, matching the hand-sketch convention.

Examples
--------
>>> round(flexural_stress(1200.0, 800.0, 6.0), 3)   # M=1200 k-in, I=800
9.0
>>> sigma_top, sigma_bot = extreme_fiber_stresses(1200.0, 800.0,
...                                               c_top=8.0, c_bot=4.0)
>>> round(sigma_top, 2), round(sigma_bot, 2)
(-12.0, 6.0)
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

import matplotlib.pyplot as plt


def flexural_stress(m_kip_in: float, i_in4: float, y_in: float) -> float:
    """Bending stress magnitude M*y/I (ksi) at distance ``y_in`` from
    the neutral axis."""
    return m_kip_in * y_in / i_in4


def extreme_fiber_stresses(m_kip_in: float, i_in4: float, *,
                           c_top: float, c_bot: float) -> tuple[float, float]:
    """(sigma_top, sigma_bot) in ksi with the structural sign
    convention: compression negative.  Positive (sagging) moment gives a
    negative top stress and positive bottom stress."""
    return (-m_kip_in * c_top / i_in4, m_kip_in * c_bot / i_in4)


def plot_flexural_stress(m_kip_in: float, i_in4: float, *, depth_in: float,
                         y_bar_in: float, width_in: float | None = None,
                         ax=None):
    """Draw the linear elastic stress distribution through the depth.

    ``y_bar_in`` locates the neutral axis above the bottom fiber, so
    asymmetric sections (composite girders, tees) show their unequal
    extreme-fiber stresses.  When ``width_in`` is given a rectangular
    section silhouette is sketched beside the diagram for scale.
    Compression plots left of the zero line (negative), tension right.
    Returns the figure.
    """
    c_top = depth_in - y_bar_in
    c_bot = y_bar_in
    sigma_top, sigma_bot = extreme_fiber_stresses(
        m_kip_in, i_in4, c_top=c_top, c_bot=c_bot)

    if ax is None:
        ax = plt.figure(figsize=(6, 5)).add_subplot(1, 1, 1)

    # depth measured from the top fiber, axis inverted like a section cut
    y_na = c_top
    ax.plot([sigma_top, 0.0, sigma_bot], [0.0, y_na, depth_in],
            "k-", lw=2.2)
    ax.axvline(0.0, color="0.5", lw=0.9)
    ax.axhline(y_na, color="0.5", ls="-.", lw=0.9)
    ax.fill_betweenx([0.0, y_na], [sigma_top, 0.0], 0.0,
                     color="tab:blue", alpha=0.25)
    ax.fill_betweenx([y_na, depth_in], 0.0, [0.0, sigma_bot],
                     color="tab:red", alpha=0.25)
    ax.annotate(f"{sigma_top:+.2f} ksi", (sigma_top, 0.0),
                textcoords="offset points", xytext=(4, 6), fontsize=10)
    ax.annotate(f"{sigma_bot:+.2f} ksi", (sigma_bot, depth_in),
                textcoords="offset points", xytext=(4, -14), fontsize=10)
    ax.annotate("N.A.", (0.0, y_na), textcoords="offset points",
                xytext=(4, 4), fontsize=9, color="0.35")

    if width_in is not None:
        span = max(abs(sigma_top), abs(sigma_bot), 1e-9)
        x0 = -1.6 * span
        scale = 0.8 * span / width_in
        ax.add_patch(plt.Rectangle((x0, 0.0), width_in * scale, depth_in,
                                   fill=False, lw=1.5, color="0.3"))
        ax.axhline(y_na, xmin=0.0, xmax=1.0, color="0.5", ls="-.", lw=0.5)

    ax.invert_yaxis()
    ax.set_xlabel("Bending stress (ksi) — compression negative")
    ax.set_ylabel("Depth from top fiber (in)")
    ax.set_title(rf"Elastic Flexural Stress, $\sigma = My/I$ "
                 rf"(M = {m_kip_in / 12.0:.0f} kip-ft)")
    ax.grid(True, alpha=0.3)
    return ax.get_figure()
