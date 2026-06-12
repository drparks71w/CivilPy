#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see package header)

"""Shear flow, lateral earth, soil profiles, moment distribution, open
channel, K-factors, development length: analytic cross-checks."""

import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from civilpy.structural.shear_flow import Plate, ShearSection
from civilpy.structural.moment_distribution import MomentDistribution
from civilpy.structural.effective_length import k_factor
from civilpy.geotech.lateral_earth import (
    rankine_ka, rankine_kp, coulomb_ka, LateralEarthPressure,
)
from civilpy.geotech.soil_profile import SoilLayer, SoilProfile
from civilpy.water_resources.open_channel import RectangularChannel
from civilpy.structural.aashto import lrfd


class TestShearFlow:
    def test_rectangle_parabola(self):
        sec = ShearSection([Plate(4.0, 12.0, 0.0)])
        # tau_max = 1.5 V/A at the NA
        assert sec.tau(48.0, 6.0) == pytest.approx(1.5 * 48.0 / 48.0)
        assert sec.tau(48.0, 11.999) == pytest.approx(0.0, abs=1e-2)

    def test_ibeam_flange_web_jump(self):
        sec = ShearSection([Plate(12, 2, 0), Plate(1, 20, 2), Plate(12, 2, 22)])
        assert sec.y_bar == pytest.approx(12.0)
        just_below = sec.tau(50.0, 21.99)   # web side of the joint
        just_above = sec.tau(50.0, 22.01)   # flange side
        assert just_below == pytest.approx(just_above * 12.0, rel=0.01)

    def test_plot(self):
        sec = ShearSection([Plate(12, 2, 0), Plate(1, 20, 2), Plate(12, 2, 22)])
        assert sec.plot(50.0) is not None
        plt.close("all")


class TestLateralEarth:
    def test_rankine_coefficients(self):
        assert rankine_ka(30.0) == pytest.approx(1.0 / 3.0)
        assert rankine_kp(30.0) == pytest.approx(3.0)
        assert rankine_ka(30.0) * rankine_kp(30.0) == pytest.approx(1.0)

    def test_coulomb_reduces_to_rankine(self):
        assert coulomb_ka(30.0) == pytest.approx(rankine_ka(30.0))

    def test_sloped_backfill_increases_ka(self):
        assert rankine_ka(30.0, beta_deg=15.0) > rankine_ka(30.0)

    def test_resultant_dry(self):
        w = LateralEarthPressure(height=12.0, gamma=120.0, phi=30.0)
        assert w.resultant == pytest.approx(0.5 * (1 / 3) * 120 * 144, rel=1e-3)
        assert w.resultant_height == pytest.approx(4.0, rel=1e-2)

    def test_surcharge_adds_rectangle(self):
        w = LateralEarthPressure(12.0, 120.0, 30.0, surcharge=300.0)
        extra = (1.0 / 3.0) * 300.0 * 12.0
        base = 0.5 * (1 / 3) * 120 * 144
        assert w.resultant == pytest.approx(base + extra, rel=1e-3)

    def test_water_table_raises_pressure(self):
        dry = LateralEarthPressure(12.0, 120.0, 30.0)
        wet = LateralEarthPressure(12.0, 120.0, 30.0, water_depth=6.0)
        assert wet.pressure_at(12.0) > dry.pressure_at(12.0)
        assert wet.plot() is not None
        plt.close("all")


class TestSoilProfile:
    def test_stress_components(self):
        sp = SoilProfile([SoilLayer("Sand", 10, 115), SoilLayer("Clay", 15, 105)],
                         water_table=10.0)
        total, pore, eff = sp.stresses_at(25.0)
        assert total == pytest.approx(115 * 10 + 105 * 15)
        assert pore == pytest.approx(62.4 * 15)
        assert eff == pytest.approx(total - pore)

    def test_plots(self):
        sp = SoilProfile([SoilLayer("Fill", 5, 110), SoilLayer("Clay", 20, 100)],
                         water_table=8.0)
        assert sp.plot(spt=[(2, 8), (7, 12), (15, 6)]) is not None
        assert sp.plot_stress_profile() is not None
        plt.close("all")


class TestMomentDistribution:
    def test_two_span_udl(self):
        md = MomentDistribution()
        md.add_span(20.0, w=2.0)
        md.add_span(20.0, w=2.0)
        m = md.solve()
        # interior support hogging moment = wL^2/8 = 100 kip-ft
        assert abs(m[0][1]) == pytest.approx(100.0, rel=1e-3)
        # beam-convention check via moment_at
        assert md.moment_at(0, 20.0) == pytest.approx(-100.0, rel=1e-3)
        assert md.moment_at(0, 0.0) == pytest.approx(0.0, abs=1e-3)

    def test_fixed_fixed_single_span(self):
        md = MomentDistribution(left_fixed=True, right_fixed=True)
        md.add_span(20.0, w=2.0)
        m = md.solve()
        assert abs(m[0][0]) == pytest.approx(2.0 * 400.0 / 12.0, rel=1e-6)

    def test_point_load_fems(self):
        md = MomentDistribution(left_fixed=True, right_fixed=True)
        md.add_span(20.0, point_load=(40.0, 10.0))
        m = md.solve()
        assert abs(m[0][0]) == pytest.approx(40.0 * 20.0 / 8.0, rel=1e-6)

    def test_plot(self):
        md = MomentDistribution()
        md.add_span(20.0, w=2.0)
        md.add_span(25.0, w=2.0, point_load=(20.0, 10.0))
        assert md.plot() is not None
        plt.close("all")


class TestOpenChannel:
    CH = RectangularChannel(width=10.0, n=0.013, slope=0.002)

    def test_critical_depth(self):
        yc = self.CH.critical_depth(200.0)
        assert yc == pytest.approx((20.0**2 / 32.2) ** (1 / 3))
        assert self.CH.froude(200.0, yc) == pytest.approx(1.0, rel=1e-3)

    def test_normal_depth_satisfies_manning(self):
        yn = self.CH.normal_depth(200.0)
        assert self.CH.manning_q(yn) == pytest.approx(200.0, rel=1e-4)

    def test_alternate_depths_share_energy(self):
        yc = self.CH.critical_depth(200.0)
        e = self.CH.specific_energy(200.0, yc) * 1.3
        y1, y2 = self.CH.alternate_depths(200.0, e)
        assert y1 < yc < y2
        assert self.CH.specific_energy(200.0, y1) == pytest.approx(e, rel=1e-4)
        assert self.CH.specific_energy(200.0, y2) == pytest.approx(e, rel=1e-4)

    def test_subcritical_energy_raises(self):
        with pytest.raises(ValueError):
            self.CH.alternate_depths(200.0, 0.1)

    def test_plot(self):
        e = self.CH.specific_energy(200.0, self.CH.critical_depth(200.0)) * 1.3
        assert self.CH.plot_specific_energy(200.0, energy=e) is not None
        plt.close("all")


class TestEffectiveLength:
    def test_chart_limits(self):
        assert k_factor(0.0001, 0.0001) == pytest.approx(0.5, abs=1e-3)
        assert k_factor(1000.0, 1000.0) == pytest.approx(1.0, abs=1e-2)
        assert k_factor(0.0001, 0.0001, sway=True) == pytest.approx(1.0, abs=1e-3)

    def test_textbook_values(self):
        assert k_factor(1.0, 1.0) == pytest.approx(0.77, abs=0.01)
        assert k_factor(1.0, 1.0, sway=True) == pytest.approx(1.32, abs=0.01)


class TestDevelopmentLength:
    def test_basic_ld(self):
        # #8 bar: ldb = 2.4*1.0*60/2 = 72 in
        r = lrfd.rebar_development_length(d_b=1.0)
        assert r.details["ldb"] == pytest.approx(72.0)
        assert r.details["ld"] == pytest.approx(72.0)

    def test_top_bar_and_epoxy_capped(self):
        r = lrfd.rebar_development_length(d_b=1.0, top_bar=True,
                                          epoxy_coated=True,
                                          cover_lt_3db=True)
        assert r.details["modifier"] == pytest.approx(1.7)  # 1.3*1.5 capped

    def test_twelve_inch_floor(self):
        r = lrfd.rebar_development_length(d_b=0.375, f_c=10.0)
        assert r.details["ld"] >= 12.0

    def test_embedment_check(self):
        r = lrfd.rebar_development_length(d_b=1.0, available=80.0)
        assert r.ok
