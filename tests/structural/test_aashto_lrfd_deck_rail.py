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

"""Hand-checked values for deck crack control, parapet yield-line, and
design-year (edition) handling."""

import math

import pytest

from civilpy.structural.aashto import lrfd


class TestEditionMapping:
    def test_current_default(self):
        assert lrfd.lrfd_edition() == "10th"

    def test_year_lookup(self):
        assert lrfd.lrfd_edition(1996) == "1st"
        assert lrfd.lrfd_edition(2005) == "3rd"
        assert lrfd.lrfd_edition(2011) == "5th"
        assert lrfd.lrfd_edition(2013) == "6th"
        assert lrfd.lrfd_edition(2018) == "8th"
        assert lrfd.lrfd_edition(2026) == "10th"

    def test_pre_lrfd_year_clamps_to_first(self):
        assert lrfd.lrfd_edition(1980) == "1st"


class TestDesignYearValues:
    def test_transfer_compression_pre_2016(self):
        old = lrfd.ps_transfer_compression_check(f_ci=5.0, design_year=2010)
        new = lrfd.ps_transfer_compression_check(f_ci=5.0)
        assert old.capacity == pytest.approx(0.60 * 5.0)
        assert new.capacity == pytest.approx(0.65 * 5.0)

    def test_transfer_compression_2016_boundary(self):
        r = lrfd.ps_transfer_compression_check(f_ci=5.0, design_year=2016)
        assert r.capacity == pytest.approx(0.65 * 5.0)

    def test_min_reinforcement_pre_2012_uses_12_mcr(self):
        old = lrfd.rc_minimum_reinforcement(
            m_n=1000.0, phi=0.9, f_c=4.0, s_c=1152.0, design_year=2008
        )
        # 1.2*Mcr vs gamma form 0.67*1.6 = 1.072
        assert old.demand == pytest.approx(1.2 * 0.48 * 1152.0)
        current = lrfd.rc_minimum_reinforcement(
            m_n=1000.0, phi=0.9, f_c=4.0, s_c=1152.0
        )
        assert current.demand == pytest.approx(0.67 * 1.6 * 0.48 * 1152.0)


class TestCrackControl:
    # 8" deck, dc = 2.5" (top mat with wearing cover), fss = 24 ksi, Class 2
    def test_deck_spacing_limit(self):
        # beta_s = 1 + 2.5/(0.7*5.5) = 1.6494
        # s_max = 700*0.75/(1.6494*24) - 5 = 13.26 - 5 = 8.26 in
        r = lrfd.rc_crack_control_spacing(
            d_c=2.5, h=8.0, f_ss=24.0, exposure_class_2=True, spacing=8.0
        )
        beta_s = 1.0 + 2.5 / (0.7 * 5.5)
        assert r.details["beta_s"] == pytest.approx(beta_s)
        assert r.capacity == pytest.approx(700.0 * 0.75 / (beta_s * 24.0) - 5.0)
        assert r.ok  # 8" spacing just passes

    def test_fss_capped_at_06fy(self):
        r = lrfd.rc_crack_control_spacing(d_c=2.0, h=8.0, f_ss=50.0, f_y=60.0)
        assert r.details["fss_used"] == pytest.approx(36.0)

    def test_class_1_allows_wider_spacing(self):
        c2 = lrfd.rc_crack_control_spacing(d_c=2.5, h=8.0, f_ss=24.0,
                                           exposure_class_2=True)
        c1 = lrfd.rc_crack_control_spacing(d_c=2.5, h=8.0, f_ss=24.0)
        assert c1.capacity > c2.capacity

    def test_z_factor_method(self):
        # z = 170, dc = 2.0, A = 2*2*8 = 32 in^2/bar (#5s at 8")
        # fsa = 170/(2*32)^(1/3) = 170/4.0 = 42.5 -> capped at 36 (0.6*60)
        r = lrfd.rc_crack_control_z_factor(d_c=2.0, a_bar=32.0, f_ss=30.0)
        assert r.capacity == pytest.approx(36.0)
        assert r.ok
        # severe exposure z = 130: fsa = 130/4 = 32.5, not capped
        r2 = lrfd.rc_crack_control_z_factor(d_c=2.0, a_bar=32.0, f_ss=30.0, z=130.0)
        assert r2.capacity == pytest.approx(130.0 / (2.0 * 32.0) ** (1 / 3))


class TestParapetYieldLine:
    # Typical 36" cast-in-place parapet: Mc = 16 kip-ft/ft, Mw = 18 kip-ft,
    # H = 3 ft, checked for TL-3/TL-4 (Ft = 54 kip, Lt = 4 / 3.5 ft)
    def test_interior_region_capacity(self):
        r = lrfd.parapet_yield_line_capacity(
            m_c=16.0, m_w=18.0, h=3.0, l_t=4.0, f_t=54.0
        )
        l_c = 2.0 + math.sqrt(4.0 + 8.0 * 3.0 * 18.0 / 16.0)
        assert r.details["Lc"] == pytest.approx(l_c)
        r_w = (2.0 / (2.0 * l_c - 4.0)) * (8.0 * 18.0 + 16.0 * l_c**2 / 3.0)
        assert r.capacity == pytest.approx(r_w)
        assert r.ok  # ~80 kip > 54 kip

    def test_end_region_weaker_than_interior(self):
        interior = lrfd.parapet_yield_line_capacity(
            m_c=16.0, m_w=18.0, h=3.0, l_t=4.0
        )
        end = lrfd.parapet_yield_line_capacity(
            m_c=16.0, m_w=18.0, h=3.0, l_t=4.0, end_region=True
        )
        assert end.capacity < interior.capacity
        assert end.details["Lc"] < interior.details["Lc"]

    def test_test_level_wrapper_tl4(self):
        r = lrfd.parapet_test_level_check(
            "TL-4", m_c=16.0, m_w=18.0, h_ft=3.0
        )
        assert r.demand == pytest.approx(54.0)
        assert r.details["height_ok"]  # 36" >= 32" min for TL-4
        assert r.ok

    def test_test_level_height_flag(self):
        r = lrfd.parapet_test_level_check(
            "TL-5", m_c=16.0, m_w=18.0, h_ft=3.0
        )
        assert not r.details["height_ok"]  # 36" < 42" min for TL-5

    def test_table_values(self):
        tl3 = lrfd.TEST_LEVEL_LOADS["TL-3"]
        assert (tl3.f_t, tl3.l_t, tl3.h_e_min) == (54.0, 4.0, 24.0)

    def test_overhang_tension(self):
        cap = lrfd.parapet_yield_line_capacity(m_c=16.0, m_w=18.0, h=3.0, l_t=4.0)
        t = lrfd.deck_overhang_collision_tension(
            r_w=cap.capacity, l_c=cap.details["Lc"], h=3.0
        )
        assert t.capacity == pytest.approx(
            cap.capacity / (cap.details["Lc"] + 6.0)
        )

    def test_parapet_design_loop(self):
        """Size parapet reinforcement (via Mc) by looping candidates."""
        passing = [
            m_c for m_c in (8.0, 10.0, 12.0, 14.0, 16.0)
            if lrfd.parapet_test_level_check(
                "TL-4", m_c=m_c, m_w=12.0, h_ft=3.0
            ).ok
        ]
        assert passing
        assert min(passing) > 8.0  # lightest section shouldn't make TL-4


class TestRegistry:
    def test_new_articles_registered(self):
        for num in ("5.6.7", "5.6.7 (pre-2005)", "A13.3.1", "A13.4.2"):
            assert num in lrfd.ARTICLES
