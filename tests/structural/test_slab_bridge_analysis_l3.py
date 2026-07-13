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

import math
import pytest
from civilpy.structural.odot.slab_bridge import SlabBridgeInput, SlabBridgeComponent

def test_b3_slab_plate_generation():
    """
    Vertical Slice B3: Single-span slab plate FEA (L3).
    Verifies that the component can produce an L3 StructuralModel.
    """
    # 1. Setup a standard SB-1-24: 20ft span, 30ft width, 0 skew
    inp = SlabBridgeInput(span_ft=20, width_ft=30, skew_deg=0)
    bridge = SlabBridgeComponent(inp)

    # 2. Produce L3 Model
    hub = bridge.structural_model(level="L3")

    # 3. Verify Nodes and Elements
    # dx=2.0, dy=2.0 -> nx=10, ny=15
    # Nodes: (nx+1)*(ny+1) = 11 * 16 = 176
    assert len(hub.nodes) == 176

    # Elements: Plate (Quads)
    # Plates: nx * ny = 10 * 15 = 150
    assert len(hub.elements) == 150

    # Check a specific element
    elem = list(hub.elements.values())[0]
    assert elem.midas_type == "PLATE"
    assert len(elem.nodes) == 4

    print("B3 Plate Generation Success: 176 nodes, 150 plate elements.")

if __name__ == "__main__":
    test_b3_slab_plate_generation()
