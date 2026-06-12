"""Plane truss analysis by the method of joints, with the force diagram.

This is the general-statics face of
:class:`civilpy.structural.strut_and_tie.StrutAndTieModel` — identical
solver and plotting (tension red/solid, compression blue/dashed), plus
member-length and axial-stress helpers for sizing.

Examples
--------
>>> t = Truss()
>>> t.add_node("A", 0, 0)
>>> t.add_node("B", 12, 0)
>>> t.add_node("C", 6, 8)
>>> t.add_member("A", "B")
>>> t.add_member("A", "C")
>>> t.add_member("B", "C")
>>> t.add_support("A", fix_x=True, fix_y=True)
>>> t.add_support("B", fix_y=True)
>>> t.add_load("C", fx=10)
>>> f = t.solve()
>>> round(t.member_lengths()[("A", "C")], 0)
10.0
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

from civilpy.structural.strut_and_tie import StrutAndTieModel


class Truss(StrutAndTieModel):
    """Pin-jointed plane truss; see the base class for the full API."""

    def member_lengths(self) -> dict[tuple[str, str], float]:
        return {(a, b): self._direction(a, b)[2] for a, b in self.members}

    def member_stresses(self, areas) -> dict[tuple[str, str], float]:
        """Axial stress per member (force units / area units).  ``areas``
        is a single area applied to every member or a {(a, b): area}
        mapping."""
        if self.forces is None:
            self.solve()
        if not isinstance(areas, dict):
            areas = {m: float(areas) for m in self.members}
        return {m: self.forces[m] / areas[m] for m in self.members}

    def plot(self, ax=None, force_units: str = "kips",
             show_reactions: bool = True):
        fig = super().plot(ax=ax, force_units=force_units,
                           show_reactions=show_reactions)
        fig.axes[0].set_title("Truss — Member Forces")
        return fig
