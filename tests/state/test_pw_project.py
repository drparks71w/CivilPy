"""ProjectWiseProject object model, exercised against a fake PW client.

The fake mirrors the folder shapes verified on the live datasource
(2026-07-21 probes): the 01 Active Projects path, 400-Engineering/Structures,
SFN_* folders with {PID}_SFN_{SFN}_{sheet} filenames, and a
"Bridge Load Rating Files" folder with {PID}_{SFN}_{sheet} filenames.
"""
import pytest

from civilpy import ProjectWiseProject


def doc(doc_id, filename, folder_id):
    return {"doc_id": doc_id, "name": filename, "filename": filename,
            "desc": "", "size": 1000, "created": "", "updated": "",
            "folder_id": folder_id}


class FakeClient:
    """Duck-typed stand-in for civilpy.general.bentley.projectwise."""

    PATH = "Documents\\01 Active Projects\\District 06\\Franklin\\112665"

    def __init__(self):
        self.folders = {
            1: [("100-Admin", 10), ("400-Engineering", 11)],
            10: [],
            11: [("Structures", 12), ("Structure Type Study", 16)],
            12: [("SFN_2510774", 13), ("SFN_2500000", 14),
                 ("Bridge Load Rating Files", 15)],
            13: [], 14: [], 15: [], 16: [],
        }
        self.docs = {
            13: [doc(101, "112665_SFN_2510774_SI001.dgn", 13),
                 doc(102, "112665_SFN_2510774_SI002.dgn", 13)],
            14: [doc(103, "112665_SFN_2500000_SI001.dgn", 14)],
            15: [doc(104, "112665_2510774_BR100.pdf", 15),
                 doc(105, "112665_2500000_BR100.pdf", 15)],
            16: [doc(106, "112665_STS_Report.pdf", 16)],
        }
        self.pulled = []

    def resolve_path(self, path):
        return 1 if path == self.PATH else 0

    def list_children(self, folder_id):
        return self.folders.get(folder_id, [])

    def list_documents(self, folder_id):
        return list(self.docs.get(folder_id, []))

    def copy_out(self, folder_id, doc_id, dest):
        self.pulled.append((folder_id, doc_id, str(dest)))
        return f"{dest}/pulled_{doc_id}"


@pytest.fixture()
def project():
    return ProjectWiseProject("112665", district="6", county="Franklin",
                              client=FakeClient())


def test_path_resolution(project):
    assert project.project_path == FakeClient.PATH   # district zero-padded
    assert project.root.id == 1


def test_sfns_and_sheets(project):
    sfns = project.sfns
    assert [s.sfn for s in sfns] == ["2510774", "2500000"]
    sheets = sfns[0].sheets
    assert {s["sheet"] for s in sheets} == {"SI001", "SI002"}
    assert all(s["sfn"] == "2510774" for s in sheets)


def test_sfn_lookup_and_load_rating(project):
    lr = project.sfn("2510774").load_rating
    assert [d["filename"] for d in lr] == ["112665_2510774_BR100.pdf"]


def test_deliverable_registry_and_getattr(project):
    sts = project.sts
    assert [d["filename"] for d in sts] == ["112665_STS_Report.pdf"]
    assert project.deliverable("sts") is sts          # cached
    with pytest.raises(KeyError):
        project.deliverable("nope")
    with pytest.raises(AttributeError):
        project.not_a_deliverable


def test_structures_fallback_search(project):
    # break the canonical path; the name search should still find Structures
    project._client.folders[11] = [("Bridges&Structures", 12),
                                   ("Structure Type Study", 16)]
    assert project.structures.id == 12


def test_pull_and_survey(project, tmp_path):
    written = project.sfn("2500000").pull(tmp_path)
    assert written and project._client.pulled[0][1] == 103
    tree = project.survey()
    assert tree["pid"] == "112665"
    names = {c["name"] for c in tree["tree"]["children"]}
    assert "400-Engineering" in names


def test_missing_location_raises():
    p = ProjectWiseProject("999999", client=FakeClient())
    with pytest.raises(LookupError):
        _ = p.project_path


def test_custom_deliverable_override():
    p = ProjectWiseProject("112665", district="06", county="Franklin",
                           client=FakeClient(),
                           deliverables={"admin": [r"^100-Admin$"]})
    assert p.deliverable("admin") == []               # folder exists, no docs
    assert "sts" in p.deliverables                    # defaults preserved
