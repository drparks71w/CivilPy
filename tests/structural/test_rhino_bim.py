#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the steel-girder BrIM emit layer."""

import json
import math

import pytest

from civilpy.structural.bridge_layout import BridgeInput
from civilpy.structural.rhino_bim import (
    BridgeEmit,
    emit_to_json,
    girder_bridge_emit,
    i_profile_wh,
    pay_item_quantities,
)


@pytest.fixture(scope="module")
def emit() -> BridgeEmit:
    return girder_bridge_emit(BridgeInput(
        spans_ft=(70.0, 90.0, 70.0),
        girder_count=5,
        girder_spacing_ft=8.0,
        girder_label="W36X150",
        overhang_ft=3.0,
        railing="SBR-1-20",
        grade="Grade 50W",
    ))


def test_component_inventory(emit):
    by_type = {t: len(emit.of_type(t)) for t in (
        "bridge", "deck", "girder", "haunch", "shear_stud", "rebar",
        "parapet", "bearing", "load_plate")}
    assert by_type["bridge"] == 1
    assert by_type["deck"] == 1
    assert by_type["girder"] == 5
    assert by_type["haunch"] == 5
    assert by_type["parapet"] == 2
    assert by_type["bearing"] == 20      # 4 stations x 5 lines
    assert by_type["load_plate"] == 20
    # composite by default -> studs: 5 girders x 115 rows (2 ft pitch) x 3
    assert by_type["shear_stud"] == 5 * 115 * 3
    assert by_type["rebar"] > 1000


def test_every_object_carries_bim_identity(emit):
    for o in emit.objects:
        if "bim.type" in o.tags:
            assert o.tags.get("bim.id"), o.tags
    ids = [o.tags["bim.id"] for o in emit.objects if "bim.type" in o.tags]
    assert len(ids) == len(set(ids)), "bim.id values must be unique"


def test_gdr_contract_preserved(emit):
    lines = [o for o in emit.objects if o.tags.get("gdr.kind") == "girder"]
    supports = [o for o in emit.objects
                if o.tags.get("gdr.kind") == "support"]
    assert len(lines) == 5 and len(supports) == 20
    for o in lines:
        assert o.kind == "polyline"
        assert o.tags["gdr.shape"] == "W36X150"
    assert emit.doc_tags["gdr.deck_t"] == "7.5"


def test_non_composite_drops_studs():
    e = girder_bridge_emit(BridgeInput(
        spans_ft=(70.0,), girder_count=5, girder_spacing_ft=8.0,
        girder_label="W36X150", overhang_ft=3.0, composite=False))
    assert not e.of_type("shear_stud")
    assert e.doc_tags["bim.composite"] == "false"


def test_studs_bear_on_flange(emit):
    layout = emit.layout
    tops = {g.start[1]: g.start[2] for g in layout.girders}
    for o in emit.of_type("shear_stud")[:50]:
        base, tip = o.points
        y_girder = min(tops, key=lambda y: abs(y - base[1]))
        assert base[2] == pytest.approx(tops[y_girder])
        assert tip[2] - base[2] == pytest.approx(0.5)      # 6 in stud
        # stays within the flange width
        assert abs(base[1] - y_girder) <= layout.section.flange_width / 24.0


def test_haunch_meets_soffit_and_flange(emit):
    layout = emit.layout
    for o in emit.of_type("haunch"):
        zs = {round(p[2], 6) for p in o.points}
        assert len(zs) == 2
        z_bot, z_top = min(zs), max(zs)
        y = o.points[0][1] + layout.section.flange_width / 24.0  # girder CL
        assert z_top == pytest.approx(layout.deck_soffit_z(y))
        assert z_top - z_bot == pytest.approx(2.0 / 12.0, abs=1e-5)


def test_girder_profile_has_fillets():
    from civilpy.structural.bridge_layout import girder_section

    sec = girder_section("W36X150")
    wh = i_profile_wh(sec)
    assert len(wh) > 16                       # fillet tessellation present
    ws = [w for w, _ in wh]
    hs = [h for _, h in wh]
    assert max(ws) == pytest.approx(sec.flange_width / 2.0)
    assert min(ws) == pytest.approx(-sec.flange_width / 2.0)
    assert min(hs) == 0.0 and max(hs) == pytest.approx(sec.depth)


def test_bearing_stack(emit):
    layout = emit.layout
    z_flange = layout.bearings[0].location[2]
    pads = emit.of_type("bearing")
    plates = emit.of_type("load_plate")
    plate = next(p for p in plates
                 if p.tags["bim.id"] == "BRG-G1-S0-LP")
    pad = next(p for p in pads if p.tags["bim.id"] == "BRG-G1-S0")
    # plate directly under the bottom flange, pad under the plate
    assert plate.points[0][2] == pytest.approx(z_flange - 1.5 / 12.0)
    assert plate.vector[2] == pytest.approx(1.5 / 12.0)
    assert pad.points[0][2] == pytest.approx(
        z_flange - 1.5 / 12.0 - 3.0 / 12.0)
    assert pad.tags["bearing.total_thickness_in"] == "3"


def test_rebar_tags_and_crank(emit):
    bars = emit.of_type("rebar")
    cranked = [b for b in bars if b.tags["rebar.bend"] == "crown-crank"]
    assert cranked, "transverse bars crossing the crown must crank"
    for b in cranked[:5]:
        assert len(b.points) == 3
    b = bars[0]
    assert b.tags["rebar.coating"] == "epoxy"
    assert b.tags["pay.item"] == "509E00200"
    assert float(b.tags["rebar.length_ft"]) > 0


def test_parapet_single_slope_profile(emit):
    par = next(p for p in emit.of_type("parapet")
               if p.tags["bim.id"] == "PAR-right")
    dys = [p[1] - par.points[0][1] for p in par.points]
    # SBR-1-20: 18 in base, 10 in top (from the 588 in^2 section), 42 in tall
    assert max(dys) == pytest.approx(18.0 / 12.0)
    assert dys[2] == pytest.approx(10.0 / 12.0)
    zs = [p[2] - par.points[0][2] for p in par.points]
    assert max(zs) == pytest.approx(42.0 / 12.0)
    assert par.tags["bim.scd"] == "SBR-1-20"
    # volume from the SCD's gross area, not a bounding box
    assert float(par.tags["pay.qty"]) == pytest.approx(
        588.0 / 144.0 * 230.0 / 27.0, rel=1e-3)


def test_sbr1_parapet_cage(emit):
    layout = emit.layout
    bars = [o for o in emit.objects if o.tags.get("rebar.mat") == "parapet"]
    y601 = [b for b in bars if b.tags["rebar.bend"] == "Y601"]
    y602 = [b for b in bars if b.tags["rebar.bend"] == "Y602"]
    gfrp = [b for b in bars if b.tags["rebar.coating"] == "GFRP"]
    # verticals at 12 in over 230 ft on both parapets; 12 GFRP runs each
    assert len(y601) == len(y602) == 2 * 230
    assert len(gfrp) == 2 * (2 * 5 + 2)
    for b in gfrp:
        assert b.tags["rebar.size"] == "#4"
        assert b.tags["pay.item"] == "509E00300"
        assert "pay.qty" not in b.tags          # producer-specific weight
    # Y602 embeds (overhang t) - 1.5 in below the barrier base: the SCD's
    # EMBEDMENT = X - 1.5 with X = 10.5 in -> exactly the 9 in minimum
    z_base = layout.barriers[0].line[0][2]
    b = next(b for b in y602 if "right" in b.tags["bim.id"])
    assert b.tags["rebar.size"] == "#6"
    assert min(p[2] for p in b.points) == pytest.approx(
        z_base - 9.0 / 12.0)
    assert max(p[2] for p in b.points) == pytest.approx(
        z_base + (42.0 - 2.0) / 12.0)
    # the horizontal deck-lap leg points toward traffic (+y on the right)
    assert b.points[0][1] > b.points[1][1]
    assert b.tags["pay.item"] == "509E00200"    # epoxy steel, weighted
    assert float(b.tags["pay.qty"]) > 0


def test_pay_item_rollup(emit):
    q = pay_item_quantities(emit)
    # structural steel: 5 girders x 230 ft x 150 plf + 20 load plates
    steel = q["513E10220"]
    assert steel["unit"] == "lb"
    assert steel["qty"] == pytest.approx(
        5 * 230.0 * 150.0 + 20 * (21 ** 2 * 1.5) / 1728.0 * 490.0, rel=1e-3)
    assert q["513E20000"]["qty"] == 5 * 115 * 3          # studs, ea
    assert q["516E10000"]["qty"] == 20                   # bearings, ea
    deck = q["511E12100"]
    assert deck["unit"] == "cy"
    # sanity: within 15% of the flat-slab estimate (crown + overhangs)
    flat_cy = 38.0 * (8.5 / 12.0) * 230.0 / 27.0
    assert deck["qty"] == pytest.approx(flat_cy, rel=0.15)
    rebar = q["509E00200"]
    assert rebar["unit"] == "lb" and rebar["qty"] > 10000


def test_emit_json_round_trip(emit):
    data = json.loads(emit_to_json(emit))
    assert data["doc_tags"]["bim.units"] == "ft"
    assert len(data["objects"]) == len(emit.objects)
    kinds = {o["kind"] for o in data["objects"]}
    assert kinds == {"prism", "polyline", "cylinder", "point"}


def test_skewed_deck_ends_follow_skew():
    e = girder_bridge_emit(BridgeInput(
        spans_ft=(80.0,), girder_count=4, girder_spacing_ft=9.0,
        girder_label="W36X150", overhang_ft=2.5, skew_deg=30.0))
    deck = e.of_type("deck")[0]
    tan30 = math.tan(math.radians(30.0))
    for x, y, _ in deck.points:
        assert x == pytest.approx(y * tan30)
    # girders stay square-cut but shifted
    g4 = next(o for o in e.of_type("girder")
              if o.tags["bim.id"] == "G4")
    assert g4.points[0][0] == pytest.approx(27.0 * tan30)
