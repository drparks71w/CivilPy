# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the PDF/UA drawing retrofit (civilpy.general.pdf_ua).

Fixtures are synthetic vector PDFs built with pikepdf — the same shape
of content a CAD exporter emits (paths, no tags), with no licensing
strings attached.
"""
import shutil
import subprocess

import pytest

pikepdf = pytest.importorskip("pikepdf")

from civilpy.general.pdf_ua import SheetManifest, tag_drawing_pdf  # noqa: E402

ALT = ("Section and plan views of a concrete drip strip with "
       "installation dimensions.")


def _vector_pdf(path, n_pages=2, with_unembedded_font=False):
    """An untagged, CAD-exporter-shaped PDF: raw path operators only."""
    pdf = pikepdf.new()
    for _ in range(n_pages):
        page = pdf.add_blank_page(page_size=(612, 792))
        ops = (b"0 0 1 RG 4 w 72 72 468 648 re S "
               b"q 1 0 0 1 100 100 cm 0 0 m 200 300 l S Q")
        if with_unembedded_font:
            page.obj.Resources = pikepdf.Dictionary(
                Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(
                    Type=pikepdf.Name.Font,
                    Subtype=pikepdf.Name.Type1,
                    BaseFont=pikepdf.Name.Helvetica,
                )))
            ops += b" BT /F1 12 Tf 90 700 Td (SHEET) Tj ET"
        page.obj.Contents = pdf.make_stream(ops)
    pdf.save(path)
    return path


@pytest.fixture
def tagged(tmp_path):
    src = _vector_pdf(tmp_path / "sheet.pdf")
    dst = tmp_path / "sheet_tagged.pdf"
    manifest = SheetManifest(
        title="DS-1-92 Drip Strip Details",
        alt_texts=(ALT, "Reinforcing details for the drip strip."),
    )
    report = tag_drawing_pdf(src, dst, manifest)
    return dst, manifest, report


def test_document_plumbing(tagged):
    dst, manifest, report = tagged
    assert report.pages == 2
    with pikepdf.open(dst) as pdf:
        root = pdf.Root
        assert root.MarkInfo.Marked == True  # noqa: E712 (pikepdf Boolean)
        assert str(root.Lang) == "en-US"
        assert root.ViewerPreferences.DisplayDocTitle == True  # noqa: E712
        assert str(pdf.docinfo["/Title"]) == manifest.title
        for page in pdf.pages:
            assert page.obj.Tabs == pikepdf.Name.S


def test_structure_tree_shape(tagged):
    dst, manifest, _ = tagged
    with pikepdf.open(dst) as pdf:
        doc = pdf.Root.StructTreeRoot.K
        assert doc.S == pikepdf.Name.Document
        figures = list(doc.K)
        assert len(figures) == 2
        for i, fig in enumerate(figures):
            assert fig.S == pikepdf.Name.Figure
            assert str(fig.Alt) == manifest.alt_texts[i]
            assert fig.K == 0
            assert fig.Pg.objgen == pdf.pages[i].obj.objgen
            assert fig.A.O == pikepdf.Name.Layout
            assert len(fig.A.BBox) == 4
            assert pdf.pages[i].obj.StructParents == i


def test_parent_tree_wiring(tagged):
    dst, _, _ = tagged
    with pikepdf.open(dst) as pdf:
        figures = list(pdf.Root.StructTreeRoot.K.K)
        nums = pdf.Root.StructTreeRoot.ParentTree.Nums
        assert [int(nums[j]) for j in (0, 2)] == [0, 1]
        for i, fig in enumerate(figures):
            assert nums[2 * i + 1][0].objgen == fig.objgen
        assert pdf.Root.StructTreeRoot.ParentTreeNext == 2


def test_content_wrapped_not_rewritten(tagged):
    dst, _, _ = tagged
    with pikepdf.open(dst) as pdf:
        for page in pdf.pages:
            streams = list(page.obj.Contents)
            assert len(streams) == 3
            assert streams[0].read_bytes().startswith(b"/Figure")
            assert streams[2].read_bytes().strip() == b"EMC"
            # the exporter's own stream is byte-identical
            assert streams[1].read_bytes().startswith(b"0 0 1 RG")


def test_xmp_declares_pdfua(tagged):
    dst, manifest, _ = tagged
    with pikepdf.open(dst) as pdf:
        xmp = pdf.Root.Metadata.read_bytes()
        assert b"<pdfuaid:part>1</pdfuaid:part>" in xmp
        assert manifest.title.encode() in xmp


def test_single_alt_broadcasts(tmp_path):
    src = _vector_pdf(tmp_path / "s.pdf", n_pages=3)
    dst = tmp_path / "t.pdf"
    report = tag_drawing_pdf(src, dst, title="Sheet", alt_text=ALT)
    assert report.pages == 3
    with pikepdf.open(dst) as pdf:
        alts = {str(f.Alt) for f in pdf.Root.StructTreeRoot.K.K}
        assert alts == {ALT}


def test_alt_count_mismatch_raises(tmp_path):
    src = _vector_pdf(tmp_path / "s.pdf", n_pages=3)
    manifest = SheetManifest(title="Sheet", alt_texts=(ALT, ALT))
    with pytest.raises(ValueError, match="3-page"):
        tag_drawing_pdf(src, tmp_path / "t.pdf", manifest)


def test_refuses_double_tagging(tagged, tmp_path):
    dst, _, _ = tagged
    with pytest.raises(ValueError, match="already has a structure tree"):
        tag_drawing_pdf(dst, tmp_path / "again.pdf",
                        title="Sheet", alt_text=ALT)


def test_quick_path_requires_both_kwargs(tmp_path):
    src = _vector_pdf(tmp_path / "s.pdf", n_pages=1)
    with pytest.raises(ValueError, match="title= and alt_text="):
        tag_drawing_pdf(src, tmp_path / "t.pdf", title="Sheet")


def test_manifest_validation():
    with pytest.raises(ValueError, match="title"):
        SheetManifest(title="  ", alt_texts=(ALT,))
    with pytest.raises(ValueError, match="alt text"):
        SheetManifest(title="Sheet", alt_texts=())
    with pytest.raises(ValueError, match="alt text"):
        SheetManifest(title="Sheet", alt_texts=(ALT, " "))


def test_manifest_json_roundtrip(tmp_path):
    manifest = SheetManifest(
        title="HW-2.1 Half-Height Headwall", alt_texts=(ALT, ALT),
        language="en-US", author="dane", subject="standard drawing")
    path = tmp_path / "manifest.json"
    manifest.to_json(path)
    assert SheetManifest.from_json(path) == manifest

    (tmp_path / "bad.json").write_text('{"title": "x"}')
    with pytest.raises(ValueError, match="malformed"):
        SheetManifest.from_json(tmp_path / "bad.json")


def test_unembedded_font_warning(tmp_path):
    src = _vector_pdf(tmp_path / "s.pdf", n_pages=1,
                      with_unembedded_font=True)
    report = tag_drawing_pdf(src, tmp_path / "t.pdf",
                             title="Sheet", alt_text=ALT)
    assert any("not embedded" in w for w in report.warnings)


def test_pure_vector_has_no_warnings(tagged):
    _, _, report = tagged
    assert report.warnings == ()


def test_edge_page_shapes_and_docinfo(tmp_path):
    """Array contents, empty pages, and pre-existing viewer prefs all
    survive the retrofit; optional manifest fields land in docinfo."""
    pdf = pikepdf.new()
    p1 = pdf.add_blank_page(page_size=(612, 792))
    p1.obj.Contents = pdf.make_indirect(pikepdf.Array([
        pdf.make_stream(b"0 0 0 RG "),
        pdf.make_stream(b"72 72 100 100 re S"),
    ]))
    p2 = pdf.add_blank_page(page_size=(612, 792))
    del p2.obj["/Contents"]
    pdf.Root.ViewerPreferences = pikepdf.Dictionary(FitWindow=True)
    src = tmp_path / "edge.pdf"
    pdf.save(src)

    manifest = SheetManifest(title="Edge Sheet", alt_texts=(ALT,),
                             author="dane", subject="sandbox",
                             keywords="pdf/ua")
    report = tag_drawing_pdf(src, tmp_path / "edge_tagged.pdf", manifest)
    assert report.pages == 2
    with pikepdf.open(tmp_path / "edge_tagged.pdf") as out:
        assert len(out.pages[0].obj.Contents) == 4  # prefix + 2 + suffix
        assert len(out.pages[1].obj.Contents) == 2  # prefix + suffix only
        assert out.Root.ViewerPreferences.FitWindow == True  # noqa: E712
        assert out.Root.ViewerPreferences.DisplayDocTitle == True  # noqa: E712
        assert str(out.docinfo["/Author"]) == "dane"
        assert str(out.docinfo["/Subject"]) == "sandbox"
        assert str(out.docinfo["/Keywords"]) == "pdf/ua"


def _font_pdf(path, font):
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(612, 792))
    type3 = pikepdf.Dictionary(  # embedded by definition; audit skips it
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type3,
        CharProcs=pikepdf.Dictionary())
    page.obj.Resources = pikepdf.Dictionary(
        Font=pikepdf.Dictionary(F1=font, F2=type3))
    page.obj.Contents = pdf.make_stream(b"BT /F1 10 Tf (x) Tj ET")
    pdf.save(path)
    return pdf, path


def test_type0_font_audit(tmp_path):
    pdf = pikepdf.new()
    cid = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.CIDFontType2,
        BaseFont=pikepdf.Name("/NotoSans"))
    font = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type0,
        BaseFont=pikepdf.Name("/NotoSans"),
        DescendantFonts=pikepdf.Array([cid]))
    _font_pdf(tmp_path / "t0.pdf", font)
    report = tag_drawing_pdf(tmp_path / "t0.pdf", tmp_path / "t0_tagged.pdf",
                             title="Sheet", alt_text=ALT)
    assert any("NotoSans" in w and "not embedded" in w
               for w in report.warnings)


def test_malformed_type0_still_warns(tmp_path):
    font = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type0,
        BaseFont=pikepdf.Name("/Broken"))  # no DescendantFonts at all
    _font_pdf(tmp_path / "b.pdf", font)
    report = tag_drawing_pdf(tmp_path / "b.pdf", tmp_path / "b_tagged.pdf",
                             title="Sheet", alt_text=ALT)
    assert any("Broken" in w for w in report.warnings)


def test_embedded_font_passes_audit(tmp_path):
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(612, 792))
    descriptor = pikepdf.Dictionary(
        Type=pikepdf.Name.FontDescriptor,
        FontName=pikepdf.Name("/Embedded"),
        FontFile2=pdf.make_stream(b"\x00\x01"))
    font = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.TrueType,
        BaseFont=pikepdf.Name("/Embedded"), FontDescriptor=descriptor)
    page.obj.Resources = pikepdf.Dictionary(
        Font=pikepdf.Dictionary(F1=font))
    page.obj.Contents = pdf.make_stream(b"BT /F1 10 Tf (x) Tj ET")
    src = tmp_path / "e.pdf"
    pdf.save(src)
    report = tag_drawing_pdf(src, tmp_path / "e_tagged.pdf",
                             title="Sheet", alt_text=ALT)
    assert report.warnings == ()


@pytest.mark.skipif(shutil.which("verapdf") is None,
                    reason="veraPDF not installed")
def test_verapdf_accepts_output(tagged):
    dst, _, _ = tagged
    result = subprocess.run(
        ["verapdf", "--flavour", "ua1", "--format", "text", str(dst)],
        capture_output=True, text=True, timeout=120)
    assert result.stdout.strip().startswith("PASS"), result.stdout
