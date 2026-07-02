#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Hand-checked values for splice design forces, slab strips, box DFs."""

import math

import pytest

from civilpy.structural.aashto import lrfd


class TestFlangeSplice:
    def test_design_force(self):
        # 16x1 flange, two 1" holes: An = 16 - 2*1.125 = 13.75 (illustrative)
        # Ae = (0.8*65/(0.95*50))*13.75 = 15.05 < Ag = 16
        r = lrfd.flange_splice_design_force(a_n=13.75, a_g=16.0,
                                            f_y=50.0, f_u=65.0)
        a_e = 0.80 * 65.0 / (0.95 * 50.0) * 13.75
        assert r.details["Ae"] == pytest.approx(a_e)
        assert r.capacity == pytest.approx(50.0 * a_e)

    def test_ae_capped_at_gross(self):
        r = lrfd.flange_splice_design_force(a_n=15.5, a_g=16.0,
                                            f_y=50.0, f_u=70.0)
        # (0.8*70/(0.95*50))*15.5 = 18.3 > 16 -> Ag governs
        assert r.details["Ae"] == pytest.approx(16.0)
        assert r.capacity == pytest.approx(800.0)


class TestWebSplice:
    def test_shear_only(self):
        f = lrfd.web_splice_design_forces(v_r_web=400.0, n_bolts=16)
        assert f.v_uw == 400.0
        assert f.h_w == 0.0
        assert f.per_bolt == pytest.approx(25.0)

    def test_moment_excess_adds_horizontal(self):
        f = lrfd.web_splice_design_forces(
            v_r_web=400.0, n_bolts=16, m_u=30000.0, m_flange=24000.0,
            moment_arm=40.0,
        )
        assert f.h_w == pytest.approx(150.0)
        assert f.per_bolt == pytest.approx(
            math.hypot(400.0 / 16.0, 150.0 / 16.0)
        )

    def test_flanges_carry_all_moment(self):
        f = lrfd.web_splice_design_forces(
            v_r_web=400.0, n_bolts=16, m_u=20000.0, m_flange=24000.0
        )
        assert f.h_w == 0.0

    def test_excess_requires_arm(self):
        with pytest.raises(ValueError):
            lrfd.web_splice_design_forces(
                v_r_web=400.0, n_bolts=16, m_u=30000.0, m_flange=24000.0
            )


class TestFlangeSplicePlateSizing:
    # Example 1 (workshop case study): 69" web, Grade 50W / HPS 70W, 5/16
    # web weld, 7/8" bolts.  Top flanges 16/18 wide, bottom 18/20 wide;
    # webs 1/2 and 9/16.  Workbook plates: top 5/8 outer x 11/16 inner,
    # 16 x 7; bottom 3/4 outer x 7/8 inner, 18 x 8.
    def test_top_flange_matches_workbook(self):
        p = lrfd.size_flange_splice_plates(
            flange_width_left=16.0, flange_width_right=18.0,
            flange_thickness=1.0,
            web_thickness_left=0.5, web_thickness_right=0.5625,
            weld_size=0.3125, outer_thickness=0.625,
        )
        assert p.outer_width == pytest.approx(16.0)
        assert p.clearance == pytest.approx(1.4375)
        assert p.inner_width == pytest.approx(7.0)      # 7.28 rounded down
        assert p.inner_thickness == pytest.approx(0.6875)   # 11/16
        assert p.min_thickness == pytest.approx(0.5625)

    def test_bottom_flange_thickness_in_band(self):
        p = lrfd.size_flange_splice_plates(
            flange_width_left=18.0, flange_width_right=20.0,
            flange_thickness=1.375,
            web_thickness_left=0.5, web_thickness_right=0.5625,
            weld_size=0.3125, outer_thickness=0.75,
        )
        assert p.outer_width == pytest.approx(18.0)
        assert p.inner_width == pytest.approx(8.0)       # 8.28 rounded down
        # Workbook picked 7/8" inner plates; must fall inside the 10% band.
        lo, hi = p.inner_thickness_band
        assert lo <= 0.875 <= hi

    def test_example_2_top_flange(self):
        # Ex 2: top flanges 19/22, webs 3/4, outer 9/16 -> inner 5/8, 8.5 wide.
        p = lrfd.size_flange_splice_plates(
            flange_width_left=19.0, flange_width_right=22.0,
            flange_thickness=1.0,
            web_thickness_left=0.75, web_thickness_right=0.75,
            weld_size=0.3125, outer_thickness=0.5625,
        )
        assert p.outer_width == pytest.approx(19.0)
        assert p.clearance == pytest.approx(1.625)
        assert p.inner_width == pytest.approx(8.5)        # 8.69 rounded down
        assert p.inner_thickness == pytest.approx(0.625)  # 5/8

    def test_default_outer_from_minimum(self):
        p = lrfd.size_flange_splice_plates(
            flange_width_left=16.0, flange_width_right=18.0,
            flange_thickness=1.0,
            web_thickness_left=0.5, web_thickness_right=0.5625,
            weld_size=0.3125,
        )
        # No outer thickness given -> rounded-up minimum (9/16").
        assert p.outer_thickness == pytest.approx(0.5625)


class TestWebSplicePlateSizing:
    def test_example_1_seal_governs(self):
        # Ex 1: 69" web, 1/2" web, 5/16" plate, 3" flange clearance ->
        # seal pitch 5.25", 13 bolts per row.
        p = lrfd.size_web_splice_plate(
            web_depth=69.0, web_thickness=0.5, web_thickness_other=0.5625,
            flange_clearance=3.0,
        )
        assert p.thickness == pytest.approx(0.3125)      # 5/16
        assert p.min_thickness == pytest.approx(0.3125)
        assert p.height == pytest.approx(63.0)
        assert p.max_pitch_seal == pytest.approx(5.25)
        assert p.min_bolts_per_row == 13
        assert p.filler_required is False                # 1/16 diff, not over

    def test_example_2_thickness(self):
        # Ex 2: 3/4" web -> min plate 7/16".
        p = lrfd.size_web_splice_plate(
            web_depth=109.0, web_thickness=0.75, web_thickness_other=0.75,
            flange_clearance=2.75,
        )
        assert p.thickness == pytest.approx(0.4375)      # 7/16
        assert p.height == pytest.approx(103.5)
        assert p.filler_required is False

    def test_filler_required_when_webs_differ(self):
        p = lrfd.size_web_splice_plate(
            web_depth=60.0, web_thickness=0.5, web_thickness_other=0.75,
            flange_clearance=3.0,
        )
        assert p.filler_required is True


class TestSlabStrip:
    def test_single_lane(self):
        # L1 = 40, W1 = 30 (capped): E = 10 + 5*sqrt(1200) = 183.2 in
        e = lrfd.slab_equivalent_strip(span_ft=40.0, width_ft=32.0,
                                       n_lanes=2, multi_lane=False)
        assert e == pytest.approx(10.0 + 5.0 * math.sqrt(40.0 * 30.0))

    def test_multi_lane_with_cap(self):
        # E = 84 + 1.44*sqrt(40*32) = 135.5; cap = 12*32/2 = 192
        e = lrfd.slab_equivalent_strip(span_ft=40.0, width_ft=32.0, n_lanes=2)
        assert e == pytest.approx(84.0 + 1.44 * math.sqrt(40.0 * 32.0))

    def test_narrow_bridge_cap_governs(self):
        e = lrfd.slab_equivalent_strip(span_ft=60.0, width_ft=20.0, n_lanes=2)
        assert e == pytest.approx(12.0 * 20.0 / 2.0)

    def test_skew_widens_strip(self):
        straight = lrfd.slab_equivalent_strip(40.0, 32.0, 2)
        skewed = lrfd.slab_equivalent_strip(40.0, 32.0, 2, skew_deg=30.0)
        assert skewed > straight


class TestBoxBeamDF:
    ARGS = dict(b_in=48.0, l_ft=80.0, i_beam=168000.0, j_beam=120000.0,
                n_beams=7)

    def test_k_factor(self):
        df = lrfd.moment_df_interior_box(**self.ARGS)
        k = max(2.5 * 7**-0.2, 1.5)
        assert df.multi_lane == pytest.approx(
            k * (48.0 / 305.0) ** 0.6 * (48.0 / 960.0) ** 0.2
            * (168000.0 / 120000.0) ** 0.06
        )

    def test_one_lane_formula(self):
        df = lrfd.moment_df_interior_box(**self.ARGS)
        k = max(2.5 * 7**-0.2, 1.5)
        assert df.one_lane == pytest.approx(
            k * (48.0 / (33.3 * 80.0)) ** 0.5 * 1.4 ** 0.25
        )
        assert df.applicable

    def test_applicability(self):
        df = lrfd.moment_df_interior_box(**{**self.ARGS, "b_in": 70.0})
        assert not df.applicability["width"]


class TestRegistry:
    def test_articles_registered(self):
        for num in ("6.13.6.1.3b", "6.13.6.1.3c", "4.6.2.3", "4.6.2.2.2b-g"):
            assert num in lrfd.ARTICLES
