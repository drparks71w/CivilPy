#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the Tier A parametric records (SlabBridgeRecord /
BoxBeamBridgeRecord): JSON round-trip, envelope validation against the
cataloged design tables, reconstitution to the emit inputs, and the
span → box selection helper."""

import json

import pytest

from civilpy.structural.bim_spec import (
    BoxBeamBridgeRecord,
    Provenance,
    SlabBridgeRecord,
    select_box,
)


class TestSlabBridgeRecord:
    @pytest.fixture()
    def record(self):
        return SlabBridgeRecord(
            span_ft=24, width_ft=32.0, skew_deg=10.0,
            standard="SB-1-24", standard_year=2024,
            provenance=Provenance(source="snbi"))

    def test_round_trip(self, record):
        doc = json.loads(json.dumps(record.to_dict()))
        assert doc["bim.type"] == "bridge"
        assert doc["subtype"] == "slab"
        assert SlabBridgeRecord.from_dict(doc) == record

    def test_validate_clean(self, record):
        assert record.validate() == []

    def test_envelope_enforced(self):
        bad = SlabBridgeRecord(span_ft=55, width_ft=32.0, skew_deg=40.0)
        problems = bad.validate()
        assert any("span_ft" in p and "design table" in p
                   for p in problems)
        assert any("skew_deg" in p for p in problems)

    def test_to_input_drives_emit(self, record, tmp_path):
        # writes a real .3dm, so it needs the optional Rhino interchange
        # dependency (civilpy[rhino]); the CI matrix installs only
        # [db,geo,web,jupyter,validation]
        pytest.importorskip("rhino3dm")
        from civilpy.structural.rhino_slab import write_slab_bridge
        emit = write_slab_bridge(tmp_path / "s.3dm", record.to_input())
        # the standard's bar schedule came out of the table, not the record
        assert len(emit.of_kind("rebar")) > 100
        assert (tmp_path / "s.3dm").exists()

    def test_snbi_provenance_source_allowed(self, record):
        assert record.provenance.source == "snbi"
        assert record.validate() == []


class TestSelectBox:
    def test_shallowest_covering_box(self):
        assert select_box(24) == "CB17-48"
        assert select_box(62) == "CB27-48"     # rounds up to 65
        assert select_box(90) == "CB42-48"

    def test_non_composite_family(self):
        assert select_box(62, composite=False) == "B27-48"

    def test_beyond_catalog(self):
        assert select_box(120) is None


class TestBoxBeamBridgeRecord:
    @pytest.fixture()
    def record(self):
        return BoxBeamBridgeRecord(box="CB27-48", span_ft=65.0, n_beams=9,
                                   skew_deg=15.0)

    def test_round_trip(self, record):
        doc = json.loads(json.dumps(record.to_dict()))
        assert doc["subtype"] == "box_beam"
        assert BoxBeamBridgeRecord.from_dict(doc) == record

    def test_validate_clean(self, record):
        assert record.validate() == []

    def test_designation_and_span_enforced(self):
        assert any("designation" in p for p in BoxBeamBridgeRecord(
            box="CB99-48", span_ft=65.0, n_beams=9).validate())
        assert any("not cataloged" in p for p in BoxBeamBridgeRecord(
            box="CB27-48", span_ft=95.0, n_beams=9).validate())

    def test_to_input_drives_emit(self):
        from civilpy.structural.rhino_box_bim import box_beam_bridge_emit
        rec = BoxBeamBridgeRecord(box="CB27-48", span_ft=65.0, n_beams=9)
        emit = box_beam_bridge_emit(rec.to_input())
        assert len(emit.objects) > 0

    def test_skewed_record_stores_and_emits(self, record):
        # the record keeps the bridge's true skew, and the emit now lays
        # the plan out on the bias (formerly a loud decline)
        from civilpy.structural.rhino_box_bim import box_beam_bridge_emit
        assert record.validate() == []
        emit = box_beam_bridge_emit(record.to_input())
        assert emit.doc_tags["bim.skew_deg"] == "15"

    def test_skew_beyond_standard_fails_validation(self):
        rec = BoxBeamBridgeRecord(box="CB27-48", span_ft=65.0, n_beams=9,
                                  skew_deg=40.0)
        assert any("skew" in p for p in rec.validate())
