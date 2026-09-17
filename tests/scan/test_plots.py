#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Overview figures draw without error on a ScanFeatures result."""

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from civilpy.scan import extract_features
from civilpy.scan.cloud import PointCloud
from civilpy.scan import plots


@pytest.fixture(scope="module")
def result(bridge_cloud):
    return extract_features(bridge_cloud, voxel=0.5)


def test_plot_functions(result, tmp_path):
    ax = plots.plot_elevation(result)
    assert ax.get_xlabel().startswith("station")
    ax = plots.plot_plan(result)
    assert ax.get_aspect() == 1.0
    png = plots.save_overview(result, tmp_path / "o.png", title="synthetic")
    assert png.stat().st_size > 10_000


def test_plots_without_deck():
    tiny = PointCloud(np.random.default_rng(0).uniform(0, 5, (40, 3)))
    res = extract_features(tiny, outliers=False, ground=False, cylinders=False,
                           clearance_cell=0, ground_mesh_cell=None, edges=False, profile=False)
    assert plots.plot_elevation(res, max_points=10) is not None
    assert plots.plot_plan(res, max_points=10) is not None
