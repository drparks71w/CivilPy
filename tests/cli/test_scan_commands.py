#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""End-to-end ``scan`` command runs through the batch front end."""

import json

import pytest

from civilpy.cli.batch import execute
from civilpy.cli.commands.scan import _bbox
from civilpy.cli.registry import CliError
from civilpy.scan.cloud import PointCloud, write_ply
from tests.scan.conftest import build_bridge


@pytest.fixture(scope="module")
def bridge_ply(tmp_path_factory):
    xyz = build_bridge(spacing=0.5)
    p = tmp_path_factory.mktemp("scan") / "bridge.ply"
    write_ply(PointCloud(xyz + [1.5e6, 4e5, 700.0]), p, world=True)
    return p


def test_bbox_parsing():
    assert _bbox(None) is None
    assert _bbox("1,2,3,4") == (1.0, 2.0, 3.0, 4.0)
    with pytest.raises(CliError):
        _bbox("1,2,3")
    with pytest.raises(CliError):
        _bbox("a,b,c,d")


def test_extract_ply_and_exports(bridge_ply, tmp_path, capsys):
    dxf = tmp_path / "f.dxf"
    js = tmp_path / "f.json"
    assert execute(["scan", "extract", str(bridge_ply), "--voxel", "0.5",
                    "--dxf", str(dxf), "--json-out", str(js)]) == 0
    out = capsys.readouterr().out
    assert "Scan overview" in out and "Planes" in out and "Cylinders" in out
    assert dxf.exists()
    report = json.loads(js.read_text())
    assert report["summary"]["roles"]["column"] == 4
    assert report["summary"]["n_spans"] == 3


def test_extract_errors(tmp_path, capsys):
    assert execute(["scan", "extract", str(tmp_path / "missing.ply")]) != 0
    (tmp_path / "x.pod").write_bytes(b"\0")
    assert execute(["scan", "extract", str(tmp_path / "x.pod")]) != 0
    assert execute(["scan", "info", str(tmp_path / "missing.las")]) != 0


laspy = pytest.importorskip("laspy")


def test_info_and_extract_las(tmp_path, capsys):
    from civilpy.scan.cloud import write_las

    xyz = build_bridge(spacing=1.0, speckle=0)
    las = write_las(PointCloud(xyz + [1.5e6, 4e5, 700.0]), tmp_path / "b.las")
    assert execute(["scan", "info", str(las)]) == 0
    out = capsys.readouterr().out
    assert "points" in out and "x range" in out
    assert execute(["scan", "extract", str(las), "--voxel", "1.0", "--no-ground",
                    "--bbox", "1500000,400000,1500100,400100", "--plane-min-points", "50",
                    "--cylinder-min-points", "50"]) == 0
    assert "Scan overview" in capsys.readouterr().out
    assert execute(["scan", "extract", str(las), "--bbox", "0,0,1,1"]) != 0
    assert "no points" in capsys.readouterr().out.lower()
