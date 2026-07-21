"""ODOT ProjectWise plan discovery — offline layer (grammars, inventory, joins).

Live PW calls (get_structures_sheets, pull_plan) need Windows + PW Explorer
and are exercised by the snbi_ui Bridge Plan Puller notebook instead.
"""
import csv

import pytest

from civilpy import projectwise as pw


# real strings from the 2026-07-21 on-box runs
ARCHIVE_ROWS = [
    {"folder": "/District 01", "doc_id": "472",
     "name": "D01-100242-PAU-00500-0-2015-00.pdf",
     "filename": "D01-100242-PAU-00500-0-2015-00.pdf",
     "desc": "PAU-100242.pdf", "size": "696628",
     "created": "2019-04-18 00:36:43.307",
     "updated": "2019-07-15 11:47:34.357", "folder_id": "8198"},
    {"folder": "/District 09", "doc_id": "9001",
     "name": "D09-78173-ADA-00052-21.77-2011-00.pdf",
     "filename": "D09-78173-ADA-00052-21.77-2011-00.pdf",
     "desc": "ADA-78173.pdf", "size": "123",
     "created": "", "updated": "", "folder_id": "8206"},
    {"folder": "/District 04", "doc_id": "9002",
     "name": "D04-105171-ATB-xx-x.xx-2022-00.pdf",
     "filename": "D04-105171-ATB-xx-x.xx-2022-00.pdf",
     "desc": "ATB-105171.pdf", "size": "5",
     "created": "", "updated": "", "folder_id": "8201"},
]


@pytest.fixture()
def inventory(tmp_path):
    path = tmp_path / "inv.csv"
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ARCHIVE_ROWS[0]))
        w.writeheader()
        w.writerows(ARCHIVE_ROWS)
    return pw.load_planvault_inventory(path)


def test_plan_set_grammar_parses_real_names():
    m = pw.PLAN_SET_GRAMMAR.search("D01-10150-PUT-114-1.82-1993-00.pdf")
    assert m["pid"] == "10150" and m["county"] == "PUT" and m["year"] == "1993"


def test_active_sheet_grammar_both_forms():
    m = pw.ACTIVE_SHEET_GRAMMAR.search("116581_SFN_2510774_SI001.dgn")
    assert (m["pid"], m["sfn"], m["sheet"]) == ("116581", "2510774", "SI001")
    m = pw.ACTIVE_SHEET_GRAMMAR.search("115418_4808224_BR100.pdf")
    assert (m["pid"], m["sfn"], m["sheet"]) == ("115418", "4808224", "BR100")


def test_parse_slm_implied_hundredths():
    assert pw.parse_slm("2292") == pytest.approx(22.92)
    assert pw.parse_slm("1.82") == pytest.approx(1.82)


def test_inventory_parses_keys(inventory):
    assert [r["pid"] for r in inventory] == ["100242", "78173", "105171"]
    assert inventory[0]["slm"] == pytest.approx(0.0)
    # grammar-less route/slm (the xx-x.xx placeholder row) falls back to desc
    assert inventory[2]["pid"] == "105171"


def test_find_plans_by_pid(inventory):
    assert len(pw.find_plans_by_pid("78173", inventory)) == 1
    assert len(pw.find_plans_by_pid("000078173", inventory)) == 1  # zero-pad safe
    assert pw.find_plans_by_pid("999999", inventory) == []


def test_find_plans_by_bridge_key_tolerance(inventory):
    hits = pw.find_plans_by_bridge_key("ADA", "52", 21.80, inventory, tol=0.20)
    assert len(hits) == 1 and hits[0]["slm_delta"] == pytest.approx(0.03)
    assert pw.find_plans_by_bridge_key("ADA", "52", 25.0, inventory) == []


def test_find_plans_by_sfn_offline(inventory):
    res = pw.find_plans_by_sfn("0102318", inventory, pids=["78173"],
                               bridge_name="ADA-00052-2292")
    assert len(res["pid_hits"]) == 1
    assert res["name_hits"] == []          # pid hit not double-reported
    res2 = pw.find_plans_by_sfn("0102318", inventory, pids=[],
                                bridge_name="ADA-00052-2177")
    assert len(res2["name_hits"]) == 1     # falls back to the name tier


def test_active_path_template():
    p = pw.ACTIVE_STRUCTURES_PATH.format(district="06", county="Franklin",
                                         pid="112665")
    assert "District 06\\Franklin\\112665\\400-Engineering" in p


def test_district_folder_anchors():
    assert pw.PLANVAULT_DISTRICT_FOLDERS["06"] == 8203
    assert len(pw.PLANVAULT_DISTRICT_FOLDERS) == 12


# --- schema-externalized project-DB query ------------------------------------

def test_load_definitions_unconfigured(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)  # no secrets.json
    assert pw.load_project_db_definitions() is None


def test_load_definitions_via_secrets(monkeypatch, tmp_path):
    import json
    defs = tmp_path / "defs.json"
    defs.write_text(json.dumps({"odbc": "DSN=x", "sfn_query": "q?",
                                "columns": ["sfn", "pid"]}))
    (tmp_path / "secrets.json").write_text(
        json.dumps({"PROJECT_DB_DEFINITIONS": str(defs)}))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert pw.load_project_db_definitions()["odbc"] == "DSN=x"


class _FakeCursor:
    def __init__(self, rows): self._rows = rows
    def execute(self, sql, *params): self.params = params
    def fetchall(self): return self._rows


class _FakeConn:
    def __init__(self, rows): self._rows = rows
    def cursor(self): return _FakeCursor(self._rows)
    def __enter__(self): return self
    def __exit__(self, *exc): return False


def test_query_projects_by_sfn_maps_generic_rows():
    defs = {"odbc": "DSN=x", "sfn_query": "SELECT ... WHERE s = ?",
            "columns": ["sfn", "pid", "label", "work_category", "status"]}
    rows = [("2510774 ", 116581.0, "FRA-270-22.65 Abutment Repair",
             "Bridge Preservation", "Active"),
            ("2510774", None, "no pid -> dropped", "", "")]
    out = pw.query_projects_by_sfn("2510774", definitions=defs,
                                   _connect=lambda cs, timeout: _FakeConn(rows))
    assert len(out) == 1
    assert out[0]["pid"] == "116581"           # float un-mangled
    assert out[0]["work_category"] == "Bridge Preservation"


def test_query_projects_unconfigured_and_failing(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert pw.query_projects_by_sfn("1") is None            # not configured
    defs = {"odbc": "DSN=x", "sfn_query": "q", "columns": ["pid"]}
    def boom(cs, timeout): raise OSError("off network")
    assert pw.query_projects_by_sfn("1", definitions=defs, _connect=boom) is None


def test_find_plans_by_sfn_prefers_project_db(inventory, monkeypatch):
    import civilpy.state.ohio.DOT.projectwise as mod
    monkeypatch.setattr(mod, "query_projects_by_sfn",
                        lambda sfn: [{"pid": "78173", "status": "Sold"}])
    res = pw.find_plans_by_sfn("0102318", inventory)
    assert res["pid_source"] == "project_db"
    assert len(res["pid_hits"]) == 1


def test_find_plans_by_sfn_falls_back_to_tims(inventory, monkeypatch):
    import civilpy.state.ohio.DOT.projectwise as mod
    monkeypatch.setattr(mod, "query_projects_by_sfn", lambda sfn: None)
    monkeypatch.setattr(mod, "sfn_to_pids", lambda sfn: ["100242"])
    res = pw.find_plans_by_sfn("x", inventory)
    assert res["pid_source"] == "tims" and len(res["pid_hits"]) == 1
