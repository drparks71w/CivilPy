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

"""Drilled-shaft axial capacity (civilpy.geotech.deep_foundation): the
AASHTO 10.8 unit-resistance equations and the boring-driven integrator."""

import math

import pytest

from civilpy.geotech import deep_foundation as df
from civilpy.geotech.boring import Borehole, DriveIncrement, GradingPoint, GradingResult, SPTResult


def _uniform_boring(n, fines, n_levels=18, spacing=2.5, depth=45.0):
    """A boring with the same N and gradation at every 2.5-ft SPT.

    The two counting increments sum to ``n`` so the field N equals ``n``.
    """
    spt = [
        SPTResult(spacing * (i + 1), (DriveIncrement(5), DriveIncrement(n // 2), DriveIncrement(n - n // 2)))
        for i in range(n_levels)
    ]
    grad = [
        GradingResult(spacing * (i + 1), (GradingPoint(2.0, 100), GradingPoint(0.075, fines)))
        for i in range(n_levels)
    ]
    return Borehole(boring_id="SYN", total_depth_ft=depth, spt=spt, grading=grad)


class TestUnitResistanceClay:
    def test_alpha_low_strength(self):
        assert df.alpha_factor(2.0) == pytest.approx(0.55)

    def test_alpha_reduces_above_ratio(self):
        # Su/pa = 4/2.116 = 1.89 -> 0.55 - 0.1*(1.89-1.5) = 0.511.
        assert df.alpha_factor(4.0) == pytest.approx(0.511, abs=0.002)

    def test_unit_side_clay(self):
        assert df.unit_side_resistance_clay(2.0) == pytest.approx(1.1)

    def test_tip_nc_capped_at_9(self):
        # Z/D = 10 -> Nc = min(9, 6*3) = 9; q_p = 9*2 = 18 ksf.
        assert df.unit_tip_resistance_clay(2.0, 30.0, 3.0) == pytest.approx(18.0)

    def test_tip_clay_limit(self):
        assert df.unit_tip_resistance_clay(20.0, 30.0, 3.0, limit_ksf=80.0) == pytest.approx(80.0)


class TestUnitResistanceSand:
    def test_beta_dense(self):
        assert df.beta_factor(10.0, 20.0) == pytest.approx(1.5 - 0.135 * math.sqrt(10), abs=1e-6)

    def test_beta_loose_reduction(self):
        base = 1.5 - 0.135 * math.sqrt(10)
        assert df.beta_factor(10.0, 7.5) == pytest.approx(base * 0.5, abs=1e-6)

    def test_beta_floor(self):
        assert df.beta_factor(100.0, 30.0) == pytest.approx(0.25)

    def test_beta_ceiling(self):
        assert df.beta_factor(0.0, 30.0) == pytest.approx(1.2)

    def test_unit_side_sand_capped(self):
        assert df.unit_side_resistance_sand(100.0, 1.0, 30.0) == pytest.approx(4.0)

    def test_tip_sand(self):
        assert df.unit_tip_resistance_sand(40.0) == pytest.approx(48.0)

    def test_tip_sand_n_capped_at_50(self):
        assert df.unit_tip_resistance_sand(80.0) == pytest.approx(60.0)


class TestDriver:
    def test_sand_tip_matches_unit_equation(self):
        bh = _uniform_boring(n=20, fines=5)
        cap = df.drilled_shaft_capacity(bh, diameter_ft=3.0, tip_depth_ft=40.0)
        # N60 at 40 ft = 20 (rod-length Cr = 1.0); q_p = 1.2*20 = 24 ksf.
        area = math.pi * 9 / 4
        assert cap.tip_nominal_kips == pytest.approx(24.0 * area, rel=0.02)
        assert cap.side_nominal_kips > 0

    def test_total_and_factored(self):
        bh = _uniform_boring(n=20, fines=5)
        cap = df.drilled_shaft_capacity(bh, 3.0, 40.0)
        assert cap.total_nominal_kips == pytest.approx(
            cap.side_nominal_kips + cap.tip_nominal_kips
        )
        f = cap.factored_kips(phi_side=0.55, phi_tip=0.50)
        assert f < cap.total_nominal_kips
        assert f == pytest.approx(
            0.55 * cap.side_nominal_kips + 0.50 * cap.tip_nominal_kips
        )

    def test_deeper_shaft_more_side(self):
        bh = _uniform_boring(n=20, fines=5)
        shallow = df.drilled_shaft_capacity(bh, 3.0, 25.0)
        deep = df.drilled_shaft_capacity(bh, 3.0, 40.0)
        assert deep.side_nominal_kips > shallow.side_nominal_kips

    def test_water_table_reduces_side(self):
        bh = _uniform_boring(n=20, fines=5)
        dry = df.drilled_shaft_capacity(bh, 3.0, 40.0, water_table_ft=100.0)
        wet = df.drilled_shaft_capacity(bh, 3.0, 40.0, water_table_ft=5.0)
        # pore pressure lowers effective stress -> less sand side resistance.
        assert wet.side_nominal_kips < dry.side_nominal_kips

    def test_clay_branch_selected(self):
        # 60% fines -> cohesive: side from alpha*Su, tip from Nc*Su.
        bh = _uniform_boring(n=10, fines=60)
        cap = df.drilled_shaft_capacity(bh, 3.0, 40.0)
        assert cap.side_nominal_kips > 0
        assert cap.tip_nominal_kips > 0

    def test_exclusions_zero_short_shaft(self):
        # Top 5 ft and bottom 1D excluded: a 7-ft, 3-ft shaft has no
        # contributing side length.
        bh = _uniform_boring(n=20, fines=5)
        cap = df.drilled_shaft_capacity(bh, 3.0, 7.0)
        assert cap.side_nominal_kips == pytest.approx(0.0)

    def test_requires_spt(self):
        with pytest.raises(ValueError):
            df.drilled_shaft_capacity(Borehole(boring_id="empty"), 3.0, 30.0)

    def test_bad_geometry(self):
        bh = _uniform_boring(n=20, fines=5)
        with pytest.raises(ValueError):
            df.drilled_shaft_capacity(bh, 0.0, 30.0)
