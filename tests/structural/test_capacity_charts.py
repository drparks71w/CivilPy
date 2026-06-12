"""Tests for the capacity-chart and section-sketch visualizations."""

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from civilpy.structural.aashto.lrfd.plots import (
    plot_mn_vs_lb, plot_column_curve, plot_rc_strain_compatibility)
from civilpy.structural.aashto.lrfd.steel import (
    lateral_torsional_buckling_resistance)
from civilpy.structural.flexural_stress import (
    flexural_stress, extreme_fiber_stresses, plot_flexural_stress)

GIRDER = dict(b_fc=16.0, t_fc=1.25, d_c=30.0, t_w=0.5625,
              f_yc=50.0, f_yw=50.0)


def test_mn_vs_lb_chart_tracks_the_check():
    fig = plot_mn_vs_lb(**GIRDER, s_xc=1200.0, l_b=240.0, f_bu=32.0)
    ax = fig.axes[0]
    ltb_line = ax.lines[0]
    xs, ys = ltb_line.get_xdata(), ltb_line.get_ydata()
    # every plotted point reproduces the 6.10.8.2.3 capacity
    for x_ft, y in zip(xs[::97], ys[::97]):
        check = lateral_torsional_buckling_resistance(
            x_ft * 12.0, **GIRDER)
        assert y == pytest.approx(check.capacity * 1200.0 / 12.0)
    # plateau at short Lb equals Fyc (Rb = Rh = 1)
    assert ys[0] == pytest.approx(50.0 * 1200.0 / 12.0)
    plt.close(fig)


def test_mn_vs_lb_stress_axis_without_sxc():
    fig = plot_mn_vs_lb(**GIRDER)
    ax = fig.axes[0]
    assert "F_{nc}" in ax.get_ylabel()
    assert ax.lines[0].get_ydata()[0] == pytest.approx(50.0)
    plt.close(fig)


def test_column_curve_single_and_multiple_grades():
    fig = plot_column_curve([36.0, 50.0], kl_over_r=90.0, f_u_ksi=18.0)
    ax = fig.axes[0]
    curves = [ln for ln in ax.lines if len(ln.get_xdata()) > 10]
    assert len(curves) == 2
    # short columns approach Fy; long columns approach elastic buckling
    for fy, line in zip((36.0, 50.0), curves):
        ys = line.get_ydata()
        assert ys[0] == pytest.approx(fy, rel=0.01)
        assert ys[-1] < 0.5 * fy
    plt.close(fig)


def test_strain_compatibility_sketch_panels():
    fig = plot_rc_strain_compatibility(
        b=14.0, h=30.0, d_s=27.0, a_s=4.0, f_c=4.0, f_y=60.0)
    assert len(fig.axes) == 3
    plt.close(fig)


def test_flexural_stress_values_and_plot():
    assert flexural_stress(1200.0, 800.0, 6.0) == pytest.approx(9.0)
    top, bot = extreme_fiber_stresses(1000.0, 500.0, c_top=10.0, c_bot=5.0)
    assert top == pytest.approx(-20.0)
    assert bot == pytest.approx(10.0)
    fig = plot_flexural_stress(1000.0, 500.0, depth_in=15.0, y_bar_in=5.0,
                               width_in=10.0)
    plt.close(fig)
