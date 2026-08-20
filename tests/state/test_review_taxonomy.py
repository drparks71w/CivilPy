"""Review-folder/file taxonomy — patterns validated against real strings
captured in the 2026-07 district recon (district_file_samples.json)."""
from civilpy.state.ohio.DOT.review_taxonomy import (
    classify_review_file, classify_review_path)


def test_planreviews_stage_layout():
    c = classify_review_path(["PlanReviews", "01-Stage2", "02-Comments"])
    assert c["stage"] == "2" and c["roles"] == ["comments"]
    assert "plan_review" in c["types"]
    c = classify_review_path(
        ["PlanReviews", "01-Stage2", "03-Disposition of Comments"])
    assert c["roles"] == ["disposition"]


def test_stage_direct_layout():
    c = classify_review_path(["Stage 3", "Submission", "09_Load Rating"])
    assert c["stage"] == "3" and c["roles"] == ["submission"]
    assert "load_rating" in c["types"]
    assert classify_review_path(["Pre-Stage 1"])["stage"] == "1"
    assert classify_review_path(["02-Stage2"])["stage"] == "2"


def test_sts_dated_resubmittal_tree():
    c = classify_review_path(["Structure Type Studies", "LUC-00475-1027",
                              "20230802 Resubmittal", "Submittal"])
    assert "sts" in c["types"] and c["roles"] == ["submission"]
    assert c["dated"] == "2023-08-02" and c["resubmittal"] is True


def test_file_kinds_from_recon():
    f = classify_review_file(
        "20230412_PID115418_LUC-051-0846 Structure Type Study-Markups.pdf")
    assert f["kind"] == "markups" and f["pid"] == "115418"
    f = classify_review_file("VAN-224_PID109112_S2__Dispositions.pdf")
    assert f["kind"] == "disposition" and f["stage"] == "2"
    f = classify_review_file("Kuhlman Bridge Rehab Load Rating_SFN_4860934.pdf")
    assert f["kind"] == "load_rating" and f["sfn"] == "4860934"
    f = classify_review_file(
        "FORM BR-100 - ATB-MR-365-0.22 BRIDGE LOAD RATING SUMMARY REPORT.pdf")
    assert f["kind"] == "load_rating"
    assert classify_review_file("random_notes.txt")["kind"] is None


def test_review_documents_walk():
    from civilpy import ProjectWiseProject
    from tests.state.test_pw_project import FakeClient, doc

    client = FakeClient()
    client.folders[1].append(("950-Reviews", 90))
    client.folders[90] = [("PlanReviews", 91)]
    client.folders[91] = [("01-Stage2", 92)]
    client.folders[92] = [("02-Comments", 93)]
    client.folders[93] = []
    client.docs[93] = [doc(901, "VAN-224_PID109112_S2__Comments.pdf", 93)]
    p = ProjectWiseProject("112665", district="06", county="Franklin",
                           client=client)
    docs = p.review_documents()
    assert len(docs) == 1
    d = docs[0]
    assert d["review_path"]["stage"] == "2"
    assert d["review_path"]["roles"] == ["comments"]
    assert d["review_file"]["kind"] == "comments"
    assert d["segments"] == ["PlanReviews", "01-Stage2", "02-Comments"]
