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

"""Hand-checked values for the prestressed concrete LRFD checks.

Geometry loosely follows a typical Ohio precast I-beam with a composite
deck: 30 x 0.6" low-relaxation strands (Aps = 6.51 in^2 using 0.217 in^2
strands ~ generic), 270 ksi, composite slab f'c = 4 ksi.
"""

import math

import pytest

from civilpy.structural.aashto import lrfd


# Shared rectangular-behavior case: Aps=4.59 (30 x 0.153), dp=36, b=48, f'c=4
RECT = dict(a_ps=4.59, f_pu=270.0, d_p=36.0, f_c=4.0, b=48.0)


class TestStrandStress:
    def test_rectangular_neutral_axis(self):
        # c = Aps*fpu / (0.85*f'c*beta1*b + k*Aps*fpu/dp)
        #   = 1239.3 / (0.85*4*0.85*48 + 0.28*1239.3/36)
        #   = 1239.3 / (138.72 + 9.639) = 8.353 in
        r = lrfd.ps_strand_stress_at_nominal(**RECT)
        c = 4.59 * 270.0 / (0.85 * 4.0 * 0.85 * 48.0 + 0.28 * 4.59 * 270.0 / 36.0)
        assert r.details["c"] == pytest.approx(c, rel=1e-6)
        assert r.details["behavior"] == "rectangular"

    def test_fps_from_c(self):
        r = lrfd.ps_strand_stress_at_nominal(**RECT)
        c = r.details["c"]
        assert r.capacity == pytest.approx(270.0 * (1.0 - 0.28 * c / 36.0))
        # fps for a tension-controlled section should be near fpu
        assert 245.0 < r.capacity < 270.0

    def test_flanged_behavior_when_na_below_flange(self):
        # Thin 3" flange on a 6" web forces the neutral axis below the flange
        r = lrfd.ps_strand_stress_at_nominal(**RECT, b_w=6.0, h_f=3.0)
        assert r.details["behavior"] == "flanged"
        rect_c = lrfd.ps_strand_stress_at_nominal(**RECT).details["c"]
        assert r.details["c"] > rect_c  # web-only compression needs deeper NA

    def test_stress_relieved_k(self):
        low = lrfd.ps_strand_stress_at_nominal(**RECT)
        sr = lrfd.ps_strand_stress_at_nominal(**RECT, k=lrfd.prestressed.K_STRESS_RELIEVED)
        assert sr.capacity < low.capacity  # larger k -> lower fps


class TestPSFlexure:
    def test_rectangular_mn(self):
        r = lrfd.ps_flexural_resistance(**RECT)
        c = r.details["c"]
        f_ps = r.details["fps"]
        a = 0.85 * c
        assert r.capacity == pytest.approx(4.59 * f_ps * (36.0 - a / 2.0), rel=1e-6)
        # ~3,100 kip-ft ballpark for this section
        assert 30000.0 < r.capacity < 45000.0

    def test_tension_controlled_phi_is_one(self):
        r = lrfd.ps_flexural_resistance(**RECT)
        assert r.details["tension_controlled"]
        assert r.phi == pytest.approx(1.0)

    def test_demand_ratio(self):
        r = lrfd.ps_flexural_resistance(**RECT, m_u=30000.0)
        assert r.ratio == pytest.approx(r.capacity / 30000.0)

    def test_flanged_mn_adds_overhang_term(self):
        r = lrfd.ps_flexural_resistance(**RECT, b_w=6.0, h_f=3.0)
        assert r.details["behavior"] == "flanged"
        # capacity still positive and below the rectangular idealization
        rect = lrfd.ps_flexural_resistance(**RECT)
        assert 0 < r.capacity < rect.capacity

    def test_mild_steel_increases_capacity(self):
        base = lrfd.ps_flexural_resistance(**RECT)
        with_mild = lrfd.ps_flexural_resistance(**RECT, a_s=2.0, d_s=38.0)
        assert with_mild.capacity > base.capacity


class TestStressLimits:
    def test_transfer_compression(self):
        r = lrfd.ps_transfer_compression_check(f_ci=5.0, stress=3.0)
        assert r.capacity == pytest.approx(0.65 * 5.0)
        assert r.ok

    def test_transfer_tension_without_bonded_reinf_caps_at_02(self):
        # 0.0948*sqrt(5) = 0.212 > 0.2 -> capped
        r = lrfd.ps_transfer_tension_check(f_ci=5.0)
        assert r.capacity == pytest.approx(0.2)

    def test_transfer_tension_with_bonded_reinf(self):
        r = lrfd.ps_transfer_tension_check(f_ci=5.0, bonded_reinforcement=True)
        assert r.capacity == pytest.approx(0.24 * math.sqrt(5.0))

    def test_service_compression_governing_case(self):
        # permanent: 0.45*7 = 3.15 vs 2.8 -> margin 1.125
        # total:     0.60*7 = 4.20 vs 4.0 -> margin 1.05 (governs)
        r = lrfd.ps_service_compression_check(
            f_c=7.0, stress_permanent=2.8, stress_total=4.0
        )
        assert r.details["governing"] == "total"
        assert r.capacity == pytest.approx(4.2)
        assert r.ok

    def test_service_tension_normal_exposure(self):
        r = lrfd.ps_service_tension_check(f_c=7.0, stress=0.4)
        assert r.capacity == pytest.approx(min(0.19 * math.sqrt(7.0), 0.6))
        assert r.ok

    def test_service_tension_severe_corrosion(self):
        r = lrfd.ps_service_tension_check(f_c=7.0, severe_corrosion=True)
        assert r.capacity == pytest.approx(min(0.0948 * math.sqrt(7.0), 0.3))


class TestLosses:
    def test_elastic_shortening(self):
        # Ep/Ect * fcgp = 28500/4500 * 1.2 = 7.6 ksi
        r = lrfd.ps_elastic_shortening_loss(f_cgp=1.2, e_ct=4500.0)
        assert r.capacity == pytest.approx(28500.0 / 4500.0 * 1.2)

    def test_approximate_longterm_at_reference_conditions(self):
        # H=70 -> gamma_h = 1.0; f'ci = 4 -> gamma_st = 1.0
        # loss = 10*fpi*Aps/Ag + 12 + 2.4
        r = lrfd.ps_approximate_longterm_loss(
            f_pi=202.5, a_ps=4.59, a_g=789.0, f_ci=4.0, humidity_pct=70.0
        )
        creep = 10.0 * 202.5 * 4.59 / 789.0
        assert r.details["gamma_h"] == pytest.approx(1.0)
        assert r.details["gamma_st"] == pytest.approx(1.0)
        assert r.capacity == pytest.approx(creep + 12.0 + 2.4)

    def test_humidity_reduces_loss(self):
        dry = lrfd.ps_approximate_longterm_loss(
            f_pi=202.5, a_ps=4.59, a_g=789.0, f_ci=4.0, humidity_pct=40.0
        )
        humid = lrfd.ps_approximate_longterm_loss(
            f_pi=202.5, a_ps=4.59, a_g=789.0, f_ci=4.0, humidity_pct=90.0
        )
        assert dry.capacity > humid.capacity


class TestRegistry:
    def test_ps_articles_registered(self):
        for num in ("5.6.3.1.1", "5.6.3.2.2", "5.9.2.3.1a", "5.9.2.3.1b",
                    "5.9.2.3.2a", "5.9.2.3.2b", "5.9.3.2.3a", "5.9.3.3"):
            assert num in lrfd.ARTICLES

    def test_strand_pattern_design_loop(self):
        """Size a strand pattern by looping candidate strand counts."""
        m_u = 28000.0  # kip-in
        counts = range(20, 42, 2)
        passing = [
            n for n in counts
            if lrfd.ps_flexural_resistance(
                a_ps=n * 0.153, f_pu=270.0, d_p=36.0, f_c=4.0, b=48.0, m_u=m_u
            ).ok
        ]
        assert passing
        assert min(passing) > 20  # demand high enough to reject the lightest
