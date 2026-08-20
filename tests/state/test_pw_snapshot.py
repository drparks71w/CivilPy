"""SnapshotClient: the offline ProjectWise backend."""
import json

import pytest

from civilpy.state.ohio.DOT.pw_snapshot import (
    SnapshotClient,
    SnapshotOffline,
    load_closed_samples,
    load_file_samples,
)
from tests.state.pw_testdata import PATH, PID, RECON_RECORD, snapshot_project


class TestFromRecon:
    def test_resolve_and_children(self):
        client, path, pid = SnapshotClient.from_recon(RECON_RECORD)
        assert pid == PID
        root = client.resolve_path(path)
        assert root == 1000
        names = [n for n, _ in client.list_children(root)]
        assert "100-Planning" in names and "950-Reviews" in names

    def test_resolve_is_case_insensitive(self):
        client, path, _ = SnapshotClient.from_recon(RECON_RECORD)
        assert client.resolve_path(path.upper()) == 1000

    def test_documents_have_per_folder_doc_ids(self):
        client, _, _ = SnapshotClient.from_recon(RECON_RECORD)
        docs = client.list_documents(1110)          # Scopes
        assert [d["doc_id"] for d in docs] == [1, 2]
        assert docs[0]["folder_id"] == 1110
        assert docs[0]["filename"].endswith("ODOT Scope.xlsx")

    def test_unknown_folder_is_empty(self):
        client, _, _ = SnapshotClient.from_recon(RECON_RECORD)
        assert client.list_children(999999) == []
        assert client.list_documents(999999) == []

    def test_copy_out_raises_offline(self):
        client, _, _ = SnapshotClient.from_recon(RECON_RECORD)
        with pytest.raises(SnapshotOffline):
            client.copy_out(1110, 1, "/tmp")

    def test_pid_from_matched_because_when_folder_descriptive(self):
        record = dict(RECON_RECORD, project_folder="- FRA IR 70 12.00",
                      matched_because="PID 654321 in name/desc")
        _, _, pid = SnapshotClient.from_recon(record)
        assert pid == "654321"


class TestClosedShape:
    RECORD = {
        "path": "00 Closed, Inactive and Cancelled Projects\\District 06"
                "\\Franklin\\98765",
        "folder_id": 5000,
        "tree": {"files": ["root.txt"], "folders": {
            "100-Planning": {"files": [], "folders": {
                "Scopes": {"files": ["Scope.xlsx"], "folders": {}}}},
            "Truncated": "..budget..",
        }},
    }

    def test_nested_folders_dict_shape(self):
        client, path, pid = SnapshotClient.from_closed("98765", self.RECORD)
        root = client.resolve_path(path)
        assert root == 5000
        names = [n for n, _ in client.list_children(root)]
        assert names == ["100-Planning"]        # budget marker skipped
        scopes = client.resolve_path(path + "\\100-Planning\\Scopes")
        assert scopes < 0                       # synthetic id
        assert client.list_documents(scopes)[0]["filename"] == "Scope.xlsx"


class TestLoaders:
    def test_load_file_samples(self, tmp_path):
        p = tmp_path / "district_file_samples.json"
        p.write_text(json.dumps({"District 06": [RECON_RECORD]}))
        projects = load_file_samples(p)
        assert list(projects) == [PID]
        project = projects[PID]
        assert project.project_path == PATH
        assert len(project.walk()) > 10

    def test_load_closed_samples(self, tmp_path):
        p = tmp_path / "closed_tree_samples.json"
        p.write_text(json.dumps({"98765": TestClosedShape.RECORD}))
        projects = load_closed_samples(p)
        assert projects["98765"].query(series="planning",
                                       area="Scopes")[0]["filename"] \
            == "Scope.xlsx"


class TestProjectIntegration:
    def test_full_object_model_offline(self):
        project = snapshot_project()
        assert [c.name for c in project.root.children][0] == "100-Planning"
        assert len(project.sfns) == 1
        assert project.sfns[0].sfn == "1234567"

    def test_survey_roundtrip(self):
        """survey() out of a snapshot can rebuild a (sampled) snapshot."""
        project = snapshot_project()
        dump = project.survey(max_depth=6)
        client, path, pid = SnapshotClient.from_survey(dump)
        assert client.resolve_path(path) == 1000
        assert pid == PID
