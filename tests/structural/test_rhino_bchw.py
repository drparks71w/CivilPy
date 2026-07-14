#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the BCHW box culvert headwall / wingwall BrIM emit."""

import math

import pytest

from civilpy.structural.odot.box_culvert_headwall import WingwallInput
from civilpy.structural.rhino_bchw import bchw_emit
from civilpy.structural.rhino_bim import pay_item_quantities


@pytest.fixture(scope="module")
def inp() -> WingwallInput:
    return WingwallInput(length_ft=14.0, skew_deg=15.0, wall_height_ft=8.0,
                         foreslope_height_ft=5.0, cutoff_wall_height_ft=2.5,
                         footing_width_ft=6.0, box_wall_thickness_in=10.0)


@pytest.fixture(scope="module")
def emit(inp):
    return bchw_emit(inp, foreslope_run_ft=8.0)


def test_component_inventory(emit):
    by_type = {}
    for o in emit.objects:
        t = o.tags.get("bim.type")
        by_type[t] = by_type.get(t, 0) + 1
    assert by_type["wingwall"] == 1
    assert by_type["foreslope_wall"] == 1
    assert by_type["cutoff_wall"] == 1
    assert by_type["footing"] == 2            # L-shape: two legs
    assert by_type["bridge"] == 1             # the document marker
    assert by_type["rebar"] > 50

    layers = {o.layer for o in emit.objects}
    assert layers == {"Culvert::Wingwalls", "Culvert::Foreslope Walls",
                      "Culvert::Footings", "Culvert::Rebar"}


def test_every_object_carries_identity_and_scd(emit):
    for o in emit.objects:
        assert o.tags.get("bim.id"), o.tags
        assert o.tags.get("bim.scd") == "BCHW"


def test_concrete_rolls_into_qc1_item(emit, inp):
    q = pay_item_quantities(emit)
    t = inp.box_wall_thickness_in / 12.0
    expect = (14.0 * (8.0 + 5.0) / 2.0 * t     # tapered wingwall
              + 8.0 * 5.0 * t                  # foreslope stem
              + 8.0 * 2.5 * t                  # cutoff wall
              + (14.0 + 8.0) * 6.0 * 1.5       # L-shaped footing
              ) / 27.0
    assert q["511E40000"]["unit"] == "cy"
    # pay.qty stamps round to tag precision, hence the loose tolerance
    assert q["511E40000"]["qty"] == pytest.approx(expect, rel=1e-3)


def test_rebar_weighted_into_epoxy_item(emit):
    q = pay_item_quantities(emit)
    assert q["509E00200"]["unit"] == "lb"
    assert q["509E00200"]["qty"] > 100.0
    bars = [o for o in emit.objects if o.tags.get("bim.type") == "rebar"]
    assert {b.tags["rebar.size"] for b in bars} == {"#5", "#6"}
    for b in bars:
        assert float(b.tags["rebar.length_ft"]) > 0.0


def test_wingwall_verticals_follow_taper(emit):
    vs = [o for o in emit.objects
          if o.tags.get("bim.id", "").startswith("BCHW-WW-F1-V")]
    heights = [o.points[1][2] - o.points[0][2] for o in vs]
    assert heights == sorted(heights, reverse=True)   # H tapers down to hf
    assert heights[0] > heights[-1]


def test_skew_shears_far_end(emit, inp):
    ww = next(o for o in emit.objects if o.tags["bim.id"] == "BCHW-WW")
    far = max(ww.points, key=lambda p: p[1])
    assert far[0] == pytest.approx(
        far[1] * math.tan(math.radians(inp.skew_deg)))


def test_rebar_toggle(inp):
    bare = bchw_emit(inp, foreslope_run_ft=8.0, rebar=False)
    assert all(o.kind != "polyline" for o in bare.objects)
    assert len(bare.objects) == 6                     # marker + 5 solids


def test_solids_only_guards(inp):
    with pytest.raises(ValueError, match="foreslope_run_ft"):
        bchw_emit(inp, foreslope_run_ft=0.0)
    with pytest.raises(ValueError, match="footing_thickness_ft"):
        bchw_emit(inp, foreslope_run_ft=8.0, footing_thickness_ft=-1.0)


def test_emit_to_3dm_round_trip(tmp_path, emit):
    pytest.importorskip("rhino3dm")
    from civilpy.structural.rhino_bim import emit_to_3dm, read_bim_quantities

    path = tmp_path / "bchw.3dm"
    counts = emit_to_3dm(emit, path)
    assert sum(counts.values()) == len(emit.objects)
    q_file = read_bim_quantities(path)
    q_emit = pay_item_quantities(emit)
    for item, rec in q_emit.items():
        assert q_file[item]["qty"] == pytest.approx(rec["qty"])
