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

"""Hand-checked values for the 5.4.2.3 creep/shrinkage models and the
5.9.3.4 refined prestress-loss family."""

import math

import pytest

from civilpy.structural.aashto import lrfd
from civilpy.structural.aashto.lrfd import creep_shrinkage as cs


class TestMaterialFactors:
    def test_vs_factor_floors_at_one(self):
        assert cs.factor_vs_ratio(3.0) == pytest.approx(1.45 - 0.39)
        assert cs.factor_vs_ratio(4.0) == pytest.approx(1.0)  # 0.93 floored

    def test_humidity_factors_at_70(self):
        assert cs.factor_humidity_creep(70.0) == pytest.approx(1.0)
        assert cs.factor_humidity_shrinkage(70.0) == pytest.approx(1.02)

    def test_strength_factor(self):
        assert cs.factor_concrete_strength(4.0) == pytest.approx(1.0)
        assert cs.factor_concrete_strength(6.0) == pytest.approx(5.0 / 7.0)

    def test_ktd_current_vs_pre2015(self):
        # current at f'ci=6, t=90: 90/(12*76/26 + 90) = 90/125.08
        cur = cs.factor_time_development(90.0, 6.0)
        assert cur == pytest.approx(90.0 / (12.0 * 76.0 / 26.0 + 90.0))
        # pre-2015: 90/(61-24+90) = 90/127
        old = cs.factor_time_development(90.0, 6.0, design_year=2010)
        assert old == pytest.approx(90.0 / 127.0)

    def test_ktd_approaches_one(self):
        assert cs.factor_time_development(20000.0, 6.0) == pytest.approx(1.0, abs=0.01)


class TestCreepShrinkage:
    def test_creep_coefficient_long_term(self):
        # f'ci=6, H=70, V/S=4 (ks=1.0), ti=1 day, t->inf:
        # psi = 1.9 * 1.0 * 1.0 * 5/7 * ~1.0 * 1 = ~1.357
        psi = lrfd.creep_coefficient(t=20000.0, t_i=1.0, f_ci=6.0,
                                     humidity_pct=70.0, v_s=4.0)
        assert psi == pytest.approx(1.9 * 5.0 / 7.0, rel=0.02)

    def test_creep_loading_age_reduces_creep(self):
        young = lrfd.creep_coefficient(t=20000.0, t_i=1.0, f_ci=6.0)
        old = lrfd.creep_coefficient(t=20000.0, t_i=90.0, f_ci=6.0)
        assert old < young
        assert old == pytest.approx(young * 90.0**-0.118 / 1.0**-0.118, rel=0.01)

    def test_shrinkage_strain_long_term(self):
        # ks=1.0, khs=1.02, kf=5/7, ktd~1: 0.48e-3 * 0.7286 = ~3.50e-4
        eps = lrfd.shrinkage_strain(t=20000.0, f_ci=6.0, humidity_pct=70.0, v_s=4.0)
        assert eps == pytest.approx(1.02 * 5.0 / 7.0 * 0.48e-3, rel=0.02)


class TestRefinedLosses:
    # AASHTO-I-beam-ish: Aps=4.59, Ag=789, Ig=260730, epg=16.4, Eci=4200
    KID_ARGS = dict(a_ps=4.59, a_g=789.0, i_g=260730.0, e_pg=16.4,
                    psi_final=1.4, e_ci=4200.0)

    def test_kid_formula(self):
        k = lrfd.ps_section_age_adjustment(**self.KID_ARGS)
        expected = 1.0 / (
            1.0 + 28500.0 / 4200.0 * 4.59 / 789.0
            * (1.0 + 789.0 * 16.4**2 / 260730.0) * (1.0 + 0.7 * 1.4)
        )
        assert k == pytest.approx(expected)
        assert 0.7 < k < 1.0  # typical range

    def test_shrinkage_loss_girder(self):
        k_id = lrfd.ps_section_age_adjustment(**self.KID_ARGS)
        r = lrfd.ps_refined_loss_shrinkage_girder(eps_bid=2.5e-4, k_id=k_id)
        assert r.capacity == pytest.approx(2.5e-4 * 28500.0 * k_id)
        assert 4.0 < r.capacity < 8.0  # ksi, typical

    def test_creep_loss_girder(self):
        r = lrfd.ps_refined_loss_creep_girder(
            f_cgp=2.4, psi_td_ti=0.8, k_id=0.8, e_ci=4200.0
        )
        assert r.capacity == pytest.approx(28500.0 / 4200.0 * 2.4 * 0.8 * 0.8)

    def test_relaxation_classic_value(self):
        # 0.75*270 jacking, fpy = 0.9*270: (202.5/30)*(202.5/243 - 0.55) = 1.91
        r = lrfd.ps_refined_loss_relaxation(f_pt=202.5, f_py=243.0)
        assert r.capacity == pytest.approx(1.9125, abs=1e-3)

    def test_relaxation_floors_at_zero(self):
        r = lrfd.ps_refined_loss_relaxation(f_pt=100.0, f_py=243.0)
        assert r.capacity == 0.0

    def test_creep_deck_stage_floors_at_zero(self):
        # Strong negative delta_f_cd (deck weight relieving compression)
        r = lrfd.ps_refined_loss_creep_deck_stage(
            f_cgp=2.4, psi_tf_ti=1.4, psi_td_ti=1.3, psi_tf_td=0.6,
            delta_f_cd=-3.0, k_df=0.8, e_ci=4200.0, e_c=4700.0,
        )
        assert r.capacity == 0.0

    def test_deck_shrinkage_gain(self):
        r = lrfd.ps_deck_shrinkage_gain(
            delta_f_cdf=0.1, k_df=0.8, psi_tf_td=0.6, e_c=4700.0
        )
        assert r.capacity == pytest.approx(
            28500.0 / 4700.0 * 0.1 * 0.8 * 1.42
        )


class TestPTLosses:
    def test_friction_loss(self):
        # 200 ksi jacking, 50 ft, 0.1 rad total curvature
        r = lrfd.ps_friction_loss(f_pj=200.0, x=50.0, alpha=0.1)
        expected = 200.0 * (1.0 - math.exp(-(0.0002 * 50.0 + 0.25 * 0.1)))
        assert r.capacity == pytest.approx(expected)

    def test_friction_increases_with_length(self):
        near = lrfd.ps_friction_loss(f_pj=200.0, x=10.0, alpha=0.05)
        far = lrfd.ps_friction_loss(f_pj=200.0, x=100.0, alpha=0.3)
        assert far.capacity > near.capacity


class TestDevelopmentAndSplitting:
    def test_development_length(self):
        # 0.6" strand, fps=255, fpe=160: ld = 1.6*(255 - 106.67)*0.6 = 142.4"
        r = lrfd.ps_strand_development(f_ps=255.0, f_pe=160.0, d_b=0.6)
        assert r.details["ld_required"] == pytest.approx(
            1.6 * (255.0 - 2.0 / 3.0 * 160.0) * 0.6
        )
        assert r.details["transfer_length"] == pytest.approx(36.0)

    def test_development_with_embedment_demand(self):
        r = lrfd.ps_strand_development(
            f_ps=255.0, f_pe=160.0, d_b=0.6, embedment=150.0
        )
        assert r.ok  # 150" available > 142.4" required

    def test_splitting_resistance(self):
        # 4 #5 legs in end zone: As = 1.24, Pr = 20*1.24 = 24.8 kip
        # vs 4% of 30-strand transfer force ~ 0.04*4.59*202.5 = 37.2 -> fails
        r = lrfd.ps_splitting_resistance(
            a_s_end=1.24, p_r_demand=0.04 * 4.59 * 202.5
        )
        assert r.capacity == pytest.approx(24.8)
        assert not r.ok

    def test_splitting_fs_capped(self):
        r = lrfd.ps_splitting_resistance(a_s_end=1.0, f_s=60.0)
        assert r.capacity == pytest.approx(20.0)


class TestRegistry:
    def test_loss_articles_registered(self):
        for num in ("5.4.2.3.2", "5.4.2.3.3", "5.9.3.4.2a", "5.9.3.4.2b",
                    "5.9.3.4.2c", "5.9.3.4.3a", "5.9.3.4.3b", "5.9.3.4.3d",
                    "5.9.3.2.2", "5.9.4.3.2", "5.9.4.4.1"):
            assert num in lrfd.ARTICLES
