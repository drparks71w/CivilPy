# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Regex taxonomy for the *full* ODOT ProjectWise project tree.

Companion to :mod:`~civilpy.state.ohio.DOT.review_taxonomy` (which covers
the ``950-Reviews`` subtree in depth).  This module classifies any folder
path inside a project against the L&D Volume 3 numbered template, verified
against the 2026-07 recon of 34 projects / ~28k files across all twelve
ODOT districts and all five datasource roots:

* **Series** — the numbered top-level folders (``000-Admin``,
  ``100-Planning`` … ``990-WorkSetStandards``).  Consultant-parallel
  folders (``301-Survey_Korda``, ``401-Engineering_GPDgroup`` …) belong to
  the same series as their ODOT sibling: a project's Survey content is the
  **union** of ``300-Survey`` and every ``30X-Survey_*``.
* **Discipline** — the folder under ``400-Engineering`` (Roadway,
  Drainage, Structures, Geotechnical, Utilities, RW, MOT, Traffic …).
* **CADD bucket** — the ODOT triple ``Basemaps / EngData / Sheets`` every
  discipline folder carries.
* **Structure** — ``Structures/SFN_{sfn}`` and ``Wall_*`` per-structure
  folders (the SFN is the join key to SNBI / AssetWise / BrR).

The classifier never *resolves* fixed paths — it labels whatever segments
a walk encounters, so district / PM naming flavors don't break callers::

    >>> classify_project_path(["401-Engineering_GPDgroup", "Structures",
    ...                        "SFN_2502118", "Sheets"])["sfn"]
    '2502118'
"""
from __future__ import annotations

import re

__all__ = [
    "SERIES_FAMILIES", "DISCIPLINES", "CADD_BUCKETS",
    "TOP_FOLDER_PAT", "STRUCT_FOLDER_PAT",
    "parse_top_folder", "classify_project_path", "merge_key",
]

#: Family token (lower-cased, from the top folder name after the number)
#: -> canonical series key.  Numbers are *not* trusted: consultant-parallel
#: folders reuse the century digit with any suffix (301-, 305-, 402-), and
#: 000-Admin coexists with 010-ProjAdmin.
SERIES_FAMILIES = {
    "admin": "admin",
    "projadmin": "admin",
    "planning": "planning",
    "environmental": "environmental",
    "survey": "survey",
    "engineering": "engineering",
    "realestate": "real_estate",
    "contracts": "contracts",
    "construction": "construction",
    "accounting": "accounting",
    "reviews": "reviews",
    "worksetstandards": "workset_standards",
    "scratch": "scratch",
}

#: Canonical discipline keys under {4,40X}-Engineering, from the recon
#: (project counts: Roadway 13, Drainage 8, RW 8, Geotechnical 8, MOT 6,
#: Structures 6, Utilities 5, Traffic 5, Lighting 1, Landscaping 1).
DISCIPLINES = {
    "roadway": "roadway",
    "drainage": "drainage",
    "structures": "structures",
    "geotechnical": "geotechnical",
    "geotech": "geotechnical",
    "utilities": "utilities",
    "utility": "utilities",
    "rw": "rw",
    "right of way": "rw",
    "mot": "mot",
    "traffic": "traffic",
    "lighting": "lighting",
    "landscaping": "landscaping",
    "signals": "traffic",
}

#: The ODOT CADD triple present inside every discipline folder.
CADD_BUCKETS = {"basemaps": "basemaps", "engdata": "engdata",
                "sheets": "sheets"}

#: ``300-Survey``, ``000-Admin``, ``301-Survey_Korda``,
#: ``401-Engineering_GPDgroup``, ``990-WorkSetStandards`` ...
TOP_FOLDER_PAT = re.compile(
    r"^(?P<number>\d{3})-(?P<family>[A-Za-z ]+?)(?:_(?P<consultant>.+))?$")

#: ``SFN_2502118``, ``SFN 2502118``, ``Wall_000``, ``Wall MSE-1`` — the
#: per-structure folders under a Structures discipline folder.
STRUCT_FOLDER_PAT = re.compile(
    r"^(?:SFN[_ ]?(?P<sfn>\d{1,7})|WALL[_ ]?(?P<wall>\S+))",
    re.IGNORECASE)


def parse_top_folder(name):
    """Parse one top-level (series) folder name.

    Returns ``{"number", "series", "consultant"}`` or ``None`` when the
    name is not a numbered series folder.  ``consultant`` is ``None`` for
    the ODOT folder itself.

    >>> parse_top_folder("301-Survey_Korda")
    {'number': '301', 'series': 'survey', 'consultant': 'Korda'}
    >>> parse_top_folder("990-WorkSetStandards")["series"]
    'workset_standards'
    >>> parse_top_folder("Photos") is None
    True
    """
    m = TOP_FOLDER_PAT.match((name or "").strip())
    if not m:
        return None
    family = re.sub(r"[^a-z]", "", m["family"].lower())
    series = SERIES_FAMILIES.get(family)
    if series is None:
        return None
    return {"number": m["number"], "series": series,
            "consultant": m["consultant"]}


def classify_project_path(segments):
    """Classify the folder segments of one document, project-root-relative.

    ``segments`` is the list of folder names *below* the project folder
    (the document's parent chain, outermost first).  Returns::

        {"series":      "survey" | "engineering" | ... | None,
         "number":      "300" | "401" | ... | None,
         "consultant":  "GPDgroup" | None,
         "discipline":  "structures" | "roadway" | ... | None,
         "bucket":      "basemaps" | "engdata" | "sheets" | None,
         "sfn":         "2502118" | None,     # zero-padded to 7 digits
         "wall":        "000" | None,
         "area":        "Scopes" | "SurveyData" | ... | None}

    ``area`` is the first sub-folder under a non-engineering series (the
    deterministic anchors: ``100-Planning/Scopes``,
    ``300-Survey/SurveyData`` ...).  All keys are always present.
    """
    info = {"series": None, "number": None, "consultant": None,
            "discipline": None, "bucket": None, "sfn": None,
            "wall": None, "area": None}
    for i, seg in enumerate(segments):
        seg = (seg or "").strip()
        if i == 0:
            top = parse_top_folder(seg)
            if top:
                info["series"] = top["series"]
                info["number"] = top["number"]
                info["consultant"] = top["consultant"]
                continue
            # not a numbered folder (root-level stray file / odd tree)
            return info
        low = seg.lower()
        if low in CADD_BUCKETS:
            info["bucket"] = CADD_BUCKETS[low]
            continue
        m = STRUCT_FOLDER_PAT.match(seg)
        if m and info["discipline"] == "structures":
            if m["sfn"]:
                info["sfn"] = m["sfn"].zfill(7)
            else:
                info["wall"] = m["wall"]
            continue
        if info["series"] == "engineering" and info["discipline"] is None:
            info["discipline"] = DISCIPLINES.get(low, low or None)
            continue
        if info["series"] not in (None, "engineering") \
                and info["area"] is None:
            info["area"] = seg
    return info


def merge_key(info):
    """The identity a document keeps across consultant-parallel folders.

    Two documents with the same merge key belong to the same logical
    branch of the project no matter which firm's folder they sit in:
    ``(series, discipline, sfn-or-wall)``.

    >>> a = classify_project_path(["300-Survey", "SurveyData"])
    >>> b = classify_project_path(["301-Survey_Korda", "SurveyData"])
    >>> merge_key(a) == merge_key(b)
    True
    """
    return (info.get("series"), info.get("discipline"),
            info.get("sfn") or info.get("wall"))
