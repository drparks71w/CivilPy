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
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

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
