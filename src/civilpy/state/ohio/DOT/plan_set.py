# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Open an ODOT DigitalPaper plan set and reach its real sheet pages.

DigitalPaper serves a project's plans as one download, but that top-level
PDF is frequently a **Bluebeam PDF package**: a 1-page wrapper carrying
the actual plan PDFs (``{CTY}-{PID}-Plan.pdf``, ``-Plan-RW.pdf``,
``-WP.pdf``) as *embedded files*.  ``fitz.open`` on the wrapper shows one
"install Bluebeam" page — the sheets are in the embedded-file array.

:func:`open_plan_set` unwraps that: it returns the constituent plan
documents (the main plan set first), each already a real multi-page sheet
document.  Non-package PDFs (a single flat plan set, or scanned TIFF-based
sets) pass through unchanged.

::

    from civilpy.state.ohio.DOT.plan_set import open_plan_set, title_page

    parts = open_plan_set("115840.pdf")     # [PlanDoc(...), ...]
    tp = title_page(parts)                  # the sheet-1 fitz.Page
"""
from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["PlanDoc", "open_plan_set", "title_page", "MAIN_PLAN_RE"]

#: the main plan set among a package's parts (vs -RW right-of-way, -WP
#: waterway-permit, addenda).  Higher score sorts first.
MAIN_PLAN_RE = re.compile(r"-Plan\.pdf$", re.IGNORECASE)
_RW_RE = re.compile(r"-(RW|WP|SUP|ADD|Addenda)\b|-Plan-", re.IGNORECASE)
_PACKAGE_HINT = re.compile(r"bluebeam|pdf package|portfolio", re.IGNORECASE)


@dataclass
class PlanDoc:
    """One real plan document unwrapped from a set."""
    name: str
    doc: "fitz.Document"          # noqa: F821
    role: str                    # "plan" | "rw" | "wp" | "other"
    source: str                  # the file/package it came from

    @property
    def n_pages(self):
        return self.doc.page_count


def _role(name):
    low = name.lower()
    if "-plan-rw" in low or low.endswith("-rw.pdf") or "right" in low:
        return "rw"
    if low.endswith("-wp.pdf") or "waterway" in low or "permit" in low:
        return "wp"
    if MAIN_PLAN_RE.search(name) or low.endswith("-plan.pdf"):
        return "plan"
    return "other"


def _is_package(doc):
    """A wrapper package = has embedded files AND (one page OR a Bluebeam
    hint on page 1)."""
    try:
        names = doc.embfile_names()
    except Exception:
        names = []
    if not names:
        return False
    if doc.page_count <= 1:
        return True
    head = (doc[0].get_text() or "")[:400]
    return bool(_PACKAGE_HINT.search(head))


def open_plan_set(source):
    """Return the plan set's real documents as ``[PlanDoc, ...]``.

    ``source`` is a path or open ``fitz.Document``.  A Bluebeam package
    is expanded to its embedded PDFs; a flat plan PDF returns a single
    ``PlanDoc``.  Ordering: main plan first, then RW / WP / other.
    Embedded non-PDF entries are skipped.
    """
    import fitz
    doc = source if isinstance(source, fitz.Document) else fitz.open(source)
    src_name = getattr(doc, "name", str(source))
    if not _is_package(doc):
        return [PlanDoc(name=src_name.split("/")[-1], doc=doc,
                        role=_role(src_name), source=src_name)]
    parts = []
    for i, raw in enumerate(doc.embfile_names()):
        info = doc.embfile_info(i)
        name = info.get("filename") or raw
        if not name.lower().endswith(".pdf"):
            continue
        data = doc.embfile_get(i)
        try:
            sub = fitz.open(stream=data, filetype="pdf")
        except Exception:
            continue
        parts.append(PlanDoc(name=name, doc=sub, role=_role(name),
                             source=src_name))
    order = {"plan": 0, "rw": 1, "wp": 2, "other": 3}
    parts.sort(key=lambda p: (order.get(p.role, 9), p.name))
    return parts or [PlanDoc(name=src_name.split("/")[-1], doc=doc,
                             role="other", source=src_name)]


def title_page(parts):
    """The title sheet (page 1 of the main plan document) from
    :func:`open_plan_set`'s result, or ``None`` if empty."""
    for p in parts:
        if p.role == "plan" and p.n_pages:
            return p.doc[0]
    for p in parts:
        if p.n_pages:
            return p.doc[0]
    return None
