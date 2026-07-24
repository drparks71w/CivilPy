"""ODOT standard-drawing number conventions: the year-suffix decoder the
standards-catalog date backfill and the era-registry queries share."""
from civilpy.state.ohio.DOT.standard_drawings import (
    drawing_family,
    year_from_drawing_no,
)


class TestYearFromDrawingNo:
    def test_two_digit_1900s(self):
        assert year_from_drawing_no("CSB-1-55") == 1955
        assert year_from_drawing_no("RB-1-31") == 1931

    def test_two_digit_2000s(self):
        assert year_from_drawing_no("SBR-1-13") == 2013
        assert year_from_drawing_no("CS-1-08") == 2008

    def test_future_two_digit_reads_1900s(self):
        # a -30 suffix cannot mean 2030 before 2030 exists
        assert year_from_drawing_no("X-1-30") == 1930

    def test_four_digit(self):
        assert year_from_drawing_no("AB-1-1998") == 1998

    def test_metric_and_sheet_suffixes(self):
        assert year_from_drawing_no("CSB-1-93M") == 1993
        assert year_from_drawing_no("RB-1-55.2") == 1955

    def test_dotted_modern_series_has_no_year(self):
        assert year_from_drawing_no("MGS-1.1") is None
        assert year_from_drawing_no("BP-2.1") is None
        assert year_from_drawing_no("TC-41.20") is None

    def test_junk(self):
        assert year_from_drawing_no(None) is None
        assert year_from_drawing_no("") is None
        assert year_from_drawing_no("NOTES") is None


class TestDrawingFamily:
    def test_year_suffix_stripped(self):
        assert drawing_family("CSB-1-55") == "CSB-1"
        assert drawing_family("CSB-1-93M") == "CSB-1"
        assert drawing_family("PSID-1-99") == "PSID-1"

    def test_dotted_series_unchanged(self):
        assert drawing_family("MGS-1.1") == "MGS-1.1"

    def test_case_normalized(self):
        assert drawing_family("csb-1-55") == "CSB-1"

    def test_junk(self):
        assert drawing_family(None) is None
        assert drawing_family("  ") is None

    def test_single_dash_year_form(self):
        # portable-barrier style: one dash, undotted 2-digit year
        assert year_from_drawing_no("PCB-91") == 1991
        assert drawing_family("PCB-91") == "PCB"
