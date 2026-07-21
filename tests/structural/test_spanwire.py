#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Span-wire sag-tension solver and ODOT hardware catalog.

Solver cases are pinned to closed-form cable statics (the cable-beam
analogy): for a level span, H = M_max / sag.  These same cases are the
skeleton for golden-file comparison runs against the legacy SWISS
executable.
"""

import pytest

from civilpy.structural import spanwire
from civilpy.structural.spanwire import SimpleSpan, SpanLoad


# ── solver: closed-form statics cases ────────────────────────────────────────


def test_midspan_point_load():
    # W = 100 lb at midspan of 100 ft, level, weightless wire, 5-ft sag:
    # M_max = WL/4 = 2500 lb-ft -> H = 500 lb; reactions split evenly.
    span = SimpleSpan(100.0, loads=[SpanLoad(50.0, 100.0)])
    sol = span.solve(5.0)
    assert sol.horizontal_tension_lb == pytest.approx(500.0, rel=1e-6)
    assert sol.sag_ft == pytest.approx(5.0, abs=1e-6)
    assert sol.start_reaction_lb == pytest.approx(50.0)
    assert sol.end_reaction_lb == pytest.approx(50.0)
    assert sol.low_point_x_ft == pytest.approx(50.0)
    assert sol.low_point_elevation_ft == pytest.approx(-5.0)


def test_uniform_wire_weight_only():
    # w = 1 plf over 100 ft, 5-ft sag: H = wL^2/8 / D = 250 lb.
    span = SimpleSpan(100.0, wire_weight_plf=1.0)
    sol = span.solve(5.0)
    assert sol.horizontal_tension_lb == pytest.approx(250.0, rel=1e-6)
    assert sol.low_point_x_ft == pytest.approx(50.0, abs=1e-6)
    assert sol.start_reaction_lb == pytest.approx(50.0)
    assert sol.end_reaction_lb == pytest.approx(50.0)


def test_asymmetric_point_load():
    # W = 100 lb at x = 25 ft of 100 ft, level: M(25) = 75*25 = 1875 lb-ft
    # -> H = 375 lb; beam reactions 75/25; kink is the low point.
    span = SimpleSpan(100.0, loads=[SpanLoad(25.0, 100.0)])
    sol = span.solve(5.0)
    assert sol.horizontal_tension_lb == pytest.approx(375.0, rel=1e-6)
    assert sol.start_reaction_lb == pytest.approx(75.0)
    assert sol.end_reaction_lb == pytest.approx(25.0)
    assert sol.low_point_x_ft == pytest.approx(25.0)
    # reactions always sum to the total load
    assert sol.start_reaction_lb + sol.end_reaction_lb == pytest.approx(span.total_load_lb)


def test_elevation_difference():
    # End 4 ft below start, W = 100 lb at midspan: y(50) = -2 - 2500/H,
    # sag = 0 - y(50) = 5 -> H = 2500/3.
    span = SimpleSpan(100.0, end_elevation_ft=-4.0, loads=[SpanLoad(50.0, 100.0)])
    sol = span.solve(5.0)
    assert sol.horizontal_tension_lb == pytest.approx(2500.0 / 3.0, rel=1e-6)
    # the chord-slope correction shifts vertical reactions toward the high end
    assert sol.start_reaction_lb == pytest.approx(50.0 + sol.horizontal_tension_lb * 0.04)
    assert sol.start_reaction_lb + sol.end_reaction_lb == pytest.approx(100.0)


def test_combined_loads_and_wire_weight_consistency():
    # No closed form needed: the solved tension must reproduce the target
    # sag through the independent evaluator, and statics must balance.
    span = SimpleSpan(
        120.0,
        wire_weight_plf=1.0,
        end_elevation_ft=2.0,
        loads=[SpanLoad(30.0, 55.0, area_sqft=1.6), SpanLoad(70.0, 90.0, area_sqft=2.3)],
    )
    sol = span.solve(4.5)
    assert span.system_sag(sol.horizontal_tension_lb) == pytest.approx(4.5, abs=1e-6)
    assert sol.start_reaction_lb + sol.end_reaction_lb == pytest.approx(span.total_load_lb)
    assert 0.0 < sol.low_point_x_ft < 120.0
    # wire hangs at or below the chord everywhere
    for x in range(0, 121, 10):
        chord = span.start_elevation_ft + (2.0 / 120.0) * x
        assert span.wire_elevation(x, sol.horizontal_tension_lb) <= chord + 1e-9


def test_light_load_brackets_downward():
    # A load light enough that the initial tension guess over-sags forces
    # the bracket to walk H downward instead of up: W = 0.5 lb at midspan
    # of 10 ft, sag 3 ft -> H = M/D = 1.25/3.
    span = SimpleSpan(10.0, loads=[SpanLoad(5.0, 0.5)])
    sol = span.solve(3.0)
    assert sol.horizontal_tension_lb == pytest.approx(1.25 / 3.0, rel=1e-6)


def test_attachment_elevations_from_clearance():
    span = SimpleSpan(100.0, loads=[SpanLoad(50.0, 100.0)])
    sol = span.solve(5.0)
    start, end = span.attachment_elevations(sol, clearance_ft=21.0, pavement_elevation_ft=0.0)
    # low point sits exactly at the clearance; level span -> both ends equal
    assert start == pytest.approx(26.0)
    assert end == pytest.approx(26.0)


def test_input_validation():
    with pytest.raises(ValueError, match="positive"):
        SimpleSpan(0.0)
    with pytest.raises(ValueError, match="negative"):
        SimpleSpan(100.0, wire_weight_plf=-1.0)
    with pytest.raises(ValueError, match="outside"):
        SimpleSpan(100.0, loads=[SpanLoad(150.0, 10.0)])
    with pytest.raises(ValueError, match="cannot be negative"):
        SimpleSpan(100.0, loads=[SpanLoad(50.0, -10.0)])
    # required sag must exceed the attachment elevation difference
    with pytest.raises(ValueError, match="elevation difference"):
        SimpleSpan(100.0, end_elevation_ft=-6.0, loads=[SpanLoad(50.0, 100.0)]).solve(5.0)
    # a span with nothing on it has no defined sag
    with pytest.raises(ValueError, match="no load"):
        SimpleSpan(100.0).solve(5.0)


# ── legacy SWISS parity helpers ──────────────────────────────────────────────


def test_swiss_design_factor():
    # SWISS manual formula: sqrt(DL^2 + (A*q)^2)/DL * 1.1 at 42 psf.
    # 617 lb / 17.7 sq ft are the manual's worked-example inputs.
    factor = spanwire.swiss_design_factor(617.0, 17.7)
    assert factor == pytest.approx(1.722, abs=1e-3)
    # no attachments -> pure 10% amplification
    assert spanwire.swiss_design_factor(500.0, 0.0) == pytest.approx(1.1)
    with pytest.raises(ValueError, match="positive"):
        spanwire.swiss_design_factor(0.0, 10.0)


def test_pole_base_moment():
    # manual definition: stringing tension x attachment height x factor
    assert spanwire.pole_base_moment(1267.0, 32.73, 1.8) == pytest.approx(74649.0, rel=1e-3)
    assert spanwire.pole_base_moment(1000.0, 30.0) == 30000.0


# ── ODOT catalog ─────────────────────────────────────────────────────────────


def test_load_codelist_default():
    catalog = spanwire.load_codelist()
    # spot values straight from ODOT's CodeList.xml
    three_ba = catalog.signals["3BA"]
    assert three_ba.weight_lb == 55.0
    assert three_ba.height_ft == 4.2
    assert three_ba.area_sqft == 1.6
    assert three_ba.sections == 3
    assert three_ba.lens_size_in == 12
    assert three_ba.material == "Aluminum"
    # backplated variant is heavier with more area
    assert catalog.signals["3BABP"].weight_lb == 70.3
    assert catalog.signals["3BABP"].area_sqft == 4.1

    assert catalog.wires["WM3"].weight_plf == 0.28
    assert catalog.wires["WM3"].category == "MESSENGER"
    assert catalog.signs["AL1"].weight_psf == 1.2
    assert catalog.signs["AL1"].hanger_lb == 10.0

    assert len(catalog.signals) >= 30
    assert len(catalog.signs) == 3
    assert len(catalog.wires) == 17


def test_load_codelist_missing_field(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("<XML><SIGNAL_LIST><SIGNAL><CODE>X</CODE></SIGNAL></SIGNAL_LIST></XML>")
    with pytest.raises(ValueError, match="missing"):
        spanwire.load_codelist(bad)


def test_load_codelist_cp1252_fallback(tmp_path):
    # declares utf-8 but contains a cp1252 em dash, like the legacy file can
    legacy = tmp_path / "legacy.xml"
    content = (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
        "<XML>legacy — comment<WIRE_LIST><WIRE><CODE>WM1</CODE>"
        "<CATEGORY>MESSENGER</CATEGORY><SECTION>1/4”</SECTION>"
        "<WEIGHT>0.12</WEIGHT></WIRE></WIRE_LIST></XML>"
    )
    legacy.write_bytes(content.encode("cp1252"))
    catalog = spanwire.load_codelist(legacy)
    assert catalog.wires["WM1"].weight_plf == 0.12
