"""Comment Resolution Form parser (header sniffing + dispositions)."""
import pandas as pd
import pytest

from civilpy.state.ohio.DOT.comment_resolution import (
    classify_disposition,
    is_resolution_filename,
    parse_comment_resolution,
    parse_comment_resolutions,
)


def frame(rows):
    return pd.DataFrame(rows)


STANDARD = frame([
    ["ODOT Comment Resolution Form", None, None, None, None],
    ["Project: FRA-70-12.00", None, None, None, None],
    ["No.", "Sheet No.", "Comment", "Designer Response", "Status"],
    [1, "5", "Show utility shots near pier 2", "Will revise", "Closed"],
    [2, "12", "Was a single span considered?",
     "N/A - culvert replacement", None],
    [None, None, None, None, None],
    [3, "1", "Update title block county", "Disagree - matches PID", "Open"],
])


class TestHeaderSniffing:
    def test_offset_header_found(self):
        rows = parse_comment_resolution({"S2": STANDARD}, filename="f.xlsx")
        assert len(rows) == 3
        assert rows[0]["header_row"] == 2
        assert rows[0]["comment"].startswith("Show utility")
        assert rows[0]["sheet_ref"] == "5"

    def test_alias_variants(self):
        df = frame([
            ["Item", "Sht", "Review Comments", "Consultant Response",
             "Disposition"],
            [1, "3", "Add scour countermeasures", "Added per BDM", "Concur"],
        ])
        rows = parse_comment_resolution({"x": df})
        assert rows[0]["comment"] == "Add scour countermeasures"
        assert rows[0]["disposition"] == "Concur"

    def test_sheet_without_header_skipped(self):
        df = frame([["just", "some", "text"], [1, 2, 3]])
        assert parse_comment_resolution({"cover": df}) == []

    def test_multiple_worksheets(self):
        rows = parse_comment_resolution(
            {"cover": frame([["title page"]]), "S2": STANDARD})
        assert {r["worksheet"] for r in rows} == {"S2"}

    def test_unmapped_columns_kept_in_extra(self):
        df = frame([
            ["No.", "Comment", "Response", "Ball in Court"],
            [1, "Check bearing seat elevations", "Fixed", "ODOT"],
        ])
        rows = parse_comment_resolution({"x": df})
        assert rows[0]["extra"] == {"Ball in Court": "ODOT"}

    def test_blank_comment_rows_dropped(self):
        rows = parse_comment_resolution({"S2": STANDARD})
        assert all(r["comment"] for r in rows)

    def test_provenance(self):
        rows = parse_comment_resolution({"S2": STANDARD}, filename="a.xlsx")
        assert rows[0]["source_file"] == "a.xlsx"
        assert rows[0]["row"] == 3


class TestDispositions:
    @pytest.mark.parametrize("text,expected", [
        ("Concur", "accepted"),
        ("Will revise, see sheet 4", "revised"),
        ("Incorporated in resubmittal", "revised"),
        ("Closed", "revised"),
        ("Disagree - no change required", "rejected"),
        ("Not incorporated, stands as is", "rejected"),
        ("N/A - culvert replacement", "na"),
        ("Pending survey verification", "open"),
        ("", None),
        (None, None),
    ])
    def test_classify(self, text, expected):
        assert classify_disposition(text) == expected

    def test_disposition_column_wins_over_response(self):
        rows = parse_comment_resolution({"S2": STANDARD})
        # row 3: response says Disagree, status says Open -> disposition
        # column ("Open") is authoritative
        assert rows[2]["disposition_class"] == "open"

    def test_falls_back_to_response(self):
        # row 2 has no Status; classify from the response text
        rows = parse_comment_resolution({"S2": STANDARD})
        assert rows[1]["disposition_class"] == "na"


class TestFilenameFilter:
    @pytest.mark.parametrize("name,expected", [
        ("LUC-475_PID114418_Comment Resolution Form.xlsx", True),
        ("20240109_DEF-115840_S1_disposition of comments.xlsx", True),
        ("20240116_DEF-115840_Preliminary RW_comments.xlsx", True),
        ("Comment Resolution Form.pdf", False),      # not a workbook
        ("FRA-70 STS Report.xlsx", False),
    ])
    def test_names(self, name, expected):
        assert is_resolution_filename(name) is expected


class TestBatch:
    def test_bad_file_recorded_not_fatal(self, tmp_path):
        bad = tmp_path / "corrupt.xlsx"
        bad.write_bytes(b"this is not a workbook")
        df = parse_comment_resolutions([bad])
        assert len(df) == 1
        assert df.iloc[0]["error"]

    def test_real_workbook_roundtrip(self, tmp_path):
        path = tmp_path / "crf.xlsx"
        STANDARD.to_excel(path, index=False, header=False)
        rows = parse_comment_resolution(path)
        assert len(rows) == 3
        assert rows[0]["disposition_class"] == "revised"
