"""Tests for GVF water-surface profiles and pipe EGL/HGL profiles."""

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from civilpy.water_resources.open_channel import RectangularChannel
from civilpy.water_resources.pipe_flow import PipeSegment, PipeProfile


# ── Gradually varied flow ──────────────────────────────────────────────────


def mild_channel():
    return RectangularChannel(width=10.0, n=0.013, slope=0.0004)


def test_friction_slope_recovers_normal_depth():
    ch = mild_channel()
    yn = ch.normal_depth(q=150.0)
    assert ch.friction_slope(150.0, yn) == pytest.approx(ch.s, rel=1e-6)


def test_profile_classification():
    ch = mild_channel()
    q = 150.0
    yn, yc = ch.normal_depth(q), ch.critical_depth(q)
    assert yn > yc                       # mild slope
    assert ch.classify_profile(q, yn * 1.5) == "M1"
    assert ch.classify_profile(q, (yn + yc) / 2.0) == "M2"
    assert ch.classify_profile(q, yc * 0.5) == "M3"
    steep = RectangularChannel(10.0, n=0.013, slope=0.03)
    assert ch.classify_profile(q, yn * 1.5)[0] == "M"
    assert steep.classify_profile(q, steep.critical_depth(q) * 2.0) == "S1"
    flat = RectangularChannel(10.0, n=0.013, slope=0.0)
    assert flat.classify_profile(q, yc * 0.5) == "H3"


def test_m1_backwater_decays_toward_normal_depth():
    ch = mild_channel()
    q = 150.0
    yn = ch.normal_depth(q)
    x, y = ch.gvf_profile(q, y_control=yn * 1.6, length=20000.0)
    assert x[-1] < 0.0                   # subcritical: marched upstream
    assert y[0] == pytest.approx(yn * 1.6)
    # monotonic decay toward yn, never crossing it
    assert (y[1:] <= y[:-1] + 1e-12).all()
    assert y[-1] > yn
    assert y[-1] == pytest.approx(yn, rel=0.02)


def test_m2_drawdown_rises_toward_normal_depth():
    ch = mild_channel()
    q = 150.0
    yn, yc = ch.normal_depth(q), ch.critical_depth(q)
    x, y = ch.gvf_profile(q, y_control=yc * 1.05, length=20000.0)
    assert x[-1] < 0.0
    assert (y[1:] >= y[:-1] - 1e-12).all()
    assert y[-1] < yn
    assert y[-1] == pytest.approx(yn, rel=0.05)


def test_supercritical_marches_downstream():
    steep = RectangularChannel(10.0, n=0.013, slope=0.03)
    q = 150.0
    yc = steep.critical_depth(q)
    x, y = steep.gvf_profile(q, y_control=yc * 0.95, length=2000.0)
    assert x[-1] > 0.0
    yn = steep.normal_depth(q)
    assert y[-1] == pytest.approx(yn, rel=0.05)   # S2 tends to normal


def test_gvf_plot_returns_figure():
    ch = mild_channel()
    yn = ch.normal_depth(150.0)
    fig = ch.plot_gvf_profile(150.0, yn * 1.5, 8000.0)
    plt.close(fig)


# ── Pipe EGL/HGL ───────────────────────────────────────────────────────────


def two_segment_line():
    return PipeProfile(
        [PipeSegment(800.0, 18.0, f=0.018, k_minor=0.5),
         PipeSegment(600.0, 12.0, f=0.020, k_minor=0.3)],
        node_elevations_ft=[150.0, 140.0, 100.0],
        source_energy_ft=170.0, q_cfs=6.0)


def test_velocities_and_continuity():
    p = two_segment_line()
    a18 = 3.14159265 / 4.0 * 1.5**2
    assert p.velocity_fps(0) == pytest.approx(6.0 / a18, rel=1e-6)
    # smaller pipe runs faster
    assert p.velocity_fps(1) > p.velocity_fps(0)


def test_head_losses_accumulate():
    p = two_segment_line()
    hand = 0.0
    for i, seg in enumerate(p.segments):
        hv = p.velocity_fps(i) ** 2 / 64.4
        hand += seg.k_minor * hv
        hand += seg.f * seg.length_ft / (seg.diameter_in / 12.0) * hv
    assert p.total_head_loss() == pytest.approx(hand)
    assert p.egl_at_end() == pytest.approx(170.0 - hand)


def test_grade_lines_monotone_and_hgl_below_egl():
    p = two_segment_line()
    x, egl, hgl, z = p.grade_lines()
    assert (egl[1:] <= egl[:-1] + 1e-12).all()   # energy only decreases
    assert (hgl <= egl + 1e-12).all()
    # the HGL gap equals the local velocity head along segment 2
    hv2 = p.velocity_head_ft(1)
    assert egl[-1] - hgl[-1] == pytest.approx(hv2)


def test_low_pressure_detection():
    # raise a high point above the HGL to force a sub-atmospheric zone
    p = PipeProfile(
        [PipeSegment(500.0, 12.0, f=0.02, k_minor=0.5),
         PipeSegment(500.0, 12.0, f=0.02)],
        node_elevations_ft=[100.0, 168.0, 90.0],
        source_energy_ft=170.0, q_cfs=5.0)
    flagged = p.low_pressure_stations()
    assert flagged and any(abs(x - 500.0) < 1e-6 for x, _ in flagged)
    fig = p.plot_egl_hgl()
    plt.close(fig)


def test_node_elevation_count_validated():
    with pytest.raises(ValueError, match="node elevations"):
        PipeProfile([PipeSegment(100.0, 12.0)], [100.0], 120.0, 2.0)
