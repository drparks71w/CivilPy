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

"""Spot-checks of the Ohio DOT Midwest Guardrail System catalog against the
cited Standard Roadway Construction Drawings (MGS series)."""

import pytest

from civilpy.structural.odot import (
    MGS,
    MGS_DRAWINGS,
    MGS_POST_SPACINGS,
    MGS_STEEL_POSTS,
    bridge_terminal_assemblies,
    mgs_drawing,
    terminals_for_railing,
)


class TestMGSStandard:
    """Standard Type MGS parameters (MGS-2.1, sheets P.1-P.2)."""

    def test_rail_height(self):
        assert MGS.rail_height == 31.0
        assert MGS.rail_height_tolerance_new == 1.0
        assert MGS.rail_height_tolerance_existing == 3.0

    def test_post_lengths_and_embedment(self):
        assert MGS.standard_post_length == 72.0   # 6 ft-0 in
        assert MGS.round_wood_post_length == 68.0  # 5 ft-8 in
        assert MGS.long_post_length == 97.0        # 8 ft-1 in
        assert MGS.embedment == 40.0               # 3 ft-4 in
        assert MGS.round_wood_embedment == 36.0    # 3 ft-0 in

    def test_post_bolt_and_panels(self):
        assert MGS.post_bolt_diameter == 0.625     # 5/8 in
        assert MGS.rail_panel_lengths == (12.5, 25.0)


class TestPostSpacing:
    """Post spacing options and required blockout heights (MGS-2.1)."""

    def test_standard_spacing(self):
        ps = MGS_POST_SPACINGS["standard"]
        assert ps.spacing == 75.0           # 6 ft-3 in
        assert ps.blockout_height == 12.0

    def test_half_spacing(self):
        ps = MGS_POST_SPACINGS["half"]
        assert ps.spacing == 37.5           # 3 ft-1.5 in
        assert ps.blockout_height == 10.0

    def test_quarter_spacing(self):
        ps = MGS_POST_SPACINGS["quarter"]
        assert ps.spacing == 18.75          # 1 ft-6.75 in
        assert ps.blockout_height == 14.0

    def test_half_is_one_half_standard(self):
        assert MGS_POST_SPACINGS["half"].spacing == pytest.approx(
            MGS_POST_SPACINGS["standard"].spacing / 2.0
        )

    def test_quarter_is_one_quarter_standard(self):
        assert MGS_POST_SPACINGS["quarter"].spacing == pytest.approx(
            MGS_POST_SPACINGS["standard"].spacing / 4.0
        )

    def test_post_spacing_helper(self):
        assert MGS.post_spacing() == 75.0
        assert MGS.post_spacing("quarter") == 18.75


class TestSteelPosts:
    """Steel beam post sections (MGS-2.1 sheet P.2 table)."""

    def test_rolled_w6x9(self):
        p = MGS_STEEL_POSTS["W6x9 rolled"]
        assert p.depth == 5.9
        assert p.flange_width == 3.94
        assert p.flange_thickness == 0.215
        assert p.web_thickness == 0.170

    def test_welded_6x8_5(self):
        p = MGS_STEEL_POSTS["6x8.5 welded"]
        assert p.depth == 6.0
        assert p.flange_thickness == 0.193

    def test_all_share_flange_width(self):
        assert all(p.flange_width == 3.94 for p in MGS_STEEL_POSTS.values())


class TestTransitionRate:
    """Rail-height transition rate (MGS-4.3)."""

    def test_max_two_inches_per_25_ft(self):
        # 2 in of height change per 25 ft of length.
        assert MGS.transition_rate_in_per_ft == pytest.approx(2.0 / 25.0)
        # Ramping 27 in to 31 in (4 in) needs at least 50 ft.
        min_length = (31.0 - 27.0) / MGS.transition_rate_in_per_ft
        assert min_length == pytest.approx(50.0)


class TestDrawingRegistry:
    def test_all_mgs_drawings_present(self):
        # The 16 MGS drawings in utils/scd/roadway.
        assert len(MGS_DRAWINGS) == 16

    def test_keys_match_scd(self):
        for scd, d in MGS_DRAWINGS.items():
            assert scd == d.scd

    def test_lookup(self):
        d = mgs_drawing("MGS-2.1")
        assert d.sheets == 7
        assert d.category == "standard"

    def test_bridge_terminal_assemblies(self):
        btas = {d.scd for d in bridge_terminal_assemblies()}
        assert btas == {"MGS-3.1", "MGS-3.2", "MGS-3.3"}

    def test_terminal_for_tst2(self):
        # The three steel tube railing is served by the TST-2 terminal.
        ds = terminals_for_railing("TST-2-21")
        assert [d.scd for d in ds] == ["MGS-3.3"]

    def test_terminal_for_br1(self):
        ds = terminals_for_railing("BR-1-13")
        assert "MGS-3.1" in [d.scd for d in ds]

    def test_thrie_beam_bullnose_sheets(self):
        assert mgs_drawing("MGS-6.3").sheets == 8
