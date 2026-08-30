#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.
"""Rhino interchange for gusset joints: the write -> reviewer-edits -> read
round trip that lets a rating be checked and corrected in Rhino."""
import math

import pytest

rhino3dm = pytest.importorskip("rhino3dm")

from civilpy.structural import gusset_geometry as gg          # noqa: E402
from civilpy.structural import rhino_gusset as rg             # noqa: E402
from civilpy.structural.rhino_layers import (                 # noqa: E402
    LAYER_GUSSET_BLOCKSHEAR, LAYER_GUSSET_FASTENERS, LAYER_GUSSET_LOSS,
    LAYER_GUSSET_OUTLINE, LAYER_GUSSET_SCANDEPTH, LAYER_GUSSET_SECTIONS,
    LAYER_GUSSET_UNBRACED, LAYER_GUSSET_WHITMORE, LAYER_GUSSET_WORKLINES,
)


def sample_joint():
    """A three-member upper-chord joint sized like CUY-10-1613's U0: a 55 x 76
    plate, a chord running out to the right, a vertical dropping away, and a
    diagonal at -57.5 degrees, all on 3 in rivet grids."""
    wp = (12.0, 64.0)
    plate = gg.GussetPlate(gg.polygon_from_bbox(0, 0, 55.0, 76.0), 0.625,
                           label="U0 outside")
    chord = gg.MemberEnd(
        "U0U1", wp, (1, 0),
        gg.rectangular_grid((15.0, 64.0), (1, 0), 12, 5, 3.0, 3.0, 1.0),
        "chord", is_chord=True)
    vert = gg.MemberEnd(
        "U0L0", wp, (0, -1),
        gg.rectangular_grid((12.0, 58.0), (0, -1), 12, 4, 3.0, 3.0, 1.0),
        "vertical")
    ang = math.radians(-57.5)
    diag = gg.MemberEnd(
        "U0L1", wp, (math.cos(ang), math.sin(ang)),
        gg.rectangular_grid((18.0, 55.0), (math.cos(ang), math.sin(ang)),
                            7, 5, 3.0, 3.0, 1.0),
        "diagonal")
    return gg.GussetJoint("11000 U0 outside", wp, plate,
                          members=[chord, vert, diag])


def layer_paths(path):
    """``{full layer path: [object names]}`` for a written ``.3dm``."""
    f = rhino3dm.File3dm.Read(str(path))
    out = {}
    for obj in f.Objects:
        ly = f.Layers[obj.Attributes.LayerIndex]
        out.setdefault(ly.FullPath, []).append(obj.Attributes.Name or "")
    return out


def tagged(path, kind):
    """Every object of a given ``gus.kind``, as its user-text dict."""
    recs, _scale = rg._read_objects(path)
    return [t for t, _g, _n in recs if t.get("kind") == kind]


# --------------------------------------------------------------------------- #
# entities
# --------------------------------------------------------------------------- #
def test_entities_cover_every_layer():
    j = sample_joint()
    ents = rg.gusset_entities(j, sections=[((0, 40.0), (55.0, 40.0), "horiz cut")])
    layers = {e.layer for e in ents}
    for want in (LAYER_GUSSET_OUTLINE, LAYER_GUSSET_FASTENERS, LAYER_GUSSET_WORKLINES,
                 LAYER_GUSSET_WHITMORE, LAYER_GUSSET_UNBRACED,
                 LAYER_GUSSET_BLOCKSHEAR, LAYER_GUSSET_SECTIONS):
        assert want in layers
    # one circle per fastener, one work line and one block-shear polygon per member
    assert sum(1 for e in ents if e.layer == LAYER_GUSSET_FASTENERS) == 143
    assert sum(1 for e in ents if e.layer == LAYER_GUSSET_WORKLINES) == 3
    assert sum(1 for e in ents if e.layer == LAYER_GUSSET_BLOCKSHEAR) == 3
    # three unbraced rays per member
    assert sum(1 for e in ents if e.layer == LAYER_GUSSET_UNBRACED) == 9


def test_derived_false_emits_only_the_round_trip_inputs():
    j = sample_joint()
    ents = rg.gusset_entities(j, derived=False)
    layers = {e.layer for e in ents}
    assert LAYER_GUSSET_WHITMORE not in layers
    assert LAYER_GUSSET_BLOCKSHEAR not in layers
    assert LAYER_GUSSET_OUTLINE in layers and LAYER_GUSSET_FASTENERS in layers


def test_unbraced_rays_are_drawn_at_the_lengths_reported():
    """The L1/Lmid/L2 rays must be as long as unbraced_lengths() says and run
    from the Whitmore section toward the joint -- a reviewer measures them."""
    j = sample_joint()
    ents = rg.gusset_entities(j)
    for m in j.members:
        lc = j.unbraced_lengths(m)
        rays = [e for e in ents if e.layer == LAYER_GUSSET_UNBRACED
                and e.tags["member"] == m.name]
        assert len(rays) == 3
        for e in rays:
            a, b = e.points[0], e.points[1]
            drawn = math.hypot(b[0] - a[0], b[1] - a[1])
            assert drawn == pytest.approx(lc[e.tags["which"]], abs=1e-9)
            assert float(e.tags["length"]) == pytest.approx(lc[e.tags["which"]])
            if drawn > 1e-6:            # direction: toward the joint, -axis
                ux = (b[0] - a[0]) / drawn
                uy = (b[1] - a[1]) / drawn
                assert ux == pytest.approx(-m.axis[0], abs=1e-9)
                assert uy == pytest.approx(-m.axis[1], abs=1e-9)


def test_whitmore_spread_lines_are_at_thirty_degrees():
    j = sample_joint()
    ents = rg.gusset_entities(j)
    spreads = [e for e in ents if e.tags.get("kind") == "whitmore_spread"]
    assert len(spreads) == 6                        # two per member
    by_member = {m.name: m for m in j.members}
    for e in spreads:
        m = by_member[e.tags["member"]]
        a, b = e.points[0], e.points[1]
        along = abs((b[0] - a[0]) * m.axis[0] + (b[1] - a[1]) * m.axis[1])
        n = gg._perp(m.axis)
        across = abs((b[0] - a[0]) * n[0] + (b[1] - a[1]) * n[1])
        assert math.degrees(math.atan2(across, along)) == pytest.approx(30.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# the round trip
# --------------------------------------------------------------------------- #
def test_write_read_round_trip_is_exact(tmp_path):
    """The contract: write -> read -> identical summary(), so a joint can go
    out to a reviewer and come back into the rating without drift."""
    j = sample_joint()
    p = tmp_path / "j.3dm"
    n = rg.gusset_to_3dm(j, p)
    assert n > 0
    k = rg.gusset_from_3dm(p)
    assert k.name == j.name
    assert k.work_point == j.work_point
    assert [m.name for m in k.members] == [m.name for m in j.members]
    assert k.summary() == j.summary()


def test_round_trip_carries_material_type_and_fastener_detail(tmp_path):
    j = sample_joint()
    j.inside.fy, j.inside.fu = 33.0, 66.0
    j.member("U0U1").spliced_at_joint = True
    j.member("U0L1").fasteners[0].kind = "bolt"
    j.member("U0L1").fasteners[0].hole = 1.125
    p = tmp_path / "j.3dm"
    rg.gusset_to_3dm(j, p)
    k = rg.gusset_from_3dm(p)
    assert (k.inside.fy, k.inside.fu) == (33.0, 66.0)
    assert k.inside.label == "U0 outside"
    assert k.member("U0U1").spliced_at_joint is True
    assert k.member("U0U1").is_chord is True
    assert k.member("U0L0").member_type == "vertical"
    assert k.member("U0L1").fasteners[0].kind == "bolt"
    assert k.member("U0L1").fasteners[0].hole == 1.125
    assert k.summary() == j.summary()


def test_section_loss_survives_the_round_trip(tmp_path):
    """A corrosion patch a reviewer sketched must come back as a thinner plate
    where it sits -- the whole point of the as-inspected rating."""
    j = sample_joint()
    j.inside.thickness.patches.append(gg.ThicknessPatch(
        gg.polygon_from_bbox(0.0, 0.0, 55.0, 12.0), 0.375, "pack rust, 2019 insp"))
    p = tmp_path / "j.3dm"
    rg.gusset_to_3dm(j, p)
    k = rg.gusset_from_3dm(p)
    assert len(k.inside.thickness.patches) == 1
    assert k.inside.thickness.patches[0].note == "pack rust, 2019 insp"
    assert k.inside.thickness.t_at((10.0, 6.0)) == 0.375
    assert k.inside.thickness.t_at((10.0, 40.0)) == 0.625
    assert k.summary() == j.summary()
    # and the loss really costs section where it overlaps a failure plane
    clean = sample_joint()
    assert k.horizontal_section(6.0)["A_gross"] < clean.horizontal_section(6.0)["A_gross"]


def test_moving_a_rivet_changes_the_geometry_that_comes_back(tmp_path):
    """A reviewer drags the last-row rivet of the diagonal 3 in farther out;
    the connection gets longer and the Whitmore section wider."""
    j = sample_joint()
    p = tmp_path / "j.3dm"
    rg.gusset_to_3dm(j, p)

    f = rhino3dm.File3dm.Read(str(p))
    moved = 0
    for obj in f.Objects:
        us = dict(obj.Attributes.GetUserStrings() or {})
        if us.get("gus.kind") == "fastener" and us.get("gus.member") == "U0L1" \
                and us.get("gus.row") == "7":            # the Whitmore row
            obj.Attributes.SetUserString("gus.x", repr(float(us["gus.x"]) + 3.0))
            moved += 1
    assert moved
    edited = tmp_path / "edited.3dm"
    assert f.Write(str(edited), 7)

    k = rg.gusset_from_3dm(edited)
    assert k.member("U0L1").n_fasteners == j.member("U0L1").n_fasteners
    assert k.member("U0L1").connection_length != pytest.approx(
        j.member("U0L1").connection_length)
    assert k.summary()["members"]["U0L1"] != j.summary()["members"]["U0L1"]


def test_untagged_fastener_is_assigned_to_the_nearest_work_line(tmp_path):
    """A field-drilled hole the reviewer drew from scratch carries no member
    tag; it belongs to the member whose work line it sits on."""
    j = sample_joint()
    p = tmp_path / "j.3dm"
    rg.gusset_to_3dm(j, p)

    f = rhino3dm.File3dm.Read(str(p))
    lay = None
    for i, ly in enumerate(f.Layers):
        if ly.FullPath == LAYER_GUSSET_FASTENERS:
            lay = i
    attr = rhino3dm.ObjectAttributes()
    attr.LayerIndex = lay
    attr.SetUserString("gus.kind", "fastener")           # no gus.member
    new_pt = j.member("U0L0").point_at(20.0, 1.5)
    f.Objects.AddCircle(rhino3dm.Circle(
        rhino3dm.Point3d(new_pt[0], new_pt[1], 0.0), 0.5625), attr)
    drilled = tmp_path / "drilled.3dm"
    assert f.Write(str(drilled), 7)

    with pytest.warns(UserWarning, match="nearest work line"):
        k = rg.gusset_from_3dm(drilled)
    assert k.member("U0L0").n_fasteners == j.member("U0L0").n_fasteners + 1
    assert k.member("U0U1").n_fasteners == j.member("U0U1").n_fasteners


def test_derived_layers_are_not_read_back(tmp_path):
    """Whitmore / block-shear / label geometry is display only: deleting it
    must not change the joint that comes back."""
    j = sample_joint()
    p = tmp_path / "j.3dm"
    rg.gusset_to_3dm(j, p)
    full = rg.gusset_from_3dm(p).summary()

    q = tmp_path / "inputs_only.3dm"
    rg.gusset_to_3dm(j, q, derived=False)
    assert rg.gusset_from_3dm(q).summary() == full


# --------------------------------------------------------------------------- #
# tags, results, units
# --------------------------------------------------------------------------- #
def test_layers_and_tags_a_reviewer_toggles(tmp_path):
    j = sample_joint()
    p = tmp_path / "j.3dm"
    rg.gusset_to_3dm(j, p, sections=[((0, 40.0), (55.0, 40.0), "horiz cut")])
    paths = layer_paths(p)
    assert LAYER_GUSSET_OUTLINE in paths and LAYER_GUSSET_SECTIONS in paths
    assert len(paths[LAYER_GUSSET_FASTENERS]) == 143
    assert set(paths[LAYER_GUSSET_FASTENERS]) == {"U0U1", "U0L0", "U0L1"}

    # every fastener names its member, its row (1 = farthest from the joint,
    # where the force enters) and its column
    fs = tagged(p, "fastener")
    chord = [t for t in fs if t["member"] == "U0U1"]
    assert len(chord) == 60
    assert {t["row"] for t in chord} == {str(i) for i in range(1, 13)}
    assert {t["col"] for t in chord} == {"1", "2", "3", "4", "5"}
    row1 = [t for t in chord if t["row"] == "1"]
    assert all(float(t["s"]) == pytest.approx(j.member("U0U1").s_first) for t in row1)

    sec = tagged(p, "section")[0]
    assert sec["label"] == "horiz cut"
    want = j.section_along((0, 40.0), (55.0, 40.0))
    assert float(sec["A_gross"]) == pytest.approx(want["A_gross"])
    assert float(sec["A_net"]) == pytest.approx(want["A_net"])


def test_derived_tags_match_the_geometry_model(tmp_path):
    j = sample_joint()
    p = tmp_path / "j.3dm"
    rg.gusset_to_3dm(j, p)
    for m in j.members:
        w = j.whitmore(m)
        bs = j.block_shear(m)
        wt = [t for t in tagged(p, "whitmore") if t["member"] == m.name][0]
        bt = [t for t in tagged(p, "blockshear") if t["member"] == m.name][0]
        assert float(wt["b"]) == pytest.approx(w["b"])
        assert float(wt["b_effective"]) == pytest.approx(w["b_effective"])
        assert float(wt["A_gross"]) == pytest.approx(w["A_gross"])
        for key in ("A_vg", "A_vn", "A_tg", "A_tn"):
            assert float(bt[key]) == pytest.approx(bs[key])


def test_clipped_whitmore_is_drawn_separately(tmp_path):
    """The chord's 51 in connection spreads wider than the plate is tall, so
    b_effective < b -- the reviewer has to see which one was used."""
    j = sample_joint()
    w = j.whitmore("U0U1")
    assert w["b_effective"] < w["b"]
    p = tmp_path / "j.3dm"
    rg.gusset_to_3dm(j, p)
    eff = [t for t in tagged(p, "whitmore_effective") if t["member"] == "U0U1"]
    assert eff, "clipped Whitmore section was not drawn"
    assert float(eff[0]["b_effective"]) == pytest.approx(w["b_effective"])
    # and the member whose section fits inside the plate gets no clipped copy
    assert not [t for t in tagged(p, "whitmore_effective") if t["member"] == "U0L1"]


def test_results_write_back_round_trips(tmp_path):
    j = sample_joint()
    results = {"edition": "LFR2012", "governing": "check 3 rivet shear",
               "rf": 5.149,
               "checks": [("2012 chk 3", "rivet shear", 5.149, 1.0, "OK")],
               "members": {"U0L1": {"governing": "rivet shear", "rf": 5.149},
                           "U0L0": {"governing": "Whitmore compression",
                                    "rf": 16.018}}}
    p = tmp_path / "j.3dm"
    rg.gusset_to_3dm(j, p, results=results)
    back = rg.read_gusset_results(p)
    assert back["edition"] == "LFR2012"
    assert back["rf"] == pytest.approx(5.149)
    assert back["checks"] == [["2012 chk 3", "rivet shear", "5.149", "1.0", "OK"]]
    assert back["members"]["U0L0"]["rf"] == pytest.approx(16.018)
    assert back["members"]["U0L1"]["governing"] == "rivet shear"


def test_file_is_stamped_inches_and_other_units_are_scaled(tmp_path):
    j = sample_joint()
    p = tmp_path / "inches.3dm"
    rg.gusset_to_3dm(j, p)
    assert rhino3dm.File3dm.Read(str(p)).Settings.ModelUnitSystem == \
        rhino3dm.UnitSystem.Inches

    q = tmp_path / "feet.3dm"
    rg.gusset_to_3dm(j, q, unit_system=rhino3dm.UnitSystem.Feet)
    k = rg.gusset_from_3dm(q)
    # same numbers authored, but the file says feet -- so they read as inches x12
    assert k.inside.gross_width == pytest.approx(12.0 * j.inside.gross_width)
    assert k.work_point[0] == pytest.approx(12.0 * j.work_point[0])


def test_reading_a_file_that_is_not_a_gusset_raises(tmp_path):
    f = rhino3dm.File3dm()
    p = tmp_path / "empty.3dm"
    assert f.Write(str(p), 7)
    with pytest.raises(ValueError, match="not a gusset file"):
        rg.gusset_from_3dm(p)


# --------------------------------------------------------------------------- #
# scan -> thickness field
# --------------------------------------------------------------------------- #
def pitted_scan(tmp_path, depth=0.08):
    """A flat scanned face with one square pit, written as a Rhino mesh the
    way a scanner export imported into Rhino arrives."""
    np = pytest.importorskip("numpy")
    xs = np.arange(0.0, 20.0, 0.25)
    ys = np.arange(0.0, 20.0, 0.25)
    X, Y = np.meshgrid(xs, ys)
    Z = np.zeros_like(X)
    pit = (X >= 6.0) & (X < 10.0) & (Y >= 6.0) & (Y < 10.0)
    Z[pit] = -depth

    f = rhino3dm.File3dm()
    f.Settings.ModelUnitSystem = rhino3dm.UnitSystem.Inches
    from civilpy.structural.rhino_layers import ensure_layer
    attr = rhino3dm.ObjectAttributes()
    attr.LayerIndex = ensure_layer(f, "Scan")
    mesh = rhino3dm.Mesh()
    for x, y, z in zip(X.ravel(), Y.ravel(), Z.ravel()):
        mesh.Vertices.Add(float(x), float(y), float(z))
    f.Objects.AddMesh(mesh, attr)
    p = tmp_path / "scan.3dm"
    assert f.Write(str(p), 7)
    return p


#: the pitted_scan() face lies in the world XY plane, so the three points a
#: reviewer would pick give plate x/y = world X/Y (an identity registration)
SCAN_REG = dict(plate_axes=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
                plane=((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)))


def test_field_from_scan_layer_finds_the_pit(tmp_path):
    p = pitted_scan(tmp_path)
    field, info = rg.field_from_scan_layer(p, "Scan", 0.625, cell=0.5,
                                          min_depth=0.03, **SCAN_REG)
    assert field.patches, "the pit was not detected"
    assert field.t_at((8.0, 8.0)) == pytest.approx(0.625 - 0.08, abs=5e-3)
    assert field.t_at((2.0, 2.0)) == 0.625           # sound plate untouched
    assert info["cell"] == 0.5
    assert info["depth_grid"].max() == pytest.approx(0.08, abs=5e-3)


def test_scan_writes_loss_patches_and_a_depth_heat_map(tmp_path):
    p = pitted_scan(tmp_path)
    out = tmp_path / "scanned.3dm"
    field, info = rg.field_from_scan_layer(p, "Scan", 0.625, out_path=out,
                                          **SCAN_REG)
    paths = layer_paths(out)
    assert LAYER_GUSSET_LOSS in paths
    assert LAYER_GUSSET_SCANDEPTH in paths
    assert len(tagged(out, "loss")) == len(field.patches)
    assert len(tagged(out, "scan_depth")) == 1
    assert float(tagged(out, "scan_depth")[0]["depth_max"]) == \
        pytest.approx(info["depth_grid"].max())


def test_scan_can_be_written_under_the_joint_it_belongs_to(tmp_path):
    """The loss has to land under the failure planes it affects, and the file
    must still read back as a joint -- with the scan's patches on the plate."""
    j = sample_joint()
    p = pitted_scan(tmp_path)
    out = tmp_path / "joint_scanned.3dm"
    field, _info = rg.field_from_scan_layer(p, "Scan", 0.625, out_path=out,
                                            joint=j, **SCAN_REG)
    paths = layer_paths(out)
    assert LAYER_GUSSET_WHITMORE in paths and LAYER_GUSSET_SCANDEPTH in paths
    k = rg.gusset_from_3dm(out)
    assert len(k.inside.thickness.patches) == len(field.patches)
    assert k.inside.thickness.t_at((8.0, 8.0)) < 0.625


def test_a_mistyped_scan_layer_is_an_error_not_the_whole_file(tmp_path):
    """Falling back to every mesh in the file would quietly rate one plate
    with another plate's scan."""
    p = pitted_scan(tmp_path)
    with pytest.raises(ValueError, match="no layer named"):
        rg.field_from_scan_layer(p, "NotAScanLayer", 0.625, **SCAN_REG)


def test_an_unregistered_scan_warns_that_it_is_in_rotated_coordinates(tmp_path):
    """Without three picked reference points the cloud's own principal axes
    become plate x/y, which silently moves the corrosion somewhere else."""
    p = pitted_scan(tmp_path)
    with pytest.warns(UserWarning, match="ROTATED coordinates"):
        rg.field_from_scan_layer(p, "Scan", 0.625)


def test_registration_axes_from_three_picked_points():
    np = pytest.importorskip("numpy")
    o, u, v, n = rg.registration_axes((1.0, 2.0, 3.0), (11.0, 2.0, 3.0),
                                      (1.0, 12.0, 3.0))
    assert np.allclose(o, (1.0, 2.0, 3.0))
    assert np.allclose(u, (1.0, 0.0, 0.0))
    assert np.allclose(v, (0.0, 1.0, 0.0))
    assert np.allclose(np.abs(n), (0.0, 0.0, 1.0))
    assert abs(float(u @ v)) < 1e-12


def test_combine_fields_adds_loss_from_both_faces():
    """Both faces pitted 0.05 at the same spot leaves 0.10 less plate, not
    0.05 -- ThicknessField.t_at takes a minimum, so the losses must be summed
    before they get there."""
    box = gg.polygon_from_bbox(0.0, 0.0, 4.0, 4.0)
    outside = gg.ThicknessField(0.625, [gg.ThicknessPatch(box, 0.575, "outside")])
    inside = gg.ThicknessField(0.625, [gg.ThicknessPatch(box, 0.575, "inside")])
    both = rg.combine_fields(outside, inside)
    assert both.t_at((2.0, 2.0)) == pytest.approx(0.525)
    assert both.t_at((10.0, 10.0)) == 0.625

    # non-overlapping pits pass through at their own depth
    far = gg.ThicknessField(0.625, [gg.ThicknessPatch(
        gg.polygon_from_bbox(20.0, 20.0, 24.0, 24.0), 0.5, "far")])
    mixed = rg.combine_fields(outside, far)
    assert mixed.t_at((2.0, 2.0)) == pytest.approx(0.575)
    assert mixed.t_at((22.0, 22.0)) == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# joint serialization (the drawing-parser -> Rhino hand-off)
# --------------------------------------------------------------------------- #
def test_joint_dict_round_trip_is_exact():
    """The per-joint JSON the batch parser writes, and the only way to carry a
    joint into Rhino's own Python (which has no rhino3dm)."""
    import json

    j = sample_joint()
    j.inside.thickness.patches.append(gg.ThicknessPatch(
        gg.polygon_from_bbox(0.0, 0.0, 55.0, 8.0), 0.4, "pack rust"))
    d = json.loads(json.dumps(gg.joint_to_dict(j)))     # must be JSON-safe
    k = gg.joint_from_dict(d)
    assert k.summary() == j.summary()
    assert k.inside.thickness.patches[0].note == "pack rust"
    assert [m.member_type for m in k.members] == [m.member_type for m in j.members]
