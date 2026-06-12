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

"""Hand-checked values for the MBE 6A LRFR rating equation and the
end-to-end capacity-check -> rating-factor composition."""

import pytest

from civilpy.structural.aashto import lrfd


class TestRatingFactor:
    # Steel girder: Mn = 60,000 kip-in, phi_f = 1.0,
    # DC = 18,000, DW = 3,000, LL+IM = 15,000 kip-in
    def test_inventory(self):
        r = lrfd.rating_factor(
            nominal_capacity=60000.0, dc=18000.0, dw=3000.0, ll_im=15000.0
        )
        expected = (60000.0 - 1.25 * 18000.0 - 1.5 * 3000.0) / (1.75 * 15000.0)
        assert r.capacity == pytest.approx(expected)
        assert r.ok  # RF = 1.26

    def test_operating_higher_than_inventory(self):
        inv = lrfd.rating_factor(60000.0, 18000.0, 15000.0, dw=3000.0)
        op = lrfd.rating_factor(60000.0, 18000.0, 15000.0, dw=3000.0,
                                level="operating")
        assert op.capacity == pytest.approx(inv.capacity * 1.75 / 1.35)

    def test_condition_factor_reduces_rf(self):
        good = lrfd.rating_factor(60000.0, 18000.0, 15000.0)
        poor = lrfd.rating_factor(60000.0, 18000.0, 15000.0, condition="poor")
        assert poor.details["phi_c"] == 0.85
        assert poor.capacity < good.capacity

    def test_phic_phis_floor(self):
        # poor (0.85) * welded two-girder (0.85) = 0.7225 -> floored at 0.85
        r = lrfd.rating_factor(60000.0, 18000.0, 15000.0, condition="poor",
                               system="welded_two_girder")
        assert r.details["C"] == pytest.approx(0.85 * 60000.0)

    def test_service_skips_system_factors(self):
        r = lrfd.rating_factor(
            nominal_capacity=29.0, dc=10.0, ll_im=12.0, service=True,
            gamma_dc=1.0, gamma_ll=1.3, condition="poor",
        )
        assert r.details["phi_c"] == 1.0
        assert r.capacity == pytest.approx((29.0 - 10.0) / (1.3 * 12.0))

    def test_composes_with_capacity_check(self):
        """End-to-end: capacity check feeds the rating equation."""
        flb = lrfd.flange_local_buckling_resistance(
            b_fc=16.0, t_fc=1.0, f_yc=50.0, f_yw=50.0
        )
        r = lrfd.rating_factor(
            nominal_capacity=flb.capacity, phi=flb.phi,
            dc=20.0, dw=2.0, ll_im=10.0,
        )
        expected = (50.0 - 1.25 * 20.0 - 1.5 * 2.0) / (1.75 * 10.0)
        assert r.capacity == pytest.approx(expected)


class TestLegalAndPosting:
    def test_legal_factor_bounds(self):
        assert lrfd.legal_load_factor(800.0) == 1.30
        assert lrfd.legal_load_factor(5000.0) == 1.45
        assert lrfd.legal_load_factor(None) == 1.45
        assert lrfd.legal_load_factor(3000.0) == pytest.approx(1.375)

    def test_posting_load(self):
        assert lrfd.posting_load(1.1, 40.0) == 40.0
        assert lrfd.posting_load(0.65, 40.0) == pytest.approx(
            40.0 * 0.35 / 0.7
        )
        assert lrfd.posting_load(0.2, 40.0) == 0.0


class TestRegistry:
    def test_lrfr_articles_registered(self):
        for num in ("6A.4.2.1", "6A.4.4.2.3a", "6A.8.3"):
            assert num in lrfd.ARTICLES
