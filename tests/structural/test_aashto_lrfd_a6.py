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

"""Hand-checked values for Appendix A6, anchorage set, multiple presence,
and the lever rule."""

import math

import pytest

from civilpy.structural.aashto import lrfd

# Doubly symmetric test girder: D=48, tw=0.5, flanges 16x1.5
# Myc = Myt = 50 * Sx; Mp ~ 1.12*My for this shape (use explicit values)
GEOM = dict(d_web=48.0, t_w=0.5, b_fc=16.0, t_fc=1.5, b_ft=16.0, t_ft=1.5)


class TestStVenantJ:
    def test_formula(self):
        j = lrfd.st_venant_j(**GEOM)
        expected = (
            48.0 * 0.125 / 3.0
            + 2.0 * (16.0 * 1.5**3 / 3.0 * (1.0 - 0.63 * 1.5 / 16.0))
        )
        assert j == pytest.approx(expected)


class TestWebPlastification:
    ARGS = dict(d_c=24.0, d_cp=24.0, t_w=0.5, m_p=56000.0,
                m_yc=50000.0, m_yt=50000.0, f_yc=50.0)

    def test_compact_web_reaches_mp(self):
        # 2Dcp/tw = 96; lambda_pw = sqrt(580)/(0.54*1.12 - 0.09)^2 = 90.4?
        # sqrt(29000/50)=24.08; /(0.6048-0.09)^2 = 24.08/0.265 = 90.86 -> 96>90.86
        # actually noncompact; use thicker web for compact: tw=0.6 -> 80 < 90.86
        r = lrfd.web_plastification_factors(**{**self.ARGS, "t_w": 0.6})
        assert r.details["compact_web"]
        assert r.details["Rpc"] == pytest.approx(56000.0 / 50000.0)
        assert r.details["Rpt"] == pytest.approx(56000.0 / 50000.0)

    def test_noncompact_web_interpolates(self):
        r = lrfd.web_plastification_factors(**self.ARGS)
        assert not r.details["compact_web"]
        assert 1.0 < r.details["Rpc"] < 56000.0 / 50000.0

    def test_rpc_exceeds_one_always_above_rh(self):
        # Even a barely noncompact web should stay above Rh = 1.0
        r = lrfd.web_plastification_factors(**self.ARGS)
        assert r.details["Rpc"] > 1.0


class TestA6FLB:
    BASE = dict(d_web=48.0, t_w=0.5, f_yc=50.0, f_yw=50.0, f_yt=50.0,
                s_xc=1000.0, s_xt=1000.0, r_pc=1.1, m_yc=50000.0)

    def test_compact_flange_plateau(self):
        r = lrfd.a6_flange_local_buckling(b_fc=16.0, t_fc=1.0, **self.BASE)
        assert r.capacity == pytest.approx(1.1 * 50000.0)
        assert r.details["compact"]

    def test_noncompact_flange_below_plateau(self):
        r = lrfd.a6_flange_local_buckling(b_fc=20.0, t_fc=0.875, **self.BASE)
        assert not r.details["compact"]
        assert r.capacity < 1.1 * 50000.0
        # kc = 4/sqrt(96) = 0.408 (within bounds)
        assert r.details["lambda_rf"] == pytest.approx(
            0.95 * math.sqrt(29000.0 * (4.0 / math.sqrt(96.0)) / 35.0)
        )


class TestA6LTB:
    BASE = dict(r_t=4.1, j_torsion=16.0, h_depth=49.5, f_yc=50.0,
                f_yw=50.0, f_yt=50.0, s_xc=1000.0, s_xt=1000.0,
                r_pc=1.1, m_yc=50000.0)

    def test_plateau(self):
        l_p = 4.1 * math.sqrt(29000.0 / 50.0)
        r = lrfd.a6_lateral_torsional_buckling(l_b=0.9 * l_p, **self.BASE)
        assert r.capacity == pytest.approx(1.1 * 50000.0)
        assert r.details["regime"] == "plateau"

    def test_lr_exceeds_6108_form(self):
        # A6.3.3-5 Lr with J credit must exceed pi*rt*sqrt(E/Fyr)
        r = lrfd.a6_lateral_torsional_buckling(l_b=100.0, **self.BASE)
        lr_6108 = math.pi * 4.1 * math.sqrt(29000.0 / 35.0)
        assert r.details["Lr"] > lr_6108

    def test_elastic_regime_includes_j_term(self):
        l_r = lrfd.a6_lateral_torsional_buckling(l_b=100.0, **self.BASE).details["Lr"]
        l_b = 1.2 * l_r
        r = lrfd.a6_lateral_torsional_buckling(l_b=l_b, **self.BASE)
        f_cr = (
            math.pi**2 * 29000.0 / (l_b / 4.1) ** 2
            * math.sqrt(1.0 + 0.078 * 16.0 / (1000.0 * 49.5) * (l_b / 4.1) ** 2)
        )
        assert r.capacity == pytest.approx(min(f_cr * 1000.0, 55000.0))
        assert r.details["regime"] == "elastic"

    def test_cb_capped(self):
        l_p = 4.1 * math.sqrt(29000.0 / 50.0)
        r = lrfd.a6_lateral_torsional_buckling(l_b=1.1 * l_p, c_b=2.0,
                                               **self.BASE)
        assert r.capacity == pytest.approx(1.1 * 50000.0)

    def test_tension_flange(self):
        r = lrfd.a6_tension_flange_yielding(r_pt=1.1, m_yt=50000.0,
                                            m_u=50000.0)
        assert r.capacity == pytest.approx(55000.0)
        assert r.ok


class TestAnchorageSet:
    def test_influence_length_and_loss(self):
        # set = 0.375 in, gradient = 0.002 ksi/in:
        # x = sqrt(28500*0.375/0.002) = 2311.7 in
        r = lrfd.ps_anchorage_set_loss(anchor_set=0.375,
                                       friction_gradient=0.002)
        x = math.sqrt(28500.0 * 0.375 / 0.002)
        assert r.details["influence_length"] == pytest.approx(x)
        assert r.capacity == pytest.approx(2.0 * 0.002 * x)

    def test_loss_decreases_with_distance(self):
        at_anchor = lrfd.ps_anchorage_set_loss(0.375, 0.002)
        midway = lrfd.ps_anchorage_set_loss(
            0.375, 0.002,
            x_from_anchor=at_anchor.details["influence_length"] / 2.0,
        )
        assert midway.capacity == pytest.approx(at_anchor.capacity / 2.0)

    def test_zero_beyond_influence(self):
        r = lrfd.ps_anchorage_set_loss(0.375, 0.002, x_from_anchor=5000.0)
        assert r.capacity == 0.0


class TestLeverRule:
    def test_multiple_presence_values(self):
        assert lrfd.multiple_presence_factor(1) == 1.20
        assert lrfd.multiple_presence_factor(2) == 1.00
        assert lrfd.multiple_presence_factor(3) == 0.85
        assert lrfd.multiple_presence_factor(5) == 0.65

    def test_classic_lever_rule(self):
        # S = 9, de = 2: wheels at 0 and 6 ft from ext girder
        # g = ((9-0) + (9-6))/(2*9) = 12/18 = 0.667; *1.2 = 0.8
        g = lrfd.lever_rule_exterior(s_ft=9.0, d_e_ft=2.0)
        assert g == pytest.approx(0.8)

    def test_without_multiple_presence(self):
        g = lrfd.lever_rule_exterior(s_ft=9.0, d_e_ft=2.0,
                                     apply_multiple_presence=False)
        assert g == pytest.approx(2.0 / 3.0)

    def test_wheel_beyond_interior_girder_dropped(self):
        # Tight spacing: second wheel lands past the interior girder
        g6 = lrfd.lever_rule_exterior(s_ft=4.0, d_e_ft=1.0,
                                      apply_multiple_presence=False)
        # x1 = 1, x2 = 7 > S=4 -> only wheel 1: (4-1)/(2*4) = 0.375
        assert g6 == pytest.approx(0.375)


class TestRegistry:
    def test_a6_articles_registered(self):
        for num in ("A6.2", "A6.3.2", "A6.3.3", "A6.4", "5.9.3.2.1",
                    "3.6.1.1.2"):
            assert num in lrfd.ARTICLES
