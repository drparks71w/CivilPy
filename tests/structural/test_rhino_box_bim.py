#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the adjacent box-beam BrIM emit layer."""

import json

import pytest

from civilpy.structural.odot import (
    BOX_FLANGE_THICKNESS_IN,
    BOX_WEB_THICKNESS_IN,
    box_beam_design,
    box_section_properties,
    diaphragm_stations_ft,
)
from civilpy.structural.rhino_bim import emit_to_json, pay_item_quantities
from civilpy.structural.rhino_box_bim import (
    BoxBridgeInput,
    box_beam_bridge_emit,
)


@pytest.fixture(scope="module")
def emit():
    return box_beam_bridge_emit(BoxBridgeInput(
        box="CB27-48", span_ft=60.0, n_beams=9))


def test_component_inventory(emit):
    design = box_beam_design("CB27-48", 60)
    n_dia = len(diaphragm_stations_ft(60.0, design.depth))
    by_type = {t: len(emit.of_type(t)) for t in (
        "bridge", "box_beam", "tendon", "bearing", "diaphragm", "tie_rod",
        "deck")}
    assert by_type["bridge"] == 1
    assert by_type["box_beam"] == 9 * 4          # 4 wall prisms per beam
    # CB27-48 @ 60 ft: strands in the 2 in and 4 in rows only
    assert by_type["tendon"] == 9 * 2
    assert by_type["bearing"] == 18
    assert by_type["diaphragm"] == n_dia
    assert by_type["tie_rod"] == n_dia
    assert by_type["deck"] == 1                  # composite topping
    ids = [o.tags["bim.id"] for o in emit.objects if "bim.type" in o.tags]
    assert len(ids) == len(set(ids))


def test_gdr_contract(emit):
    lines = [o for o in emit.objects if o.tags.get("gdr.kind") == "girder"]
    assert len(lines) == 9
    for o in lines:
        assert o.tags["gdr.family"] == "box"
        assert o.tags["gdr.box"] == "CB27-48"
        assert o.points[0][2] == pytest.approx(27.0 / 12.0)  # top of box
    assert emit.doc_tags["gdr.family"] == "box"


def test_hollow_tube_geometry(emit):
    flange = BOX_FLANGE_THICKNESS_IN / 12.0
    web = BOX_WEB_THICKNESS_IN / 12.0
    beam1 = [o for o in emit.of_type("box_beam")
             if o.tags["bim.id"].startswith("BB1-")]
    parts = {o.tags["box_beam.part"]: o for o in beam1}
    assert set(parts) == {"top_flange", "bottom_flange", "left_web",
                          "right_web"}
    top = parts["top_flange"]
    assert min(p[2] for p in top.points) == pytest.approx(27.0 / 12.0 - flange)
    assert top.vector[2] == pytest.approx(flange)
    left = parts["left_web"]
    ys = [p[1] for p in left.points]
    assert max(ys) - min(ys) == pytest.approx(web)
    assert left.vector[2] == pytest.approx(27.0 / 12.0 - 2.0 * flange)


def test_strand_rows_follow_design(emit):
    design = box_beam_design("CB27-48", 60)
    rows = [o for o in emit.of_type("tendon")
            if o.tags["bim.id"].startswith("BB1-")]
    by_row = {float(o.tags["tendon.row_in"]): int(o.tags["tendon.strands"])
              for o in rows}
    assert by_row[2.0] == design.strands_2in
    assert by_row[4.0] == design.strands_4in
    assert sum(by_row.values()) == design.n_strands
    for o in rows:
        assert o.points[0][2] == pytest.approx(
            float(o.tags["tendon.row_in"]) / 12.0)


def test_member_pay_item_counts_each_beam_once(emit):
    q = pay_item_quantities(emit)
    members = q["515E10000"]
    assert members["unit"] == "ea" and members["qty"] == 9
    assert q["516E10000"]["qty"] == 18           # pads
    section = box_section_properties(27)
    top = next(o for o in emit.of_type("box_beam")
               if o.tags["bim.id"] == "BB1-TOP_FLANGE")
    assert float(top.tags["box_beam.concrete_cy"]) == pytest.approx(
        section.area / 144.0 * 60.0 / 27.0, rel=1e-4)
    # precast diaphragms and tie rods are included in the member
    for o in (*emit.of_type("diaphragm"), *emit.of_type("tie_rod")):
        assert "pay.item" not in o.tags


def test_composite_topping_vs_noncomposite():
    e = box_beam_bridge_emit(BoxBridgeInput(
        box="B27-48", span_ft=60.0, n_beams=9))
    assert not e.of_type("deck")
    assert e.doc_tags["bim.composite"] == "false"
    q = pay_item_quantities(e)
    assert "511E12100" not in q
    top = next(o for o in e.of_type("box_beam")
               if o.tags["box_beam.part"] == "top_flange")
    assert top.tags["box_beam.beam_type"] == "non_composite"


def test_invalid_span_names_valid_ones():
    with pytest.raises(KeyError, match="CB27-48"):
        box_beam_bridge_emit(BoxBridgeInput(
            box="CB27-48", span_ft=61.0, n_beams=9))


def test_skew_not_supported():
    with pytest.raises(ValueError, match="skew"):
        box_beam_bridge_emit(BoxBridgeInput(
            box="CB27-48", span_ft=60.0, n_beams=9, skew_deg=15.0))


def test_emit_json_round_trip(emit):
    data = json.loads(emit_to_json(emit))
    assert len(data["objects"]) == len(emit.objects)
    assert data["doc_tags"]["bim.family"] == "box"
    assert "Superstructure::Box Beams" in data["layers"]
