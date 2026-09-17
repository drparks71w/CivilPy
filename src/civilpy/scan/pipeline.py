#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""One-call feature extraction for a bridge-site scan.

:func:`extract_features` runs the chain — condition → ground → planes →
cylinders → leftover clusters → boundaries / edges / clearance → role
labels — with defaults tuned for a 0.25 ft voxelised terrestrial scan in
feet, and returns a :class:`ScanFeatures` you can summarise, serialise or
export.  Every stage is a plain function elsewhere in the package, so a
site that needs different thresholds can call them directly.

::

    cloud = read_las("bridge.las", voxel=0.25)
    res = extract_features(cloud, plane_distance=0.08, cylinder_radius=(0.5, 5.0))
    print(res.summary())
    res.export_dxf("bridge_features.dxf", world=True)
    res.export_3dm("bridge_features.3dm", world=True)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from civilpy.scan.cloud import PointCloud
from civilpy.scan.features import (ClearanceGrid, CylinderFeature, LineFeature,
                                   PlaneFeature, PolylineFeature, SubstructureUnit,
                                   clearance_grid, cylinder_feature, intersect_planes,
                                   label_bridge_roles, longitudinal_profile, merge_coplanar,
                                   plane_feature, span_clearances, span_layout,
                                   substructure_from_profile)
from civilpy.scan.mesh import Mesh
from civilpy.scan.preprocess import (ensure_normals, remove_statistical_outliers)
from civilpy.scan.segment import (euclidean_clusters, ground_mask, segment_cylinders,
                                  segment_planes)

Log = Optional[Callable[[str], None]]


@dataclass
class ScanFeatures:
    """Everything :func:`extract_features` found, in the cloud's working
    frame (add :attr:`origin` to get world coordinates)."""

    cloud: PointCloud
    ground: np.ndarray                          # boolean mask over cloud
    planes: list[PlaneFeature] = field(default_factory=list)
    cylinders: list[CylinderFeature] = field(default_factory=list)
    edges: list[LineFeature] = field(default_factory=list)
    polylines: list[PolylineFeature] = field(default_factory=list)
    units: list[SubstructureUnit] = field(default_factory=list)
    spans: list[dict] = field(default_factory=list)
    superstructure_depth: Optional[float] = None
    clusters: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    cluster_index: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    clearance: Optional[ClearanceGrid] = None
    ground_mesh: Optional[Mesh] = None
    axis_origin: np.ndarray = field(default_factory=lambda: np.zeros(2))
    axis_direction: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0]))
    params: dict = field(default_factory=dict)

    @property
    def origin(self) -> np.ndarray:
        return self.cloud.origin

    @property
    def unassigned(self) -> np.ndarray:
        """Mask of points in no ground / plane / cylinder feature."""
        m = ~self.ground
        for p in self.planes:
            if p.inliers is not None:
                m[p.inliers] = False
        for c in self.cylinders:
            if c.inliers is not None:
                m[c.inliers] = False
        return m

    def by_role(self, role: str) -> list:
        return [f for f in self.planes + self.cylinders + self.units if f.role == role]

    @property
    def deck(self) -> Optional[PlaneFeature]:
        d = self.by_role("deck")
        return d[0] if d else None

    def summary(self) -> dict:
        n = len(self.cloud)
        assigned = n - int(self.unassigned.sum())
        roles: dict[str, int] = {}
        for f in self.planes + self.cylinders:
            roles[f.role] = roles.get(f.role, 0) + 1
        out = {
            "source": self.cloud.source,
            "crs": self.cloud.crs,
            "origin": self.origin.tolist(),
            "n_points": n,
            "n_ground": int(self.ground.sum()),
            "n_assigned": assigned,
            "assigned_fraction": round(assigned / n, 4) if n else 0.0,
            "n_planes": len(self.planes),
            "n_cylinders": len(self.cylinders),
            "n_edges": len(self.edges),
            "n_units": len(self.units),
            "n_spans": len(self.spans),
            "span_lengths": [round(sp["length"], 2) for sp in self.spans],
            "superstructure_depth": (None if self.superstructure_depth is None
                                     else round(self.superstructure_depth, 2)),
            "n_clusters": int(self.clusters.max() + 1) if len(self.clusters) else 0,
            "roles": roles,
            "axis_origin": self.axis_origin.tolist(),
            "axis_direction": self.axis_direction.tolist(),
        }
        if self.deck is not None:
            d = self.deck
            out["deck"] = {"elevation": round(d.elevation, 3), "length": round(d.extent_u, 2),
                           "width": round(d.extent_v, 2), "area": round(d.area, 1),
                           "tilt_deg": round(d.tilt_deg, 3)}
        if self.units:
            out["units"] = [{"name": u.name, "role": u.role, "station": round(u.station, 2),
                             "height": round(u.height, 2), "length": round(u.length, 2),
                             "width": round(u.width, 2), "z_bottom": round(u.z_bottom, 2),
                             "z_top": round(u.z_top, 2)} for u in self.units]
        if self.clearance is not None:
            out["min_clearance"] = self.clearance.min_clearance()
        return out

    def to_dict(self) -> dict:
        return {
            "summary": self.summary(),
            "params": self.params,
            "planes": [p.to_dict() for p in self.planes],
            "cylinders": [c.to_dict() for c in self.cylinders],
            "edges": [e.to_dict() for e in self.edges],
            "polylines": [p.to_dict() for p in self.polylines],
            "units": [u.to_dict() for u in self.units],
            "spans": self.spans,
        }

    def save_json(self, path) -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.to_dict(), indent=2, default=_json_default),
                        encoding="utf-8")
        return path

    def _export_kwargs(self, world: bool, points: bool) -> dict:
        return {
            "planes": self.planes, "cylinders": self.cylinders, "lines": self.edges,
            "polylines": self.polylines, "units": self.units,
            "meshes": [self.ground_mesh] if self.ground_mesh is not None else [],
            "points": self.cloud.xyz[self.unassigned] if points else None,
            "origin": self.origin if world else None,
        }

    def export_dxf(self, path, world: bool = True, points: bool = False, **kw) -> Path:
        """DXF of all features (see :func:`civilpy.scan.cad.export_dxf`)."""
        from civilpy.scan.cad import export_dxf
        return export_dxf(path, **self._export_kwargs(world, points), **kw)

    def export_3dm(self, path, world: bool = True, points: bool = True, **kw) -> Path:
        """Rhino ``.3dm`` of all features (see :func:`civilpy.scan.cad.export_3dm`)."""
        from civilpy.scan.cad import export_3dm
        return export_3dm(path, **self._export_kwargs(world, points), **kw)

    def export_meshes(self, folder, fmt: str = "ply", world: bool = False) -> list[Path]:
        """One mesh file per plane / cylinder / ground surface."""
        from civilpy.scan.mesh import box_mesh, cylinder_mesh, plane_mesh

        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        off = self.origin if world else np.zeros(3)
        out = []
        items = [(f"plane_{i:02d}_{p.role}", plane_mesh(p)) for i, p in enumerate(self.planes)]
        items += [(f"cyl_{i:02d}_{c.role}", cylinder_mesh(c)) for i, c in enumerate(self.cylinders)]
        items += [(f"unit_{i:02d}_{u.role}", box_mesh(u)) for i, u in enumerate(self.units)]
        if self.ground_mesh is not None:
            items.append(("ground", self.ground_mesh))
        for name, m in items:
            if m.n_faces:
                out.append(m.translated(off).save(folder / f"{name}.{fmt}"))
        return out


def _json_default(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def extract_features(cloud: PointCloud, *,
                     outliers: bool = True, outlier_k: int = 20, outlier_std: float = 2.0,
                     normals_k: int = 16,
                     ground: bool = True, ground_cell: float = 1.0, ground_window: float = 60.0,
                     ground_slope: float = 0.2, ground_threshold: float = 0.3,
                     plane_distance: float = 0.06, plane_min_points: int = 400,
                     max_planes: int = 24, plane_normal_angle: float = 25.0,
                     plane_connect: Optional[float] = None, boundary_alpha: Optional[float] = None,
                     plane_min_extent: float = 1.0, merge_planes: bool = True,
                     cylinders: bool = True, cylinder_distance: float = 0.06,
                     cylinder_radius: tuple[float, float] = (0.4, 6.0),
                     cylinder_min_points: int = 200, max_cylinders: int = 16,
                     cylinder_vertical_angle: Optional[float] = 20.0,
                     cluster_radius: Optional[float] = None, cluster_min_points: int = 50,
                     edges: bool = True, clearance_cell: float = 1.0,
                     clearance_min_gap: float = 4.0, clearance_min_support: int = 4,
                     ground_mesh_cell: Optional[float] = 2.0,
                     profile: bool = True, substructure: bool = True,
                     unit_margin: float = 5.0, unit_min_drop: float = 4.0,
                     unit_min_points: int = 50, voxel: Optional[float] = None,
                     log: Log = None) -> ScanFeatures:
    """Extract bridge features from a conditioned point cloud.

    Distances are in feet and default to a 0.25 ft voxel grid; pass
    ``voxel`` to record the grid size used (it seeds ``plane_connect`` and
    ``cluster_radius`` at 3× when those are ``None``).  Steps:

    1. statistical outlier removal (``outliers``) and PCA normals;
    2. ground by progressive morphological filter (``ground_*``; the
       window must exceed the deck width);
    3. RANSAC planes on the non-ground points (``plane_*``); each plane's
       inliers are kept connected within ``plane_connect`` ft, its
       boundary is an alpha shape of ``boundary_alpha`` ft (``None`` →
       convex hull), planes narrower than ``plane_min_extent`` (a
       single row of points where two faces meet) are discarded, and
       coplanar horizontal fragments are merged (``merge_planes``);
    4. RANSAC cylinders on what remains (``cylinder_*``; vertical within
       ``cylinder_vertical_angle`` degrees when set);
    5. Euclidean clusters of the leftover points (``cluster_*``);
    6. crease edges between touching planes, the deck longitudinal
       profile, the under-clearance grid (restricted to the deck
       footprint when a deck was found) and a ground mesh;
    7. role labels (:func:`~civilpy.scan.features.label_bridge_roles`);
    8. substructure units and the span layout from the lowest-point
       profile under the deck (``unit_*``;
       :func:`~civilpy.scan.features.substructure_from_profile`).
    """
    say = log or (lambda s: None)
    params = {k: v for k, v in locals().items() if k not in ("cloud", "log", "say")}
    if voxel and plane_connect is None:
        plane_connect = 3.0 * voxel
    if voxel and cluster_radius is None:
        cluster_radius = 3.0 * voxel

    if outliers and len(cloud) > outlier_k:
        before = len(cloud)
        cloud = remove_statistical_outliers(cloud, k=outlier_k, std_ratio=outlier_std)
        say(f"outliers: {before - len(cloud):,} removed, {len(cloud):,} kept")
    cloud = ensure_normals(cloud, k=normals_k)
    xyz = cloud.xyz
    n = len(xyz)

    if ground and n:
        gmask = ground_mask(xyz, cell=ground_cell, max_window=ground_window, slope=ground_slope,
                            initial_threshold=ground_threshold, max_threshold=6.0)
        say(f"ground: {gmask.sum():,} of {n:,} points")
    else:
        gmask = np.zeros(n, dtype=bool)
    ground_z = float(np.median(xyz[gmask, 2])) if gmask.any() else None
    structure = np.nonzero(~gmask)[0]

    planes: list[PlaneFeature] = []
    if len(structure) >= plane_min_points:
        models = segment_planes(xyz[structure], distance=plane_distance,
                                min_points=plane_min_points, max_planes=max_planes,
                                normals=cloud.normals[structure],
                                normal_angle=plane_normal_angle, connect_radius=plane_connect)
        for pm in models:
            pm.inliers = structure[pm.inliers]
            pf = plane_feature(pm, xyz, alpha=boundary_alpha)
            if min(pf.extent_u, pf.extent_v) < plane_min_extent:
                continue
            pf.name = f"plane_{len(planes):02d}"
            planes.append(pf)
        if merge_planes and len(planes) > 1:
            before = len(planes)
            planes = merge_coplanar(planes, xyz, alpha=boundary_alpha)
            if len(planes) < before:
                say(f"planes: merged {before - len(planes)} coplanar horizontal fragments")
        say(f"planes: {len(planes)} ({sum(p.n_points for p in planes):,} points)")

    used = np.zeros(n, dtype=bool)
    used[gmask] = True
    for p in planes:
        used[p.inliers] = True
    rest = np.nonzero(~used)[0]

    cyls: list[CylinderFeature] = []
    if cylinders and len(rest) >= cylinder_min_points:
        axis = (0, 0, 1) if cylinder_vertical_angle is not None else None
        models = segment_cylinders(xyz[rest], distance=cylinder_distance,
                                   min_points=cylinder_min_points, max_cylinders=max_cylinders,
                                   radius_range=cylinder_radius, normals=cloud.normals[rest],
                                   axis=axis, axis_angle=cylinder_vertical_angle,
                                   connect_radius=plane_connect)
        for i, cm in enumerate(models):
            cm.inliers = rest[cm.inliers]
            cyls.append(cylinder_feature(cm, name=f"cyl_{i:02d}"))
            used[cm.inliers] = True
        say(f"cylinders: {len(cyls)} ({sum(c.n_points for c in cyls):,} points)")
    rest = np.nonzero(~used)[0]

    labels = np.zeros(0, dtype=int)
    if cluster_radius and len(rest) >= cluster_min_points:
        try:
            labels = euclidean_clusters(xyz[rest], radius=cluster_radius,
                                        min_points=cluster_min_points)
            say(f"clusters: {labels.max() + 1 if len(labels) else 0} from {len(rest):,} leftover points")
        except MemoryError as exc:                # too many leftover pairs: skip, keep the rest
            say(f"clusters: skipped ({exc})")
            rest = np.zeros(0, dtype=int)

    origin2, direction2 = label_bridge_roles(planes, cyls, ground_z=ground_z)
    say("roles: " + ", ".join(f"{f.role}" for f in planes + cyls))

    edge_list: list[LineFeature] = []
    if edges:
        for i in range(len(planes)):
            for j in range(i + 1, len(planes)):
                ln = intersect_planes(planes[i], planes[j])
                if ln is None:
                    continue
                # only keep creases that both faces' points actually reach
                mid = 0.5 * (ln.start + ln.end)
                da = np.min(np.linalg.norm(xyz[planes[i].inliers] - mid, axis=1))
                db = np.min(np.linalg.norm(xyz[planes[j].inliers] - mid, axis=1))
                if max(da, db) <= 4.0 * plane_distance + (voxel or 0.25) * 3:
                    ln.name = f"edge_{planes[i].name}_{planes[j].name}"
                    edge_list.append(ln)
        say(f"edges: {len(edge_list)}")

    polylines: list[PolylineFeature] = []
    deck = next((p for p in planes if p.role == "deck"), None)
    if profile and deck is not None:
        prof = longitudinal_profile(xyz[deck.inliers], origin2, direction2, half_width=2.0,
                                    bin_size=2.0, side="top")
        if len(prof) >= 2:
            from civilpy.scan.preprocess import from_axis_frame
            pts = from_axis_frame(np.column_stack([prof[:, 0], np.zeros(len(prof)), prof[:, 1]]),
                                  origin2, direction2)
            polylines.append(PolylineFeature(pts, role="section", name="deck_profile"))

    units: list[SubstructureUnit] = []
    spans: list[dict] = []
    sup_depth = None
    if substructure and deck is not None:
        units, info = substructure_from_profile(
            xyz, ~gmask, deck, origin2, direction2, margin=unit_margin,
            min_drop=unit_min_drop, min_points=unit_min_points)
        sup_depth = info["superstructure_depth"]
        spans = span_layout(units, info["deck_station_range"])
        say(f"substructure: {len(units)} units, {len(spans)} spans "
            + ", ".join(f"{sp['length']:.1f}" for sp in spans)
            + (f"; superstructure depth {sup_depth:.1f} ft" if sup_depth else ""))

    clearance = None
    if clearance_cell:
        footprint = None
        if deck is not None:
            footprint = deck.boundary if deck.boundary is not None else deck.corners
        cl_xyz = xyz
        if deck is not None and sup_depth is not None:
            # search below the superstructure underside so the voids between
            # deck, floor beams and bracing are not mistaken for clearance
            cl_xyz = xyz[xyz[:, 2] < deck.elevation - sup_depth + 1.0]
        clearance = clearance_grid(cl_xyz, cell=clearance_cell, min_gap=clearance_min_gap,
                                   min_support=clearance_min_support, footprint=footprint)
        if deck is not None and sup_depth is not None:
            # the gap must be closed by the superstructure, not by something under it
            clearance = clearance.restrict_upper(deck.elevation - sup_depth - 2.0)
        if spans:
            span_clearances(spans, clearance, origin2, direction2)
        mc = clearance.min_clearance()
        if mc:
            say(f"min clearance: {mc['clearance']:.2f} ft at ({mc['x']:.1f}, {mc['y']:.1f})")

    gmesh = None
    if ground_mesh_cell and gmask.sum() >= 3:
        try:
            gmesh = Mesh.from_grid(xyz[gmask], cell=ground_mesh_cell, stat="mean", name="ground")
            gmesh.layer = "Scan::Ground"
        except ValueError:
            gmesh = None

    return ScanFeatures(cloud=cloud, ground=gmask, planes=planes, cylinders=cyls,
                        edges=edge_list, polylines=polylines, units=units, spans=spans,
                        superstructure_depth=sup_depth, clusters=labels,
                        cluster_index=rest, clearance=clearance, ground_mesh=gmesh,
                        axis_origin=np.asarray(origin2, float),
                        axis_direction=np.asarray(direction2, float), params=params)


__all__ = ["ScanFeatures", "extract_features"]
