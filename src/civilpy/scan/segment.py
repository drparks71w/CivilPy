#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Segmentation: primitives (planes, cylinders), ground, clusters, regions.

All algorithms are ``numpy``/``scipy`` implementations chosen for what a
bridge scan actually contains — large planar faces (deck, soffit, walls,
girder webs), round columns and piles, and a ground surface that must be
peeled off first:

* :func:`ransac_plane` / :func:`segment_planes` — vectorised RANSAC with
  SVD refinement; iterative extraction of the ``max_planes`` largest.
* :func:`ransac_cylinder` / :func:`segment_cylinders` — two-point-with-
  normals RANSAC for right circular cylinders with a radius window
  (piers 1–6 ft, piles 0.5–1.5 ft, pipes / posts smaller).
* :func:`ground_mask` — a progressive morphological filter (Zhang et al.
  2003) on a min-elevation raster, which separates terrain from the
  structure standing on it without any classification in the file.
* :func:`euclidean_clusters` — connected components under a distance
  radius (the PCL ``EuclideanClusterExtraction`` idea).
* :func:`region_growing` — smoothness-constrained growth from low-
  curvature seeds; produces smooth patches even when they are not planar.
* :func:`slice_elevation` / :func:`slice_axis` — cross-sections.

Every function takes an ``(N, 3)`` array (or a
:class:`~civilpy.scan.cloud.PointCloud`) and returns index arrays / masks /
labels so callers can keep the point attributes they care about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from civilpy.scan.cloud import PointCloud
from civilpy.scan.preprocess import local_pca

ArrayOrCloud = Union[np.ndarray, PointCloud]


def _xyz(obj: ArrayOrCloud) -> np.ndarray:
    return obj.xyz if isinstance(obj, PointCloud) else np.asarray(obj, dtype=float)


def _normals(obj: ArrayOrCloud, normals, k: int = 16) -> np.ndarray:
    if normals is not None:
        return np.asarray(normals, dtype=float)
    if isinstance(obj, PointCloud) and obj.normals is not None:
        return np.asarray(obj.normals, dtype=float)
    n, _, _ = local_pca(_xyz(obj), k=k)
    return n


# ---------------------------------------------------------------------------
# plane RANSAC
# ---------------------------------------------------------------------------

@dataclass
class PlaneModel:
    """``normal · x = d`` with unit ``normal``."""

    normal: np.ndarray
    d: float
    inliers: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    rms: float = 0.0

    @property
    def centroid(self) -> np.ndarray:
        return self.normal * self.d

    def distance(self, xyz) -> np.ndarray:
        return np.asarray(xyz, dtype=float) @ self.normal - self.d

    def project(self, xyz) -> np.ndarray:
        xyz = np.asarray(xyz, dtype=float)
        return xyz - np.outer(self.distance(xyz), self.normal)


def fit_plane_lsq(xyz: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Total-least-squares plane; returns ``(unit normal, d, rms)``."""
    P = np.asarray(xyz, dtype=float)
    c = P.mean(axis=0)
    _, s, vt = np.linalg.svd(P - c, full_matrices=False)
    n = vt[-1]
    if n[2] < 0 or (n[2] == 0 and n[int(np.argmax(np.abs(n)))] < 0):
        n = -n
    d = float(c @ n)
    rms = float(np.sqrt(np.mean(((P - c) @ n) ** 2))) if len(P) > 3 else 0.0
    return n, d, rms


def ransac_plane(obj: ArrayOrCloud, distance: float = 0.05, n_iter: int = 500,
                 sample_size: int = 50_000, seed: Optional[int] = 0,
                 normals=None, normal_angle: Optional[float] = None,
                 axis=None, axis_angle: Optional[float] = None) -> Optional[PlaneModel]:
    """Largest plane by RANSAC.

    ``distance`` is the inlier band (ft); hypotheses are scored on a random
    ``sample_size`` subset then the winner is refined by SVD on all inliers
    (twice).  Optional constraints: ``normals`` + ``normal_angle`` (deg)
    reject inliers whose point normal disagrees with the plane;
    ``axis`` + ``axis_angle`` keep only planes whose normal is within
    ``axis_angle`` degrees of ``axis`` (e.g. ``(0, 0, 1)`` for
    horizontal surfaces).
    """
    xyz = _xyz(obj)
    n = len(xyz)
    if n < 3:
        return None
    rng = np.random.default_rng(seed)
    score_idx = np.arange(n) if n <= sample_size else rng.choice(n, sample_size, replace=False)
    S = xyz[score_idx]
    tri = rng.integers(0, n, size=(n_iter, 3))
    p0, p1, p2 = xyz[tri[:, 0]], xyz[tri[:, 1]], xyz[tri[:, 2]]
    nrm = np.cross(p1 - p0, p2 - p0)
    length = np.linalg.norm(nrm, axis=1)
    ok = length > 1e-12
    if axis is not None and axis_angle is not None:
        a = np.asarray(axis, dtype=float)
        a = a / np.linalg.norm(a)
        cosang = np.abs(nrm @ a) / np.where(ok, length, 1)
        ok &= cosang >= np.cos(np.radians(axis_angle))
    if not ok.any():
        return None
    nrm = nrm[ok] / length[ok, None]
    p0 = p0[ok]
    d = np.einsum("ij,ij->i", nrm, p0)
    dist = np.abs(S @ nrm.T - d[None, :])          # (m, hyp)
    counts = (dist <= distance).sum(axis=0)
    best = int(np.argmax(counts))
    if counts[best] < 3:
        return None
    normal, dd = nrm[best], d[best]
    inl = np.abs(xyz @ normal - dd) <= distance
    for _ in range(2):
        if inl.sum() < 3:
            break
        normal, dd, _ = fit_plane_lsq(xyz[inl])
        inl = np.abs(xyz @ normal - dd) <= distance
    if normals is not None and normal_angle is not None:
        nn = np.asarray(normals, dtype=float)
        cosang = np.abs(nn @ normal)
        inl &= cosang >= np.cos(np.radians(normal_angle))
    idx = np.nonzero(inl)[0]
    if len(idx) < 3:
        return None
    _, _, rms = fit_plane_lsq(xyz[idx])
    return PlaneModel(normal=normal, d=float(dd), inliers=idx, rms=rms)


def segment_planes(obj: ArrayOrCloud, distance: float = 0.05, min_points: int = 500,
                   max_planes: int = 20, n_iter: int = 500, seed: Optional[int] = 0,
                   normals=None, normal_angle: Optional[float] = 30.0,
                   connect_radius: Optional[float] = None,
                   min_fraction: float = 0.0) -> list[PlaneModel]:
    """Iteratively extract planes, largest first, until fewer than
    ``min_points`` (or ``min_fraction`` of the input) remain in the best
    candidate or ``max_planes`` are found.

    With ``connect_radius`` each plane's inliers are reduced to their
    largest spatially connected component, so two coplanar faces on
    opposite sides of a pier (or a wall and a distant retaining wall)
    become separate planes instead of one.  Inlier indices refer to the
    input array.
    """
    xyz = _xyz(obj)
    nn = _normals(obj, normals) if normal_angle is not None else None
    remaining = np.arange(len(xyz))
    planes: list[PlaneModel] = []
    floor = max(min_points, int(min_fraction * len(xyz)))
    rng_seed = seed
    while len(remaining) >= max(floor, 3) and len(planes) < max_planes:
        sub = xyz[remaining]
        sub_n = nn[remaining] if nn is not None else None
        pm = ransac_plane(sub, distance=distance, n_iter=n_iter, seed=rng_seed,
                          normals=sub_n, normal_angle=normal_angle)
        if rng_seed is not None:
            rng_seed += 1
        if pm is None or len(pm.inliers) < floor:
            break
        local = pm.inliers
        if connect_radius:
            labels = euclidean_clusters(sub[local], radius=connect_radius, min_points=1)
            if labels.max() >= 0:
                biggest = np.bincount(labels[labels >= 0]).argmax()
                local = local[labels == biggest]
                if len(local) < floor:
                    # the best plane is fragmented: drop its points from
                    # consideration rather than looping forever
                    remaining = np.setdiff1d(remaining, remaining[pm.inliers])
                    continue
                normal, d, rms = fit_plane_lsq(sub[local])
                pm = PlaneModel(normal=normal, d=d, rms=rms)
        pm.inliers = remaining[local]
        planes.append(pm)
        remaining = np.setdiff1d(remaining, pm.inliers)
    return planes


# ---------------------------------------------------------------------------
# cylinder RANSAC
# ---------------------------------------------------------------------------

@dataclass
class CylinderModel:
    """A right circular cylinder: a point ``center`` on the axis, unit
    ``axis`` direction, ``radius``, and the axial ``extent`` (min, max)
    of its inliers relative to ``center``."""

    center: np.ndarray
    axis: np.ndarray
    radius: float
    inliers: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    extent: tuple[float, float] = (0.0, 0.0)
    rms: float = 0.0

    @property
    def length(self) -> float:
        return float(self.extent[1] - self.extent[0])

    @property
    def start(self) -> np.ndarray:
        return self.center + self.axis * self.extent[0]

    @property
    def end(self) -> np.ndarray:
        return self.center + self.axis * self.extent[1]

    def radial_distance(self, xyz) -> np.ndarray:
        """Signed distance from the cylinder surface (positive outside)."""
        rel = np.asarray(xyz, dtype=float) - self.center
        t = rel @ self.axis
        perp = rel - np.outer(t, self.axis)
        return np.linalg.norm(perp, axis=1) - self.radius


def _fit_circle_2d(pts: np.ndarray) -> tuple[np.ndarray, float]:
    """Algebraic (Kåsa) least-squares circle through 2-D points."""
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([2 * x, 2 * y, np.ones(len(x))])
    b = x ** 2 + y ** 2
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = sol[0], sol[1]
    r = np.sqrt(max(sol[2] + cx ** 2 + cy ** 2, 0.0))
    return np.array([cx, cy]), float(r)


def _cylinder_from_inliers(xyz: np.ndarray, axis: np.ndarray,
                           normals: Optional[np.ndarray] = None) -> CylinderModel:
    """Re-fit a cylinder to inlier points.  With ``normals`` the axis is
    refined first as the least-variance direction of the normal set (every
    normal of a cylinder is perpendicular to its axis); the centre and
    radius then come from an algebraic circle fit in the plane
    perpendicular to that axis."""
    axis = axis / np.linalg.norm(axis)
    if normals is not None and len(normals) >= 3:
        nn = np.asarray(normals, dtype=float)
        _, vecs = np.linalg.eigh(nn.T @ nn)
        cand = vecs[:, 0]
        if cand @ axis < 0:
            cand = -cand
        if cand @ axis > np.cos(np.radians(15.0)):       # reject a wild jump
            axis = cand
    # in-plane basis perpendicular to the axis
    helper = np.array([1.0, 0, 0]) if abs(axis[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = np.cross(axis, helper)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    c0 = xyz.mean(axis=0)
    rel = xyz - c0
    uv = np.column_stack([rel @ e1, rel @ e2])
    c2, r = _fit_circle_2d(uv)
    center = c0 + c2[0] * e1 + c2[1] * e2
    t = (xyz - center) @ axis
    model = CylinderModel(center=center, axis=axis, radius=r,
                          extent=(float(t.min()), float(t.max())))
    model.rms = float(np.sqrt(np.mean(model.radial_distance(xyz) ** 2)))
    return model


def ransac_cylinder(obj: ArrayOrCloud, distance: float = 0.05, n_iter: int = 1000,
                    radius_range: tuple[float, float] = (0.25, 8.0),
                    normals=None, normal_angle: float = 20.0,
                    axis=None, axis_angle: Optional[float] = None,
                    sample_size: int = 30_000, seed: Optional[int] = 0,
                    k_normals: int = 16) -> Optional[CylinderModel]:
    """Largest cylinder by RANSAC on two points *with normals*.

    For each hypothesis the axis is ``n1 × n2``, the centre is the least-
    squares intersection of the two normal lines projected perpendicular
    to that axis, and the radius follows.  Inliers lie within ``distance``
    of the surface and have normals within ``normal_angle`` degrees of the
    radial direction (this is what stops a flat wall from scoring as a
    huge-radius cylinder).  ``radius_range`` bounds the hypotheses;
    ``axis`` + ``axis_angle`` restrict the axis direction (``(0, 0, 1)``
    for vertical columns and piles).
    """
    xyz = _xyz(obj)
    n = len(xyz)
    if n < 10:
        return None
    nn = _normals(obj, normals, k=k_normals)
    rng = np.random.default_rng(seed)
    score_idx = np.arange(n) if n <= sample_size else rng.choice(n, sample_size, replace=False)
    S, SN = xyz[score_idx], nn[score_idx]
    pairs = rng.integers(0, n, size=(n_iter, 2))
    p1, p2 = xyz[pairs[:, 0]], xyz[pairs[:, 1]]
    n1, n2 = nn[pairs[:, 0]], nn[pairs[:, 1]]
    ax = np.cross(n1, n2)
    length = np.linalg.norm(ax, axis=1)
    ok = length > np.sin(np.radians(5.0))
    if axis is not None and axis_angle is not None:
        a = np.asarray(axis, dtype=float)
        a = a / np.linalg.norm(a)
        ok &= np.abs(ax @ a) / np.where(ok, length, 1) >= np.cos(np.radians(axis_angle))
    if not ok.any():
        return None
    ax = ax[ok] / length[ok, None]
    p1, p2, n1, n2 = p1[ok], p2[ok], n1[ok], n2[ok]
    m = len(ax)
    # project into the plane perpendicular to each axis
    def _perp(v):
        return v - np.einsum("ij,ij->i", v, ax)[:, None] * ax
    q1, q2, m1, m2 = _perp(p1), _perp(p2), _perp(n1), _perp(n2)
    # closest point between the two normal lines q1 + s m1 and q2 + t m2
    w = q1 - q2
    a11 = np.einsum("ij,ij->i", m1, m1)
    a12 = -np.einsum("ij,ij->i", m1, m2)
    a22 = np.einsum("ij,ij->i", m2, m2)
    b1 = -np.einsum("ij,ij->i", w, m1)
    b2 = np.einsum("ij,ij->i", w, m2)
    det = a11 * a22 - a12 * a12
    good = np.abs(det) > 1e-9
    s = np.where(good, (b1 * a22 - a12 * b2) / np.where(good, det, 1), 0)
    t = np.where(good, (a11 * b2 - a12 * b1) / np.where(good, det, 1), 0)
    c1 = q1 + s[:, None] * m1
    c2 = q2 + t[:, None] * m2
    center = 0.5 * (c1 + c2)
    r = 0.5 * (np.linalg.norm(q1 - center, axis=1) + np.linalg.norm(q2 - center, axis=1))
    good &= (r >= radius_range[0]) & (r <= radius_range[1])
    if not good.any():
        return None
    ax, center, r = ax[good], center[good], r[good]
    m = len(ax)
    cos_thr = np.cos(np.radians(normal_angle))
    best, best_count = -1, 0
    # score in blocks to bound memory: (hyp, sample) matrices
    block = max(1, int(2e7 // max(len(S), 1)))
    for b0 in range(0, m, block):
        A, C, R = ax[b0:b0 + block], center[b0:b0 + block], r[b0:b0 + block]
        rel = S[None, :, :] - C[:, None, :]                       # (h, s, 3)
        tt = np.einsum("hsi,hi->hs", rel, A)
        perp = rel - tt[:, :, None] * A[:, None, :]
        dist = np.linalg.norm(perp, axis=2)
        radial = perp / np.where(dist[:, :, None] > 0, dist[:, :, None], 1)
        cosang = np.abs(np.einsum("hsi,si->hs", radial, SN))
        inl = (np.abs(dist - R[:, None]) <= distance) & (cosang >= cos_thr)
        counts = inl.sum(axis=1)
        j = int(np.argmax(counts))
        if counts[j] > best_count:
            best, best_count = b0 + j, int(counts[j])
    if best < 0 or best_count < 10:
        return None
    model = CylinderModel(center=center[best], axis=ax[best], radius=float(r[best]))

    def _inliers(mdl):
        rel = xyz - mdl.center
        tt = rel @ mdl.axis
        perp = rel - np.outer(tt, mdl.axis)
        dist = np.linalg.norm(perp, axis=1)
        radial = perp / np.where(dist[:, None] > 0, dist[:, None], 1)
        cosang = np.abs(np.einsum("ij,ij->i", radial, nn))
        return (np.abs(dist - mdl.radius) <= distance) & (cosang >= cos_thr)

    inl = _inliers(model)
    for _ in range(4):
        if inl.sum() < 10:
            break
        model = _cylinder_from_inliers(xyz[inl], model.axis, nn[inl])
        inl = _inliers(model)
    idx = np.nonzero(inl)[0]
    if len(idx) < 10:
        return None
    model = _cylinder_from_inliers(xyz[idx], model.axis, nn[idx])
    model.inliers = idx
    return model


def segment_cylinders(obj: ArrayOrCloud, distance: float = 0.05, min_points: int = 300,
                      max_cylinders: int = 20, n_iter: int = 1000,
                      radius_range: tuple[float, float] = (0.25, 8.0),
                      normals=None, normal_angle: float = 20.0,
                      axis=None, axis_angle: Optional[float] = None,
                      connect_radius: Optional[float] = None,
                      seed: Optional[int] = 0) -> list[CylinderModel]:
    """Iteratively extract cylinders, largest first (see
    :func:`ransac_cylinder`).  ``connect_radius`` keeps only the largest
    connected component of each cylinder's inliers, which separates two
    identical columns in a pier bent that the same model would otherwise
    grab as one (they are coaxial only if they happen to line up)."""
    xyz = _xyz(obj)
    nn = _normals(obj, normals)
    remaining = np.arange(len(xyz))
    out: list[CylinderModel] = []
    rng_seed = seed
    while len(remaining) >= max(min_points, 10) and len(out) < max_cylinders:
        sub, sub_n = xyz[remaining], nn[remaining]
        cm = ransac_cylinder(sub, distance=distance, n_iter=n_iter, radius_range=radius_range,
                             normals=sub_n, normal_angle=normal_angle, axis=axis,
                             axis_angle=axis_angle, seed=rng_seed)
        if rng_seed is not None:
            rng_seed += 1
        if cm is None or len(cm.inliers) < min_points:
            break
        local = cm.inliers
        if connect_radius:
            labels = euclidean_clusters(sub[local], radius=connect_radius, min_points=1)
            if labels.max() >= 0:
                biggest = np.bincount(labels[labels >= 0]).argmax()
                local = local[labels == biggest]
                if len(local) < min_points:
                    remaining = np.setdiff1d(remaining, remaining[cm.inliers])
                    continue
                cm = _cylinder_from_inliers(sub[local], cm.axis, sub_n[local])
        cm.inliers = remaining[local]
        out.append(cm)
        remaining = np.setdiff1d(remaining, cm.inliers)
    return out


# ---------------------------------------------------------------------------
# ground filter (progressive morphological, Zhang et al. 2003)
# ---------------------------------------------------------------------------

def ground_mask(obj: ArrayOrCloud, cell: float = 1.0, max_window: float = 40.0,
                slope: float = 0.15, initial_threshold: float = 0.25,
                max_threshold: float = 3.0, final_threshold: Optional[float] = None) -> np.ndarray:
    """Boolean mask of ground points.

    The minimum elevation per ``cell`` is rasterised (gaps filled from the
    nearest cell), then opened with growing square windows up to
    ``max_window`` ft; cells that drop by more than the height threshold
    ``min(slope * window + initial_threshold, max_threshold)`` under an
    opening are non-ground and replaced by the opened value.  Points within
    ``final_threshold`` (default ``initial_threshold``) of the resulting
    bare-earth surface are ground.

    ``max_window`` must exceed the largest object footprint that should be
    stripped (a bridge deck 40 ft wide needs ≥ 40); ``slope`` is the
    steepest terrain gradient to keep (ft/ft).
    """
    xyz = _xyz(obj)
    n = len(xyz)
    if n == 0:
        return np.zeros(0, dtype=bool)
    lo = xyz[:, :2].min(axis=0)
    ij = np.floor((xyz[:, :2] - lo) / cell).astype(int)
    ncol = ij[:, 0].max() + 1
    nrow = ij[:, 1].max() + 1
    flat = ij[:, 1] * ncol + ij[:, 0]
    zmin = np.full(nrow * ncol, np.inf)
    np.minimum.at(zmin, flat, xyz[:, 2])
    zmin = zmin.reshape(nrow, ncol)
    empty = ~np.isfinite(zmin)
    if empty.any():
        _, (ri, ci) = ndimage.distance_transform_edt(empty, return_distances=True,
                                                    return_indices=True)
        zmin = zmin[ri, ci]
    surf = zmin.copy()
    w_cells = 1
    while True:
        w = 2 * w_cells + 1
        if (w - 1) * cell > max_window and w_cells > 1:
            break
        opened = ndimage.grey_opening(surf, size=(w, w), mode="nearest")
        dh = min(slope * (w - 1) * cell + initial_threshold, max_threshold)
        surf = np.where(surf - opened > dh, opened, surf)
        if (w - 1) * cell >= max_window:
            break
        w_cells *= 2
    thr = initial_threshold if final_threshold is None else final_threshold
    return (xyz[:, 2] - surf[ij[:, 1], ij[:, 0]]) <= thr


# ---------------------------------------------------------------------------
# clustering
# ---------------------------------------------------------------------------

def euclidean_clusters(obj: ArrayOrCloud, radius: float, min_points: int = 10,
                       max_pairs: int = 200_000_000) -> np.ndarray:
    """Connected-component labels (0..k-1, largest first; ``-1`` for
    points in clusters smaller than ``min_points``).

    Two points are linked when closer than ``radius``.  Pair enumeration is
    the memory cost (~16 bytes per pair); pick ``radius`` a little above
    the point spacing — 2–3× the voxel size is usual.
    """
    xyz = _xyz(obj)
    n = len(xyz)
    if n == 0:
        return np.zeros(0, dtype=int)
    tree = cKDTree(xyz)
    pairs = tree.query_pairs(radius, output_type="ndarray")
    if len(pairs) > max_pairs:
        raise MemoryError(f"{len(pairs):,} neighbour pairs at radius {radius}; "
                          "down-sample or reduce the radius")
    g = coo_matrix((np.ones(len(pairs), dtype=np.int8), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    _, labels = connected_components(g, directed=False)
    counts = np.bincount(labels)
    order = np.argsort(-counts)                      # rank by size
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))
    out = rank[labels]
    out[counts[labels] < min_points] = -1
    return out


def region_growing(obj: ArrayOrCloud, k: int = 16, angle: float = 8.0,
                   curvature: float = 0.03, min_points: int = 100,
                   normals=None, max_regions: int = 500) -> np.ndarray:
    """Smoothness-constrained region growing (Rabbani et al. 2006).

    Seeds are taken in order of increasing curvature; a neighbour joins the
    region when the angle between its normal and the *current* point's
    normal is below ``angle`` degrees, and it becomes a new seed when its
    curvature is below ``curvature``.  Returns labels like
    :func:`euclidean_clusters` (``-1`` = unassigned / too small).
    """
    xyz = _xyz(obj)
    n = len(xyz)
    if n == 0:
        return np.zeros(0, dtype=int)
    k = int(min(k, n))
    tree = cKDTree(xyz)
    nn, curv, _ = local_pca(xyz, k=k, tree=tree)
    if normals is not None:
        nn = np.asarray(normals, dtype=float)
    elif isinstance(obj, PointCloud) and obj.normals is not None:
        nn = np.asarray(obj.normals, dtype=float)
    _, nbr = tree.query(xyz, k=k, workers=-1)          # (n, k) including self
    cos_thr = np.cos(np.radians(angle))
    labels = np.full(n, -1, dtype=int)
    order = np.argsort(curv)
    region = 0
    for s in order:
        if labels[s] >= 0:
            continue
        if region >= max_regions:
            break
        labels[s] = region
        seeds = np.array([s])
        members = [s]
        while len(seeds):
            cand = nbr[seeds]                                   # (m, k)
            src = np.repeat(seeds, cand.shape[1])
            cand = cand.ravel()
            fresh = labels[cand] < 0
            cand, src = cand[fresh], src[fresh]
            if len(cand) == 0:
                break
            smooth = np.abs(np.einsum("ij,ij->i", nn[cand], nn[src])) >= cos_thr
            cand = np.unique(cand[smooth])
            if len(cand) == 0:
                break
            labels[cand] = region
            members.append(cand)
            seeds = cand[curv[cand] < curvature]
        size = sum(np.size(m) for m in members)
        if size < min_points:
            labels[np.concatenate([np.atleast_1d(m) for m in members])] = -2
        else:
            region += 1
    labels[labels == -2] = -1
    if region == 0:
        return labels
    counts = np.bincount(labels[labels >= 0], minlength=region)
    order = np.argsort(-counts)
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))
    keep = labels >= 0
    labels[keep] = rank[labels[keep]]
    return labels


# ---------------------------------------------------------------------------
# slices
# ---------------------------------------------------------------------------

def slice_elevation(obj: ArrayOrCloud, z0: float, z1: float) -> np.ndarray:
    """Indices of points with ``z0 <= z <= z1``."""
    z = _xyz(obj)[:, 2]
    return np.nonzero((z >= z0) & (z <= z1))[0]


def slice_axis(obj: ArrayOrCloud, origin, direction, station: float,
               half_width: float = 0.5) -> np.ndarray:
    """Indices of points within ``half_width`` of the plane perpendicular
    to the XY ``direction`` at ``station`` ft from ``origin``."""
    xyz = _xyz(obj)
    o = np.asarray(origin, dtype=float)[:2]
    u = np.asarray(direction, dtype=float)[:2]
    u = u / np.linalg.norm(u)
    s = (xyz[:, :2] - o) @ u
    return np.nonzero(np.abs(s - station) <= half_width)[0]


def elevation_histogram(obj: ArrayOrCloud, bin_size: float = 0.5):
    """``(bin_edges, counts)`` of point elevations — the quickest way to
    see the ground, deck and soffit levels of a bridge scan."""
    z = _xyz(obj)[:, 2]
    if len(z) == 0:
        return np.zeros(1), np.zeros(0, dtype=int)
    edges = np.arange(np.floor(z.min()), np.ceil(z.max()) + bin_size, bin_size)
    counts, _ = np.histogram(z, bins=edges)
    return edges, counts


__all__ = ["PlaneModel", "CylinderModel", "fit_plane_lsq", "ransac_plane",
           "segment_planes", "ransac_cylinder", "segment_cylinders", "ground_mask",
           "euclidean_clusters", "region_growing", "slice_elevation", "slice_axis",
           "elevation_histogram"]
