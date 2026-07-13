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

def test_b2_slab_grillage_generation():
    """
    Vertical Slice B2: Single-span slab grillage (L2).
    Verifies that the component can produce an L2 StructuralModel.
    """
    # 1. Setup a standard SB-1-24: 20ft span, 30ft width, 15deg skew
    inp = SlabBridgeInput(span_ft=20, width_ft=30, skew_deg=15)
    bridge = SlabBridgeComponent(inp)

    # 2. Produce L2 Model
    hub = bridge.structural_model(level="L2")

    # 3. Verify Nodes and Elements
    # dx=2.0, dy=2.0 -> nx=10, ny=15
    # Nodes: (nx+1)*(ny+1) = 11 * 16 = 176
    assert len(hub.nodes) == 176

    # Elements:
    # Longitudinal: (nx)*(ny+1) = 10 * 16 = 160
    # Transverse: (nx+1)*(ny) = 11 * 15 = 165
    # Total: 325
    assert len(hub.elements) == 325

    # 4. Verify Loads
    # Each longitudinal element should have a DC1 beam load
    assert len(hub.beam_loads) == 160

    # Check a specific beam load
    # Slab thickness for 20ft is 16.25 in.
    # DC1_area = (16.25/12) * 0.150 = 0.203125 kip/ft^2
    # For interior strip (width=2.0ft), DC1_klf = 0.40625 kip/ft
    # For exterior strip (width=1.0ft), DC1_klf = 0.203125 kip/ft

    bloads_dc1 = [bl for bl in hub.beam_loads if bl.case == "DC1"]
    assert len(bloads_dc1) == 160

    # Check exterior klf
    # Nodes j=0 or j=15 are exterior
    exterior_bloads = []
    for bl in bloads_dc1:
        elem = hub.elements[bl.element_id]
        node_a = hub.nodes[elem.node_a]
        # At y=0 or y=30
        if math.isclose(node_a.y, 0.0) or math.isclose(node_a.y, 30.0):
            exterior_bloads.append(bl)

    assert len(exterior_bloads) == 20 # 2 edges * 10 segments
    for bl in exterior_bloads:
        assert math.isclose(bl.w_start, 0.203125, rel_tol=1e-5)

    print("B2 Grillage Generation Success: 176 nodes, 325 elements, 160 beam loads.")

if __name__ == "__main__":
    test_b2_slab_grillage_generation()
