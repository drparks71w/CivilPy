#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Synthetic bridge-site point clouds for the scan-to-CAD tests.

Nothing here touches a real scan: the fixtures sample ideal surfaces —
an undulating ground, a deck slab with soffit and barriers, two abutment
walls with wingwalls, four round columns — with a little Gaussian noise
and some random speckle, so every algorithm has a known answer to hit.
"""

import numpy as np
import pytest

from civilpy.scan.cloud import PointCloud


def plane_points(rng, center, u, v, len_u, len_v, spacing, noise=0.01):
    a = np.arange(-len_u / 2, len_u / 2, spacing)
    b = np.arange(-len_v / 2, len_v / 2, spacing)
    A, B = np.meshgrid(a, b)
    u, v = np.asarray(u, float), np.asarray(v, float)
    pts = np.asarray(center, float) + A.ravel()[:, None] * u + B.ravel()[:, None] * v
    n = np.cross(u, v)
    n /= np.linalg.norm(n)
    return pts + rng.normal(0, noise, len(pts))[:, None] * n


def cylinder_points(rng, base, radius, height, spacing, noise=0.01):
    ang = np.arange(0, 2 * np.pi, spacing / radius)
    z = np.arange(0, height, spacing)
    A, Z = np.meshgrid(ang, z)
    r = radius + rng.normal(0, noise, A.size)
    return np.column_stack([base[0] + r * np.cos(A.ravel()), base[1] + r * np.sin(A.ravel()),
                            base[2] + Z.ravel()])


#: Ground truth for :func:`build_bridge`, in the synthetic frame (ft).
TRUTH = {
    "deck_z": 30.0, "soffit_z": 27.5, "deck_len": 150.0, "deck_wid": 36.0,
    "abutment_x": (-75.0, 75.0), "column_r": 2.0,
    "columns_xy": [(-25, -10), (-25, 10), (25, -10), (25, 10)],
    "ground_fn": lambda x, y: 0.01 * x + 0.5 * np.sin(y / 15.0),
}


def build_bridge(spacing=0.5, seed=1, speckle=200):
    rng = np.random.default_rng(seed)
    parts = []
    g = plane_points(rng, (0, 0, 0), (1, 0, 0), (0, 1, 0), 300, 120, spacing * 1.5, noise=0.04)
    g[:, 2] += TRUTH["ground_fn"](g[:, 0], g[:, 1])
    parts.append(g)
    parts.append(plane_points(rng, (0, 0, TRUTH["deck_z"]), (1, 0, 0), (0, 1, 0), 150, 36, spacing))
    parts.append(plane_points(rng, (0, 0, TRUTH["soffit_z"]), (1, 0, 0), (0, 1, 0), 150, 36, spacing))
    for y in (-18, 18):
        parts.append(plane_points(rng, (0, y, 31.5), (1, 0, 0), (0, 0, 1), 150, 3, spacing))
    for x in TRUTH["abutment_x"]:
        parts.append(plane_points(rng, (x, 0, 14), (0, 1, 0), (0, 0, 1), 40, 27, spacing))
    for x, y in ((-85, -20), (-85, 20), (85, -20), (85, 20)):
        parts.append(plane_points(rng, (x, y, 8), (1, 0, 0), (0, 0, 1), 20, 14, spacing))
    for x, y in TRUTH["columns_xy"]:
        parts.append(cylinder_points(rng, (x, y, 0), TRUTH["column_r"], 27.5, spacing))
    xyz = np.vstack(parts)
    if speckle:
        xyz = np.vstack([xyz, rng.uniform([-150, -60, 0], [150, 60, 35], (speckle, 3))])
    return xyz


@pytest.fixture(scope="session")
def bridge_xyz():
    """Synthetic-frame ``(N, 3)`` array (~130k points at 0.5 ft spacing)."""
    return build_bridge()


@pytest.fixture(scope="session")
def bridge_cloud(bridge_xyz):
    """The same bridge in a state-plane-like frame, re-based to local."""
    return PointCloud(bridge_xyz + np.array([1.5e6, 4.0e5, 700.0]),
                      intensity=np.full(len(bridge_xyz), 1000.0)).to_local()


@pytest.fixture
def rng():
    return np.random.default_rng(7)
