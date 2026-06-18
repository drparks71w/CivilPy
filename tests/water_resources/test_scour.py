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

"""HEC-18 bridge scour (civilpy.water_resources.scour), including the
boring-log D50/D95 tie-in."""

import math

import pytest

from civilpy.geotech.boring import Borehole, GradingPoint, GradingResult
from civilpy.water_resources import scour as s


class TestSupporting:
    def test_froude(self):
        assert s.froude_number(10.0, 10.0) == pytest.approx(0.557, abs=0.002)

    def test_froude_bad_depth(self):
        with pytest.raises(ValueError):
            s.froude_number(10.0, 0.0)

    def test_critical_velocity(self):
        # Ku y^(1/6) D^(1/3): 11.17 * 10^(1/6) * (2/304.8)^(1/3).
        assert s.critical_velocity(10.0, 2.0) == pytest.approx(3.069, abs=0.005)

    def test_critical_velocity_grows_with_grain(self):
        assert s.critical_velocity(10.0, 8.0) > s.critical_velocity(10.0, 2.0)

    def test_angle_factor_unity_at_zero_skew(self):
        assert s.angle_of_attack_factor(20.0, 5.0, 0.0) == pytest.approx(1.0)

    def test_angle_factor_value(self):
        # (cos30 + 4 sin30)^0.65 = 2.866^0.65.
        assert s.angle_of_attack_factor(20.0, 5.0, 30.0) == pytest.approx(1.983, abs=0.003)


class TestK4Armoring:
    def test_fine_bed_is_unity(self):
        assert s.armoring_factor_k4(10.0, 10.0, 5.0, 0.5, 15.0) == 1.0

    def test_d95_threshold(self):
        # D50 coarse but D95 below 20 mm -> no armoring credit.
        assert s.armoring_factor_k4(10.0, 10.0, 5.0, 5.0, 10.0) == 1.0

    def test_coarse_bed_reduces(self):
        k4 = s.armoring_factor_k4(5.0, 10.0, 5.0, 10.0, 40.0)
        assert 0.4 <= k4 < 1.0

    def test_floor_at_low_velocity(self):
        # Approach velocity below incipient motion -> K4 at its 0.4 floor.
        assert s.armoring_factor_k4(1.0, 10.0, 5.0, 10.0, 40.0) == pytest.approx(0.4)


class TestPierScourCSU:
    def test_hand_value(self):
        ys = s.pier_scour_csu(10.0, 10.0, 5.0, k1=1.0, k2=1.0, k3=1.1)
        assert ys == pytest.approx(10.9, abs=0.1)

    def test_k4_scales_linearly(self):
        full = s.pier_scour_csu(10.0, 10.0, 5.0, k4=1.0)
        armored = s.pier_scour_csu(10.0, 10.0, 5.0, k4=0.5)
        assert armored == pytest.approx(0.5 * full)

    def test_wider_pier_more_scour(self):
        assert s.pier_scour_csu(10, 10, 8) > s.pier_scour_csu(10, 10, 4)


class TestContraction:
    def test_clear_water_positive(self):
        ys = s.clear_water_contraction_scour(5000.0, 100.0, 1.0, 8.0)
        assert ys == pytest.approx(9.08, abs=0.1)

    def test_clear_water_finer_scours_more(self):
        fine = s.clear_water_contraction_scour(5000.0, 100.0, 0.5, 8.0)
        coarse = s.clear_water_contraction_scour(5000.0, 100.0, 5.0, 8.0)
        assert fine > coarse

    def test_live_bed_no_scour_when_discharge_drops(self):
        ys = s.live_bed_contraction_scour(8.0, 6000.0, 5000.0, 120.0, 100.0, 8.0)
        assert ys < 0  # deposition, not scour

    def test_live_bed_scours_with_narrowing(self):
        ys = s.live_bed_contraction_scour(8.0, 5000.0, 5000.0, 150.0, 80.0, 8.0)
        assert ys > 0


class TestFromBoring:
    def _coarse_boring(self):
        # D50 = 2 mm, D95 = 20 mm at the streambed (5 ft).
        pts = (
            GradingPoint(50.0, 100),
            GradingPoint(20.0, 95),
            GradingPoint(4.75, 60),
            GradingPoint(2.0, 50),
            GradingPoint(0.075, 5),
        )
        return Borehole(boring_id="PIER-1", grading=[GradingResult(5.0, pts)])

    def test_reads_d50_d95(self):
        bh = self._coarse_boring()
        res = s.pier_scour_from_boring(bh, 5.0, 8.0, 12.0, 4.0, shape="round")
        assert res.d50_mm == pytest.approx(2.0, abs=0.01)
        assert res.d95_mm == pytest.approx(20.0, abs=0.1)
        assert res.scour_depth_ft > 0

    def test_shape_sets_k1(self):
        bh = self._coarse_boring()
        sq = s.pier_scour_from_boring(bh, 5.0, 8.0, 12.0, 4.0, shape="square")
        rd = s.pier_scour_from_boring(bh, 5.0, 8.0, 12.0, 4.0, shape="round")
        assert sq.k1 == 1.1 and rd.k1 == 1.0
        assert sq.scour_depth_ft > rd.scour_depth_ft

    def test_skew_engages_k2(self):
        bh = self._coarse_boring()
        straight = s.pier_scour_from_boring(bh, 5.0, 8.0, 12.0, 4.0, pier_length_ft=20.0, skew_deg=0.0)
        skewed = s.pier_scour_from_boring(bh, 5.0, 8.0, 12.0, 4.0, pier_length_ft=20.0, skew_deg=20.0)
        assert skewed.k2 > 1.0
        assert straight.k2 == pytest.approx(1.0)

    def test_bad_shape(self):
        bh = self._coarse_boring()
        with pytest.raises(ValueError):
            s.pier_scour_from_boring(bh, 5.0, 8.0, 12.0, 4.0, shape="hexagon")

    def test_no_gradation_skips_k4(self):
        bh = Borehole(boring_id="nogr")
        res = s.pier_scour_from_boring(bh, 5.0, 8.0, 12.0, 4.0)
        assert res.k4 == 1.0
        assert res.d50_mm is None
