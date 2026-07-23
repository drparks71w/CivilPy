# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Offline ProjectWise backend built from captured folder trees.

Live ProjectWise access needs Windows plus a logged-in ProjectWise
Explorer, but everything above the wire protocol —
:class:`~civilpy.state.ohio.DOT.pw_project.ProjectWiseProject`, the
taxonomies, the completion checks, the MCP server — only needs a client
that can answer ``resolve_path`` / ``list_children`` / ``list_documents``.
:class:`SnapshotClient` is that client, fed by the recon JSON the crawler
notebooks capture on-box:

* ``district_file_samples.json`` records — full project trees with folder
  ids and filenames (loader: :func:`load_file_samples`),
* ``closed_tree_samples.json`` records — nested ``{"folders", "files"}``
  dicts without per-folder ids (loader: :func:`load_closed_samples`),
* ``ProjectWiseProject.survey()`` dumps (loader:
  :meth:`SnapshotClient.from_survey`).

So the same analysis code runs on-box against the live datasource and
anywhere else against the committed snapshots::

    projects = load_file_samples("crawler_output/district_file_samples.json")
    project = projects["115840"]              # a ProjectWiseProject
    project.query(series="survey")            # walks the snapshot

Snapshots are read-only: ``copy_out`` raises :class:`SnapshotOffline`.
Folders that were captured without ids get synthetic negative ids —
stable within one client, never valid on the live datasource.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

__all__ = ["SnapshotOffline", "SnapshotClient",
           "load_file_samples", "load_closed_samples"]

PID_IN_MATCH = re.compile(r"PID[\s_]*(\d{5,7})", re.IGNORECASE)


class SnapshotOffline(RuntimeError):
    """Raised when an operation needs the live datasource (e.g. pulling
    document content) but the client is a snapshot."""


class SnapshotClient:
    """Duck-typed stand-in for :mod:`civilpy.general.bentley.projectwise`
    answering from a captured tree.

    Build one with a constructor classmethod (:meth:`from_recon`,
    :meth:`from_closed`, :meth:`from_survey`) rather than directly.
    Multiple projects can share one client via :meth:`add_tree`.
    """

    def __init__(self):
        self._children = {}      # folder_id -> [(name, id), ...]
        self._docs = {}          # folder_id -> [doc dict, ...]
        self._paths = {}         # normalized path -> folder_id
        self._names = {}         # folder_id -> name
        self._next_synthetic = -2

    # -- construction ---------------------------------------------------------
    def _new_id(self, wanted=None):
        if wanted is not None:
            return wanted
        fid = self._next_synthetic
        self._next_synthetic -= 1
        return fid

    def _register(self, path, fid, name):
        self._paths[path.lower()] = fid
        self._names[fid] = name
        self._children.setdefault(fid, [])
        self._docs.setdefault(fid, [])

    def _add_document(self, fid, filename):
        seq = len(self._docs[fid]) + 1        # doc_id is per-folder (live too)
        self._docs[fid].append({
            "doc_id": seq, "name": filename, "filename": filename,
            "desc": "", "size": None, "created": "", "updated": "",
            "folder_id": fid})

    def add_tree(self, path, tree):
        """Attach one captured project tree at ``path``.

        ``tree`` may be either recon shape
        (``{"name", "id", "files": [...], "children": [...]}``) or the
        closed-sample shape (``{"folders": {name: node}, "files": [...]}``).
        Returns the root folder id.
        """
        root_id = self._new_id(tree.get("id"))
        name = tree.get("name") or path.rsplit("\\", 1)[-1]
        self._register(path, root_id, name)
        self._fill(root_id, path, tree)
        return root_id

    def _fill(self, fid, path, node):
        for filename in node.get("files") or []:
            self._add_document(fid, filename)
        kids = node.get("children")
        if kids is None:
            folders = node.get("folders") or {}
            kids = [dict(sub if isinstance(sub, dict) else {},
                         name=kid_name)
                    for kid_name, sub in folders.items()
                    if isinstance(sub, dict)]      # skip "..budget.." marks
        for kid in kids:
            kid_id = self._new_id(kid.get("id"))
            kid_path = f"{path}\\{kid['name']}"
            self._register(kid_path, kid_id, kid["name"])
            self._children[fid].append((kid["name"], kid_id))
            self._fill(kid_id, kid_path, kid)

    @classmethod
    def from_recon(cls, record):
        """Client + resolved path for one ``district_file_samples`` record.

        Returns ``(client, path, pid)``.  The PID comes from the project
        folder name when it is a bare PID, else from ``matched_because``.
        """
        client = cls()
        path = record["path"]
        tree = dict(record["tree"], id=record.get("folder_id",
                                                  record["tree"].get("id")))
        client.add_tree(path, tree)
        name = str(record.get("project_folder") or "")
        pid = name if name.isdigit() else None
        if pid is None:
            m = PID_IN_MATCH.search(str(record.get("matched_because") or ""))
            pid = m.group(1) if m else name
        return client, path, pid

    @classmethod
    def from_closed(cls, pid, record):
        """Client + path for one ``closed_tree_samples.json`` record."""
        client = cls()
        path = record["path"]
        tree = dict(record["tree"], id=record.get("folder_id"), name=str(pid))
        client.add_tree(path, tree)
        return client, path, str(pid)

    @classmethod
    def from_survey(cls, survey):
        """Client + path for one ``ProjectWiseProject.survey()`` dump.

        Only the sampled filenames are present in a survey, so document
        listings are partial — fine for structure checks, wrong for
        counting."""
        client = cls()
        tree = _survey_to_tree(survey["tree"])
        client.add_tree(survey["path"], tree)
        return client, survey["path"], str(survey["pid"])

    # -- the client protocol --------------------------------------------------
    def resolve_path(self, path):
        return self._paths.get((path or "").lower(), 0)

    def folder_path(self, folder_id):
        for path, fid in self._paths.items():
            if fid == folder_id:
                return path
        return None

    def list_children(self, folder_id):
        return list(self._children.get(folder_id, []))

    def list_children_info(self, folder_id):
        return [(n, i, "") for n, i in self._children.get(folder_id, [])]

    def list_documents(self, folder_id):
        return [dict(d) for d in self._docs.get(folder_id, [])]

    def copy_out(self, folder_id, doc_id, dest_dir):
        raise SnapshotOffline(
            "document content is not captured in a snapshot -- pull "
            "documents on-box against the live datasource")


def _survey_to_tree(node):
    return {"name": node.get("name"), "id": node.get("id"),
            "files": list(node.get("sample") or []),
            "children": [_survey_to_tree(c)
                         for c in node.get("children") or []]}


def _project_for(client, path, pid):
    from civilpy.state.ohio.DOT.pw_project import ProjectWiseProject
    return ProjectWiseProject(pid, path=path, client=client)


def load_file_samples(json_path):
    """``district_file_samples.json`` -> ``{pid: ProjectWiseProject}``.

    Every project gets its own :class:`SnapshotClient`, wired in through
    ``ProjectWiseProject(client=...)`` so the full object model (query,
    deliverables, SFNs, review documents, checks) works offline.
    """
    data = json.loads(Path(json_path).read_text())
    projects = {}
    for records in data.values():
        for record in records:
            client, path, pid = SnapshotClient.from_recon(record)
            projects[pid] = _project_for(client, path, pid)
    return projects


def load_closed_samples(json_path):
    """``closed_tree_samples.json`` -> ``{pid: ProjectWiseProject}``."""
    data = json.loads(Path(json_path).read_text())
    return {str(pid): _project_for(*SnapshotClient.from_closed(pid, rec))
            for pid, rec in data.items()}
