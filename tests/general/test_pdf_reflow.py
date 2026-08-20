"""pdf_reflow: recover reading order from Bentley-scrambled PDFs.

The fixture PDF is built the way MicroStation emits text: lines of each
block written bottom-up, blocks in draw order, two columns interleaved.
"""
import pytest

fitz = pytest.importorskip("fitz")

from civilpy.general.pdf_reflow import (
    extract_numbered_notes,
    find_notes_pages,
    page_has_text,
    reflow_page,
    reflow_pdf,
)

LEFT = ["GENERAL NOTES:",
        "1. DESIGN SPECIFICATIONS:",
        "THIS STRUCTURE CONFORMS TO THE ODOT",
        "BRIDGE DESIGN MANUAL, 2026 EDITION."]
RIGHT = ["17. NOISE BARRIER FOUNDATION IN POOR SOIL:",
         "CONTACT THE OFFICE OF GEOTECHNICAL",
         "ENGINEERING TO DETERMINE IF THE SHAFT",
         "SHOULD BE EXTENDED."]


@pytest.fixture(scope="module")
def scrambled_pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("pdf") / "scrambled.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # right column first (draw order != reading order), lines bottom-up
    for i, line in enumerate(reversed(RIGHT)):
        page.insert_text((360, 700 - i * 14), line, fontsize=9)
    for i, line in enumerate(reversed(LEFT)):
        page.insert_text((36, 700 - i * 14), line, fontsize=9)
    # second page: no text at all (vector-only title sheet stand-in)
    empty = doc.new_page(width=612, height=792)
    empty.draw_line((0, 0), (100, 100))
    doc.save(path)
    doc.close()
    return path


class TestReflow:
    def test_stream_order_is_scrambled(self, scrambled_pdf):
        raw = fitz.open(scrambled_pdf)[0].get_text()
        # sanity: the fixture reproduces the failure (right column and/or
        # reversed lines come first in stream order)
        assert raw.index("NOISE BARRIER") < raw.index("GENERAL NOTES")

    def test_reflow_restores_reading_order(self, scrambled_pdf):
        text = reflow_page(fitz.open(scrambled_pdf)[0])
        lines = text.splitlines()
        assert lines[:4] == LEFT           # left column first, top-down
        assert lines[4:] == RIGHT          # then right column

    def test_no_text_page_returns_empty(self, scrambled_pdf):
        page = fitz.open(scrambled_pdf)[1]
        assert not page_has_text(page)
        assert reflow_page(page) == ""

    def test_reflow_pdf_maps_pages(self, scrambled_pdf):
        result = reflow_pdf(scrambled_pdf)
        assert set(result) == {1, 2}
        assert "GENERAL NOTES" in result[1]
        assert result[2] == ""

    def test_pages_filter(self, scrambled_pdf):
        assert set(reflow_pdf(scrambled_pdf, pages=[2])) == {2}


class TestNotesExtraction:
    def test_numbered_notes_split(self, scrambled_pdf):
        text = reflow_page(fitz.open(scrambled_pdf)[0])
        notes = extract_numbered_notes(text)
        nums = [n["num"] for n in notes]
        assert nums == ["1", "17"]
        assert notes[0]["title"] == "DESIGN SPECIFICATIONS"
        assert "BRIDGE DESIGN MANUAL" in notes[0]["body"]
        assert notes[1]["title"].startswith("NOISE BARRIER FOUNDATION")
        assert notes[1]["body"].endswith("EXTENDED.")

    def test_find_notes_pages(self, scrambled_pdf):
        assert find_notes_pages(scrambled_pdf) == [1]

    def test_lettered_items(self):
        notes = extract_numbered_notes(
            "A. FIRST THING:\nbody one\nB. SECOND THING:\nbody two")
        assert [n["num"] for n in notes] == ["A", "B"]
