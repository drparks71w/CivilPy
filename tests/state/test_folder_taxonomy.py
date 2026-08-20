"""Full-tree folder taxonomy, validated against recon-observed shapes."""
import pytest

from civilpy.state.ohio.DOT.folder_taxonomy import (
    classify_project_path,
    merge_key,
    parse_top_folder,
)


class TestParseTopFolder:
    def test_odot_series(self):
        assert parse_top_folder("300-Survey") == {
            "number": "300", "series": "survey", "consultant": None}

    def test_consultant_parallel(self):
        got = parse_top_folder("401-Engineering_GPDgroup")
        assert got["series"] == "engineering"
        assert got["consultant"] == "GPDgroup"

    def test_consultant_with_underscores(self):
        got = parse_top_folder("305-Survey_Lawhon_Associates")
        assert got["consultant"] == "Lawhon_Associates"

    def test_projadmin_variant(self):
        assert parse_top_folder("010-ProjAdmin")["series"] == "admin"
        assert parse_top_folder("000-Admin")["series"] == "admin"

    def test_workset_standards(self):
        assert parse_top_folder("990-WorkSetStandards")["series"] \
            == "workset_standards"

    @pytest.mark.parametrize("name", ["Photos", "SFN_2510774", "",
                                      "123-Nonsense", None])
    def test_non_series_names(self, name):
        assert parse_top_folder(name) is None


class TestClassifyProjectPath:
    def test_engineering_structures_sfn(self):
        info = classify_project_path(
            ["400-Engineering", "Structures", "SFN_2510774", "Sheets"])
        assert info["series"] == "engineering"
        assert info["discipline"] == "structures"
        assert info["sfn"] == "2510774"
        assert info["bucket"] == "sheets"

    def test_sfn_zero_padded(self):
        info = classify_project_path(
            ["400-Engineering", "Structures", "SFN_2", "EngData"])
        assert info["sfn"] == "0000002"

    def test_wall_folder(self):
        info = classify_project_path(
            ["400-Engineering", "Structures", "Wall_000"])
        assert info["wall"] == "000"
        assert info["sfn"] is None

    def test_consultant_discipline(self):
        info = classify_project_path(
            ["401-Engineering_GPDgroup", "Roadway", "Basemaps"])
        assert info["discipline"] == "roadway"
        assert info["consultant"] == "GPDgroup"
        assert info["bucket"] == "basemaps"

    def test_survey_area(self):
        info = classify_project_path(["300-Survey", "SurveyData", "Reports"])
        assert info["series"] == "survey"
        assert info["area"] == "SurveyData"

    def test_planning_scopes(self):
        assert classify_project_path(
            ["100-Planning", "Scopes"])["area"] == "Scopes"

    def test_geotech_alias(self):
        info = classify_project_path(["400-Engineering", "Geotech"])
        assert info["discipline"] == "geotechnical"

    def test_unnumbered_root_returns_blank(self):
        info = classify_project_path(["Photos", "Site Visit"])
        assert info["series"] is None
        assert info["discipline"] is None

    def test_root_level_document(self):
        info = classify_project_path([])
        assert info["series"] is None

    def test_reviews_series(self):
        info = classify_project_path(
            ["950-Reviews", "PlanReviews", "01-Stage2"])
        assert info["series"] == "reviews"

    def test_all_keys_always_present(self):
        info = classify_project_path(["600-Contracts"])
        assert set(info) == {"series", "number", "consultant", "discipline",
                             "bucket", "sfn", "wall", "area"}


class TestMergeKey:
    def test_consultant_folders_merge(self):
        odot = classify_project_path(
            ["400-Engineering", "Structures", "SFN_2510774", "Sheets"])
        firm = classify_project_path(
            ["401-Engineering_GPDgroup", "Structures", "SFN_2510774",
             "Sheets"])
        assert merge_key(odot) == merge_key(firm)

    def test_different_sfns_do_not_merge(self):
        a = classify_project_path(
            ["400-Engineering", "Structures", "SFN_1111111"])
        b = classify_project_path(
            ["400-Engineering", "Structures", "SFN_2222222"])
        assert merge_key(a) != merge_key(b)

    def test_wall_in_key(self):
        wall = classify_project_path(
            ["400-Engineering", "Structures", "Wall_000"])
        assert merge_key(wall)[2] == "000"
