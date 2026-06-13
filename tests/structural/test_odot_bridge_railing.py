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

"""Spot-checks of the Ohio DOT bridge-railing catalog against the cited
Standard Bridge Drawings (BR-1-13, SBR-1/2/3-20, TST-1-99, TST-2-21,
DBR-2-73, DBR-3-11, TBR-1-11, PCB-91)."""

import pytest

from civilpy.structural.aashto.lrfd.railing import TEST_LEVEL_LOADS
from civilpy.structural.odot import (
    BRIDGE_RAILINGS,
    BridgeRailing,
    railing,
    railings_for_test_level,
)


class TestCatalogIntegrity:
    def test_designation_keys_match(self):
        for key, r in BRIDGE_RAILINGS.items():
            assert key == r.designation

    def test_all_entries_are_bridge_railings(self):
        assert all(isinstance(r, BridgeRailing) for r in BRIDGE_RAILINGS.values())

    def test_lookup_helper(self):
        assert railing("BR-1 (36 in)").scd == "BR-1-13"

    def test_lookup_missing_raises(self):
        with pytest.raises(KeyError):
            railing("does-not-exist")

    def test_test_levels_are_known_or_blank(self):
        # Every stated test level must index Table A13.2-1; blanks are the
        # only allowed "unrated" marker.
        for r in BRIDGE_RAILINGS.values():
            assert r.test_level == "" or r.test_level in TEST_LEVEL_LOADS

    def test_test_level_load_linkage(self):
        # A rated railing returns its Table A13.2-1 forces; an unrated one
        # returns None.
        assert railing("BR-1 (42 in)").test_level_load() is TEST_LEVEL_LOADS["TL-5"]
        assert railing("DBR-2 (deep beam)").test_level_load() is None

    def test_filter_by_test_level(self):
        tl5 = {r.designation for r in railings_for_test_level("TL-5")}
        assert tl5 == {
            "BR-1 (42 in)",
            "SBR-1 (42 in)",
            "SBR-2 (57 in median, back-to-back)",
        }


class TestBR113:
    """New Jersey shape concrete bridge railing (BR-1-13, sheet 9/9)."""

    def test_36in_section_area_and_level(self):
        r = railing("BR-1 (36 in)")
        assert r.shape == "New Jersey"
        assert r.height == 36.0
        assert r.section_area == pytest.approx(423.25)
        assert r.test_level == "TL-4"  # NCHRP 350 TL-4

    def test_42in_section_area_and_level(self):
        r = railing("BR-1 (42 in)")
        assert r.height == 42.0
        assert r.section_area == pytest.approx(474.50)
        assert r.test_level == "TL-5"  # NCHRP 350 TL-5

    def test_materials_and_transition(self):
        r = railing("BR-1 (36 in)")
        assert r.f_c == 4.5 and r.f_y == 60.0
        assert r.vertical_bar_spacing == 12.0
        assert r.transition_length_ft == 14.0
        assert r.transition_volume_cy == pytest.approx(1.63)
        assert railing("BR-1 (42 in)").transition_volume_cy == pytest.approx(1.71)


class TestSingleSlope:
    """Single slope concrete railings (SBR-1/2/3-20, sheet 5/5)."""

    def test_sbr3_36in(self):
        r = railing("SBR-3 (36 in)")
        assert r.shape == "single slope"
        assert r.height == 36.0
        assert r.section_area == pytest.approx(524.0)
        assert r.test_level == "TL-4"
        assert r.transition_volume_cy == pytest.approx(1.74)

    def test_sbr1_42in(self):
        r = railing("SBR-1 (42 in)")
        assert r.height == 42.0
        assert r.section_area == pytest.approx(588.0)
        assert r.test_level == "TL-5"
        assert r.transition_volume_cy == pytest.approx(1.82)

    def test_sbr2_median_type_b1_is_tl3(self):
        r = railing("SBR-2 (57 in median)")
        assert r.height == 57.0
        # 9.05 sq ft section reported on the drawing.
        assert r.section_area == pytest.approx(9.05 * 144.0)
        assert r.test_level == "TL-3"
        assert r.vertical_bar_spacing == 24.0  # Type B1: 2 ft-0 in o.c.

    def test_sbr2_back_to_back_is_tl5(self):
        r = railing("SBR-2 (57 in median, back-to-back)")
        assert r.test_level == "TL-5"
        assert r.vertical_bar_spacing == 7.0

    def test_single_slope_design_strengths(self):
        for d in ("SBR-1 (42 in)", "SBR-3 (36 in)", "SBR-2 (57 in median)"):
            r = railing(d)
            assert r.f_c == 4.5 and r.f_y == 60.0


class TestSteelTube:
    """Steel tube railings (TST-1-99 sheet 4/4, TST-2-21 sheet 15/15)."""

    def test_tst1_twin_tube(self):
        r = railing("TST-1 (twin steel tube)")
        assert r.material == "steel"
        assert r.test_level == "TL-4"  # NCHRP 350 TL-4
        assert r.post_shape == "W6x25"
        assert r.post_spacing == 75.0  # 6 ft-3 in
        assert r.rail_element == "2 - TS 8x4x5/16"
        assert r.f_y_steel == 46.0  # tube yield

    def test_tst2_three_tube(self):
        r = railing("TST-2 (three steel tube)")
        assert r.test_level == "TL-4"  # MASH TL-4
        assert r.post_spacing == 96.0  # 8 ft
        assert r.f_y_steel == 50.0
        assert r.weight_per_ft == 80.0
        assert r.f_c == 4.5


class TestBeamGuardrail:
    """Deep / thrie beam railings (DBR-2-73, DBR-3-11, TBR-1-11)."""

    def test_dbr2_legacy_unrated(self):
        r = railing("DBR-2 (deep beam)")
        assert r.scd == "DBR-2-73"
        assert r.test_level == ""  # no numeric level on the 1973 drawing
        assert r.test_level_load() is None
        assert r.post_shape == "W6x25"
        assert r.post_spacing == 75.0

    def test_dbr3_retrofit_tl3(self):
        r = railing("DBR-3 (deep beam retrofit)")
        assert r.test_level == "TL-3"  # FHWA HSSD/B-207
        assert "HSS 8x4x3/16" in r.rail_element

    def test_tbr1_thrie_beam_unrated(self):
        r = railing("TBR-1 (thrie beam retrofit)")
        assert r.test_level == ""  # NHS-acceptable, no numeric level stated
        assert r.f_c == 4.0
        assert r.post_spacing == 75.0


class TestPortableBarrier:
    """Portable concrete barrier (PCB-91)."""

    def test_unanchored_is_tl3(self):
        r = railing("PCB (portable, unanchored)")
        assert r.test_level == "TL-3"
        assert r.height == 32.0
        assert r.base_width == 24.0
        assert r.f_c == 4.0
        assert r.segment_length_ft == (10.0, 12.0)

    def test_anchored_is_tl4(self):
        assert railing("PCB (portable, anchored)").test_level == "TL-4"
