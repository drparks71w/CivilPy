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


# ── Phase-6 breadth: bent pier, pile bent, seat abutment ─────────────────

from civilpy.structural.bim_spec import (  # noqa: E402
    BENT_PIER_CHECK_INPUTS,
    PILE_BENT_CHECK_INPUTS,
    SEAT_ABUTMENT_CHECK_INPUTS,
    BentPierRecord,
    PileBentRecord,
    PileRecord,
    SeatAbutmentRecord,
    WingwallRecord,
    abutment_metrics,
)


@pytest.fixture()
def bent_cap() -> PierCapRecord:
    """A bent/pile-bent/abutment cap: governing tie in the bottom chord."""
    return PierCapRecord(span_ft=36.0, depth_ft=4.0, thickness_ft=3.5,
                         tie_bar_size=9, tie_bar_count=8, tie_at_top=False)


@pytest.fixture()
def bent_record(bent_cap) -> BentPierRecord:
    return BentPierRecord(
        pier_cap=bent_cap,
        column=PierStemRecord(height_ft=18.0, bars_area_in2=8.0,
                              diameter_in=36.0),
        column_xs_ft=(6.0, 18.0, 30.0),
        footing=FootingRecord(length_ft=9.0, width_ft=9.0,
                              thickness_ft=3.0))


@pytest.fixture()
def pile_bent_record(bent_cap) -> PileBentRecord:
    return PileBentRecord(
        pier_cap=bent_cap,
        piles=PileRecord(xs_ft=(2.0, 10.0, 18.0, 26.0, 34.0)))


@pytest.fixture()
def abutment_record(bent_cap) -> SeatAbutmentRecord:
    return SeatAbutmentRecord(
        cap=bent_cap,
        piles=PileRecord(xs_ft=(2.0, 10.0, 18.0, 26.0, 34.0),
                         shape="HP10X42"),
        wingwall=WingwallRecord(length_ft=12.0, stem_height_ft=8.0,
                                stem_thickness_ft=1.5, base_width_ft=6.0,
                                footing_thickness_ft=2.0))


def test_breadth_round_trips(bent_record, pile_bent_record,
                             abutment_record):
    for rec in (bent_record, pile_bent_record, abutment_record):
        assert rec.validate() == []
        wire = json.loads(json.dumps(rec.to_dict()))
        assert type(rec).from_dict(wire) == rec
    assert bent_record.to_dict()["subtype"] == "bent"
    assert pile_bent_record.to_dict()["subtype"] == "pile_bent"
    doc = abutment_record.to_dict()
    assert doc["bim.type"] == "abutment" and doc["subtype"] == "seat"
    # identity guard: a pier document cannot load as an abutment
    with pytest.raises(ValueError, match="not a abutment/seat"):
        SeatAbutmentRecord.from_dict(bent_record.to_dict())


def test_breadth_cross_validation(bent_record, pile_bent_record):
    doc = bent_record.to_dict()
    doc["column_xs_ft"] = [6.0]                    # one column = hammerhead
    problems = BentPierRecord.from_dict(doc).validate()
    assert any(">= 2 columns" in p for p in problems)

    doc["column_xs_ft"] = [6.0, 99.0]              # off the cap end
    problems = BentPierRecord.from_dict(doc).validate()
    assert any("outside the cap span" in p for p in problems)

    doc2 = pile_bent_record.to_dict()
    doc2["piles"]["xs_ft"] = []
    problems = PileBentRecord.from_dict(doc2).validate()
    assert any("at least one pile" in p for p in problems)


# every (element, article) pair resolves against its own record schema
_BREADTH_MAPS = [
    (BentPierRecord, BENT_PIER_CHECK_INPUTS),
    (PileBentRecord, PILE_BENT_CHECK_INPUTS),
    (SeatAbutmentRecord, SEAT_ABUTMENT_CHECK_INPUTS),
]


@pytest.mark.parametrize(
    "cls,mapping,article",
    [(cls, m, a) for cls, m in _BREADTH_MAPS for a in m],
    ids=lambda v: getattr(v, "__name__", None) or (
        v if isinstance(v, str) else None))
def test_breadth_check_inputs_resolve(cls, mapping, article):
    """The §3 forcing function for the Phase-6 elements — same contract
    as the hammerhead test: check exists, required params mapped, mapped
    names real, referenced paths on the schema."""
    from civilpy.structural.aashto import lrfd

    fn = lrfd.ARTICLES.get(article)
    assert fn is not None, f"{article} missing from the ported ARTICLES"

    sig = inspect.signature(fn)
    m = mapping[article]
    required = {p.name for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty}
    assert not required - set(m), (
        f"{article}: required inputs {sorted(required - set(m))} have no "
        f"Spec-field resolution on {cls.__name__}")
    assert not set(m) - set(sig.parameters), (
        f"{article}: mapped names {sorted(set(m) - set(sig.parameters))} "
        f"are not parameters of {fn.__name__}")
    schema = record_paths(cls)
    for param, entry in m.items():
        paths = ((entry[1],) if entry[0] == "field"
                 else entry[1] if entry[0] == "derived" else ())
        for path in paths:
            assert path in schema, (
                f"{article}.{param}: path {path!r} not on {cls.__name__}")


def test_pile_check_runs_from_record_inputs(pile_bent_record):
    """The pile compression check resolves a_g / r_y from the stored HP
    label and runs — the first exercise of 6.9.4.1.1 from a record."""
    from civilpy.structural.aashto import lrfd
    from civilpy.structural.steel import SteelSection

    p = pile_bent_record.piles
    hp = SteelSection(p.shape)
    a_g = float(hp.area.magnitude)
    r_y = float(hp.r_y.magnitude)
    kl_over_r = 1.0 * max(p.unbraced_length_ft, 1.0) * 12.0 / r_y
    res = lrfd.ARTICLES["6.9.4.1.1"](a_g=a_g, f_y=p.fy_ksi,
                                     kl_over_r=kl_over_r)
    assert res.capacity > 0.0


def test_bent_builds_placed_geometry(bent_record, layout):
    from civilpy.structural.substructure import substructure_units

    unit = substructure_units(layout)[1]
    geom = bent_record.build(layout, unit)
    assert len(geom.columns) == 3 and len(geom.footings) == 3
    assert not geom.piles
    m = pier_metrics(geom)
    assert m["n_columns"] == 3
    assert m["stem_height_ft"] == pytest.approx(18.0)
    # three 36 in circular columns
    import math
    one = math.pi * 1.5 ** 2 * 18.0 / 27.0
    assert m["stem_volume_cy"] == pytest.approx(3 * one, rel=1e-3)
    json.dumps(m)


def test_pile_bent_builds_placed_geometry(pile_bent_record, layout):
    from civilpy.structural.substructure import substructure_units

    unit = substructure_units(layout)[1]
    geom = pile_bent_record.build(layout, unit)
    assert not geom.columns and len(geom.piles) == 5
    assert all(p.shape == "HP12X53" for p in geom.piles)
    m = pier_metrics(geom)
    assert m["n_piles"] == 5
    assert m["pile_total_lf"] == pytest.approx(5 * 40.0)
    json.dumps(m)


def test_abutment_builds_placed_geometry(abutment_record, layout):
    from civilpy.structural.substructure import substructure_units

    unit = substructure_units(layout)[0]        # the rear abutment
    geom = abutment_record.build(layout, unit)
    assert len(geom.piles) == 5
    assert geom.backwall is not None and geom.backwall.height_ft > 0.0
    assert len(geom.wingwalls) == 4             # stem + footing, both ends
    m = abutment_metrics(geom)
    assert m["n_piles"] == 5 and m["pile_total_lf"] == pytest.approx(200.0)
    assert m["backwall_height_ft"] > 0.0
    assert m["wingwall_volume_cy"] > 0.0
    assert m["concrete_cy"] > m["cap_volume_cy"]
    assert m["height_ft"] > m["cap_depth_ft"]
    json.dumps(m)


def test_breadth_records_emit_tagged_objects(bent_record, pile_bent_record,
                                             abutment_record, layout):
    """All three breadth elements flow through the tagged emit — piles,
    backwall, and wingwalls land as objects with bim.type tags."""
    from civilpy.structural.rhino_bim import substructure_emit
    from civilpy.structural.substructure import substructure_units
    from civilpy.structural.substructure_layout import SubstructureLayout

    units = substructure_units(layout)
    sub = SubstructureLayout(
        layout=layout,
        abutments=(abutment_record.build(layout, units[0]),),
        piers=(bent_record.build(layout, units[1]),))
    kinds = {o.tags.get("bim.type") for o in substructure_emit(sub)}
    assert {"pier_cap", "column", "footing", "abutment_cap", "backwall",
            "wingwall", "pile"} <= kinds


# ══ Phase-6a: girder record + beam-customization schema spaces (§3a) ═════════

import math  # noqa: E402

from civilpy.structural.bim_spec import (  # noqa: E402
    GIRDER_CHECK_INPUTS,
    BearingStiffenerRecord,
    CompositeRecord,
    CrossFrameRecord,
    FieldSpliceRecord,
    GirderSectionRecord,
    LongitudinalStiffenerRecord,
    PlateSegmentRecord,
    SteelGirderRecord,
    TransverseStiffenerRecord,
    girder_metrics,
)


@pytest.fixture()
def girder() -> SteelGirderRecord:
    """A built-up plate girder carrying every §3a customization."""
    return SteelGirderRecord(
        section=GirderSectionRecord(
            web_depth_in=54.0, web_thickness_in=0.5,
            top_flange_width_in=16.0, top_flange_thickness_in=1.0,
            bot_flange_width_in=18.0, bot_flange_thickness_in=1.25,
            fyc_ksi=50.0, fyw_ksi=50.0),
        length_ft=160.0, grade="Grade 50W",
        plates=(
            PlateSegmentRecord(0.0, 80.0, 54.0, 0.5, 16.0, 1.0, 18.0, 1.25),
            PlateSegmentRecord(80.0, 160.0, 54.0, 0.5, 16.0, 1.25, 18.0, 1.5)),
        composite=CompositeRecord(effective_width_in=96.0),
        transverse_stiffener=TransverseStiffenerRecord(
            plate_width_in=6.0, plate_thickness_in=0.5, spacing_in=72.0),
        bearing_stiffener=BearingStiffenerRecord(
            plate_width_in=7.0, plate_thickness_in=0.625, pairs=1),
        longitudinal_stiffener=LongitudinalStiffenerRecord(
            plate_width_in=5.0, plate_thickness_in=0.5,
            location_from_top_flange_in=18.0),
        cross_frame=CrossFrameRecord(
            member_shape="L4X4X1/2", member_length_ft=8.0, spacing_ft=20.0),
        splice=FieldSpliceRecord(
            station_ft=80.0, flange_width_left_in=16.0,
            flange_width_right_in=16.0, flange_thickness_in=1.0,
            web_depth_in=54.0, web_thickness_left_in=0.5,
            web_thickness_right_in=0.5),
        provenance=Provenance(source="brr"))


def test_girder_round_trips(girder):
    doc = girder.to_dict()
    assert doc["bim.type"] == "girder" and doc["subtype"] == "steel"
    wire = json.loads(json.dumps(doc))
    assert SteelGirderRecord.from_dict(wire) == girder
    # nested + tuple-of-record fields survive the wire
    assert wire["section"]["web_depth_in"] == 54.0
    assert wire["plates"][1]["bot_flange_thickness_in"] == 1.5
    assert wire["splice"]["station_ft"] == 80.0
    with pytest.raises(ValueError, match="not a girder/steel"):
        SteelGirderRecord.from_dict({"bim.type": "pier", "subtype": "bent"})


def test_girder_validate_clean(girder):
    assert girder.validate() == []
    girder.validate(strict=True)
    # minimal girder: just a cataloged section, no customizations
    minimal = SteelGirderRecord(
        section=GirderSectionRecord(label="W36X150"), length_ft=80.0)
    assert minimal.validate() == []
    assert minimal.provenance.source == "manual"


def test_girder_section_is_label_xor_plates():
    both = GirderSectionRecord(label="W36X150", web_depth_in=36.0,
                               web_thickness_in=0.6, top_flange_width_in=12.0,
                               top_flange_thickness_in=0.9,
                               bot_flange_width_in=12.0,
                               bot_flange_thickness_in=0.9)
    assert any("either a catalog label" in p for p in both.validate())
    neither = GirderSectionRecord()
    assert any("either a catalog label" in p for p in neither.validate())


def test_girder_catches_bad_data_and_plate_gaps(girder):
    doc = girder.to_dict()
    doc["section"]["web_thickness_in"] = -0.5           # bound
    doc["grade"] = "Grade 999"                          # enum
    doc["plates"][1]["x_start_ft"] = 90.0               # gap after 80 ft
    bad = SteelGirderRecord.from_dict(doc)
    problems = bad.validate()
    assert any("section.web_thickness_in" in p and "> 0" in p
               for p in problems)
    assert any("grade" in p and "Grade 999" in p for p in problems)
    assert any("gap/overlap" in p for p in problems)


def test_girder_section_resolve_catalog_and_plates(girder):
    d, t_w, b_fc, t_fc = girder.section.resolve()
    assert (d, t_w, b_fc, t_fc) == (54.0, 0.5, 16.0, 1.0)
    cat = GirderSectionRecord(label="W36X150")
    d2, t_w2, b_fc2, t_fc2 = cat.resolve()
    assert d2 == pytest.approx(35.9) and b_fc2 == pytest.approx(12.0)


def test_girder_field_metadata_rides_on_the_field():
    from dataclasses import fields as dfields

    by_name = {f.name: f for f in dfields(CrossFrameRecord)}
    assert by_name["frame_type"].metadata["enum"] == ("X", "K", "bent_plate")
    assert "6.9.4.1.1" in by_name["member_shape"].metadata["checks"]
    sec = {f.name: f for f in dfields(GirderSectionRecord)}
    assert sec["web_depth_in"].metadata["unit"] == "in"


# ── check coverage: the §3 forcing function, §3a elements ─────────────────

#: Every ported LRFD check that consumes a steel girder line.  6.7.4
#: (cross-frame spacing) and 6.10.11.3 (longitudinal stiffener) are absent by
#: design -- not yet in the ported library, so their fields are quantity space.
GIRDER_CHECKS = (
    "6.10.8.2.2", "6.10.8.2.3", "6.10.9",          # section: flange/LTB/web
    "6.10.10.1.2", "6.10.10.4",                    # composite studs
    "6.10.11.2.3",                                 # bearing stiffener
    "6.8.2.1", "6.9.4.1.1",                        # cross-frame members
    "6.13.6.1.3b", "6.13.6.1.3c", "6.13.6.1.4",    # field splice
)


def test_every_girder_check_is_mapped():
    assert set(GIRDER_CHECK_INPUTS) == set(GIRDER_CHECKS)


@pytest.mark.parametrize("article", GIRDER_CHECKS)
def test_girder_check_inputs_resolve(article):
    from civilpy.structural.aashto import lrfd

    fn = lrfd.ARTICLES.get(article)
    assert fn is not None, f"{article} missing from the ported ARTICLES"

    sig = inspect.signature(fn)
    mapping = GIRDER_CHECK_INPUTS[article]
    required = {p.name for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty}
    assert not required - set(mapping), (
        f"{article} ({fn.__name__}): required inputs "
        f"{sorted(required - set(mapping))} have no Spec-field resolution")
    assert not set(mapping) - set(sig.parameters), (
        f"{article}: mapped names {sorted(set(mapping) - set(sig.parameters))}"
        f" are not parameters of {fn.__name__}")
    schema = record_paths(SteelGirderRecord)
    for param, entry in mapping.items():
        paths = ((entry[1],) if entry[0] == "field"
                 else entry[1] if entry[0] == "derived" else ())
        for path in paths:
            assert path in schema, (
                f"{article}.{param}: path {path!r} not on SteelGirderRecord")


def test_girder_checks_run_from_record_inputs(girder):
    """First exercise of the steel port from record-resolved inputs: the
    section, composite, cross-frame member, and splice checks all produce
    sane numbers from Spec fields alone."""
    from civilpy.structural.aashto import lrfd
    from civilpy.structural.steel import SteelSection

    A = lrfd.ARTICLES
    d, t_w, b_fc, t_fc = girder.section.resolve()
    sec = girder.section
    assert A["6.10.8.2.2"](b_fc=b_fc, t_fc=t_fc, f_yc=sec.fyc_ksi,
                           f_yw=sec.fyw_ksi).capacity > 0.0
    assert A["6.10.9"](d_web=d, t_w=t_w, f_yw=sec.fyw_ksi).capacity > 0.0

    cf = girder.cross_frame
    m = SteelSection(cf.member_shape)
    a_g, r_y = float(m.area.magnitude), float(m.r_y.magnitude)
    assert A["6.8.2.1"](a_g=a_g, f_y=cf.fy_ksi).capacity > 0.0
    kl_r = 1.0 * cf.member_length_ft * 12.0 / r_y
    assert A["6.9.4.1.1"](a_g=a_g, f_y=cf.fy_ksi,
                          kl_over_r=kl_r).capacity > 0.0

    comp = girder.composite
    e_c = 57.0 * math.sqrt(comp.deck_fc_ksi * 1000.0) / 1000.0
    assert A["6.10.10.4"](d_stud=comp.stud_diameter_in,
                          f_c=comp.deck_fc_ksi, e_c=e_c).capacity > 0.0

    sp = girder.splice
    plates = A["6.13.6.1.3b"](
        flange_width_left=sp.flange_width_left_in,
        flange_width_right=sp.flange_width_right_in,
        flange_thickness=sp.flange_thickness_in,
        web_thickness_left=sp.web_thickness_left_in,
        web_thickness_right=sp.web_thickness_right_in)
    assert plates is not None


def test_girder_metrics_sidecar(girder):
    m = girder_metrics(girder)
    assert m["length_ft"] == 160.0
    assert m["is_plate_girder"] is True and m["section_label"] is None
    assert m["web_depth_in"] == 54.0
    assert m["is_composite"] is True
    assert m["n_plate_segments"] == 2
    assert m["has_bearing_stiffeners"] is True
    assert m["has_longitudinal_stiffener"] is True
    assert m["n_splices"] == 1
    assert m["cross_frame_bays"] == 8          # 160 ft / 20 ft
    json.dumps(m)


def test_girder_to_bridge_input_catalog_and_plate(girder):
    from civilpy.structural.bridge_layout import BridgeInput

    cat = SteelGirderRecord(
        section=GirderSectionRecord(label="W36X150"), length_ft=80.0,
        grade="Grade 50W", composite=CompositeRecord())
    bi = cat.to_bridge_input(girder_count=5, girder_spacing_ft=8.0,
                             overhang_ft=3.0)
    assert isinstance(bi, BridgeInput)
    assert bi.girder_label == "W36X150" and bi.composite is True
    # the plate-section girder can't feed the current prismatic engine yet
    with pytest.raises(NotImplementedError, match="plate-section emit"):
        girder.to_bridge_input(girder_count=5, girder_spacing_ft=8.0,
                               overhang_ft=3.0)
