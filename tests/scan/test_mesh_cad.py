#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Meshing, primitive meshes, mesh writers, DXF / 3dm export, Terrain bridge."""

import numpy as np
import pytest

from civilpy.scan import cad, features as F, mesh as M
from civilpy.scan.cloud import PointCloud, read_ply
from civilpy.scan.segment import CylinderModel, ransac_plane
from tests.scan.conftest import plane_points


def test_mesh_basics_and_delaunay(rng):
    pts = plane_points(rng, (0, 0, 5), (1, 0, 0), (0, 1, 0), 10, 10, 1.0, noise=0)
    m = M.Mesh.delaunay(pts, name="sq")
    assert m.n_vertices == 100 and m.n_faces == 162
    assert m.area() == pytest.approx(81.0)
    assert (m.face_normals()[:, 2] > 0).all()
    lo, hi = m.bounds
    assert lo[2] == pytest.approx(5) and hi[2] == pytest.approx(5)
    assert m.translated((0, 0, 1)).bounds[0][2] == pytest.approx(6)
    assert m.edge_lengths().max() == pytest.approx(np.sqrt(2))
    # two separated patches: max_edge stops the bridge triangles
    far = np.vstack([pts, pts + [50, 0, 0]])
    m2 = M.Mesh.delaunay(PointCloud(far), plane=((0, 0, 1), 0), max_edge=2.0)
    assert m2.area() == pytest.approx(162.0)
    assert m2.n_vertices == 200
    pf = F.plane_feature(ransac_plane(pts, distance=0.05, n_iter=20), pts)
    assert M.Mesh.delaunay(pts, plane=pf).n_faces == 162
    with pytest.raises(ValueError):
        M.Mesh.delaunay(pts[:2])
    assert M.Mesh(np.zeros((0, 3)), np.zeros((0, 3))).bounds[0].tolist() == [0, 0, 0]


def test_grid_mesh(rng):
    pts = rng.uniform([0, 0, 0], [20, 10, 0.1], (5000, 3))
    m = M.Mesh.from_grid(pts, cell=1.0, stat="mean")
    assert m.n_faces == 2 * 19 * 9 and abs(m.area() - 171) < 5      # vertices at cell centres
    hole = pts[~((pts[:, 0] > 8) & (pts[:, 0] < 12))]
    mh = M.Mesh.from_grid(hole, cell=1.0, stat="max")
    assert mh.n_faces < m.n_faces
    filled = M.Mesh.from_grid(hole, cell=1.0, stat="min", fill=True)
    assert filled.n_faces == m.n_faces
    with pytest.raises(ValueError):
        M.Mesh.from_grid(pts, stat="median")
    with pytest.raises(ValueError):
        M.Mesh.from_grid(np.zeros((0, 3)))
    t = m.to_terrain()
    assert abs(t.elevation_at(10, 5) - 0.05) < 0.05


def test_primitive_meshes_and_polygon(rng):
    square = np.array([[0, 0], [4, 0], [4, 4], [0, 4.0]])
    assert len(M.polygon_triangles(square)) == 2
    concave = np.array([[0, 0], [4, 0], [4, 4], [2, 1], [0, 4.0]])
    tris = M.polygon_triangles(concave)
    assert len(tris) == 3
    assert len(M.polygon_triangles(concave[::-1])) == 3         # CW input
    assert len(M.polygon_triangles(square[:2])) == 0
    pts = plane_points(rng, (0, 0, 3), (1, 0, 0), (0, 1, 0), 10, 6, 0.5, noise=0)
    pf = F.plane_feature(ransac_plane(pts, distance=0.05, n_iter=20), pts, alpha=1.5)
    pm = M.plane_mesh(pf)
    assert pm.area() == pytest.approx(pf.area, rel=0.02)
    assert (pm.face_normals()[:, 2] > 0).all()
    rect = M.plane_mesh(pf, use_boundary=False)
    assert rect.n_faces == 2 and rect.area() == pytest.approx(9.5 * 5.5, rel=0.01)
    pf.boundary = None
    assert M.plane_mesh(pf).n_faces == 2
    cf = F.cylinder_feature(CylinderModel(np.array([0, 0, 5.0]), np.array([0, 0, 1.0]), 2.0,
                                          np.arange(3), (-5, 5)))
    cm = M.cylinder_mesh(cf, segments=64)
    assert cm.area() == pytest.approx(2 * np.pi * 2 * 10 + 2 * np.pi * 4, rel=0.01)
    assert M.cylinder_mesh(cf, segments=16, capped=False).n_faces == 32
    tilted = F.cylinder_feature(CylinderModel(np.zeros(3), np.array([1, 0, 0.0]), 1.0, np.arange(3), (0, 2)))
    assert M.cylinder_mesh(tilted).n_vertices == 66


def test_mesh_writers(tmp_path, rng):
    pts = plane_points(rng, (0, 0, 0), (1, 0, 0), (0, 1, 0), 4, 4, 1.0, noise=0)
    m = M.Mesh.delaunay(pts, name="patch")
    for ext in ("ply", "obj", "stl"):
        p = m.save(tmp_path / f"m.{ext}")
        assert p.stat().st_size > 0
    back = read_ply(tmp_path / "m.ply")
    assert np.allclose(np.sort(back.xyz, axis=0), np.sort(m.vertices, axis=0))
    m.write_ply(tmp_path / "a.ply", binary=False)
    assert (tmp_path / "a.ply").read_text().startswith("ply\nformat ascii")
    obj = (tmp_path / "m.obj").read_text()
    assert obj.startswith("o patch") and obj.count("\nf ") == m.n_faces
    stl = (tmp_path / "m.stl").read_bytes()
    assert len(stl) == 84 + 50 * m.n_faces
    with pytest.raises(ValueError):
        m.save(tmp_path / "m.xyz")


def test_export_dxf(tmp_path, rng):
    import ezdxf

    pts = plane_points(rng, (0, 0, 30), (1, 0, 0), (0, 1, 0), 20, 10, 0.5, noise=0)
    pf = F.plane_feature(ransac_plane(pts, distance=0.05, n_iter=20), pts)
    pf.role = "deck"
    cf = F.cylinder_feature(CylinderModel(np.array([0, 0, 5.0]), np.array([0, 0, 1.0]), 1.0,
                                          np.arange(3), (-5, 5)))
    cf.role = "column"
    ln = F.LineFeature(np.zeros(3), np.array([1, 1, 1.0]))
    pl = F.PolylineFeature(np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0.0]]), closed=True, role="section")
    empty = M.Mesh(np.zeros((0, 3)), np.zeros((0, 3)))
    unit = F.SubstructureUnit(station=0, station_range=(-2, 2), offset_range=(-5, 5), z_bottom=0,
                              z_top=20, n_points=9, centroid=np.zeros(3),
                              corners=np.array([[-2, -5, 0], [2, -5, 0], [2, 5, 0], [-2, 5, 0],
                                                [-2, -5, 20], [2, -5, 20], [2, 5, 20], [-2, 5, 20.0]]),
                              name="p1")
    p = cad.export_dxf(tmp_path / "f.dxf", planes=[pf], cylinders=[cf], lines=[ln], polylines=[pl],
                       meshes=[empty], units=[unit], points=rng.uniform(0, 1, (500, 3)), max_points=50,
                       origin=(100, 200, 300))
    doc = ezdxf.readfile(str(p))
    msp = doc.modelspace()
    kinds = {}
    for e in msp:
        kinds[e.dxftype()] = kinds.get(e.dxftype(), 0) + 1
    assert kinds["MESH"] == 3 and kinds["LINE"] == 1 and kinds["POLYLINE"] == 1 and kinds["POINT"] == 50
    layers = {e.dxf.layer for e in msp}
    assert {"Deck_Bridge Deck", "Substructure_Columns", "Scan_Points", "Substructure_Piers"} <= layers
    line = next(e for e in msp if e.dxftype() == "LINE")
    assert tuple(line.dxf.start) == (100, 200, 300)
    assert cad.dxf_layer_name('A::B<C>') == "A_B_C_"
    tiny = F.PolylineFeature(np.zeros((1, 3)))
    cad.export_dxf(tmp_path / "g.dxf", polylines=[tiny])


rhino3dm = pytest.importorskip("rhino3dm")


def test_export_3dm(tmp_path, rng):
    pts = plane_points(rng, (0, 0, 30), (1, 0, 0), (0, 1, 0), 20, 10, 0.5, noise=0)
    pf = F.plane_feature(ransac_plane(pts, distance=0.05, n_iter=20), pts, name="deck1")
    pf.role = "deck"
    cf = F.cylinder_feature(CylinderModel(np.array([0, 0, 5.0]), np.array([0, 0, 1.0]), 1.0,
                                          np.arange(3), (-5, 5)))
    cf.role = "column"
    ln = F.LineFeature(np.zeros(3), np.array([1, 1, 1.0]), meta={"planes": ["a", "b"], "k": 1})
    pl = F.PolylineFeature(np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0.0]]), closed=True, role="section")
    gm = M.Mesh.delaunay(pts, name="ground")
    gm.layer = "Scan::Ground"
    unit = F.SubstructureUnit(station=0, station_range=(-2, 2), offset_range=(-5, 5), z_bottom=0,
                              z_top=20, n_points=9, centroid=np.zeros(3),
                              corners=np.array([[-2, -5, 0], [2, -5, 0], [2, 5, 0], [-2, 5, 0],
                                                [-2, -5, 20], [2, -5, 20], [2, 5, 20], [-2, 5, 20.0]]),
                              name="p1")
    p = cad.export_3dm(tmp_path / "f.3dm", planes=[pf], cylinders=[cf], lines=[ln], polylines=[pl],
                       meshes=[gm, M.Mesh(np.zeros((0, 3)), np.zeros((0, 3)))], units=[unit],
                       points=rng.uniform(0, 1, (100, 3)), max_points=20, origin=(1, 2, 3))
    f = rhino3dm.File3dm.Read(str(p))
    assert len(f.Objects) == 7
    paths = {f.Layers[i].FullPath for i in range(len(f.Layers))}
    assert {"Deck::Bridge Deck", "Substructure::Columns", "Scan::Ground", "Scan::Points",
            "Substructure::Piers"} <= paths
    pier = next(o for o in f.Objects if o.Attributes.Name == "p1")
    assert pier.Attributes.GetUserString("scan:height") == "20.0"
    kinds = {type(o.Geometry).__name__ for o in f.Objects}
    assert {"Brep", "Mesh", "LineCurve", "PolylineCurve", "PointCloud"} <= kinds
    names = {o.Attributes.Name for o in f.Objects}
    assert "deck1" in names
    col = next(o for o in f.Objects if type(o.Geometry).__name__ == "Brep")
    assert col.Attributes.GetUserString("scan:radius") == "1.0"
    p2 = cad.export_3dm(tmp_path / "g.3dm", cylinders=[cf], solids=False,
                        polylines=[F.PolylineFeature(np.zeros((1, 3)))])
    f2 = rhino3dm.File3dm.Read(str(p2))
    assert type(f2.Objects[0].Geometry).__name__ == "Mesh"


def test_ground_terrain(bridge_xyz):
    ground = bridge_xyz[bridge_xyz[:, 2] < 3.0]
    t = cad.ground_terrain(ground, cell=2.0)
    assert abs(t.elevation_at(0, 0) - 0.0) < 0.3
    t2 = cad.ground_terrain(ground[::20], max_edge=20.0)
    assert t2.elevation_at(0, 0) is not None
