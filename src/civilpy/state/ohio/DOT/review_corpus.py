# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Phase-0 harvest: assemble the review corpus from ProjectWise projects.

The "what went wrong" graph starts here: one row per classified review
document across every findable project, joined to the CO review log, with
comment-resolution tables parsed into individual comment rows where the
file content is reachable.

Works in two modes through the same call:

* **offline** (snapshots) — document metadata + classifications only;
  produces the ``documents`` table and leaves ``comments`` empty except
  for provenance stubs of the resolution files it *would* pull;
* **on-box** (live client) — pass ``fetch=`` (a
  ``(folder_id, doc_id, dest_dir) -> path`` callable, e.g.
  ``pw.copy_out``) and every comment-resolution workbook is pulled and
  parsed into the ``comments`` table.

::

    from civilpy.state.ohio.DOT.review_corpus import build_review_corpus

    corpus = build_review_corpus(projects.values(), review_log=log_df)
    corpus.documents            # one row per review document
    corpus.comments             # one row per comment (needs fetch= or
                                # previously pulled files via local_dir=)
    corpus.save("review_corpus")    # parquet (falls back to csv)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from civilpy.state.ohio.DOT.comment_resolution import (
    is_resolution_filename,
    parse_comment_resolution,
)

__all__ = ["ReviewCorpus", "build_review_corpus", "document_rows"]


@dataclass
class ReviewCorpus:
    """The Phase-0 corpus: review documents, parsed comments, and the
    review-log join."""
    documents: pd.DataFrame
    comments: pd.DataFrame
    log_matches: pd.DataFrame = field(default_factory=pd.DataFrame)

    def save(self, stem):
        """Write ``<stem>_documents`` / ``_comments`` / ``_log`` as
        parquet, falling back to csv when no parquet engine is
        installed.  Returns the written paths."""
        written = []
        for name, df in (("documents", self.documents),
                         ("comments", self.comments),
                         ("log", self.log_matches)):
            if df is None or df.empty:
                continue
            base = Path(f"{stem}_{name}")
            try:
                path = base.with_suffix(".parquet")
                df.to_parquet(path)
            except Exception:
                path = base.with_suffix(".csv")
                df.to_csv(path, index=False)
            written.append(path)
        return written


def document_rows(project):
    """One flat dict per review document of one project (the
    ``documents`` table shape)."""
    rows = []
    for rec in project.query(series="reviews"):
        rp = rec.get("review_path") or {}
        rf = rec.get("review_file") or {}
        rows.append({
            "pid": project.pid,
            "doc_id": rec.get("doc_id"),
            "folder_id": rec.get("folder_id"),
            "filename": rec.get("filename"),
            "size": rec.get("size"),
            "path": "/".join(rec.get("segments") or []),
            "review_types": ";".join(rp.get("types") or []),
            "stage": rp.get("stage") or rf.get("stage"),
            "roles": ";".join(rp.get("roles") or []),
            "dated": rp.get("dated"),
            "resubmittal": bool(rp.get("resubmittal")),
            "kind": rf.get("kind"),
            "sfn": rf.get("sfn") or rec["tree"].get("sfn"),
            "is_resolution": is_resolution_filename(rec.get("filename")),
        })
    return rows


def _match_log(documents, review_log):
    """Review-log coverage: one row per log review of the harvested PIDs
    with the count of matching harvested documents.

    Matching is PID + stage (a stage-less log row or document matches any
    stage); date-level pairing is left to analysis because submittal
    folder dates and log ``date_in`` routinely differ by days.
    """
    log = review_log.copy()
    log["pid"] = pd.to_numeric(log["pid"], errors="coerce").astype("Int64")
    log["_stage"] = log["stage"].astype(str).str.extract(r"([123])")[0] \
        if "stage" in log else None
    docs = documents.copy()
    docs["pid"] = pd.to_numeric(docs["pid"], errors="coerce").astype("Int64")
    log = log[log.pid.isin(set(docs.pid.dropna()))]
    n_docs, n_res = [], []
    for _, row in log.iterrows():
        mine = docs[docs.pid == row.pid]
        if row.get("_stage") and pd.notna(row["_stage"]):
            mine = mine[mine.stage.isna()
                        | (mine.stage.astype(str) == row["_stage"])]
        n_docs.append(len(mine))
        n_res.append(int(mine.is_resolution.sum()))
    log = log.drop(columns=["_stage"], errors="ignore")
    log["n_harvested_docs"] = n_docs
    log["n_resolution_files"] = n_res
    return log


def build_review_corpus(projects, review_log=None, fetch=None,
                        local_dir=None, max_pulls=None):
    """Assemble the corpus from an iterable of
    :class:`~civilpy.state.ohio.DOT.pw_project.ProjectWiseProject`
    (live or snapshot-backed).

    ``fetch``
        optional ``(folder_id, doc_id, dest_dir) -> local path`` used to
        pull comment-resolution workbooks (live client's ``copy_out``).
    ``local_dir``
        directory to pull into, and/or where previously pulled files
        already sit (matched by filename) — lets an offline run parse
        workbooks a previous on-box run downloaded.
    ``max_pulls``
        cap on downloads for a budgeted sitting.
    """
    doc_rows, comment_rows = [], []
    local_dir = Path(local_dir) if local_dir else None
    pulls = 0
    for project in projects:
        rows = document_rows(project)
        doc_rows.extend(rows)
        for row in rows:
            if not row["is_resolution"]:
                continue
            source = None
            if local_dir:
                candidate = local_dir / row["filename"]
                if candidate.exists():
                    source = candidate
            if source is None and fetch is not None and local_dir is not None:
                if max_pulls is not None and pulls >= max_pulls:
                    continue
                try:
                    source = fetch(row["folder_id"], row["doc_id"],
                                   local_dir)
                    pulls += 1
                except Exception as err:
                    comment_rows.append({
                        "pid": row["pid"], "source_file": row["filename"],
                        "error": f"{type(err).__name__}: {err}"})
                    continue
            if source is None:
                continue
            try:
                for c in parse_comment_resolution(source,
                                                  filename=row["filename"]):
                    comment_rows.append(dict(c, pid=row["pid"],
                                             stage=row["stage"],
                                             review_types=row["review_types"],
                                             dated=row["dated"]))
            except Exception as err:
                comment_rows.append({
                    "pid": row["pid"], "source_file": row["filename"],
                    "error": f"{type(err).__name__}: {err}"})
    documents = pd.DataFrame(doc_rows)
    comments = pd.DataFrame(comment_rows)
    log_matches = pd.DataFrame()
    if review_log is not None and not documents.empty:
        log_matches = _match_log(documents, review_log)
    return ReviewCorpus(documents=documents, comments=comments,
                        log_matches=log_matches)
