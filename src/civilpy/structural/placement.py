"""
Placement and multi-representation contract for bridge components (A3).

This module defines the base classes for bridge components that can be placed
on an Alignment and Terrain, and emit multiple representations (Rhino/MIDAS).
"""

#  CivilPy
#  Copyright (C) $originalComment.match("Copyright \(C\) (\d+)", 1)-2026 Dane Parks
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

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from civilpy.transportation.alignment import Alignment
    from civilpy.transportation.terrain import Terrain
    from civilpy.structural.structural_model import StructuralModel


@runtime_checkable
class BridgeComponent(Protocol):
    """Protocol for a bridge component that can be placed in a CDE."""

    def geometry(self) -> Any:
        """Returns the geometric representation (e.g. Rhino BREP/curves/points)."""
        ...

    def structural_model(self) -> StructuralModel:
        """Returns the analysis hub representation (StructuralModel)."""
        ...


@dataclass
class Placement:
    """Defines where a component sits relative to the site's project geometry."""
    alignment: Alignment
    station: float
    offset: float = 0.0
    terrain: Terrain | None = None

    @property
    def point(self):
        """Returns the 3D point in global coordinates."""
        return self.alignment.point_at(self.station, self.offset)

    @property
    def elevation(self):
        """Returns the elevation at this placement (alignment profile or terrain)."""
        if self.terrain:
            x, y, _ = self.point
            return self.terrain.elevation_at(x, y)
        return self.alignment.elevation_at(self.station)


class PlacedComponent:
    """Wraps a component with its placement information."""

    def __init__(self, component: BridgeComponent, placement: Placement):
        self.component = component
        self.placement = placement

    @property
    def frame(self):
        """Returns the coordinate frame at the placement (origin, tangent, normal)."""
        return self.placement.alignment.frame_at(self.placement.station)

    def global_geometry(self):
        """Returns geometry transformed into global coordinates."""
        # This will depend on the geometry type (e.g. Rhino transform)
        return self.component.geometry()

    def structural_hub(self) -> StructuralModel:
        """Returns the structural model spoke for this component."""
        return self.component.structural_model()


class Bridge(BridgeComponent):
    """A collection of bridge components forming a complete structure."""

    def __init__(self, alignment: Alignment, terrain: Terrain | None = None):
        self.alignment = alignment
        self.terrain = terrain
        self.components: list[PlacedComponent] = []

    def add_component(self, component: BridgeComponent, station: float, offset: float = 0.0):
        placement = Placement(self.alignment, station, offset, self.terrain)
        placed = PlacedComponent(component, placement)
        self.components.append(placed)
        return placed

    def geometry(self) -> list[Any]:
        return [c.global_geometry() for c in self.components]

    def structural_model(self) -> StructuralModel:
        from civilpy.structural.structural_model import StructuralModel
        hub = StructuralModel()
        # Merge all component models into one hub
        # This requires a merge operation in StructuralModel which we might need to add
        # or we just iterate and add.
        for pc in self.components:
            comp_model = pc.structural_hub()
            # For now, we assume components are responsible for their own absolute positioning
            # in the hub if they know about their placement.
            # In A3, we'll refine how the hub is assembled.
            pass
        return hub
