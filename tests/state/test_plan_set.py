"""Unwrapping ODOT DigitalPaper plan sets (Bluebeam PDF packages)."""
import pytest

fitz = pytest.importorskip("fitz")

from civilpy.state.ohio.DOT.plan_set import open_plan_set, title_page


def _plain_pdf(tmp, name, pages, first_text="TITLE SHEET"):
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=2448, height=1584)
        page.insert_text((100, 100), first_text if i == 0 else f"SHEET {i+1}")
    path = tmp / name
    doc.save(path)
    return path


def _package(tmp, name, embedded):
    """A 1-page wrapper PDF embedding the given {filename: pages} PDFs."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "This is a PDF package created by Bluebeam Revu")
    for fname, pages in embedded.items():
        sub = _plain_pdf(tmp, "_emb_" + fname, pages)
        doc.embfile_add(fname, open(sub, "rb").read(), filename=fname)
    path = tmp / name
    doc.save(path)
    return path


class TestFlatPdf:
    def test_single_plan_passthrough(self, tmp_path):
        path = _plain_pdf(tmp_path, "115840-Plan.pdf", 143)
        parts = open_plan_set(str(path))
        assert len(parts) == 1
        assert parts[0].role == "plan"
        assert parts[0].n_pages == 143

    def test_title_page_is_page_one(self, tmp_path):
        path = _plain_pdf(tmp_path, "flat-Plan.pdf", 5)
        tp = title_page(open_plan_set(str(path)))
        assert "TITLE SHEET" in tp.get_text()


class TestPackage:
    def test_unwraps_embedded_plans(self, tmp_path):
        path = _package(tmp_path, "115840.pdf", {
            "DEF-115840-Plan.pdf": 143,
            "DEF-115840-Plan-RW.pdf": 20,
            "DEF-115840-WP.pdf": 2})
        parts = open_plan_set(str(path))
        names = [p.name for p in parts]
        assert "DEF-115840-Plan.pdf" in names
        assert len(parts) == 3

    def test_main_plan_sorts_first(self, tmp_path):
        path = _package(tmp_path, "pkg.pdf", {
            "X-Plan-RW.pdf": 20, "X-WP.pdf": 2, "X-Plan.pdf": 143})
        parts = open_plan_set(str(path))
        assert parts[0].role == "plan"
        assert parts[0].n_pages == 143

    def test_roles_assigned(self, tmp_path):
        path = _package(tmp_path, "pkg.pdf", {
            "X-Plan.pdf": 10, "X-Plan-RW.pdf": 5, "X-WP.pdf": 1})
        roles = {p.name: p.role for p in open_plan_set(str(path))}
        assert roles["X-Plan.pdf"] == "plan"
        assert roles["X-Plan-RW.pdf"] == "rw"
        assert roles["X-WP.pdf"] == "wp"

    def test_title_page_from_main_plan(self, tmp_path):
        path = _package(tmp_path, "pkg.pdf", {
            "X-Plan-RW.pdf": 5, "X-Plan.pdf": 10})
        tp = title_page(open_plan_set(str(path)))
        assert "TITLE SHEET" in tp.get_text()

    def test_non_pdf_embeds_skipped(self, tmp_path):
        doc = fitz.open()
        doc.new_page(width=612, height=792).insert_text(
            (72, 72), "Bluebeam PDF package")
        sub = _plain_pdf(tmp_path, "_x-Plan.pdf", 10)
        doc.embfile_add("X-Plan.pdf", open(sub, "rb").read(),
                        filename="X-Plan.pdf")
        doc.embfile_add("notes.txt", b"just text", filename="notes.txt")
        path = tmp_path / "pkg.pdf"
        doc.save(path)
        parts = open_plan_set(str(path))
        assert [p.name for p in parts] == ["X-Plan.pdf"]
