#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Meshing: from points and fitted primitives to triangle meshes.

Two kinds of surface come out of a bridge scan and they want different
meshers:

* **Height-field-like** surfaces (ground, deck top, a single wall face)
  mesh cleanly by projecting onto their best plane and Delaunay-
  triangulating (:meth:`Mesh.delaunay`), dropping slivers longer than
  ``max_edge``; or by rasterising (:meth:`Mesh.from_grid`) when the cloud
  is huge.  Both are pure ``scipy``.
* **Closed / general** surfaces (a whole pier, a bearing) need a
  reconstruction that reasons about normals — :func:`poisson_mesh` and
  :func:`ball_pivot_mesh` wrap ``open3d`` (imported when called).

Fitted primitives are meshed exactly: :func:`plane_mesh` triangulates a
:class:`~civilpy.scan.features.PlaneFeature`'s boundary polygon and
:func:`cylinder_mesh` builds a capped tube for a
:class:`~civilpy.scan.features.CylinderFeature`.

:class:`Mesh` writes PLY / OBJ / STL without dependencies and converts to
``open3d``, ``rhino3dm`` and :class:`~civilpy.transportation.terrain.Terrain`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import numpy as np
from scipy import ndimage
from scipy.spatial import Delaunay

from civilpy.scan.cloud import PointCloud
from civilpy.scan.features import CylinderFeature, PlaneFeature, SubstructureUnit
from civilpy.scan.segment import fit_plane_lsq

ArrayOrCloud = Union[np.ndarray, PointCloud]


def _xyz(obj: ArrayOrCloud) -> np.ndarray:
    return obj.xyz if isinstance(obj, PointCloud) else np.asarray(obj, dtype=float)


@dataclass
class Mesh:
    """Triangle mesh: ``vertices`` (V, 3) float and ``faces`` (F, 3) int."""

    vertices: np.ndarray
    faces: np.ndarray
    name: str = ""
    layer: str = "Scan"
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        self.vertices = np.asarray(self.vertices, dtype=float).reshape(-1, 3)
        self.faces = np.asarray(self.faces, dtype=int).reshape(-1, 3)

    # -- properties -------------------------------------------------------

    @property
    def n_vertices(self) -> int:
        return len(self.vertices)

    @property
    def n_faces(self) -> int:
        return len(self.faces)

    @property
    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        if self.n_vertices == 0:
            return np.zeros(3), np.zeros(3)
        return self.vertices.min(axis=0), self.vertices.max(axis=0)

    def face_normals(self) -> np.ndarray:
        a, b, c = (self.vertices[self.faces[:, i]] for i in range(3))
        n = np.cross(b - a, c - a)
        L = np.linalg.norm(n, axis=1)
        return n / np.where(L > 0, L, 1)[:, None]

    def area(self) -> float:
        a, b, c = (self.vertices[self.faces[:, i]] for i in range(3))
        return float(0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum())

    def translated(self, offset) -> "Mesh":
        return Mesh(self.vertices + np.asarray(offset, dtype=float), self.faces.copy(),
                    name=self.name, layer=self.layer, meta=dict(self.meta))

    def edge_lengths(self) -> np.ndarray:
        v = self.vertices
        f = self.faces
        return np.column_stack([np.linalg.norm(v[f[:, 0]] - v[f[:, 1]], axis=1),
                                np.linalg.norm(v[f[:, 1]] - v[f[:, 2]], axis=1),
                                np.linalg.norm(v[f[:, 2]] - v[f[:, 0]], axis=1)])

    def drop_unused_vertices(self) -> "Mesh":
        used = np.unique(self.faces)
        remap = np.full(self.n_vertices, -1)
        remap[used] = np.arange(len(used))
        return Mesh(self.vertices[used], remap[self.faces], name=self.name,
                    layer=self.layer, meta=dict(self.meta))

    # -- constructors -----------------------------------------------------

    @classmethod
    def delaunay(cls, obj: ArrayOrCloud, plane=None, max_edge: Optional[float] = None,
                 name: str = "") -> "Mesh":
        """Triangulate points projected onto a plane.

        ``plane`` is ``(normal, d)`` or a :class:`PlaneFeature`; ``None``
        fits one by least squares (for ground use ``((0, 0, 1), 0)`` to
        force the XY projection).  Triangles with any edge longer than
        ``max_edge`` are discarded so the mesh stops at holes and at the
        cloud's real boundary rather than spanning them.
        """
        pts = _xyz(obj)
        if len(pts) < 3:
            raise ValueError("need at least three points to mesh")
        if plane is None:
            normal, _, _ = fit_plane_lsq(pts)
        elif isinstance(plane, PlaneFeature):
            normal = plane.normal
        else:
            normal = np.asarray(plane[0], dtype=float)
            normal = normal / np.linalg.norm(normal)
        helper = np.array([1.0, 0, 0]) if abs(normal[0]) < 0.9 else np.array([0, 1.0, 0])
        u = np.cross(normal, helper)
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)
        c = pts.mean(axis=0)
        uv = np.column_stack([(pts - c) @ u, (pts - c) @ v])
        tri = Delaunay(uv)
        faces = tri.simplices
        m = cls(pts, faces, name=name)
        if max_edge is not None:
            keep = (m.edge_lengths() <= max_edge).all(axis=1)
            m = cls(pts, faces[keep], name=name).drop_unused_vertices()
        # orient faces so their normal agrees with the plane normal
        flip = m.face_normals() @ normal < 0
        m.faces[flip] = m.faces[flip][:, [0, 2, 1]]
        return m

    @classmethod
    def from_grid(cls, obj: ArrayOrCloud, cell: float = 1.0, stat: str = "mean",
                  fill: bool = False, name: str = "") -> "Mesh":
        """Rasterise to a ``cell``-ft DEM (``stat`` = mean / min / max per
        cell) and mesh the grid — the fast path for big ground clouds.
        Empty cells are skipped unless ``fill`` copies the nearest value."""
        pts = _xyz(obj)
        if len(pts) == 0:
            raise ValueError("empty cloud")
        lo = pts[:, :2].min(axis=0)
        ix = np.floor((pts[:, 0] - lo[0]) / cell).astype(int)
        iy = np.floor((pts[:, 1] - lo[1]) / cell).astype(int)
        nx, ny = ix.max() + 1, iy.max() + 1
        flat = iy * nx + ix
        if stat == "mean":
            s = np.bincount(flat, weights=pts[:, 2], minlength=nx * ny)
            n = np.bincount(flat, minlength=nx * ny)
            z = np.where(n > 0, s / np.where(n > 0, n, 1), np.nan)
        elif stat in ("min", "max"):
            z = np.full(nx * ny, np.inf if stat == "min" else -np.inf)
            (np.minimum if stat == "min" else np.maximum).at(z, flat, pts[:, 2])
            z[~np.isfinite(z)] = np.nan
        else:
            raise ValueError("stat must be mean, min or max")
        z = z.reshape(ny, nx)
        if fill and np.isnan(z).any():
            _, (ri, ci) = ndimage.distance_transform_edt(np.isnan(z), return_distances=True,
                                                        return_indices=True)
            z = z[ri, ci]
        gx, gy = np.meshgrid(lo[0] + (np.arange(nx) + 0.5) * cell,
                             lo[1] + (np.arange(ny) + 0.5) * cell)
        verts = np.column_stack([gx.ravel(), gy.ravel(), z.ravel()])
        vid = np.arange(nx * ny).reshape(ny, nx)
        a = vid[:-1, :-1].ravel()
        b = vid[:-1, 1:].ravel()
        c = vid[1:, 1:].ravel()
        d = vid[1:, :-1].ravel()
        faces = np.vstack([np.column_stack([a, b, c]), np.column_stack([a, c, d])])
        ok = np.isfinite(verts[faces, 2]).all(axis=1)
        return cls(verts, faces[ok], name=name).drop_unused_vertices()

    # -- converters -------------------------------------------------------

    def to_open3d(self):  # pragma: no cover - optional dependency
        o3d = _import_open3d()
        m = o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(self.vertices),
                                      o3d.utility.Vector3iVector(self.faces))
        m.compute_vertex_normals()
        return m

    @classmethod
    def from_open3d(cls, m, name: str = "") -> "Mesh":  # pragma: no cover
        return cls(np.asarray(m.vertices), np.asarray(m.triangles), name=name)

    def to_rhino(self):  # pragma: no cover - optional dependency
        """A ``rhino3dm.Mesh`` (lazy import)."""
        import rhino3dm
        m = rhino3dm.Mesh()
        for v in self.vertices:
            m.Vertices.Add(float(v[0]), float(v[1]), float(v[2]))
        for f in self.faces:
            m.Faces.AddFace(int(f[0]), int(f[1]), int(f[2]))
        m.Normals.ComputeNormals()
        m.Compact()
        return m

    def to_terrain(self):
        """A :class:`~civilpy.transportation.terrain.Terrain` that answers
        ``elevation_at`` from this mesh (meant for ground / deck meshes)."""
        from civilpy.transportation.terrain import Terrain
        return Terrain(self.vertices, faces=self.faces)

    # -- writers ----------------------------------------------------------

    def save(self, path) -> Path:
        path = Path(path)
        ext = path.suffix.lower()
        if ext == ".ply":
            return self.write_ply(path)
        if ext == ".obj":
            return self.write_obj(path)
        if ext == ".stl":
            return self.write_stl(path)
        raise ValueError(f"unsupported mesh extension {ext!r}")

    def write_ply(self, path, binary: bool = True) -> Path:
        path = Path(path)
        header = ["ply", "format " + ("binary_little_endian" if binary else "ascii") + " 1.0",
                  f"element vertex {self.n_vertices}",
                  "property double x", "property double y", "property double z",
                  f"element face {self.n_faces}",
                  "property list uchar int vertex_indices", "end_header"]
        with open(path, "wb") as fh:
            fh.write(("\n".join(header) + "\n").encode("ascii"))
            if binary:
                fh.write(self.vertices.astype("<f8").tobytes())
                rec = np.empty(self.n_faces, dtype=[("n", "u1"), ("i", "<i4", (3,))])
                rec["n"] = 3
                rec["i"] = self.faces
                fh.write(rec.tobytes())
            else:
                np.savetxt(fh, self.vertices, fmt="%.6f")
                np.savetxt(fh, np.column_stack([np.full(self.n_faces, 3), self.faces]), fmt="%d")
        return path

    def write_obj(self, path) -> Path:
        path = Path(path)
        with open(path, "w", encoding="ascii") as fh:
            if self.name:
                fh.write(f"o {self.name}\n")
            for v in self.vertices:
                fh.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            for f in self.faces + 1:
                fh.write(f"f {f[0]} {f[1]} {f[2]}\n")
        return path

    def write_stl(self, path) -> Path:
        """Binary STL (float32 — write a locally-based mesh, not state plane)."""
        path = Path(path)
        n = self.face_normals().astype("<f4")
        tri = self.vertices[self.faces].astype("<f4")
        rec = np.zeros(self.n_faces, dtype=[("n", "<f4", (3,)), ("v", "<f4", (3, 3)),
                                            ("attr", "<u2")])
        rec["n"], rec["v"] = n, tri
        with open(path, "wb") as fh:
            fh.write(b"\0" * 80)
            fh.write(np.uint32(self.n_faces).tobytes())
            fh.write(rec.tobytes())
        return path


def _import_open3d():  # pragma: no cover
    try:
        import open3d as o3d
    except ImportError as exc:
        raise ImportError("this step needs 'open3d' (pip install open3d)") from exc
    return o3d


# ---------------------------------------------------------------------------
# primitive meshes
# ---------------------------------------------------------------------------

def polygon_triangles(loop: np.ndarray) -> np.ndarray:
    """Ear-clipping triangulation of a simple 2-D polygon (M, 2) → (M-2, 3)."""
    p = np.asarray(loop, dtype=float)
    n = len(p)
    if n < 3:
        return np.zeros((0, 3), dtype=int)
    idx = list(range(n))
    # ensure CCW
    area = 0.5 * (np.dot(p[:, 0], np.roll(p[:, 1], -1)) - np.dot(p[:, 1], np.roll(p[:, 0], -1)))
    if area < 0:
        idx.reverse()
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 10 * n:
        guard += 1
        m = len(idx)
        found = False
        for k in range(m):
            i0, i1, i2 = idx[(k - 1) % m], idx[k], idx[(k + 1) % m]
            a, b, c = p[i0], p[i1], p[i2]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-12:
                continue
            others = [j for j in idx if j not in (i0, i1, i2)]
            if others:
                q = p[others]
                d1 = (b[0] - a[0]) * (q[:, 1] - a[1]) - (b[1] - a[1]) * (q[:, 0] - a[0])
                d2 = (c[0] - b[0]) * (q[:, 1] - b[1]) - (c[1] - b[1]) * (q[:, 0] - b[0])
                d3 = (a[0] - c[0]) * (q[:, 1] - c[1]) - (a[1] - c[1]) * (q[:, 0] - c[0])
                if ((d1 > 0) & (d2 > 0) & (d3 > 0)).any():
                    continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            found = True
            break
        if not found:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return np.asarray(tris, dtype=int).reshape(-1, 3)


def plane_mesh(pf: PlaneFeature, use_boundary: bool = True) -> Mesh:
    """Mesh a plane feature: its alpha/convex boundary polygon when present
    (``use_boundary``), else the oriented bounding rectangle."""
    if use_boundary and pf.boundary is not None and len(pf.boundary) >= 3:
        loop = np.asarray(pf.boundary, dtype=float)
    else:
        loop = np.asarray(pf.corners, dtype=float)
    rel = loop - pf.centroid
    uv = np.column_stack([rel @ pf.u, rel @ pf.v])
    faces = polygon_triangles(uv)
    m = Mesh(loop, faces, name=pf.name or pf.role, layer=pf.layer,
             meta={"role": pf.role, "feature": "plane"})
    flip = m.face_normals() @ pf.normal < 0
    m.faces[flip] = m.faces[flip][:, [0, 2, 1]]
    return m


def cylinder_mesh(cf: CylinderFeature, segments: int = 32, capped: bool = True) -> Mesh:
    """A closed tube from ``cf.start`` to ``cf.end``."""
    axis = cf.axis / np.linalg.norm(cf.axis)
    helper = np.array([1.0, 0, 0]) if abs(axis[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = np.cross(axis, helper)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    ang = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    ring = np.outer(np.cos(ang), e1) + np.outer(np.sin(ang), e2)
    bottom = cf.start + cf.radius * ring
    top = cf.end + cf.radius * ring
    verts = np.vstack([bottom, top])
    i = np.arange(segments)
    j = (i + 1) % segments
    faces = np.vstack([np.column_stack([i, j, j + segments]),
                       np.column_stack([i, j + segments, i + segments])])
    if capped:
        cb, ct = len(verts), len(verts) + 1
        verts = np.vstack([verts, cf.start, cf.end])
        faces = np.vstack([faces, np.column_stack([np.full(segments, cb), j, i]),
                           np.column_stack([np.full(segments, ct), i + segments, j + segments])])
    return Mesh(verts, faces, name=cf.name or cf.role, layer=cf.layer,
                meta={"role": cf.role, "feature": "cylinder", "radius": cf.radius})


def box_mesh(unit: SubstructureUnit) -> Mesh:
    """The bounding box of a :class:`SubstructureUnit` as a closed mesh
    (``corners`` are bottom 0-3 then top 4-7, both counter-clockwise)."""
    c = np.asarray(unit.corners, dtype=float)
    faces = np.array([[0, 2, 1], [0, 3, 2],                 # bottom (facing down)
                      [4, 5, 6], [4, 6, 7],                 # top
                      [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                      [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    return Mesh(c, faces, name=unit.name or unit.role, layer=unit.layer,
                meta={"role": unit.role, "feature": "substructure", "height": unit.height})


# ---------------------------------------------------------------------------
# open3d reconstruction (lazy)
# ---------------------------------------------------------------------------

def poisson_mesh(cloud: PointCloud, depth: int = 9, k_normals: int = 16,
                 density_quantile: float = 0.02, name: str = "") -> Mesh:  # pragma: no cover
    """Screened Poisson reconstruction via ``open3d``; low-density vertices
    (below ``density_quantile``) are trimmed to remove the balloon
    Poisson wraps around open scans."""
    from civilpy.scan.preprocess import ensure_normals

    o3d = _import_open3d()
    cloud = ensure_normals(cloud, k=k_normals)
    pcd = cloud.to_open3d()
    mesh, dens = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=depth)
    dens = np.asarray(dens)
    if density_quantile > 0 and len(dens):
        mesh.remove_vertices_by_mask(dens < np.quantile(dens, density_quantile))
    return Mesh.from_open3d(mesh, name=name)


def ball_pivot_mesh(cloud: PointCloud, radii=(0.25, 0.5, 1.0), k_normals: int = 16,
                    name: str = "") -> Mesh:  # pragma: no cover
    """Ball-pivoting reconstruction via ``open3d`` (radii in ft, roughly
    1–4× the point spacing)."""
    from civilpy.scan.preprocess import ensure_normals

    o3d = _import_open3d()
    cloud = ensure_normals(cloud, k=k_normals)
    pcd = cloud.to_open3d()
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
        pcd, o3d.utility.DoubleVector(list(radii)))
    return Mesh.from_open3d(mesh, name=name)


def decimate(mesh: Mesh, target_faces: int) -> Mesh:  # pragma: no cover
    """Quadric decimation via ``open3d``."""
    m = mesh.to_open3d().simplify_quadric_decimation(int(target_faces))
    out = Mesh.from_open3d(m, name=mesh.name)
    out.layer, out.meta = mesh.layer, dict(mesh.meta)
    return out


__all__ = ["Mesh", "polygon_triangles", "plane_mesh", "cylinder_mesh", "box_mesh", "poisson_mesh",
           "ball_pivot_mesh", "decimate"]
