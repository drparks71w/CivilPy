# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Retrofit CAD drawing PDFs with a minimal PDF/UA (tagged PDF) structure.

CAD PDF exporters (Rhino's ``FilePdf``, Bentley Print Organizer, AutoCAD
plot drivers) emit untagged PDFs: raw vectors and text runs with no
``/StructTreeRoot``, no marked content, no alternative text. Assistive
technology gets nothing, and accessibility standards (WCAG / Section 508
via PDF/UA, ISO 14289) are normally satisfied afterward by hand in
Acrobat, sheet by sheet.

This module implements the honest, tractable slice of the problem — the
"whole sheet is one figure" retrofit (Tier 1 in
``docs/Accessible_Drawings.md``):

* each page's entire content stream is wrapped in a single
  marked-content sequence (``/Figure <</MCID 0>> BDC … EMC``) by
  *prepending and appending* tiny streams — the exporter's own bytes
  are never modified;
* one ``Figure`` structure element per page carries the alt text, a
  ``/BBox`` layout attribute, and is wired through a ``Document`` root
  and the parent tree;
* the document gets the rest of the PDF/UA plumbing: ``/MarkInfo``,
  ``/Lang``, ``/ViewerPreferences /DisplayDocTitle``, page ``/Tabs``,
  a doc-info title, and XMP metadata declaring ``pdfuaid:part=1``.

What it deliberately does **not** do: semantic decomposition of the
drawing (per-detail figures, notes as live text, tables) — that requires
regenerating the sheet, not retrofitting it (Tier 2) — and it cannot fix
non-embedded fonts; those are reported as warnings instead.

::

    from civilpy.general.pdf_ua import SheetManifest, tag_drawing_pdf

    manifest = SheetManifest(
        title="DS-1-92 Drip Strip Details",
        alt_texts=("Standard drawing of a concrete drip strip: section, "
                   "plan, and installation dimensions.",),
    )
    report = tag_drawing_pdf("DS-1-92.pdf", "DS-1-92_tagged.pdf", manifest)
    for w in report.warnings:
        print(w)

Requires ``pikepdf`` (``pip install civilpy[pdf]``). Output should still
be checked with a real validator (veraPDF, PAC) — this module makes the
file *structurally* conformant; only a validator plus human judgment on
the alt text makes it *actually* accessible.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union
from xml.sax.saxutils import escape

__all__ = ["SheetManifest", "TagReport", "tag_drawing_pdf"]


def _pikepdf():
    try:
        import pikepdf
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "pdf_ua needs pikepdf — install with: pip install civilpy[pdf]"
        ) from exc
    return pikepdf


@dataclass(frozen=True)
class SheetManifest:
    """What the tagger needs to know about a drawing PDF.

    ``alt_texts`` holds one entry per page, or a single entry that is
    broadcast to every page. The JSON form (``pages`` as a list of
    objects) is the contract for anything upstream that generates
    manifests — per-page objects can grow fields later (finer-grained
    tags, reading order) without breaking Tier 1 consumers.
    """

    title: str
    alt_texts: Tuple[str, ...]
    language: str = "en-US"
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None

    def __post_init__(self):
        if not self.title.strip():
            raise ValueError("manifest title must not be empty")
        if not self.alt_texts:
            raise ValueError("manifest needs at least one alt text")
        if any(not a.strip() for a in self.alt_texts):
            raise ValueError("alt texts must not be empty — the alt text "
                             "is the entire point of the Figure tag")
        object.__setattr__(self, "alt_texts", tuple(self.alt_texts))

    def to_json(self, path: Union[str, Path]) -> None:
        data = {
            "title": self.title,
            "language": self.language,
            "pages": [{"alt_text": a} for a in self.alt_texts],
        }
        for key in ("author", "subject", "keywords"):
            if getattr(self, key) is not None:
                data[key] = getattr(self, key)
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "SheetManifest":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        try:
            pages = data["pages"]
            alts = tuple(p["alt_text"] for p in pages)
            return cls(
                title=data["title"],
                alt_texts=alts,
                language=data.get("language", "en-US"),
                author=data.get("author"),
                subject=data.get("subject"),
                keywords=data.get("keywords"),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"malformed sheet manifest {path}: {exc}") from exc


@dataclass(frozen=True)
class TagReport:
    """What :func:`tag_drawing_pdf` did, and what it couldn't fix."""

    src: str
    dst: str
    pages: int
    warnings: Tuple[str, ...] = field(default_factory=tuple)


def _broadcast_alts(alts: Sequence[str], n_pages: int) -> Tuple[str, ...]:
    if len(alts) == n_pages:
        return tuple(alts)
    if len(alts) == 1:
        return tuple(alts) * n_pages
    raise ValueError(
        f"manifest has {len(alts)} alt texts for a {n_pages}-page PDF — "
        "provide exactly one per page, or a single one to broadcast")


def _xmp_packet(manifest: SheetManifest) -> bytes:
    title = escape(manifest.title)
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '  <rdf:Description rdf:about=""\n'
        '      xmlns:dc="http://purl.org/dc/elements/1.1/"\n'
        '      xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/">\n'
        '   <pdfuaid:part>1</pdfuaid:part>\n'
        '   <dc:title><rdf:Alt>'
        f'<rdf:li xml:lang="x-default">{title}</rdf:li>'
        '</rdf:Alt></dc:title>\n'
        '  </rdf:Description>\n'
        ' </rdf:RDF>\n'
        '</x:xmpmeta>\n'
        '<?xpacket end="w"?>'
    ).encode("utf-8")


def _font_warnings(pdf) -> Tuple[str, ...]:
    """Report fonts without embedded font programs (PDF/UA requires
    embedding; a retrofit can't add font programs after the fact)."""
    pikepdf = _pikepdf()
    seen, warnings = set(), []
    for page_no, page in enumerate(pdf.pages, start=1):
        resources = page.obj.get("/Resources")
        fonts = resources.get("/Font") if resources is not None else None
        if fonts is None:
            continue
        for name, font in fonts.items():
            subtype = str(font.get("/Subtype", ""))
            if subtype == "/Type3":
                continue  # glyph procedures live in the PDF by definition
            descriptor = font.get("/FontDescriptor")
            if subtype == "/Type0":
                try:
                    descriptor = font.DescendantFonts[0].get("/FontDescriptor")
                except (AttributeError, IndexError, pikepdf.PdfError):
                    descriptor = None
            embedded = descriptor is not None and any(
                key in descriptor
                for key in ("/FontFile", "/FontFile2", "/FontFile3"))
            base = str(font.get("/BaseFont", name))
            if not embedded and base not in seen:
                seen.add(base)
                warnings.append(
                    f"page {page_no}: font {base} is not embedded — "
                    "PDF/UA requires embedded fonts; re-export with font "
                    "embedding enabled")
    return tuple(warnings)


def tag_drawing_pdf(
    src: Union[str, Path],
    dst: Union[str, Path],
    manifest: Optional[SheetManifest] = None,
    *,
    title: Optional[str] = None,
    alt_text: Optional[str] = None,
    language: str = "en-US",
) -> TagReport:
    """Write ``dst`` as a tagged copy of ``src`` (one Figure per page).

    Pass either a :class:`SheetManifest`, or ``title=`` + ``alt_text=``
    for the single-alt quick path. Refuses PDFs that already carry a
    ``/StructTreeRoot`` — stacking a second structure tree on top of an
    existing one produces nonsense, and un-tagging is out of scope.
    """
    pikepdf = _pikepdf()
    Name, Dictionary, Array = pikepdf.Name, pikepdf.Dictionary, pikepdf.Array

    if manifest is None:
        if title is None or alt_text is None:
            raise ValueError("pass a SheetManifest, or both title= and alt_text=")
        manifest = SheetManifest(title=title, alt_texts=(alt_text,),
                                 language=language)

    src, dst = Path(src), Path(dst)
    with pikepdf.open(src) as pdf:
        if "/StructTreeRoot" in pdf.Root:
            raise ValueError(
                f"{src.name} already has a structure tree — refusing to "
                "double-tag (remediate or start from the untagged export)")

        n_pages = len(pdf.pages)
        alts = _broadcast_alts(manifest.alt_texts, n_pages)

        struct_root = pdf.make_indirect(Dictionary(Type=Name.StructTreeRoot))
        doc_elem = pdf.make_indirect(Dictionary(
            Type=Name.StructElem, S=Name.Document, P=struct_root))

        figures, nums = [], []
        for i, page in enumerate(pdf.pages):
            prefix = pdf.make_stream(b"/Figure <</MCID 0>> BDC\n")
            suffix = pdf.make_stream(b"\nEMC")
            contents = page.obj.get("/Contents")
            if contents is None:
                streams = [prefix, suffix]
            elif isinstance(contents, Array):
                streams = [prefix, *contents, suffix]
            else:
                streams = [prefix, contents, suffix]
            page.obj.Contents = pdf.make_indirect(Array(streams))
            page.obj.StructParents = i
            page.obj.Tabs = Name.S

            bbox = Array([float(v) for v in page.mediabox])
            figure = pdf.make_indirect(Dictionary(
                Type=Name.StructElem, S=Name.Figure, P=doc_elem,
                Pg=page.obj, K=0,
                Alt=pikepdf.String(alts[i]),
                A=Dictionary(O=Name.Layout, BBox=bbox, Placement=Name.Block),
            ))
            figures.append(figure)
            nums.append(i)
            nums.append(Array([figure]))

        doc_elem.K = Array(figures)
        struct_root.K = doc_elem
        struct_root.ParentTree = pdf.make_indirect(Dictionary(Nums=Array(nums)))
        struct_root.ParentTreeNext = n_pages

        pdf.Root.StructTreeRoot = struct_root
        pdf.Root.MarkInfo = Dictionary(Marked=True)
        pdf.Root.Lang = pikepdf.String(manifest.language)
        if "/ViewerPreferences" not in pdf.Root:
            pdf.Root.ViewerPreferences = Dictionary()
        pdf.Root.ViewerPreferences.DisplayDocTitle = True

        # Hand-built XMP: pikepdf's metadata editor doesn't know the
        # pdfuaid namespace, and round-tripping through it would drop
        # the conformance claim.
        pdf.Root.Metadata = pdf.make_stream(
            _xmp_packet(manifest), Type=Name.Metadata, Subtype=Name.XML)
        docinfo = pdf.docinfo
        docinfo["/Title"] = manifest.title
        for key, value in (("/Author", manifest.author),
                           ("/Subject", manifest.subject),
                           ("/Keywords", manifest.keywords)):
            if value is not None:
                docinfo[key] = value

        warnings = _font_warnings(pdf)
        pdf.save(dst)

    return TagReport(src=str(src), dst=str(dst), pages=n_pages,
                     warnings=warnings)
