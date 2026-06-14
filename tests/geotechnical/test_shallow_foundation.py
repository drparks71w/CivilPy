#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see the module header for the full notice)

"""Spread-footing bearing capacity, contact pressure, structural checks,
and settlement (civilpy.geotech.shallow_foundation)."""

import math

import pytest

from civilpy.geotech import shallow_foundation as sf
from civilpy.geotech.soil_profile import SoilLayer, SoilProfile


class TestBearingFactors:
    def test_unknown_method(self):
        with pytest.raises(ValueError):
            sf.bearing_capacity_factors(30, "bogus")

    def test_vesic_phi30(self):
        f = sf.bearing_capacity_factors(30, "vesic")
        assert f.nc == pytest.approx(30.14, abs=0.05)
        assert f.nq == pytest.approx(18.40, abs=0.05)
        assert f.ngamma == pytest.approx(22.40, abs=0.05)

    def test_meyerhof_ngamma(self):
        f = sf.bearing_capacity_factors(30, "meyerhof")
        assert f.ngamma == pytest.approx(15.67, abs=0.1)

    def test_hansen_ngamma(self):
        f = sf.bearing_capacity_factors(30, "hansen")
        assert f.ngamma == pytest.approx(15.07, abs=0.1)

    def test_terzaghi_phi30(self):
        f = sf.bearing_capacity_factors(30, "terzaghi")
        assert f.nc == pytest.approx(37.16, abs=0.1)
        assert f.nq == pytest.approx(22.46, abs=0.1)
        assert f.ngamma > 0

    def test_phi_zero_vesic(self):
        f = sf.bearing_capacity_factors(0, "vesic")
        assert f.nc == pytest.approx(5.14)
        assert f.nq == 1.0
        assert f.ngamma == 0.0

    def test_phi_zero_terzaghi(self):
        f = sf.bearing_capacity_factors(0, "terzaghi")
        assert f.nc == pytest.approx(5.7)

    def test_nq_helper(self):
        assert sf.nq_from_phi(30) == pytest.approx(18.40, abs=0.05)


class TestModifiers:
    def test_shape_factors(self):
        f = sf.bearing_capacity_factors(30)
        sc, sq, sg = sf.shape_factors(5, 10, 30, f.nq, f.nc)
        assert sc > 1 and sq > 1
        assert sg == pytest.approx(1.0 - 0.4 * 0.5)

    def test_shape_sgamma_floor(self):
        # B/L = 1 -> 1 - 0.4 = 0.6 is the floor.
        _, _, sg = sf.shape_factors(10, 10, 30, 18.4, 30.14)
        assert sg == pytest.approx(0.6)

    def test_depth_shallow(self):
        dc, dq, dg = sf.depth_factors(3, 6, 30)  # d/b = 0.5 <= 1
        assert dc == pytest.approx(1.0 + 0.4 * 0.5)
        assert dg == 1.0

    def test_depth_deep_uses_arctan(self):
        dc, dq, dg = sf.depth_factors(12, 6, 30)  # d/b = 2 > 1
        k = math.atan(2.0)
        assert dc == pytest.approx(1.0 + 0.4 * k)

    def test_inclination_no_load(self):
        assert sf.inclination_factors(0, 100, 5, 5, 30, 0, 25) == (1, 1, 1)

    def test_inclination_phi_zero(self):
        ic, iq, ig = sf.inclination_factors(10, 100, 5, 5, 0, 1000, 25)
        assert ic < 1.0 and iq == 1.0 and ig == 1.0

    def test_inclination_friction(self):
        ic, iq, ig = sf.inclination_factors(5000, 100000, 5, 5, 30, 500, 25)
        assert 0 < ig < iq < 1.0
        assert ic < 1.0

    def test_inclination_exceeds_resistance(self):
        with pytest.raises(ValueError):
            sf.inclination_factors(1e6, 10, 5, 5, 30, 0, 25)


class TestWaterTable:
    def test_below_wedge(self):
        q, g = sf.bearing_water_table(120, 130, 4, 6, water_table=20)
        assert q == pytest.approx(480)
        assert g == 120

    def test_within_wedge(self):
        q, g = sf.bearing_water_table(120, 130, 4, 6, water_table=7)
        assert q == pytest.approx(480)
        gb = 130 - 62.4
        assert g == pytest.approx(gb + (7 - 4) / 6 * (120 - gb))

    def test_above_footing(self):
        q, g = sf.bearing_water_table(120, 130, 4, 6, water_table=2)
        gb = 130 - 62.4
        assert q == pytest.approx(120 * 2 + gb * 2)
        assert g == pytest.approx(gb)


class TestBearingCapacity:
    def test_basic_strip(self):
        r = sf.ultimate_bearing_capacity(
            6, 6, 4, 120, 30, c=0, method="vesic", shape=False, depth=False
        )
        assert r.q_ult > 0
        assert r.terms["cohesion"] == 0.0
        assert r.q_ult_ksf == pytest.approx(r.q_ult / 1000)
        assert r.area_eff == pytest.approx(36)

    def test_allowable_and_factored(self):
        r = sf.ultimate_bearing_capacity(6, 6, 4, 120, 30)
        assert r.allowable(3) == pytest.approx(r.q_ult / 3)
        assert r.nominal_load() == pytest.approx(r.q_ult * r.area_eff)
        assert r.factored_load(0.45) == pytest.approx(0.45 * r.nominal_load())

    def test_shape_depth_increase_capacity(self):
        plain = sf.ultimate_bearing_capacity(
            6, 6, 4, 120, 30, shape=False, depth=False
        )
        full = sf.ultimate_bearing_capacity(6, 6, 4, 120, 30)
        assert full.q_ult > plain.q_ult

    def test_eccentric_reduces_width(self):
        r = sf.ultimate_bearing_capacity(8, 10, 4, 120, 30, ecc_b=1.0)
        assert r.b_eff == pytest.approx(6.0)
        assert r.l_eff == pytest.approx(10.0)

    def test_eccentric_both_directions_orders(self):
        # ecc on the long side makes l_eff small -> roles swap so b_eff<=l_eff
        r = sf.ultimate_bearing_capacity(10, 8, 4, 120, 30, ecc_l=3.0)
        assert r.b_eff <= r.l_eff

    def test_inclined_load(self):
        r = sf.ultimate_bearing_capacity(
            6, 6, 4, 120, 30, c=200, h=5000, v=80000
        )
        rv = sf.ultimate_bearing_capacity(6, 6, 4, 120, 30, c=200)
        assert r.q_ult < rv.q_ult  # inclination reduces capacity

    def test_inclined_load_v_default_zero(self):
        r = sf.ultimate_bearing_capacity(6, 6, 4, 120, 30, c=500, h=10)
        assert r.q_ult > 0

    def test_water_table_path(self):
        r = sf.ultimate_bearing_capacity(
            6, 6, 4, 120, 30, water_table=2, gamma_sat=130
        )
        assert r.modifiers["q_surcharge"] > 0

    def test_water_table_default_gamma_sat(self):
        r = sf.ultimate_bearing_capacity(6, 6, 4, 120, 30, water_table=2)
        assert r.q_ult > 0

    def test_bad_geometry(self):
        with pytest.raises(ValueError):
            sf.ultimate_bearing_capacity(0, 6, 4, 120, 30)

    def test_excess_eccentricity(self):
        with pytest.raises(ValueError):
            sf.ultimate_bearing_capacity(6, 6, 4, 120, 30, ecc_b=4)


class TestContactPressure:
    def test_requires_positive_load(self):
        with pytest.raises(ValueError):
            sf.contact_pressure(0, 100, 8, 8)

    def test_trapezoid_full_contact(self):
        cp = sf.contact_pressure(100000, 50000, 8, 8)
        assert not cp.uplift and cp.full_contact
        assert cp.q_min > 0
        assert cp.contact_length == 8

    def test_concentric_uniform(self):
        cp = sf.contact_pressure(64000, 0, 8, 8)
        assert cp.q_max == pytest.approx(cp.q_min)
        assert cp.q_max == pytest.approx(1000)

    def test_triangular_uplift(self):
        cp = sf.contact_pressure(100000, 200000, 8, 8)
        assert cp.uplift and cp.q_min == 0.0
        assert cp.contact_length == pytest.approx(3 * (4 - 2))

    def test_resultant_off_footing(self):
        with pytest.raises(ValueError):
            sf.contact_pressure(100000, 100000 * 4, 8, 8)


class TestStructural:
    def test_one_way_demand_outside(self):
        # huge d -> critical section beyond footing -> zero shear
        assert sf.one_way_shear_demand(3000, 8, 8, 2, d_in=200) == 0.0

    def test_one_way_demand_positive(self):
        v = sf.one_way_shear_demand(3000, 8, 10, 2, d_in=12)
        assert v > 0

    def test_one_way_shear_check(self):
        res = sf.footing_one_way_shear(
            3000, 8, 10, 2, thickness_in=24, cover_in=3, f_c=4
        )
        assert res.article == "5.7.3.3"
        assert res.ratio is not None

    def test_punching_shear_default_beta(self):
        res = sf.footing_punching_shear(
            400, 18, 18, thickness_in=30, cover_in=3, f_c=4, q_net=3000
        )
        assert res.article == "5.12.8.6.3"
        assert res.details["relief"] > 0
        assert res.details["beta_c"] == pytest.approx(1.0)

    def test_punching_shear_explicit_beta(self):
        res = sf.footing_punching_shear(
            400, 12, 36, thickness_in=30, cover_in=3, f_c=4, beta_c=3.0
        )
        assert res.details["beta_c"] == 3.0

    def test_flexure_demand(self):
        m = sf.footing_flexure_demand(3000, 10, 2)
        assert m == pytest.approx(3000 * 16 / 2 * 12 / 1000)

    def test_flexure_check(self):
        res = sf.footing_flexure(
            3000, 10, 2, a_s=1.0, thickness_in=24, cover_in=3, f_c=4
        )
        assert res.article == "5.6.3.2"
        assert res.ratio is not None


class TestSettlement:
    def test_stress_2to1(self):
        assert sf.stress_increase_2to1(1000, 8, 10, 0) == pytest.approx(1000)
        assert sf.stress_increase_2to1(1000, 8, 8, 8) == pytest.approx(
            1000 * 64 / (16 * 16)
        )

    def test_schmertmann_profile_limits(self):
        assert sf._schmertmann_profile(1.0) == (0.1, 0.5, 2.0)
        assert sf._schmertmann_profile(10.0) == (0.2, 1.0, 4.0)
        mid = sf._schmertmann_profile(5.5)
        assert 0.1 < mid[0] < 0.2

    def test_schmertmann_constant_es(self):
        r = sf.schmertmann_settlement(2000, 8, 8, 4, es_profile=200000)
        assert r.settlement_in > 0
        assert r.c1 <= 1.0 and r.c2 >= 1.0

    def test_schmertmann_callable_es(self):
        r = sf.schmertmann_settlement(
            2000, 8, 8, 4, es_profile=lambda z: 200000 + 5000 * z
        )
        assert r.settlement_in > 0
        # softer at top, stiffer deep -> less than uniform-soft case
        assert len(r.contributions) == 20

    def test_schmertmann_strip(self):
        r = sf.schmertmann_settlement(2000, 4, 40, 4, es_profile=200000)
        assert r.settlement_in > 0  # L/B = 10 plane-strain branch

    def test_schmertmann_requires_positive(self):
        with pytest.raises(ValueError):
            sf.schmertmann_settlement(0, 8, 8, 4, es_profile=200000)

    def test_schmertmann_c1_floor(self):
        # very deep footing under small load -> C1 hits the 0.5 floor
        r = sf.schmertmann_settlement(500, 8, 8, 20, es_profile=200000)
        assert r.c1 == 0.5


class TestConsolidation:
    def _profile(self):
        sp = SoilProfile(
            [SoilLayer("Sand", 10, 120), SoilLayer("Clay", 20, 110)],
            water_table=5,
        )
        return sp

    def test_normally_consolidated(self):
        sp = self._profile()
        layers = [sf.ConsolidationLayer(1, cc=0.3, e0=0.8)]
        r = sf.consolidation_settlement(sp, layers, delta_sigma=1000)
        assert r.settlement_in > 0
        assert len(r.contributions) == 1

    def test_overconsolidated_below_pc(self):
        sp = self._profile()
        # large preconsolidation -> stays on recompression curve
        layers = [sf.ConsolidationLayer(1, cc=0.3, e0=0.8, cr=0.05,
                                        sigma_pc=50000)]
        r = sf.consolidation_settlement(sp, layers, delta_sigma=500)
        assert r.settlement_in > 0

    def test_overconsolidated_crossing_pc(self):
        sp = self._profile()
        layers = [sf.ConsolidationLayer(1, cc=0.3, e0=0.8, cr=0.05,
                                        sigma_pc=2500)]
        r = sf.consolidation_settlement(sp, layers, delta_sigma=2000,
                                        n_slices=2)
        assert r.settlement_in > 0
        assert len(r.contributions) == 2

    def test_callable_delta_sigma(self):
        sp = self._profile()
        layers = [sf.ConsolidationLayer(1, cc=0.3, e0=0.8)]
        r = sf.consolidation_settlement(
            sp, layers, delta_sigma=lambda z: sf.stress_increase_2to1(
                4000, 8, 8, z - 10
            )
        )
        assert r.settlement_in > 0

    def test_nonpositive_stress_raises(self):
        sp = SoilProfile([SoilLayer("A", 10, 62.4)], water_table=0)
        layers = [sf.ConsolidationLayer(0, cc=0.3, e0=0.8)]
        with pytest.raises(ValueError):
            sf.consolidation_settlement(sp, layers, delta_sigma=100)
