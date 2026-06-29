#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Truss extraction (Phase 3): turn a SIMP density field into a strut-and-tie
truss.

Pipeline: threshold the density to a binary load path, thin it to a one-pixel
skeleton (Zhang–Suen), walk the skeleton into a node/edge graph, force a node at
every support and load, simplify each traced path to straight members
(Douglas–Peucker), collapse near-coincident nodes, and emit a
:class:`~civilpy.structural.strut_and_tie.StrutAndTieModel` with the supports and
loads attached.  Pure NumPy — the thinning is hand-rolled so no ``scikit-image``
dependency is required.
"""

from __future__ import annotations

import string

import numpy as np

from civilpy.structural.strut_and_tie import StrutAndTieModel


# ── morphological thinning (Zhang–Suen) ───────────────────────────────────

def zhang_suen(binary: np.ndarray) -> np.ndarray:
    """Thin a binary image to a 1-pixel skeleton (Zhang–Suen 1984)."""
    img = binary.astype(np.uint8).copy()
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            P = np.pad(img, 1)
            p2 = P[:-2, 1:-1]; p3 = P[:-2, 2:]; p4 = P[1:-1, 2:]
            p5 = P[2:, 2:];    p6 = P[2:, 1:-1]; p7 = P[2:, :-2]
            p8 = P[1:-1, :-2]; p9 = P[:-2, :-2]
            neighbors = [p2, p3, p4, p5, p6, p7, p8, p9]
            B = sum(neighbors)
            seq = neighbors + [p2]
            A = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(int) for i in range(8))
            if step == 0:
                c1 = (p2 * p4 * p6 == 0)
                c2 = (p4 * p6 * p8 == 0)
            else:
                c1 = (p2 * p4 * p8 == 0)
                c2 = (p2 * p6 * p8 == 0)
            mark = (img == 1) & (B >= 2) & (B <= 6) & (A == 1) & c1 & c2
            if mark.any():
                img[mark] = 0
                changed = True
    return img.astype(bool)


# ── skeleton → graph ──────────────────────────────────────────────────────

_NEIGH = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]


def _neighbors(skel, r, c):
    out = []
    for dr, dc in _NEIGH:
        rr, cc = r + dr, c + dc
        if 0 <= rr < skel.shape[0] and 0 <= cc < skel.shape[1] and skel[rr, cc]:
            out.append((rr, cc))
    return out


def _trace_graph(skel, anchors):
    """Return ``(nodes, edges)``: nodes are skeleton pixels that are endpoints,
    junctions, or forced anchors; edges are pixel polylines between them."""
    deg = {}
    px = list(zip(*np.nonzero(skel)))
    for (r, c) in px:
        deg[(r, c)] = len(_neighbors(skel, r, c))
    nodeset = {p for p in px if deg[p] != 2}
    nodeset |= set(anchors)
    if not nodeset and px:
        nodeset = {px[0]}  # a clean loop — seed one node

    edges = []
    visited_edge = set()
    for start in nodeset:
        for nb in _neighbors(skel, *start):
            if (start, nb) in visited_edge:
                continue
            path = [start, nb]
            visited_edge.add((start, nb))
            visited_edge.add((nb, start))
            prev, cur = start, nb
            while cur not in nodeset:
                nxts = [p for p in _neighbors(skel, *cur) if p != prev]
                if not nxts:
                    break
                nxt = nxts[0]
                visited_edge.add((cur, nxt)); visited_edge.add((nxt, cur))
                path.append(nxt)
                prev, cur = cur, nxt
            if len(path) >= 2 and path[0] != path[-1]:
                edges.append(path)
    return nodeset, edges


# ── public extractor ──────────────────────────────────────────────────────

def extract_truss(result, *, threshold: float = 0.3,
                  merge: float | None = None) -> StrutAndTieModel:
    """Extract a :class:`StrutAndTieModel` from a
    :class:`~civilpy.structural.stm_topology.simp.DensityResult`.

    Parameters
    ----------
    threshold:
        Density above which a cell is part of the load path.
    merge:
        Node-merge tolerance in pixels (default scales with the mesh).  Each
        traced skeleton path becomes a single straight member between its real
        graph nodes, so truss joints land only at supports, loads, and genuine
        junctions.
    """
    mesh = result.mesh
    if merge is None:
        merge = max(3.0, 0.05 * mesh.nelx)

    binary = result.density >= threshold
    skel = zhang_suen(binary)

    # anchor pixels: nearest skeleton pixel to each support / load
    sk_idx = np.argwhere(skel)
    anchors, anchor_points = [], []
    for kind, pt in _bc_points(mesh.problem):
        rc = _nearest_skel(sk_idx, _xy_to_rc(mesh, *pt))
        if rc is not None:
            anchors.append(rc)
            anchor_points.append((kind, pt, rc))

    nodeset, edges = _trace_graph(skel, anchors)

    # truss nodes live only at the real graph nodes (junctions + anchors);
    # each traced path becomes ONE straight member between its endpoints, so a
    # smooth arch with no junction is a single strut, not a wobbly chain.
    coords = {}          # (r,c) -> id
    node_rc = []         # id -> (r,c)
    members = []

    def node_for(rc):
        if rc not in coords:
            coords[rc] = len(node_rc)
            node_rc.append(rc)
        return coords[rc]

    anchor_ids = set()
    for path in edges:
        ia, ib = node_for(path[0]), node_for(path[-1])
        if ia != ib:
            members.append((ia, ib))
    for _, _, rc in anchor_points:
        if rc in coords:
            anchor_ids.add(coords[rc])

    # merge near-coincident nodes, then clean the truss topology
    node_rc, members, remap = _merge_nodes(node_rc, members, merge, anchor_ids)
    anchor_ids = {remap[i] for i in anchor_ids if i in remap}
    node_rc, members, anchor_ids = _cleanup_graph(node_rc, members, anchor_ids)

    # assemble the StrutAndTieModel in model coordinates
    model = StrutAndTieModel()
    labels = _labeler()
    id_label = {}
    for nid, rc in enumerate(node_rc):
        if rc is None:
            continue
        x, y = _rc_to_xy(mesh, *rc)
        lab = labels()
        id_label[nid] = lab
        model.add_node(lab, x, y)
    seen = set()
    for ia, ib in members:
        la, lb = id_label.get(ia), id_label.get(ib)
        if la is None or lb is None or la == lb:
            continue
        key = frozenset((la, lb))
        if key in seen:
            continue
        seen.add(key)
        model.add_member(la, lb)

    # attach supports and loads to the node nearest each anchor, and relocate
    # that node onto the true boundary-condition coordinate (the reaction/load
    # genuinely acts there, and it pins the support to the structure boundary).
    used = set()
    for kind, pt, rc in anchor_points:
        lab = _nearest_label(model, pt, exclude=used)
        if lab is None:
            continue
        used.add(lab)
        model.nodes[lab] = (float(pt[0]), float(pt[1]))
        if kind[0] == "support":
            model.add_support(lab, fix_x=kind[1], fix_y=kind[2])
        else:
            model.add_load(lab, fx=kind[1], fy=kind[2])

    return model


# ── helpers ────────────────────────────────────────────────────────────────

def _bc_points(problem):
    for s in problem.supports:
        yield ("support", s.fix_x, s.fix_y), (s.x, s.y)
    for ld in problem.loads:
        yield ("load", ld.fx, ld.fy), (ld.x, ld.y)


def _xy_to_rc(mesh, x, y):
    col = (x - mesh.x0) / mesh.h - 0.5
    row = (mesh.ytop - y) / mesh.h - 0.5
    return row, col


def _rc_to_xy(mesh, r, c):
    return mesh.x0 + (c + 0.5) * mesh.h, mesh.ytop - (r + 0.5) * mesh.h


def _nearest_skel(sk_idx, rc):
    if len(sk_idx) == 0:
        return None
    d = (sk_idx[:, 0] - rc[0]) ** 2 + (sk_idx[:, 1] - rc[1]) ** 2
    r, c = sk_idx[int(np.argmin(d))]
    return (int(r), int(c))


def _merge_nodes(node_rc, members, tol, anchor_ids=frozenset()):
    """Collapse nodes within ``tol`` pixels.  Two distinct anchor nodes are
    never merged together (supports and loads must stay separate).  Returns
    ``(new_rc, new_members, full_remap)`` mapping every old id to its new id."""
    pts = np.array([rc for rc in node_rc], float)
    rep = list(range(len(node_rc)))
    for i in range(len(node_rc)):
        if rep[i] != i:
            continue
        for j in range(i + 1, len(node_rc)):
            if rep[j] != j:
                continue
            if i in anchor_ids and j in anchor_ids:
                continue
            if np.hypot(*(pts[i] - pts[j])) <= tol:
                rep[j] = i
    keep = sorted(set(rep))
    compact = {old: k for k, old in enumerate(keep)}
    full_remap = {i: compact[rep[i]] for i in range(len(node_rc))}
    new_rc = [node_rc[old] for old in keep]
    new_members = []
    for a, b in members:
        a, b = full_remap[a], full_remap[b]
        if a != b:
            new_members.append((a, b))
    return new_rc, new_members, full_remap


def _cleanup_graph(node_rc, members, anchor_ids):
    """Make the graph a stable truss: drop duplicate members, iteratively prune
    degree-1 spurs and contract degree-2 chains (both only at non-anchor
    nodes), then keep the connected component holding the most anchors."""
    from collections import defaultdict

    edges = {frozenset((a, b)) for a, b in members if a != b}
    adj = defaultdict(set)
    for e in edges:
        a, b = tuple(e)
        adj[a].add(b); adj[b].add(a)

    changed = True
    while changed:
        changed = False
        for nd in list(adj.keys()):
            deg = len(adj[nd])
            if nd in anchor_ids:
                continue
            if deg == 1:
                nb = next(iter(adj[nd]))
                adj[nb].discard(nd); adj.pop(nd, None)
                edges.discard(frozenset((nd, nb)))
                changed = True
            elif deg == 2:
                a, b = tuple(adj[nd])
                adj[a].discard(nd); adj[b].discard(nd); adj.pop(nd, None)
                edges.discard(frozenset((nd, a))); edges.discard(frozenset((nd, b)))
                if a != b:
                    edges.add(frozenset((a, b)))
                    adj[a].add(b); adj[b].add(a)
                changed = True
            elif deg == 0:
                adj.pop(nd, None)
                changed = True

    # connected components — keep the one with the most anchor nodes
    seen, comps = set(), []
    for start in adj:
        if start in seen:
            continue
        stack, comp = [start], set()
        while stack:
            u = stack.pop()
            if u in comp:
                continue
            comp.add(u); seen.add(u)
            stack.extend(adj[u] - comp)
        comps.append(comp)
    if comps:
        best = max(comps, key=lambda c: (len(c & anchor_ids), len(c)))
        edges = {e for e in edges if set(e) <= best}
        kept_nodes = best
    else:
        kept_nodes = set()

    keep = sorted(kept_nodes)
    compact = {old: k for k, old in enumerate(keep)}
    new_rc = [node_rc[old] for old in keep]
    new_members = [(compact[a], compact[b]) for e in edges for a, b in [tuple(e)]]
    new_anchor_ids = {compact[a] for a in anchor_ids if a in compact}
    return new_rc, new_members, new_anchor_ids


def _labeler():
    seq = []
    n = [0]

    def nxt():
        i = n[0]
        n[0] += 1
        s = ""
        i2 = i
        while True:
            s = string.ascii_uppercase[i2 % 26] + s
            i2 = i2 // 26 - 1
            if i2 < 0:
                break
        return s
    return nxt


def _nearest_label(model, pt, exclude=()):
    best, bestd = None, None
    for lab, (x, y) in model.nodes.items():
        if lab in exclude:
            continue
        d = (x - pt[0]) ** 2 + (y - pt[1]) ** 2
        if bestd is None or d < bestd:
            best, bestd = lab, d
    return best
