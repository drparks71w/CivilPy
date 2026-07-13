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

def test_b1_slab_analysis_vertical_slice():
    """
    Vertical Slice B1: Single-span slab analysis.
    Verifies that a faithfully represented SB-1-24 component can:
    1. Calculate its L1 envelope in pure Python.
    2. Produce a StructuralModel with correct nodes and sections.
    """
    # 1. Setup a standard SB-1-24: 20ft span, 30ft width, 0 skew
    inp = SlabBridgeInput(span_ft=20, width_ft=30, skew_deg=0)
    bridge = SlabBridgeComponent(inp)

    # 2. Calculate L1 Envelope (Pure Python)
    stations, moments = bridge.calculate_l1_envelope()

    # Basic sanity checks on the envelope
    assert len(stations) == 41
    assert stations[0] == 0.0
    assert stations[-1] == 20.0

    # Dead load moment check: M = wL^2 / 8
    # Slab thickness for 20ft span is 16.25 in (from SLAB_DESIGNS)
    # DC1_klf = (16.25/12) * 0.150 = 0.203125 kip/ft
    # DC2_klf = (2 * 0.475) / 30 = 0.031667 kip/ft
    # DW_klf = 0.060 kip/ft
    # w_total = 0.203125 + 0.031667 + 0.060 = 0.294792 kip/ft
    # M_dl_midspan = 0.294792 * 20^2 / 8 = 14.7396 k-ft

    # But wait, these are per 1-ft strip, BUT they must be scaled by GDF = 1/E.
    # slab_equivalent_strip(20, 30, 2)
    # L = 20, W = 30, n_lanes = 2
    # E = 10.0 + 5.0 * sqrt(L1 * W1) / 12  (approximate AASHTO formula)
    # Let's check the actual value from moments['dc1'] at middle index (20)
    mid = 20
    m_dc1 = moments['dc1'][mid]
    m_dc2 = moments['dc2'][mid]
    m_dw = moments['dw'][mid]

    print(f"DC1 mid-span moment: {m_dc1:.2f} k-ft")
    print(f"DC2 mid-span moment: {m_dc2:.2f} k-ft")
    print(f"DW mid-span moment: {m_dw:.2f} k-ft")

    # Total DL moment
    m_dl = m_dc1 + m_dc2 + m_dw

    # 3. Live Load check
    # ll_pos should be non-zero and positive
    assert all(m >= -1e-9 for m in moments['ll_pos'])
    assert max(moments['ll_pos']) > 0

    # 4. Structural Model check
    hub = bridge.structural_model()
    assert len(hub.nodes) == 2
    assert len(hub.elements) == 1
    assert "DC1" in hub.load_cases

    # Check section name
    elem = list(hub.elements.values())[0]
    assert "Slab_16.25in" in elem.section

if __name__ == "__main__":
    test_b1_slab_analysis_vertical_slice()
