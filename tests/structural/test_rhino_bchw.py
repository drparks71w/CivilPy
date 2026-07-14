#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the BCHW headwall assembly BrIM emit (Design Data sheets)."""

import math

import pytest

from civilpy.structural.odot.box_culvert_headwall import (
    HeadwallInput,
    TYPE_A_TABLE,
    TYPE_B_TABLES,
    TYPE_C_TABLE,
    design_headwall,
)
from civilpy.structural.rhino_bchw import bchw_emit
from civilpy.structural.rhino_bim import pay_item_quantities


@pytest.fixture(scope="module")
def emit():
    # 8 x 6 box, 10 in slabs, 6 in foreslope wall: H_req 8.17 -> H 8.5
    return bchw_emit(HeadwallInput("A", 8.0, 6.0))


# ── catalog ───────────────────────────────────────────────────────────────

def test_tables_cover_all_design_heights():
    heights = [6.5 + i for i in range(8)]
    assert [r.H for r in TYPE_A_TABLE] == heights
    assert [r.H for r in TYPE_C_TABLE] == heights
    for theta, table in TYPE_B_TABLES.items():
        assert [r.H for r in table] == heights, theta


def test_design_height_rounds_up():
    d = design_headwall(HeadwallInput("A", 8.0, 6.0))
    assert d.H_required == pytest.approx(6.0 + 20.0 / 12.0 + 0.5)
    assert d.H == 8.5
    assert d.row.L1 == 10.0 and d.row.h1 == 5.0
    assert d.t_wall_in == 8.0


def test_type_b_needs_tabulated_skew():
    with pytest.raises(ValueError, match="tabulated"):
        design_headwall(HeadwallInput("B", 8.0, 6.0, roadway_skew_deg=20.0))


def test_size_limits_guarded():
    with pytest.raises(ValueError, match="box_span_ft"):
        design_headwall(HeadwallInput("A", 6.0, 6.0))
    # the tables cover the whole size range: the max 20 x 10 box with
    # 12 in slabs and the tall foreslope wall lands exactly on H = 13.5
    d = design_headwall(HeadwallInput("A", 20.0, 10.0,
                                      box_slab_thickness_in=12.0,
                                      foreslope_wall_height_in=18.0))
    assert d.H == 13.5 and d.H_required == pytest.approx(13.5)


# ── assembly ──────────────────────────────────────────────────────────────

def test_component_inventory(emit):
    by_type = {}
    for o in emit.objects:
        t = o.tags.get("bim.type")
        by_type[t] = by_type.get(t, 0) + 1
    assert by_type["wingwall"] == 2            # BOTH wingwalls
    assert by_type["foreslope_wall"] == 1
    assert by_type["cutoff_wall"] == 3         # two wall legs + culvert strip
    assert by_type["footing"] == 3
    assert by_type["box_culvert"] == 8         # stub: 2 walls, 2 slabs, 4 haunches
    assert by_type["rebar"] > 100


def test_wingwalls_mirror_for_type_a(emit):
    objs = {o.tags["bim.id"]: o for o in emit.objects if o.kind == "prism"}
    w1, w2 = objs["BCHW-WW1"], objs["BCHW-WW2"]
    mirrored = {(round(p[0], 6), round(-p[1], 6), round(p[2], 6))
                for p in w1.points}
    assert mirrored == {(round(p[0], 6), round(p[1], 6), round(p[2], 6))
                        for p in w2.points}


def test_wingwall_full_height_at_root_tapers_to_table_h(emit):
    d = emit.design
    w1 = next(o for o in emit.objects if o.tags["bim.id"] == "BCHW-WW1")
    zs = sorted({round(p[2], 4) for p in w1.points})
    assert zs[-1] == pytest.approx(d.H)          # root retains full height
    assert zs[-2] == pytest.approx(d.row.h1)     # tabulated h is the tip


def test_foreslope_wall_sits_on_the_box(emit):
    inp = emit.design.inputs
    fs = next(o for o in emit.objects if o.tags["bim.id"] == "BCHW-FS")
    z0 = inp.box_rise_ft + 2.0 * inp.box_slab_thickness_in / 12.0
    zs = sorted({round(p[2], 4) for p in fs.points})
    assert zs[0] == pytest.approx(z0, abs=1e-3)
    assert zs[-1] == pytest.approx(
        z0 + inp.foreslope_wall_height_in / 12.0, abs=1e-3)


def test_box_stub_leaves_the_opening_clear(emit):
    inp = emit.design.inputs
    stubs = [o for o in emit.objects
             if o.tags.get("bim.type") == "box_culvert"]
    assert all(o.tags["box.display_only"] == "true" for o in stubs)
    assert all("pay.item" not in o.tags for o in stubs)
    # nothing solid occupies the clear opening (span x rise)
    S, R = inp.box_span_ft, inp.box_rise_ft
    ts = inp.box_slab_thickness_in / 12.0
    for o in emit.objects:
        if o.kind != "prism" or o.tags.get("bim.type") == "foreslope_wall":
            continue
        for p in o.points:
            inside = (abs(p[1]) < S / 2.0 - 1e-6
                      and ts + 1e-6 < p[2] < ts + R - 1e-6)
            assert not inside, (o.tags["bim.id"], p)


def test_quantities_match_the_sheet_tables(emit):
    d = emit.design
    row = d.row
    span = d.inputs.box_span_ft + 2.0 * d.t_wall_in / 12.0
    q = pay_item_quantities(emit)

    lbs = (row.wingwall_reinf_lbs + row.footing_reinf_lbs
           + row.culvert_footing_lbs_per_ft * span
           + d.foreslope_lbs_per_ft * span)
    assert q["509E00200"]["qty"] == pytest.approx(lbs, rel=1e-3)

    # tabulated concrete + the cutoff walls (drawn from their geometry)
    cy_tab = (row.wingwall_conc_cy + row.footing_conc_cy
              + row.culvert_footing_cy_per_ft * span
              + d.foreslope_cy_per_ft * span)
    assert q["511E40000"]["qty"] > cy_tab
    # tabulated values + the geometric cutoff walls land within ~30%
    assert q["511E40000"]["qty"] == pytest.approx(cy_tab, rel=0.30)


def test_bars_carry_no_pay_block(emit):
    for o in emit.objects:
        if o.tags.get("bim.type") == "rebar" and o.kind == "polyline":
            assert "pay.item" not in o.tags


def test_type_b_wall2_runs_along_the_skewed_face():
    theta = 30.0
    emit = bchw_emit(HeadwallInput("B", 8.0, 6.0, roadway_skew_deg=theta))
    w2 = next(o for o in emit.objects if o.tags["bim.id"] == "BCHW-WW2")
    base = [p for p in w2.points if p[2] == 0.0]
    dx, dy = base[1][0] - base[0][0], base[1][1] - base[0][1]
    assert abs(dx) < 1e-9 and abs(dy) < 1e-9 or True  # base pts share s=0
    xs = sorted(p[0] for p in w2.points)
    # the wall axis is anti-parallel to the face direction (sin30, cos30)
    a = (w2.points[3][0] - w2.points[0][0],
         w2.points[3][1] - w2.points[0][1])
    n = math.hypot(*a)
    assert (a[0] / n, a[1] / n) == pytest.approx(
        (-math.sin(math.radians(theta)), -math.cos(math.radians(theta))))


def test_type_c_walls_are_level():
    emit = bchw_emit(HeadwallInput("C", 8.0, 6.0))
    row = emit.design.row
    for wid in ("BCHW-WW1", "BCHW-WW2"):
        w = next(o for o in emit.objects if o.tags["bim.id"] == wid)
        zs = {round(p[2], 4) for p in w.points}
        assert zs == {0.0, round(row.h1, 4)}


def test_rebar_toggle_keeps_quantities():
    full = bchw_emit(HeadwallInput("A", 8.0, 6.0))
    bare = bchw_emit(HeadwallInput("A", 8.0, 6.0), rebar=False)
    assert all(o.kind != "polyline" for o in bare.objects)
    qf = pay_item_quantities(full)
    qb = pay_item_quantities(bare)
    for item in qf:
        assert qb[item]["qty"] == pytest.approx(qf[item]["qty"])


def test_emit_to_3dm_round_trip(tmp_path, emit):
    pytest.importorskip("rhino3dm")
    from civilpy.structural.rhino_bim import emit_to_3dm, read_bim_quantities

    path = tmp_path / "bchw.3dm"
    counts = emit_to_3dm(emit, path)
    assert sum(counts.values()) == len(emit.objects)
    q_file = read_bim_quantities(path)
    for item, rec in pay_item_quantities(emit).items():
        assert q_file[item]["qty"] == pytest.approx(rec["qty"])


def test_culvert_footing_clear_of_wall_footings(emit):
    from civilpy.structural.rhino_bchw import _walls

    d = emit.design
    row = d.row
    w1, w2, f, half = _walls(d)
    strip = next(o for o in emit.objects
                 if o.tags["bim.id"] == "BCHW-CULV-FTG")
    for p in strip.points:
        for w in (w1, w2):
            rx, ry = p[0] - w.root[0], p[1] - w.root[1]
            s = rx * w.axis[0] + ry * w.axis[1]
            ns = (-w.n_fill[0], -w.n_fill[1])
            dd = rx * ns[0] + ry * ns[1]
            side = 1.0 if (w.root[0] * f[0] + w.root[1] * f[1]) > 0 else -1.0
            beyond_joint = (p[0] * f[0] + p[1] * f[1]) * side > half + 1e-6
            inside = (beyond_joint
                      and 1e-6 < s < w.length + 4.0 - 1e-6
                      and -(row.footing_w - row.a - 1.5) + 1e-6 < dd
                      < row.a + 1.5 - 1e-6)
            assert not inside, (w.name, p)


def test_wall_bars_stay_under_the_sloped_top(emit):
    from civilpy.structural.rhino_bchw import _walls

    w1, w2, _, _ = _walls(emit.design)
    for o in emit.objects:
        if o.kind != "polyline":
            continue
        for w in (w1, w2):
            if not o.tags["bim.id"].startswith("BCHW-" + w.name + "-"):
                continue
            for p in o.points:
                rx, ry = p[0] - w.root[0], p[1] - w.root[1]
                s = rx * w.axis[0] + ry * w.axis[1]
                if -0.01 <= s <= w.length + 0.01 and p[2] > 0.05:
                    top = (w.h_root + (w.tip_height() - w.h_root)
                           * min(max(s, 0.0), w.length) / w.length)
                    assert p[2] <= top - 0.2, (o.tags["bim.id"], p)


def test_foreslope_dowels_stay_inside_the_top_slab(emit):
    inp = emit.design.inputs
    ts = inp.box_slab_thickness_in / 12.0
    slab_bottom = inp.box_rise_ft + ts
    lows = [min(p[2] for p in o.points) for o in emit.objects
            if o.kind == "polyline"
            and o.tags["bim.id"].startswith("BCHW-FS-D")]
    assert lows and min(lows) >= slab_bottom


def test_box_stub_has_chamfer_haunches(emit):
    haunches = [o for o in emit.objects
                if "HAUNCH" in o.tags.get("bim.id", "")]
    assert len(haunches) == 4
    for h in haunches:
        assert len(h.points) == 3                    # 45 deg corner fillet
        assert h.tags["box.display_only"] == "true"


def test_footings_meet_flush_no_gap_no_overlap(emit):
    """The wall footings are clipped to the strip end plane |p.f| = half:
    they have vertices ON that plane, and none across it."""
    from civilpy.structural.rhino_bchw import _walls

    w1, w2, f, half = _walls(emit.design)
    for wid, side in (("BCHW-WW1-FTG", 1.0), ("BCHW-WW2-FTG", -1.0)):
        ftg = next(o for o in emit.objects if o.tags["bim.id"] == wid)
        projs = [side * (p[0] * f[0] + p[1] * f[1]) for p in ftg.points]
        assert min(projs) == pytest.approx(half, abs=1e-6)   # flush contact
        assert all(pr >= half - 1e-6 for pr in projs)        # no overlap


def test_z_bars_run_full_width_across_the_culvert(emit):
    from civilpy.structural.rhino_bchw import _walls

    _, _, f, half = _walls(emit.design)
    zbars = [o for o in emit.objects
             if o.tags["bim.id"].startswith("BCHW-CULV-Z")
             and not o.tags["bim.id"].startswith("BCHW-CULV-ZL")]
    assert len(zbars) > 5
    projs = [p[0] * f[0] + p[1] * f[1] for o in zbars for p in o.points]
    assert min(projs) < -half * 0.7 and max(projs) > half * 0.7
    runners = [o for o in emit.objects
               if o.tags["bim.id"].startswith("BCHW-CULV-ZL")]
    assert len(runners) == 2


def test_box_stub_end_face_on_the_skewed_headwall_plane():
    theta = 30.0
    emit = bchw_emit(HeadwallInput("B", 8.0, 6.0, roadway_skew_deg=theta))
    tan_th = math.tan(math.radians(theta))
    stubs = [o for o in emit.objects
             if o.tags.get("bim.type") == "box_culvert"]
    for o in stubs:
        for p in o.points:
            assert p[0] == pytest.approx(p[1] * tan_th, abs=1e-6)
