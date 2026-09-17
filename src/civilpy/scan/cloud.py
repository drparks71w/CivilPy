#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""The :class:`PointCloud` container and streaming point-cloud I/O.

Static scans of a bridge site are large — 170M to 330M points per file is
typical for a terrestrial survey — so every reader here works **chunk by
chunk** and applies its reductions (bounding-box clip, class filter,
every-*n*-th decimation, voxel grid) before the next chunk is loaded.
A 9 GB ``.las`` reduced to a 0.25 ft voxel grid comes out at a few million
points and fits comfortably alongside the rest of the pipeline.

Supported formats

* ``.las`` / ``.laz`` — :func:`read_las` / :func:`write_las` (lazy
  ``laspy``; ``laz`` needs the ``lazrs`` or ``laszip`` backend).
* ``.xyz`` / ``.txt`` / ``.csv`` — :func:`read_xyz` / :func:`write_xyz`:
  whitespace or comma rows of ``x y z [r g b] [intensity] ...``.
* ``.ply`` — :func:`read_ply` / :func:`write_ply`: ASCII or binary
  little-endian point clouds (no dependency).
* ``.pod`` — Bentley Pointools; closed format, **not** supported.  Export
  the scan to LAS from MicroStation before reading.

Coordinates are kept as ``float64`` and a :attr:`PointCloud.origin` records
any shift applied by :meth:`PointCloud.to_local`, so state-plane values
(``~1e7`` ft) can be worked on near the origin and written back out in
their original frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterator, Optional

import numpy as np

#: ASPRS standard point classes (LAS 1.2+), for readable ``classes=`` filters.
ASPRS_CLASSES = {
    0: "never classified", 1: "unclassified", 2: "ground",
    3: "low vegetation", 4: "medium vegetation", 5: "high vegetation",
    6: "building", 7: "low point (noise)", 9: "water", 10: "rail",
    11: "road surface", 13: "wire - guard", 14: "wire - conductor",
    15: "transmission tower", 17: "bridge deck", 18: "high noise",
}

Progress = Optional[Callable[[int, int], None]]


@dataclass
class PointCloud:
    """An ``(N, 3)`` point set with optional per-point attributes.

    Attributes
    ----------
    xyz : ndarray (N, 3) float64
        Coordinates in the working frame (world minus :attr:`origin`).
    intensity : ndarray (N,), optional
    rgb : ndarray (N, 3), optional
        Colour, in whatever range the source used (LAS uses 16-bit).
    classification : ndarray (N,) uint8, optional
    normals : ndarray (N, 3), optional
        Unit normals (see :func:`civilpy.scan.preprocess.estimate_normals`).
    origin : ndarray (3,)
        World-frame offset subtracted from ``xyz``; ``xyz + origin`` is the
        world coordinate.  Zero until :meth:`to_local` is called.
    crs : str, optional
        Human-readable CRS name / WKT parsed from the source, if any.
    source : str, optional
        Path the cloud was read from (provenance for reports).
    """

    xyz: np.ndarray
    intensity: Optional[np.ndarray] = None
    rgb: Optional[np.ndarray] = None
    classification: Optional[np.ndarray] = None
    normals: Optional[np.ndarray] = None
    origin: np.ndarray = field(default_factory=lambda: np.zeros(3))
    crs: Optional[str] = None
    source: Optional[str] = None

    def __post_init__(self):
        self.xyz = np.asarray(self.xyz, dtype=float)
        if self.xyz.ndim != 2 or self.xyz.shape[1] != 3:
            raise ValueError("xyz must be an (N, 3) array")
        self.origin = np.asarray(self.origin, dtype=float).reshape(3)
        n = len(self.xyz)
        for name in ("intensity", "rgb", "classification", "normals"):
            arr = getattr(self, name)
            if arr is not None:
                arr = np.asarray(arr)
                if len(arr) != n:
                    raise ValueError(f"{name} has {len(arr)} rows, xyz has {n}")
                setattr(self, name, arr)

    # -- basics -----------------------------------------------------------

    def __len__(self) -> int:
        return len(self.xyz)

    def __repr__(self) -> str:
        attrs = [k for k in ("intensity", "rgb", "classification", "normals")
                 if getattr(self, k) is not None]
        return (f"PointCloud({len(self):,} points, attrs={attrs}, "
                f"origin={self.origin.round(3).tolist()})")

    @property
    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """``(min_xyz, max_xyz)`` in the working frame."""
        if len(self) == 0:
            z = np.zeros(3)
            return z, z
        return self.xyz.min(axis=0), self.xyz.max(axis=0)

    @property
    def world_xyz(self) -> np.ndarray:
        """Coordinates with :attr:`origin` added back."""
        return self.xyz + self.origin

    def _attrs(self) -> dict:
        return {k: getattr(self, k) for k in
                ("intensity", "rgb", "classification", "normals")}

    def select(self, mask_or_index) -> "PointCloud":
        """A new cloud holding the rows picked by a boolean mask or index."""
        idx = np.asarray(mask_or_index)
        kw = {k: (v[idx] if v is not None else None) for k, v in self._attrs().items()}
        return PointCloud(self.xyz[idx], origin=self.origin.copy(), crs=self.crs,
                          source=self.source, **kw)

    def to_local(self, origin=None) -> "PointCloud":
        """Shift so the working frame is near zero (default: floor of the
        minimum corner).  Idempotent: calling again re-bases onto the
        accumulated :attr:`origin`."""
        if origin is None:
            lo = self.xyz.min(axis=0) if len(self) else np.zeros(3)
            origin = np.floor(lo)
        origin = np.asarray(origin, dtype=float).reshape(3)
        return replace(self, xyz=self.xyz - origin, origin=self.origin + origin)

    def to_world(self) -> "PointCloud":
        """Undo :meth:`to_local`."""
        return replace(self, xyz=self.xyz + self.origin, origin=np.zeros(3))

    def with_normals(self, normals) -> "PointCloud":
        return replace(self, normals=np.asarray(normals, dtype=float))

    @staticmethod
    def concat(clouds: list["PointCloud"]) -> "PointCloud":
        """Stack clouds (re-based onto the first cloud's origin).  An
        attribute is kept only if every input has it."""
        if not clouds:
            return PointCloud(np.zeros((0, 3)))
        base = clouds[0].origin
        xyz = np.vstack([c.xyz + (c.origin - base) for c in clouds])
        kw = {}
        for k in ("intensity", "rgb", "classification", "normals"):
            vals = [getattr(c, k) for c in clouds]
            kw[k] = np.concatenate(vals) if all(v is not None for v in vals) else None
        return PointCloud(xyz, origin=base.copy(), crs=clouds[0].crs,
                          source=clouds[0].source, **kw)

    # -- interop ----------------------------------------------------------

    def to_open3d(self):  # pragma: no cover - optional dependency
        """An ``open3d.geometry.PointCloud`` (lazy import)."""
        o3d = _import_open3d()
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(self.xyz)
        if self.rgb is not None:
            rgb = np.asarray(self.rgb, dtype=float)
            if rgb.max() > 1.0:
                rgb = rgb / (65535.0 if rgb.max() > 255 else 255.0)
            pcd.colors = o3d.utility.Vector3dVector(rgb)
        if self.normals is not None:
            pcd.normals = o3d.utility.Vector3dVector(self.normals)
        return pcd

    @classmethod
    def from_open3d(cls, pcd, origin=None) -> "PointCloud":  # pragma: no cover
        xyz = np.asarray(pcd.points)
        rgb = np.asarray(pcd.colors) if pcd.has_colors() else None
        nrm = np.asarray(pcd.normals) if pcd.has_normals() else None
        return cls(xyz, rgb=rgb, normals=nrm,
                   origin=np.zeros(3) if origin is None else origin)

    # -- writers ----------------------------------------------------------

    def save(self, path) -> Path:
        """Write by extension: ``.las``/``.laz``, ``.ply``, ``.xyz``/``.txt``."""
        path = Path(path)
        ext = path.suffix.lower()
        if ext in (".las", ".laz"):
            return write_las(self, path)
        if ext == ".ply":
            return write_ply(self, path)
        if ext in (".xyz", ".txt", ".csv"):
            return write_xyz(self, path)
        raise ValueError(f"unsupported point-cloud extension {ext!r}")


# ---------------------------------------------------------------------------
# reduction helpers used by the streaming readers
# ---------------------------------------------------------------------------

class VoxelAccumulator:
    """Running voxel-grid average over chunks of points.

    Each chunk is binned on a ``size``-ft cubic grid anchored at ``anchor``
    and merged into the running per-voxel sums, so the memory footprint
    scales with the number of *occupied voxels*, not the number of points
    read.  :meth:`result` returns the centroid (and mean attributes) of
    every voxel.  Voxel indices are packed into one ``int64`` key (21 bits
    per axis, ±1M voxels around ``anchor`` — ±260,000 ft at 0.25 ft), so
    merging is a 1-D ``np.unique`` and the anchor only needs to be *near*
    the data, not at its minimum.
    """

    _BITS = 21

    def __init__(self, size: float, anchor=(0.0, 0.0, 0.0)):
        if size <= 0:
            raise ValueError("voxel size must be positive")
        self.size = float(size)
        self.anchor = np.asarray(anchor, dtype=float).reshape(3)
        self._keys = np.zeros(0, dtype=np.int64)
        self._sum = np.zeros((0, 3))
        self._cnt = np.zeros(0, dtype=np.int64)
        self._attr_sum: dict[str, np.ndarray] = {}
        self._first_class: Optional[np.ndarray] = None
        self.n_points = 0

    def _pack(self, xyz: np.ndarray) -> np.ndarray:
        half = 1 << (self._BITS - 1)
        ijk = np.floor((xyz - self.anchor) / self.size).astype(np.int64) + half
        if (ijk < 0).any() or (ijk >= 2 * half).any():
            raise ValueError("points fall outside the packable voxel range "
                             "(more than 1M voxels from the anchor; use a larger "
                             "voxel or an anchor nearer the data)")
        return (ijk[:, 0] << (2 * self._BITS)) | (ijk[:, 1] << self._BITS) | ijk[:, 2]

    def add(self, xyz, intensity=None, rgb=None, classification=None) -> None:
        xyz = np.asarray(xyz, dtype=float)
        if len(xyz) == 0:
            return
        keys = self._pack(xyz)
        n_old = len(self._keys)
        uniq, inv = np.unique(np.concatenate([self._keys, keys]), return_inverse=True)
        inv = inv.ravel()
        m = len(uniq)
        new_sum = np.zeros((m, 3))
        new_cnt = np.zeros(m, dtype=np.int64)
        for col in range(3):
            new_sum[:, col] = (np.bincount(inv[:n_old], weights=self._sum[:, col], minlength=m)
                               + np.bincount(inv[n_old:], weights=xyz[:, col], minlength=m))
        new_cnt = (np.bincount(inv[:n_old], weights=self._cnt, minlength=m)
                   + np.bincount(inv[n_old:], minlength=m)).astype(np.int64)
        attrs = {}
        if intensity is not None:
            attrs["intensity"] = np.asarray(intensity, dtype=float).reshape(-1, 1)
        if rgb is not None:
            attrs["rgb"] = np.asarray(rgb, dtype=float).reshape(-1, 3)
        for name, arr in attrs.items():
            width = arr.shape[1]
            acc = np.zeros((m, width))
            old = self._attr_sum.get(name)
            for col in range(width):
                if old is not None:
                    acc[:, col] += np.bincount(inv[:n_old], weights=old[:, col], minlength=m)
                acc[:, col] += np.bincount(inv[n_old:], weights=arr[:, col], minlength=m)
            self._attr_sum[name] = acc
        if classification is not None:
            cls = np.full(m, 255, dtype=np.int16)
            if self._first_class is not None:
                cls[inv[:n_old]] = self._first_class
            fresh = cls[inv[n_old:]] == 255
            # assign in reverse so the first point seen per voxel wins
            cls[inv[n_old:][fresh][::-1]] = np.asarray(classification)[fresh][::-1]
            self._first_class = cls
        self._keys, self._sum, self._cnt = uniq, new_sum, new_cnt
        self.n_points += len(xyz)

    def __len__(self) -> int:
        return len(self._keys)

    def result(self, **cloud_kwargs) -> PointCloud:
        cnt = np.maximum(self._cnt, 1)[:, None]
        kw = {}
        if "intensity" in self._attr_sum:
            kw["intensity"] = (self._attr_sum["intensity"] / cnt).ravel()
        if "rgb" in self._attr_sum:
            kw["rgb"] = self._attr_sum["rgb"] / cnt
        if self._first_class is not None:
            kw["classification"] = self._first_class.astype(np.uint8)
        return PointCloud(self._sum / cnt, **kw, **cloud_kwargs)


def _bbox_mask(x, y, bbox) -> np.ndarray:
    xmin, ymin, xmax, ymax = bbox
    return (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)


class _ChunkReducer:
    """Applies the common reader options to each chunk and collects them."""

    def __init__(self, *, bbox=None, zrange=None, classes=None, every=1,
                 voxel=None, max_points=None, anchor=(0, 0, 0)):
        self.bbox, self.zrange, self.every = bbox, zrange, max(1, int(every))
        self.classes = None if classes is None else set(int(c) for c in classes)
        self.max_points = max_points
        self.acc = VoxelAccumulator(voxel, anchor) if voxel else None
        self.parts: list[dict] = []
        self.kept = 0
        self.seen = 0
        self._phase = 0

    def done(self) -> bool:
        return self.max_points is not None and self.acc is None and self.kept >= self.max_points

    def add(self, xyz, intensity=None, rgb=None, classification=None) -> None:
        n = len(xyz)
        keep = np.ones(n, dtype=bool)
        if self.bbox is not None:
            keep &= _bbox_mask(xyz[:, 0], xyz[:, 1], self.bbox)
        if self.zrange is not None:
            keep &= (xyz[:, 2] >= self.zrange[0]) & (xyz[:, 2] <= self.zrange[1])
        if self.classes is not None and classification is not None:
            keep &= np.isin(classification, list(self.classes))
        if self.every > 1:
            # continue the stride across chunk boundaries
            stride = np.zeros(n, dtype=bool)
            stride[(self.every - self._phase) % self.every::self.every] = True
            self._phase = (self._phase + n) % self.every
            keep &= stride
        self.seen += n
        idx = np.nonzero(keep)[0]
        if len(idx) == 0:
            return
        sub = lambda a: None if a is None else np.asarray(a)[idx]  # noqa: E731
        if self.acc is not None:
            self.acc.add(xyz[idx], sub(intensity), sub(rgb), sub(classification))
            self.kept = len(self.acc)
            return
        if self.max_points is not None:
            room = self.max_points - self.kept
            if room <= 0:
                return
            idx = idx[:room]
        self.parts.append({"xyz": xyz[idx], "intensity": sub(intensity),
                           "rgb": sub(rgb), "classification": sub(classification)})
        self.kept += len(idx)

    def result(self, **cloud_kwargs) -> PointCloud:
        if self.acc is not None:
            return self.acc.result(**cloud_kwargs)
        if not self.parts:
            return PointCloud(np.zeros((0, 3)), **cloud_kwargs)
        xyz = np.vstack([p["xyz"] for p in self.parts])
        kw = {}
        for k in ("intensity", "rgb", "classification"):
            vals = [p[k] for p in self.parts]
            kw[k] = np.concatenate(vals) if all(v is not None for v in vals) else None
        return PointCloud(xyz, **kw, **cloud_kwargs)


# ---------------------------------------------------------------------------
# LAS / LAZ
# ---------------------------------------------------------------------------

def _import_laspy():
    try:
        import laspy
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "reading LAS/LAZ needs 'laspy' (pip install civilpy[lidar] or "
            "pip install 'laspy[lazrs]')") from exc
    return laspy


def _import_open3d():  # pragma: no cover
    try:
        import open3d as o3d
    except ImportError as exc:
        raise ImportError("this step needs 'open3d' (pip install open3d)") from exc
    return o3d


def las_info(path) -> dict:
    """Header summary of a ``.las``/``.laz`` file without reading its points.

    Returns point count / format / version, bounds, scale/offset, the
    dimension names present, and the CRS name when one is stored.
    """
    laspy = _import_laspy()
    path = Path(path)
    with laspy.open(str(path)) as reader:
        h = reader.header
        crs_name = None
        try:
            crs = h.parse_crs()
            crs_name = crs.name if crs is not None else None
        except Exception:  # pragma: no cover - pyproj optional / odd VLRs
            crs_name = None
        return {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "version": f"{h.version.major}.{h.version.minor}",
            "point_format": int(h.point_format.id),
            "point_count": int(h.point_count),
            "mins": [float(v) for v in h.mins],
            "maxs": [float(v) for v in h.maxs],
            "scales": [float(v) for v in h.scales],
            "offsets": [float(v) for v in h.offsets],
            "dimensions": list(h.point_format.dimension_names),
            "has_rgb": "red" in h.point_format.dimension_names,
            "crs": crs_name,
            "vlrs": [(v.user_id, int(v.record_id)) for v in h.vlrs],
        }


def iter_las_chunks(path, chunk_size: int = 2_000_000) -> Iterator[dict]:
    """Yield ``{"xyz", "intensity", "rgb", "classification"}`` dicts per
    chunk of a ``.las``/``.laz`` file (world coordinates, float64)."""
    laspy = _import_laspy()
    with laspy.open(str(path)) as reader:
        has_rgb = "red" in reader.header.point_format.dimension_names
        for pts in reader.chunk_iterator(chunk_size):
            xyz = np.column_stack([np.asarray(pts.x, dtype=float),
                                   np.asarray(pts.y, dtype=float),
                                   np.asarray(pts.z, dtype=float)])
            rgb = None
            if has_rgb:
                rgb = np.column_stack([np.asarray(pts.red), np.asarray(pts.green),
                                       np.asarray(pts.blue)]).astype(np.uint16)
            yield {
                "xyz": xyz,
                "intensity": np.asarray(pts.intensity),
                "rgb": rgb,
                "classification": np.asarray(pts.classification, dtype=np.uint8),
            }


def read_las(path, *, bbox=None, zrange=None, classes=None, every: int = 1,
             voxel: Optional[float] = None, max_points: Optional[int] = None,
             chunk_size: int = 2_000_000, local: bool = True,
             progress: Progress = None) -> PointCloud:
    """Stream a ``.las``/``.laz`` file into a :class:`PointCloud`.

    Parameters
    ----------
    bbox : (xmin, ymin, xmax, ymax), optional
        World-frame clip applied per chunk.
    zrange : (zmin, zmax), optional
        Elevation clip.
    classes : iterable of int, optional
        Keep only these ASPRS classes (see :data:`ASPRS_CLASSES`).  Most
        static scans are unclassified (all 0), so leave ``None`` unless the
        vendor classified the file.
    every : int
        Keep every ``every``-th point (cheap decimation).
    voxel : float, optional
        Voxel-grid size in ft; points are averaged per voxel as they
        stream so memory scales with occupied voxels.  ``0.25`` ft is a
        good working density for bridge features; ``1.0`` for a site
        overview.
    max_points : int, optional
        Stop after this many kept points (ignored with ``voxel``).
    local : bool
        Shift onto a local origin at the file's floored minimum corner
        (recommended — state-plane values are ~1e7 ft).
    progress : callable ``(points_read, points_total)``, optional
    """
    laspy = _import_laspy()
    path = Path(path)
    with laspy.open(str(path)) as reader:
        total = int(reader.header.point_count)
        mins = np.asarray(reader.header.mins, dtype=float)
    info = las_info(path)
    anchor = np.floor(mins)
    red = _ChunkReducer(bbox=bbox, zrange=zrange, classes=classes, every=every,
                        voxel=voxel, max_points=max_points, anchor=anchor)
    for chunk in iter_las_chunks(path, chunk_size):
        red.add(chunk["xyz"], chunk["intensity"], chunk["rgb"], chunk["classification"])
        if progress is not None:
            progress(red.seen, total)
        if red.done():
            break
    cloud = red.result(crs=info["crs"], source=str(path))
    return cloud.to_local(anchor) if local and len(cloud) else cloud


def write_las(cloud: PointCloud, path, *, point_format: int = 2,
              scale: float = 0.001) -> Path:
    """Write a cloud (world frame) to ``.las``/``.laz`` with ``laspy``."""
    laspy = _import_laspy()
    path = Path(path)
    xyz = cloud.world_xyz
    header = laspy.LasHeader(point_format=point_format, version="1.2")
    header.scales = np.array([scale] * 3)
    header.offsets = np.floor(xyz.min(axis=0)) if len(xyz) else np.zeros(3)
    las = laspy.LasData(header)
    las.x, las.y, las.z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    if cloud.intensity is not None:
        las.intensity = np.clip(cloud.intensity, 0, 65535).astype(np.uint16)
    if cloud.classification is not None:
        las.classification = cloud.classification.astype(np.uint8)
    if cloud.rgb is not None and "red" in header.point_format.dimension_names:
        rgb = np.asarray(cloud.rgb, dtype=float)
        if rgb.size and rgb.max() <= 1.0:
            rgb = rgb * 65535
        elif rgb.size and rgb.max() <= 255:
            rgb = rgb * 257
        rgb = np.clip(rgb, 0, 65535).astype(np.uint16)
        las.red, las.green, las.blue = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    las.write(str(path))
    return path


# ---------------------------------------------------------------------------
# XYZ text
# ---------------------------------------------------------------------------

def read_xyz(path, *, columns: Optional[dict] = None, delimiter=None,
             skiprows: int = 0, bbox=None, zrange=None, every: int = 1,
             voxel: Optional[float] = None, max_points: Optional[int] = None,
             chunk_size: int = 1_000_000, local: bool = True,
             progress: Progress = None) -> PointCloud:
    """Stream a whitespace / CSV point file into a :class:`PointCloud`.

    ``columns`` maps attribute names to 0-based column indices, e.g.
    ``{"x": 0, "y": 1, "z": 2, "r": 3, "g": 4, "b": 5, "intensity": 6}``.
    When omitted the layout is inferred from the first row: 3 columns =
    xyz; 4 = xyz + intensity; 6+ = xyz + rgb (+ intensity in column 6).
    The other keyword arguments match :func:`read_las`.
    """
    import pandas as pd

    path = Path(path)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for _ in range(skiprows):
            fh.readline()
        first = fh.readline()
    sep = delimiter
    if sep is None:
        sep = "," if "," in first else r"\s+"
    ncol = len(first.replace(",", " ").split())
    if columns is None:
        columns = {"x": 0, "y": 1, "z": 2}
        if ncol == 4:
            columns["intensity"] = 3
        elif ncol >= 6:
            columns.update({"r": 3, "g": 4, "b": 5})
            if ncol >= 7:
                columns["intensity"] = 6
    has_rgb = all(k in columns for k in ("r", "g", "b"))
    has_int = "intensity" in columns

    size = path.stat().st_size
    red = None
    anchor = None
    bytes_seen = 0
    for chunk in pd.read_csv(path, sep=sep, header=None, skiprows=skiprows,
                             chunksize=chunk_size, engine="c",
                             dtype=float, comment="#"):
        vals = chunk.to_numpy()
        xyz = vals[:, [columns["x"], columns["y"], columns["z"]]]
        if red is None:
            anchor = np.floor(xyz.min(axis=0))
            red = _ChunkReducer(bbox=bbox, zrange=zrange, every=every,
                                voxel=voxel, max_points=max_points, anchor=anchor)
        rgb = vals[:, [columns["r"], columns["g"], columns["b"]]] if has_rgb else None
        inten = vals[:, columns["intensity"]] if has_int else None
        red.add(xyz, inten, rgb, None)
        if progress is not None:
            bytes_seen += int(chunk.memory_usage(index=False).sum())
            progress(min(bytes_seen, size), size)
        if red.done():
            break
    if red is None:
        return PointCloud(np.zeros((0, 3)), source=str(path))
    cloud = red.result(source=str(path))
    return cloud.to_local(anchor) if local and len(cloud) else cloud


def write_xyz(cloud: PointCloud, path, *, fmt: str = "%.4f",
              delimiter: str = " ") -> Path:
    """Write ``x y z [r g b] [intensity]`` rows (world frame)."""
    path = Path(path)
    cols = [cloud.world_xyz]
    fmts = [fmt] * 3
    if cloud.rgb is not None:
        cols.append(np.asarray(cloud.rgb, dtype=float))
        fmts += ["%g"] * 3
    if cloud.intensity is not None:
        cols.append(np.asarray(cloud.intensity, dtype=float)[:, None])
        fmts.append("%g")
    np.savetxt(path, np.hstack(cols), fmt=fmts, delimiter=delimiter)
    return path


# ---------------------------------------------------------------------------
# PLY (no dependency)
# ---------------------------------------------------------------------------

_PLY_TYPES = {"char": "b", "uchar": "B", "int8": "b", "uint8": "B",
              "short": "h", "ushort": "H", "int16": "h", "uint16": "H",
              "int": "i", "uint": "I", "int32": "i", "uint32": "I",
              "float": "f", "float32": "f", "double": "d", "float64": "d"}


def read_ply(path, *, local: bool = False) -> PointCloud:
    """Read the ``vertex`` element of an ASCII or binary PLY file."""
    path = Path(path)
    with open(path, "rb") as fh:
        header = []
        while True:
            line = fh.readline()
            if not line:
                raise ValueError("not a PLY file (no end_header)")
            header.append(line.decode("ascii", "replace").strip())
            if header[-1] == "end_header":
                break
        if header[0] != "ply":
            raise ValueError("not a PLY file")
        fmt = next(h.split()[1] for h in header if h.startswith("format"))
        n_vertex, props = 0, []
        cur = None
        for h in header:
            parts = h.split()
            if parts[0] == "element":
                cur = parts[1]
                if cur == "vertex":
                    n_vertex = int(parts[2])
            elif parts[0] == "property" and cur == "vertex":
                props.append((parts[2], parts[1]))
        names = [p[0] for p in props]
        if fmt == "ascii":
            rows = [fh.readline().split() for _ in range(n_vertex)]
            data = np.asarray(rows, dtype=float)
        else:
            endian = "<" if fmt == "binary_little_endian" else ">"
            dt = np.dtype([(n, endian + _PLY_TYPES[t]) for n, t in props])
            rec = np.frombuffer(fh.read(dt.itemsize * n_vertex), dtype=dt, count=n_vertex)
            data = np.column_stack([rec[n].astype(float) for n in names])
    col = {n: i for i, n in enumerate(names)}
    xyz = data[:, [col["x"], col["y"], col["z"]]]
    rgb = None
    if all(k in col for k in ("red", "green", "blue")):
        rgb = data[:, [col["red"], col["green"], col["blue"]]]
    nrm = None
    if all(k in col for k in ("nx", "ny", "nz")):
        nrm = data[:, [col["nx"], col["ny"], col["nz"]]]
    inten = data[:, col["intensity"]] if "intensity" in col else None
    cloud = PointCloud(xyz, rgb=rgb, normals=nrm, intensity=inten, source=str(path))
    return cloud.to_local() if local else cloud


def write_ply(cloud: PointCloud, path, *, binary: bool = True,
              world: bool = False) -> Path:
    """Write a point cloud as PLY (binary little-endian by default).

    ``world=False`` writes working-frame coordinates (small numbers, safe
    for float32 viewers); ``world=True`` adds :attr:`PointCloud.origin`
    back and stores doubles.
    """
    path = Path(path)
    xyz = cloud.world_xyz if world else cloud.xyz
    ftype = "double" if world else "float"
    props = [("x", ftype), ("y", ftype), ("z", ftype)]
    cols = [xyz[:, 0], xyz[:, 1], xyz[:, 2]]
    if cloud.normals is not None:
        props += [("nx", "float"), ("ny", "float"), ("nz", "float")]
        cols += [cloud.normals[:, 0], cloud.normals[:, 1], cloud.normals[:, 2]]
    if cloud.rgb is not None:
        rgb = np.asarray(cloud.rgb, dtype=float)
        if rgb.size and rgb.max() > 255:
            rgb = rgb / 257.0
        elif rgb.size and rgb.max() <= 1.0:
            rgb = rgb * 255.0
        rgb = np.clip(np.rint(rgb), 0, 255)
        props += [("red", "uchar"), ("green", "uchar"), ("blue", "uchar")]
        cols += [rgb[:, 0], rgb[:, 1], rgb[:, 2]]
    if cloud.intensity is not None:
        props.append(("intensity", "float"))
        cols.append(np.asarray(cloud.intensity, dtype=float))
    header = ["ply", "format " + ("binary_little_endian" if binary else "ascii") + " 1.0",
              f"element vertex {len(cloud)}"]
    header += [f"property {t} {n}" for n, t in props]
    header.append("end_header")
    with open(path, "wb") as fh:
        fh.write(("\n".join(header) + "\n").encode("ascii"))
        if binary:
            dt = np.dtype([(n, "<" + _PLY_TYPES[t]) for n, t in props])
            rec = np.empty(len(cloud), dtype=dt)
            for (n, _), c in zip(props, cols):
                rec[n] = c
            fh.write(rec.tobytes())
        else:
            arr = np.column_stack(cols)
            np.savetxt(fh, arr, fmt="%.6g")
    return path


def read_cloud(path, **kwargs) -> PointCloud:
    """Dispatch on extension to :func:`read_las`, :func:`read_xyz` or
    :func:`read_ply`."""
    ext = Path(path).suffix.lower()
    if ext in (".las", ".laz"):
        return read_las(path, **kwargs)
    if ext == ".ply":
        return read_ply(path, **{k: v for k, v in kwargs.items() if k == "local"})
    if ext in (".xyz", ".txt", ".csv", ".pts"):
        return read_xyz(path, **kwargs)
    if ext == ".pod":
        raise ValueError("Bentley Pointools .pod is a closed format — export "
                         "the scan to LAS from MicroStation/Pointools first")
    raise ValueError(f"unsupported point-cloud extension {ext!r}")


__all__ = ["PointCloud", "VoxelAccumulator", "ASPRS_CLASSES", "las_info",
           "iter_las_chunks", "read_las", "write_las", "read_xyz", "write_xyz",
           "read_ply", "write_ply", "read_cloud"]
