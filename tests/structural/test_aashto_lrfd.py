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

"""Hand-checked values for the AASHTO LRFD check functions.

Reference values computed by hand from the 9th Edition equations; geometry
loosely follows the FHWA Steel Bridge Design Handbook example I-girder.
"""

import math

import pytest

from civilpy.structural.aashto import lrfd


class TestFlangeLocalBuckling:
    def test_compact_flange_reaches_fyc(self):
        # 16 x 1.0 flange, lambda_f = 8.0 < lambda_pf = 0.38*sqrt(29000/50) = 9.15
        r = lrfd.flange_local_buckling_resistance(
            b_fc=16.0, t_fc=1.0, f_yc=50.0, f_yw=50.0
        )
        assert r.capacity == pytest.approx(50.0)
        assert r.details["compact"] is True

    def test_noncompact_flange_interpolates(self):
        # 20 x 0.875 flange: lambda_f = 11.43, lambda_pf = 9.15
        # Fyr = max(min(0.7*50, 50), 25) = 35 ksi
        # lambda_rf = 0.56*sqrt(29000/35) = 16.12
        # Fnc = (1 - (1 - 35/50)*(11.43-9.15)/(16.12-9.15))*50 = 45.10 ksi
        r = lrfd.flange_local_buckling_resistance(
            b_fc=20.0, t_fc=0.875, f_yc=50.0, f_yw=50.0
        )
        lam_f = 20.0 / (2 * 0.875)
        lam_pf = 0.38 * math.sqrt(29000.0 / 50.0)
        lam_rf = 0.56 * math.sqrt(29000.0 / 35.0)
        expected = (1 - (1 - 35.0 / 50.0) * (lam_f - lam_pf) / (lam_rf - lam_pf)) * 50.0
        assert r.capacity == pytest.approx(expected)
        assert r.capacity == pytest.approx(45.10, abs=0.05)
        assert r.details["compact"] is False

    def test_demand_sets_ratio(self):
        r = lrfd.flange_local_buckling_resistance(
            b_fc=16.0, t_fc=1.0, f_yc=50.0, f_yw=50.0, f_bu=40.0
        )
        assert r.ratio == pytest.approx(50.0 / 40.0)
        assert r.ok


class TestLateralTorsionalBuckling:
    # rt for bfc=16, tfc=1.0, Dc=24, tw=0.5:
    #   rt = 16/sqrt(12*(1 + 24*0.5/(3*16*1.0))) = 4.105 in
    RT = 16.0 / math.sqrt(12.0 * (1.0 + 24.0 * 0.5 / (3.0 * 16.0 * 1.0)))

    def kwargs(self, l_b):
        return dict(
            l_b=l_b, b_fc=16.0, t_fc=1.0, d_c=24.0, t_w=0.5, f_yc=50.0, f_yw=50.0
        )

    def test_plateau_below_lp(self):
        l_p = self.RT * math.sqrt(29000.0 / 50.0)
        r = lrfd.lateral_torsional_buckling_resistance(**self.kwargs(l_p * 0.9))
        assert r.capacity == pytest.approx(50.0)
        assert r.details["regime"] == "inelastic-plateau"

    def test_inelastic_interpolation(self):
        l_p = self.RT * math.sqrt(29000.0 / 50.0)
        l_r = math.pi * self.RT * math.sqrt(29000.0 / 35.0)
        l_b = (l_p + l_r) / 2.0
        r = lrfd.lateral_torsional_buckling_resistance(**self.kwargs(l_b))
        expected = (1 - (1 - 35.0 / 50.0) * 0.5) * 50.0  # midpoint of Lp..Lr
        assert r.capacity == pytest.approx(expected)

    def test_elastic_buckling(self):
        l_r = math.pi * self.RT * math.sqrt(29000.0 / 35.0)
        l_b = 1.5 * l_r
        r = lrfd.lateral_torsional_buckling_resistance(**self.kwargs(l_b))
        f_cr = math.pi**2 * 29000.0 / (l_b / self.RT) ** 2
        assert r.capacity == pytest.approx(f_cr)
        assert r.details["regime"] == "elastic"

    def test_cb_capped_at_plateau(self):
        l_p = self.RT * math.sqrt(29000.0 / 50.0)
        l_b = l_p * 1.05
        r = lrfd.lateral_torsional_buckling_resistance(**self.kwargs(l_b) | {"c_b": 2.0})
        assert r.capacity == pytest.approx(50.0)  # Cb amplification capped at RbRhFyc


class TestWebShear:
    def test_stocky_web_full_plastic(self):
        # D/tw = 48/0.75 = 64 < 1.12*sqrt(29000*5/50) = 60.3? No: 60.3 < 64,
        # use a thicker web: 48/1.0 = 48 < 60.3 -> C = 1.0
        r = lrfd.web_shear_resistance(d_web=48.0, t_w=1.0, f_yw=50.0)
        assert r.details["C"] == pytest.approx(1.0)
        assert r.capacity == pytest.approx(0.58 * 50.0 * 48.0 * 1.0)

    def test_slender_web_elastic_buckling(self):
        # D/tw = 96/0.5 = 192 > 1.40*sqrt(29000*5/50) = 75.4 -> elastic C
        r = lrfd.web_shear_resistance(d_web=96.0, t_w=0.5, f_yw=50.0)
        c = 1.57 / 192.0**2 * (29000.0 * 5.0 / 50.0)
        assert r.details["C"] == pytest.approx(c)
        assert r.capacity == pytest.approx(c * 0.58 * 50.0 * 96.0 * 0.5)

    def test_tension_field_exceeds_c_vp(self):
        r_no_tf = lrfd.web_shear_resistance(d_web=96.0, t_w=0.5, f_yw=50.0, d_o=96.0)
        r_tf = lrfd.web_shear_resistance(
            d_web=96.0, t_w=0.5, f_yw=50.0, d_o=96.0,
            tension_field=True, b_fc=20.0, t_fc=1.5, b_ft=20.0, t_ft=1.5,
        )
        assert r_tf.capacity > r_no_tf.capacity
        assert r_tf.details["equation"] == "6.10.9.3.2-2"

    def test_tension_field_requires_flanges(self):
        with pytest.raises(ValueError):
            lrfd.web_shear_resistance(
                d_web=96.0, t_w=0.5, f_yw=50.0, d_o=96.0, tension_field=True
            )


class TestRCFlexure:
    def test_singly_reinforced_rectangular(self):
        # As = 3.0 in^2, fy = 60, f'c = 4, b = 12, ds = 21.5
        # a = 3*60/(0.85*4*12) = 4.412 in, c = a/0.85 = 5.190
        # Mn = 180*(21.5 - 2.206) = 3472.9 kip-in
        # eps_t = 0.003*(21.5-5.190)/5.190 = 0.00943 > 0.005 -> phi = 0.9
        r = lrfd.rc_rectangular_flexural_resistance(
            a_s=3.0, f_y=60.0, f_c=4.0, b=12.0, d_s=21.5
        )
        assert r.details["a"] == pytest.approx(4.4118, abs=1e-3)
        assert r.capacity == pytest.approx(180.0 * (21.5 - 4.4118 / 2.0), rel=1e-4)
        assert r.phi == pytest.approx(0.9)
        assert r.details["tension_controlled"]

    def test_over_reinforced_reduces_phi(self):
        # Heavy steel drives c up and eps_t below 0.005
        r = lrfd.rc_rectangular_flexural_resistance(
            a_s=12.0, f_y=60.0, f_c=4.0, b=12.0, d_s=21.5
        )
        assert r.details["eps_t"] < 0.005
        assert r.phi < 0.9

    def test_compression_steel_increases_capacity(self):
        base = lrfd.rc_rectangular_flexural_resistance(
            a_s=8.0, f_y=60.0, f_c=4.0, b=12.0, d_s=21.5
        )
        with_comp = lrfd.rc_rectangular_flexural_resistance(
            a_s=8.0, f_y=60.0, f_c=4.0, b=12.0, d_s=21.5,
            a_s_prime=2.0, d_s_prime=2.5,
        )
        assert with_comp.factored_capacity > base.factored_capacity


class TestRCMinReinforcement:
    def test_mcr_governs_without_demand(self):
        # 12x24 beam: Sc = 12*24^2/6 = 1152 in^3, fr = 0.24*sqrt(4) = 0.48
        # Mcr = 0.67*1.6*0.48*1152 = 592.8 kip-in
        r = lrfd.rc_minimum_reinforcement(m_n=1000.0, phi=0.9, f_c=4.0, s_c=1152.0)
        assert r.demand == pytest.approx(0.67 * 1.6 * 0.48 * 1152.0)
        assert r.ok

    def test_133_mu_governs_when_smaller(self):
        r = lrfd.rc_minimum_reinforcement(
            m_n=1000.0, phi=0.9, f_c=4.0, s_c=1152.0, m_u=300.0
        )
        assert r.demand == pytest.approx(1.33 * 300.0)


class TestRCShear:
    def test_concrete_only_simplified(self):
        # bv = 12, dv = 20, f'c = 4: Vc = 0.0316*2*2*12*20 = 30.34 kip
        r = lrfd.rc_shear_resistance(b_v=12.0, d_v=20.0, f_c=4.0)
        assert r.capacity == pytest.approx(0.0316 * 2.0 * 2.0 * 12.0 * 20.0)
        assert r.phi == 0.9

    def test_stirrups_add_vs(self):
        # #4 stirrups (Av = 0.40) at 12 in, theta = 45: Vs = 0.4*60*20/12 = 40
        r = lrfd.rc_shear_resistance(
            b_v=12.0, d_v=20.0, f_c=4.0, a_v=0.40, s=12.0, f_y=60.0
        )
        assert r.details["Vs"] == pytest.approx(40.0)

    def test_upper_limit_governs(self):
        r = lrfd.rc_shear_resistance(
            b_v=12.0, d_v=20.0, f_c=4.0, a_v=4.0, s=3.0, f_y=60.0
        )
        assert r.capacity == pytest.approx(0.25 * 4.0 * 12.0 * 20.0)


class TestRegistry:
    def test_articles_registered(self):
        for num in ("6.10.8.2.2", "6.10.8.2.3", "6.10.8.1.2", "6.10.9",
                    "5.6.3.2", "5.6.3.3", "5.7.3.3"):
            assert num in lrfd.ARTICLES

    def test_design_loop_over_flange_sizes(self):
        """The motivating use case: size a compression flange by looping."""
        demand = 42.0  # ksi factored flange stress
        candidates = [(w, t) for w in (12, 14, 16, 18) for t in (0.75, 1.0, 1.25)]
        passing = [
            (w, t)
            for w, t in candidates
            if lrfd.flange_local_buckling_resistance(
                b_fc=w, t_fc=t, f_yc=50.0, f_yw=50.0, f_bu=demand
            ).ok
        ]
        assert passing  # at least one candidate works
        assert all(
            w / (2 * t) <= 0.56 * math.sqrt(29000.0 / 35.0) for w, t in passing
        )
