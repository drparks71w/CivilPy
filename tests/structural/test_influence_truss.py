#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see package header)

"""Influence lines and truss analysis: analytic cross-checks."""

import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from civilpy.structural.influence_lines import InfluenceLine
from civilpy.structural.truss import Truss


class TestInfluenceOrdinates:
    def test_reaction_il_linear(self):
        il = InfluenceLine.reaction(span=20.0, support="A")
        assert il.eta(0.0) == pytest.approx(1.0)
        assert il.eta(20.0) == pytest.approx(0.0)
        assert il.eta(5.0) == pytest.approx(0.75)

    def test_shear_il_jump(self):
        il = InfluenceLine.shear(span=20.0, section=8.0)
        assert il.eta(7.999) == pytest.approx(-7.999 / 20.0, abs=1e-3)
        assert il.eta(8.001) == pytest.approx(1.0 - 8.001 / 20.0, abs=1e-3)

    def test_moment_il_peak(self):
        il = InfluenceLine.moment(span=20.0, section=8.0)
        # peak = a*b/L = 8*12/20 = 4.8 at the section
        assert il.eta(8.0) == pytest.approx(4.8)

    def test_overhang_negative_region(self):
        # supports at 0 and 20, beam extends to 26 (6-ft overhang):
        # unit load on the overhang lifts R_A negative
        il = InfluenceLine.reaction(span=20.0, support="A", length=26.0)
        assert il.eta(26.0) == pytest.approx(-0.3)

    def test_midspan_moment_overhang(self):
        il = InfluenceLine.moment(span=20.0, section=10.0, length=26.0)
        assert il.eta(23.0) == pytest.approx(-1.5)  # negative on overhang


class TestMovingLoads:
    def test_single_axle_finds_peak(self):
        il = InfluenceLine.moment(span=20.0, section=10.0)
        r = il.maximize_axle_train([10.0], [0.0])
        assert r.value == pytest.approx(50.0, rel=1e-3)  # PL/4
        assert r.position == pytest.approx(10.0, abs=0.1)

    def test_tandem_on_short_span(self):
        il = InfluenceLine.moment(span=20.0, section=10.0)
        # 25-kip tandem at 4 ft, straddle: eta(8)+eta(12) = 4+4
        r = il.maximize_axle_train([25.0, 25.0], [0.0, 4.0])
        assert r.value == pytest.approx(25.0 * (4.0 + 4.0), rel=1e-2)

    def test_hl93_tandem_governs_short_span(self):
        il = InfluenceLine.moment(span=20.0, section=10.0)
        hl = il.hl93_effect()
        assert hl["truck"] == pytest.approx(200.0, rel=1e-2)
        assert hl["total"] == pytest.approx(200.0 * 1.33 + 32.0, rel=1e-2)

    def test_hl93_truck_governs_long_span(self):
        il = InfluenceLine.moment(span=120.0, section=60.0)
        hl = il.hl93_effect()
        # truck >> tandem at 120 ft
        assert hl["truck"] > 25.0 * 2 * 29.0  # tandem ceiling

    def test_lane_load_positive_area_only(self):
        il = InfluenceLine.reaction(span=20.0, support="A", length=26.0)
        net = il.uniform_load_effect(1.0, positive_only=False)
        pos = il.uniform_load_effect(1.0)
        assert pos > net

    def test_negative_extreme(self):
        il = InfluenceLine.reaction(span=20.0, support="A", length=26.0)
        r = il.maximize_axle_train([10.0], [0.0], sign=-1.0)
        assert r.value == pytest.approx(-3.0)  # 10 * eta(26) = -3

    def test_plot_with_train(self):
        il = InfluenceLine.moment(span=60.0, section=30.0)
        fig = il.plot(axle_train=([8, 32, 32], [0, 14, 28]))
        assert fig is not None
        plt.close("all")


class TestTruss:
    def _tri(self):
        t = Truss()
        t.add_node("A", 0, 0)
        t.add_node("B", 12, 0)
        t.add_node("C", 6, 8)
        t.add_member("A", "B")
        t.add_member("A", "C")
        t.add_member("B", "C")
        t.add_support("A", fix_x=True, fix_y=True)
        t.add_support("B", fix_y=True)
        return t

    def test_lengths(self):
        t = self._tri()
        assert t.member_lengths()[("A", "C")] == pytest.approx(10.0)

    def test_vertical_load_forces(self):
        t = self._tri()
        t.add_load("C", fy=-50.0)
        f = t.solve()
        # symmetric: diagonal force = (P/2)/sin(theta), sin = 8/10
        assert f[("A", "C")] == pytest.approx(-25.0 / 0.8)
        assert f[("A", "B")] == pytest.approx(25.0 / 0.8 * 0.6)  # tie

    def test_stresses(self):
        t = self._tri()
        t.add_load("C", fy=-50.0)
        s = t.member_stresses(2.0)
        assert s[("A", "C")] == pytest.approx(-31.25 / 2.0)

    def test_plot_titled(self):
        t = self._tri()
        t.add_load("C", fy=-50.0)
        fig = t.plot()
        assert "Truss" in fig.axes[0].get_title()
        plt.close("all")
