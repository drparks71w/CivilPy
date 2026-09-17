#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Point-cloud conditioning: down-sampling, outlier removal, normals, crops.

Everything here is ``numpy`` + ``scipy.spatial.cKDTree``; nothing needs
``open3d``.  Functions accept either a :class:`~civilpy.scan.cloud.PointCloud`
or a bare ``(N, 3)`` array and return the same kind they were given (masks
and normals are returned as arrays).

Typical order for a bridge scan::

    cloud = read_las(path, voxel=0.25)              # streaming voxel grid
    cloud = remove_statistical_outliers(cloud)       # scanner speckle
    cloud = cloud.with_normals(estimate_normals(cloud, k=16))
"""

from __future__ import annotations

from typing import Optional, Union

import numpy as np
from scipy.spatial import cKDTree

from civilpy.scan.cloud import PointCloud, VoxelAccumulator

ArrayOrCloud = Union[np.ndarray, PointCloud]


def _xyz(obj: ArrayOrCloud) -> np.ndarray:
    return obj.xyz if isinstance(obj, PointCloud) else np.asarray(obj, dtype=float)


def _apply_mask(obj: ArrayOrCloud, mask: np.ndarray):
    return obj.select(mask) if isinstance(obj, PointCloud) else _xyz(obj)[mask]


# ---------------------------------------------------------------------------
# down-sampling
# ---------------------------------------------------------------------------

def voxel_downsample(obj: ArrayOrCloud, size: float) -> ArrayOrCloud:
    """Average points per ``size``-ft cubic voxel (attributes averaged,
    classification taken from the first point in each voxel)."""
    if isinstance(obj, PointCloud):
        acc = VoxelAccumulator(size, anchor=obj.xyz.min(axis=0) if len(obj) else (0, 0, 0))
        acc.add(obj.xyz, obj.intensity, obj.rgb, obj.classification)
        out = acc.result(origin=obj.origin.copy(), crs=obj.crs, source=obj.source)
        return out
    xyz = _xyz(obj)
    acc = VoxelAccumulator(size, anchor=xyz.min(axis=0) if len(xyz) else (0, 0, 0))
    acc.add(xyz)
    return acc.result().xyz


def random_downsample(obj: ArrayOrCloud, n: int, seed: Optional[int] = 0) -> ArrayOrCloud:
    """Keep a uniform random subset of ``n`` points (all if fewer)."""
    xyz = _xyz(obj)
    if len(xyz) <= n:
        return obj
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(len(xyz), size=n, replace=False))
    return _apply_mask(obj, idx)


# ---------------------------------------------------------------------------
# outlier removal
# ---------------------------------------------------------------------------

def statistical_outlier_mask(obj: ArrayOrCloud, k: int = 20,
                             std_ratio: float = 2.0) -> np.ndarray:
    """Boolean mask of points whose mean distance to their ``k`` nearest
    neighbours is within ``mean + std_ratio * std`` of the global
    distribution (the classic SOR filter)."""
    xyz = _xyz(obj)
    n = len(xyz)
    if n <= k:
        return np.ones(n, dtype=bool)
    tree = cKDTree(xyz)
    d, _ = tree.query(xyz, k=k + 1, workers=-1)
    mean_d = d[:, 1:].mean(axis=1)
    thresh = mean_d.mean() + std_ratio * mean_d.std()
    return mean_d <= thresh


def remove_statistical_outliers(obj: ArrayOrCloud, k: int = 20,
                                std_ratio: float = 2.0) -> ArrayOrCloud:
    """Drop statistical outliers (see :func:`statistical_outlier_mask`)."""
    return _apply_mask(obj, statistical_outlier_mask(obj, k, std_ratio))


def radius_outlier_mask(obj: ArrayOrCloud, radius: float, min_neighbors: int = 4) -> np.ndarray:
    """Boolean mask of points with at least ``min_neighbors`` others within
    ``radius`` (isolated speckle fails the test)."""
    xyz = _xyz(obj)
    if len(xyz) == 0:
        return np.zeros(0, dtype=bool)
    tree = cKDTree(xyz)
    counts = tree.query_ball_point(xyz, r=radius, return_length=True, workers=-1)
    return np.asarray(counts) - 1 >= min_neighbors


def remove_radius_outliers(obj: ArrayOrCloud, radius: float,
                           min_neighbors: int = 4) -> ArrayOrCloud:
    return _apply_mask(obj, radius_outlier_mask(obj, radius, min_neighbors))


# ---------------------------------------------------------------------------
# normals and local surface descriptors
# ---------------------------------------------------------------------------

def local_pca(xyz: np.ndarray, k: int = 16, radius: Optional[float] = None,
              chunk: int = 200_000, tree: Optional[cKDTree] = None):
    """Per-point PCA of the ``k``-neighbourhood (or all points within
    ``radius`` when given, capped at ``k``).

    Returns ``(normals, curvature, eigenvalues)`` where ``normals`` is the
    smallest-eigenvalue direction (unit, unoriented), ``curvature`` is
    ``λ0 / (λ0+λ1+λ2)`` (0 on a plane, ~1/3 in a volume), and
    ``eigenvalues`` is ``(N, 3)`` ascending.
    """
    xyz = np.asarray(xyz, dtype=float)
    n = len(xyz)
    k = int(min(max(k, 3), n))
    normals = np.zeros((n, 3))
    curvature = np.zeros(n)
    eig = np.zeros((n, 3))
    if n < 3:
        normals[:, 2] = 1.0
        return normals, curvature, eig
    tree = tree or cKDTree(xyz)
    for start in range(0, n, chunk):
        q = xyz[start:start + chunk]
        d, idx = tree.query(q, k=k, workers=-1,
                            distance_upper_bound=radius if radius else np.inf)
        if radius:
            valid = np.isfinite(d)
            idx = np.where(valid, idx, np.arange(start, start + len(q))[:, None])
            w = valid.astype(float)
        else:
            w = np.ones(idx.shape)
        nb = xyz[idx]                                   # (m, k, 3)
        cnt = w.sum(axis=1)[:, None]
        mean = (nb * w[:, :, None]).sum(axis=1) / cnt
        diff = (nb - mean[:, None, :]) * w[:, :, None]
        cov = np.einsum("mki,mkj->mij", diff, diff) / cnt[:, :, None]
        vals, vecs = np.linalg.eigh(cov)                # ascending
        normals[start:start + len(q)] = vecs[:, :, 0]
        eig[start:start + len(q)] = np.clip(vals, 0, None)
        total = np.clip(vals, 0, None).sum(axis=1)
        curvature[start:start + len(q)] = np.where(total > 0, np.clip(vals[:, 0], 0, None) / np.where(total > 0, total, 1), 0)
    return normals, curvature, eig


def estimate_normals(obj: ArrayOrCloud, k: int = 16, radius: Optional[float] = None,
                     orient: Optional[str] = "up") -> np.ndarray:
    """Unit normals by neighbourhood PCA.

    ``orient``: ``"up"`` flips so ``n_z >= 0`` (sensible for ground / deck
    surfaces), ``"outward"`` flips to point away from the cloud centroid
    (sensible for a single column or pier), ``None`` leaves PCA signs.
    """
    xyz = _xyz(obj)
    normals, _, _ = local_pca(xyz, k=k, radius=radius)
    if orient == "up":
        flip = normals[:, 2] < 0
        normals[flip] *= -1
    elif orient == "outward" and len(xyz):
        c = xyz.mean(axis=0)
        flip = np.einsum("ij,ij->i", normals, xyz - c) < 0
        normals[flip] *= -1
    return normals


def ensure_normals(cloud: PointCloud, k: int = 16) -> PointCloud:
    """Return ``cloud`` unchanged if it has normals, else with PCA normals."""
    if cloud.normals is not None:
        return cloud
    return cloud.with_normals(estimate_normals(cloud, k=k))


# ---------------------------------------------------------------------------
# crops and frames
# ---------------------------------------------------------------------------

def crop_bbox(obj: ArrayOrCloud, xmin=None, ymin=None, xmax=None, ymax=None,
              zmin=None, zmax=None) -> ArrayOrCloud:
    """Axis-aligned crop; any bound may be ``None``."""
    xyz = _xyz(obj)
    m = np.ones(len(xyz), dtype=bool)
    for i, (lo, hi) in enumerate(((xmin, xmax), (ymin, ymax), (zmin, zmax))):
        if lo is not None:
            m &= xyz[:, i] >= lo
        if hi is not None:
            m &= xyz[:, i] <= hi
    return _apply_mask(obj, m)


def crop_polygon(obj: ArrayOrCloud, polygon, zmin=None, zmax=None) -> ArrayOrCloud:
    """Keep points whose XY falls inside a closed polygon ``[(x, y), ...]``."""
    from matplotlib.path import Path as MplPath

    xyz = _xyz(obj)
    m = MplPath(np.asarray(polygon, dtype=float)).contains_points(xyz[:, :2])
    if zmin is not None:
        m &= xyz[:, 2] >= zmin
    if zmax is not None:
        m &= xyz[:, 2] <= zmax
    return _apply_mask(obj, m)


def crop_corridor(obj: ArrayOrCloud, start, end, half_width: float,
                  zmin=None, zmax=None) -> ArrayOrCloud:
    """Keep points within ``half_width`` of the XY segment ``start→end``
    (a bridge corridor along its axis)."""
    xyz = _xyz(obj)
    s = np.asarray(start, dtype=float)[:2]
    e = np.asarray(end, dtype=float)[:2]
    d = e - s
    L = np.linalg.norm(d)
    if L == 0:
        raise ValueError("start and end coincide")
    u = d / L
    rel = xyz[:, :2] - s
    along = rel @ u
    across = rel[:, 0] * -u[1] + rel[:, 1] * u[0]
    m = (along >= 0) & (along <= L) & (np.abs(across) <= half_width)
    if zmin is not None:
        m &= xyz[:, 2] >= zmin
    if zmax is not None:
        m &= xyz[:, 2] <= zmax
    return _apply_mask(obj, m)


def principal_axes(xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(centroid_xy, unit_direction_xy)`` of the longest horizontal extent
    — the natural "bridge axis" of a corridor-shaped scan.  The direction
    is signed so its larger component is positive."""
    xy = np.asarray(xyz, dtype=float)[:, :2]
    c = xy.mean(axis=0)
    _, _, vt = np.linalg.svd(xy - c, full_matrices=False)
    u = vt[0]
    if u[int(np.argmax(np.abs(u)))] < 0:
        u = -u
    return c, u


def to_axis_frame(xyz: np.ndarray, origin, direction) -> np.ndarray:
    """Express points as ``(station, offset, z)`` relative to an XY axis
    through ``origin`` with unit ``direction`` (left offset positive)."""
    xyz = np.asarray(xyz, dtype=float)
    o = np.asarray(origin, dtype=float)[:2]
    u = np.asarray(direction, dtype=float)[:2]
    u = u / np.linalg.norm(u)
    rel = xyz[:, :2] - o
    s = rel @ u
    t = rel[:, 0] * -u[1] + rel[:, 1] * u[0]
    return np.column_stack([s, t, xyz[:, 2]])


def from_axis_frame(sot: np.ndarray, origin, direction) -> np.ndarray:
    """Inverse of :func:`to_axis_frame`."""
    sot = np.asarray(sot, dtype=float)
    o = np.asarray(origin, dtype=float)[:2]
    u = np.asarray(direction, dtype=float)[:2]
    u = u / np.linalg.norm(u)
    n = np.array([-u[1], u[0]])
    xy = o + sot[:, [0]] * u + sot[:, [1]] * n
    return np.column_stack([xy, sot[:, 2]])


__all__ = ["voxel_downsample", "random_downsample", "statistical_outlier_mask",
           "remove_statistical_outliers", "radius_outlier_mask",
           "remove_radius_outliers", "local_pca", "estimate_normals",
           "ensure_normals", "crop_bbox", "crop_polygon", "crop_corridor",
           "principal_axes", "to_axis_frame", "from_axis_frame"]
