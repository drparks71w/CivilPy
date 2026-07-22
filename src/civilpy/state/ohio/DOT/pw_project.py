# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Lazy object model of an ODOT ProjectWise design project.

``ProjectWiseProject`` wraps one project (by PID) on the active datasource
and exposes its folder tree and the standard L&D Volume 3 deliverables as
attributes, resolving everything lazily — nothing touches ProjectWise until
an attribute actually needs it, and every folder/document listing is cached
for the life of the object.

::

    from civilpy import ProjectWiseProject

    project = ProjectWiseProject("112665", district="06", county="Franklin")
    project.sts               # Structure Type Study documents
    project.stage_2_plans     # Stage 2 detail-design documents
    project.sfns              # [ProjectWiseSFN, ...] from Structures/SFN_*
    project.sfns[0].load_rating   # that bridge's load-rating files
    project.survey()          # full folder-tree dump (recon / cache refresh)
    project.close()           # or use it as a context manager

Deliverable lookup is registry-driven (:data:`DELIVERABLES`): each name maps
to folder-name patterns searched breadth-first through the project tree.
The registry is seeded from the L&D Vol. 3 deliverable list and the folder
names verified on-box so far; extend or override per-instance via
``ProjectWiseProject(..., deliverables={...})``.  Compliance-review helpers
(BDM / L&D Vol. 1-2 / AASHTO checklists) should build on these accessors
rather than raw folder walks.

Requires Windows + a logged-in ProjectWise Explorer for live access; the
module itself imports anywhere (handy for testing and for building against
cached ``survey()`` output).
"""
from __future__ import annotations

import re

from civilpy.state.ohio.DOT.projectwise import (
    ACTIVE_PROJECT_PATH,
    ACTIVE_SHEET_GRAMMAR,
    DATASOURCE_ACTIVE,
)
from civilpy.state.ohio.DOT.sheet_taxonomy import (
    SHEET_ACCESSORS,
    classify_filename,
)

#: L&D Vol. 3 deliverables -> folder-name patterns (case-insensitive regex,
#: matched against folder names breadth-first through the project tree).
#: Names marked (verified) were confirmed on the live datasource (2026-07
#: Probe F tree surveys of pw-02); the rest are seeded from the manual's
#: deliverable list pending recon.  Verified skeleton: every active project
#: carries the numbered template (000-Admin/010-ProjAdmin, 100-Planning,
#: 200-Environmental, 300-Survey, 400-Engineering/<discipline>/{Basemaps,
#: EngData,Sheets}, 500-RealEstate, 600-Contracts, 800-Construction,
#: 950-Reviews).  Review submittals live under 950-Reviews as
#: ``<type>/<bridge>/<YYYYMMDD (Re)Submittal>/Submittal`` and staged
#: deliverable packages under 950-Reviews/Stage N/01-Submission/
#: ``YYYYMMDD_StageN_Submittal/{Stage N Plans, Structure Design Reports,
#: Bridge Load Rating Files, Bridge Stage N Checklists, Cost Estimate}``
#: (mirrored in 010-ProjAdmin/Correspondence/Deliverables).
DELIVERABLES = {
    "sts": [r"structure\s*type\s*stud", r"\bSTS\b"],    # (verified: "Structure Type Studies")
    "preliminary_plans": [r"preliminary", r"stage\s*1"],
    "stage_1_plans": [r"stage\s*_?1"],                  # (verified: "Stage 1 Plans", "Stage1_Submittal")
    "stage_2_plans": [r"stage\s*_?2"],                  # (verified: "Stage 2 Plans", "Stage2_Submittal")
    "stage_3_plans": [r"stage\s*_?3"],                  # (verified: "Stage3Railroad_Submittal")
    "final_tracings": [r"final\s*tracing", r"signed.*plans?"],
    "structures": [r"^structures$"],                    # (verified: 400-Engineering/Structures)
    "load_rating": [r"load\s*rating"],                  # (verified: "Bridge Load Rating Files")
    "reviews": [r"^950-Reviews$"],                      # (verified: review-submittal home)
    "design_reports": [r"structure\s*design\s*report"], # (verified: "Structure Design Reports")
    "aer": [r"\bAERs?\b", r"alternative\s*evaluation"], # (verified: "950-Reviews/AERs")
    "foundation": [r"foundation", r"geotech", r"soil"],
    "hydraulics": [r"hydraul", r"scour", r"h\s*&\s*h"],
    "estimates": [r"estimate"],
    "correspondence": [r"correspondence", r"comments", r"review"],
}


class PWFolder:
    """One ProjectWise folder, with lazy, cached children and documents."""

    def __init__(self, client, folder_id, name="", path=""):
        self._client = client
        self.id = folder_id
        self.name = name
        self.path = path
        self._children = None
        self._documents = None

    @property
    def children(self):
        if self._children is None:
            self._children = [
                PWFolder(self._client, fid, n, f"{self.path}/{n}")
                for n, fid in self._client.list_children(self.id)]
        return self._children

    @property
    def documents(self):
        if self._documents is None:
            self._documents = self._client.list_documents(self.id)
        return self._documents

    def __getitem__(self, name):
        for child in self.children:
            if (child.name or "").lower() == name.lower():
                return child
        raise KeyError(f"{name!r} not under {self.path or self.name!r}")

    def find_folders(self, patterns, max_depth=4, budget=500):
        """Breadth-first search for folders whose name matches any pattern."""
        pats = [re.compile(p, re.IGNORECASE) for p in patterns]
        hits, frontier = [], [(self, 0)]
        while frontier and budget > 0:
            node, depth = frontier.pop(0)
            budget -= 1
            for child in node.children:
                if any(p.search(child.name or "") for p in pats):
                    hits.append(child)
                elif depth + 1 < max_depth:
                    frontier.append((child, depth + 1))
        return hits

    def all_documents(self, max_depth=2):
        """Documents in this folder and ``max_depth`` levels of subfolders."""
        docs, stack = [], [(self, 0)]
        while stack:
            node, depth = stack.pop()
            for d in node.documents:
                docs.append(dict(d, folder=node.path or node.name))
            if depth + 1 <= max_depth:
                stack.extend((c, depth + 1) for c in node.children)
        return docs

    def tree(self, max_depth=6, budget=2000, _depth=0):
        """Nested dict of the folder structure with document counts and a
        few sample filenames per folder — the recon format Probe F uses."""
        node = {"name": self.name, "id": self.id,
                "n_docs": len(self.documents),
                "sample": [d.get("filename") for d in self.documents[:3]]}
        if _depth < max_depth and budget > 0:
            kids = []
            for child in self.children:
                budget -= 1
                if budget <= 0:
                    break
                kids.append(child.tree(max_depth, budget, _depth + 1))
            if kids:
                node["children"] = kids
        return node


class ProjectWiseSFN:
    """One bridge (``SFN_*`` folder) within a project's Structures folder."""

    def __init__(self, project, folder):
        self.project = project
        self.folder = folder
        m = re.search(r"SFN[_ ]?(\d{7})", folder.name or "", re.IGNORECASE)
        self.sfn = m.group(1) if m else None
        self.bridge_key = None      # CTY-ROUTE-SLM, from the folder description

    @property
    def sheets(self):
        """This bridge's sheets, with pid/sfn/sheet parsed from filenames."""
        out = []
        for d in self.folder.all_documents():
            m = ACTIVE_SHEET_GRAMMAR.search(d.get("filename") or "")
            out.append(dict(d, pid=m and m["pid"], sfn=m and m["sfn"],
                            sheet=m and m["sheet"]))
        return out

    @property
    def load_rating(self):
        """Load-rating documents for this bridge: the project's load-rating
        deliverable filtered to this SFN by filename."""
        docs = self.project.deliverable("load_rating")
        if self.sfn:
            mine = [d for d in docs if self.sfn in (d.get("filename") or "")]
            return mine or docs
        return docs

    def sheet_set(self, name):
        """This bridge's documents for a named structure-scope sheet type
        (see ``sheet_taxonomy.SHEET_ACCESSORS``): the project-wide sheets of
        that code, filtered to this SFN by the naming convention."""
        spec = SHEET_ACCESSORS.get(name)
        if spec is None or spec["scope"] != "structure":
            raise KeyError(f"{name!r} is not a structure-scope sheet set")
        return [d for d in self.project.sheet_set(name)
                if (c := classify_filename(d.get("filename")))
                and c.get("sfn") == self.sfn]

    def __getattr__(self, name):
        if not name.startswith("_"):
            spec = SHEET_ACCESSORS.get(name)
            if spec is not None and spec["scope"] == "structure":
                return self.sheet_set(name)
        raise AttributeError(name)

    def pull(self, dest_dir):
        """Copy every sheet in this bridge's folder to ``dest_dir``."""
        return [self.project._client.copy_out(d["folder_id"], d["doc_id"],
                                              dest_dir)
                for d in self.folder.all_documents()]

    def __repr__(self):
        return f"<ProjectWiseSFN {self.sfn or self.folder.name}>"


class ProjectWiseProject:
    """Lazy handle on one active ProjectWise project, by PID."""

    def __init__(self, pid, district=None, county=None, path=None,
                 datasource=DATASOURCE_ACTIVE, deliverables=None,
                 client=None):
        self.pid = str(pid)
        self.district = district and str(district).zfill(2)
        self.county = county
        self.datasource = datasource
        self.deliverables = dict(DELIVERABLES, **(deliverables or {}))
        self._path = path
        self._client = client          # injectable for tests / cached replay
        self._session = None
        self._root = None
        self._deliverable_cache = {}

    # -- session -------------------------------------------------------------
    def _ensure_client(self):
        if self._client is None:
            from civilpy.general.bentley import projectwise as pw
            if self._session is None:
                self._session = pw.PW_SESSION(self.datasource)
                self._session.__enter__()
                pw.extend_prototypes()
            self._client = pw
        return self._client

    def close(self):
        if self._session is not None:
            self._session.__exit__(None, None, None)
            self._session = None
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- resolution ----------------------------------------------------------
    @property
    def project_path(self):
        if self._path:
            return self._path
        if not (self.district and self.county):
            raise LookupError(
                f"PID {self.pid}: pass district= and county= (or path=) to "
                "resolve the project folder — or supply a cached survey")
        return ACTIVE_PROJECT_PATH.format(
            district=self.district, county=self.county, pid=self.pid)

    @property
    def root(self):
        """The project's top folder (deliverables search from here)."""
        if self._root is None:
            client = self._ensure_client()
            path = self.project_path
            fid = client.resolve_path(path)
            if not fid:
                raise LookupError(f"could not resolve {path!r} "
                                  f"on {self.datasource}")
            self._root = PWFolder(client, fid, self.pid, path)
        return self._root

    @property
    def structures(self):
        """The ``400-Engineering/Structures`` folder (falls back to a
        breadth-first name search if the canonical path shifts)."""
        try:
            return self.root["400-Engineering"]["Structures"]
        except KeyError:
            hits = self.root.find_folders([r"structures"], max_depth=3)
            if hits:
                return hits[0]
            raise LookupError(
                f"no Structures folder under {self.project_path!r}")

    # -- sheets (L&D Vol. 3 file-code taxonomy) --------------------------------
    def documents(self, max_depth=6, budget=1500, refresh=False):
        """Every document in the project tree (budgeted walk, cached).

        Each dict gains a ``sheet`` key with :func:`classify_filename`'s
        parse (or ``None`` for non-conforming names).
        """
        if refresh or getattr(self, "_all_docs", None) is None:
            docs, stack = [], [(self.root, 0)]
            remaining = budget
            while stack and remaining > 0:
                node, depth = stack.pop()
                remaining -= 1
                for d in node.documents:
                    docs.append(dict(d, folder=node.path or node.name,
                                     sheet=classify_filename(d.get("filename"))))
                if depth + 1 <= max_depth:
                    stack.extend((c, depth + 1) for c in node.children)
            self._all_docs = docs
        return self._all_docs

    def sheet_set(self, name):
        """Documents for a named sheet type (``sheet_taxonomy
        .SHEET_ACCESSORS``), matched by the L&D filename code anywhere in
        the project tree."""
        spec = SHEET_ACCESSORS.get(name)
        if spec is None:
            raise KeyError(f"unknown sheet set {name!r}; known: "
                           f"{sorted(SHEET_ACCESSORS)}")
        codes = set(spec["codes"])
        return [d for d in self.documents()
                if d["sheet"] and d["sheet"]["code"] in codes]

    # -- deliverables ----------------------------------------------------------
    def deliverable(self, name):
        """Documents for a named deliverable (see :data:`DELIVERABLES`)."""
        if name not in self.deliverables:
            raise KeyError(f"unknown deliverable {name!r}; known: "
                           f"{sorted(self.deliverables)}")
        if name not in self._deliverable_cache:
            docs = []
            for folder in self.root.find_folders(self.deliverables[name]):
                docs.extend(folder.all_documents())
            self._deliverable_cache[name] = docs
        return self._deliverable_cache[name]

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            registry = object.__getattribute__(self, "deliverables")
        except AttributeError:
            raise AttributeError(name)
        if name in registry:
            return self.deliverable(name)
        spec = SHEET_ACCESSORS.get(name)
        if spec is not None:
            # structure-scope sets are meaningful per-SFN, but on the project
            # they return the union across all its structures
            return self.sheet_set(name)
        raise AttributeError(name)

    @property
    def sfns(self):
        """The project's bridges, one per ``SFN_*`` folder under Structures."""
        return [ProjectWiseSFN(self, f) for f in self.structures.children
                if re.match(r"SFN[_ ]?\d", f.name or "", re.IGNORECASE)]

    def sfn(self, number):
        """The :class:`ProjectWiseSFN` for one structure file number."""
        number = str(number)
        for s in self.sfns:
            if s.sfn == number:
                return s
        raise KeyError(f"SFN {number} not in project {self.pid}")

    # -- recon / caching -------------------------------------------------------
    def survey(self, max_depth=6):
        """Full folder-tree dump (names, ids, doc counts, sample filenames).

        Run this on-box and commit the JSON — it is both the recon that
        refines :data:`DELIVERABLES` and a cache other tooling can navigate
        without a live ProjectWise session.
        """
        return {"pid": self.pid, "datasource": self.datasource,
                "path": self.project_path,
                "tree": self.root.tree(max_depth=max_depth)}

    def __repr__(self):
        return f"<ProjectWiseProject PID {self.pid}>"
