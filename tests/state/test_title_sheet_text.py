"""Deterministic (no-ML) title-sheet parser.

The fixture is a synthetic title sheet drawn with the real ODOT anchor
headings in their usual positions, so the geometry-based capture regions
are exercised end to end.
"""
import pytest

fitz = pytest.importorskip("fitz")

from civilpy.state.ohio.DOT.title_sheet_text import (
    expand_sheet_numbers,
    find_anchor,
    parse_sheet_index,
    parse_title_sheet,
)


@pytest.fixture(scope="module")
def title_pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("ts") / "title.pdf"
    doc = fitz.open()
    page = doc.new_page(width=2448, height=1584)     # 34x22in landscape

    def put(x, y, text, size=11):
        page.insert_text((x, y), text, fontsize=size)

    # --- INDEX OF SHEETS block (left-centre) ---
    put(760, 430, "INDEX OF SHEETS:")
    index = [("TITLE SHEET", "1"), ("SCHEMATIC PLAN", "2"),
             ("TYPICAL SECTIONS", "3-4"), ("GENERAL NOTES", "5"),
             ("MAINTENANCE OF TRAFFIC", "6-7"), ("GENERAL SUMMARY", "8"),
             ("PROJECT SITE PLAN", "9"), ("PLAN AND PROFILE", "10"),
             ("CROSS SECTIONS", "11-17"),
             ("STRUCTURES OVER 20 FOOT SPAN", "40-50")]
    for i, (title, sheets) in enumerate(index):
        y = 460 + i * 22
        put(760, y, title)
        put(1050, y, sheets)

    # --- STANDARD CONSTRUCTION DRAWINGS (lower-centre) ---
    put(930, 1210, "STANDARD CONSTRUCTION DRAWINGS")
    scds = [("BP-1.1", "7/28/00"), ("BP-2.1", "7/17/15"),
            ("MGS-1.1", "1/19/18"), ("TC-41.20", "10/18/13")]
    for i, (code, date) in enumerate(scds):
        y = 1240 + i * 20
        put(930, y, code)
        put(1080, y, date)

    # --- right-edge metadata strip ---
    put(1760, 60, "FEDERAL PROJECT NUMBER")
    put(1760, 82, "E025 (762)")
    put(1760, 150, "RAILROAD INVOLVEMENT")
    put(1760, 172, "NONE")
    put(1760, 240, "PID No.")
    put(1760, 262, "115549")

    # --- project description (upper-right) ---
    put(1760, 320, "PROJECT DESCRIPTION")
    put(1760, 342, "UPGRADING 0.44 MILE OF FERNWOOD ROAD")

    # --- standard-specifications note (lower-left), the CMS citation ---
    put(100, 1300, "THE STANDARD SPECIFICATIONS OF THE STATE OF OHIO,")
    put(100, 1322, "DEPARTMENT OF TRANSPORTATION, INCLUDING SUPPLEMENTAL")
    put(100, 1344, "SPECIFICATIONS LISTED IN 2019 SPECIFICATIONS SHALL")
    put(100, 1366, "GOVERN THIS IMPROVEMENT.")

    doc.save(path)
    return str(path)


@pytest.fixture()
def parsed(title_pdf):
    return parse_title_sheet(fitz.open(title_pdf)[0])


class TestAnchors:
    def test_finds_multiword_anchor(self, title_pdf):
        words = [w[:5] for w in fitz.open(title_pdf)[0].get_text("words")]
        box = find_anchor(words, "INDEX OF SHEETS")
        assert box is not None and box[0] < box[2]

    def test_punctuation_insensitive(self, title_pdf):
        # the drawn text is "INDEX OF SHEETS:" (trailing colon)
        words = [w[:5] for w in fitz.open(title_pdf)[0].get_text("words")]
        assert find_anchor(words, "INDEX OF SHEETS") is not None

    def test_absent_anchor_returns_none(self, title_pdf):
        words = [w[:5] for w in fitz.open(title_pdf)[0].get_text("words")]
        assert find_anchor(words, "NONEXISTENT HEADING") is None

    def test_expected_anchors_present(self, parsed):
        for a in ("sheet_index", "scds", "federal_project", "railroad",
                  "project_description"):
            assert a in parsed["anchors_found"], a


class TestSheetIndex:
    def test_titles_and_numbers(self, parsed):
        idx = {e["title"]: e["sheets"] for e in parsed["sheet_index"]}
        assert idx["TITLE SHEET"] == "1"
        assert idx["TYPICAL SECTIONS"] == "3-4"
        assert idx["CROSS SECTIONS"] == "11-17"
        assert idx["STRUCTURES OVER 20 FOOT SPAN"] == "40-50"

    def test_all_entries_captured(self, parsed):
        assert len(parsed["sheet_index"]) == 10

    def test_does_not_bleed_into_scds(self, parsed):
        titles = {e["title"] for e in parsed["sheet_index"]}
        assert not any("BP-" in t for t in titles)


class TestSheetIndexRealWorld:
    """Layout quirks seen in the pulled DigitalPaper corpus."""

    def test_p_prefixed_numbers(self):
        from civilpy.state.ohio.DOT.title_sheet_text import (
            _lines, parse_sheet_index)

        class W(tuple):
            pass
        # (x0, y0, x1, y1, text) rows: "SCHEMATIC PLAN  P.2"
        words = [(760, 460, 900, 472, "SCHEMATIC"),
                 (905, 460, 980, 472, "PLAN"),
                 (1050, 460, 1090, 472, "P.2"),
                 (760, 482, 900, 494, "TYPICAL"),
                 (905, 482, 980, 494, "SECTIONS"),
                 (1050, 482, 1120, 494, "P.3-P.5")]
        entries = parse_sheet_index(words)
        got = {e["title"]: e["sheets"] for e in entries}
        assert got["SCHEMATIC PLAN"] == "2"
        assert got["TYPICAL SECTIONS"] == "3-5"

    def test_route_number_in_title_not_mistaken(self):
        from civilpy.state.ohio.DOT.title_sheet_text import parse_sheet_index
        # "PLAN AND PROFILE - S.R. 161   25"  -> sheet 25, route stays
        words = [(760, 460, 900, 472, "PLAN"),
                 (905, 460, 950, 472, "AND"),
                 (955, 460, 1010, 472, "PROFILE"),
                 (1015, 460, 1030, 472, "-"),
                 (1035, 460, 1075, 472, "S.R."),
                 (1080, 460, 1110, 472, "161"),
                 (1250, 460, 1280, 472, "25")]
        entries = parse_sheet_index(words)
        assert entries[0]["sheets"] == "25"
        assert "161" in entries[0]["title"]

    def test_year_not_treated_as_sheet(self):
        from civilpy.state.ohio.DOT.title_sheet_text import parse_sheet_index
        words = [(760, 460, 900, 472, "GENERAL"),
                 (905, 460, 980, 472, "NOTES"),
                 (1050, 460, 1090, 472, "5"),
                 (1300, 460, 1360, 472, "2023")]
        entries = parse_sheet_index(words)
        assert entries[0]["sheets"] == "5"

    def test_range_split_across_tokens(self):
        from civilpy.state.ohio.DOT.title_sheet_text import parse_sheet_index
        words = [(760, 460, 900, 472, "GENERAL"),
                 (905, 460, 980, 472, "NOTES"),
                 (1050, 460, 1090, 472, "P.03"),
                 (1095, 460, 1105, 472, "-"),
                 (1110, 460, 1150, 472, "04")]
        entries = parse_sheet_index(words)
        assert entries[0]["sheets"] == "03-04"       # leading zeros kept
        assert expand_sheet_numbers(entries) == {3, 4}
        assert entries[0]["title"] == "GENERAL NOTES"


class TestExpandSheetNumbers:
    def test_ranges_and_singles(self):
        got = expand_sheet_numbers([{"sheets": "1"}, {"sheets": "3-4"},
                                    {"sheets": "11-17"}, {"sheets": None}])
        assert got == {1, 3, 4} | set(range(11, 18))

    def test_comma_list(self):
        assert expand_sheet_numbers([{"sheets": "2,5,9"}]) == {2, 5, 9}

    def test_completeness_gap(self, parsed):
        expected = parsed["expected_sheets"]
        # index claims 1..17 and 40..50 -> if an archive only has 1..17,
        # 40..50 are the missing set
        have = set(range(1, 18))
        missing = expected - have
        assert missing == set(range(40, 51))


class TestScds:
    def test_code_date_pairs(self, parsed):
        scds = {s["code"]: s["date"] for s in parsed["scds"]}
        assert scds["BP-1.1"] == "7/28/00"
        assert scds["MGS-1.1"] == "1/19/18"
        assert len(parsed["scds"]) == 4


class TestMetadata:
    def test_federal_project(self, parsed):
        assert "E025" in parsed["federal_project"]

    def test_railroad(self, parsed):
        assert "NONE" in parsed["railroad"]

    def test_pid_candidate(self, parsed):
        assert "115549" in parsed["pid_candidates"]


class TestLocateTitlePage:
    """DigitalPaper prepends a contract-proposal cover; the title sheet
    with the index is often page 2+."""

    def test_skips_cover_page(self, tmp_path, title_pdf):
        from civilpy.state.ohio.DOT.title_sheet_text import locate_title_page
        # build a 2-page doc: cover, then the real title sheet
        doc = fitz.open()
        cover = doc.new_page(width=2448, height=1584)
        cover.insert_text((100, 100),
                          "US 35-19.80  PID - 90273 Dist 7  Contract Proposal")
        # append the fixture title sheet (has INDEX OF SHEETS)
        doc.insert_pdf(fitz.open(title_pdf))
        page = locate_title_page(doc)
        assert page.number == 1              # page 2 (0-indexed)

    def test_page_one_when_index_there(self, title_pdf):
        from civilpy.state.ohio.DOT.title_sheet_text import locate_title_page
        page = locate_title_page(fitz.open(title_pdf))
        assert page.number == 0

    def test_falls_back_to_first_page(self, tmp_path):
        from civilpy.state.ohio.DOT.title_sheet_text import locate_title_page
        doc = fitz.open()
        doc.new_page(width=612, height=792).insert_text((72, 72), "no index")
        assert locate_title_page(doc).number == 0


class TestNoTextLayer:
    def test_blank_page_yields_no_anchors(self, tmp_path):
        path = tmp_path / "blank.pdf"
        doc = fitz.open()
        doc.new_page(width=2448, height=1584)
        doc.save(path)
        parsed = parse_title_sheet(fitz.open(path)[0])
        assert parsed["anchors_found"] == []
        assert parsed["sheet_index"] is None


class TestSpecYear:
    """The CMS spec year cited in the standard-specifications note —
    phrasings from the real corpus plus the older spelled-out forms."""

    def test_parsed_from_fixture_sheet(self, parsed):
        assert parsed["spec_year"] == 2019

    def test_year_before_bare_specifications(self):
        from civilpy.state.ohio.DOT.title_sheet_text import parse_spec_year
        text = ("INCLUDING SUPPLEMENTAL SPECIFICATIONS LISTED IN "
                "2023 SPECIFICATIONS SHALL GOVERN THIS IMPROVEMENT")
        assert parse_spec_year(text) == 2023

    def test_spelled_out_cms_phrase_wins(self):
        from civilpy.state.ohio.DOT.title_sheet_text import parse_spec_year
        assert parse_spec_year(
            "THE 2013 CONSTRUCTION AND MATERIAL SPECIFICATIONS OF THE "
            "STATE OF OHIO") == 2013

    def test_dated_after_phrase(self):
        from civilpy.state.ohio.DOT.title_sheet_text import parse_spec_year
        assert parse_spec_year(
            "CONSTRUCTION AND MATERIAL SPECIFICATIONS DATED "
            "JANUARY 1, 2008 SHALL GOVERN") == 2008

    def test_absent_note_returns_none(self):
        from civilpy.state.ohio.DOT.title_sheet_text import parse_spec_year
        assert parse_spec_year("GENERAL NOTES AND A 2021 AADT TABLE") is None
