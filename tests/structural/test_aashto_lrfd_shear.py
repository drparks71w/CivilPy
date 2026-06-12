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

"""Hand-checked values for the 5.7 concrete shear suite (MCFT, detailing,
longitudinal reinforcement, interface shear, torsion threshold)."""

import math

import pytest

from civilpy.structural.aashto import lrfd


class TestMCFT:
    # RC section: Mu = 3000 kip-in, Vu = 100 kip, dv = 30 in,
    # As = 4.0 in^2 -> Es*As = 116,000 kip
    def test_eps_and_beta_theta_with_min_reinf(self):
        p = lrfd.rc_mcft_beta_theta(
            m_u=3000.0, v_u=100.0, d_v=30.0, e_s_a_s=29000.0 * 4.0
        )
        eps = (3000.0 / 30.0 + 100.0) / 116000.0
        assert p.eps_s == pytest.approx(eps)
        assert p.beta == pytest.approx(4.8 / (1.0 + 750.0 * eps))
        assert p.theta_deg == pytest.approx(29.0 + 3500.0 * eps)

    def test_prestress_reduces_strain(self):
        rc = lrfd.rc_mcft_beta_theta(
            m_u=3000.0, v_u=100.0, d_v=30.0, e_s_a_s=29000.0 * 4.0
        )
        ps = lrfd.rc_mcft_beta_theta(
            m_u=3000.0, v_u=100.0, d_v=30.0, e_s_a_s=29000.0 * 4.0,
            a_ps=2.0, f_po=189.0, e_p_a_ps=28500.0 * 2.0,
        )
        assert ps.eps_s < rc.eps_s
        assert ps.beta > rc.beta  # lower strain -> more concrete shear

    def test_negative_strain_floor(self):
        p = lrfd.rc_mcft_beta_theta(
            m_u=100.0, v_u=10.0, d_v=30.0, e_s_a_s=29000.0 * 4.0,
            a_ps=4.0, f_po=189.0, e_p_a_ps=28500.0 * 4.0,
        )
        assert p.eps_s >= -0.40e-3

    def test_no_min_reinf_penalty(self):
        with_reinf = lrfd.rc_mcft_beta_theta(
            m_u=3000.0, v_u=100.0, d_v=30.0, e_s_a_s=29000.0 * 4.0
        )
        without = lrfd.rc_mcft_beta_theta(
            m_u=3000.0, v_u=100.0, d_v=30.0, e_s_a_s=29000.0 * 4.0,
            has_min_transverse_reinf=False, s_x=30.0,
        )
        s_xe = 30.0 * 1.38 / (0.75 + 0.63)
        assert without.s_xe == pytest.approx(s_xe)
        assert without.beta == pytest.approx(
            with_reinf.beta * 51.0 / (39.0 + s_xe)
        )
        assert without.beta < with_reinf.beta

    def test_sxe_bounds(self):
        p = lrfd.rc_mcft_beta_theta(
            m_u=3000.0, v_u=100.0, d_v=30.0, e_s_a_s=29000.0 * 4.0,
            has_min_transverse_reinf=False, s_x=5.0,
        )
        assert p.s_xe == 12.0  # lower bound

    def test_requires_sx_without_reinf(self):
        with pytest.raises(ValueError):
            lrfd.rc_mcft_beta_theta(
                m_u=3000.0, v_u=100.0, d_v=30.0, e_s_a_s=29000.0 * 4.0,
                has_min_transverse_reinf=False,
            )

    def test_feeds_shear_resistance(self):
        p = lrfd.rc_mcft_beta_theta(
            m_u=3000.0, v_u=100.0, d_v=30.0, e_s_a_s=29000.0 * 4.0
        )
        r = lrfd.rc_shear_resistance(
            b_v=12.0, d_v=30.0, f_c=4.0, a_v=0.4, s=12.0,
            beta=p.beta, theta_deg=p.theta_deg, v_u=100.0,
        )
        assert r.details["beta"] == p.beta
        assert r.capacity > 0


class TestShearDetailing:
    def test_min_transverse(self):
        # 0.0316*sqrt(4)*12*12/60 = 0.1517 in^2
        r = lrfd.rc_min_transverse_reinforcement(
            b_v=12.0, s=12.0, f_c=4.0, a_v=0.40
        )
        assert r.demand == pytest.approx(0.0316 * 2.0 * 12.0 * 12.0 / 60.0)
        assert r.ok  # two #4 legs comfortably exceed

    def test_max_spacing_low_shear(self):
        # vu = 50/(0.9*12*30) = 0.154 < 0.5 = 0.125*4 -> smax = min(24, 24) = 24
        r = lrfd.rc_max_stirrup_spacing(
            v_u=50.0, b_v=12.0, d_v=30.0, f_c=4.0, s=18.0
        )
        assert not r.details["high_shear"]
        assert r.capacity == pytest.approx(24.0)
        assert r.ok

    def test_max_spacing_high_shear(self):
        # vu = 200/(0.9*12*30) = 0.617 > 0.5 -> smax = min(12, 12) = 12
        r = lrfd.rc_max_stirrup_spacing(
            v_u=200.0, b_v=12.0, d_v=30.0, f_c=4.0, s=18.0
        )
        assert r.details["high_shear"]
        assert r.capacity == pytest.approx(12.0)
        assert not r.ok


class TestLongitudinalReinforcement:
    def test_demand_formula(self):
        r = lrfd.rc_longitudinal_reinforcement(
            m_u=3000.0, v_u=100.0, d_v=30.0, theta_deg=36.0,
            a_s_f_y=4.0 * 60.0, v_s=40.0,
        )
        cot = 1.0 / math.tan(math.radians(36.0))
        expected = 3000.0 / (30.0 * 0.9) + (100.0 / 0.9 - 20.0) * cot
        assert r.demand == pytest.approx(expected)

    def test_vs_capped_at_vu_over_phi(self):
        r = lrfd.rc_longitudinal_reinforcement(
            m_u=3000.0, v_u=90.0, d_v=30.0, theta_deg=45.0,
            a_s_f_y=240.0, v_s=500.0,
        )
        assert r.details["Vs_used"] == pytest.approx(90.0 / 0.9)


class TestInterfaceShear:
    def test_roughened_slab_on_girder(self):
        # Acv = 42*12 = 504 in^2/ft-run segment, Avf = 0.62, f'c slab = 4
        # Vni = 0.28*504 + 1.0*(0.62*60) = 141.1 + 37.2 = 178.3
        # cap = min(0.3*4, 1.8)*504 = 1.2*504 = 604.8
        r = lrfd.rc_interface_shear(a_cv=504.0, f_c=4.0, a_vf=0.62)
        assert r.capacity == pytest.approx(0.28 * 504.0 + 0.62 * 60.0)
        assert r.details["upper_limit"] == pytest.approx(604.8)

    def test_monolithic_stronger_than_cold_joint(self):
        mono = lrfd.rc_interface_shear(a_cv=504.0, f_c=4.0, a_vf=0.62,
                                       case="monolithic")
        cold = lrfd.rc_interface_shear(a_cv=504.0, f_c=4.0, a_vf=0.62,
                                       case="not_roughened")
        assert mono.capacity > cold.capacity

    def test_upper_limit_governs_with_heavy_reinf(self):
        r = lrfd.rc_interface_shear(a_cv=100.0, f_c=4.0, a_vf=10.0)
        assert r.capacity == pytest.approx(min(0.3 * 4.0, 1.8) * 100.0)

    def test_min_avf_detail(self):
        r = lrfd.rc_interface_shear(a_cv=504.0, f_c=4.0)
        assert r.details["Avf_min"] == pytest.approx(0.05 * 504.0 / 60.0)


class TestTorsionThreshold:
    def test_rc_threshold(self):
        # 12x24 beam: Acp = 288, pc = 72
        # Tcr = 0.126*2*(288^2/72) = 0.252*1152 = 290.3 kip-in
        r = lrfd.rc_torsion_threshold(a_cp=288.0, p_c=72.0, f_c=4.0, t_u=50.0)
        assert r.details["Tcr"] == pytest.approx(0.126 * 2.0 * 288.0**2 / 72.0)
        assert r.capacity == pytest.approx(0.25 * 0.9 * r.details["Tcr"])
        assert r.ok  # 50 < 65.3 -> torsion negligible

    def test_prestress_raises_threshold(self):
        rc = lrfd.rc_torsion_threshold(a_cp=288.0, p_c=72.0, f_c=4.0)
        ps = lrfd.rc_torsion_threshold(a_cp=288.0, p_c=72.0, f_c=4.0, f_pc=1.0)
        assert ps.capacity > rc.capacity


class TestRegistry:
    def test_shear_articles_registered(self):
        for num in ("5.7.3.4.2", "5.7.2.5", "5.7.2.6", "5.7.3.5",
                    "5.7.4", "5.7.2.1"):
            assert num in lrfd.ARTICLES


class TestDeflection:
    def test_effective_inertia_uncracked(self):
        assert lrfd.rc_effective_moment_of_inertia(
            i_g=10000.0, i_cr=4000.0, m_cr=500.0, m_a=400.0
        ) == 10000.0

    def test_effective_inertia_cracked(self):
        # Mcr/Ma = 0.5: Ie = 0.125*10000 + 0.875*4000 = 4750
        ie = lrfd.rc_effective_moment_of_inertia(
            i_g=10000.0, i_cr=4000.0, m_cr=500.0, m_a=1000.0
        )
        assert ie == pytest.approx(4750.0)

    def test_deflection_limits(self):
        # 80 ft span in inches: 960/800 = 1.2 in
        r = lrfd.deflection_limit(span=960.0, deflection=1.0)
        assert r.capacity == pytest.approx(1.2)
        assert r.ok
        ped = lrfd.deflection_limit(span=960.0, pedestrian=True)
        assert ped.capacity == pytest.approx(0.96)
        cant = lrfd.deflection_limit(span=120.0, cantilever=True)
        assert cant.capacity == pytest.approx(0.4)
