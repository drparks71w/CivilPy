"""MCP server core API (snapshot store; the mcp SDK itself is optional)."""
import json

import pytest

from civilpy.mcp.pw_server import (
    LiveStore,
    SnapshotStore,
    describe_project,
    list_projects,
    project_checklist,
    query_documents,
    review_summary,
)
from tests.state.pw_testdata import PID, RECON_RECORD, SFN


@pytest.fixture()
def store(tmp_path):
    (tmp_path / "district_file_samples.json").write_text(
        json.dumps({"District 06": [RECON_RECORD]}))
    return SnapshotStore(tmp_path)


class TestSnapshotStore:
    def test_lists_projects(self, store):
        assert list_projects(store) == [PID]

    def test_missing_pid_is_keyerror(self, store):
        with pytest.raises(KeyError):
            store.get("000000")

    def test_empty_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SnapshotStore(tmp_path / "nothing")


class TestCoreApi:
    def test_describe(self, store):
        d = describe_project(store, PID)
        resources = {b["resource"] for b in d["branches"]}
        assert f"pw://{PID}/engineering/structures/{SFN}" in resources
        assert d["n_documents"] == 22

    def test_query_by_resource(self, store):
        docs = query_documents(
            store, resource=f"pw://{PID}/engineering/structures/{SFN}")
        assert len(docs) == 4
        assert all(d["sfn"] == SFN for d in docs)

    def test_query_filters_compose_with_resource(self, store):
        docs = query_documents(
            store, resource=f"pw://{PID}/reviews", kind="comments")
        assert len(docs) == 2

    def test_query_needs_target(self, store):
        with pytest.raises(ValueError):
            query_documents(store)

    def test_query_results_carry_clickable_links(self, store):
        doc = query_documents(store, pid=PID, series="planning")[0]
        assert doc["link"].startswith("pw:\\\\ohiodot-pw.bentley.com")
        assert doc["link"].endswith(doc["filename"])

    def test_checklist_with_stage_appends_deliverables(self, store):
        result = project_checklist(store, PID, stage=2)
        checks = {f["check"] for f in result["findings"]}
        assert "stage_2:load_rating_files" in checks

    def test_query_limit(self, store):
        assert len(query_documents(store, pid=PID, limit=3)) == 3

    def test_checklist(self, store):
        result = project_checklist(store, PID, stage=3)
        assert result["summary"].get("ok", 0) >= 9
        checks = {f["check"] for f in result["findings"]}
        assert "load_rating" in checks

    def test_review_summary(self, store):
        result = review_summary(store, PID)
        assert any(r["comments_addressed"] for r in result["rounds"])


class TestLiveStore:
    def test_path_map_resolution(self):
        store = LiveStore({PID: "01 Active Projects\\District 06"
                                "\\Franklin\\" + PID})
        project = store.get(PID)
        assert project.project_path.endswith(PID)
        assert store.get(PID) is project          # cached

    def test_from_availability(self, tmp_path):
        csv = tmp_path / "avail.csv"
        csv.write_text("pid,found,path\n"
                       f"{PID},True,01 Active Projects\\D6\\{PID}\n"
                       "999,False,\n")
        store = LiveStore.from_availability(csv)
        assert store.pids() == [PID]


class TestServerWiring:
    def test_build_server_requires_mcp(self, store):
        pytest.importorskip("mcp")
        from civilpy.mcp.pw_server import build_server
        server = build_server(store)
        assert server is not None
