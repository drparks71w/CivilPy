#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the project-object Spec records: JSON round-trip, validation
(including the ISO-date and nested-schedule rules), the era-standards
lookup, and the versioned similarity feature export."""

import json

import pytest

from civilpy.structural.bim_spec import Provenance
from civilpy.structural.project_spec import (
    FEATURES_VERSION,
    EraStandardsRecord,
    MOTRecord,
    ProjectRecord,
    RERecord,
    StandardRef,
    SurveyRecord,
)


@pytest.fixture()
def era() -> EraStandardsRecord:
    return EraStandardsRecord(
        spec_year=2019,
        scds=(StandardRef(code="SBR-1-13", date="2018-07-20"),
              StandardRef(code="EXJ-4-87", date=None)),
        plan_inserts=(StandardRef(code="PIS-2019-01", date="2019-01-18"),),
        sbd_set=(StandardRef(code="CS-1-08", date="2008-07-18"),),
        bdm_edition="2020", ld_vol1_edition="2018")


@pytest.fixture()
def record(era) -> ProjectRecord:
    return ProjectRecord(
        pid="115840", sfns=("2701200", "2701219"), district=5,
        county="LIC", route="SR-16", letting_date="2023-04-12",
        work_category="bridge replacement", era=era,
        mot=MOTRecord(scheme="part_width", n_phases=2,
                      barrier_types=("PCB-91",), lanes_maintained=2,
                      min_lane_width_ft=11.0),
        real_estate=RERecord(n_parcels=6, n_takes_fee=2,
                             n_takes_temporary_easement=4,
                             n_utility_relocations=1),
        survey=SurveyRecord(horizontal_datum="NAD83(2011)",
                            vertical_datum="NAVD88"),
        provenance=Provenance(source="plans", doc_id="TIMS-115840",
                              sheet="1"))


# ── round-trip + validation ───────────────────────────────────────────────

def test_json_round_trip(record):
    doc = record.to_dict()
    assert doc["bim.type"] == "project"
    assert doc["subtype"] == "record"
    wire = json.loads(json.dumps(doc))
    back = ProjectRecord.from_dict(wire)
    assert back == record
    # the JSONB query paths the application side promotes/filters on
    assert wire["era"]["spec_year"] == 2019
    assert wire["era"]["scds"][0]["code"] == "SBR-1-13"
    assert wire["mot"]["scheme"] == "part_width"
    assert wire["sfns"] == ["2701200", "2701219"]


def test_from_dict_rejects_wrong_element(record):
    with pytest.raises(ValueError, match="not a project/record"):
        ProjectRecord.from_dict({"bim.type": "pier",
                                 "subtype": "hammerhead"})


def test_validate_clean(record):
    assert record.validate() == []
    record.validate(strict=True)


def test_validate_catches_bad_data(record):
    doc = record.to_dict()
    doc["pid"] = "  "                                  # blank
    doc["letting_date"] = "04/12/2023"                 # not ISO
    doc["mot"]["scheme"] = "hope"                      # enum
    doc["era"]["scds"][1]["date"] = "sometime in 87"   # nested schedule
    bad = ProjectRecord.from_dict(doc)
    problems = bad.validate()
    assert any("pid: blank" in p for p in problems)
    assert any("letting_date" in p and "ISO" in p for p in problems)
    assert any("mot.scheme" in p and "hope" in p for p in problems)
    assert any("era.scds[1].date" in p for p in problems)
    with pytest.raises(ValueError):
        bad.validate(strict=True)


def test_optional_components_default_none():
    rec = ProjectRecord(pid="99999")
    assert rec.validate() == []
    assert rec.era is None and rec.mot is None
    assert rec.provenance is not None       # stamped by __post_init__
    back = ProjectRecord.from_dict(json.loads(json.dumps(rec.to_dict())))
    assert back == rec


def test_sfns_entries_guarded():
    rec = ProjectRecord(pid="1", sfns=("2701200", ""))
    assert any("sfns" in p for p in rec.validate())


# ── era-standards lookup ──────────────────────────────────────────────────

def test_standard_date_lookup(era):
    assert era.standard_date("SBR-1-13") == "2018-07-20"
    assert era.standard_date("sbr-1-13 ") == "2018-07-20"   # normalized
    assert era.standard_date("EXJ-4-87") is None            # listed undated
    assert era.standard_date("CS-1-08") == "2008-07-18"     # sbd_set
    assert era.standard_date("PIS-2019-01") == "2019-01-18"  # plan insert
    assert era.standard_date("XYZ-9-99") is None


# ── similarity feature export ─────────────────────────────────────────────

def test_features_flat_and_versioned(record):
    f = record.features()
    assert f["features_version"] == FEATURES_VERSION
    # JSON scalars only — the contract the PCA pipeline relies on
    assert all(v is None or isinstance(v, (int, float, str))
               for v in f.values())
    assert f["n_bridges"] == 2
    assert f["district"] == "5"            # categorical, not numeric
    assert f["letting_year"] == 2023
    assert f["spec_year"] == 2019
    assert f["n_scds"] == 2
    assert f["mot_scheme"] == "part_width"
    assert f["mot_temp_structure"] == 0
    assert f["re_parcels"] == 6


def test_features_sparse_record():
    f = ProjectRecord(pid="1", era=EraStandardsRecord(spec_year=1957)).features()
    assert f["letting_year"] == 1957       # spec year stands in
    assert f["mot_scheme"] is None
    assert f["n_bridges"] == 0
