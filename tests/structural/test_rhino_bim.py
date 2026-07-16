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


def test_read_bim_round_trip(tmp_path, emit):
    r3 = pytest.importorskip("rhino3dm")
    from civilpy.structural.rhino_bim import read_bim_quantities, read_bim_tags

    # bake a minimal tagged file the way a backend would
    f = r3.File3dm()
    f.Settings.ModelUnitSystem = r3.UnitSystem.Feet
    for obj in emit.objects:
        if obj.tags.get("bim.type") in ("bridge", "bearing", "girder"):
            attr = r3.ObjectAttributes()
            for k, v in obj.tags.items():
                attr.SetUserString(k, v)
            f.Objects.AddPoint(r3.Point3d(*obj.points[0]), attr)
    path = tmp_path / "bim.3dm"
    assert f.Write(str(path), 7)

    back = read_bim_tags(path)
    assert back["bridge"]["bim.girder_label"] == "W36X150"
    assert len(back["components"]) == 25          # 20 bearings + 5 girders
    q = read_bim_quantities(path)
    assert q["516E10000"]["qty"] == 20
    assert q["513E10220"]["qty"] == pytest.approx(5 * 230.0 * 150.0)


def test_cost_estimate_pricing():
    from civilpy.structural.bim import DEFAULT_UNIT_PRICES, cost_estimate

    q = {"513E10220": {"desc": "steel", "unit": "lb", "qty": 1000.0,
                       "objects": 5},
         "516E10000": {"desc": "bearing", "unit": "ea", "qty": 4.0,
                       "objects": 4},
         "999E99999": {"desc": "mystery", "unit": "ea", "qty": 2.0,
                       "objects": 2}}
    est = cost_estimate(q, prices={"516E10000": 2500.0})
    # default book price, override price, and the unpriced item
    assert est.rows["513E10220"]["cost"] == pytest.approx(
        1000.0 * DEFAULT_UNIT_PRICES["513E10220"])
    assert est.rows["516E10000"]["unit_price"] == 2500.0
    assert est.rows["999E99999"]["cost"] is None
    assert est.unpriced == ("999E99999",)
    assert est.total == pytest.approx(
        1000.0 * DEFAULT_UNIT_PRICES["513E10220"] + 4 * 2500.0)
    # quantity fields ride along and the table renders
    assert est.rows["513E10220"]["objects"] == 5
    assert "total" in str(est)


def test_read_back_skips_hidden_layers(tmp_path, emit):
    r3 = pytest.importorskip("rhino3dm")
    from civilpy.structural.rhino_bim import (
        read_bim_estimate, read_bim_quantities, read_bim_tags)

    # a live layer plus a Legacy tree hidden at the *parent* only —
    # the child stays Visible, like a real Rhino doc with Legacy off
    f = r3.File3dm()
    live = r3.Layer(); live.Name = "Bearings"
    i_live = f.Layers.Add(live)
    parent = r3.Layer(); parent.Name = "Legacy"; parent.Visible = False
    f.Layers.Add(parent)
    child = r3.Layer(); child.Name = "Bearings-old"
    child.ParentLayerId = f.Layers[1].Id
    i_child = f.Layers.Add(child)

    def add(tags, layer_index):
        attr = r3.ObjectAttributes()
        attr.LayerIndex = layer_index
        for k, v in tags.items():
            attr.SetUserString(k, v)
        f.Objects.AddPoint(r3.Point3d(0, 0, 0), attr)

    add({"bim.type": "bridge", "bim.id": "BRIDGE"}, i_child)  # marker hidden
    for o in emit.objects:
        if o.tags.get("bim.type") == "bearing":
            add(o.tags, i_live)
            add(o.tags, i_child)          # stale duplicate under Legacy
    path = tmp_path / "legacy.3dm"
    assert f.Write(str(path), 7)

    # only the live copies count, but the bridge record still comes back
    back = read_bim_tags(path)
    assert back["bridge"]["bim.id"] == "BRIDGE"
    assert len(back["components"]) == 20
    assert read_bim_quantities(path)["516E10000"]["qty"] == 20
    q_all = read_bim_quantities(path, include_hidden=True)
    assert q_all["516E10000"]["qty"] == 40
    est = read_bim_estimate(path, prices={"516E10000": 1800.0})
    assert est.total == pytest.approx(20 * 1800.0)


def test_emit_json_round_trip(emit):
    data = json.loads(emit_to_json(emit))
    assert data["doc_tags"]["bim.units"] == "ft"
    assert len(data["objects"]) == len(emit.objects)
    kinds = {o["kind"] for o in data["objects"]}
    assert kinds == {"prism", "polyline", "cylinder", "point"}


def test_emit_to_3dm_round_trip(tmp_path, emit):
    r3 = pytest.importorskip("rhino3dm")
    from civilpy.structural.rhino_bim import emit_to_3dm, read_bim_quantities

    path = tmp_path / "baked.3dm"
    counts = emit_to_3dm(emit, path)
    assert sum(counts.values()) == len(emit.objects)

    # every prism landed as a capped solid, not a mesh fallback
    f = r3.File3dm.Read(str(path))
    n_prisms = sum(1 for o in emit.objects if o.kind == "prism")
    n_cyls = sum(1 for o in emit.objects if o.kind == "cylinder")
    n_breps = sum(1 for o in f.Objects
                  if isinstance(o.Geometry, (r3.Brep, r3.Extrusion)))
    assert n_breps == n_prisms + n_cyls

    # the saved file regenerates the estimate exactly
    q_emit = pay_item_quantities(emit)
    q_file = read_bim_quantities(path)
    assert set(q_file) == set(q_emit)
    for item, rec in q_emit.items():
        assert q_file[item]["qty"] == pytest.approx(rec["qty"])


def _mesh_volume(m) -> float:
    """Signed volume of a closed mesh by the divergence theorem — an
    independent check that the ear-clipped caps close the solid
    correctly (a fan that left the section would skew this)."""
    vol = 0.0
    for i in range(len(m.Faces)):
        idx = list(m.Faces[i])
        tris = [(idx[0], idx[1], idx[2])]
        if len(idx) == 4 and idx[2] != idx[3]:
            tris.append((idx[0], idx[2], idx[3]))
        for a, b, c in tris:
            v0, v1, v2 = m.Vertices[a], m.Vertices[b], m.Vertices[c]
            vol += (v0.X * (v1.Y * v2.Z - v1.Z * v2.Y)
                    - v0.Y * (v1.X * v2.Z - v1.Z * v2.X)
                    + v0.Z * (v1.X * v2.Y - v1.Y * v2.X)) / 6.0
    return vol


def test_emit_to_3dm_mesh_flavor(tmp_path, emit):
    """The web-viewer flavor: every solid lands as a *closed* mesh (no
    breps — 3DMLoader would render those empty), tags and the estimate
    round-trip identically to the brep flavor."""
    r3 = pytest.importorskip("rhino3dm")
    from civilpy.structural.bridge_layout import girder_section
    from civilpy.structural.rhino_bim import (
        _polygon_area, emit_to_3dm, read_bim_quantities)

    path = tmp_path / "web.3dm"
    counts = emit_to_3dm(emit, path, mesh=True)
    assert sum(counts.values()) == len(emit.objects)

    f = r3.File3dm.Read(str(path))
    n_solids = sum(1 for o in emit.objects
                   if o.kind in ("prism", "cylinder"))
    meshes = [o for o in f.Objects if isinstance(o.Geometry, r3.Mesh)]
    assert len(meshes) == n_solids
    assert not any(isinstance(o.Geometry, (r3.Brep, r3.Extrusion))
                   for o in f.Objects)
    for o in meshes:
        assert o.Geometry.IsClosed, dict(
            o.Attributes.GetUserStrings() or {})

    # the non-convex I-profile caps close to the exact prism volume
    g1 = next(o for o in meshes
              if dict(o.Attributes.GetUserStrings())["bim.id"] == "G1")
    sec = girder_section("W36X150")
    area_ft2 = _polygon_area(i_profile_wh(sec)) / 144.0
    assert _mesh_volume(g1.Geometry) == pytest.approx(
        area_ft2 * emit.layout.total_length_ft, rel=1e-6)
    # the crowned deck closes to its tagged pay quantity
    deck = next(o for o in meshes
                if dict(o.Attributes.GetUserStrings()).get("bim.type")
                == "deck")
    assert _mesh_volume(deck.Geometry) / 27.0 == pytest.approx(
        float(dict(deck.Attributes.GetUserStrings())["pay.qty"]), rel=1e-3)

    # identical read-back contract to the brep flavor
    q_emit = pay_item_quantities(emit)
    q_file = read_bim_quantities(path)
    assert set(q_file) == set(q_emit)
    for item, rec in q_emit.items():
        assert q_file[item]["qty"] == pytest.approx(rec["qty"])


def test_triangulate_loop_nonconvex():
    from civilpy.structural.rhino_bim import _triangulate_loop

    # CCW L-shape: a centroid fan would leave the section
    poly = [(0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (1.0, 1.0),
            (1.0, 3.0), (0.0, 3.0)]
    tris = _triangulate_loop(poly)
    assert len(tris) == len(poly) - 2

    def area(a, b, c):
        return ((b[0] - a[0]) * (c[1] - a[1])
                - (b[1] - a[1]) * (c[0] - a[0])) / 2.0

    total = sum(area(poly[a], poly[b], poly[c]) for a, b, c in tris)
    assert total == pytest.approx(6.0)          # all CCW, sums to the area
    assert all(area(poly[a], poly[b], poly[c]) > 0 for a, b, c in tris)


# ── substructure emit ─────────────────────────────────

@pytest.fixture(scope="module")
def sub_emit(emit):
    from civilpy.structural.aashto.lrfd.columns import RebarLayer
    from civilpy.structural.abutment import RetainingWall
    from civilpy.structural.pier import MultiColumnBent, PierCap, PierColumn
    from civilpy.structural.rhino_bim import add_substructure
    from civilpy.structural.substructure_layout import (
        AbutmentSpec, FootingSpec, substructure_from_layout)
    from tests.structural.test_substructure_layout import _cap_design

    layout = emit.layout
    # girders span 32 ft along the cap; 2.5 ft edges -> 37 ft cap
    pier_cap = _cap_design(span=37.0, depth=5.0, thickness=4.0)
    bent = MultiColumnBent(
        PierCap(length=37.0 * 12.0, width=48.0, depth=60.0,
                column_positions=[138.0, 306.0]),
        [PierColumn(height=240.0, diameter=42.0,
                    layers=[RebarLayer(area=12.0, depth=6.0)])
         for _ in range(2)])
    spec = AbutmentSpec(
        pile_xs_ft=(1.0, 11.0, 21.0, 31.0), pile_shape="HP10X42",
        pile_length_ft=40.0,
        wingwall=RetainingWall(
            stem_height=12.0, stem_thickness=1.5, toe_length=3.0,
            heel_length=6.0, footing_thickness=2.5, backfill_gamma=120.0,
            backfill_phi=32.0),
        wingwall_length_ft=10.0)
    sub = substructure_from_layout(
        layout, pier_cap=pier_cap, pier_bent=bent,
        abutment_cap=_cap_design(span=37.0, depth=3.5, thickness=3.0),
        abutment=spec,
        footing=FootingSpec(length_ft=10.0, width_ft=10.0,
                            thickness_ft=3.0))
    return add_substructure(emit, sub), sub


def test_substructure_component_inventory(sub_emit):
    full, _ = sub_emit
    by_type = {t: len(full.of_type(t)) for t in (
        "pier_cap", "abutment_cap", "beam_seat", "column", "footing",
        "pile", "backwall", "wingwall")}
    # 3 spans -> 2 piers + 2 abutments over 5 girder lines
    assert by_type["pier_cap"] == 2
    assert by_type["abutment_cap"] == 2
    assert by_type["beam_seat"] == 4 * 5
    assert by_type["column"] == 2 * 2
    assert by_type["footing"] == 2 * 2
    assert by_type["pile"] == 2 * 4
    assert by_type["backwall"] == 2
    assert by_type["wingwall"] == 2 * 4       # 2 stems + 2 footings each
    ids = [o.tags["bim.id"] for o in full.objects if "bim.type" in o.tags]
    assert len(ids) == len(set(ids))


def test_substructure_cap_sits_under_bearing_stack(sub_emit):
    full, sub = sub_emit
    layout = full.layout
    pier = sub.piers[0]
    cap = next(o for o in full.of_type("pier_cap")
               if o.tags["bim.id"] == "PIER2-CAP")
    z_top = max(p[2] for p in cap.points)
    pad_bottoms = [bp.location[2] - (1.5 + 3.0) / 12.0
                   for bp in layout.bearings if bp.station_index == 1]
    assert z_top == pytest.approx(min(pad_bottoms) - 3.0 / 12.0)
    assert z_top == pytest.approx(pier.cap.origin[2])
    # every seat spans exactly from the cap top to its pad bottom
    for seat in (o for o in full.of_type("beam_seat")
                 if o.tags["bim.id"].startswith("PIER2-")):
        z_base = seat.points[0][2]
        assert z_base == pytest.approx(z_top)
        h = float(seat.tags["beam_seat.height_in"]) / 12.0
        assert z_base + h == pytest.approx(z_base + seat.vector[2])


def test_substructure_columns_meet_cap_and_footing(sub_emit):
    full, sub = sub_emit
    pier = sub.piers[0]
    z_cap_bot = pier.cap.origin[2] - pier.cap.depth_ft
    cols = [o for o in full.of_type("column")
            if o.tags["bim.id"].startswith("PIER2-")]
    ftgs = [o for o in full.of_type("footing")
            if o.tags["bim.id"].startswith("PIER2-")]
    for col in cols:
        base, top = col.points
        assert top[2] == pytest.approx(z_cap_bot)
        assert col.radius_ft == pytest.approx(42.0 / 24.0)
        assert base[2] == pytest.approx(z_cap_bot - 20.0)
    for ftg in ftgs:
        # footing prism rises through its thickness to the column base
        assert max(p[2] for p in ftg.points) + ftg.vector[2] == (
            pytest.approx(z_cap_bot - 20.0))


def test_substructure_pile_profile_and_pay(sub_emit):
    full, _ = sub_emit
    pile = next(o for o in full.of_type("pile")
                if o.tags["bim.id"] == "ABUT1-PILE-1")
    assert pile.tags["pile.shape"] == "HP10X42"
    assert pile.tags["pay.item"] == "507E10000"
    assert float(pile.tags["pay.qty"]) == 40.0
    assert pile.vector == (0.0, 0.0, -40.0)
    assert len(pile.points) > 16              # true I-profile with fillets
    ys = [p[1] for p in pile.points]
    assert max(ys) - min(ys) == pytest.approx(10.1 / 12.0)  # flange width


def test_substructure_cap_rebar_from_stm_schedule(sub_emit):
    full, sub = sub_emit
    pier = sub.piers[0]
    bars = [o for o in full.objects
            if o.tags.get("bim.id", "").startswith("PIER2-CAPBAR-")]
    # the stub design's governing tie: 12 x #10
    assert len(bars) == pier.cap.tie_bar_count == 12
    z_cap_bot = pier.cap.origin[2] - pier.cap.depth_ft
    for b in bars:
        assert b.tags["rebar.size"] == "#10"
        assert b.tags["rebar.mat"] == "pier_cap"
        assert b.tags["pay.item"] == "509E00200"
        z = b.points[0][2]
        assert z == pytest.approx(z_cap_bot + (3.0 + 10.0 / 8.0 / 2.0) / 12.0)
    stirrups = [o for o in full.objects
                if o.tags.get("bim.id", "").startswith("PIER2-STIR-")]
    assert len(stirrups) == 37                # 37 ft cap at 12 in
    for s in stirrups[:3]:
        assert s.points[0] == s.points[-1]    # closed hoop
        assert s.tags["rebar.bend"] == "stirrup"


def test_substructure_column_rebar_carries_design_area(sub_emit):
    full, sub = sub_emit
    col = sub.piers[0].columns[0]
    verts = [o for o in full.objects
             if o.tags.get("bim.id", "").startswith("PIER2-COL1-V")]
    ties = [o for o in full.objects
            if o.tags.get("bim.id", "").startswith("PIER2-COL1-T")]
    # 12.0 in^2 of layer steel broken into #9 bars (1.0 in^2)
    assert len(verts) == 12
    for v in verts:
        assert v.points[0][2] == pytest.approx(col.z_bot)
        assert v.points[1][2] == pytest.approx(col.z_top)
        r = math.hypot(v.points[0][0] - col.center[0],
                       v.points[0][1] - col.center[1])
        assert r == pytest.approx(42.0 / 24.0 - 3.0 / 12.0 - 0.5 / 12.0)
    assert ties and all(t.tags["rebar.bend"] == "hoop" for t in ties)


def test_substructure_wall_mats(sub_emit):
    full, _ = sub_emit
    bw = [o for o in full.objects
          if o.tags.get("bim.id", "").startswith("ABUT1-BW-")]
    assert bw, "backwall mats missing"
    faces = {o.tags["bim.id"].split("-")[2] for o in bw}
    assert faces == {"F1", "F2"}
    for o in bw:
        assert o.tags["rebar.mat"] == "backwall"
        assert o.tags["rebar.size"] == "#5"


def test_substructure_pay_rollup(sub_emit):
    full, sub = sub_emit
    q = pay_item_quantities(full)
    conc = q["511E40000"]
    assert conc["unit"] == "cy"
    expect = sum(g.cap.volume_cy for g in sub.units)
    expect += sum((s.side_in / 12.0) ** 2 * (s.height_in / 12.0) / 27.0
                  for g in sub.units for s in g.seats)
    for pier in sub.piers:
        expect += sum(c.volume_cy for c in pier.columns)
        expect += sum(f.volume_cy for f in pier.footings)
    for ab in sub.abutments:
        expect += ab.backwall.volume_cy
        expect += sum(w.volume_cy for w in ab.wingwalls)
    assert conc["qty"] == pytest.approx(expect, rel=1e-3)
    piles = q["507E10000"]
    assert piles["unit"] == "ft" and piles["qty"] == 8 * 40.0
    # superstructure items are untouched by the merge
    assert q["513E20000"]["qty"] == 5 * 115 * 3


def test_pile_bent_pier_emit(emit):
    from civilpy.structural.rhino_bim import substructure_emit
    from civilpy.structural.substructure_layout import (
        AbutmentSpec, PileBentSpec, SeatAbutmentSpec, assemble_substructure)
    from tests.structural.test_substructure_layout import _cap_design

    cap = _cap_design(span=37.0, depth=3.0, thickness=3.0)
    sub = assemble_substructure(emit.layout, {
        "pier": PileBentSpec(cap_design=cap,
                             pile_xs_ft=(1.0, 11.0, 21.0, 31.0)),
        "abutment": SeatAbutmentSpec(
            cap_design=cap,
            spec=AbutmentSpec(pile_xs_ft=(1.0, 11.0, 21.0, 31.0)))})
    objs = substructure_emit(sub, rebar=None)
    piles = [o for o in objs if o.tags.get("bim.type") == "pile"]
    # 2 pile-bent piers + 2 abutments, 4 piles each
    assert len(piles) == 4 * 4
    pier_piles = [o for o in piles
                  if o.tags["bim.id"].startswith("PIER2-PILE-")]
    assert len(pier_piles) == 4
    for p in pier_piles:
        assert p.tags["pile.shape"] == "HP12X53"
        assert p.tags["pay.item"] == "507E10000"
    assert not [o for o in objs if o.tags.get("bim.type") == "column"]


def test_hammerhead_pier_emit(emit):
    from civilpy.structural.pier import PierColumn
    from civilpy.structural.aashto.lrfd.columns import RebarLayer
    from civilpy.structural.rhino_bim import substructure_emit
    from civilpy.structural.substructure_layout import (
        AbutmentSpec, HammerheadSpec, SeatAbutmentSpec,
        assemble_substructure)
    from tests.structural.test_substructure_layout import _cap_design

    stem = PierColumn(height=22.0 * 12.0, b=72.0, h=60.0,
                      layers=[RebarLayer(area=10.0, depth=6.0)])
    sub = assemble_substructure(emit.layout, {
        "pier": HammerheadSpec(
            cap_design=_cap_design(span=38.0, depth=6.0, thickness=5.0,
                                   tie_at_top=True),
            column=stem, tip_depth_ft=2.5),
        "abutment": SeatAbutmentSpec(
            cap_design=_cap_design(span=38.0, depth=3.5, thickness=3.0),
            spec=AbutmentSpec(pile_xs_ft=(1.0, 12.0, 24.0, 35.0)))})
    objs = substructure_emit(sub)

    cap = next(o for o in objs if o.tags.get("bim.id") == "PIER2-CAP")
    # elevation-profile prism: level top + 4-point tapered soffit,
    # extruded across the width
    assert len(cap.points) == 6
    z_top = max(p[2] for p in cap.points)
    assert min(p[2] for p in cap.points) == pytest.approx(z_top - 6.0)
    # the tips stop at the taper depth
    assert cap.points[2][2] == pytest.approx(z_top - 2.5)
    assert cap.points[-1][2] == pytest.approx(z_top - 2.5)
    assert cap.vector[1] == pytest.approx(0.0)
    assert abs(cap.vector[0]) == pytest.approx(5.0)   # width across bridge
    assert cap.tags["pier_cap.tip_depth_ft"] == "2.5"

    # cantilever main steel lands in the top chord
    bars = [o for o in objs
            if o.tags.get("bim.id", "").startswith("PIER2-CAPBAR-")]
    assert bars
    for b in bars:
        assert b.points[0][2] == pytest.approx(
            z_top - (3.0 + 10.0 / 8.0 / 2.0) / 12.0)
    # stirrups follow the tapered soffit: shorter hoops near the tips
    stirrups = [o for o in objs
                if o.tags.get("bim.id", "").startswith("PIER2-STIR-")]
    tip_h = max(p[2] for p in stirrups[0].points) - min(
        p[2] for p in stirrups[0].points)
    mid = stirrups[len(stirrups) // 2]
    mid_h = max(p[2] for p in mid.points) - min(p[2] for p in mid.points)
    assert tip_h < mid_h
    # one column, 22 ft tall, under the full-depth soffit
    cols = [o for o in objs
            if o.tags.get("bim.id", "").startswith("PIER2-COL")
            and o.tags.get("bim.type") == "column"]
    assert len(cols) == 1


def test_semi_integral_abutment_emit(emit):
    from civilpy.structural.rhino_bim import substructure_emit
    from civilpy.structural.substructure_layout import (
        AbutmentSpec, PileBentSpec, SemiIntegralAbutmentSpec,
        assemble_substructure)
    from tests.structural.test_substructure_layout import _cap_design

    cap = _cap_design(span=37.0, depth=3.5, thickness=3.0)
    sub = assemble_substructure(emit.layout, {
        "pier": PileBentSpec(cap_design=cap,
                             pile_xs_ft=(1.0, 11.0, 21.0, 31.0)),
        "abutment": SemiIntegralAbutmentSpec(
            cap_design=cap,
            spec=AbutmentSpec(pile_xs_ft=(1.0, 11.0, 21.0, 31.0)),
            diaphragm_thickness_in=30.0)})
    objs = substructure_emit(sub)
    dias = [o for o in objs if o.tags.get("bim.type") == "diaphragm"]
    assert len(dias) == 2
    for d in dias:
        assert d.layer == "Superstructure::Diaphragms"
        assert d.tags["pay.item"] == "511E12100"     # superstructure item
        assert d.tags["mat.class"] == "QC2"
        assert float(d.tags["pay.qty"]) > 0
    assert not [o for o in objs if o.tags.get("bim.type") == "backwall"]
    # the diaphragm carries its own two-face mat
    assert [o for o in objs
            if o.tags.get("bim.id", "").startswith("ABUT1-DIA-")]


def test_integral_abutment_emit_suppresses_bearings():
    from civilpy.structural.rhino_bim import substructure_emit
    from civilpy.structural.substructure_layout import (
        IntegralAbutmentSpec, PileBentSpec, assemble_substructure)
    from tests.structural.test_substructure_layout import _cap_design

    inp = BridgeInput(spans_ft=(70.0, 70.0), girder_count=5,
                      girder_spacing_ft=8.0, girder_label="W36X150",
                      overhang_ft=3.0, railing="SBR-1-20",
                      grade="Grade 50W")
    e = girder_bridge_emit(inp, integral_supports=(0, 2))
    # bearings only at the pier line: 5 pads + 5 plates
    assert len(e.of_type("bearing")) == 5
    assert len(e.of_type("load_plate")) == 5
    # every gdr support point survives for the analysis reader
    supports = [o for o in e.objects
                if o.tags.get("gdr.kind") == "support"]
    assert len(supports) == 15
    integral_pts = [o for o in supports
                    if o.tags.get("gdr.integral") == "true"]
    assert len(integral_pts) == 10
    assert e.doc_tags["bim.integral_supports"] == "0,2"

    sub = assemble_substructure(e.layout, {
        "pier": PileBentSpec(
            cap_design=_cap_design(span=37.0, depth=3.0, thickness=3.0),
            pile_xs_ft=(1.0, 11.0, 21.0, 31.0)),
        "abutment": IntegralAbutmentSpec(
            pile_xs_ft=(2.0, 10.0, 18.0, 26.0, 34.0))})
    objs = substructure_emit(sub)
    # no abutment cap, no seats at the integral ends; diaphragm instead
    assert not [o for o in objs
                if o.tags.get("bim.type") == "abutment_cap"]
    assert not [o for o in objs
                if o.tags.get("bim.id", "").startswith("ABUT1-SEAT")]
    dias = [o for o in objs if o.tags.get("bim.type") == "diaphragm"]
    assert len(dias) == 2
    abut_piles = [o for o in objs
                  if o.tags.get("bim.id", "").startswith("ABUT1-PILE-")]
    assert len(abut_piles) == 5


def test_stm_overlay_lands_in_the_cap(sub_emit):
    from civilpy.structural.rhino_bim import stm_overlay_emit
    from civilpy.structural.strut_and_tie import StrutAndTieModel

    full, sub = sub_emit
    pier = sub.piers[0]
    m = StrutAndTieModel()
    m.add_node("A", 0.0, 0.0)                # girder 1, cap bottom
    m.add_node("B", 16.0, 5.0)               # mid-cap, cap top
    m.add_member("A", "B")
    m.forces = {("A", "B"): 120.0}
    overlay = stm_overlay_emit(m, pier, full.layout)
    assert len(overlay) == 1
    tie = overlay[0]
    assert tie.layer == "Substructure::STM::Ties"
    assert tie.tags["stm.kind"] == "tie"
    assert "pay.item" not in tie.tags        # analysis-only, never estimated
    # node A maps to girder 1 (y=0) at the cap soffit under pier 2
    z_bot = pier.cap.origin[2] - pier.cap.depth_ft
    assert tie.points[0] == pytest.approx((70.0, 0.0, z_bot))
    assert tie.points[1][2] == pytest.approx(z_bot + 5.0)
    m.forces = {("A", "B"): -80.0}
    strut = stm_overlay_emit(m, pier, full.layout)[0]
    assert strut.layer == "Substructure::STM::Struts"
    assert strut.tags["stm.kind"] == "strut"


def test_substructure_read_back_round_trip(tmp_path, sub_emit):
    r3 = pytest.importorskip("rhino3dm")
    from civilpy.structural.rhino_bim import read_bim_quantities

    full, _ = sub_emit
    f = r3.File3dm()
    f.Settings.ModelUnitSystem = r3.UnitSystem.Feet
    for obj in full.objects:
        if obj.tags.get("bim.type") in ("pier_cap", "abutment_cap", "pile",
                                        "backwall", "column"):
            attr = r3.ObjectAttributes()
            for k, v in obj.tags.items():
                attr.SetUserString(k, v)
            f.Objects.AddPoint(r3.Point3d(*obj.points[0]), attr)
    path = tmp_path / "sub.3dm"
    assert f.Write(str(path), 7)

    q = read_bim_quantities(path)
    assert q["507E10000"]["qty"] == 8 * 40.0
    baked = pay_item_quantities(full)
    baked_conc = sum(
        float(o.tags["pay.qty"]) for o in full.objects
        if o.tags.get("bim.type") in ("pier_cap", "abutment_cap",
                                      "backwall", "column"))
    assert q["511E40000"]["qty"] == pytest.approx(baked_conc, abs=0.05)
    assert q["507E10000"]["unit"] == baked["507E10000"]["unit"]


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
