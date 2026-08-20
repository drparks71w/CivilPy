"""Bluebeam/PDF markup extraction (civilpy.general.pdf_markups).

Builds a small annotated PDF with PyMuPDF and reads it back — the same
annotation keys (/T, /Subj, /Contents, /IRT) Bluebeam Revu writes.
"""
import pytest

fitz = pytest.importorskip("fitz")

from civilpy.general.pdf_markups import extract_markups, markup_summary


@pytest.fixture()
def marked_pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    a1 = page.add_text_annot((72, 72), "Check bearing seat elevation")
    a1.set_info(title="Dane Parks", subject="Callout",
                content="Check bearing seat elevation")
    a1.update()
    a2 = page.add_rect_annot(fitz.Rect(100, 100, 200, 150))
    a2.set_info(title="Jim Calanni", subject="Cloud+",
                content="Rebar lap length per BDM 1004")
    a2.update()
    # reply thread: a3 answers a2 (Bluebeam writes /IRT for replies)
    a3 = page.add_text_annot((110, 160), "Will revise")
    a3.set_info(title="Consultant", subject="Reply", content="Will revise")
    a3.update()
    doc.xref_set_key(a3.xref, "IRT", f"{a2.xref} 0 R")
    path = tmp_path / "marked.pdf"
    doc.save(path)
    doc.close()
    return path


def test_extract_markups(marked_pdf):
    marks = extract_markups(marked_pdf)
    assert len(marks) == 3
    by_author = {m["author"]: m for m in marks}
    assert by_author["Dane Parks"]["subject"] == "Callout"
    assert by_author["Jim Calanni"]["contents"] == "Rebar lap length per BDM 1004"
    assert all(m["page"] == 1 for m in marks)


def test_reply_threading(marked_pdf):
    marks = extract_markups(marked_pdf)
    parent = next(m for m in marks if m["author"] == "Jim Calanni")
    reply = next(m for m in marks if m["author"] == "Consultant")
    assert reply["reply_to"] == parent["id"]
    assert parent["reply_to"] is None


def test_markup_summary(marked_pdf):
    s = markup_summary(extract_markups(marked_pdf))
    assert s["total"] == 3 and s["replies"] == 1
    assert s["by_author"]["Dane Parks"] == 1
    assert s["pages"] == [1]


def test_unannotated_pdf(tmp_path):
    doc = fitz.open()
    doc.new_page()
    path = tmp_path / "plain.pdf"
    doc.save(path)
    doc.close()
    assert extract_markups(path) == []
    assert markup_summary([])["total"] == 0


def test_arrow_geometry_and_anchor_text(tmp_path):
    from civilpy.general.pdf_markups import anchor_text, render_clip
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((300, 300), "ABUTMENT ELEVATION")   # the referent
    a = page.add_line_annot((100, 100), (295, 295))      # arrow to it
    a.set_info(title="Reviewer", content="Move to sheet 3")
    a.update()
    path = tmp_path / "arrow.pdf"
    doc.save(path); doc.close()

    m = next(m for m in extract_markups(path) if m["type"] == "Line")
    assert m["arrow_head"] == (295.0, 295.0)
    assert "ABUTMENT ELEVATION" in anchor_text(path, m)
    out = render_clip(path, m, tmp_path / "clip.png")
    assert out.stat().st_size > 0
