#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the AS-1-15 approach slab BrIM emit (rhino_approach_slab).

Covers the placement contract (near/far side, alignment + station +
offset), the layer taxonomy, and the pay-measurement split: ITEM 526
carries the plan area with the slab bars incidental, ITEM 509 carries
the anchor bars.
"""

import math

import pytest

from civilpy.structural.odot.approach_slab import (
    ApproachSlabInput,
    d_bar_count,
    layout_approach_slab,
)
from civilpy.structural.rhino_approach_slab import approach_slab_emit
from civilpy.structural.rhino_bim import pay_item_quantities
from civilpy.structural.rhino_layers import (
    LAYER_APPROACH_SLAB,
    LAYER_APPROACH_SLAB_REBAR,
)
from civilpy.transportation.alignment import Alignment, Tangent, VerticalProfile

INP = ApproachSlabInput(length_ft=25.0, width_ft=40.0)


def _slab(emit):
    return next(o for o in emit.objects
                if o.tags.get("bim.type") == "approach_slab")


def _bars(emit):
    return [o for o in emit.objects if o.tags.get("bim.type") == "rebar"]


# ── object inventory ─────────────────────────────────────────────────────

def test_emit_inventory_matches_layout():
    emit = approach_slab_emit(INP)
    layout = layout_approach_slab(INP)
    bars = _bars(emit)
    assert len(bars) == len(layout.bars)
    assert len(emit.objects) == len(layout.bars) + 2   # slab + outline
    assert _slab(emit).layer == LAYER_APPROACH_SLAB
    assert all(b.layer == LAYER_APPROACH_SLAB_REBAR for b in bars)


def test_slab_tags_carry_item_526_area():
    emit = approach_slab_emit(INP)
    tags = _slab(emit).tags
    assert tags["bim.scd"] == "AS-1-15"
    assert tags["pay.item"] == "526E10000"
    assert float(tags["pay.qty"]) == pytest.approx(25.0 * 40.0 / 9.0)
    assert tags["approach_slab.thickness_in"] == "15"


def test_slab_bars_have_diameters_but_no_pay_block():
    emit = approach_slab_emit(INP)
    for bar in _bars(emit):
        assert "rebar.dia_in" in bar.tags
        assert "rebar.weight_plf" in bar.tags
        assert "rebar.length_ft" in bar.tags
        if bar.tags["rebar.mark"].startswith("D8"):
            assert bar.tags["pay.item"] == "509E00200"
        else:
            assert not any(k.startswith("pay.") for k in bar.tags)


def test_pay_rollup_526_and_509():
    emit = approach_slab_emit(INP)
    layout = layout_approach_slab(INP)
    rollup = pay_item_quantities(emit)
    assert rollup["526E10000"]["qty"] == pytest.approx(
        layout.pay_area_sy, abs=0.01)
    n_d = d_bar_count(INP.width_ft)
    lbs = n_d * layout.anchor_length_ft * 2.670   # #8 @ 2.670 lb/ft
    assert rollup["509E00200"]["qty"] == pytest.approx(lbs, abs=0.1)
    assert rollup["509E00200"]["objects"] == n_d


# ── placement: side toggle ───────────────────────────────────────────────

def test_near_side_runs_down_station_far_up_station():
    """Default frame: bridge limit at the origin, stations along +Y."""
    near = _slab(approach_slab_emit(INP, side="near"))
    far = _slab(approach_slab_emit(INP, side="far"))
    assert max(p[1] for p in near.points) <= 1e-9
    assert min(p[1] for p in far.points) >= -1e-9
    # both are centered on the (default) centerline
    for obj in (near, far):
        xs = [p[0] for p in obj.points] \
            + [p[0] + obj.vector[0] for p in obj.points]
        assert min(xs) == pytest.approx(-INP.width_ft / 2.0)
        assert max(xs) == pytest.approx(INP.width_ft / 2.0)


def test_far_is_near_rotated_180():
    """The far slab is the near slab rotated 180 deg about the placement
    point — anchor bars stay at the bridge end, skew stays parallel."""
    inp = ApproachSlabInput(length_ft=25.0, width_ft=40.0, skew_deg=20.0)
    near = approach_slab_emit(inp, side="near")
    far = approach_slab_emit(inp, side="far")
    for a, b in zip(near.objects, far.objects):
        for pa, pb in zip(a.points, b.points):
            assert pa[0] == pytest.approx(-pb[0])
            assert pa[1] == pytest.approx(-pb[1])
            assert pa[2] == pytest.approx(pb[2])


def test_anchor_bars_at_bridge_limit_both_sides():
    for side in ("near", "far"):
        emit = approach_slab_emit(INP, side=side)
        anchors = [b for b in _bars(emit)
                   if b.tags["rebar.mark"].startswith("D8")]
        assert anchors
        for bar in anchors:
            # every anchor bar stays within a couple feet of the
            # bridge-limit line (station 0 here), whichever the side
            assert all(abs(p[1]) < 3.0 for p in bar.points)


def test_side_guard():
    with pytest.raises(ValueError, match="side"):
        approach_slab_emit(INP, side="left")


# ── placement: alignment + station + offset ──────────────────────────────

def test_alignment_placement_east_tangent():
    """Bridge limit at station 1100 on an eastbound tangent from the
    origin: the near slab runs back to station 1075, top of slab at the
    profile elevation, centered 6 ft right of the centerline."""
    al = Alignment((0.0, 0.0), 90.0, [Tangent(2000.0)],
                   profile=VerticalProfile([(1000.0, 500.0, 0.0),
                                            (3000.0, 520.0, 0.0)]),
                   start_station_ft=1000.0)
    emit = approach_slab_emit(INP, side="near", alignment=al,
                              station_ft=1100.0, offset_ft=6.0)
    outline = next(o for o in emit.objects
                   if o.tags["bim.id"] == "APS-OUTLINE")
    xs = [p[0] for p in outline.points]
    ys = [p[1] for p in outline.points]
    zs = [p[2] for p in outline.points]
    # eastbound: x is distance along stations; slab spans 75..100 ft
    assert min(xs) == pytest.approx(75.0)
    assert max(xs) == pytest.approx(100.0)
    # right of an eastbound tangent is -y; center offset 6 ft right
    assert (min(ys) + max(ys)) / 2.0 == pytest.approx(-6.0)
    assert max(ys) - min(ys) == pytest.approx(INP.width_ft)
    # top of slab at the station-1100 profile elevation (1% grade)
    assert all(z == pytest.approx(501.0) for z in zs)


def test_alignment_requires_station():
    al = Alignment((0.0, 0.0), 0.0, [Tangent(100.0)])
    with pytest.raises(ValueError, match="station"):
        approach_slab_emit(INP, alignment=al)


# ── doc tags ─────────────────────────────────────────────────────────────

def test_doc_tags_record_placement():
    emit = approach_slab_emit(INP, side="far")
    assert emit.doc_tags["bim.scd"] == "AS-1-15"
    assert emit.doc_tags["aps.side"] == "far"
    assert emit.side == "far"
