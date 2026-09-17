#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""RANSAC primitives, ground filter, clustering, region growing, slices."""

import numpy as np
import pytest

from civilpy.scan import segment as S
from civilpy.scan.cloud import PointCloud
from civilpy.scan.preprocess import estimate_normals
from tests.scan.conftest import TRUTH, cylinder_points, plane_points


def test_fit_plane_lsq_orients_up(rng):
    pts = plane_points(rng, (0, 0, 5), (1, 0, 0), (0, 1, 0), 10, 10, 0.5, noise=0)
    n, d, rms = S.fit_plane_lsq(pts)
    assert np.allclose(n, [0, 0, 1]) and d == pytest.approx(5) and rms < 1e-9
    wall = plane_points(rng, (3, 0, 0), (0, 1, 0), (0, 0, 1), 10, 10, 0.5, noise=0)
    n, d, _ = S.fit_plane_lsq(wall)
    assert abs(n[0]) == pytest.approx(1) and n[0] * d == pytest.approx(3)
    assert S.fit_plane_lsq(np.zeros((3, 3)))[2] == 0.0


def test_ransac_plane_finds_largest_and_constraints(rng):
    floor = plane_points(rng, (0, 0, 0), (1, 0, 0), (0, 1, 0), 40, 40, 0.5)
    wall = plane_points(rng, (0, 0, 5), (1, 0, 0), (0, 0, 1), 20, 10, 0.5)
    xyz = np.vstack([floor, wall])
    pm = S.ransac_plane(xyz, distance=0.05, n_iter=200)
    assert abs(pm.normal[2]) > 0.999 and abs(pm.d) < 0.05
    assert len(pm.inliers) == pytest.approx(len(floor), rel=0.02)
    assert pm.rms < 0.02 and np.allclose(pm.centroid, pm.normal * pm.d)
    assert np.abs(pm.distance(pm.project(xyz))).max() < 1e-9
    # restrict to vertical-normal planes → the wall
    pw = S.ransac_plane(xyz, distance=0.05, axis=(0, 1, 0), axis_angle=10)
    # the wall plus the floor row it stands on
    assert abs(pw.normal[1]) > 0.98 and len(pw.inliers) == pytest.approx(len(wall), rel=0.15)
    # normal-consistency filter removes the wall's bottom row from the floor plane
    nn = estimate_normals(xyz, k=10)
    pf = S.ransac_plane(xyz, distance=0.05, normals=nn, normal_angle=20)
    assert len(pf.inliers) <= len(floor) + 50
    assert S.ransac_plane(xyz[:2]) is None
    assert S.ransac_plane(xyz, axis=(1, 0, 0), axis_angle=0.0) is None
    assert S.ransac_plane(PointCloud(xyz), distance=0.05, sample_size=500) is not None


def test_segment_planes_iterates_and_connects(rng):
    a = plane_points(rng, (0, 0, 0), (1, 0, 0), (0, 1, 0), 20, 20, 0.5)
    b = plane_points(rng, (60, 0, 0), (1, 0, 0), (0, 1, 0), 20, 20, 0.5)     # coplanar, far away
    c = plane_points(rng, (0, 0, 10), (1, 0, 0), (0, 1, 0), 10, 10, 0.5)
    xyz = np.vstack([a, b, c])
    merged = S.segment_planes(xyz, distance=0.05, min_points=100, normal_angle=None)
    assert len(merged) == 2                                   # a+b then c
    split = S.segment_planes(xyz, distance=0.05, min_points=100, normal_angle=None,
                             connect_radius=1.5)
    assert len(split) == 3
    sizes = sorted(len(p.inliers) for p in split)
    assert sizes[0] == pytest.approx(len(c), rel=0.05)
    assert S.segment_planes(xyz, min_points=10 ** 6) == []
    assert len(S.segment_planes(PointCloud(xyz), distance=0.05, min_points=100, max_planes=1)) == 1
    frag = S.segment_planes(xyz, distance=0.05, min_points=len(a) + 10, normal_angle=None,
                            connect_radius=1.5, max_planes=5)
    assert frag == []                                          # each fragment too small → dropped


def test_ransac_cylinder_recovers_radius_and_axis(rng):
    col = cylinder_points(rng, (5, 5, 0), 1.5, 20, 0.25)
    floor = plane_points(rng, (5, 5, 0), (1, 0, 0), (0, 1, 0), 20, 20, 0.5)
    xyz = np.vstack([col, floor])
    nn = estimate_normals(xyz, k=12, orient=None)
    cm = S.ransac_cylinder(xyz, distance=0.05, n_iter=800, normals=nn, radius_range=(0.5, 5))
    assert cm.radius == pytest.approx(1.5, abs=0.03)
    assert abs(cm.axis[2]) > 0.995
    assert np.allclose(cm.center[:2], [5, 5], atol=0.05)
    assert cm.length == pytest.approx(20, abs=0.6)
    assert len(cm.inliers) == pytest.approx(len(col), rel=0.05)
    assert cm.rms < 0.03
    assert np.abs(cm.radial_distance(xyz[cm.inliers])).max() < 0.06
    assert cm.start[2] < cm.end[2]
    # vertical-axis constraint and normals from a PointCloud
    pc = PointCloud(xyz, normals=nn)
    cv = S.ransac_cylinder(pc, distance=0.05, axis=(0, 0, 1), axis_angle=10, seed=3)
    assert cv is not None and cv.radius == pytest.approx(1.5, abs=0.03)
    assert S.ransac_cylinder(xyz[:5]) is None
    assert S.ransac_cylinder(xyz, radius_range=(100, 200), normals=nn) is None


def test_segment_cylinders_separates_columns(rng):
    cols = [cylinder_points(rng, (x, y, 0), TRUTH["column_r"], 10, 0.3)
            for x, y in ((0, 0), (0, 12), (30, 0))]
    xyz = np.vstack(cols + [rng.uniform(-5, 35, (200, 3))])
    found = S.segment_cylinders(xyz, distance=0.05, min_points=200, n_iter=600,
                                radius_range=(1, 3), axis=(0, 0, 1), axis_angle=10,
                                connect_radius=1.0)
    assert len(found) == 3
    centers = sorted((round(c.center[0]), round(c.center[1])) for c in found)
    assert centers == [(0, 0), (0, 12), (30, 0)]
    for c in found:
        assert c.radius == pytest.approx(2.0, abs=0.05)
    assert S.segment_cylinders(xyz, min_points=10 ** 6) == []
    assert len(S.segment_cylinders(PointCloud(xyz), min_points=200, max_cylinders=1,
                                   radius_range=(1, 3))) == 1


def test_ground_mask_strips_structure(bridge_xyz):
    m = S.ground_mask(bridge_xyz, cell=1.0, max_window=60, slope=0.2, initial_threshold=0.3)
    z_true = TRUTH["ground_fn"](bridge_xyz[:, 0], bridge_xyz[:, 1])
    is_ground = np.abs(bridge_xyz[:, 2] - z_true) < 0.2
    recall = (m & is_ground).sum() / is_ground.sum()
    precision = (m & is_ground).sum() / m.sum()
    assert recall > 0.97 and precision > 0.97
    assert len(S.ground_mask(np.zeros((0, 3)))) == 0
    tiny = S.ground_mask(np.array([[0, 0, 0.0], [0.5, 0.5, 0.1]]), cell=10.0, max_window=5)
    assert tiny.all()


def test_euclidean_clusters_and_region_growing(rng):
    a = rng.uniform(0, 5, (300, 3))
    b = rng.uniform(20, 25, (150, 3))
    lone = np.array([[100.0, 100.0, 100.0]])
    xyz = np.vstack([a, b, lone])
    labels = S.euclidean_clusters(xyz, radius=1.5, min_points=5)
    assert labels[:300].tolist() == [0] * 300
    assert labels[300:450].tolist() == [1] * 150
    assert labels[-1] == -1
    assert len(S.euclidean_clusters(np.zeros((0, 3)), 1.0)) == 0
    with pytest.raises(MemoryError):
        S.euclidean_clusters(xyz, radius=1.5, max_pairs=10)
    # two perpendicular planes → two smooth regions
    floor = plane_points(rng, (0, 0, 0), (1, 0, 0), (0, 1, 0), 20, 20, 0.5, noise=0)
    wall = plane_points(rng, (0, 12, 5), (1, 0, 0), (0, 0, 1), 20, 10, 0.5, noise=0)
    pw = np.vstack([floor, wall])
    reg = S.region_growing(pw, k=10, angle=10, curvature=0.01, min_points=50)
    assert reg.max() == 1
    assert (reg[:len(floor)] == reg[0]).mean() > 0.95
    assert (reg[len(floor):] == reg[-1]).mean() > 0.95
    assert reg[0] != reg[-1]
    pc = PointCloud(pw, normals=estimate_normals(pw, k=10))
    assert S.region_growing(pc, k=10, min_points=50).max() == 1
    assert S.region_growing(pw, k=10, min_points=10 ** 6).max() == -1
    assert len(S.region_growing(np.zeros((0, 3)))) == 0
    assert S.region_growing(pw, k=10, min_points=50, max_regions=1).max() == 0


def test_slices_and_histogram(bridge_xyz):
    deck = S.slice_elevation(bridge_xyz, TRUTH["deck_z"] - 0.1, TRUTH["deck_z"] + 0.1)
    assert len(deck) > 10_000
    cut = S.slice_axis(bridge_xyz, (0, 0), (1, 0), station=0.0, half_width=0.5)
    assert np.abs(bridge_xyz[cut, 0]).max() <= 0.5
    edges, counts = S.elevation_histogram(bridge_xyz, 1.0)
    peaks = edges[np.argsort(-counts)[:6]]
    assert any(abs(p - TRUTH["deck_z"]) <= 1 for p in peaks)
    e, c = S.elevation_histogram(np.zeros((0, 3)))
    assert len(c) == 0
