# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tier-2 completion / absence checks over an ODOT ProjectWise project.

The automated-review strategy triages findings into three tiers:

1. **auto** — deterministic lint (sheet naming, CADD standards) that
   should never reach a human as a review comment;
2. **absence** — a deliverable the L&D template says should exist by now
   is missing.  Majors are usually omissions, and omissions are checkable
   without AI: this module is that checklist;
3. **judgment** — design-level review, out of scope here (the MCP
   assistant's job — grounded, cited, volume-capped).

Every check runs against :meth:`ProjectWiseProject.query
<civilpy.state.ohio.DOT.pw_project.ProjectWiseProject.query>`, so it
works identically on the live datasource and on committed snapshots
(:mod:`~civilpy.state.ohio.DOT.pw_snapshot`).  Checks that only make
sense for a bridge project skip themselves (``status="n/a"``) when the
project has no Structures branch.

::

    from civilpy.state.ohio.DOT.review_checks import run_checks, summarize

    findings = run_checks(project, stage=3)
    summarize(findings)     # {'ok': 8, 'missing': 2, ...}

A finding is a plain dict::

    {"check": "load_rating", "tier": "absence", "status": "missing",
     "stage": 3, "evidence": "...", "n_docs": 0}

``status`` values: ``ok`` (evidence found), ``missing`` (should exist,
doesn't), ``attention`` (exists but incomplete — e.g. comments without a
disposition), ``n/a`` (check does not apply to this project/stage).
"""
from __future__ import annotations

import re

__all__ = ["run_checks", "summarize", "review_rounds",
           "comments_addressed", "sheet_naming_conformance", "CHECKS"]

UTILITY_PAT = re.compile(r"util", re.IGNORECASE)
GEOTECH_PAT = re.compile(r"boring|geotech|soil|\bB-?\d{3}\b", re.IGNORECASE)
SCOPE_PAT = re.compile(r"scope", re.IGNORECASE)
ALTERNATIVE_PAT = re.compile(r"alt(?:ernative)?s?\b|\bconceptual",
                             re.IGNORECASE)


def _finding(check, tier, status, evidence, n_docs=0, stage=None):
    return {"check": check, "tier": tier, "status": status,
            "stage": stage, "evidence": evidence, "n_docs": n_docs}


def _has_structures(project):
    return bool(project.query(discipline="structures")
                or project.query(series="reviews", pattern=r"SFN|structure"))


# -- individual checks ---------------------------------------------------------

def check_scope_form(project, stage=None):
    """100-Planning/Scopes must hold a scope form (the 'was it scoped'
    anchor; present in 18/28 recon projects, 2,023/7,727 corpus-wide)."""
    docs = project.query(series="planning", area="Scopes")
    forms = [d for d in docs if SCOPE_PAT.search(d.get("filename") or "")]
    if forms:
        return _finding("scope_form", "absence", "ok",
                        f"e.g. {forms[0]['filename']}", len(forms))
    if docs:
        return _finding("scope_form", "absence", "attention",
                        f"Scopes folder has {len(docs)} docs but none "
                        "named like a scope form", len(docs))
    return _finding("scope_form", "absence", "missing",
                    "no 100-Planning/Scopes documents")


def check_survey_reports(project, stage=None):
    """300-Survey/SurveyData must exist with content (28/28 in recon —
    its absence is a red flag on any real project)."""
    docs = project.query(series="survey")
    if docs:
        return _finding("survey_data", "absence", "ok",
                        f"{len(docs)} survey documents", len(docs))
    return _finding("survey_data", "absence", "missing",
                    "no 300-Survey content")


def check_utility_shots(project, stage=None):
    """Utility evidence: utilities discipline content, or utility-named
    survey files.  Missing utility survey shots is a canonical
    construction-conflict precursor."""
    docs = project.query(discipline="utilities")
    if not docs:
        docs = [d for d in project.query(series="survey")
                if UTILITY_PAT.search(d.get("filename") or "")]
    if docs:
        return _finding("utility_evidence", "absence", "ok",
                        f"e.g. {docs[0]['filename']}", len(docs))
    return _finding("utility_evidence", "absence", "missing",
                    "no utilities discipline content and no utility-named "
                    "survey files")


def check_geotech(project, stage=None):
    """Geotechnical exploration present (borings / geotech EngData)."""
    docs = project.query(discipline="geotechnical")
    if not docs:
        docs = [d for d in project.walk()
                if GEOTECH_PAT.search(d.get("filename") or "")]
    if docs:
        return _finding("geotech", "absence", "ok",
                        f"e.g. {docs[0]['filename']}", len(docs))
    return _finding("geotech", "absence", "missing",
                    "no geotechnical discipline content or boring-named "
                    "files anywhere")


def check_sfn_folders(project, stage=None):
    """Bridge projects must carry per-structure ``Structures/SFN_*``
    folders with content (627/7,727 projects corpus-wide)."""
    if not _has_structures(project):
        return _finding("sfn_folders", "absence", "n/a",
                        "no structures branch on this project")
    docs = project.query(discipline="structures")
    sfns = sorted({d["tree"]["sfn"] for d in docs if d["tree"]["sfn"]})
    if sfns:
        return _finding("sfn_folders", "absence", "ok",
                        f"SFN folders: {', '.join(sfns)}", len(docs))
    if docs:
        return _finding("sfn_folders", "absence", "attention",
                        f"Structures has {len(docs)} docs but no SFN_* "
                        "folders (files not filed per structure)",
                        len(docs))
    return _finding("sfn_folders", "absence", "missing",
                    "Structures discipline exists but is empty")


def check_sts(project, stage=None):
    """A Structure Type Study must exist (and show alternatives) before
    detail design on a structure project."""
    if not _has_structures(project):
        return _finding("sts", "absence", "n/a",
                        "no structures branch on this project")
    docs = project.query(pattern=r"structure\s*type\s*stud|\bSTS\b")
    docs += [d for d in project.query(series="reviews")
             if "sts" in (d.get("review_path", {}).get("types") or [])]
    if not docs:
        return _finding("sts", "absence", "missing",
                        "no Structure Type Study documents anywhere",
                        stage=stage)
    alts = [d for d in docs
            if ALTERNATIVE_PAT.search(d.get("filename") or "")]
    if alts:
        return _finding("sts", "absence", "ok",
                        f"STS with alternatives: {alts[0]['filename']}",
                        len(docs))
    return _finding("sts", "absence", "ok",
                    f"e.g. {docs[0]['filename']} (alternatives not "
                    "evident from filenames)", len(docs))


def check_load_rating(project, stage=None):
    """Load-rating files must exist by Stage 3 on a structure project."""
    if not _has_structures(project):
        return _finding("load_rating", "absence", "n/a",
                        "no structures branch on this project")
    docs = project.query(pattern=r"load\s*rating|\bBR-?100\b")
    if docs:
        return _finding("load_rating", "absence", "ok",
                        f"e.g. {docs[0]['filename']}", len(docs),
                        stage=stage)
    status = "missing" if (stage or 0) >= 3 else "attention"
    return _finding("load_rating", "absence", status,
                    "no load-rating documents "
                    + ("(required at Stage 3)" if (stage or 0) >= 3
                       else "(will be required by Stage 3)"),
                    stage=stage)


def check_contracts(project, stage=None):
    """600-Contracts (the as-advertised set) must exist for a project at
    or past sale."""
    docs = project.query(series="contracts")
    if docs:
        return _finding("as_advertised", "absence", "ok",
                        f"{len(docs)} contract documents", len(docs))
    status = "missing" if (stage or 0) >= 4 else "n/a"
    return _finding("as_advertised", "absence", status,
                    "no 600-Contracts content"
                    + ("" if status == "missing"
                       else " (project not at sale)"), stage=stage)


def check_review_rounds(project, stage=None):
    """Every review round with comments needs a disposition — the
    'were the comments addressed' check."""
    rounds = review_rounds(project)
    if not rounds:
        return _finding("review_rounds", "absence", "attention",
                        "no classified review documents under 950-Reviews")
    open_rounds = [r for r in rounds
                   if r["comments"] and not r["dispositions"]]
    if open_rounds:
        labels = ", ".join(_round_label(r) for r in open_rounds[:4])
        return _finding("review_rounds", "absence", "attention",
                        f"{len(open_rounds)}/{len(rounds)} rounds have "
                        f"comments with no disposition: {labels}",
                        sum(len(r['comments']) for r in open_rounds))
    return _finding("review_rounds", "absence", "ok",
                    f"{len(rounds)} rounds, all comment sets have "
                    "dispositions or no comments yet",
                    sum(len(r['comments']) for r in rounds))


def check_sheet_naming(project, stage=None):
    """Tier-1 lint: fraction of CADD sheets following the L&D §1204
    filename codes.  Never a human comment — pre-submission tooling."""
    ratio, n_sheets = sheet_naming_conformance(project)
    if n_sheets == 0:
        return _finding("sheet_naming", "auto", "n/a",
                        "no documents in Sheets/Basemaps buckets")
    status = "ok" if ratio >= 0.5 else "attention"
    return _finding("sheet_naming", "auto", status,
                    f"{ratio:.0%} of {n_sheets} CADD files parse against "
                    "the L&D §1204 taxonomy", n_sheets)


#: name -> (tier, callable).  Order is report order.
CHECKS = {
    "scope_form": check_scope_form,
    "survey_data": check_survey_reports,
    "utility_evidence": check_utility_shots,
    "geotech": check_geotech,
    "sfn_folders": check_sfn_folders,
    "sts": check_sts,
    "load_rating": check_load_rating,
    "review_rounds": check_review_rounds,
    "as_advertised": check_contracts,
    "sheet_naming": check_sheet_naming,
}


# -- helpers -------------------------------------------------------------------

def review_rounds(project):
    """Group the 950-Reviews walk into review rounds.

    A round is one ``(types, stage, dated)`` bucket of documents with the
    role split out::

        {"types": ("sts",), "stage": "2", "dated": "2023-08-02",
         "resubmittal": False, "submissions": [...], "comments": [...],
         "dispositions": [...], "other": [...]}
    """
    buckets = {}
    for rec in project.query(series="reviews"):
        rp = rec.get("review_path") or {}
        key = (tuple(rp.get("types") or ()), rp.get("stage"),
               rp.get("dated"))
        b = buckets.setdefault(key, {
            "types": key[0], "stage": key[1], "dated": key[2],
            "resubmittal": bool(rp.get("resubmittal")),
            "submissions": [], "comments": [], "dispositions": [],
            "other": []})
        roles = set(rp.get("roles") or [])
        kind = (rec.get("review_file") or {}).get("kind")
        if "disposition" in roles or kind == "disposition":
            b["dispositions"].append(rec)
        elif "comments" in roles or kind in ("comments", "markups"):
            b["comments"].append(rec)
        elif "submission" in roles or kind in ("plan_set", "report"):
            b["submissions"].append(rec)
        else:
            b["other"].append(rec)
        b["resubmittal"] = b["resubmittal"] or bool(rp.get("resubmittal"))
    return sorted(buckets.values(),
                  key=lambda b: (b["stage"] or "", b["dated"] or ""))


def comments_addressed(project):
    """Per-round answer to 'were the review comments addressed':
    ``[(round_label, True/False/None)]`` — None when the round has no
    comments to address."""
    out = []
    for r in review_rounds(project):
        if not r["comments"]:
            out.append((_round_label(r), None))
        else:
            out.append((_round_label(r), bool(r["dispositions"])))
    return out


def _round_label(r):
    bits = ["/".join(r["types"]) or "review"]
    if r["stage"]:
        bits.append(f"stage {r['stage']}")
    if r["dated"]:
        bits.append(r["dated"])
    return " ".join(bits)


def sheet_naming_conformance(project):
    """``(ratio, n)`` of documents inside Sheets/Basemaps CADD buckets
    whose filenames parse against the L&D §1204 taxonomy."""
    docs = [d for d in project.walk()
            if d["tree"]["bucket"] in ("sheets", "basemaps")
            and (d.get("filename") or "").lower().endswith(
                (".dgn", ".dwg", ".pdf"))]
    if not docs:
        return 0.0, 0
    good = sum(1 for d in docs if d["sheet"])
    return good / len(docs), len(docs)


# -- entry points --------------------------------------------------------------

def run_checks(project, stage=None, checks=None):
    """Run the registry (or a subset by name) against one project."""
    names = checks or list(CHECKS)
    findings = []
    for name in names:
        try:
            findings.append(CHECKS[name](project, stage=stage))
        except Exception as err:                     # a check must not kill the run
            findings.append(_finding(name, "absence", "error",
                                     f"{type(err).__name__}: {err}"))
    return findings


def summarize(findings):
    """Status counts plus the list of non-ok checks."""
    counts = {}
    for f in findings:
        counts[f["status"]] = counts.get(f["status"], 0) + 1
    return {"counts": counts,
            "flags": [f for f in findings
                      if f["status"] in ("missing", "attention", "error")]}
