"""Tier-2 completion / absence checks."""
import copy

import pytest

from civilpy.state.ohio.DOT.pw_project import ProjectWiseProject
from civilpy.state.ohio.DOT.pw_snapshot import SnapshotClient
from civilpy.state.ohio.DOT.review_checks import (
    CHECKS,
    comments_addressed,
    review_rounds,
    run_checks,
    sheet_naming_conformance,
    summarize,
)
from tests.state.pw_testdata import RECON_RECORD, snapshot_project


def project_without(*folder_names):
    """The synthetic project with named top-level folders removed."""
    record = copy.deepcopy(RECON_RECORD)
    record["tree"]["children"] = [
        c for c in record["tree"]["children"]
        if c["name"] not in folder_names]
    client, path, pid = SnapshotClient.from_recon(record)
    return ProjectWiseProject(pid, path=path, client=client)


def by_check(findings):
    return {f["check"]: f for f in findings}


class TestCompleteProject:
    def test_all_green_but_none_error(self):
        findings = run_checks(snapshot_project(), stage=3)
        assert not [f for f in findings if f["status"] == "error"]
        got = by_check(findings)
        for name in ("scope_form", "survey_data", "utility_evidence",
                     "geotech", "sfn_folders", "sts", "load_rating",
                     "as_advertised", "review_rounds"):
            assert got[name]["status"] == "ok", (name, got[name])

    def test_summary_counts(self):
        s = summarize(run_checks(snapshot_project(), stage=3))
        assert s["counts"]["ok"] >= 9
        assert all(f["status"] != "missing" for f in s["flags"])


class TestAbsenceDetection:
    def test_missing_scope_form(self):
        p = project_without("100-Planning")
        assert by_check(run_checks(p))["scope_form"]["status"] == "missing"

    def test_missing_survey(self):
        p = project_without("300-Survey", "301-Survey_Korda")
        got = by_check(run_checks(p))
        assert got["survey_data"]["status"] == "missing"

    def test_missing_utility_evidence(self):
        p = project_without("300-Survey")     # consultant survey remains,
        got = by_check(run_checks(p))         # but has no utility files
        assert got["utility_evidence"]["status"] == "missing"

    def test_load_rating_required_at_stage_3(self):
        record = copy.deepcopy(RECON_RECORD)
        eng = next(c for c in record["tree"]["children"]
                   if c["name"] == "400-Engineering")
        sfn = eng["children"][2]["children"][0]
        sfn["children"] = [c for c in sfn["children"]
                           if c["name"] != "EngData"]
        client, path, pid = SnapshotClient.from_recon(record)
        p = ProjectWiseProject(pid, path=path, client=client)
        assert by_check(run_checks(p, stage=3))["load_rating"]["status"] \
            == "missing"
        assert by_check(run_checks(p, stage=1))["load_rating"]["status"] \
            == "attention"

    def test_non_structure_project_skips_structure_checks(self):
        p = project_without("400-Engineering", "401-Engineering_GPDgroup",
                            "950-Reviews")
        got = by_check(run_checks(p))
        assert got["sfn_folders"]["status"] == "n/a"
        assert got["sts"]["status"] == "n/a"
        assert got["load_rating"]["status"] == "n/a"

    def test_contracts_only_required_at_sale(self):
        p = project_without("600-Contracts")
        assert by_check(run_checks(p, stage=2))["as_advertised"]["status"] \
            == "n/a"
        assert by_check(run_checks(p, stage=4))["as_advertised"]["status"] \
            == "missing"


class TestReviewRounds:
    def test_rounds_grouped(self):
        rounds = review_rounds(snapshot_project())
        assert len(rounds) >= 2
        stage2 = next(r for r in rounds if r["stage"] == "2")
        assert stage2["comments"] and stage2["dispositions"]

    def test_comments_addressed(self):
        answers = dict(comments_addressed(snapshot_project()))
        assert any(v is True for v in answers.values())

    def test_open_round_flagged(self):
        record = copy.deepcopy(RECON_RECORD)
        reviews = next(c for c in record["tree"]["children"]
                       if c["name"] == "950-Reviews")
        stage2 = reviews["children"][0]["children"][0]
        stage2["children"] = [c for c in stage2["children"]
                              if "Disposition" not in c["name"]]
        client, path, pid = SnapshotClient.from_recon(record)
        p = ProjectWiseProject(pid, path=path, client=client)
        finding = by_check(run_checks(p))["review_rounds"]
        assert finding["status"] == "attention"
        assert "no disposition" in finding["evidence"]


class TestSheetNaming:
    def test_conformance_ratio(self):
        ratio, n = sheet_naming_conformance(snapshot_project())
        assert n == 5                       # 2 GP/GN + 3 SB sheets
        assert ratio == 1.0


class TestRobustness:
    def test_a_broken_check_reports_not_raises(self, monkeypatch):
        def boom(project, stage=None):
            raise RuntimeError("kaput")
        monkeypatch.setitem(CHECKS, "scope_form", boom)
        got = by_check(run_checks(snapshot_project()))
        assert got["scope_form"]["status"] == "error"
        assert "kaput" in got["scope_form"]["evidence"]

    def test_check_subset(self):
        findings = run_checks(snapshot_project(), checks=["geotech"])
        assert [f["check"] for f in findings] == ["geotech"]
