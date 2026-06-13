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

"""SPT correlations (civilpy.geotech.spt) and the CANDE soil adapter
(civilpy.geotech.cande_adapter)."""

import math

import pytest

from civilpy.geotech import spt
from civilpy.geotech.boring import Borehole, DriveIncrement, GradingPoint, GradingResult, SPTResult
from civilpy.geotech.cande_adapter import (
    clay_soil_material_from_spt,
    duncan_selig_from_gradation,
    in_situ_soil_material,
    soil_material_from_spt,
)


class TestSptCorrelations:
    def test_overburden_capped_at_low_stress(self):
        # Very low effective stress would blow CN up; it is capped.
        assert spt.overburden_correction(10.0) == pytest.approx(1.7)

    def test_overburden_unit_stress(self):
        # CN = sqrt(2000/2000) = 1.0 at one atmosphere.
        assert spt.overburden_correction(2000.0) == pytest.approx(1.0)

    def test_n1_60(self):
        assert spt.n1_60(20.0, 2000.0) == pytest.approx(20.0)
        assert spt.n1_60(20.0, 500.0) == pytest.approx(20.0 * 1.7)  # capped

    def test_friction_angle_hatanaka(self):
        # sqrt(20*20) + 20 = 20 + 20 = 40.
        assert spt.friction_angle_from_n(20.0) == pytest.approx(40.0)

    def test_relative_density_clamped(self):
        assert spt.relative_density_from_n(60.0) == pytest.approx(1.0)
        assert spt.relative_density_from_n(15.0) == pytest.approx(0.5)

    def test_undrained_strength_linear(self):
        assert spt.undrained_shear_strength_from_n(10.0, factor_psf=100.0) == pytest.approx(1000.0)

    def test_elastic_modulus_sand(self):
        # 500*(20+15) kPa * 0.1450377 psi/kPa = 2538 psi.
        assert spt.elastic_modulus_from_spt(20, "sand") == pytest.approx(2538.2, abs=1.0)

    def test_elastic_modulus_bad_type(self):
        with pytest.raises(ValueError):
            spt.elastic_modulus_from_spt(20, "loam")

    def test_elastic_modulus_from_su(self):
        # 300 * 1000 psf / 144 = 2083 psi.
        assert spt.elastic_modulus_from_su(1000.0, 300.0) == pytest.approx(2083.3, abs=1.0)

    def test_unit_weight_monotonic(self):
        weights = [spt.unit_weight_from_n(n) for n in (2, 7, 20, 40, 60)]
        assert weights == sorted(weights)


class TestCandeAdapter:
    def test_elastic_material_from_spt(self):
        m = soil_material_from_spt(20, "sand")
        assert m.model == "isotropic"
        assert m.e_psi == pytest.approx(2538.2, abs=1.0)
        assert m.nu == pytest.approx(0.30)
        assert m.density_pcf == spt.unit_weight_from_n(20)

    def test_clay_material_path(self):
        m = clay_soil_material_from_spt(10, modulus_ratio=300, su_factor_psf=100)
        assert m.model == "isotropic"
        assert m.nu == pytest.approx(0.45)
        # Su = 1000 psf, E = 300*1000/144.
        assert m.e_psi == pytest.approx(2083.3, abs=1.0)

    def test_duncan_selig_coarse_maps_to_sw(self):
        g = GradingResult(5.0, (GradingPoint(2.0, 100), GradingPoint(0.075, 8)))
        m = duncan_selig_from_gradation(g, compaction_percent=92, density_pcf=125)
        assert m.model == "duncan_selig"
        assert m.name == "SW90"  # nearest canned to 92%

    def test_duncan_selig_fine_maps_to_group(self):
        g = GradingResult(5.0, (GradingPoint(2.0, 100), GradingPoint(0.075, 70)))
        ml = duncan_selig_from_gradation(g, 95, 120)
        cl = duncan_selig_from_gradation(g, 95, 120, fine_group="CL")
        assert ml.name == "ML95"
        assert cl.name == "CL95"

    def test_in_situ_silty_sand_branch(self):
        bh = Borehole(
            boring_id="B-1",
            spt=[SPTResult(1.5, (DriveIncrement(12), DriveIncrement(14), DriveIncrement(10)))],
            grading=[GradingResult(1.5, (GradingPoint(2.0, 95), GradingPoint(0.075, 40)))],
        )
        m = in_situ_soil_material(bh, 1.5)
        # 40% fines -> coarse silty_sand path, N = 24.
        assert m.model == "isotropic"
        assert m.nu == pytest.approx(0.35)
        assert m.e_psi == pytest.approx(spt.elastic_modulus_from_spt(24, "silty_sand"), abs=1.0)

    def test_in_situ_clay_branch(self):
        bh = Borehole(
            boring_id="B-1",
            spt=[SPTResult(3.0, (DriveIncrement(3), DriveIncrement(4), DriveIncrement(5)))],
            grading=[GradingResult(3.0, (GradingPoint(2.0, 100), GradingPoint(0.075, 60)))],
        )
        m = in_situ_soil_material(bh, 3.0)
        # 60% fines -> clay path, nu 0.45.
        assert m.nu == pytest.approx(0.45)

    def test_in_situ_requires_spt(self):
        bh = Borehole(boring_id="B-empty")
        with pytest.raises(ValueError):
            in_situ_soil_material(bh, 5.0)

    def test_material_emits_valid_cande_lines(self):
        # The adapter output must drop straight into a CANDE deck.
        m = soil_material_from_spt(20, "sand")
        lines = m._d_lines(1, last=True)
        assert lines[0].lstrip().startswith("D-1!!")
        assert "D-2.Isotropic" in lines[1]
