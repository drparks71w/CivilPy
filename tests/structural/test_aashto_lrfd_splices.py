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
