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

"""Hand-checked values for the Chapter 8 timber factors and flexure."""

import math

import pytest

from civilpy.structural.aashto import lrfd


class TestFactors:
    def test_ckf(self):
        assert lrfd.format_conversion_ckf(0.85) == pytest.approx(2.5 / 0.85)
        assert lrfd.format_conversion_ckf(0.90, bearing=True) == pytest.approx(
            2.1 / 0.90
        )

    def test_cf_deep_beam(self):
        assert lrfd.size_factor_cf(16.0) == pytest.approx((12.0 / 16.0) ** (1 / 9))
        assert lrfd.size_factor_cf(10.0) == 1.0

    def test_ci(self):
        assert lrfd.incising_factor_ci() == 0.80
        assert lrfd.incising_factor_ci(modulus=True) == 0.95

    def test_clambda(self):
        assert lrfd.time_effect_clambda("Strength I") == 0.8
        assert lrfd.time_effect_clambda("Strength II") == 1.0

    def test_bearing_cb(self):
        assert lrfd.bearing_factor_cb(3.0) == pytest.approx(3.375 / 3.0)
        assert lrfd.bearing_factor_cb(8.0) == 1.0
        assert lrfd.bearing_factor_cb(3.0, near_end=True) == 1.0


class TestBeamStability:
    # 6x16 stringer, Le = 120 in, Fb* = 2.0 ksi, E' = 1300 ksi
    def test_cl_formula(self):
        r = lrfd.beam_stability_cl(
            f_b_star=2.0, e_adj=1300.0, l_e=120.0, d=16.0, b=6.0
        )
        r_b = math.sqrt(120.0 * 16.0 / 36.0)
        f_be = 0.76 * 1300.0 / r_b**2
        a = f_be / 2.0
        expected = (1 + a) / 1.9 - math.sqrt((1 + a) ** 2 / 3.61 - a / 0.95)
        assert r.details["RB"] == pytest.approx(r_b)
        assert r.capacity == pytest.approx(expected)
        assert 0.0 < r.capacity < 1.0
        assert r.details["RB_ok"]

    def test_stockier_beam_higher_cl(self):
        slender = lrfd.beam_stability_cl(
            f_b_star=2.0, e_adj=1300.0, l_e=120.0, d=16.0, b=4.0
        )
        stocky = lrfd.beam_stability_cl(
            f_b_star=2.0, e_adj=1300.0, l_e=120.0, d=16.0, b=8.0
        )
        assert stocky.capacity > slender.capacity

    def test_msr_grading_higher(self):
        vis = lrfd.beam_stability_cl(
            f_b_star=2.0, e_adj=1300.0, l_e=120.0, d=16.0, b=6.0
        )
        msr = lrfd.beam_stability_cl(
            f_b_star=2.0, e_adj=1300.0, l_e=120.0, d=16.0, b=6.0, grading="msr"
        )
        assert msr.capacity > vis.capacity


class TestFlexure:
    def test_resistance(self):
        # 6x16: Sx = 6*16^2/6 = 256 in^3, Fb_adj = 2.0 ksi, CL = 0.9
        r = lrfd.timber_flexural_resistance(
            f_b_adj=2.0, s_x=256.0, c_l=0.9, m_u=300.0
        )
        assert r.capacity == pytest.approx(2.0 * 256.0 * 0.9)
        assert r.phi == 0.85
        assert r.ok  # 0.85*460.8 = 391.7 > 300

    def test_timber_design_loop(self):
        """Pick a stringer depth for a demand by looping sizes."""
        m_u = 350.0  # kip-in
        passing = [
            d for d in (12.0, 14.0, 16.0, 18.0)
            if lrfd.timber_flexural_resistance(
                f_b_adj=2.0 * lrfd.size_factor_cf(d),
                s_x=6.0 * d**2 / 6.0,
                m_u=m_u,
            ).ok
        ]
        assert passing
        assert 12.0 not in passing  # too shallow for this demand


class TestRegistry:
    def test_timber_articles_registered(self):
        for num in ("8.4.4.2", "8.4.4.4", "8.4.4.7", "8.4.4.9",
                    "8.6.2", "8.8.3", "8.6"):
            assert num in lrfd.ARTICLES


class TestVolumeFactor:
    def test_small_member_is_one(self):
        assert lrfd.volume_factor_cv(d=10.0, b=5.0, l_ft=20.0) == 1.0

    def test_large_glulam_reduces(self):
        cv = lrfd.volume_factor_cv(d=36.0, b=8.75, l_ft=60.0)
        expected = ((12.0 / 36.0) * (5.125 / 8.75) * (21.0 / 60.0)) ** 0.10
        assert cv == pytest.approx(expected)
        assert cv < 1.0

    def test_southern_pine_exponent(self):
        other = lrfd.volume_factor_cv(d=36.0, b=8.75, l_ft=60.0)
        sp = lrfd.volume_factor_cv(d=36.0, b=8.75, l_ft=60.0,
                                   southern_pine=True)
        assert sp > other  # smaller exponent, milder reduction


class TestColumnStability:
    def test_cp_formula(self):
        # 8x8 post, Le=96: Le/d = 12, FcE = 0.76*1300/144 = 6.861
        # Fco' = 1.0: B = 6.861
        r = lrfd.column_stability_cp(f_co_adj=1.0, e_adj=1300.0,
                                     l_e=96.0, d=8.0)
        b = 0.76 * 1300.0 / 144.0
        expected = (1 + b) / 1.6 - math.sqrt(((1 + b) / 1.6) ** 2 - b / 0.8)
        assert r.capacity == pytest.approx(expected)
        assert 0.9 < r.capacity < 1.0  # stocky column

    def test_slender_column_low_cp(self):
        stocky = lrfd.column_stability_cp(1.0, 1300.0, l_e=96.0, d=8.0)
        slender = lrfd.column_stability_cp(1.0, 1300.0, l_e=288.0, d=8.0)
        assert slender.capacity < stocky.capacity
        assert slender.details["slenderness_ok"]

    def test_over_slender_flagged(self):
        r = lrfd.column_stability_cp(1.0, 1300.0, l_e=440.0, d=8.0)
        assert not r.details["slenderness_ok"]
        assert not r.ok

    def test_glulam_c_higher_cp(self):
        sawn = lrfd.column_stability_cp(1.0, 1300.0, 192.0, 8.0, c=0.8)
        glulam = lrfd.column_stability_cp(1.0, 1300.0, 192.0, 8.0, c=0.9)
        assert glulam.capacity > sawn.capacity
