#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""End-to-end extraction on the synthetic bridge and the report object."""

import json

import numpy as np
import pytest

from civilpy.scan import extract_features
from civilpy.scan.cloud import PointCloud
from civilpy.scan.pipeline import ScanFeatures
from tests.scan.conftest import TRUTH


@pytest.fixture(scope="module")
def result(bridge_cloud):
    log = []
    res = extract_features(bridge_cloud, voxel=0.5, log=log.append)
    res.log = log
    return res


def test_pipeline_finds_the_bridge(result):
    s = result.summary()
    assert s["assigned_fraction"] > 0.97
    roles = s["roles"]
    assert roles["deck"] == 1 and roles["soffit"] == 1 and roles["abutment"] == 2
    assert roles["wingwall"] == 4 and roles["barrier"] == 2 and roles["column"] == 4
    off = result.origin
    deck = result.deck
    assert deck.elevation + off[2] == pytest.approx(700 + TRUTH["deck_z"], abs=0.05)
    assert deck.extent_u == pytest.approx(TRUTH["deck_len"], abs=1.0)
    assert deck.extent_v == pytest.approx(TRUTH["deck_wid"], abs=1.0)
    for c in result.cylinders:
        assert c.radius == pytest.approx(TRUTH["column_r"], abs=0.05)
        assert c.tilt_deg < 1.0
    found = sorted((round(c.center[0] + off[0] - 1.5e6), round(c.center[1] + off[1] - 4e5))
                   for c in result.cylinders)
    assert found == sorted(TRUTH["columns_xy"])
    assert s["min_clearance"]["clearance"] == pytest.approx(26.2, abs=0.6)
    assert abs(result.axis_direction[0]) > 0.999
    assert len(result.edges) >= 8                          # deck/barrier, soffit/abutment, abutment/wingwall
    assert any(p.name == "deck_profile" for p in result.polylines)
    assert result.ground_mesh is not None and result.ground_mesh.n_faces > 100
    assert [u.role for u in result.units] == ["abutment", "pier", "pier", "abutment"]
    assert s["n_spans"] == 3 and all(abs(L - 50) <= 2.0 for L in s["span_lengths"])
    assert s["superstructure_depth"] == pytest.approx(2.5, abs=0.6)
    assert len(s["units"]) == 4 and result.by_role("pier") == result.units[1:3]
    assert result.clusters.max() >= 0 and len(result.cluster_index) == len(result.clusters)
    assert any("ground:" in line for line in result.log)
    assert result.by_role("column") == result.cylinders


def test_report_serialisation_and_exports(result, tmp_path):
    d = result.to_dict()
    assert len(d["planes"]) == len(result.planes) and d["summary"]["n_cylinders"] == 4
    p = result.save_json(tmp_path / "r.json")
    back = json.loads(p.read_text())
    assert back["summary"]["roles"]["deck"] == 1
    dxf = result.export_dxf(tmp_path / "r.dxf", points=True)
    assert dxf.stat().st_size > 10_000
    files = result.export_meshes(tmp_path / "meshes", fmt="obj", world=True)
    assert len(files) == len(result.planes) + len(result.cylinders) + len(result.units) + 1
    assert len(d["units"]) == 4 and len(d["spans"]) == 3
    pytest.importorskip("rhino3dm")
    assert result.export_3dm(tmp_path / "r.3dm").exists()


def test_pipeline_degenerate_inputs():
    tiny = PointCloud(np.random.default_rng(0).uniform(0, 5, (30, 3)))
    res = extract_features(tiny, outliers=False, ground=False, cylinders=False,
                           clearance_cell=0, ground_mesh_cell=None, edges=False, profile=False)
    assert isinstance(res, ScanFeatures) and res.planes == [] and res.cylinders == []
    assert res.summary()["n_ground"] == 0 and res.deck is None
    assert res.unassigned.all()
    empty = extract_features(PointCloud(np.zeros((0, 3))), outliers=False, clearance_cell=0)
    assert empty.summary()["n_points"] == 0 and empty.summary()["assigned_fraction"] == 0.0


def test_pipeline_options(bridge_cloud):
    sub = bridge_cloud.select(bridge_cloud.xyz[:, 2] > 20)     # deck, barriers, column tops
    res = extract_features(sub, outliers=False, ground=False, cylinders=True,
                           cylinder_min_points=100, plane_connect=1.5, cluster_radius=1.5,
                           boundary_alpha=2.0, clearance_cell=2.0, ground_mesh_cell=None,
                           profile=True)
    assert res.deck is not None and res.deck.boundary is not None
    assert res.summary()["n_ground"] == 0
    assert res.params["boundary_alpha"] == 2.0
