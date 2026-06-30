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
from itertools import combinations

import numpy as np
from scipy.optimize import linprog

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


# ── ground-structure stabilization (Phase 3½) ──────────────────────────────
#
# Skeleton tracing reliably finds the *struts* (the load fans down to the
# supports) but routinely misses the *ties* — the top and bottom chords — because
# a tension chord hugs the member face where the SIMP density is smeared and
# thin, and because long collinear runs get contracted away.  The raw truss is
# therefore usually a mechanism (more joint equations than members + reactions).
#
# Rather than merging joints until the truss accidentally becomes solvable (which
# collapses a rich pier-cap into a bare triangle), we *complete* it the way a
# truss topology optimizer would: treat the skeleton joints as a node set, lay in
# every candidate member that runs through solid material (a "ground structure"),
# size them all by a fully-stressed solve, then prune the members that carry
# essentially no force.  What survives is the discrete strut-and-tie load path.


def is_stable(model, tol: float = 1e-8) -> bool:
    """True when the truss has no mechanism — its free-DOF stiffness matrix
    (unit member stiffness, supports applied) is non-singular.

    This is the honest stability test the pipeline needs: the member/reaction
    *count* (:meth:`StrutAndTieModel.degree_of_indeterminacy`) is necessary but
    not sufficient, and ``np.linalg.solve`` can return garbage for a near-
    mechanism instead of raising.  We compare the smallest singular value of the
    free-free stiffness block against the largest.
    """
    if len(model.nodes) < 3 or len(model.members) < 3:
        return False
    kff = _free_stiffness(model)
    if kff.size == 0:
        return False
    s = np.linalg.svd(kff, compute_uv=False)
    return bool(s[-1] > tol * s[0])


def refine_truss(model, density_result, *, method: str = "lp", **kwargs):
    """Turn a raw skeleton truss into a clean, solved strut-and-tie model.

    ``method="lp"`` (default) runs :func:`layout_optimize_truss` — a single
    global plastic truss layout optimization that is inherently symmetric for a
    symmetric problem.  It returns a *new* model.  ``method="fsd"`` (or an ``lp``
    failure) falls back to the in-place ground-structure fully-stressed-design
    refinement :func:`_refine_fsd`.

    Returns the model to use (possibly a new object), so callers must use the
    return value rather than assuming in-place mutation.
    """
    if method == "lp":
        lp = layout_optimize_truss(model, density_result,
                                   **{k: kwargs[k] for k in kwargs
                                      if k in _LP_KW})
        if lp is not None and len(lp.members) >= 3:
            return lp
    _refine_fsd(model, density_result,
                **{k: kwargs[k] for k in kwargs if k in _FSD_KW})
    return model


_LP_KW = {"keep", "min_density", "search", "betweenness", "cluster_tol",
          "symmetric"}
_FSD_KW = {"search", "passover_tol", "threshold", "coverage", "prune_frac"}


# ── method 1: plastic truss layout optimization (LP) ─────────────────────────
#
# The principled extractor.  Skeleton tracing only fixes the node *positions*;
# the discrete load path is then chosen by a linear program that minimizes the
# Michell structural volume ``sum |F_i| L_i w_i`` subject to nodal equilibrium
# ``B F = P`` over a ground structure of candidate members.  Because an LP finds
# the global optimum, a symmetric problem yields a symmetric truss — no
# path-dependent, symmetry-breaking greedy pruning.  Each member is split into a
# tension part ``t>=0`` and a compression part ``c>=0`` so ties and struts share
# one linear model; ``w_i`` is a gentle density weight (members down dense bands
# are cheaper) and candidates that cross a void are filtered out entirely.


def layout_optimize_truss(model, density_result, *, keep: float = 0.02,
                          min_density: float = 0.12, search: float | None = None,
                          betweenness: float | None = None,
                          cluster_tol: float | None = None,
                          symmetric: bool = True):
    """Extract a strut-and-tie model by LP plastic layout optimization.

    Uses ``model``'s joints (cleaned: clustered, and mirrored when the problem is
    symmetric) as the node set, lays a density-filtered ground structure between
    them, and solves a single LP for the minimum-volume equilibrium load path.
    Returns a new :class:`StrutAndTieModel` with member forces and reactions
    already populated, or ``None`` if the program is infeasible (caller falls
    back to the FSD refinement).
    """
    mesh = density_result.mesh
    width = mesh.width
    if search is None:
        search = max(3.0 * mesh.h, 0.02 * width)
    if betweenness is None:
        betweenness = 0.04 * width
    if cluster_tol is None:
        cluster_tol = 0.055 * width
    sample = _density_sampler(mesh, density_result.density)

    anchors = ([("support", model.nodes[l], model.supports[l]) for l in model.supports]
               + [("load", model.nodes[l], tuple(model.loads[l])) for l in model.loads])
    if not anchors:
        return None

    # 1. clean, optionally symmetric node set
    raw = list(model.nodes.values()) + [a[1] for a in anchors]
    x0 = _detect_symmetry(anchors) if symmetric else None
    nodes = (_symmetrize(raw, x0, cluster_tol) if x0 is not None
             else _cluster_points(raw, cluster_tol))
    nodes = np.array(nodes, dtype=float)
    for _, (px, py), _ in anchors:                    # snap exact anchor coords
        nodes[int(np.argmin((nodes[:, 0] - px) ** 2 + (nodes[:, 1] - py) ** 2))] = (px, py)
    nodes = np.array(_cluster_points(nodes, 1e-6), dtype=float)
    n = len(nodes)
    if n < 3:
        return None

    mirror = {}
    if x0 is not None:
        for i, (x, y) in enumerate(nodes):
            mirror[i] = int(np.argmin((nodes[:, 0] - (2 * x0 - x)) ** 2
                                      + (nodes[:, 1] - y) ** 2))

    # 2. ground structure of candidate members (betweenness + density filters)
    members, meta = [], []
    for i, j in combinations(range(n), 2):
        pa, pb = tuple(nodes[i]), tuple(nodes[j])
        length = float(np.hypot(pb[0] - pa[0], pb[1] - pa[1]))
        if length < 1e-6:
            continue
        others = [tuple(nodes[k]) for k in range(n) if k not in (i, j)]
        if _passes_over_node(pa, pb, others, betweenness):
            continue
        avg, mn = _line_density(sample, pa, pb, search, mesh.h)
        if avg < min_density or mn < 0.02:
            continue
        w = 1.0 / (avg + 0.6)                          # gentle density weight
        members.append((i, j))
        meta.append((length, w, (pb[0] - pa[0]) / length, (pb[1] - pa[1]) / length))
    m = len(members)
    if m < 3:
        return None

    # 3. equilibrium B (t - c) = -P over the free DOFs
    fixed = np.zeros((n, 2), dtype=bool)
    load = np.zeros((n, 2))
    for kind, (px, py), spec in anchors:
        i = int(np.argmin((nodes[:, 0] - px) ** 2 + (nodes[:, 1] - py) ** 2))
        if kind == "support":
            fixed[i, 0] |= bool(spec[0])
            fixed[i, 1] |= bool(spec[1])
        else:
            load[i, 0] += spec[0]
            load[i, 1] += spec[1]
    free = [(i, d) for i in range(n) for d in range(2) if not fixed[i, d]]
    rowi = {fd: r for r, fd in enumerate(free)}
    a_eq = np.zeros((len(free), 2 * m))
    b_eq = np.zeros(len(free))
    for (i, d), r in rowi.items():
        b_eq[r] = -load[i, d]
    for k, (i, j) in enumerate(members):
        _, _, cx, cy = meta[k]
        for node, u in ((i, (cx, cy)), (j, (-cx, -cy))):
            for d in range(2):
                if (node, d) in rowi:
                    a_eq[rowi[(node, d)], k] += u[d]
                    a_eq[rowi[(node, d)], m + k] -= u[d]

    # 4. symmetry equality constraints t_k == t_mirror, c_k == c_mirror
    if x0 is not None:
        key = {frozenset(mb): k for k, mb in enumerate(members)}
        seen, extra = set(), []
        for k, (i, j) in enumerate(members):
            kk = key.get(frozenset((mirror[i], mirror[j])))
            if kk is None or kk == k or (k, kk) in seen:
                continue
            seen.add((k, kk))
            seen.add((kk, k))
            rt = np.zeros(2 * m); rt[k] = 1; rt[kk] = -1; extra.append(rt)
            rc = np.zeros(2 * m); rc[m + k] = 1; rc[m + kk] = -1; extra.append(rc)
        if extra:
            a_eq = np.vstack([a_eq, np.vstack(extra)])
            b_eq = np.concatenate([b_eq, np.zeros(len(extra))])

    # 5. minimize Michell volume sum L_k w_k (t_k + c_k)
    cost = np.array([meta[k][0] * meta[k][1] for k in range(m)])
    res = linprog(np.concatenate([cost, cost]), A_eq=a_eq, b_eq=b_eq,
                  bounds=[(0, None)] * (2 * m), method="highs")
    if not res.success:
        return None

    f = res.x[:m] - res.x[m:]
    fmax = float(np.abs(f).max()) or 1.0
    kept = [k for k in range(m) if abs(f[k]) > keep * fmax]
    if len(kept) < 3:
        return None

    return _assemble_model(nodes, members, meta, f, kept, anchors, load)


def _assemble_model(nodes, members, meta, f, kept, anchors, load):
    out = StrutAndTieModel()
    used = sorted({nd for k in kept for nd in members[k]})
    labeler = _labeler()
    label = {i: labeler() for i in used}
    for i in used:
        out.add_node(label[i], float(nodes[i, 0]), float(nodes[i, 1]))
    forces = {}
    for k in kept:
        i, j = members[k]
        out.add_member(label[i], label[j])
        forces[(label[i], label[j])] = float(f[k])
    out.forces = forces

    reactions = {}
    for kind, (px, py), spec in anchors:
        i = int(np.argmin((nodes[:, 0] - px) ** 2 + (nodes[:, 1] - py) ** 2))
        if i not in label:
            continue
        lab = label[i]
        if kind == "support":
            out.add_support(lab, fix_x=bool(spec[0]), fix_y=bool(spec[1]))
            rx = ry = 0.0
            for k in kept:
                a, b = members[k]
                if i in (a, b):
                    _, _, cx, cy = meta[k]
                    u = (cx, cy) if a == i else (-cx, -cy)
                    rx -= u[0] * f[k]
                    ry -= u[1] * f[k]
            reactions[lab] = [rx - load[i, 0], ry - load[i, 1]]
        else:
            out.add_load(lab, fx=spec[0], fy=spec[1])
    out.reactions = reactions
    return out


# ── node-set helpers (clustering + symmetry) ─────────────────────────────────

def _cluster_points(pts, tol):
    """Greedy single-link clustering: collapse points within ``tol`` to their
    centroid (cleans noisy skeleton joints into single geometric centers)."""
    pts = [tuple(float(c) for c in p) for p in pts]
    out = []
    while pts:
        seed = pts.pop()
        group, rest = [seed], []
        for p in pts:
            (group if np.hypot(p[0] - seed[0], p[1] - seed[1]) <= tol
             else rest).append(p)
        pts = rest
        out.append((float(np.mean([g[0] for g in group])),
                    float(np.mean([g[1] for g in group]))))
    return out


def _detect_symmetry(anchors, tol=0.5):
    """Vertical mirror axis ``x0`` if every support/load has a mirror partner in
    the anchor set, else ``None``."""
    xs = [a[1][0] for a in anchors]
    x0 = (min(xs) + max(xs)) / 2.0
    pts = [a[1] for a in anchors]
    for x, y in pts:
        mx = 2 * x0 - x
        if not any(abs(mx - px) < tol and abs(y - py) < tol for px, py in pts):
            return None
    return x0


def _symmetrize(pts, x0, tol):
    """Fold points across ``x0``, cluster the half-plane, then unfold — yielding
    an exactly mirror-symmetric node set (axis points land on ``x0``)."""
    left = [(x if x <= x0 else 2 * x0 - x, y) for x, y in pts]
    out = []
    for cx, cy in _cluster_points(left, tol):
        if abs(cx - x0) <= 0.5 * tol:
            out.append((x0, cy))
        else:
            out.append((cx, cy))
            out.append((2 * x0 - cx, cy))
    return _cluster_points(out, 1e-6)


def _line_density(sample, pa, pb, search, h, n=25):
    """Mean and min density along a member, searching ``search`` perpendicular
    (a line integral of the density field, per the literature's recommendation
    to weight members by the material they actually run through)."""
    offs = np.linspace(-search, search, max(3, int(2 * search / h) + 1))
    vals = []
    for t in np.linspace(0.0, 1.0, n):
        x = pa[0] + t * (pb[0] - pa[0])
        y = pa[1] + t * (pb[1] - pa[1])
        vals.append(max(sample(x + ox, y + oy) for ox in offs for oy in offs))
    return float(np.mean(vals)), float(np.min(vals))


# ── method 2: ground-structure fully-stressed design (fallback) ──────────────

def _refine_fsd(model, density_result, *, search: float | None = None,
                passover_tol: float | None = None, threshold: float = 0.25,
                coverage: float = 0.8, prune_frac: float = 0.04):
    """Fallback completion: add every solid-supported candidate member, size by
    a fully-stressed solve, then prune the dead ones (in place).  Used when the
    LP layout optimization is infeasible."""
    mesh = density_result.mesh
    if search is None:
        search = max(3.0 * mesh.h, 0.02 * mesh.width)
    if passover_tol is None:
        passover_tol = 2.0 * search
    sample = _density_sampler(mesh, density_result.density)

    # 1. ground structure — add every solid-supported, non-pass-over candidate
    labels = list(model.nodes)
    existing = {frozenset(m) for m in model.members}
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            if frozenset((a, b)) in existing:
                continue
            pa, pb = model.nodes[a], model.nodes[b]
            others = [model.nodes[c] for c in labels if c != a and c != b]
            if _passes_over_node(pa, pb, others, passover_tol):
                continue
            if _seg_in_solid(sample, mesh.h, pa, pb, search, threshold, coverage):
                model.add_member(a, b)

    # 2. size by a fully-stressed solve, then 3. prune the dead members
    anchors = set(model.supports) | set(model.loads)
    try:
        model.solve_fully_stressed()
    except ValueError:
        return model     # ground structure itself unsolvable; leave for review
    _prune_members(model, anchors, prune_frac)
    try:
        model.solve_fully_stressed()
    except ValueError:
        pass
    return model


def _free_stiffness(model):
    """Free-DOF truss stiffness with unit member stiffness (1/L axial)."""
    idx = {n: i for i, n in enumerate(model.nodes)}
    ndof = 2 * len(model.nodes)
    k = np.zeros((ndof, ndof))
    for a, b in model.members:
        (xa, ya), (xb, yb) = model.nodes[a], model.nodes[b]
        length = np.hypot(xb - xa, yb - ya)
        if length < 1e-9:
            continue
        cx, cy = (xb - xa) / length, (yb - ya) / length
        c = np.array([cx, cy, -cx, -cy])
        d = [2 * idx[a], 2 * idx[a] + 1, 2 * idx[b], 2 * idx[b] + 1]
        k[np.ix_(d, d)] += np.outer(c, c) / length
    fixed = np.zeros(ndof, dtype=bool)
    for n, (fx, fy) in model.supports.items():
        if n not in idx:
            continue
        if fx:
            fixed[2 * idx[n]] = True
        if fy:
            fixed[2 * idx[n] + 1] = True
    free = ~fixed
    return k[np.ix_(free, free)] if free.any() else np.zeros((0, 0))


def _density_sampler(mesh, density):
    def sample(x, y):
        col = int(round((x - mesh.x0) / mesh.h - 0.5))
        row = int(round((mesh.ytop - y) / mesh.h - 0.5))
        if 0 <= row < mesh.nely and 0 <= col < mesh.nelx:
            return float(density[row, col])
        return 0.0
    return sample


def _seg_in_solid(sample, h, pa, pb, search, threshold, coverage, n=24):
    xa, ya = pa
    xb, yb = pb
    offs = np.linspace(-search, search, max(3, int(2 * search / h) + 1))
    hits = 0
    for t in np.linspace(0.0, 1.0, n):
        x = xa + t * (xb - xa)
        y = ya + t * (yb - ya)
        if max(sample(x + ox, y + oy) for ox in offs for oy in offs) >= threshold:
            hits += 1
    return hits / n >= coverage


def _passes_over_node(pa, pb, others, tol):
    ax, ay = pa
    bx, by = pb
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 < 1e-12:
        return True
    for cx, cy in others:
        t = ((cx - ax) * dx + (cy - ay) * dy) / seg2
        if 0.02 < t < 0.98:
            px, py = ax + t * dx, ay + t * dy
            if (cx - px) ** 2 + (cy - py) ** 2 < tol * tol:
                return True
    return False


def _anchors_connected(model, anchors):
    used = {n for m in model.members for n in m}
    return all(a in used for a in anchors)


def _prune_members(model, anchors, frac):
    """Greedily drop the lowest-force member while the truss stays stable and
    every support/load remains attached — the ground-structure clean-up."""
    while True:
        try:
            model.solve_fully_stressed()
        except ValueError:
            return
        forces = model.forces or {}
        fmax = max((abs(v) for v in forces.values()), default=0.0)
        if fmax <= 0.0:
            return
        removed = False
        for mem in sorted(model.members, key=lambda m: abs(forces.get(m, 0.0))):
            if abs(forces.get(mem, 0.0)) >= frac * fmax:
                break
            saved_members = list(model.members)
            saved_area = model.areas.get(mem)
            model.members = [m for m in model.members if m != mem]
            model.areas.pop(mem, None)
            if is_stable(model) and _anchors_connected(model, anchors):
                removed = True
                break
            model.members = saved_members
            if saved_area is not None:
                model.areas[mem] = saved_area
        if not removed:
            return
