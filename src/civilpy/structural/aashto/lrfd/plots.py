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

"""Notebook plotting helpers for the LRFD check results.

The check functions themselves stay pure (no matplotlib import on the
calculation path); these helpers render their outputs following the
package-wide convention (optional ``ax``, figure returned).
"""

import matplotlib.pyplot as plt


def plot_pm_interaction(points, ax=None, p_u: float | None = None,
                        m_u: float | None = None, units: str = "kip, kip-in"):
    """Plot a column interaction diagram from
    :func:`~civilpy.structural.aashto.lrfd.columns.rc_pm_interaction_diagram`
    output: the nominal curve dashed, the factored (phi-reduced) curve
    solid, and optionally the factored demand point (Pu, Mu).  Returns the
    figure."""
    if ax is None:
        ax = plt.figure(figsize=(6, 7)).add_subplot(1, 1, 1)
    ax.plot([pt.m_n for pt in points], [pt.p_n for pt in points],
            "b--", lw=1.2, label=r"nominal $(M_n, P_n)$")
    ax.plot([pt.phi_mn for pt in points], [pt.phi_pn for pt in points],
            "b-", lw=1.8, label=r"factored $(\phi M_n, \phi P_n)$")
    if p_u is not None and m_u is not None:
        ax.plot(m_u, p_u, "r*", markersize=14, label=r"$(M_u, P_u)$")
    ax.axhline(0.0, color="k", lw=0.8)
    ax.set_xlabel(f"Moment ({units.split(',')[-1].strip()})")
    ax.set_ylabel(f"Axial ({units.split(',')[0].strip()})")
    ax.set_title("Column P-M Interaction Diagram")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)
    return ax.get_figure()
