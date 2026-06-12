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

"""Hand-checked values for RC column checks and moment magnification."""

import pytest

from civilpy.structural.aashto import lrfd


class TestAxial:
    # 36" circular column: Ag = 1017.9, 12 #9 bars Ast = 12.0
    def test_tied(self):
        r = lrfd.rc_column_axial_resistance(
            a_g=1017.9, a_st=12.0, f_c=4.0, f_y=60.0
        )
        p_o = 0.85 * 4.0 * (1017.9 - 12.0) + 60.0 * 12.0
        assert r.details["Po"] == pytest.approx(p_o)
        assert r.capacity == pytest.approx(0.80 * p_o)
        assert r.phi == 0.75

    def test_spiral_higher(self):
        tied = lrfd.rc_column_axial_resistance(1017.9, 12.0, 4.0, 60.0)
        spiral = lrfd.rc_column_axial_resistance(1017.9, 12.0, 4.0, 60.0,
                                                 spiral=True)
        assert spiral.capacity == pytest.approx(tied.capacity * 0.85 / 0.80)


class TestReinforcementLimits:
    def test_typical_column_passes(self):
        # 12.0/1017.9 = 1.18% steel; strength ratio = 12*60/(1017.9*4) = 0.177
        r = lrfd.rc_column_reinforcement_limits(1017.9, 12.0, 4.0, 60.0)
        assert r.ok

    def test_under_reinforced_fails_min(self):
        r = lrfd.rc_column_reinforcement_limits(1017.9, 8.0, 6.0, 60.0)
        # 8*60/(1017.9*6) = 0.0786 < 0.135
        assert not r.details["min_steel"]
        assert not r.ok

    def test_over_reinforced_fails_max(self):
        r = lrfd.rc_column_reinforcement_limits(1000.0, 90.0, 4.0, 60.0)
        assert not r.details["max_steel"]


class TestSpiral:
    def test_required_ratio(self):
        # Ag = 1017.9, Ac = 803.8 (32.0" core): 0.45*(1.2664-1)*4/60
        r = lrfd.rc_spiral_reinforcement(a_g=1017.9, a_c=803.8, f_c=4.0)
        assert r.details["rho_s_min"] == pytest.approx(
            0.45 * (1017.9 / 803.8 - 1.0) * 4.0 / 60.0
        )

    def test_provided_vs_required(self):
        r = lrfd.rc_spiral_reinforcement(
            a_g=1017.9, a_c=803.8, f_c=4.0, rho_s_provided=0.01
        )
        assert r.ok


class TestMomentMagnification:
    def test_short_column_no_magnification(self):
        r = lrfd.moment_magnification(p_u=100.0, p_e=10000.0,
                                      m_1=50.0, m_2=100.0)
        # Cm = 0.6+0.4*0.5 = 0.8; raw delta = 0.8/(1-100/7500) < 1 -> 1.0
        assert r.details["Cm"] == pytest.approx(0.8)
        assert r.capacity == 1.0

    def test_slender_column_magnifies(self):
        r = lrfd.moment_magnification(p_u=500.0, p_e=1500.0,
                                      m_1=100.0, m_2=100.0)
        # Cm = 1.0; delta = 1/(1-500/1125) = 1.8
        assert r.capacity == pytest.approx(1.0 / (1.0 - 500.0 / 1125.0))

    def test_reverse_curvature_lowers_cm(self):
        single = lrfd.moment_magnification(500.0, 1500.0, m_1=100.0, m_2=100.0)
        reverse = lrfd.moment_magnification(500.0, 1500.0, m_1=-100.0, m_2=100.0)
        assert reverse.details["Cm"] < single.details["Cm"]

    def test_sway_requires_sums(self):
        with pytest.raises(ValueError):
            lrfd.moment_magnification(500.0, 1500.0, braced=False)

    def test_sway_magnifier(self):
        r = lrfd.moment_magnification(
            500.0, 1500.0, braced=False, sum_p_u=2000.0, sum_p_e=8000.0
        )
        assert r.details["delta_s"] == pytest.approx(
            1.0 / (1.0 - 2000.0 / 6000.0)
        )


class TestRegistry:
    def test_column_articles_registered(self):
        for num in ("5.6.4.4", "5.6.4.2", "5.6.4.6", "4.5.3.2.2b"):
            assert num in lrfd.ARTICLES
