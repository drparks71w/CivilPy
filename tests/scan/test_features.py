#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Feature records, boundaries, clearance grid, sections and role labels."""

import numpy as np
import pytest

from civilpy.scan import features as F
from civilpy.scan.segment import CylinderModel, ransac_plane
from civilpy.structural import rhino_layers as L
from tests.scan.conftest import TRUTH, plane_points


def _plane_feat(rng, center, u, v, lu, lv, alpha=None, name="p"):
    pts = plane_points(rng, center, u, v, lu, lv, 0.5, noise=0.0)
    pm = ransac_plane(pts, distance=0.05, n_iter=50)
    return F.plane_feature(pm, pts, alpha=alpha, name=name), pts


def test_plane_feature_geometry(rng):
    pf, pts = _plane_feat(rng, (0, 0, 10), (1, 0, 0), (0, 1, 0), 40, 20)
    assert pf.orientation == "horizontal" and pf.tilt_deg < 0.01
    assert pf.extent_u == pytest.approx(39.5, abs=0.1) and pf.extent_v == pytest.approx(19.5, abs=0.1)
    assert pf.area == pytest.approx(39.5 * 19.5, rel=0.01)
    assert pf.elevation == pytest.approx(10)
    assert pf.corners.shape == (4, 3) and pf.boundary.shape[1] == 3
    assert abs(pf.strike[0]) == pytest.approx(1)
    assert pf.layer == F.LAYER_SCAN_PLANES
    d = pf.to_dict()
    assert d["orientation"] == "horizontal" and "inliers" not in d and d["boundary_vertices"] > 0
    wall, _ = _plane_feat(rng, (5, 0, 0), (0, 1, 0), (0, 0, 1), 10, 6)
    assert wall.orientation == "vertical" and abs(wall.strike[1]) == pytest.approx(1)
    slope, _ = _plane_feat(rng, (0, 0, 0), (1, 0, 0), (0, 1, 1), 10, 6)
    assert slope.orientation == "sloped"
    # alpha shape follows a notch the convex hull would bridge
    pts = plane_points(rng, (0, 0, 0), (1, 0, 0), (0, 1, 0), 40, 40, 0.5, noise=0)
    notch = ~((pts[:, 0] > 0) & (np.abs(pts[:, 1]) < 5))
    pm = ransac_plane(pts[notch], distance=0.05, n_iter=20)
    concave = F.plane_feature(pm, pts[notch], alpha=1.5)
    convex = F.plane_feature(pm, pts[notch], alpha=None)
    assert concave.area < convex.area - 100
    assert len(concave.boundary) > len(convex.boundary)


def test_alpha_shape_and_simplify(rng):
    xy = rng.uniform(0, 10, (400, 2))
    loops = F.alpha_shape_edges(xy, alpha=1.5)
    assert len(loops) >= 1 and len(loops[0]) >= 4
    assert len(F.alpha_shape_edges(xy[:3], 1.0)[0]) == 3
    assert len(F.alpha_shape_edges(xy, alpha=1e-6)[0]) >= 3          # falls back to the hull
    zig = np.array([[0, 0, 0], [1, 0.01, 0], [2, -0.01, 0], [3, 0, 0], [3, 3, 0]], float)
    simp = F.simplify_polyline(zig, 0.1)
    assert len(simp) == 3 and simp[0].tolist() == [0, 0, 0]
    assert len(F.simplify_polyline(zig[:2], 0.1)) == 2
    square = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]], float)
    closed = F.simplify_polyline(square, 0.1, closed=True)
    assert len(closed) == 4
    loop, area = F.plane_boundary(np.zeros((2, 3)), np.array([0, 0, 1.0]), np.zeros(3),
                                  np.array([1, 0, 0.0]), np.array([0, 1, 0.0]))
    assert area == 0.0 and len(loop) == 2


def test_intersect_planes(rng):
    floor, _ = _plane_feat(rng, (0, 0, 0), (1, 0, 0), (0, 1, 0), 20, 20, name="floor")
    wall, _ = _plane_feat(rng, (0, 10, 5), (1, 0, 0), (0, 0, 1), 20, 10, name="wall")
    ln = F.intersect_planes(floor, wall)
    assert ln is not None
    assert ln.start[1] == pytest.approx(10, abs=0.05) and ln.end[1] == pytest.approx(10, abs=0.05)
    assert abs(ln.start[2]) < 0.05 and ln.length == pytest.approx(19.5, abs=0.2)
    assert ln.meta["planes"] == ["floor", "wall"] and ln.layer == F.LAYER_SCAN_EDGES
    assert "length" in ln.to_dict()
    other, _ = _plane_feat(rng, (0, 0, 5), (1, 0, 0), (0, 1, 0), 20, 20)
    assert F.intersect_planes(floor, other) is None               # parallel
    far, _ = _plane_feat(rng, (100, 10, 5), (1, 0, 0), (0, 0, 1), 10, 10)
    assert F.intersect_planes(floor, far) is None                 # no overlap
    assert F.intersect_planes(floor, far, clip=False).length == pytest.approx(20)


def test_cylinder_and_polyline_records():
    cm = CylinderModel(center=np.array([1, 2, 5.0]), axis=np.array([0, 0, 1.0]), radius=1.25,
                       inliers=np.arange(10), extent=(-5.0, 5.0), rms=0.01)
    cf = F.cylinder_feature(cm, name="c")
    assert cf.length == pytest.approx(10) and cf.diameter == 2.5 and cf.tilt_deg == 0
    assert cf.start.tolist() == [1, 2, 0] and cf.end.tolist() == [1, 2, 10]
    assert cf.to_dict()["n_points"] == 10
    pl = F.PolylineFeature(np.array([[0, 0, 0], [3, 0, 0], [3, 4, 0.0]]), closed=True, role="section")
    assert pl.length == pytest.approx(12) and pl.layer == F.LAYER_SCAN_SECTIONS
    assert pl.to_dict()["n_vertices"] == 3
    assert F.PolylineFeature(np.zeros((1, 3))).length == 0.0
    assert F.layer_for("nonsense") == F.LAYER_SCAN_PLANES


def test_clearance_grid(bridge_xyz):
    cg = F.clearance_grid(bridge_xyz, cell=2.0, min_gap=4.0)     # 16 pts/surface/cell at 0.5 ft
    mc = cg.min_clearance()
    # soffit at 27.5 over ground ≈ 0.01x + 0.5 sin(y/15): min gap ≈ 27.5 - (0.75 + 0.5) ≈ 26.2
    assert 25.5 < mc["clearance"] < 27.0
    assert abs(mc["z_high"] - TRUTH["soffit_z"]) < 0.3
    assert abs(mc["x"]) <= 75 and abs(mc["y"]) <= 18                # under the deck
    assert cg.cell_centers().shape[1] == 3 and cg.valid.sum() > 500
    # column-edge voids are not reported as clearance
    assert np.nanmin(cg.gap) > 20
    sub = F.clearance_grid(bridge_xyz, cell=2.0, min_gap=4.0, bbox=(-10, -10, 10, 10))
    assert sub.gap.shape[0] <= 11
    empty = F.clearance_grid(np.zeros((0, 3)))
    assert empty.min_clearance() is None
    ground_only = F.clearance_grid(bridge_xyz[bridge_xyz[:, 2] < 2.0], cell=2.0)
    assert ground_only.min_clearance() is None


def test_sections_and_profile(bridge_xyz):
    sec = F.cross_section(bridge_xyz, (0, 0), (1, 0), station=0.0, half_width=0.5)
    assert sec.shape[1] == 2 and np.abs(sec[:, 0]).max() <= 60
    top = F.section_envelope(sec, bin_size=0.5, side="top")
    deck_part = top[np.abs(top[:, 0]) < 15]
    assert np.abs(deck_part[:, 1] - TRUTH["deck_z"]).max() < 0.3
    bottom = F.section_envelope(sec, bin_size=1.0, side="bottom")
    assert bottom[np.abs(bottom[:, 0]) < 15][:, 1].max() < 3
    assert F.section_envelope(np.zeros((0, 2))).shape == (0, 2)
    prof = F.longitudinal_profile(bridge_xyz, (0, 0), (1, 0), half_width=1.0, bin_size=2.0)
    on_deck = prof[np.abs(prof[:, 0]) < 70]
    assert np.abs(on_deck[:, 1] - TRUTH["deck_z"]).max() < 0.3


def test_bridge_axis_and_roles(rng):
    deck, _ = _plane_feat(rng, (0, 0, 30), (1, 0, 0), (0, 1, 0), 150, 36, name="deck")
    soffit, _ = _plane_feat(rng, (0, 0, 27.5), (1, 0, 0), (0, 1, 0), 150, 36, name="soffit")
    abut, _ = _plane_feat(rng, (-75, 0, 14), (0, 1, 0), (0, 0, 1), 40, 27, name="abut")
    pier, _ = _plane_feat(rng, (0, 0, 14), (0, 1, 0), (0, 0, 1), 40, 27, name="pier")
    wing, _ = _plane_feat(rng, (-85, 20, 8), (1, 0, 0), (0, 0, 1), 20, 14, name="wing")
    barrier, _ = _plane_feat(rng, (0, 18, 31.5), (1, 0, 0), (0, 0, 1), 150, 3, name="bar")
    web, _ = _plane_feat(rng, (0, 5, 26), (1, 0, 0), (0, 0, 1), 150, 3, name="web")
    cap, _ = _plane_feat(rng, (0, 0, 24), (1, 0, 0), (0, 1, 0), 6, 36, name="cap")
    low, _ = _plane_feat(rng, (60, 50, 0.2), (1, 0, 0), (0, 1, 0), 10, 10, name="low")
    chord, _ = _plane_feat(rng, (0, 8, 55), (1, 0, 0), (0, 0, 1), 100, 2, name="chord")
    rock, _ = _plane_feat(rng, (0, 80, 40), (1, 0, 0), (0, 0, 1), 60, 30, name="rock")
    slope, _ = _plane_feat(rng, (60, -50, 5), (1, 0, 0), (0, 1, 1), 10, 10, name="slope")
    col = F.cylinder_feature(CylinderModel(np.array([25, 10, 10.0]), np.array([0, 0, 1.0]), 2.0,
                                           np.arange(5), (-10, 10)))
    pile = F.cylinder_feature(CylinderModel(np.array([25, -10, 5.0]), np.array([0, 0, 1.0]), 0.5,
                                            np.arange(5), (-5, 5)))
    tilted = F.cylinder_feature(CylinderModel(np.array([0, 0, 5.0]), np.array([1, 0, 1.0]) / 2 ** .5, 1.0,
                                              np.arange(5), (-5, 5)))
    planes = [deck, soffit, abut, pier, wing, barrier, web, cap, low, slope, chord, rock]
    o, d = F.label_bridge_roles(planes, [col, pile, tilted], ground_z=0.0)
    assert abs(d[0]) > 0.99
    roles = {p.name: p.role for p in planes}
    assert roles == {"deck": "deck", "soffit": "soffit", "abut": "abutment", "pier": "pier_face",
                     "wing": "wingwall", "bar": "barrier", "web": "girder_web", "cap": "cap",
                     "low": "ground", "slope": "plane", "chord": "truss", "rock": "wall"}
    assert (col.role, pile.role, tilted.role) == ("column", "pile", "cylinder")
    assert deck.layer == L.LAYER_BRIDGE_DECK and col.layer == L.LAYER_SUB_COLUMNS
    # explicit axis, no deck, no ground
    o2, d2 = F.label_bridge_roles([abut, wing], [], axis=((0, 0), (0, 1)))
    assert d2.tolist() == [0, 1]
    assert F.label_bridge_roles([], [], )[1].tolist() == [1.0, 0.0]
    assert F.label_bridge_roles([cap], [])[0].shape == (2,)
    bo, bd = F.bridge_axis(np.zeros((0, 3)), deck)
    assert abs(bd[0]) > 0.99
    po, pd = F.bridge_axis(rng.uniform([0, 0, 0], [100, 5, 1], (200, 3)))
    assert abs(pd[0]) > 0.99
