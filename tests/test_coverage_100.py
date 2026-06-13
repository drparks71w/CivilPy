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


# ── structural/influence_lines.py — two-span section past first support ───────

def test_two_span_il_section_in_second_span():
    from civilpy.structural.influence_lines import InfluenceLine
    shear = InfluenceLine.two_span_shear((40.0, 40.0), section=50.0)  # c > l1
    moment = InfluenceLine.two_span_moment((40.0, 40.0), section=50.0)
    assert callable(shear.eta) and callable(moment.eta)
    # evaluate across the structure to exercise the section-dependent branches
    assert isinstance(shear.eta(10.0), float)
    assert isinstance(moment.eta(70.0), float)


# ── structural/beam_bending.py — moment alias ─────────────────────────────────

def test_beam_get_bending_moment_alias():
    from civilpy.structural.beam_bending import Beam, PointLoadV
    beam = Beam(20.0)
    beam.pinned_support = 0
    beam.rolling_support = 20.0
    beam.add_loads([PointLoadV(-10.0, 10.0)])
    assert beam.get_bending_moment() == beam.get_moment_function()


# ── structural/strut_and_tie.py — unstable geometry raises ────────────────────

def test_strut_and_tie_unstable_model_raises():
    from civilpy.structural.strut_and_tie import StrutAndTieModel
    m = StrutAndTieModel()
    m.add_node("A", 0.0, 0.0)
    m.add_node("B", 10.0, 0.0)
    m.add_member("A", "B")
    m.add_load("B", fy=-10.0)          # loaded but inadequately restrained
    m.add_support("A", fix_x=True)     # singular / unstable system
    with pytest.raises(ValueError, match="unstable"):
        m.solve()


# ── structural/aashto/lrfd/prestressed.py — mild compression steel ────────────

def test_ps_flexural_with_compression_steel():
    from civilpy.structural.aashto.lrfd import prestressed as ps
    r = ps.ps_flexural_resistance(a_ps=4.59, f_pu=270.0, d_p=36.0, f_c=4.0, b=48.0,
                                  a_s=2.0, d_s=34.0, f_y=60.0,
                                  a_s_prime=1.0, d_s_prime=2.0, f_y_prime=60.0)
    assert r.capacity > 0


# ── geotech/boring.py — SPT / gradation / sample / borehole edges ─────────────

from civilpy.geotech.boring import (
    DriveIncrement, SPTResult, GradingPoint, GradingResult, Sample, Borehole,
)


def test_sptresult_n_value_and_n60_branches():
    one = SPTResult(10.0, (DriveIncrement(5),))
    assert one.n_value is None              # < 2 increments → no N
    assert one.n60() is None                # N is None → N60 None
    assert one.total_penetration_in == 6.0

    two = SPTResult(10.0, (DriveIncrement(4), DriveIncrement(6)))
    assert two.n_value == 10                # 2 increments → sum of both

    three = SPTResult(8.0, (DriveIncrement(3), DriveIncrement(5), DriveIncrement(7)))
    # borehole-diameter correction branches: <=4.7, <=6.0, else
    assert three.n60(borehole_diameter_in=4.0) > 0
    assert three.n60(borehole_diameter_in=5.5) > 0
    assert three.n60(borehole_diameter_in=8.0, liner=True, rod_length_ft=40.0) > 0
    # rod-length Cr bands: <13 (default depth 8), 13-20, 20-33, >=33
    assert three.n60(rod_length_ft=15.0) > 0
    assert three.n60(rod_length_ft=25.0) > 0


def test_grading_size_lookups_and_coefficients():
    pts = (GradingPoint(10.0, 100), GradingPoint(2.0, 60),
           GradingPoint(0.5, 40), GradingPoint(0.075, 10))
    g = GradingResult(5.0, pts)
    assert g.percent_passing_at(2.0) == 60          # exact match
    assert 40 < g.percent_passing_at(1.0) < 60      # interpolated
    assert g.percent_passing_at(100.0) is None      # outside range
    assert g.d_size(60) == 2.0                       # exact percent
    assert g.d10 is not None and g.d30 is not None and g.d60 is not None
    assert g.coefficient_of_uniformity is not None
    assert g.coefficient_of_curvature is not None
    # percent outside the curve → None
    assert g.d_size(0.0) is None

    # degenerate curves with duplicate keys exercise the equal-key branches
    dup_size = GradingResult(5.0, (GradingPoint(2.0, 80), GradingPoint(2.0, 40)))
    assert dup_size.percent_passing_at(2.0) in (80, 40)
    dup_pct = GradingResult(5.0, (GradingPoint(4.0, 50), GradingPoint(1.0, 50)))
    assert dup_pct.d_size(50) in (4.0, 1.0)

    # single-point curve queried at its exact key falls through to the
    # no-bracket return (empty consecutive-pair loop)
    one_pt = GradingResult(5.0, (GradingPoint(2.0, 50),))
    assert one_pt.percent_passing_at(2.0) is None
    assert one_pt.d_size(50) is None


def test_sample_recovery_and_borehole_lookups():
    s = Sample(depth_top_ft=5.0, depth_bottom_ft=7.0)   # no recovery recorded
    assert s.recovery_percent is None
    bh = Borehole(boring_id="B1")                        # no ground elevation/data
    assert bh.elevation_at(5.0) is None
    assert bh.n_at(5.0) is None
    assert bh.d50_at(5.0) is None                        # no gradation present


# ── geotech/boring_io.py — DIGGS parser helpers and edge cases ────────────────

import xml.etree.ElementTree as ET
from civilpy.geotech import boring_io as bio


def _el(xml):
    return ET.fromstring(xml)


def test_boring_io_text_and_float_helpers():
    el = _el("<r><a>  12.5 m </a><b></b><c>not-a-number</c></r>")
    assert bio._text(el, "a") == "12.5 m"
    assert bio._text(el, "b") is None          # empty text
    assert bio._text(el, "missing") is None    # absent element
    assert bio._float("12.5 m") == 12.5        # takes first token
    assert bio._float(None) is None
    assert bio._float("   ") is None           # IndexError path
    assert bio._float("abc") is None           # ValueError path


def test_boring_io_ref_and_id_helpers():
    el = _el('<r xmlns:x="u"><ref x:href="#B-001}"/><noref/><thing x:id="G7"/></r>')
    assert bio._ref_id(el, "ref") == "B-001"   # strips # and stray brace
    assert bio._ref_id(el, "noref") is None    # child present, no href
    assert bio._ref_id(el, "absent") is None   # child absent
    assert bio._gml_id(_el('<x id="abc"/>')) == "abc"
    assert bio._gml_id(_el("<x/>")) is None
    assert bio._first(_el("<r><a/></r>"), "z") is None


def test_boring_io_poslist_helper():
    assert bio._poslist_floats(_el("<r><pos>1 2 3</pos></r>")) == [1.0, 2.0, 3.0]
    assert bio._poslist_floats(_el("<r><other/></r>")) == []


def test_load_root_from_bytes_and_path(tmp_path):
    xml = b'<Diggs xmlns="http://diggsml.org/schemas/2.5.a"></Diggs>'
    assert bio._load_root(xml).tag.endswith("Diggs")          # bytes branch
    p = tmp_path / "d.xml"
    p.write_bytes(xml)
    assert bio._load_root(str(p)).tag.endswith("Diggs")       # path branch
    with open(p, "rb") as fh:
        assert bio._load_root(fh).tag.endswith("Diggs")       # file-object branch


def test_parse_borehole_full_and_partial():
    full = _el(
        "<Borehole id='B-1'>"
        "<name>B-1</name>"
        "<referencePoint><pos>-83.0 40.0 800.0</pos></referencePoint>"
        "<station>12+34</station><offset>5 ft</offset><offsetDirection>RT</offsetDirection>"
        "<totalMeasuredDepth>50 ft</totalMeasuredDepth><boreholePurpose>design</boreholePurpose>"
        "<whenConstructed><start>2020-01-01</start></whenConstructed>"
        "<waterStrike><waterLocation><pos>10.5</pos></waterLocation></waterStrike>"
        "</Borehole>")
    bh = bio._parse_borehole(full, project="P")
    assert bh.boring_id == "B-1" and bh.latitude == 40.0 and bh.ground_elevation_ft == 800.0
    assert bh.station == "12+34" and bh.offset_ft == 5.0 and bh.total_depth_ft == 50.0
    assert bh.date == "2020-01-01" and bh.water_strike_depth_ft == 10.5

    # 2-coord reference point, name falls back to gml id, no optional blocks
    partial = _el("<Borehole id='B-2'><referencePoint><pos>-83.1 40.1</pos>"
                  "</referencePoint></Borehole>")
    bh2 = bio._parse_borehole(partial, project=None)
    assert bh2.boring_id == "B-2" and bh2.longitude == -83.1 and bh2.ground_elevation_ft is None


def test_depth_from_test_location_and_gml_fallback():
    with_loc = _el("<Test><location><pos>1.5 2.0</pos></location></Test>")
    assert bio._depth_from_test(with_loc) == 1.5
    by_id = _el("<Test id='SPT_B-1_3.5'/>")        # numeric suffix of gml:id
    assert bio._depth_from_test(by_id) == 3.5


def test_parse_spt_variants():
    good = _el("<Test id='SPT_B_2.0'>"
               "<DrivenPenetrationTest><hammerType>auto</hammerType>"
               "<hammerEfficiency>0.8</hammerEfficiency></DrivenPenetrationTest>"
               "<DriveSet><blowCount>5</blowCount><penetration>6</penetration></DriveSet>"
               "<DriveSet><blowCount>7</blowCount></DriveSet>"
               "<DriveSet><penetration>6</penetration></DriveSet>"  # no blowCount → skipped
               "</Test>")
    spt = bio._parse_spt(good)
    assert spt is not None and len(spt.increments) == 2 and spt.hammer_type == "auto"
    assert bio._parse_spt(_el("<Test/>")) is None                  # no depth
    assert bio._parse_spt(_el("<Test id='SPT_B_2.0'/>")) is None   # depth but no increments


def test_parse_grading_variants():
    good = _el("<Test id='PSD_B_4.0'>"
               "<Grading><particleSize>2.0</particleSize><percentPassing>60</percentPassing></Grading>"
               "<Grading><particleSize>0.075</particleSize></Grading>"  # missing pct → skipped
               "</Test>")
    g = bio._parse_grading(good)
    assert g is not None and len(g.points) == 1
    assert bio._parse_grading(_el("<Test/>")) is None              # no depth
    assert bio._parse_grading(_el("<Test id='PSD_B_4.0'/>")) is None  # depth but no points


def test_parse_sample_variants():
    two = _el("<SamplingActivity><samplingLocation><pos>5.0 7.0</pos></samplingLocation>"
              "<samplingMethod><name>SS</name></samplingMethod>"
              "<totalSampleRecoveryLength>18</totalSampleRecoveryLength></SamplingActivity>")
    s = bio._parse_sample(two)
    assert s.depth_top_ft == 5.0 and s.depth_bottom_ft == 7.0 and s.method == "SS"
    one = _el("<SamplingActivity><samplingLocation><pos>9.0</pos></samplingLocation></SamplingActivity>")
    s1 = bio._parse_sample(one)
    assert s1.depth_top_ft == s1.depth_bottom_ft == 9.0
    assert bio._parse_sample(_el("<SamplingActivity/>")) is None   # no location


def test_parse_diggs_ignores_orphan_tests():
    # a Test whose samplingFeatureRef matches no Borehole is skipped
    doc = (
        '<Diggs xmlns="http://diggsml.org/schemas/2.5.a" '
        'xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<Test><samplingFeatureRef xlink:href="#nope"/><DriveSet/></Test>'
        '</Diggs>'
    )
    assert bio.parse_diggs(doc) == []


def test_parse_diggs_full_document_links_records():
    doc = (
        '<Diggs xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<Project><name>Demo Project</name></Project>'
        '<Borehole id="B-1"><name>B-1</name>'
        '<referencePoint><pos>-83 40 800</pos></referencePoint></Borehole>'
        # SPT attached via a prefixed ref that only resolves after trimming
        '<Test id="SPT_x_2.0"><samplingFeatureRef xlink:href="#Borehole_B-1"/>'
        '<DriveSet><blowCount>5</blowCount></DriveSet>'
        '<DriveSet><blowCount>7</blowCount></DriveSet></Test>'
        # grading attached via the PARTICLE name path
        '<Test id="PSD_x_4.0"><samplingFeatureRef xlink:href="#B-1"/>'
        '<name>PARTICLE SIZE</name>'
        '<Grading><particleSize>2.0</particleSize><percentPassing>60</percentPassing></Grading>'
        '</Test>'
        '<SamplingActivity><samplingFeatureRef xlink:href="#B-1"/>'
        '<samplingLocation><pos>5 7</pos></samplingLocation></SamplingActivity>'
        '</Diggs>'
    )
    holes = bio.parse_diggs(doc)
    assert len(holes) == 1
    bh = holes[0]
    assert bh.project == "Demo Project"
    assert len(bh.spt) == 1 and bh.spt[0].n_value == 12
    assert len(bh.grading) == 1
    assert len(bh.samples) == 1 and bh.samples[0].depth_bottom_ft == 7.0


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
