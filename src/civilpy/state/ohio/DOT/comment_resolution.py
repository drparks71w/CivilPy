# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Parser for ODOT Comment Resolution Form spreadsheets.

The recon found these to be the single richest review artifact: structured
``comment / response / disposition`` tables, one row per review comment
(87 of them across the 34 sampled projects, named like
``LUC-475-10.21_115418_1350_COMMENT RESOLUTION FORM_August 2024.xlsx`` or
``20240109_DEF-115840_S1_disposition of comments.xlsx``).

Layouts vary by PM/consultant, so nothing is assumed about row/column
positions: the parser sniffs every worksheet for a header row (a row
where at least two cells fuzzy-match the known column aliases), maps the
columns it recognizes, and emits one dict per comment row.  Unrecognized
columns are preserved under ``extra`` — the raw layer is never thrown
away.

::

    from civilpy.state.ohio.DOT.comment_resolution import (
        parse_comment_resolution, is_resolution_filename)

    rows = parse_comment_resolution("Comment Resolution Form.xlsx")
    rows[0]["comment"], rows[0]["response"], rows[0]["disposition"]

Dispositions are additionally *classified* into
``accepted / revised / rejected / na / open`` by
:func:`classify_disposition` — keyword rules seeded from disposition
language observed in review PDFs; treat the raw text as ground truth and
the class as an interpretation layer.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

__all__ = ["COLUMN_ALIASES", "parse_comment_resolution",
           "parse_comment_resolutions", "classify_disposition",
           "is_resolution_filename"]

#: canonical field -> regexes matched (case-insensitively) against header
#: cell text.  First canonical field whose alias matches wins per cell.
COLUMN_ALIASES = {
    "seq": [r"^(comment\s*)?(no|num|number|item|#)\.?$", r"^comment\s*id$"],
    "sheet_ref": [r"^(sheet|sht|dwg|drawing|page)\b", r"sheet\s*(no|number)"],
    "discipline": [r"^(discipline|office|area|category)$"],
    "author": [r"^(commenter|reviewer|author|origin(ator)?|commented\s*by|"
               r"comment\s*by|by)$"],
    "comment": [r"^(review\s*)?comments?$", r"^comment\s*description$"],
    "response": [r"response", r"^resolution$", r"^reply$", r"^answer$"],
    "disposition": [r"disposi", r"^status$", r"^action$",
                    r"^accepted\??$", r"^concur"],
    "date": [r"^date\b"],
}

#: disposition text -> class.  Order matters (first hit wins): "will
#: revise, see response" must classify revised, not open.
_DISPOSITION_RULES = [
    ("na", re.compile(r"\bn/?a\b|not\s+applicable", re.I)),
    ("rejected", re.compile(
        r"reject|disagree|no\s+change|not\s+incorporat|withdrawn|"
        r"stands?\s+as\s+is", re.I)),
    ("revised", re.compile(
        r"revis|incorporat|updated|corrected|added|removed|will\s+(be\s+)?"
        r"(chang|fix|updat|address)|changed|done|complete|addressed|"
        r"closed|resolved", re.I)),
    ("accepted", re.compile(
        r"accept|concur|agree|acknowledged|noted|ok\b|yes\b", re.I)),
    ("open", re.compile(r"open|pending|tbd|to\s+be\s+determined|in\s+"
                        r"progress|under\s+review", re.I)),
]

RESOLUTION_NAME_PAT = re.compile(
    r"comment\s*resolution|resolution\s*form|disposition", re.IGNORECASE)


def is_resolution_filename(filename):
    """Whether a filename looks like a comment-resolution table (used to
    pick which review documents to pull and parse)."""
    name = filename or ""
    return bool(RESOLUTION_NAME_PAT.search(name)
                and name.lower().endswith((".xlsx", ".xlsm", ".xls"))) \
        or bool(re.search(r"_comments?\d*\.(xlsx|xlsm|xls)$", name,
                          re.IGNORECASE))


def classify_disposition(text):
    """``accepted / revised / rejected / na / open`` or ``None``."""
    if not text or not str(text).strip():
        return None
    s = str(text)
    for label, pat in _DISPOSITION_RULES:
        if pat.search(s):
            return label
    return None


def _match_header(cell):
    text = str(cell or "").strip()
    if not text or len(text) > 60:
        return None
    for field, pats in COLUMN_ALIASES.items():
        for pat in pats:
            if re.search(pat, text, re.IGNORECASE):
                return field
    return None


def _find_header(df, scan_rows=12):
    """``(row_index, {col_index: field})`` of the best header row, or
    ``(None, {})``.  A row qualifies with >=2 recognized fields, one of
    which must be ``comment``."""
    best = (None, {})
    for i in range(min(scan_rows, len(df))):
        mapping = {}
        for j, cell in enumerate(df.iloc[i]):
            field = _match_header(cell)
            if field and field not in mapping.values():
                mapping[j] = field
        if "comment" in mapping.values() and len(mapping) >= 2 \
                and len(mapping) > len(best[1]):
            best = (i, mapping)
    return best


def parse_comment_resolution(source, filename=None):
    """Parse one workbook into comment rows.

    ``source`` is a path, file-like object, or ``{sheet: DataFrame}``
    (header-less frames, as from ``pd.read_excel(..., header=None)``).
    Returns a list of dicts with the canonical fields (``seq, sheet_ref,
    discipline, author, comment, response, disposition, date``), the
    classified ``disposition_class``, ``extra`` (unmapped cells of the
    row), and provenance (``source_file, worksheet, header_row, row``).
    Worksheets without a recognizable header are skipped.
    """
    if isinstance(source, dict):
        sheets = source
    else:
        filename = filename or str(source)
        sheets = pd.read_excel(source, sheet_name=None, header=None,
                               dtype=object)
    rows = []
    for ws_name, df in sheets.items():
        if df.empty:
            continue
        header_row, mapping = _find_header(df)
        if header_row is None:
            continue
        headers = {j: str(df.iat[header_row, j] or "").strip()
                   for j in range(df.shape[1])}
        for i in range(header_row + 1, len(df)):
            raw = df.iloc[i]
            rec = {field: None for field in COLUMN_ALIASES}
            extra = {}
            for j, value in enumerate(raw):
                if pd.isna(value) or str(value).strip() == "":
                    continue
                value = str(value).strip()
                if j in mapping:
                    rec[mapping[j]] = value
                elif headers.get(j):
                    extra[headers[j]] = value
            if not rec["comment"]:
                continue                      # blank / spacer / totals row
            rec["disposition_class"] = (
                classify_disposition(rec["disposition"])
                or classify_disposition(rec["response"]))
            rec["extra"] = extra
            rec["source_file"] = filename
            rec["worksheet"] = ws_name
            rec["header_row"] = header_row
            rec["row"] = i
            rows.append(rec)
    return rows


def parse_comment_resolutions(paths):
    """Parse many workbooks -> one DataFrame (bad files are recorded, not
    fatal: rows with only ``source_file`` + ``error`` mark failures)."""
    all_rows = []
    for path in paths:
        try:
            all_rows.extend(parse_comment_resolution(path))
        except Exception as err:
            all_rows.append({"source_file": str(path),
                             "error": f"{type(err).__name__}: {err}"})
    return pd.DataFrame(all_rows)
