"""Full-tree walk / query / branches / pw:// resources."""
import pytest

from civilpy.state.ohio.DOT.pw_project import parse_resource, resource_uri
from tests.state.pw_testdata import PID, SFN, snapshot_project


@pytest.fixture()
def project():
    return snapshot_project()


class TestWalk:
    def test_every_document_classified(self, project):
        docs = project.walk()
        assert len(docs) == 22
        assert all("tree" in d and "segments" in d for d in docs)

    def test_review_docs_get_review_classification(self, project):
        reviews = [d for d in project.walk()
                   if d["tree"]["series"] == "reviews"]
        assert reviews and all("review_path" in d for d in reviews)

    def test_non_review_docs_do_not(self, project):
        planning = [d for d in project.walk()
                    if d["tree"]["series"] == "planning"]
        assert planning and all("review_path" not in d for d in planning)

    def test_walk_is_cached(self, project):
        assert project.walk() is project.walk()


class TestQuery:
    def test_series_filter(self, project):
        assert len(project.query(series="planning")) == 2

    def test_consultant_folders_merge_by_default(self, project):
        merged = project.query(discipline="structures", sfn=SFN,
                               bucket="sheets")
        assert len(merged) == 3          # 2 ODOT + 1 GPDgroup

    def test_consultant_pin(self, project):
        odot = project.query(discipline="structures", sfn=SFN,
                             bucket="sheets", consultant="")
        firm = project.query(discipline="structures", sfn=SFN,
                             bucket="sheets", consultant="GPDgroup")
        assert len(odot) == 2 and len(firm) == 1

    def test_sfn_accepts_int_and_pads(self, project):
        assert project.query(sfn=int(SFN)) == project.query(sfn=SFN)

    def test_review_kind_and_stage(self, project):
        hits = project.query(series="reviews", stage=2, kind="comments")
        # the Comments PDF and the Comment Resolution workbook both
        # classify as comment artifacts
        assert len(hits) == 2
        assert any("S2_Comments" in h["filename"] for h in hits)

    def test_sheet_code(self, project):
        assert len(project.query(sheet_code="SB")) == 3

    def test_pattern(self, project):
        assert project.query(pattern=r"alternatives\s+matrix")

    def test_set_valued_filter(self, project):
        both = project.query(series={"planning", "contracts"})
        assert len(both) == 3


class TestBranches:
    def test_merge_key_counts(self, project):
        b = project.branches()
        assert b[("engineering", "structures", SFN)] == 4   # 3 sheets + 1 engdata
        assert b[("survey", None, None)] == 3               # ODOT 2 + Korda 1


class TestResources:
    def test_uri_roundtrip(self):
        uri = resource_uri(PID, "engineering", "structures", SFN)
        pid, kwargs = parse_resource(uri)
        assert pid == PID
        assert kwargs == {"series": "engineering",
                          "discipline": "structures", "sfn": SFN}

    def test_project_only(self):
        assert parse_resource(f"pw://{PID}") == (PID, {})

    def test_series_only_uri(self):
        assert resource_uri(PID, "survey") == f"pw://{PID}/survey"

    def test_sfn_padded_in_uri(self):
        assert resource_uri(PID, "engineering", "structures", 42) \
            .endswith("/0000042")

    def test_reject_non_pw(self):
        with pytest.raises(ValueError):
            parse_resource("http://example.com")


class TestPwUrl:
    def test_project_link(self, project):
        url = project.pw_url()
        assert url.startswith("pw:\\\\ohiodot-pw.bentley.com:"
                              "ohiodot-pw-02\\Documents\\01 Active Projects")
        assert url.endswith(PID)

    def test_document_link(self, project):
        doc = project.query(discipline="structures", sfn=SFN,
                            bucket="sheets", consultant="")[0]
        url = project.pw_url(doc)
        assert url.endswith(
            f"400-Engineering\\Structures\\SFN_{SFN}\\Sheets\\"
            f"{doc['filename']}")
