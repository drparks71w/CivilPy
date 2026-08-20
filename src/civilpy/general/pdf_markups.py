# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Extract markup/comment annotations from PDFs (Bluebeam-aware).

Bluebeam Revu stores its markups as standard PDF annotations with a few
vendor extensions: ``/T`` is the author, ``/Contents`` the comment text,
``/Subj`` the markup tool name ("Callout", "Cloud+", "Text Box", ...),
``/IRT`` links replies to their parent markup, and ``/BSIColumnData``
carries Bluebeam's custom-column values.  Everything here reads through
PyMuPDF (``civilpy[pdf]`` extra) and degrades gracefully when the
vendor keys are absent, so it works on any annotated PDF.
"""
from __future__ import annotations


def extract_markups(pdf_path, include_bluebeam_raw=True):
    """Return one dict per markup annotation in ``pdf_path``.

    Keys: ``page`` (1-based), ``type``, ``author``, ``subject``,
    ``contents``, ``created``, ``modified``, ``rect`` (x0, y0, x1, y1),
    ``id`` (the annotation's /NM name), ``reply_to`` (the parent
    markup's id when this is a reply, else None), and — when
    ``include_bluebeam_raw`` — ``bluebeam`` with any ``/BSI*`` vendor
    keys found on the annotation.

    Pop-up helper annotations (the little note windows) are skipped;
    they duplicate their parent markup's text.
    """
    import fitz  # PyMuPDF — civilpy[pdf] extra

    markups = []
    with fitz.open(str(pdf_path)) as doc:
        xref_names = {}          # annotation xref -> /NM, for reply linking
        raw = []
        for page_index, page in enumerate(doc):
            for annot in page.annots() or []:
                if annot.type[1] == "Popup":
                    continue
                info = annot.info
                entry = {
                    "page": page_index + 1,
                    "type": annot.type[1],
                    "author": info.get("title", ""),
                    "subject": info.get("subject", ""),
                    "contents": (info.get("content") or "").strip(),
                    "created": info.get("creationDate", ""),
                    "modified": info.get("modDate", ""),
                    "rect": tuple(round(v, 2) for v in annot.rect),
                    "id": info.get("id", ""),
                    "reply_to": None,
                }
                xref_names[annot.xref] = entry["id"]
                irt = doc.xref_get_key(annot.xref, "IRT")
                irt_xref = None
                if irt and irt[0] == "xref":
                    irt_xref = int(irt[1].split()[0])
                # anchor geometry: arrows/leaders point AT the referent —
                # a comment like "move to sheet 3" is meaningless without
                # where the arrow head lands.
                try:
                    verts = annot.vertices
                except Exception:
                    verts = None
                if verts:
                    entry["vertices"] = [(round(x, 2), round(y, 2))
                                         for x, y in verts]
                    if entry["type"] in ("Line", "PolyLine"):
                        entry["arrow_head"] = entry["vertices"][-1]
                if include_bluebeam_raw:
                    bsi = {}
                    for key in doc.xref_get_keys(annot.xref):
                        if key.startswith("BSI"):
                            bsi[key] = doc.xref_get_key(annot.xref, key)[1]
                    if bsi:
                        entry["bluebeam"] = bsi
                raw.append((entry, irt_xref))

        for entry, irt_xref in raw:
            if irt_xref is not None:
                entry["reply_to"] = xref_names.get(irt_xref)
            markups.append(entry)
    return markups


def markup_summary(markups):
    """Aggregate a list from :func:`extract_markups` into counts.

    Returns ``{"total", "replies", "pages", "by_author", "by_subject",
    "by_type"}`` — the shape used for review-log dashboards.
    """
    from collections import Counter

    by_author, by_subject, by_type = Counter(), Counter(), Counter()
    pages = set()
    replies = 0
    for m in markups:
        by_author[m["author"] or "(unknown)"] += 1
        by_subject[m["subject"] or m["type"]] += 1
        by_type[m["type"]] += 1
        pages.add(m["page"])
        if m["reply_to"]:
            replies += 1
    return {
        "total": len(markups),
        "replies": replies,
        "pages": sorted(pages),
        "by_author": dict(by_author.most_common()),
        "by_subject": dict(by_subject.most_common()),
        "by_type": dict(by_type.most_common()),
    }


def anchor_text(pdf_path, markup, margin=72):
    """Sheet text near a markup's anchor — labels, dimensions, detail
    titles under the arrow/cloud.  ``margin`` is in points (72 = 1 inch).

    This is what turns "move to sheet 3" + an arrow into a record that
    knows *what* should move: the words the annotation points at.
    """
    import fitz

    with fitz.open(str(pdf_path)) as doc:
        page = doc[markup["page"] - 1]
        pts = [markup.get("arrow_head")] if markup.get("arrow_head") else []
        pts += list(markup.get("vertices") or [])
        rect = fitz.Rect(*markup["rect"])
        for x, y in [p for p in pts if p]:
            rect |= fitz.Rect(x, y, x, y)
        clip = fitz.Rect(rect.x0 - margin, rect.y0 - margin,
                         rect.x1 + margin, rect.y1 + margin) & page.rect
        # whole words whose box touches the clip — get_text(clip=...) would
        # slice words at the boundary ("ABUTMENT E")
        words = [w for w in page.get_text("words")
                 if fitz.Rect(w[:4]).intersects(clip)]
        return " ".join(w[4] for w in words).strip()


def render_clip(pdf_path, markup, out_path, margin=108, dpi=150):
    """Render the sheet region around a markup to a PNG.

    The clip is the self-contained visual context for a comment card —
    reviewable (by human or model) without hauling the full plan set.
    Returns the output path.
    """
    import fitz

    with fitz.open(str(pdf_path)) as doc:
        page = doc[markup["page"] - 1]
        rect = fitz.Rect(*markup["rect"])
        for x, y in ([markup["arrow_head"]] if markup.get("arrow_head") else []):
            rect |= fitz.Rect(x, y, x, y)
        clip = fitz.Rect(rect.x0 - margin, rect.y0 - margin,
                         rect.x1 + margin, rect.y1 + margin) & page.rect
        pix = page.get_pixmap(clip=clip, dpi=dpi)
        pix.save(str(out_path))
    return out_path
