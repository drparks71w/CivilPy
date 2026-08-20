# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Reflow scrambled text from MicroStation / ORD / OBM plan-set PDFs.

Bentley products emit PDF text in draw order, not reading order: lines
inside a text block come out bottom-up, blocks come out in whatever
order they were drawn, and multi-column sheets interleave. ``get_text()``
on a General Notes sheet is word salad — but the *geometry* is intact
(every word carries correct coordinates), so reading order is mechanically
recoverable with no OCR and no ML:

1. take the page's text blocks,
2. cluster blocks into columns by x-position,
3. read columns left→right, blocks top→down, and **re-sort the lines
   inside every block by y** (undoing the bottom-up emission).

Verified against a 2026 ODOT full plan set: stream order gives
``"SPAN =24'-0"M AX."`` fragments; reflow returns the notes as written
("17. NOISE BARRIER FOUNDATION IN POOR SOIL: IN AREAS WHERE ...").

Two caveats this module is honest about:

* Sheets whose text was plotted **as vector curves** (common for title
  sheets) have no text layer at all — ``page_has_text`` returns False
  and reflow returns ``""``. Those pages need raster + OCR
  (:mod:`civilpy.state.ohio.DOT.title_sheet` finds the regions to OCR).
* Reflow recovers *paragraph text* (notes, specifications). Dimension
  strings and callouts scattered around a detail view have no linear
  reading order to recover; use the words + coordinates directly for
  those (``page.get_text("words")``).

::

    import fitz
    from civilpy.general.pdf_reflow import reflow_page, extract_numbered_notes

    doc = fitz.open("plan_set.pdf")
    text = reflow_page(doc[99])
    notes = extract_numbered_notes(text)
    notes[0]     # {"num": "17", "title": "NOISE BARRIER FOUNDATION ...", ...}
"""
from __future__ import annotations

import re

__all__ = ["page_has_text", "reflow_page", "reflow_pdf",
           "extract_numbered_notes", "find_notes_pages"]

#: Blocks whose left edges differ by more than this fraction of the page
#: width start a new column.  0.18 handles ODOT's 2-4 column note sheets.
COLUMN_GAP_FRAC = 0.18

#: "17. TITLE OF NOTE:" / "3) TITLE" / "A. TITLE" at the start of a line.
NOTE_HEAD_PAT = re.compile(
    r"^\s*(?P<num>\d{1,3}|[A-Z])[.)]\s+(?P<title>[^\n]{3,120})$",
    re.MULTILINE)


def page_has_text(page, min_chars=20):
    """Whether the page carries a usable text layer.

    Bentley title sheets are often pure vector geometry (text plotted as
    curves) — those need the OCR path, not reflow."""
    return len(page.get_text() or "") >= min_chars


def reflow_page(page, col_gap_frac=COLUMN_GAP_FRAC):
    """The page's text in reading order (columns left→right, blocks
    top→down, lines within a block re-sorted by y).

    Returns ``""`` for pages with no text layer.
    """
    d = page.get_text("dict")
    blocks = [b for b in d.get("blocks", []) if b.get("type") == 0]
    if not blocks:
        return ""
    width = page.rect.width or 1.0
    blocks.sort(key=lambda b: b["bbox"][0])
    columns, current, right_edge = [], [], None
    for b in blocks:
        if right_edge is None or b["bbox"][0] - right_edge < \
                width * col_gap_frac:
            current.append(b)
        else:
            columns.append(current)
            current = [b]
        x0 = b["bbox"][0]
        right_edge = x0 if right_edge is None else max(right_edge, x0)
    columns.append(current)

    out = []
    for column in columns:
        column.sort(key=lambda b: b["bbox"][1])
        for b in column:
            lines = sorted(b.get("lines", []),
                           key=lambda l: (round(l["bbox"][1], 1),
                                          l["bbox"][0]))
            for line in lines:
                text = "".join(s.get("text", "")
                               for s in line.get("spans", []))
                if text.strip():
                    out.append(text.rstrip())
    return "\n".join(out)


def reflow_pdf(source, pages=None, col_gap_frac=COLUMN_GAP_FRAC):
    """Reflow a whole document -> ``{page_number: text}`` (1-based).

    ``source`` is a path or an open ``fitz.Document``; ``pages`` limits
    to an iterable of 1-based page numbers.  Pages without a text layer
    map to ``""`` so callers can route them to OCR.
    """
    import fitz
    doc = source if isinstance(source, fitz.Document) else fitz.open(source)
    wanted = set(pages) if pages is not None else None
    result = {}
    for i, page in enumerate(doc, start=1):
        if wanted is not None and i not in wanted:
            continue
        result[i] = reflow_page(page, col_gap_frac=col_gap_frac)
    return result


def extract_numbered_notes(text):
    """Split reflowed notes text into individual notes.

    Returns ``[{"num", "title", "body"}]`` for headings shaped like
    ``17. NOISE BARRIER FOUNDATION IN POOR SOIL:`` — the unit the
    non-standard-note detector compares against the standard-note
    library.
    """
    notes = []
    matches = list(NOTE_HEAD_PAT.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        notes.append({"num": m["num"],
                      "title": m["title"].strip().rstrip(":"),
                      "body": body})
    return notes


def find_notes_pages(source, pattern=r"GENERAL\s+NOTES?|NOTES?\s*:"):
    """1-based page numbers whose text mentions a notes heading —
    a cheap router for where to run :func:`extract_numbered_notes`."""
    import fitz
    doc = source if isinstance(source, fitz.Document) else fitz.open(source)
    pat = re.compile(pattern, re.IGNORECASE)
    return [i for i, page in enumerate(doc, start=1)
            if pat.search(page.get_text() or "")]
