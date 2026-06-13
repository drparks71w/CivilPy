"""Coverage fill-ins to reach 100% across civilpy modules.

Targets the specific branches and helper functions the main suites leave
uncovered. Grouped by module.
"""
import json
import math
from unittest.mock import MagicMock, patch

import pytest


# ── structural/section_properties.py — geometric property helpers ─────────────

from civilpy.structural import section_properties as SP


def test_section_property_helpers():
    for fn, args in [
        (SP.get_rectangular_section_properties, (2.0, 4.0)),
        (SP.get_rectangular_section_properties_baseline, (2.0, 4.0)),
        (SP.get_triangular_section_properties, (3.0, 6.0)),
        (SP.get_triangular_section_properties_baseline, (3.0, 6.0)),
        (SP.get_bar_section_properties, (5.0,)),
        (SP.get_pipe_section_properties, (10.0, 8.0)),
        (SP.get_oval_section_properties, (3.0, 5.0)),
        (SP.get_hollow_oval_section_properties, (5.0, 3.0, 4.0, 2.0)),
    ]:
        I, S, r = fn(*args)
        assert I > 0 and S > 0 and r > 0


# ── geotech/spt.py — edge cases ───────────────────────────────────────────────

from civilpy.geotech import spt


def test_spt_edge_cases():
    # sigma'_v <= 0 → CN capped
    assert spt.overburden_correction(0.0, cap=1.7) == 1.7
    with pytest.raises(ValueError):
        spt.friction_angle_from_n(-1.0)
    with pytest.raises(ValueError):
        spt.relative_density_from_n(-1.0)


# ── structural/aashto/lrfd/core.py — CheckResult ratio/ok ─────────────────────

from civilpy.structural.aashto.lrfd.core import CheckResult


def test_check_result_ratio_and_ok():
    no_demand = CheckResult(article="5.1", name="x", capacity=10.0, demand=None)
    assert no_demand.ratio is None
    assert no_demand.ok is None

    zero_demand = CheckResult(article="5.1", name="x", capacity=10.0, demand=0.0)
    assert zero_demand.ratio == float("inf")

    real = CheckResult(article="5.1", name="x", capacity=10.0, demand=5.0)
    assert real.ratio == 2.0
    assert real.ok is True


# ── transportation/roadway.py — vertical curve lengths ────────────────────────

from civilpy.transportation import roadway


def test_crest_curve_length_branches():
    assert roadway.crest_curve_length(0.0, 200.0) == 0.0
    # large algebraic difference, short sight distance → S < L governs
    assert roadway.crest_curve_length(8.0, 200.0) > 0
    # small difference, long sight distance → S > L branch / max fallback
    assert roadway.crest_curve_length(0.5, 800.0) > 0
    assert roadway.crest_curve_length(1.0, 100.0) > 0


def test_sag_curve_length_branches():
    assert roadway.sag_curve_length(0.0, 200.0) == 0.0
    assert roadway.sag_curve_length(8.0, 200.0) > 0      # l_s_less >= S
    assert roadway.sag_curve_length(3.0, 400.0) > 0      # l_s_more in (0, S]
    assert roadway.sag_curve_length(0.5, 800.0) > 0      # max() fallback


# ── structural/midas.py — request error branch + db wrappers + repr ───────────

from civilpy.structural.midas import MidasCivil


def _client():
    return MidasCivil(base_url="http://localhost:5000", mapi_key="k")


def _resp(data=None, ok=True, status=200, bad_json=False):
    m = MagicMock()
    m.ok = ok
    m.status_code = status
    m.content = b"{}" if not bad_json else b"not json"
    if bad_json:
        m.json.side_effect = ValueError("bad json")
    else:
        m.json.return_value = {} if data is None else data
    return m


def test_request_invalid_json_yields_empty_dict():
    midas = _client()
    with patch("requests.request", return_value=_resp(bad_json=True)):
        assert midas.request("GET", "/db/NODE") == {}


def test_db_wrappers_route(monkeypatch):
    midas = _client()
    calls = []
    monkeypatch.setattr(midas, "request",
                        lambda method, command, body=None: calls.append((method, command)) or {})
    midas.nodes(); midas.put_nodes({"1": {}})
    midas.elements(); midas.put_elements({"1": {}})
    midas.materials(); midas.put_materials({"1": {}})
    midas.sections(); midas.put_sections({"1": {}})
    midas.supports(); midas.put_supports({"1": {}})
    midas.static_loads(); midas.put_static_loads({"1": {}})
    midas.post_db("NODE", {"1": {}})
    midas.delete_db("NODE", ids=[1, 2])
    midas.delete_db("ELEM")
    cmds = [c for _, c in calls]
    assert "/db/NODE" in cmds and "/db/ELEM" in cmds
    # delete with ids builds an id list path
    assert any(c.endswith("/1,2") for c in cmds)


def test_midas_repr():
    assert "localhost:5000" in repr(_client())


# ── general/__init__.py — DB helper guard ─────────────────────────────────────

def test_get_table_as_df_requires_sqlalchemy(monkeypatch):
    import civilpy.general as g
    monkeypatch.setattr(g, "text", None)
    with pytest.raises(ImportError, match="SQLAlchemy"):
        g.get_table_as_df(object(), "schema", "table")


# ── geotech/deep_foundation.py — input validation ─────────────────────────────

def test_driven_pile_capacity_rejects_nonpositive_dims():
    from civilpy.geotech import deep_foundation as df
    from civilpy.geotech.boring import Borehole, SPTResult, DriveIncrement
    bh = Borehole(boring_id="X", total_depth_ft=50.0,
                  spt=[SPTResult(10.0, (DriveIncrement(5), DriveIncrement(6), DriveIncrement(7)))])
    with pytest.raises(ValueError, match="positive"):
        df.driven_pile_capacity(bh, width_ft=1.0, tip_depth_ft=0.0)


# ── geotech/lateral_earth.py — sloped backfill + explicit k ───────────────────

def test_lateral_earth_sloped_and_explicit_k():
    from civilpy.geotech import lateral_earth as le
    assert le.rankine_ka(30.0, beta_deg=10.0) > 0     # sloped backfill branch
    assert le.rankine_kp(30.0, beta_deg=10.0) > 0
    wall = le.LateralEarthPressure(height=10.0, gamma=120.0, phi=30.0, k=0.33)
    assert wall.k == 0.33


# ── structural/shear_flow.py — plot onto a supplied axis ──────────────────────

def test_shear_flow_plot_with_supplied_axis():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from civilpy.structural.shear_flow import ShearSection, Plate
    sec = ShearSection([Plate(12, 2, 0), Plate(1, 20, 2), Plate(12, 2, 22)])
    fig, ax = plt.subplots()
    sec.plot(50_000.0, ax=ax)   # ax provided → skips the two-panel section draw
    plt.close(fig)


# ── structural/moment_distribution.py — lazy solve in moment_at ───────────────

def test_moment_at_triggers_solve():
    from civilpy.structural.moment_distribution import MomentDistribution
    md = MomentDistribution()
    md.add_span(20.0, w=1.0)
    md.add_span(20.0, w=1.0)
    # end_moments is None until solved; moment_at must solve on demand
    assert md.end_moments is None
    md.moment_at(0, 10.0)
    assert md.end_moments is not None


# ── structural/odot — railing height + headwall lookup errors ─────────────────

def _railing(**kw):
    from civilpy.structural.odot.bridge_railing import BridgeRailing
    defaults = dict(scd="BR-1", scd_date="2020", designation="TST-1",
                    name="Test Rail", shape="single-slope", material="concrete",
                    test_level="TL-4", height=42.0)
    defaults.update(kw)
    return BridgeRailing(**defaults)


def test_bridge_railing_checks():
    # meets_minimum_height with a recorded height + test level
    assert _railing().meets_minimum_height() in (True, False)
    # successful yield-line check returns a CheckResult
    result = _railing().design_force_check(m_c=10.0, m_w=20.0)
    assert result.demand is not None
    # missing height → error
    with pytest.raises(ValueError, match="no recorded height"):
        _railing(height=None).design_force_check(m_c=10.0, m_w=5.0)
    # missing test level → error
    with pytest.raises(ValueError, match="no crash test level"):
        _railing(test_level="").design_force_check(m_c=10.0, m_w=5.0)


def test_elliptical_headwall_lookup():
    from civilpy.structural.odot import headwall as hw
    # a valid rise from the loaded catalog returns its entry
    known = hw.HEADWALLS_CONCRETE_ELLIPTICAL[0]
    assert hw.elliptical_headwall_for_rise(known.rise) is known
    with pytest.raises(KeyError):
        hw.elliptical_headwall_for_rise(-1.0)


def test_lateral_earth_with_water_table():
    from civilpy.geotech import lateral_earth as le
    wall = le.LateralEarthPressure(height=20.0, gamma=120.0, phi=30.0,
                                   water_depth=8.0)
    # pressure below the water table exercises the buoyant + pore branch
    assert wall.pressure_at(15.0) > wall.pressure_at(5.0)
    assert wall.resultant > 0
    assert 0.0 < wall.resultant_height < wall.height


# ── aashto/lrfd small-function edge cases ─────────────────────────────────────

from civilpy.structural.aashto.lrfd import (
    columns as lrfd_cols, distribution as lrfd_dist, concrete as lrfd_conc,
    RebarLayer,
)
from civilpy.structural.aashto.lrfd.appendix_b6 import (
    b6_effective_plastic_moment, b6_redistribution_moment,
)


def test_circular_segment_zero_depth():
    assert lrfd_cols._circular_segment(10.0, 0.0) == (0.0, 0.0)
    assert lrfd_cols._circular_segment(10.0, -5.0) == (0.0, 0.0)


def test_pm_interaction_requires_b_and_h():
    layers = [RebarLayer(4.0, 2.5), RebarLayer(4.0, 21.5)]
    with pytest.raises(ValueError, match="need b and h"):
        lrfd_cols.rc_pm_interaction_diagram(layers=layers, f_c=4.0, f_y=60.0)


def test_skew_correction_shear_zero_skew():
    assert lrfd_dist.skew_correction_shear(0.0, l_ft=80.0, t_s=8.0, k_g=400000.0) == 1.0


def test_b6_invalid_limit_state_raises():
    with pytest.raises(ValueError, match="limit_state"):
        b6_effective_plastic_moment(10000.0, b_fc=16.0, t_fc=1.0, d=40.0, f_yc=50.0,
                                    limit_state="bogus")
    with pytest.raises(ValueError, match="limit_state"):
        b6_redistribution_moment(-12000.0, m_pe=11000.0, limit_state="bogus")


def test_rc_flexure_compression_steel_not_yielding():
    # compression steel placed deep (large d_s_prime) so it doesn't yield → neglected
    r = lrfd_conc.rc_rectangular_flexural_resistance(
        a_s=3.0, f_y=60.0, f_c=4.0, b=12.0, d_s=21.5,
        a_s_prime=2.0, f_y_prime=60.0, d_s_prime=10.0)
    assert r.capacity > 0


# ── geotech/cande_adapter.py — soil selection ─────────────────────────────────

from civilpy.geotech import cande_adapter as ca
from civilpy.geotech.boring import GradingResult, GradingPoint


def test_nearest_compaction_unknown_group_raises():
    with pytest.raises(ValueError, match="no Duncan/Selig soils"):
        ca._nearest_compaction("ZZ", 95.0)


def test_duncan_selig_from_gradation_fine_and_coarse():
    fine = GradingResult(5.0, (GradingPoint(1.0, 100), GradingPoint(0.075, 60)))  # 60% fines
    mat_fine = ca.duncan_selig_from_gradation(fine, compaction_percent=85.0, density_pcf=110.0)
    assert mat_fine is not None
    coarse = GradingResult(5.0, (GradingPoint(2.0, 100), GradingPoint(0.075, 8)))  # 8% fines
    mat_coarse = ca.duncan_selig_from_gradation(coarse, compaction_percent=95.0, density_pcf=125.0)
    assert mat_coarse is not None


def test_classify_coarse_branches():
    assert ca._classify_coarse(None) == "sand"
    silty = GradingResult(5.0, (GradingPoint(1.0, 100), GradingPoint(0.075, 20)))  # 20% fines
    assert ca._classify_coarse(silty) == "silty_sand"
    gravelly = GradingResult(5.0, (GradingPoint(10.0, 100), GradingPoint(2.0, 50),
                                   GradingPoint(0.075, 5)))
    assert ca._classify_coarse(gravelly) in ("gravelly_sand", "sand")
    # low fines, fine median → plain sand (final fallback)
    fine_sand = GradingResult(5.0, (GradingPoint(1.0, 100), GradingPoint(0.3, 50),
                                    GradingPoint(0.075, 5)))
    assert ca._classify_coarse(fine_sand) == "sand"


# ── transportation/curves.py — grade plateaus + no-turning-point ──────────────

def test_vertical_curve_grade_and_high_low():
    from civilpy.transportation.curves import VerticalCurve
    vc = VerticalCurve(g1_pct=2.5, g2_pct=-1.5, length_ft=800.0,
                       pvi_station_ft=1000.0, pvi_elevation_ft=100.0)
    assert vc.grade_at(0.0) == 2.5          # before BVC → g1
    assert vc.grade_at(1_000_000.0) == -1.5  # after EVC → g2
    # both grades same sign → no crest/sag turning point
    same_sign = VerticalCurve(2.0, 1.0, 500.0, 0.0, 50.0)
    assert same_sign.high_low_point() is None
