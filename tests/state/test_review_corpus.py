"""Phase-0 corpus assembly."""
import pandas as pd
import pytest

from civilpy.state.ohio.DOT.review_corpus import (
    build_review_corpus,
    document_rows,
)
from tests.state.pw_testdata import PID, snapshot_project


@pytest.fixture()
def project():
    return snapshot_project()


class TestDocumentRows:
    def test_one_row_per_review_document(self, project):
        rows = document_rows(project)
        assert len(rows) == 8
        assert all(r["pid"] == PID for r in rows)

    def test_classification_columns(self, project):
        rows = {r["filename"]: r for r in document_rows(project)}
        comments = rows[f"FRA-70_PID{PID}_S2_Comments.pdf"]
        assert comments["stage"] == "2"
        assert comments["kind"] == "comments"
        sts = rows["FRA-70 Structure Type Study.pdf"]
        assert "sts" in sts["review_types"]
        assert sts["dated"] == "2023-08-01"
        assert sts["resubmittal"] is True

    def test_resolution_files_flagged(self, project):
        rows = document_rows(project)
        res = [r for r in rows if r["is_resolution"]]
        assert len(res) == 1
        assert res[0]["filename"].endswith(".xlsx")


class TestBuildCorpus:
    def test_offline_documents_only(self, project):
        corpus = build_review_corpus([project])
        assert len(corpus.documents) == 8
        assert corpus.comments.empty

    def test_local_dir_parses_previous_pulls(self, project, tmp_path):
        # a previously pulled resolution workbook, matched by filename
        wb = pd.DataFrame([
            ["No.", "Comment", "Response", "Status"],
            [1, "Label the approach slab", "Added", "Closed"],
        ])
        name = f"20240201_FRA-{PID}_S2_Comment Resolution Form.xlsx"
        wb.to_excel(tmp_path / name, index=False, header=False)
        corpus = build_review_corpus([project], local_dir=tmp_path)
        assert len(corpus.comments) == 1
        row = corpus.comments.iloc[0]
        assert row["comment"] == "Label the approach slab"
        assert row["disposition_class"] == "revised"
        assert row["pid"] == PID
        assert row["stage"] == "2"

    def test_fetch_called_for_resolutions(self, project, tmp_path):
        pulled = []

        def fetch(folder_id, doc_id, dest):
            pulled.append((folder_id, doc_id))
            wb = pd.DataFrame([["No.", "Comment", "Response"],
                               [1, "Check camber diagram", "Revised"]])
            path = tmp_path / "pulled.xlsx"
            wb.to_excel(path, index=False, header=False)
            return path

        corpus = build_review_corpus([project], fetch=fetch,
                                     local_dir=tmp_path)
        assert len(pulled) == 1
        assert corpus.comments.iloc[0]["comment"] == "Check camber diagram"

    def test_fetch_errors_recorded(self, project, tmp_path):
        def fetch(folder_id, doc_id, dest):
            raise OSError("network gone")
        corpus = build_review_corpus([project], fetch=fetch,
                                     local_dir=tmp_path)
        assert "network gone" in corpus.comments.iloc[0]["error"]

    def test_max_pulls_budget(self, project, tmp_path):
        calls = []

        def fetch(folder_id, doc_id, dest):
            calls.append(1)
            raise OSError("should not be called")

        build_review_corpus([project], fetch=fetch, local_dir=tmp_path,
                            max_pulls=0)
        assert calls == []

    def test_log_coverage(self, project):
        log = pd.DataFrame([
            {"review_id": 1, "pid": int(PID), "stage": "2",
             "review_type": "Bridge - Detail Design"},
            {"review_id": 2, "pid": int(PID), "stage": "3",
             "review_type": "Bridge - Detail Design"},
            {"review_id": 3, "pid": 999999, "stage": "2",
             "review_type": "Study"},
        ])
        corpus = build_review_corpus([project], review_log=log)
        lm = corpus.log_matches
        assert len(lm) == 2                        # other PID dropped
        s2 = lm[lm.review_id == 1].iloc[0]
        assert s2["n_harvested_docs"] > 0
        assert s2["n_resolution_files"] == 1

    def test_save_falls_back_to_csv(self, project, tmp_path,
                                    monkeypatch):
        corpus = build_review_corpus([project])
        monkeypatch.setattr(pd.DataFrame, "to_parquet",
                            lambda self, *a, **k: (_ for _ in ()).throw(
                                ImportError("no engine")))
        written = corpus.save(tmp_path / "corpus")
        assert written and all(p.suffix == ".csv" for p in written)
