# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Deterministic (no-ML) title-sheet parser for ODOT plan sets.

Modern ODOT plan sets published through DigitalPaper carry a full vector
text layer on every page (verified: 143/143 pages of a 2024-award set),
so the title sheet parses with pure geometry — find the standard anchor
headings by phrase, then harvest the words in each anchor's capture
region:

* ``INDEX OF SHEETS`` — sheet titles + sheet-number column → the
  authoritative list for completeness checks (index says N sheets;
  does the set/archive have them?),
* ``STANDARD CONSTRUCTION DRAWINGS`` — SCD codes + revision dates,
* ``SUPPLEMENTAL SPECIFICATIONS`` / ``SPECIAL PROVISIONS``,
* ``PROJECT DESCRIPTION``, ``DESIGN DESIGNATION``,
  ``RAILROAD INVOLVEMENT``, ``FEDERAL PROJECT NUMBER``.

This is the fast path; the ML model
(:mod:`~civilpy.state.ohio.DOT.title_sheet`) remains the fallback for
scanned/curves-only sheets where no text layer exists — route on
:func:`~civilpy.general.pdf_reflow.page_has_text`.

::

    import fitz
    from civilpy.state.ohio.DOT.title_sheet_text import parse_title_sheet

    sheet = parse_title_sheet(fitz.open(pdf)[0])
    sheet["sheet_index"]     # [{"title": "GENERAL NOTES", "sheets": "5"}, ...]
    sheet["scds"]            # [{"code": "BP-1.1", "date": "7/28/00"}, ...]
"""
from __future__ import annotations

import re

__all__ = ["ANCHORS", "find_anchor", "parse_title_sheet",
           "parse_sheet_index", "expand_sheet_numbers"]

#: canonical field -> anchor phrase variants (matched on normalized words)
ANCHORS = {
    "sheet_index": ["INDEX OF SHEETS", "SHEET INDEX"],
    "scds": ["STANDARD CONSTRUCTION DRAWINGS"],
    "supplemental_specs": ["SUPPLEMENTAL SPECIFICATIONS"],
    "special_provisions": ["SPECIAL PROVISIONS"],
    "project_description": ["PROJECT DESCRIPTION"],
    "design_designation": ["DESIGN DESIGNATION"],
    "railroad": ["RAILROAD INVOLVEMENT"],
    "federal_project": ["FEDERAL PROJECT NUMBER", "FEDERAL PROJECT NO"],
    "earth_disturbed": ["EARTH DISTURBED AREAS"],
    "design_exceptions": ["DESIGN EXCEPTIONS"],
}

SCD_CODE_PAT = re.compile(r"^[A-Z]{1,4}-?\d[\d.\-]*M?$")
DATE_PAT = re.compile(r"^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$")
SHEET_NO_PAT = re.compile(r"^\d{1,3}(?:[-,]\d{1,3})*\.?$")


def _norm(token):
    return re.sub(r"[^\w]", "", (token or "").upper())


def _words(page):
    """(x0, y0, x1, y1, text) word tuples, geometry in points."""
    return [w[:5] for w in page.get_text("words")]


def find_anchor(words, phrase, y_tol=4.0):
    """Bounding box of ``phrase`` (consecutive words on one visual line),
    or ``None``.  Word tokens are compared punctuation-insensitively, so
    ``INDEX OF SHEETS:`` matches ``INDEX OF SHEETS``."""
    toks = [_norm(t) for t in phrase.split()]
    for i, w in enumerate(words):
        if _norm(w[4]) != toks[0]:
            continue
        got = [w]
        for tok in toks[1:]:
            nxt = [x for x in words
                   if abs(x[1] - w[1]) < y_tol and x[0] >= got[-1][2] - 2
                   and _norm(x[4]) == tok]
            if not nxt:
                break
            got.append(min(nxt, key=lambda x: x[0]))
        if len(got) == len(toks):
            return (got[0][0], min(g[1] for g in got),
                    got[-1][2], max(g[3] for g in got))
    return None


def _capture_region(words, anchor, anchors_below, page_height,
                    x_slack=12.0, x_span=None):
    """Words inside an anchor's capture region: from just under the
    anchor down to the next anchor that overlaps it horizontally (or the
    page bottom), spanning the anchor's column."""
    x0 = anchor[0] - x_slack
    x1 = anchor[2] + (x_span if x_span is not None else
                      3.0 * (anchor[2] - anchor[0]))
    y0 = anchor[3]
    y1 = page_height
    for other in anchors_below:
        if other[1] > anchor[3] and other[0] < x1 and other[2] > x0:
            y1 = min(y1, other[1] - 1)
    return [w for w in words
            if x0 <= w[0] < x1 and y0 < w[1] < y1]


def _lines(words, y_bin=5.0):
    """Group words into visual lines (sorted top-down, left-right)."""
    rows = {}
    for w in sorted(words, key=lambda w: (w[1], w[0])):
        key = round(w[1] / y_bin)
        for k in (key - 1, key, key + 1):
            if k in rows and abs(rows[k][0][1] - w[1]) < y_bin:
                rows[k].append(w)
                break
        else:
            rows[key] = [w]
    return [sorted(v, key=lambda w: w[0])
            for _, v in sorted(rows.items(),
                               key=lambda kv: kv[1][0][1])]


def parse_sheet_index(region_words):
    """``[{"title", "sheets"}]`` from the INDEX OF SHEETS region.

    Each visual row splits into the leftmost run of words (title) and a
    trailing sheet-number token (``5``, ``3-4``, ``11-17``); wrapped
    titles without a number merge into the previous entry when no number
    is present at all."""
    entries = []
    for line in _lines(region_words):
        texts = [w[4] for w in line]
        if not texts:
            continue
        sheets = None
        if SHEET_NO_PAT.match(texts[-1]) and len(texts) > 1:
            sheets = texts[-1].rstrip(".")
            texts = texts[:-1]
        title = " ".join(texts).strip().rstrip(".")
        if not title:
            continue
        if sheets is None and entries and entries[-1]["sheets"] is None:
            entries[-1]["title"] += " " + title
            continue
        entries.append({"title": title, "sheets": sheets})
    return entries


def expand_sheet_numbers(entries):
    """Every individual sheet number claimed by an index —
    ``[{"sheets": "3-4"}, {"sheets": "7"}]`` → ``{3, 4, 7}``.  This is
    the expected-set side of the archive-completeness check."""
    out = set()
    for e in entries:
        token = e.get("sheets")
        if not token:
            continue
        for part in token.split(","):
            if "-" in part:
                a, b = part.split("-", 1)
                if a.isdigit() and b.isdigit() and int(b) >= int(a):
                    out.update(range(int(a), int(b) + 1))
            elif part.isdigit():
                out.add(int(part))
    return out


def _parse_scds(region_words):
    """SCD ``code`` / ``date`` pairs from the standard-drawings block."""
    toks = [w[4] for line in _lines(region_words) for w in line]
    out, current = [], None
    for tok in toks:
        if SCD_CODE_PAT.match(tok.upper()):
            if current:
                out.append(current)
            current = {"code": tok.upper(), "date": None}
        elif DATE_PAT.match(tok) and current and current["date"] is None:
            current["date"] = tok
    if current:
        out.append(current)
    return out


def _region_text(region_words):
    return "\n".join(" ".join(w[4] for w in line)
                     for line in _lines(region_words))


def parse_title_sheet(page):
    """Parse one title-sheet page into a structured dict.

    Returns ``{"anchors_found": [...], "sheet_index": [...],
    "expected_sheets": {...}, "scds": [...], "supplemental_specs": str,
    "special_provisions": str, "project_description": str,
    "design_designation": str, "railroad": str, "federal_project": str,
    "pid_candidates": [...]}`` — fields whose anchor is absent are
    ``None``/empty.  Route curves-only pages (no text layer) to the ML
    model instead; see the module docstring.
    """
    words = _words(page)
    H = page.rect.height
    found = {}
    for field, phrases in ANCHORS.items():
        for phrase in phrases:
            box = find_anchor(words, phrase)
            if box:
                found[field] = box
                break
    boxes = list(found.values())
    regions = {field: _capture_region(words, box, boxes, H)
               for field, box in found.items()}

    result = {"anchors_found": sorted(found),
              "sheet_index": None, "expected_sheets": set(),
              "scds": None, "supplemental_specs": None,
              "special_provisions": None, "project_description": None,
              "design_designation": None, "railroad": None,
              "federal_project": None, "pid_candidates": []}
    if "sheet_index" in regions:
        result["sheet_index"] = parse_sheet_index(regions["sheet_index"])
        result["expected_sheets"] = expand_sheet_numbers(
            result["sheet_index"])
    if "scds" in regions:
        result["scds"] = _parse_scds(regions["scds"])
    for field in ("supplemental_specs", "special_provisions",
                  "project_description", "design_designation",
                  "railroad", "federal_project"):
        if field in regions:
            result[field] = _region_text(regions[field])

    # PID: usually in the right-edge title strip ("PID No. 123456") or
    # next to a "PID" label anywhere on the sheet.  Collect plausible
    # 5-7 digit numbers from both, de-duplicated, order-preserving.
    W = page.rect.width
    seen = set()

    def add(token):
        if re.fullmatch(r"\d{5,7}", token) and token not in seen:
            seen.add(token)
            result["pid_candidates"].append(token)

    pid_labels = [w for w in words if _norm(w[4]) in ("PID", "PIDNO",
                                                      "PIDNUMBER")]
    for label in pid_labels:                     # numbers near a PID label
        for w in words:
            near_x = abs(w[0] - label[0]) < 0.10 * W or \
                (label[2] <= w[0] <= label[2] + 0.10 * W)
            near_y = abs(w[1] - label[1]) < 40
            if near_x and near_y:
                add(w[4])
    for w in words:                              # right-edge title strip
        if w[0] > 0.90 * W:
            add(w[4])
    return result
