#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Scan-to-CAD export: features and meshes to DXF and Rhino ``.3dm``.

Both writers take the same ingredients — :class:`~civilpy.scan.features.PlaneFeature`,
:class:`~civilpy.scan.features.CylinderFeature`, :class:`~civilpy.scan.features.LineFeature`,
:class:`~civilpy.scan.features.PolylineFeature`, :class:`~civilpy.scan.mesh.Mesh`
and optional thinned points — and place each on the layer its ``role``
maps to in :mod:`civilpy.structural.rhino_layers` (``Deck::Bridge Deck``,
``Substructure::Columns``, ...), so scanned as-built geometry lands in the
same layer tree as civilpy's parametric design models.

* :func:`export_dxf` — ``ezdxf`` (a core dependency): planes and cylinders
  as ``MESH`` entities, edges as ``LINE``, boundaries / sections as
  ``POLYLINE`` (3-D), points as ``POINT``.  DXF layer names cannot contain
  ``::`` so the nested path is flattened with ``_`` (``Deck_Bridge Deck``).
* :func:`export_3dm` — ``rhino3dm`` (lazy): cylinders become capped
  ``Brep`` solids, everything else a mesh / polyline / point cloud, on the
  real nested layers via :func:`~civilpy.structural.rhino_layers.ensure_layer`.

Coordinates are written as given; pass ``origin`` to add a local-frame
offset back (``PointCloud.origin``) so the file lands in state plane.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from civilpy.scan.features import (CylinderFeature, LineFeature, PlaneFeature,
                                   PolylineFeature, SubstructureUnit, LAYER_SCAN_POINTS)
from civilpy.scan.mesh import Mesh, box_mesh, cylinder_mesh, plane_mesh


def _origin(origin) -> np.ndarray:
    return np.zeros(3) if origin is None else np.asarray(origin, dtype=float).reshape(3)


def _collect_meshes(planes: Iterable[PlaneFeature], cylinders: Iterable[CylinderFeature],
                    meshes: Iterable[Mesh], segments: int,
                    units: Iterable[SubstructureUnit] = ()) -> list[Mesh]:
    out = [plane_mesh(p) for p in planes]
    out += [cylinder_mesh(c, segments=segments) for c in cylinders]
    out += [box_mesh(u) for u in units]
    out += list(meshes)
    return out


#: DXF ACI colours per top-level group, roughly matching the Rhino palette.
_DXF_COLORS = {"Deck": 5, "Superstructure": 3, "Substructure": 1, "Scan": 8,
               "Site": 2, "Review": 6}


def dxf_layer_name(layer: str) -> str:
    """Flatten a ``Group::Leaf`` path into a legal DXF layer name."""
    bad = '<>/\\":;?*|=`'
    name = layer.replace("::", "_")
    return "".join("_" if ch in bad else ch for ch in name)


def export_dxf(path, *, planes: Iterable[PlaneFeature] = (), cylinders: Iterable[CylinderFeature] = (),
               lines: Iterable[LineFeature] = (), polylines: Iterable[PolylineFeature] = (),
               meshes: Iterable[Mesh] = (), units: Iterable[SubstructureUnit] = (),
               points: Optional[np.ndarray] = None,
               points_layer: str = LAYER_SCAN_POINTS, max_points: int = 200_000,
               origin=None, segments: int = 32, version: str = "R2010") -> Path:
    """Write features to a DXF (see module docstring)."""
    import ezdxf

    off = _origin(origin)
    doc = ezdxf.new(version)
    doc.units = ezdxf.units.FT
    msp = doc.modelspace()
    layers: set[str] = set()

    def layer(name: str) -> str:
        dn = dxf_layer_name(name)
        if dn not in layers:
            group = name.split("::")[0]
            doc.layers.add(dn, color=_DXF_COLORS.get(group, 7))
            layers.add(dn)
        return dn

    for m in _collect_meshes(planes, cylinders, meshes, segments, units):
        if m.n_faces == 0:
            continue
        ent = msp.add_mesh(dxfattribs={"layer": layer(m.layer)})
        with ent.edit_data() as md:
            md.vertices = [tuple(v) for v in (m.vertices + off)]
            md.faces = [tuple(int(i) for i in f) for f in m.faces]
    for ln in lines:
        msp.add_line(tuple(ln.start + off), tuple(ln.end + off),
                     dxfattribs={"layer": layer(ln.layer)})
    for pl in polylines:
        pts = np.asarray(pl.points, dtype=float) + off
        if len(pts) < 2:
            continue
        ent = msp.add_polyline3d([tuple(p) for p in pts], dxfattribs={"layer": layer(pl.layer)})
        if pl.closed:
            ent.close(True)
    if points is not None and len(points):
        pts = np.asarray(points, dtype=float)
        if len(pts) > max_points:
            pts = pts[np.linspace(0, len(pts) - 1, max_points).astype(int)]
        ln = layer(points_layer)
        for p in pts + off:
            msp.add_point(tuple(p), dxfattribs={"layer": ln})
    path = Path(path)
    doc.saveas(str(path))
    return path


def export_3dm(path, *, planes: Iterable[PlaneFeature] = (), cylinders: Iterable[CylinderFeature] = (),
               lines: Iterable[LineFeature] = (), polylines: Iterable[PolylineFeature] = (),
               meshes: Iterable[Mesh] = (), units: Iterable[SubstructureUnit] = (),
               points: Optional[np.ndarray] = None,
               points_layer: str = LAYER_SCAN_POINTS, max_points: int = 2_000_000,
               origin=None, segments: int = 32, solids: bool = True,
               names: bool = True) -> Path:
    """Write features to a Rhino ``.3dm`` (lazy ``rhino3dm``).

    ``solids`` makes cylinders capped ``Brep`` solids (what a designer
    would model) instead of meshes.  Object names carry the feature name /
    role and a ``scan:*`` user-string block records the fit statistics.
    """
    import rhino3dm as r3

    from civilpy.structural.rhino_layers import ensure_layer

    off = _origin(origin)
    f = r3.File3dm()
    f.Settings.ModelUnitSystem = r3.UnitSystem.Feet
    layer_cache: dict[str, int] = {}

    def attrs(layer: str, name: str = "", meta: Optional[dict] = None):
        if layer not in layer_cache:
            layer_cache[layer] = ensure_layer(f, layer)
        a = r3.ObjectAttributes()
        a.LayerIndex = layer_cache[layer]
        if names and name:
            a.Name = name
        for k, v in (meta or {}).items():
            if isinstance(v, (int, float, str, bool)):
                a.SetUserString(f"scan:{k}", str(v))
        return a

    for p in planes:
        m = plane_mesh(p)
        if m.n_faces:
            f.Objects.AddMesh(m.translated(off).to_rhino(),
                              attrs(p.layer, p.name or p.role,
                                    {"role": p.role, "n_points": p.n_points, "rms": round(p.rms, 4),
                                     "area": round(p.area, 2), "tilt_deg": round(p.tilt_deg, 2)}))
    for c in cylinders:
        meta = {"role": c.role, "n_points": c.n_points, "rms": round(c.rms, 4),
                "radius": round(c.radius, 4), "length": round(c.length, 3),
                "tilt_deg": round(c.tilt_deg, 2)}
        a = attrs(c.layer, c.name or c.role, meta)
        if solids:
            start = c.start + off
            plane = r3.Plane(r3.Point3d(*map(float, start)), r3.Vector3d(*map(float, c.axis)))
            circle = r3.Circle(r3.Point3d(*map(float, start)), float(c.radius))
            circle.Plane = plane
            brep = r3.Brep.CreateFromCylinder(r3.Cylinder(circle, float(c.length)), True, True)
            if brep is not None:
                f.Objects.AddBrep(brep, a)
                continue
        f.Objects.AddMesh(cylinder_mesh(c, segments=segments).translated(off).to_rhino(), a)
    for u in units:
        f.Objects.AddMesh(box_mesh(u).translated(off).to_rhino(),
                          attrs(u.layer, u.name or u.role,
                                {"role": u.role, "n_points": u.n_points, "height": round(u.height, 2),
                                 "station": round(u.station, 2), "length": round(u.length, 2),
                                 "width": round(u.width, 2)}))
    for m in meshes:
        if m.n_faces:
            f.Objects.AddMesh(m.translated(off).to_rhino(), attrs(m.layer, m.name, m.meta))
    for ln in lines:
        s, e = ln.start + off, ln.end + off
        f.Objects.AddLine(r3.Point3d(*map(float, s)), r3.Point3d(*map(float, e)),
                          attrs(ln.layer, ln.name or ln.role, ln.meta))
    for pl in polylines:
        pts = np.asarray(pl.points, dtype=float) + off
        if len(pts) < 2:
            continue
        if pl.closed:
            pts = np.vstack([pts, pts[:1]])
        poly = r3.Polyline([r3.Point3d(*map(float, p)) for p in pts])
        f.Objects.AddPolyline(poly, attrs(pl.layer, pl.name or pl.role, pl.meta))
    if points is not None and len(points):
        pts = np.asarray(points, dtype=float)
        if len(pts) > max_points:
            pts = pts[np.linspace(0, len(pts) - 1, max_points).astype(int)]
        pc = r3.PointCloud()
        for p in pts + off:
            pc.Add(r3.Point3d(float(p[0]), float(p[1]), float(p[2])))
        f.Objects.AddPointCloud(pc, attrs(points_layer, "scan points"))
    path = Path(path)
    f.Write(str(path), 8)
    return path


def ground_terrain(xyz: np.ndarray, cell: Optional[float] = None, max_edge: Optional[float] = None):
    """A :class:`~civilpy.transportation.terrain.Terrain` from ground
    points: rasterised to ``cell`` when given (fast, regular), else a
    Delaunay TIN with ``max_edge`` sliver removal.  This is how a scanned
    site feeds the alignment / substructure placement pipeline."""
    if cell:
        return Mesh.from_grid(xyz, cell=cell, stat="mean").to_terrain()
    return Mesh.delaunay(xyz, plane=((0, 0, 1), 0), max_edge=max_edge).to_terrain()


__all__ = ["export_dxf", "export_3dm", "dxf_layer_name", "ground_terrain"]
