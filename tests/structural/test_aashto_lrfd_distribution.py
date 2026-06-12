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

"""Hand-checked values for 4.6.2.2 live-load distribution factors."""

import math

import pytest

from civilpy.structural.aashto import lrfd

# Typical steel I-girder bridge: S = 9 ft, L = 80 ft, ts = 8 in,
# girder I = 40,000 in^4, A = 50 in^2, eg = 30 in, n = 8
KG = lrfd.longitudinal_stiffness_kg(8.0, 40000.0, 50.0, 30.0)
ARGS = dict(s_ft=9.0, l_ft=80.0, t_s=8.0, k_g=KG)


class TestKg:
    def test_formula(self):
        assert KG == pytest.approx(8.0 * (40000.0 + 50.0 * 900.0))


class TestInteriorMoment:
    def test_multi_lane_formula(self):
        df = lrfd.moment_df_interior(**ARGS)
        stiff = KG / (12.0 * 80.0 * 512.0)
        expected = 0.075 + (9.0 / 9.5) ** 0.6 * (9.0 / 80.0) ** 0.2 * stiff**0.1
        assert df.multi_lane == pytest.approx(expected)
        assert 0.5 < df.multi_lane < 0.9  # sane range for 9 ft spacing

    def test_one_lane_formula(self):
        df = lrfd.moment_df_interior(**ARGS)
        stiff = KG / (12.0 * 80.0 * 512.0)
        expected = 0.06 + (9.0 / 14.0) ** 0.4 * (9.0 / 80.0) ** 0.3 * stiff**0.1
        assert df.one_lane == pytest.approx(expected)
        assert df.governing == df.multi_lane  # multi governs at 9 ft

    def test_applicability_flags(self):
        df = lrfd.moment_df_interior(**ARGS)
        assert df.applicable
        wide = lrfd.moment_df_interior(s_ft=18.0, l_ft=80.0, t_s=8.0, k_g=KG)
        assert not wide.applicable
        assert not wide.applicability["spacing"]


class TestInteriorShear:
    def test_formulas(self):
        df = lrfd.shear_df_interior(s_ft=9.0)
        assert df.one_lane == pytest.approx(0.36 + 9.0 / 25.0)
        assert df.multi_lane == pytest.approx(0.2 + 0.75 - (9.0 / 35.0) ** 2)

    def test_shear_df_exceeds_moment_df(self):
        m = lrfd.moment_df_interior(**ARGS)
        v = lrfd.shear_df_interior(s_ft=9.0)
        assert v.governing > m.governing  # typical for I-girders


class TestExterior:
    def test_moment_e_factor(self):
        interior = lrfd.moment_df_interior(**ARGS)
        ext = lrfd.moment_df_exterior(interior, d_e_ft=2.0)
        assert ext.multi_lane == pytest.approx(
            (0.77 + 2.0 / 9.1) * interior.multi_lane
        )

    def test_shear_e_factor(self):
        interior = lrfd.shear_df_interior(s_ft=9.0)
        ext = lrfd.shear_df_exterior(interior, d_e_ft=2.0)
        assert ext.multi_lane == pytest.approx(0.8 * interior.multi_lane)

    def test_lever_rule_passthrough(self):
        interior = lrfd.moment_df_interior(**ARGS)
        ext = lrfd.moment_df_exterior(interior, d_e_ft=2.0,
                                      one_lane_lever_rule=0.75)
        assert ext.one_lane == 0.75

    def test_de_applicability(self):
        interior = lrfd.moment_df_interior(**ARGS)
        ext = lrfd.moment_df_exterior(interior, d_e_ft=6.0)
        assert not ext.applicability["de"]


class TestSkew:
    def test_no_moment_reduction_below_30(self):
        assert lrfd.skew_correction_moment(20.0, **ARGS) == 1.0

    def test_moment_reduction_at_45(self):
        c = lrfd.skew_correction_moment(45.0, **ARGS)
        c1 = 0.25 * (KG / (12.0 * 80.0 * 512.0)) ** 0.25 * (9.0 / 80.0) ** 0.5
        assert c == pytest.approx(1.0 - c1)  # tan45 = 1
        assert c < 1.0

    def test_shear_increase(self):
        c = lrfd.skew_correction_shear(30.0, l_ft=80.0, t_s=8.0, k_g=KG)
        expected = 1.0 + 0.2 * (12.0 * 80.0 * 512.0 / KG) ** 0.3 * math.tan(
            math.radians(30.0)
        )
        assert c == pytest.approx(expected)
        assert c > 1.0


class TestIM:
    def test_values(self):
        assert lrfd.dynamic_load_allowance() == 1.33
        assert lrfd.dynamic_load_allowance(fatigue=True) == 1.15
        assert lrfd.dynamic_load_allowance("deck_joint") == 1.75


class TestDesignLoop:
    def test_girder_spacing_study(self):
        """The demand side of a design loop: DF per candidate spacing."""
        dfs = {s: lrfd.moment_df_interior(s_ft=s, l_ft=80.0, t_s=8.0, k_g=KG)
               for s in (6.0, 8.0, 10.0, 12.0)}
        gov = [d.governing for d in dfs.values()]
        assert gov == sorted(gov)  # wider spacing -> more load per girder
        assert all(d.applicable for d in dfs.values())
