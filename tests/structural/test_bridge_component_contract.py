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

from civilpy.transportation.alignment import Alignment, Tangent
from civilpy.structural.placement import Placement, Bridge
from civilpy.structural.odot.slab_bridge import SlabBridgeInput, SlabBridgeComponent

def test_a3_contract():
    # 1. Site
    align = Alignment(start_point=(0,0), start_bearing_deg=90,
                      elements=[Tangent(length_ft=500)])

    # 2. Bridge
    bridge = Bridge(alignment=align)

    # 3. Component
    inp = SlabBridgeInput(span_ft=20, width_ft=30)
    comp = SlabBridgeComponent(inp)

    # 4. Placement
    placed = bridge.add_component(comp, station=100.0)

    # 5. Verification
    print(f"Placed at: {placed.placement.point}")
    x, y, z = placed.placement.point
    assert x == 100.0
    assert abs(y) < 1e-10
    assert z == 0.0

    model = comp.structural_model()
    print(f"Model: {model}")
    assert len(model.nodes) == 2
    assert len(model.elements) == 1

    geom = comp.geometry()
    print(f"Geometry keys: {list(geom.keys())}")
    assert "layout" in geom

if __name__ == "__main__":
    test_a3_contract()
    print("A3 Contract Verification Passed!")
