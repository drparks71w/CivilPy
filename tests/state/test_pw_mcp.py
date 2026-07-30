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
from tests.state.pw_testdata import DATASOURCE, PID, RECON_RECORD, SFN


@pytest.fixture()
def store(tmp_path):
    (tmp_path / "district_file_samples.json").write_text(
        json.dumps({"District 06": [RECON_RECORD]}))
    return SnapshotStore(tmp_path, datasource=DATASOURCE)


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
        assert doc["link"].startswith(f"pw:\\\\{DATASOURCE}")
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


class TestRegisteredToolsAndResources:
    """The FastMCP tools/resources are closures over the store, so exercise
    them through the registry the way a client would reach them."""

    @pytest.fixture()
    def server(self, store):
        pytest.importorskip("mcp")
        from civilpy.mcp.pw_server import build_server
        return build_server(store)

    @pytest.mark.anyio
    async def _tools(self, server):
        return {t.name: t for t in await server.list_tools()}

    def test_all_five_tools_registered(self, server):
        import asyncio
        names = {t.name for t in asyncio.run(server.list_tools())}
        assert names == {"pw_projects", "pw_describe", "pw_documents",
                         "pw_checklist", "pw_review_summary"}

    def test_every_tool_carries_a_description(self, server):
        import asyncio
        for t in asyncio.run(server.list_tools()):
            assert t.description and t.description.strip()

    def test_tool_bodies_delegate_to_the_core_api(self, server, store):
        """Calling each tool must return the same payload as the plain
        function it wraps."""
        import asyncio
        from civilpy.mcp.pw_server import (describe_project, list_projects,
                                           project_checklist, query_documents,
                                           review_summary)

        def texts(name, **kw):
            """FastMCP emits one content item per element of a list return."""
            return [c.text for c in asyncio.run(server.call_tool(name, kw))]

        def obj(name, **kw):
            return json.loads("".join(texts(name, **kw)))

        def roundtrip(value):
            return json.loads(json.dumps(value))

        # list-returning tools -> one text item per element
        assert texts("pw_projects") == list_projects(store)
        assert [json.loads(x) for x in
                texts("pw_documents", pid=PID, series="planning")] == \
            roundtrip(query_documents(store, pid=PID, series="planning"))
        # dict-returning tools -> a single JSON object
        assert obj("pw_describe", pid=PID) == \
            roundtrip(describe_project(store, PID))
        assert obj("pw_checklist", pid=PID) == \
            roundtrip(project_checklist(store, PID, stage=None))
        assert obj("pw_review_summary", pid=PID) == \
            roundtrip(review_summary(store, PID))

    def test_checklist_tool_passes_stage_through(self, server, store):
        import asyncio
        from civilpy.mcp.pw_server import project_checklist
        out = asyncio.run(server.call_tool("pw_checklist",
                                           {"pid": PID, "stage": 2}))
        payload = json.loads("".join(c.text for c in out))
        assert payload == json.loads(
            json.dumps(project_checklist(store, PID, stage=2)))
        assert payload["stage"] == 2

    def test_resources_render_json(self, server, store):
        import asyncio
        from civilpy.mcp.pw_server import describe_project
        body = asyncio.run(server.read_resource(f"pw://{PID}"))
        assert json.loads(body[0].content) == json.loads(
            json.dumps(describe_project(store, PID)))

    def test_series_resource_filters_by_series(self, server, store):
        import asyncio
        from civilpy.mcp.pw_server import query_documents
        body = asyncio.run(server.read_resource(f"pw://{PID}/planning"))
        assert json.loads(body[0].content) == json.loads(json.dumps(
            query_documents(store, pid=PID, series="planning")))


    def test_sfn_resource_scopes_to_one_structure(self, server, store):
        import asyncio
        from civilpy.mcp.pw_server import query_documents
        body = asyncio.run(server.read_resource(
            f"pw://{PID}/engineering/structures/{SFN}"))
        expected = query_documents(store, pid=PID, series="engineering",
                                   discipline="structures", sfn=SFN)
        assert json.loads(body[0].content) == json.loads(json.dumps(expected))
        assert expected, "fixture should carry structures documents"


class TestSnapshotStoreConstruction:
    def test_empty_directory_is_a_clear_error(self, tmp_path):
        from civilpy.mcp.pw_server import SnapshotStore
        with pytest.raises(FileNotFoundError, match="no snapshot JSONs"):
            SnapshotStore(tmp_path)

    def test_closed_samples_are_loaded_too(self, tmp_path):
        from civilpy.mcp.pw_server import SnapshotStore
        (tmp_path / "district_file_samples.json").write_text(
            json.dumps({"District 06": [RECON_RECORD]}))
        (tmp_path / "closed_tree_samples.json").write_text(
            json.dumps({}))
        assert SnapshotStore(tmp_path).pids() == [PID]


class TestMainEntryPoint:
    def test_snapshot_mode_from_env(self, tmp_path, monkeypatch):
        from civilpy.mcp import pw_server
        (tmp_path / "district_file_samples.json").write_text(
            json.dumps({"District 06": [RECON_RECORD]}))
        monkeypatch.setenv("CIVILPY_PW_SNAPSHOT", str(tmp_path))
        monkeypatch.delenv("CIVILPY_PW_PATHS", raising=False)
        built = {}

        class _FakeServer:
            def run(self):
                built["ran"] = True

        def _fake_build(store):
            built["store"] = store
            return _FakeServer()

        monkeypatch.setattr(pw_server, "build_server", _fake_build)
        pw_server.main()
        assert built["store"].pids() == [PID]

    def test_live_mode_from_path_map(self, tmp_path, monkeypatch):
        from civilpy.mcp import pw_server
        pmap = tmp_path / "paths.json"
        pmap.write_text(json.dumps({"112665": "01 Active Projects/x"}))
        monkeypatch.delenv("CIVILPY_PW_SNAPSHOT", raising=False)
        monkeypatch.setenv("CIVILPY_PW_PATHS", str(pmap))
        built = {}

        class _FakeServer:
            def run(self):
                built["ran"] = True

        def _fake_build(store):
            built["store"] = store
            return _FakeServer()

        monkeypatch.setattr(pw_server, "build_server", _fake_build)
        pw_server.main()
        assert built["store"].pids() == ["112665"]

    def test_falls_back_to_cwd(self, tmp_path, monkeypatch):
        from civilpy.mcp import pw_server
        (tmp_path / "district_file_samples.json").write_text(
            json.dumps({"District 06": [RECON_RECORD]}))
        monkeypatch.delenv("CIVILPY_PW_SNAPSHOT", raising=False)
        monkeypatch.delenv("CIVILPY_PW_PATHS", raising=False)
        monkeypatch.chdir(tmp_path)
        built = {}

        class _FakeServer:
            def run(self):
                built["ran"] = True

        def _fake_build(store):
            built["store"] = store
            return _FakeServer()

        monkeypatch.setattr(pw_server, "build_server", _fake_build)
        pw_server.main()
        assert built["store"].pids() == [PID]
