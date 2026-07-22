# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Regex taxonomy for ODOT ProjectWise review folders and files.

Derived from the 2026-07 district recon (28 sampled structural-review
projects, ~23k filenames): the numbered project *folder* template is
essentially universal, but everything below ``950-Reviews`` is
PM-flavored.  Two dominant layouts cover ~80%::

    950-Reviews/PlanReviews/01-Stage2/{01-Submission,02-Comments,
                                      03-Disposition of Comments}/...
    950-Reviews/Stage 2/{Submission,Comments}/...

plus per-deliverable trees like
``Structure Type Studies/<bridge>/<YYYYMMDD Resubmittal>/Submittal``.
File naming is freeform (only ~6% follow the L&D §1204 codes), so
discovery works by *classifying* folder segments and filenames with the
patterns here instead of resolving fixed paths.
"""
from __future__ import annotations

import re

#: Stage number in a folder or file segment: "Stage 1", "Stage1",
#: "01-Stage2", "Pre-Stage 1", "S2" (file shorthand handled separately).
STAGE_PAT = re.compile(r"(?:\b|_|-)(?:pre-?)?stage\s*_?-?\s*([123])\b", re.I)
FILE_STAGE_PAT = re.compile(r"(?:\b|_)S([123])(?:\b|_)")

#: Role of a folder within a review thread.  Order matters: the first
#: matching role wins per segment ("03-Disposition of Comments" is a
#: disposition folder, not a comments folder).
ROLE_PATTERNS = {
    "disposition": re.compile(r"disposi", re.I),
    "submission": re.compile(r"submi(?:ssion|ttal)", re.I),
    "comments": re.compile(r"comment|markup", re.I),
}

#: Review type, usually the first level under 950-Reviews.
TYPE_PATTERNS = {
    "plan_review": re.compile(r"plan\s*reviews?", re.I),
    "sts": re.compile(r"structure\s*type\s*stud|type\s*study|\bSTS\b", re.I),
    "aer": re.compile(r"\bAERs?\b|alternative\s*evaluation", re.I),
    "load_rating": re.compile(r"load\s*rating", re.I),
    "tracings": re.compile(r"tracing", re.I),
    "feasibility": re.compile(r"feasibility", re.I),
    "geotech": re.compile(r"geotech", re.I),
    "right_of_way": re.compile(r"\bRW\b|right[\s-]*of[\s-]*way", re.I),
    "preliminary": re.compile(r"preliminary", re.I),
}

#: Dated submittal folders: "20230802 Resubmittal", "20240405 Submission".
DATED_PAT = re.compile(r"^(\d{4})(\d{2})(\d{2})\b")
RESUBMIT_PAT = re.compile(r"re-?submi", re.I)

#: File-content kinds (checked in order — first hit wins).
FILE_KIND_PATTERNS = [
    ("disposition", re.compile(r"disposi", re.I)),
    ("markups", re.compile(r"markup", re.I)),
    ("comments", re.compile(r"comment", re.I)),
    ("load_rating", re.compile(r"load\s*rating|\bBR-?100\b", re.I)),
    ("estimate", re.compile(r"estimate|\.est$", re.I)),
    ("transmittal", re.compile(r"transmittal", re.I)),
    ("report", re.compile(r"report|study", re.I)),
    ("checklist", re.compile(r"checklist", re.I)),
    ("correspondence", re.compile(r"\.msg$", re.I)),
    ("plan_set", re.compile(r"plans?\b|\bplan\s*set", re.I)),
]

SFN_PAT = re.compile(r"(?<!\d)(\d{7})(?!\d)")
PID_PAT = re.compile(r"PID\s*_?(\d{5,6})", re.I)


def classify_review_path(segments):
    """Classify the folder segments *below* ``950-Reviews``.

    Returns ``{"stage", "roles", "types", "dated", "resubmittal"}`` where
    stage is ``"1"|"2"|"3"|None``, roles/types are sorted lists, dated is
    ``"YYYY-MM-DD"`` of the innermost dated submittal folder (or None).
    """
    stage = None
    roles, types = set(), set()
    dated, resub = None, False
    for seg in segments:
        m = STAGE_PAT.search(seg)
        if m:
            stage = m.group(1)
        for role, pat in ROLE_PATTERNS.items():
            if pat.search(seg):
                roles.add(role)
                break                      # first matching role wins per segment
        for typ, pat in TYPE_PATTERNS.items():
            if pat.search(seg):
                types.add(typ)
        m = DATED_PAT.match(seg)
        if m:
            dated = "-".join(m.groups())
        if RESUBMIT_PAT.search(seg):
            resub = True
    return {"stage": stage, "roles": sorted(roles), "types": sorted(types),
            "dated": dated, "resubmittal": resub}


def classify_review_file(filename):
    """Classify one filename: ``{"kind", "stage", "sfn", "pid"}``."""
    kind = next((k for k, pat in FILE_KIND_PATTERNS
                 if pat.search(filename)), None)
    m = STAGE_PAT.search(filename) or FILE_STAGE_PAT.search(filename)
    sfn = SFN_PAT.search(filename)
    pid = PID_PAT.search(filename)
    return {"kind": kind, "stage": m.group(1) if m else None,
            "sfn": sfn.group(1) if sfn else None,
            "pid": pid.group(1) if pid else None}
