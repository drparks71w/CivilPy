#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Down-sampling, outlier filters, normals, crops and axis frames."""

import numpy as np
import pytest

from civilpy.scan import preprocess as P
from civilpy.scan.cloud import PointCloud


def test_voxel_and_random_downsample(rng):
    xyz = rng.uniform(0, 10, (2000, 3))
    v = P.voxel_downsample(xyz, 2.0)
    assert 0 < len(v) <= 125
    pc = PointCloud(xyz, intensity=np.ones(2000), origin=(1, 2, 3))
    vc = P.voxel_downsample(pc, 2.0)
    assert isinstance(vc, PointCloud) and vc.origin.tolist() == [1, 2, 3]
    assert vc.intensity.shape == (len(vc),)
    r = P.random_downsample(xyz, 100)
    assert r.shape == (100, 3)
    assert P.random_downsample(xyz, 5000) is xyz
    assert len(P.random_downsample(pc, 10)) == 10


def test_outlier_filters(rng):
    grid = np.column_stack([np.repeat(np.arange(20.0), 20), np.tile(np.arange(20.0), 20),
                            np.zeros(400)])
    speckle = np.array([[10.5, 10.5, 30.0], [5.5, 5.5, -25.0]])
    xyz = np.vstack([grid, speckle])
    m = P.statistical_outlier_mask(xyz, k=8, std_ratio=1.5)
    assert not m[-1] and not m[-2] and m[:400].all()
    assert len(P.remove_statistical_outliers(PointCloud(xyz), k=8, std_ratio=1.5)) == 400
    m = P.radius_outlier_mask(xyz, radius=1.5, min_neighbors=3)
    assert not m[-1] and m[:400].sum() >= 396
    assert len(P.remove_radius_outliers(xyz, 1.5, 3)) >= 396
    assert P.statistical_outlier_mask(xyz[:5], k=20).all()
    assert len(P.radius_outlier_mask(np.zeros((0, 3)), 1.0)) == 0


def test_normals_on_plane_and_orientation(rng):
    xyz = rng.uniform(0, 10, (500, 3))
    xyz[:, 2] = 0.3 * xyz[:, 0]                       # plane tilted about y
    n = P.estimate_normals(xyz, k=12)
    expected = np.array([-0.3, 0, 1.0]) / np.linalg.norm([0.3, 0, 1.0])
    assert np.abs(n @ expected).min() > 0.99
    assert (n[:, 2] >= 0).all()                        # oriented up
    _, curv, eig = P.local_pca(xyz, k=12)
    assert curv.max() < 1e-6 and eig.shape == (500, 3)
    # outward orientation on a sphere shell
    d = rng.normal(size=(400, 3))
    sphere = d / np.linalg.norm(d, axis=1)[:, None] * 5
    n = P.estimate_normals(sphere, k=10, orient="outward")
    assert (np.einsum("ij,ij->i", n, sphere) > 0).all()
    raw = P.estimate_normals(sphere, k=10, orient=None)
    assert raw.shape == (400, 3)
    # radius neighbourhood and degenerate sizes
    n_r = P.estimate_normals(xyz, k=12, radius=2.0)
    assert np.abs(n_r @ expected).min() > 0.98
    tiny, _, _ = P.local_pca(np.zeros((2, 3)))
    assert tiny[:, 2].tolist() == [1.0, 1.0]
    pc = P.ensure_normals(PointCloud(xyz))
    assert pc.normals is not None and P.ensure_normals(pc) is pc


def test_crops_and_axis_frames(rng):
    xyz = rng.uniform(-50, 50, (3000, 3))
    box = P.crop_bbox(xyz, xmin=0, xmax=10, zmax=0)
    assert (box[:, 0] >= 0).all() and (box[:, 0] <= 10).all() and (box[:, 2] <= 0).all()
    pc = P.crop_bbox(PointCloud(xyz), ymin=0)
    assert isinstance(pc, PointCloud) and (pc.xyz[:, 1] >= 0).all()
    poly = P.crop_polygon(xyz, [(-10, -10), (10, -10), (10, 10), (-10, 10)], zmin=0, zmax=10)
    assert (np.abs(poly[:, :2]) <= 10).all() and (poly[:, 2] >= 0).all() and (poly[:, 2] <= 10).all()
    cor = P.crop_corridor(xyz, (-40, 0), (40, 0), half_width=5, zmin=-10, zmax=10)
    assert (np.abs(cor[:, 1]) <= 5).all() and (np.abs(cor[:, 0]) <= 40).all()
    with pytest.raises(ValueError):
        P.crop_corridor(xyz, (0, 0), (0, 0), 1)
    # a corridor along x → principal axis is x
    strip = rng.uniform([-100, -5, 0], [100, 5, 1], (500, 3))
    c, u = P.principal_axes(strip)
    assert abs(u[0]) > 0.99 and u[0] > 0
    sot = P.to_axis_frame(strip, c, u)
    back = P.from_axis_frame(sot, c, u)
    assert np.allclose(back, strip)
    # left offset positive: a point at +y for an x axis
    assert P.to_axis_frame(np.array([[0, 3, 0.0]]), (0, 0), (1, 0))[0, 1] == pytest.approx(3)
