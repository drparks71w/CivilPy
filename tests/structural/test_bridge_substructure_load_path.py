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
from civilpy.structural.odot.capped_pile_abutment import AbutmentInput, layout_capped_pile_abutment

def test_track_c_load_path():
    """
    Vertical Slice Track C: Load transfer from Slab Bridge to Abutment.
    """
    # 1. Superstructure: SB-1-24 (20ft span, 30ft width)
    bridge_inp = SlabBridgeInput(span_ft=20, width_ft=30, skew_deg=0)
    bridge = SlabBridgeComponent(bridge_inp)

    # Analyze L1 model (pure Python)
    # calculate_l1_envelope gives moments, but for reactions we'll use the structural model
    hub = bridge.structural_model(level="L1")

    # Simulate a "solved" model by manually adding reactions to the results
    # M_total_DL = 14.74 k-ft per 1ft strip (from B1 test)
    # Total Reaction per strip = wL/2 = 0.2948 * 20 / 2 = 2.948 kips
    # Total Reaction for full width (30ft) = 2.948 * 30 = 88.44 kips
    from civilpy.structural.structural_model import Result
    res = Result(case="Total_DL")
    # Supports are nodes 'Support_A' and 'Support_B'
    n1_id = hub.node_by_label("Support_A").id
    n2_id = hub.node_by_label("Support_B").id

    # Vertical reaction FZ is at index 2
    res.reactions[n1_id] = (0, 0, 44.22, 0, 0, 0) # Half on each abutment
    res.reactions[n2_id] = (0, 0, 44.22, 0, 0, 0)
    hub.results["Total_DL"] = res

    # 2. Extract reactions
    reactions = bridge.extract_bearing_reactions(hub)
    assert math.isclose(reactions["A"], 44.22, abs_tol=0.1)

    # 3. Substructure: CPA-1-08 (Capped Pile Abutment)
    # 30ft width -> 5 piles @ 7ft approx
    abut_inp = AbutmentInput(wingwall_length_ft=15, skew_deg=0, n_piles=5, pile_spacing_ft=7, footing_depth_ft=3.5)
    abut_layout = layout_capped_pile_abutment(abut_inp)

    # Produce Abutment analytical model loaded with the bridge reaction
    abut_hub = abut_layout.structural_model(reaction=reactions["A"])

    # Verify Abutment Hub
    assert len(abut_hub.nodes) == 5
    assert len(abut_hub.elements) == 4
    assert len(abut_hub.beam_loads) == 4

    # Cap length = (5-1)*7 + 2*1.5 = 28 + 3 = 31 ft
    # Load = 44.22 / 31 = 1.426 klf
    for bl in abut_hub.beam_loads:
        assert math.isclose(bl.w_start, 1.426, rel_tol=1e-3)

    print("Track C Load Path Success: Successfully transferred 44.22 kips to abutment cap model.")

if __name__ == "__main__":
    test_track_c_load_path()
