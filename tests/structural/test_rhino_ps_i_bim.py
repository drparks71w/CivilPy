#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the prestressed I-beam BrIM emit layer (PSID-1-13)."""

import json

import pytest

from civilpy.structural.odot.ps_i_beam import (
    i_beam_diaphragm_stations_ft,
    ps_i_beam_section,
)
from civilpy.structural.ps_i_beam_pipeline import ps_i_beam_line_checks
from civilpy.structural.rhino_bim import emit_to_json, pay_item_quantities
from civilpy.structural.rhino_ps_i_bim import (
    PSIBridgeInput,
    ps_i_bridge_emit,
)

INP = PSIBridgeInput("WF48-49", 95.0, 5, spacing_ft=9.0, overhang_ft=2.5,
                     fci_ksi=5.0, fc_ksi=7.0, barrier_klf=0.9)


@pytest.fixture(scope="module")
def checks():
    return ps_i_beam_line_checks(
        "WF48-49", 95.0, 5, spacing_ft=9.0, fci_ksi=5.0, fc_ksi=7.0,
        barrier_klf=0.9)


@pytest.fixture(scope="module")
def emit(checks):
    return ps_i_bridge_emit(INP, checks=checks)


def test_component_inventory(emit, checks):
    n_sta = len(i_beam_diaphragm_stations_ft(95.0))
    n_rows = len({z for _, z in checks.design.pattern})
    by_type = {t: len(emit.of_type(t)) for t in (
        "bridge", "ps_i_beam", "tendon", "bearing", "diaphragm",
        "haunch", "deck")}
    assert by_type["bridge"] == 1
    assert by_type["ps_i_beam"] == 5             # one prism per beam
    assert by_type["tendon"] == 5 * n_rows
    assert by_type["bearing"] == 10
    assert by_type["diaphragm"] == n_sta * 4     # stations x bays
    assert by_type["haunch"] == 5
    assert by_type["deck"] == 1
    ids = [o.tags["bim.id"] for o in emit.objects if "bim.type" in o.tags]
    assert len(ids) == len(set(ids))


def test_gdr_contract(emit):
    lines = [o for o in emit.objects if o.tags.get("gdr.kind") == "girder"]
    assert len(lines) == 5
    for o in lines:
        assert o.tags["gdr.family"] == "ps_i"
        assert o.tags["gdr.section"] == "WF48-49"
        assert o.points[0][2] == pytest.approx(48.0 / 12.0)  # top of beam
    # beam 1 centerline sits one overhang in from the deck edge
    assert lines[0].points[0][1] == pytest.approx(2.5)
    assert emit.doc_tags["gdr.family"] == "ps_i"


def test_beam_prism_true_profile(emit):
    sec = ps_i_beam_section("WF48-49")
    beam1 = next(o for o in emit.of_type("ps_i_beam")
                 if o.tags["bim.id"] == "PSI1")
    ys = [p[1] for p in beam1.points]
    zs = [p[2] for p in beam1.points]
    assert max(zs) - min(zs) == pytest.approx(sec.depth_in / 12.0)
    # widest at the top flange (49 in), centered on the beam line
    assert max(ys) - min(ys) == pytest.approx(49.0 / 12.0)
    assert (max(ys) + min(ys)) / 2.0 == pytest.approx(2.5)
    assert beam1.vector == (95.0, 0.0, 0.0)
    assert beam1.tags["ps_i_beam.section"] == "WF48-49"
    assert beam1.tags["bim.scd"] == "PSID-1-13"


def test_strand_rows_follow_designed_pattern(emit, checks):
    design = checks.design
    rows = [o for o in emit.of_type("tendon")
            if o.tags["bim.id"].startswith("PSI1-")]
    by_row = {float(o.tags["tendon.row_in"]): int(o.tags["tendon.strands"])
              for o in rows}
    assert sum(by_row.values()) == design.n_strands
    # rows reconcile with the pattern's own z histogram
    for z in by_row:
        assert by_row[z] == sum(1 for _, zz in design.pattern if zz == z)
    # the designed debonds ride on the rows
    total_db = sum(int(o.tags.get("tendon.debonded", 0)) for o in rows)
    assert total_db == design.n_debonded
    for o in rows:
        assert o.points[0][2] == pytest.approx(
            float(o.tags["tendon.row_in"]) / 12.0)


def test_member_pay_item_counts_each_beam_once(emit):
    q = pay_item_quantities(emit)
    members = q["515E20000"]
    assert members["unit"] == "ea" and members["qty"] == 5
    assert q["516E10000"]["qty"] == 10           # pads
    assert q["515E30000"]["qty"] == 12           # 3 stations x 4 bays
    sec = ps_i_beam_section("WF48-49")
    beam1 = next(o for o in emit.of_type("ps_i_beam")
                 if o.tags["bim.id"] == "PSI1")
    assert float(beam1.tags["ps_i_beam.concrete_cy"]) == pytest.approx(
        sec.area_in2 / 144.0 * 95.0 / 27.0, rel=1e-4)
    # deck + haunches roll into the one superstructure concrete item
    deck_cy = q["511E12100"]["qty"]
    assert deck_cy > 95.0 * 41.0 * (8.5 / 12.0) / 27.0  # slab + haunches


def test_haunch_and_deck_geometry(emit):
    h = next(o for o in emit.of_type("haunch"))
    assert float(h.tags["haunch.depth_in"]) == 2.0
    assert float(h.tags["haunch.width_in"]) == 49.0
    deck = next(o for o in emit.of_type("deck"))
    z0 = min(p[2] for p in deck.points)
    assert z0 == pytest.approx((48.0 + 2.0) / 12.0)  # beam top + haunch
    ys = [p[1] for p in deck.points]
    assert max(ys) - min(ys) == pytest.approx(4 * 9.0 + 2 * 2.5)


def test_emit_designs_when_no_checks_given():
    e = ps_i_bridge_emit(PSIBridgeInput(
        "AASHTO Type 3", 60.0, 5, spacing_ft=7.5))
    beam = next(o for o in e.of_type("ps_i_beam"))
    assert int(beam.tags["ps_i_beam.n_strands"]) > 0
    assert e.doc_tags["bim.family"] == "ps_i"


def test_skew_not_supported():
    with pytest.raises(ValueError, match="skew"):
        ps_i_bridge_emit(PSIBridgeInput(
            "WF48-49", 95.0, 5, spacing_ft=9.0, skew_deg=15.0))


def test_emit_json_round_trip(emit):
    data = json.loads(emit_to_json(emit))
    assert len(data["objects"]) == len(emit.objects)
    assert data["doc_tags"]["bim.family"] == "ps_i"
    assert "Superstructure::Girders" in data["layers"]
