# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""MCP server for the ODOT ProjectWise navigator.

Exposes the full-tree project model — classified document queries,
``pw://`` branch resources, tier-2 completion checks, review-round
summaries — so an assistant can ask "the geotech report", "the Stage 2
comments", "is this project missing anything for Stage 3?" without any
path knowledge.  Addresses are the classified ``pw://`` scheme from
:mod:`~civilpy.state.ohio.DOT.pw_project`, so folder renames and
consultant-parallel folders never change an answer.

Backends
--------
* :class:`SnapshotStore` — the committed crawler recon JSONs
  (``district_file_samples.json``, ``closed_tree_samples.json``).  Works
  on any machine; document *content* is not available.
* :class:`LiveStore` — the live datasource through the ProjectWise SDK
  (Windows + logged-in ProjectWise Explorer).  Projects resolve through
  an explicit ``{pid: path}`` map (e.g. built from the crawler's
  ``pw_folder_index.json``) or the canonical active-projects template.

Running
-------
``pip install civilpy[mcp]`` then::

    civilpy-pw-mcp                     # snapshot mode
    CIVILPY_PW_SNAPSHOT=/path/to/crawler_output civilpy-pw-mcp

The core functions (:func:`list_projects` ... :func:`project_checklist`)
are plain Python over a store — usable and testable without the ``mcp``
package installed; only :func:`build_server`/:func:`main` require it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from civilpy.state.ohio.DOT.pw_project import (
    ProjectWiseProject,
    parse_resource,
    resource_uri,
)
from civilpy.state.ohio.DOT.review_checks import (
    comments_addressed,
    run_checks,
    summarize,
)

__all__ = ["SnapshotStore", "LiveStore", "list_projects", "describe_project",
           "query_documents", "project_checklist", "review_summary",
           "build_server", "main"]


class SnapshotStore:
    """Projects from the committed recon JSONs (see
    :mod:`~civilpy.state.ohio.DOT.pw_snapshot`)."""

    def __init__(self, snapshot_dir, datasource=None):
        from civilpy.state.ohio.DOT.pw_snapshot import (
            load_closed_samples, load_file_samples)
        self.dir = Path(snapshot_dir)
        self.datasource = datasource
        self.projects = {}
        samples = self.dir / "district_file_samples.json"
        closed = self.dir / "closed_tree_samples.json"
        if samples.exists():
            self.projects.update(load_file_samples(samples))
        if closed.exists():
            self.projects.update(load_closed_samples(closed))
        if not self.projects:
            raise FileNotFoundError(
                f"no snapshot JSONs under {self.dir} (expected "
                "district_file_samples.json / closed_tree_samples.json)")

    def pids(self):
        return sorted(self.projects)

    def get(self, pid):
        try:
            project = self.projects[str(pid)]
        except KeyError:
            raise KeyError(f"PID {pid} not in snapshot "
                           f"({len(self.projects)} projects)") from None
        if self.datasource and not project.datasource:
            project.datasource = self.datasource
        return project


class LiveStore:
    """Projects resolved on the live datasource.

    ``path_map`` is ``{pid: full folder path}`` — build it from the
    crawler's ``pw_folder_index.json`` / ``co_pw_availability.csv`` so
    closed/sold/additional-root projects resolve too.  Without a map
    entry the store falls back to the active-projects template, which
    needs ``district`` and ``county`` kwargs on :meth:`get`.
    """

    def __init__(self, path_map=None, datasource=None):
        self.path_map = {str(k): v for k, v in (path_map or {}).items()}
        self.datasource = datasource
        self._cache = {}

    @classmethod
    def from_availability(cls, availability_csv):
        import pandas as pd
        df = pd.read_csv(availability_csv)
        found = df[df["found"] & df["path"].notna()]
        return cls({str(int(r.pid)): r.path for r in found.itertuples()})

    def pids(self):
        return sorted(self.path_map)

    def get(self, pid, district=None, county=None):
        pid = str(pid)
        if pid not in self._cache:
            self._cache[pid] = ProjectWiseProject(
                pid, district=district, county=county,
                path=self.path_map.get(pid), datasource=self.datasource)
        return self._cache[pid]


# -- core API (no mcp dependency) ----------------------------------------------

def list_projects(store):
    """The PIDs the store can serve."""
    return store.pids()


def describe_project(store, pid):
    """Branch map of one project: the ``pw://`` resources under it with
    document counts."""
    project = store.get(pid)
    branches = []
    for (series, discipline, sfn), n in sorted(
            project.branches().items(), key=lambda kv: str(kv[0])):
        if series is None:
            continue
        branches.append({
            "resource": resource_uri(pid, series, discipline, sfn),
            "series": series, "discipline": discipline, "sfn": sfn,
            "n_docs": n})
    return {"pid": str(pid), "path": project.project_path,
            "n_documents": len(project.walk()), "branches": branches}


def query_documents(store, resource=None, pid=None, series=None,
                    discipline=None, sfn=None, kind=None, stage=None,
                    pattern=None, limit=200):
    """Classified document query — by ``pw://`` resource or by filters."""
    kwargs = {}
    if resource:
        pid, kwargs = parse_resource(resource)
    if pid is None:
        raise ValueError("pass resource='pw://...' or pid=")
    for key, val in (("series", series), ("discipline", discipline),
                     ("sfn", sfn), ("kind", kind), ("stage", stage),
                     ("pattern", pattern)):
        if val is not None:
            kwargs[key] = val
    project = store.get(pid)
    hits = project.query(**kwargs)
    return [{"filename": d.get("filename"),
             "path": "/".join(d.get("segments") or []),
             "link": project.pw_url(d),
             "doc_id": d.get("doc_id"), "folder_id": d.get("folder_id"),
             "series": d["tree"]["series"],
             "discipline": d["tree"]["discipline"],
             "sfn": d["tree"]["sfn"],
             "kind": (d.get("review_file") or {}).get("kind"),
             "stage": (d.get("review_path") or {}).get("stage"),
             "sheet_code": d["sheet"] and d["sheet"].get("code")}
            for d in hits[:limit]]


def project_checklist(store, pid, stage=None):
    """Tier-2 completion/absence findings for one project.  With a
    ``stage`` (``"sts"``, 1, 2, 3) the stage's submittal-package
    deliverables (from the ODOT review checklists) are appended."""
    from civilpy.state.ohio.DOT.review_checks import (
        STAGE_DELIVERABLES, check_stage_deliverables)
    project = store.get(pid)
    numeric = stage if isinstance(stage, int) else None
    findings = run_checks(project, stage=numeric)
    if stage in STAGE_DELIVERABLES:
        findings += check_stage_deliverables(project, stage)
    return {"pid": str(pid), "stage": stage, "findings": findings,
            "summary": summarize(findings)["counts"]}


def review_summary(store, pid):
    """Review rounds and whether each round's comments were addressed."""
    project = store.get(pid)
    return {"pid": str(pid),
            "rounds": [{"round": label, "comments_addressed": status}
                       for label, status in comments_addressed(project)]}


# -- MCP wiring ----------------------------------------------------------------

def build_server(store):
    """A FastMCP server over ``store`` (requires ``pip install
    civilpy[mcp]``)."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        "civilpy-projectwise",
        instructions=(
            "ODOT ProjectWise navigator. Addresses are pw://{pid}/"
            "{series}/{discipline}/{sfn}: series is one of admin/planning/"
            "environmental/survey/engineering/real_estate/contracts/"
            "construction/reviews/workset_standards/scratch. Start with "
            "pw_projects, then pw_describe for a project's branches."))

    @mcp.tool()
    def pw_projects() -> list:
        """List the PIDs this server can navigate."""
        return list_projects(store)

    @mcp.tool()
    def pw_describe(pid: str) -> dict:
        """A project's branch map: every pw:// resource with doc counts."""
        return describe_project(store, pid)

    @mcp.tool()
    def pw_documents(resource: str = "", pid: str = "", series: str = "",
                     discipline: str = "", sfn: str = "", kind: str = "",
                     stage: str = "", pattern: str = "") -> list:
        """Query documents by pw:// resource and/or filters (kind is a
        review-file kind: comments, markups, disposition, report,
        plan_set, load_rating...; pattern is a filename regex)."""
        return query_documents(
            store, resource=resource or None, pid=pid or None,
            series=series or None, discipline=discipline or None,
            sfn=sfn or None, kind=kind or None, stage=stage or None,
            pattern=pattern or None)

    @mcp.tool()
    def pw_checklist(pid: str, stage: int = 0) -> dict:
        """Tier-2 completion checks (scope form, survey, geotech, SFN
        folders, STS, load rating, review dispositions, ...)."""
        return project_checklist(store, pid, stage=stage or None)

    @mcp.tool()
    def pw_review_summary(pid: str) -> dict:
        """Review rounds and whether each round's comments have
        dispositions."""
        return review_summary(store, pid)

    @mcp.resource("pw://{pid}")
    def project_resource(pid: str) -> str:
        return json.dumps(describe_project(store, pid), indent=1)

    @mcp.resource("pw://{pid}/{series}")
    def series_resource(pid: str, series: str) -> str:
        return json.dumps(query_documents(
            store, pid=pid, series=series), indent=1)

    @mcp.resource("pw://{pid}/engineering/{discipline}/{sfn}")
    def sfn_resource(pid: str, discipline: str, sfn: str) -> str:
        return json.dumps(query_documents(
            store, pid=pid, series="engineering", discipline=discipline,
            sfn=sfn), indent=1)

    return mcp


def main():
    """Console entry point (``civilpy-pw-mcp``).

    ``CIVILPY_PW_SNAPSHOT`` selects snapshot mode (a directory holding
    the crawler JSONs); ``CIVILPY_PW_PATHS`` (a json ``{pid: path}``
    file) selects live mode with that path map.
    """
    snapshot = os.environ.get("CIVILPY_PW_SNAPSHOT")
    paths_file = os.environ.get("CIVILPY_PW_PATHS")
    if snapshot:
        store = SnapshotStore(snapshot)
    elif paths_file:
        store = LiveStore(json.loads(Path(paths_file).read_text()))
    else:
        store = SnapshotStore(Path.cwd())
    build_server(store).run()


if __name__ == "__main__":   # pragma: no cover
    main()
