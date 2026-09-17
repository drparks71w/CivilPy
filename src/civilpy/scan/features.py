#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Geometric features extracted from a scan, and the bridge-specific
measurements built on them.

Feature records
---------------
:class:`PlaneFeature`, :class:`CylinderFeature`, :class:`LineFeature` and
:class:`PolylineFeature` are plain dataclasses of JSON-safe fields (plus
``numpy`` arrays for geometry) so a result can be serialised with
:meth:`to_dict` and re-drawn by :mod:`civilpy.scan.cad` later.  Each
carries a ``role`` label (``"deck"``, ``"abutment"``, ``"column"``, ...)
assigned by :func:`label_bridge_roles`, and a ``layer`` naming the Rhino
layer from :mod:`civilpy.structural.rhino_layers` it belongs on.

Measurements
------------
* :func:`plane_boundary` — alpha-shape (or convex) outline of a plane's
  inliers, as a closed 3-D polyline.  This is the "as-scanned" edge of a
  deck, wall or cap.
* :func:`intersect_planes` — the crease line where two faces meet (deck
  edge, wall corner).
* :func:`clearance_grid` — per-cell under-clearance: the largest vertical
  gap between ground/roadway below and structure above, i.e. SNBI
  ``B.RH.02`` minimum vertical underclearance measured everywhere at once.
* :func:`cross_section` — a station cut through the cloud as
  ``(offset, z)`` points for drawing a typical section.
* :func:`substructure_from_profile` — piers / abutments as
  :class:`SubstructureUnit` records found from the *lowest structure point
  per station* under the deck (a tower bent, masonry pier or wall pier is
  neither a plane nor a cylinder, but it always reaches far below the
  girders), and :func:`span_layout` — the span lengths between them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional, Union

import numpy as np
from scipy.spatial import ConvexHull, Delaunay

from civilpy.scan.cloud import PointCloud
from civilpy.scan.preprocess import principal_axes, to_axis_frame
from civilpy.scan.segment import (CylinderModel, PlaneModel, euclidean_clusters,
                                  fit_plane_lsq)
from civilpy.structural import rhino_layers as L

ArrayOrCloud = Union[np.ndarray, PointCloud]


def _xyz(obj: ArrayOrCloud) -> np.ndarray:
    return obj.xyz if isinstance(obj, PointCloud) else np.asarray(obj, dtype=float)


def _tolist(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (np.floating, np.integer)):
        return v.item()
    if isinstance(v, (list, tuple)):
        return [_tolist(x) for x in v]
    if isinstance(v, dict):
        return {k: _tolist(x) for k, x in v.items()}
    return v


# ---------------------------------------------------------------------------
# feature records
# ---------------------------------------------------------------------------

#: Layer per role — the scan-derived geometry lands on the same nested
#: Rhino layers civilpy's parametric writers use, so a scanned pier and a
#: designed pier stack in one model.  Scan-only roles (ground, unknown)
#: get a proposed ``Scan`` group.
LAYER_SCAN = "Scan"
LAYER_SCAN_GROUND = "Scan::Ground"
LAYER_SCAN_PLANES = "Scan::Planes"
LAYER_SCAN_CYLINDERS = "Scan::Cylinders"
LAYER_SCAN_EDGES = "Scan::Edges"
LAYER_SCAN_SECTIONS = "Scan::Sections"
LAYER_SCAN_CLEARANCE = "Scan::Clearance"
LAYER_SCAN_POINTS = "Scan::Points"
#: Proposed leaf for whole substructure units (a pier as scanned, before it
#: is decomposed into cap / columns / footing).
LAYER_SUB_PIERS = "Substructure::Piers"

ROLE_LAYERS = {
    "deck": L.LAYER_BRIDGE_DECK,
    "soffit": L.LAYER_GIRDERS,
    "barrier": L.LAYER_BARRIERS,
    "girder_web": L.LAYER_GIRDERS,
    "abutment": L.LAYER_SUB_BACKWALLS,
    "wingwall": L.LAYER_SUB_WINGWALLS,
    "pier_face": L.LAYER_SUB_CAPS,
    "cap": L.LAYER_SUB_CAPS,
    "column": L.LAYER_SUB_COLUMNS,
    "pile": L.LAYER_SUB_PILES,
    "pier": LAYER_SUB_PIERS,
    "truss": L.LAYER_TRUSS_CHORDS,
    "superstructure": L.LAYER_SUPERSTRUCTURE,
    "wall": LAYER_SCAN_PLANES,
    "ground": LAYER_SCAN_GROUND,
    "plane": LAYER_SCAN_PLANES,
    "cylinder": LAYER_SCAN_CYLINDERS,
    "edge": LAYER_SCAN_EDGES,
    "section": LAYER_SCAN_SECTIONS,
    "clearance": LAYER_SCAN_CLEARANCE,
}


def layer_for(role: str) -> str:
    return ROLE_LAYERS.get(role, LAYER_SCAN_PLANES)


@dataclass
class PlaneFeature:
    """A planar face: ``normal · x = d`` plus its in-plane extent.

    ``u``/``v`` are in-plane unit axes (``u`` along the longer extent),
    ``extent_u``/``extent_v`` are the corresponding lengths, ``corners``
    the oriented bounding rectangle (4, 3) and ``boundary`` the
    alpha-shape outline (closed, (M, 3)) when computed.
    """

    normal: np.ndarray
    d: float
    centroid: np.ndarray
    u: np.ndarray
    v: np.ndarray
    extent_u: float
    extent_v: float
    corners: np.ndarray
    n_points: int
    rms: float
    area: float
    boundary: Optional[np.ndarray] = None
    inliers: Optional[np.ndarray] = None
    role: str = "plane"
    name: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def tilt_deg(self) -> float:
        """Angle between the normal and vertical (0 = horizontal face)."""
        return float(np.degrees(np.arccos(np.clip(abs(self.normal[2]), 0, 1))))

    @property
    def orientation(self) -> str:
        t = self.tilt_deg
        return "horizontal" if t < 10 else ("vertical" if t > 80 else "sloped")

    @property
    def elevation(self) -> float:
        return float(self.centroid[2])

    @property
    def strike(self) -> np.ndarray:
        """Horizontal unit direction along the face (for vertical faces the
        wall direction; for horizontal faces ``u``)."""
        if self.orientation == "vertical":
            s = np.array([-self.normal[1], self.normal[0], 0.0])
        else:
            s = np.array([self.u[0], self.u[1], 0.0])
        n = np.linalg.norm(s)
        return s / n if n else np.array([1.0, 0, 0])

    @property
    def layer(self) -> str:
        return layer_for(self.role)

    def to_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if k not in ("inliers", "boundary")}
        d["tilt_deg"] = self.tilt_deg
        d["orientation"] = self.orientation
        d["layer"] = self.layer
        d["boundary_vertices"] = 0 if self.boundary is None else int(len(self.boundary))
        return _tolist(d)


@dataclass
class CylinderFeature:
    """A right circular cylinder segment from ``start`` to ``end``."""

    center: np.ndarray
    axis: np.ndarray
    radius: float
    start: np.ndarray
    end: np.ndarray
    n_points: int
    rms: float
    inliers: Optional[np.ndarray] = None
    role: str = "cylinder"
    name: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def length(self) -> float:
        return float(np.linalg.norm(self.end - self.start))

    @property
    def diameter(self) -> float:
        return 2.0 * self.radius

    @property
    def tilt_deg(self) -> float:
        """Angle between the axis and vertical (0 = plumb column)."""
        return float(np.degrees(np.arccos(np.clip(abs(self.axis[2]), 0, 1))))

    @property
    def layer(self) -> str:
        return layer_for(self.role)

    def to_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if k != "inliers"}
        d.update(length=self.length, diameter=self.diameter, tilt_deg=self.tilt_deg,
                 layer=self.layer)
        return _tolist(d)


@dataclass
class LineFeature:
    """A straight edge between two points."""

    start: np.ndarray
    end: np.ndarray
    role: str = "edge"
    name: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def length(self) -> float:
        return float(np.linalg.norm(self.end - self.start))

    @property
    def layer(self) -> str:
        return layer_for(self.role)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(length=self.length, layer=self.layer)
        return _tolist(d)


@dataclass
class PolylineFeature:
    """An open or closed 3-D polyline (boundary, section, profile)."""

    points: np.ndarray
    closed: bool = False
    role: str = "edge"
    name: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def length(self) -> float:
        p = np.asarray(self.points, dtype=float)
        if len(p) < 2:
            return 0.0
        seg = np.linalg.norm(np.diff(p, axis=0), axis=1).sum()
        if self.closed:
            seg += np.linalg.norm(p[0] - p[-1])
        return float(seg)

    @property
    def layer(self) -> str:
        return layer_for(self.role)

    def to_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if k != "points"}
        d.update(length=self.length, n_vertices=int(len(self.points)), layer=self.layer)
        return _tolist(d)


@dataclass
class SubstructureUnit:
    """A pier or abutment as a station range along the bridge axis.

    Found by :func:`substructure_from_profile`; geometry is the box the
    unit's points occupy in the axis frame (``station``/``offset``/``z``)
    plus the same box's ``corners`` (8, 3) in cloud coordinates.
    """

    station: float
    station_range: tuple[float, float]
    offset_range: tuple[float, float]
    z_bottom: float
    z_top: float
    n_points: int
    centroid: np.ndarray
    corners: np.ndarray
    inliers: Optional[np.ndarray] = None
    role: str = "pier"
    name: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def height(self) -> float:
        return float(self.z_top - self.z_bottom)

    @property
    def length(self) -> float:
        """Extent along the bridge axis."""
        return float(self.station_range[1] - self.station_range[0])

    @property
    def width(self) -> float:
        """Extent across the bridge axis."""
        return float(self.offset_range[1] - self.offset_range[0])

    @property
    def layer(self) -> str:
        return layer_for(self.role)

    def to_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if k != "inliers"}
        d.update(height=self.height, length=self.length, width=self.width, layer=self.layer)
        return _tolist(d)


# ---------------------------------------------------------------------------
# building features from segment models
# ---------------------------------------------------------------------------

def plane_axes(normal: np.ndarray, pts: np.ndarray, centroid: np.ndarray):
    """In-plane orthonormal ``(u, v)`` with ``u`` along the longest extent."""
    rel = pts - centroid
    rel = rel - np.outer(rel @ normal, normal)
    if len(rel) >= 2:
        _, _, vt = np.linalg.svd(rel, full_matrices=False)
        u = vt[0] - (vt[0] @ normal) * normal
    else:
        u = np.array([1.0, 0, 0]) if abs(normal[0]) < 0.9 else np.array([0, 1.0, 0])
        u = u - (u @ normal) * normal
    nu = np.linalg.norm(u)
    u = u / nu if nu > 1e-12 else np.cross(normal, [0, 0, 1.0])
    if u[int(np.argmax(np.abs(u)))] < 0:
        u = -u
    v = np.cross(normal, u)
    return u, v


def plane_feature(model: PlaneModel, xyz: np.ndarray, *, alpha: Optional[float] = None,
                  name: str = "") -> PlaneFeature:
    """Build a :class:`PlaneFeature` from a RANSAC :class:`PlaneModel` and
    the array its inliers index.  ``alpha`` (ft) requests an alpha-shape
    boundary; ``None`` uses the convex hull."""
    pts = np.asarray(xyz, dtype=float)[model.inliers]
    proj = pts - np.outer(pts @ model.normal - model.d, model.normal)
    c = proj.mean(axis=0)
    u, v = plane_axes(model.normal, proj, c)
    su = (proj - c) @ u
    sv = (proj - c) @ v
    umin, umax, vmin, vmax = su.min(), su.max(), sv.min(), sv.max()
    corners = np.array([c + a * u + b * v for a, b in
                        ((umin, vmin), (umax, vmin), (umax, vmax), (umin, vmax))])
    boundary, area = plane_boundary(proj, model.normal, c, u, v, alpha=alpha)
    return PlaneFeature(normal=model.normal.copy(), d=float(model.d), centroid=c, u=u, v=v,
                        extent_u=float(umax - umin), extent_v=float(vmax - vmin),
                        corners=corners, n_points=int(len(model.inliers)),
                        rms=float(model.rms), area=float(area), boundary=boundary,
                        inliers=model.inliers, name=name)


def merge_coplanar(planes: list[PlaneFeature], xyz: np.ndarray, *, angle: float = 3.0,
                   distance: float = 0.4, horizontal_only: bool = True,
                   alpha: Optional[float] = None) -> list[PlaneFeature]:
    """Merge plane features that lie in the same plane (normals within
    ``angle`` degrees, offsets within ``distance`` ft) into one feature
    re-fitted to the union of their inliers.

    RANSAC and the connectivity step fragment an open-deck bridge (ties
    with gaps) or a long deck into several coplanar pieces; merged, the
    deck reports its full length.  ``horizontal_only`` leaves vertical
    planes alone — two wingwalls on the same side of a straight bridge
    are coplanar but are not one wall.
    """
    planes = list(planes)
    cos_thr = np.cos(np.radians(angle))
    merged = True
    while merged:
        merged = False
        for i in range(len(planes)):
            a = planes[i]
            if horizontal_only and a.orientation != "horizontal":
                continue
            for j in range(i + 1, len(planes)):
                b = planes[j]
                if horizontal_only and b.orientation != "horizontal":
                    continue
                if abs(a.normal @ b.normal) < cos_thr:
                    continue
                # same side / same plane: project b's centroid onto a
                if abs((b.centroid - a.centroid) @ a.normal) > distance:
                    continue
                if a.inliers is None or b.inliers is None:
                    continue
                union = np.unique(np.concatenate([a.inliers, b.inliers]))
                normal, d, rms = fit_plane_lsq(xyz[union])
                pm = PlaneModel(normal=normal, d=d, inliers=union, rms=rms)
                new = plane_feature(pm, xyz, alpha=alpha, name=a.name)
                new.role, new.meta = a.role, {**a.meta, "merged_from": [a.name, b.name]}
                planes[i] = new
                del planes[j]
                merged = True
                break
            if merged:
                break
    return planes


def cylinder_feature(model: CylinderModel, name: str = "") -> CylinderFeature:
    return CylinderFeature(center=model.center.copy(), axis=model.axis.copy(),
                           radius=float(model.radius), start=model.start, end=model.end,
                           n_points=int(len(model.inliers)), rms=float(model.rms),
                           inliers=model.inliers, name=name)


# ---------------------------------------------------------------------------
# boundaries
# ---------------------------------------------------------------------------

def alpha_shape_edges(xy: np.ndarray, alpha: float) -> list[np.ndarray]:
    """Closed boundary loops (index arrays) of the 2-D alpha shape: keep
    Delaunay triangles with circumradius ``< alpha`` and chain the edges
    that belong to exactly one kept triangle.  Loops come largest first."""
    xy = np.asarray(xy, dtype=float)
    if len(xy) < 4:
        return [np.arange(len(xy))]
    tri = Delaunay(xy)
    s = tri.simplices
    a = xy[s[:, 0]]
    b = xy[s[:, 1]]
    c = xy[s[:, 2]]
    la = np.linalg.norm(b - c, axis=1)
    lb = np.linalg.norm(a - c, axis=1)
    lc = np.linalg.norm(a - b, axis=1)
    sp = (la + lb + lc) / 2
    area = np.sqrt(np.clip(sp * (sp - la) * (sp - lb) * (sp - lc), 0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        circ = np.where(area > 1e-12, la * lb * lc / (4 * area), np.inf)
    keep = s[circ < alpha]
    if len(keep) == 0:
        hull = ConvexHull(xy)
        return [hull.vertices]
    edges = np.vstack([keep[:, [0, 1]], keep[:, [1, 2]], keep[:, [2, 0]]])
    edges = np.sort(edges, axis=1)
    uniq, counts = np.unique(edges, axis=0, return_counts=True)
    boundary = uniq[counts == 1]
    # chain edges into loops
    adj: dict[int, list[int]] = {}
    for i, j in boundary:
        adj.setdefault(int(i), []).append(int(j))
        adj.setdefault(int(j), []).append(int(i))
    seen = set()
    loops = []
    for start in adj:
        if start in seen:
            continue
        loop = [start]
        seen.add(start)
        prev, cur = None, start
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            cur, prev = nxt[0], cur
            loop.append(cur)
            seen.add(cur)
        loops.append(np.asarray(loop))
    loops.sort(key=lambda lp: -_polygon_area(xy[lp]))
    return loops


def _polygon_area(p: np.ndarray) -> float:
    if len(p) < 3:
        return 0.0
    x, y = p[:, 0], p[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def plane_boundary(pts: np.ndarray, normal: np.ndarray, centroid: np.ndarray,
                   u: np.ndarray, v: np.ndarray, alpha: Optional[float] = None
                   ) -> tuple[np.ndarray, float]:
    """Outline of in-plane points as a closed ``(M, 3)`` loop and its area.
    ``alpha`` ft gives an alpha shape (concave, follows notches and
    openings' outer rim); ``None`` gives the convex hull."""
    pts = np.asarray(pts, dtype=float)
    rel = pts - centroid
    uv = np.column_stack([rel @ u, rel @ v])
    if len(uv) < 3:
        return pts.copy(), 0.0
    if alpha is None:
        hull = ConvexHull(uv)
        idx = hull.vertices
        area = float(hull.volume)
    else:
        idx = alpha_shape_edges(uv, alpha)[0]
        area = _polygon_area(uv[idx])
        if len(idx) < 3:
            hull = ConvexHull(uv)
            idx, area = hull.vertices, float(hull.volume)
    loop = centroid + np.outer(uv[idx, 0], u) + np.outer(uv[idx, 1], v)
    return loop, area


def simplify_polyline(points: np.ndarray, tolerance: float, closed: bool = False) -> np.ndarray:
    """Ramer–Douglas–Peucker simplification of a 2-D/3-D polyline."""
    p = np.asarray(points, dtype=float)
    if len(p) < 3:
        return p.copy()
    if closed:
        # split at the farthest point from p[0] so the loop becomes two open runs
        far = int(np.argmax(np.linalg.norm(p - p[0], axis=1)))
        a = simplify_polyline(p[:far + 1], tolerance)
        b = simplify_polyline(np.vstack([p[far:], p[:1]]), tolerance)
        return np.vstack([a[:-1], b[:-1]])
    keep = np.zeros(len(p), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(p) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        seg = p[j] - p[i]
        L = np.linalg.norm(seg)
        rel = p[i + 1:j] - p[i]
        if L == 0:
            dist = np.linalg.norm(rel, axis=1)
        else:
            t = np.clip(rel @ seg / (L * L), 0, 1)
            dist = np.linalg.norm(rel - np.outer(t, seg), axis=1)
        k = int(np.argmax(dist))
        if dist[k] > tolerance:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return p[keep]


def intersect_planes(a: PlaneFeature, b: PlaneFeature, clip: bool = True
                     ) -> Optional[LineFeature]:
    """The line where two planes meet, clipped to the overlap of their
    inlier extents along that line.  ``None`` when (near-)parallel or, with
    ``clip``, when the extents do not overlap."""
    direction = np.cross(a.normal, b.normal)
    L = np.linalg.norm(direction)
    if L < np.sin(np.radians(2.0)):
        return None
    direction /= L
    # a point on the line: solve [na; nb; dir] x = [da; db; dir·c]
    A = np.vstack([a.normal, b.normal, direction])
    rhs = np.array([a.d, b.d, direction @ (0.5 * (a.centroid + b.centroid))])
    p0 = np.linalg.solve(A, rhs)
    if not clip:
        return LineFeature(p0 - direction * 10, p0 + direction * 10)
    ta = (a.corners - p0) @ direction
    tb = (b.corners - p0) @ direction
    lo, hi = max(ta.min(), tb.min()), min(ta.max(), tb.max())
    if hi <= lo:
        return None
    return LineFeature(start=p0 + direction * lo, end=p0 + direction * hi,
                       meta={"planes": [a.name, b.name]})


# ---------------------------------------------------------------------------
# bridge-specific measurements
# ---------------------------------------------------------------------------

@dataclass
class ClearanceGrid:
    """Per-cell vertical gap between the lowest structure above and the
    highest ground / roadway below (see :func:`clearance_grid`)."""

    x_edges: np.ndarray
    y_edges: np.ndarray
    gap: np.ndarray          # (ny, nx) ft, NaN where no gap ≥ min_gap
    z_low: np.ndarray        # top of the lower body (ground / road / rail)
    z_high: np.ndarray       # underside of the upper body (soffit / beam)

    @property
    def valid(self) -> np.ndarray:
        return np.isfinite(self.gap)

    def min_clearance(self) -> Optional[dict]:
        """``{"clearance", "x", "y", "z_low", "z_high"}`` at the tightest
        cell, or ``None`` when no cell has two bodies."""
        if not self.valid.any():
            return None
        j, i = np.unravel_index(np.nanargmin(self.gap), self.gap.shape)
        return {
            "clearance": float(self.gap[j, i]),
            "x": float(0.5 * (self.x_edges[i] + self.x_edges[i + 1])),
            "y": float(0.5 * (self.y_edges[j] + self.y_edges[j + 1])),
            "z_low": float(self.z_low[j, i]),
            "z_high": float(self.z_high[j, i]),
        }

    def restrict_upper(self, z_min: float) -> "ClearanceGrid":
        """Invalidate cells whose upper body is below ``z_min`` — keeps
        only gaps closed by the superstructure underside, not by a tree
        canopy or a cable under the deck footprint."""
        bad = self.valid & (self.z_high < z_min)
        gap, lo, hi = self.gap.copy(), self.z_low.copy(), self.z_high.copy()
        gap[bad] = lo[bad] = hi[bad] = np.nan
        return ClearanceGrid(self.x_edges, self.y_edges, gap, lo, hi)

    def cell_centers(self) -> np.ndarray:
        """``(n_valid, 3)`` points at ``(x, y, z_high)`` for drawing."""
        j, i = np.nonzero(self.valid)
        x = 0.5 * (self.x_edges[i] + self.x_edges[i + 1])
        y = 0.5 * (self.y_edges[j] + self.y_edges[j + 1])
        return np.column_stack([x, y, self.z_high[j, i]])


def clearance_grid(obj: ArrayOrCloud, cell: float = 1.0, min_gap: float = 3.0,
                   min_support: int = 4, support_depth: float = 0.5,
                   bbox=None, footprint=None) -> ClearanceGrid:
    """Vertical under-clearance everywhere at once.

    Points are binned on a ``cell`` × ``cell`` XY grid and sorted by
    elevation; within each cell every jump between consecutive elevations
    of at least ``min_gap`` ft is a candidate clearance, its lower end the
    top of ground / roadway / rail and its upper end the underside of the
    structure.  A candidate counts only when both ends are *surfaces* —
    at least ``min_support`` points within ``support_depth`` ft above the
    upper end and below the lower end — which rejects the voids between
    stray points at a column edge, in vegetation or along a cable.  The
    largest supported gap wins; cells with none are NaN.  ``min_gap``
    should exceed the girder depth so the deck-to-soffit gap is never
    mistaken for clearance.

    With a 0.25 ft working voxel a 1 ft cell of surface holds ~16 points,
    so ``min_support=4`` is conservative; coarsen ``cell`` for sparser
    clouds.  ``footprint`` (an XY polygon such as the deck boundary)
    restricts the search to the structure, so a tree canopy on the
    approach cannot report as a 4 ft clearance.
    """
    import pandas as pd

    xyz = _xyz(obj)
    if bbox is not None:
        xmin, ymin, xmax, ymax = bbox
        m = ((xyz[:, 0] >= xmin) & (xyz[:, 0] <= xmax) &
             (xyz[:, 1] >= ymin) & (xyz[:, 1] <= ymax))
        xyz = xyz[m]
    if footprint is not None and len(xyz):
        from matplotlib.path import Path as MplPath
        poly = np.asarray(footprint, dtype=float)[:, :2]
        xyz = xyz[MplPath(poly).contains_points(xyz[:, :2])]
    if len(xyz) == 0:
        e = np.zeros(1)
        z = np.zeros((0, 0))
        return ClearanceGrid(e, e, z, z, z)
    lo = xyz[:, :2].min(axis=0)
    hi = xyz[:, :2].max(axis=0)
    nx = int(np.floor((hi[0] - lo[0]) / cell)) + 1
    ny = int(np.floor((hi[1] - lo[1]) / cell)) + 1
    ix = np.floor((xyz[:, 0] - lo[0]) / cell).astype(int)
    iy = np.floor((xyz[:, 1] - lo[1]) / cell).astype(int)
    flat = iy * nx + ix
    order = np.lexsort((xyz[:, 2], flat))
    fs, zs = flat[order], xyz[order, 2]
    zmin = zs.min()
    zspan = (zs.max() - zmin) + 2 * support_depth + 1.0
    keys = fs * zspan + (zs - zmin)                 # sorted, cell-major then z
    same = fs[1:] == fs[:-1]
    dz = np.where(same, zs[1:] - zs[:-1], -np.inf)
    cand = np.nonzero(np.isfinite(dz) & (dz >= min_gap))[0]
    gap = np.full(nx * ny, np.nan)
    zlo = np.full(nx * ny, np.nan)
    zhi = np.full(nx * ny, np.nan)
    if len(cand):
        c_cell = fs[cand]
        c_lo, c_hi = zs[cand], zs[cand + 1]
        base = c_cell * zspan - zmin
        above = (np.searchsorted(keys, base + c_hi + support_depth, side="right")
                 - np.searchsorted(keys, base + c_hi, side="left"))
        below = (np.searchsorted(keys, base + c_lo, side="right")
                 - np.searchsorted(keys, base + c_lo - support_depth, side="left"))
        ok = (above >= min_support) & (below >= min_support)
        df = pd.DataFrame({"cell": c_cell[ok], "dz": dz[cand][ok],
                           "zlo": c_lo[ok], "zhi": c_hi[ok]})
        if len(df):
            best = df.loc[df.groupby("cell")["dz"].idxmax()]
            gap[best["cell"].to_numpy()] = best["dz"].to_numpy()
            zlo[best["cell"].to_numpy()] = best["zlo"].to_numpy()
            zhi[best["cell"].to_numpy()] = best["zhi"].to_numpy()
    x_edges = lo[0] + cell * np.arange(nx + 1)
    y_edges = lo[1] + cell * np.arange(ny + 1)
    return ClearanceGrid(x_edges, y_edges, gap.reshape(ny, nx),
                         zlo.reshape(ny, nx), zhi.reshape(ny, nx))


def cross_section(obj: ArrayOrCloud, origin, direction, station: float,
                  half_width: float = 0.5) -> np.ndarray:
    """``(offset, z)`` points of a slab of the cloud ``half_width`` either
    side of ``station`` along the XY axis ``origin``/``direction`` (left
    offset positive)."""
    sot = to_axis_frame(_xyz(obj), origin, direction)
    m = np.abs(sot[:, 0] - station) <= half_width
    return sot[m][:, 1:]


def section_envelope(section: np.ndarray, bin_size: float = 0.25, side: str = "top") -> np.ndarray:
    """Reduce a ``(offset, z)`` section to its top (or bottom) envelope
    polyline by binning on offset — the profile of a deck/rail surface or
    the underside of a superstructure."""
    if len(section) == 0:
        return np.zeros((0, 2))
    o = section[:, 0]
    b = np.floor((o - o.min()) / bin_size).astype(int)
    n = b.max() + 1
    z = np.full(n, -np.inf if side == "top" else np.inf)
    (np.maximum if side == "top" else np.minimum).at(z, b, section[:, 1])
    ok = np.isfinite(z)
    x = o.min() + (np.arange(n) + 0.5) * bin_size
    return np.column_stack([x[ok], z[ok]])


def longitudinal_profile(obj: ArrayOrCloud, origin, direction, half_width: float = 1.0,
                         bin_size: float = 1.0, side: str = "top") -> np.ndarray:
    """``(station, z)`` envelope along the axis within ``half_width`` of
    the centreline — the deck / rail profile grade line as scanned."""
    sot = to_axis_frame(_xyz(obj), origin, direction)
    m = np.abs(sot[:, 1]) <= half_width
    sec = sot[m][:, [0, 2]]
    return section_envelope(sec, bin_size, side)


def bridge_axis(obj: ArrayOrCloud, deck: Optional[PlaneFeature] = None):
    """``(origin_xy, direction_xy)`` of the bridge: the deck plane's long
    axis when a deck was found, else the principal axis of the cloud."""
    if deck is not None:
        u = deck.u[:2]
        n = np.linalg.norm(u)
        if n > 1e-9:
            u = u / n
            if u[int(np.argmax(np.abs(u)))] < 0:
                u = -u
            return deck.centroid[:2].copy(), u
    return principal_axes(_xyz(obj))


# ---------------------------------------------------------------------------
# substructure units and span layout
# ---------------------------------------------------------------------------

def substructure_from_profile(xyz: np.ndarray, mask: np.ndarray, deck: PlaneFeature,
                              origin, direction, *, bin_size: float = 2.0,
                              margin: float = 5.0, min_drop: float = 4.0,
                              min_points: int = 50, min_bin_points: int = 5,
                              end_tolerance: float = 12.0, cluster_radius: float = 1.0,
                              ground_clearance: float = 3.0, min_length: float = 1.0
                              ) -> tuple[list[SubstructureUnit], dict]:
    """Find piers and abutments from the lowest-structure-point profile.

    Within the deck corridor (deck width plus ``margin`` each side, deck
    station range plus ``end_tolerance``) the non-ground points below the
    deck are binned by station; over a span the lowest point is the
    girder / truss underside, at a substructure unit it is the ground.
    ``mask`` marks structure (non-ground) points; the *other* points are
    taken as ground, and structure within ``ground_clearance`` ft of the
    highest ground in a station bin is ignored — brush, riprap and rock
    the ground filter left behind are not part of the bridge, while a
    pier continues far above them.  A unit's ``z_bottom`` is the lowest
    ground it stands on when ground was seen there.
    Stations with at least ``min_bin_points`` points deeper than the
    typical superstructure depth ``D`` (the 40th percentile of the
    lowest-point profile) by more than ``max(min_drop, 0.25 D)``, *and*
    with those deep points spanning at least ``min_drop`` vertically, are
    substructure — a stray point (a bird, a leaf) or a patch of ground the
    ground filter missed is not a pier, but a column, tower leg or
    masonry shaft is continuous from the girders down; contiguous runs
    (1-bin gaps allowed) become :class:`SubstructureUnit` records holding
    the points below ``deck - D`` in that run.  Units within
    ``end_tolerance`` of either deck end are ``"abutment"``, the rest
    ``"pier"``.

    Returns ``(units, info)`` where ``info`` carries the superstructure
    depth, the deck station range and the profile arrays for plotting.
    """
    sot = to_axis_frame(xyz, origin, direction)
    deck_s = (deck.corners[:, :2] - np.asarray(origin, float)) @ np.asarray(direction, float)
    s_lo, s_hi = float(deck_s.min()), float(deck_s.max())
    half_w = 0.5 * deck.extent_v + margin
    deck_z = deck.elevation
    in_corridor = ((np.abs(sot[:, 1]) <= half_w) & (sot[:, 2] < deck_z - 0.5)
                   & (sot[:, 0] >= s_lo - end_tolerance) & (sot[:, 0] <= s_hi + end_tolerance))
    s0 = s_lo - end_tolerance
    nb = int(np.floor((s_hi + end_tolerance - s0) / bin_size)) + 1
    # ground surface per station bin: the highest ground point in the corridor
    ground_hi = np.full(nb, -np.inf)
    ground_lo = np.full(nb, np.inf)
    g_idx = np.nonzero(in_corridor & ~mask)[0]
    if len(g_idx):
        gb = np.clip(np.floor((sot[g_idx, 0] - s0) / bin_size).astype(int), 0, nb - 1)
        np.maximum.at(ground_hi, gb, sot[g_idx, 2])
        np.minimum.at(ground_lo, gb, sot[g_idx, 2])
    corridor = in_corridor & mask
    idx = np.nonzero(corridor)[0]
    info = {"superstructure_depth": None, "deck_station_range": (s_lo, s_hi),
            "profile_station": np.zeros(0), "profile_depth": np.zeros(0),
            "ground_station_z": ground_lo}
    if len(idx) < min_points:
        return [], info
    b = np.clip(np.floor((sot[idx, 0] - s0) / bin_size).astype(int), 0, nb - 1)
    if len(g_idx):
        floor_z = np.where(np.isfinite(ground_hi), ground_hi + ground_clearance, -np.inf)
        above = sot[idx, 2] > floor_z[b]
        idx, b = idx[above], b[above]
        if len(idx) < min_points:
            return [], info
    # structure bottom per station: the lowest 0.5 ft elevation slab holding
    # at least min_bin_points — a stray speck below the girders is ignored
    z_all = sot[idx, 2]
    zb = np.floor((z_all - z_all.min()) / 0.5).astype(int)
    nz = zb.max() + 1
    occ = np.bincount(b * nz + zb, minlength=nb * nz).reshape(nb, nz) >= min_bin_points
    have = occ.any(axis=1)
    lowest = np.where(have, occ.argmax(axis=1), 0)
    zmin = np.where(have, z_all.min() + lowest * 0.5, np.inf)
    depth = np.where(have, deck_z - zmin, np.nan)
    stations = s0 + (np.arange(nb) + 0.5) * bin_size
    info["profile_station"], info["profile_depth"] = stations, depth
    if have.sum() < 3:
        return [], info
    D = float(np.nanpercentile(depth, 40))
    info["superstructure_depth"] = D
    drop = D + max(min_drop, 0.25 * D)
    deep_m = z_all < deck_z - drop
    deep = np.bincount(b[deep_m], minlength=nb)
    z_hi = np.full(nb, -np.inf)
    z_lo = np.full(nb, np.inf)
    np.maximum.at(z_hi, b[deep_m], z_all[deep_m])
    np.minimum.at(z_lo, b[deep_m], z_all[deep_m])
    is_unit = have & (deep >= min_bin_points) & ((z_hi - z_lo) >= min_drop)
    # contiguous runs, bridging single-bin gaps
    runs = []
    i = 0
    while i < nb:
        if not is_unit[i]:
            i += 1
            continue
        j = i
        while j + 1 < nb and (is_unit[j + 1] or (j + 2 < nb and is_unit[j + 2])):
            j += 1
        runs.append((i, j))
        i = j + 1
    units: list[SubstructureUnit] = []
    u_dir = np.asarray(direction, float)
    n_dir = np.array([-u_dir[1], u_dir[0]])
    o = np.asarray(origin, float)
    for i, j in runs:
        sel = idx[(b >= i) & (b <= j) & (sot[idx, 2] < deck_z - D)]
        if len(sel) < min_points:
            continue
        labels = euclidean_clusters(xyz[sel], radius=cluster_radius, min_points=1)
        keep = np.zeros(len(sel), dtype=bool)
        for lab in range(labels.max() + 1):
            m = labels == lab
            zc = sot[sel[m], 2]
            if zc.max() - zc.min() >= min_drop:
                keep |= m
        sel = sel[keep]
        if len(sel) < min_points:
            continue
        k = len(units)
        ss, tt, zz = sot[sel, 0], sot[sel, 1], sot[sel, 2]
        s0, s1 = float(ss.min()), float(ss.max())
        if s1 - s0 < min_length:
            continue
        t0, t1 = float(tt.min()), float(tt.max())
        z0, z1 = float(zz.min()), float(zz.max())
        g_here = ground_lo[i:j + 1]
        if np.isfinite(g_here).any():
            z0 = min(z0, float(np.nanmin(np.where(np.isfinite(g_here), g_here, np.nan))))
        corners = []
        for z in (z0, z1):
            for sa, ta in ((s0, t0), (s1, t0), (s1, t1), (s0, t1)):
                xy = o + sa * u_dir + ta * n_dir
                corners.append([xy[0], xy[1], z])
        centre = 0.5 * (s0 + s1)
        near_end = centre - s_lo < end_tolerance or s_hi - centre < end_tolerance
        units.append(SubstructureUnit(
            station=centre, station_range=(s0, s1), offset_range=(t0, t1),
            z_bottom=z0, z_top=z1, n_points=int(len(sel)), centroid=xyz[sel].mean(axis=0),
            corners=np.asarray(corners), inliers=sel,
            role="abutment" if near_end else "pier", name=f"unit_{k:02d}"))
    return units, info


def span_clearances(spans: list[dict], grid: ClearanceGrid, origin, direction) -> list[dict]:
    """Add ``min_clearance`` (and its ``clearance_z_low`` / ``z_high``) to
    each span dict from the clearance cells whose centre station falls in
    that span; ``None`` where no supported gap exists (a span over open
    water that was not scanned)."""
    if not grid.valid.any():
        for sp in spans:
            sp["min_clearance"] = None
        return spans
    centres = grid.cell_centers()
    st = to_axis_frame(centres, origin, direction)[:, 0]
    j, i = np.nonzero(grid.valid)
    gaps, lows = grid.gap[j, i], grid.z_low[j, i]
    highs = grid.z_high[j, i]
    for sp in spans:
        m = (st >= sp["start_station"]) & (st <= sp["end_station"])
        if m.any():
            k = int(np.argmin(gaps[m]))
            sp["min_clearance"] = float(gaps[m][k])
            sp["clearance_z_low"] = float(lows[m][k])
            sp["clearance_z_high"] = float(highs[m][k])
        else:
            sp["min_clearance"] = None
    return spans


def span_layout(units: list[SubstructureUnit], deck_station_range: tuple[float, float]
                ) -> list[dict]:
    """Spans between consecutive substructure units — pier centre to pier
    centre, and to the *inside face* of an abutment unit (its wingwalls
    extend the unit away from the span) — closed at the deck ends when no
    abutment unit was found there."""
    s_lo, s_hi = deck_station_range
    mid = 0.5 * (s_lo + s_hi)
    stations = []
    for u in units:
        if u.role == "abutment":
            stations.append(u.station_range[1] if u.station < mid else u.station_range[0])
        else:
            stations.append(u.station)
    stations.sort()
    if not stations or stations[0] - s_lo > 1.0:
        stations = [s_lo] + stations
    if s_hi - stations[-1] > 1.0:
        stations = stations + [s_hi]
    spans = []
    for i in range(len(stations) - 1):
        spans.append({"span": i + 1, "start_station": float(stations[i]),
                      "end_station": float(stations[i + 1]),
                      "length": float(stations[i + 1] - stations[i])})
    return spans


# ---------------------------------------------------------------------------
# bridge-role labelling
# ---------------------------------------------------------------------------

def label_bridge_roles(planes: list[PlaneFeature], cylinders: list[CylinderFeature],
                       ground_z: Optional[float] = None, axis=None,
                       min_deck_area: float = 200.0, corridor: float = 15.0
                       ) -> tuple[np.ndarray, np.ndarray]:
    """Assign ``role`` labels in place using simple, explainable rules and
    return the bridge ``(origin_xy, direction_xy)`` used.

    * **deck** — the largest horizontal plane (area ≥ ``min_deck_area``)
      above ground; **soffit** — horizontal planes below the deck and above
      ground with the same footprint direction; **cap** — smaller
      horizontal planes under the soffit.
    * Vertical planes: **abutment** when the wall runs roughly *across* the
      bridge axis (within 30°) and its footprint sits near either end;
      **pier_face** when across the axis mid-span; **wingwall** /
      **girder_web** / **barrier** / **truss** when *along* the axis,
      split by height relative to the deck (a barrier sits within 6 ft
      above the deck; anything higher over the deck footprint is a
      through-truss member).  Vertical planes outside the deck corridor
      (``corridor`` ft beyond the deck edge) are plain **wall**s — rock
      cuts, buildings, retaining walls on the approaches.
    * Cylinders: **column** when radius ≥ 0.75 ft, **pile** otherwise
      (both require a near-vertical axis; others stay ``"cylinder"``).
    """
    horiz = [p for p in planes if p.orientation == "horizontal"]
    deck = None
    if horiz:
        cands = [p for p in horiz if p.area >= min_deck_area and
                 (ground_z is None or p.elevation > ground_z + 3.0)]
        if cands:
            deck = max(cands, key=lambda p: p.area * (1 + p.elevation / 1e6))
            # the deck is the highest of the big horizontal planes, not just the largest
            top = max(cands, key=lambda p: p.elevation)
            if top.area >= 0.5 * deck.area:
                deck = top
            deck.role = "deck"
    if axis is None:
        if deck is not None:
            origin, direction = bridge_axis(np.zeros((0, 3)), deck)
        else:
            allc = [p.centroid for p in planes] + [c.center for c in cylinders]
            if len(allc) >= 2:
                origin, direction = principal_axes(np.asarray(allc))
            else:
                origin, direction = np.zeros(2), np.array([1.0, 0.0])
    else:
        origin, direction = np.asarray(axis[0], float), np.asarray(axis[1], float)
        direction = direction / np.linalg.norm(direction)
    deck_z = deck.elevation if deck is not None else None
    half_w = (0.5 * deck.extent_v if deck is not None else 0.0) + corridor
    # extent of the structure along the axis, for end-vs-middle tests
    stations = []
    for p in planes:
        stations.append((p.corners[:, :2] - origin) @ direction)
    for c in cylinders:
        stations.append(np.array([(c.center[:2] - origin) @ direction]))
    if stations:
        s_all = np.concatenate(stations)
        s_min, s_max = float(s_all.min()), float(s_all.max())
    else:
        s_min, s_max = -1.0, 1.0
    span = max(s_max - s_min, 1e-9)

    for p in planes:
        if p is deck:
            continue
        if p.orientation == "horizontal":
            if ground_z is not None and p.elevation < ground_z + 1.0:
                p.role = "ground"
            elif deck_z is not None and p.elevation < deck_z - 0.5:
                p.role = "soffit" if (p.area >= 0.25 * deck.area) else "cap"
            else:
                p.role = "plane"
        elif p.orientation == "vertical":
            cosang = abs(p.strike[:2] @ direction)
            rel_xy = p.centroid[:2] - origin
            s_c = rel_xy @ direction
            t_c = rel_xy[0] * -direction[1] + rel_xy[1] * direction[0]
            rel = (s_c - s_min) / span
            near_end = rel < 0.15 or rel > 0.85
            if deck is not None and abs(t_c) > half_w:
                p.role = "wall"                    # off the structure entirely
            elif cosang < 0.5:                     # wall runs across the axis
                p.role = "abutment" if near_end else "pier_face"
            else:                                  # wall runs along the axis
                if deck_z is not None and p.centroid[2] > deck_z + 6.0:
                    p.role = "truss"
                elif deck_z is not None and p.centroid[2] > deck_z - 1.0:
                    p.role = "barrier"
                elif deck_z is not None and p.extent_v < 12.0 and p.centroid[2] > deck_z - 12.0 and not near_end:
                    p.role = "girder_web"
                else:
                    p.role = "wingwall"
        else:
            p.role = "plane"
    for c in cylinders:
        if c.tilt_deg <= 15.0:
            c.role = "column" if c.radius >= 0.75 else "pile"
        else:
            c.role = "cylinder"
    return origin, direction


__all__ = ["PlaneFeature", "CylinderFeature", "LineFeature", "PolylineFeature",
           "SubstructureUnit", "substructure_from_profile", "span_layout", "span_clearances",
           "LAYER_SUB_PIERS",
           "ClearanceGrid", "ROLE_LAYERS", "LAYER_SCAN", "layer_for", "plane_axes",
           "plane_feature", "cylinder_feature", "merge_coplanar", "alpha_shape_edges", "plane_boundary",
           "simplify_polyline", "intersect_planes", "clearance_grid", "cross_section",
           "section_envelope", "longitudinal_profile", "bridge_axis", "label_bridge_roles",
           "fit_plane_lsq"]
