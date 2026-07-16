#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the storable Spec records: JSON round-trip, validation,
reconstitution to geometry, the metrics sidecar, and the check-coverage
forcing function (build plan §3: every check consuming a hammerhead must
resolve its inputs to Spec fields — a gap here is the live backlog)."""

import inspect
import json

import pytest

from civilpy.structural.bim_spec import (
    HAMMERHEAD_CHECK_INPUTS,
    CapDetailingRecord,
    FootingRecord,
    HammerheadPierRecord,
    PierCapRecord,
    PierStemRecord,
    Provenance,
    pier_metrics,
    record_paths,
    stem_rebar_layers,
)


@pytest.fixture()
def record() -> HammerheadPierRecord:
    return HammerheadPierRecord(
        pier_cap=PierCapRecord(span_ft=38.0, depth_ft=6.0,
                               thickness_ft=5.0, tie_bar_size=10,
                               tie_bar_count=12, tip_depth_ft=2.5),
        pier_stem=PierStemRecord(height_ft=22.0, bars_area_in2=10.0,
                                 b_in=72.0, h_in=60.0),
        footing=FootingRecord(length_ft=14.0, width_ft=12.0,
                              thickness_ft=3.5),
        standard=None, standard_year=None,
        provenance=Provenance(source="plans", doc_id="PLN-001",
                              sheet="S-12"))


# ── round-trip + validation ───────────────────────────────────────────────

def test_json_round_trip(record):
    doc = record.to_dict()
    assert doc["bim.type"] == "pier"
    assert doc["subtype"] == "hammerhead"
    assert doc["schema_version"] >= 1
    # genuinely JSON-safe, and the identity survives the wire
    wire = json.loads(json.dumps(doc))
    back = HammerheadPierRecord.from_dict(wire)
    assert back == record
    # the JSONB query paths from the build plan resolve on the document
    assert wire["pier_stem"]["height_ft"] == 22.0
    assert wire["pier_cap"]["tip_depth_ft"] == 2.5
    assert wire["provenance"]["source"] == "plans"


def test_from_dict_rejects_wrong_element():
    with pytest.raises(ValueError, match="not a pier/hammerhead"):
        HammerheadPierRecord.from_dict({"bim.type": "abutment",
                                        "subtype": "seat"})


def test_validate_clean(record):
    assert record.validate() == []
    record.validate(strict=True)


def test_validate_catches_bad_data(record):
    doc = record.to_dict()
    doc["pier_cap"]["depth_ft"] = "six feet"          # type
    doc["pier_stem"]["height_ft"] = -22.0             # bound
    doc["provenance"]["source"] = "hearsay"           # enum
    bad = HammerheadPierRecord.from_dict(doc)
    problems = bad.validate()
    assert any("pier_cap.depth_ft" in p and "float" in p
               for p in problems)
    assert any("pier_stem.height_ft" in p and "> 0" in p
               for p in problems)
    assert any("provenance.source" in p and "hearsay" in p
               for p in problems)
    with pytest.raises(ValueError):
        bad.validate(strict=True)


def test_validate_cross_field_rules(record):
    doc = record.to_dict()
    doc["pier_cap"]["tip_depth_ft"] = 9.0             # deeper than the cap
    doc["pier_stem"]["diameter_in"] = 48.0            # and rectangular
    bad = HammerheadPierRecord.from_dict(doc)
    problems = bad.validate()
    assert any("tip_depth_ft" in p and "exceeds" in p for p in problems)
    assert any("b_in+h_in or diameter_in" in p for p in problems)


def test_defaults_fill_in(record):
    assert isinstance(record.detailing, CapDetailingRecord)
    assert record.detailing.cover_in == 3.0
    minimal = HammerheadPierRecord(
        pier_cap=record.pier_cap, pier_stem=record.pier_stem)
    assert minimal.provenance.source == "manual"
    assert minimal.validate() == []


def test_field_metadata_rides_on_the_field():
    from dataclasses import fields

    by_name = {f.name: f for f in fields(PierCapRecord)}
    assert by_name["depth_ft"].metadata["unit"] == "ft"
    assert "5.8.2.4" in by_name["tie_bar_size"].metadata["checks"]
    stem = {f.name: f for f in fields(PierStemRecord)}
    assert stem["fixity"].metadata["enum"] == ("fixed-fixed", "fixed-free")


# ── check coverage: the §3 forcing function ───────────────────────────────

#: Every LRFD check that consumes a hammerhead pier.  Adding a check to
#: the ported library that a hammerhead should run makes this list — and
#: the mapping in HAMMERHEAD_CHECK_INPUTS — the enforced backlog.
HAMMERHEAD_CHECKS = (
    "5.8.2.4", "5.8.2.5", "5.8.2.6",                  # cap D-region STM
    "5.7.3.3", "5.7.2.5", "5.7.2.6",                  # cap sectional shear
    "5.6.7", "5.10.8.2.1",                            # serviceability/detail
    "5.6.4.4", "5.6.4.2", "5.6.4.5 check",            # stem
    "4.5.3.2.2b",                                     # slenderness
)


def test_every_hammerhead_check_is_mapped():
    assert set(HAMMERHEAD_CHECK_INPUTS) == set(HAMMERHEAD_CHECKS)


@pytest.mark.parametrize("article", HAMMERHEAD_CHECKS)
def test_check_inputs_resolve_to_spec_fields(article):
    """For each check: it exists in the ported library, every *required*
    parameter is mapped, every mapped name is a real parameter, and every
    referenced record path exists on the schema."""
    from civilpy.structural.aashto import lrfd

    fn = lrfd.ARTICLES.get(article)
    assert fn is not None, f"{article} missing from the ported ARTICLES"

    sig = inspect.signature(fn)
    mapping = HAMMERHEAD_CHECK_INPUTS[article]
    required = {p.name for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty}
    unmapped = required - set(mapping)
    assert not unmapped, (
        f"{article} ({fn.__name__}): required inputs {sorted(unmapped)} "
        f"have no Spec-field resolution — extend the record or the map")
    unknown = set(mapping) - set(sig.parameters)
    assert not unknown, (f"{article}: mapped names {sorted(unknown)} are "
                         f"not parameters of {fn.__name__}")

    schema = record_paths(HammerheadPierRecord)
    for param, entry in mapping.items():
        kind = entry[0]
        assert kind in ("field", "derived", "loads"), (article, param)
        paths = ((entry[1],) if kind == "field"
                 else entry[1] if kind == "derived" else ())
        for path in paths:
            assert path in schema, (
                f"{article}.{param}: path {path!r} does not exist on "
                f"HammerheadPierRecord")


def test_checks_actually_run_from_record_inputs(record):
    """First real exercise of the port from record-resolved inputs: the
    stem axial/limits checks and the cap tie check produce sane numbers
    from Spec fields alone (demand-side inputs are analysis outputs)."""
    from civilpy.structural.aashto import lrfd
    from civilpy.structural.steel import Rebar

    s, c = record.pier_stem, record.pier_cap
    a_g = s.b_in * s.h_in
    axial = lrfd.ARTICLES["5.6.4.4"](a_g=a_g, a_st=s.bars_area_in2,
                                     f_c=s.fc_ksi, f_y=s.fy_ksi,
                                     spiral=s.spiral)
    assert axial.capacity > 0.0

    limits = lrfd.ARTICLES["5.6.4.2"](a_g=a_g, a_st=s.bars_area_in2,
                                      f_c=s.fc_ksi, f_y=s.fy_ksi)
    assert limits.article == "5.6.4.2"

    a_st = c.tie_bar_count * float(Rebar(c.tie_bar_size).area.magnitude)
    tie = lrfd.ARTICLES["5.8.2.4"](a_st=a_st, f_y=c.fy_ksi, p_u=700.0)
    assert tie.capacity == pytest.approx(a_st * c.fy_ksi)

    layers = stem_rebar_layers(record)
    assert sum(l.area for l in layers) == pytest.approx(s.bars_area_in2)
    pm = lrfd.ARTICLES["5.6.4.5 check"](
        p_u=800.0, m_u=6000.0, layers=layers, f_c=s.fc_ksi, f_y=s.fy_ksi,
        h=s.h_in, b=s.b_in)
    assert pm.capacity > 0.0


# ── reconstitution: record -> geometry -> emit -> metrics ─────────────────

@pytest.fixture(scope="module")
def layout():
    from civilpy.structural.bridge_layout import BridgeInput, layout_bridge

    return layout_bridge(BridgeInput(
        spans_ft=(80.0, 80.0), girder_count=5, girder_spacing_ft=8.0,
        girder_label="W36X150", overhang_ft=3.0, railing="SBR-1-20",
        grade="Grade 50W"))


def test_record_builds_placed_geometry(record, layout):
    from civilpy.structural.substructure import substructure_units
    from civilpy.structural.substructure_layout import PierGeometry

    unit = substructure_units(layout)[1]          # the single pier
    geom = record.build(layout, unit)
    assert isinstance(geom, PierGeometry)
    assert geom.cap.length_ft == pytest.approx(38.0)
    assert geom.cap.depth_ft == pytest.approx(6.0)
    assert geom.cap.soffit_profile is not None    # tapered tips
    assert len(geom.columns) == 1
    col = geom.columns[0]
    assert col.height_ft == pytest.approx(22.0)
    assert col.b_in == 72.0 and col.h_in == 60.0
    assert geom.footings[0].length_ft == 14.0
    # the stored tie schedule carried through to the placed cap
    assert geom.cap.tie_bar_size == 10
    assert geom.cap.tie_bar_count == 12
    assert geom.cap.tie_z_frac is not None and geom.cap.tie_z_frac > 0.5


def test_round_tripped_record_builds_identical_geometry(record, layout):
    from civilpy.structural.substructure import substructure_units

    unit = substructure_units(layout)[1]
    wire = json.loads(json.dumps(record.to_dict()))
    again = HammerheadPierRecord.from_dict(wire)
    assert again.build(layout, unit) == record.build(layout, unit)


def test_record_emits_mesh_3dm_with_tags(tmp_path, record, layout):
    r3 = pytest.importorskip("rhino3dm")
    from civilpy.structural.rhino_bim import (
        read_bim_tags, substructure_emit)
    from civilpy.structural.rhino_layers import ensure_layer
    from civilpy.structural.substructure import substructure_units
    from civilpy.structural.substructure_layout import SubstructureLayout

    unit = substructure_units(layout)[1]
    geom = record.build(layout, unit)
    sub = SubstructureLayout(layout=layout, abutments=(), piers=(geom,))
    objs = substructure_emit(sub)

    f = r3.File3dm()
    f.Settings.ModelUnitSystem = r3.UnitSystem.Feet
    from civilpy.structural.rhino_bim import _prism_geometry, _cylinder_mesh
    layer_idx = {name: ensure_layer(f, name)
                 for name in sorted({o.layer for o in objs})}
    import math as _math
    for o in objs:
        a = r3.ObjectAttributes()
        a.LayerIndex = layer_idx[o.layer]
        for k, v in o.tags.items():
            a.SetUserString(k, str(v))
        if o.kind == "prism":
            f.Objects.AddMesh(_prism_geometry(r3, o.points, o.vector,
                                              mesh=True), a)
        elif o.kind == "cylinder":
            f.Objects.AddMesh(_cylinder_mesh(r3, o.points[0], o.points[1],
                                             o.radius_ft), a)
        elif o.kind == "polyline":
            pl = r3.Polyline()
            for p in o.points:
                pl.Add(*p)
            f.Objects.AddCurve(pl.ToPolylineCurve(), a)
        else:
            f.Objects.AddPoint(r3.Point3d(*o.points[0]), a)
    path = tmp_path / "hammerhead.3dm"
    assert f.Write(str(path), 7)

    back = read_bim_tags(path)
    caps = [t for t in back["components"]
            if t.get("bim.type") == "pier_cap"]
    assert len(caps) == 1
    assert caps[0]["pier_cap.tip_depth_ft"] == "2.5"
    assert [t for t in back["components"]
            if t.get("bim.type") == "column"]


def test_pier_metrics_sidecar(record, layout):
    from civilpy.structural.substructure import substructure_units

    unit = substructure_units(layout)[1]
    geom = record.build(layout, unit)
    m = pier_metrics(geom)

    assert m["cap_length_ft"] == pytest.approx(38.0)
    assert m["cap_depth_ft"] == pytest.approx(6.0)
    assert m["tip_depth_ft"] == pytest.approx(2.5)
    assert m["stem_height_ft"] == pytest.approx(22.0)
    assert m["n_columns"] == 1 and m["n_seats"] == 5
    # stem volume: 6 ft x 5 ft x 22 ft
    assert m["stem_volume_cy"] == pytest.approx(6.0 * 5.0 * 22.0 / 27.0,
                                                rel=1e-3)
    assert m["footing_volume_cy"] == pytest.approx(
        14.0 * 12.0 * 3.5 / 27.0, rel=1e-3)
    assert m["concrete_cy"] > m["cap_volume_cy"] + m["stem_volume_cy"]
    # pier height: cap top down to the footing bottom
    assert m["height_ft"] == pytest.approx(
        geom.cap.origin[2] - (geom.footings[0].z_top - 3.5))
    # JSON-safe: the sidecar lands next to the JSONB record
    json.dumps(m)
