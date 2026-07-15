#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""End-to-end command runs through the batch front end."""

import pytest

from civilpy.cli.batch import execute, one_shot_line
from civilpy.cli.registry import find_spec
from civilpy.cli.session import CliContext

from tests.geotechnical.test_boring import DIGGS_FIXTURE


@pytest.fixture()
def diggs_file(tmp_path):
    path = tmp_path / "B-001.xml"
    path.write_text(DIGGS_FIXTURE)
    return path


def test_odot_slab_simple(capsys):
    assert execute(["odot", "slab", "20"]) == 0
    out = capsys.readouterr().out
    assert "16.25" in out  # 20 ft simple-span deck thickness
    assert "#8" in out     # A bar


def test_odot_slab_bad_span_exits_2(capsys):
    assert execute(["odot", "slab", "99"]) == 2
    assert "not available" in capsys.readouterr().out


def test_hydro_channel_matches_doctest_values(capsys):
    assert execute([
        "hydro", "channel", "200", "--width", "10",
        "--n", "0.013", "--slope", "0.002",
    ]) == 0
    out = capsys.readouterr().out
    assert "2.316" in out  # critical depth from open_channel docstring


def test_road_vcurve_k_value(capsys):
    assert execute([
        "road", "vcurve", "--g1", "2", "--g2", "-1.5", "--length", "600",
    ]) == 0
    out = capsys.readouterr().out
    assert "171.43" in out  # K = 600 / 3.5


def test_road_hcurve_tangent(capsys):
    assert execute(["road", "hcurve", "--radius", "1000", "--delta", "35"]) == 0
    assert "315.30" in capsys.readouterr().out  # T = R tan(Δ/2)


def test_boring_parse_writes_xlsx(diggs_file, tmp_path, capsys):
    openpyxl = pytest.importorskip("openpyxl")
    out = tmp_path / "boring.xlsx"
    assert execute(["boring", "parse", str(diggs_file), "-o", str(out)]) == 0
    wb = openpyxl.load_workbook(out)
    assert "Boreholes" in wb.sheetnames and "provenance" in wb.sheetnames
    spt = wb["SPT"]
    assert spt["E2"].value == 24  # N from the fixture's 12/14/10 drive


def test_boring_parse_missing_file(capsys):
    assert execute(["boring", "parse", "does-not-exist.xml"]) == 2
    assert "no such file" in capsys.readouterr().out


def test_scour_pier_reads_boring_gradation(diggs_file, capsys):
    assert execute([
        "hydro", "scour-pier", "--velocity", "6.2", "--depth", "8",
        "--pier-width", "3", "--boring", str(diggs_file),
        "--bed-depth", "1.5",
    ]) == 0
    out = capsys.readouterr().out
    assert "0.18" in out  # D50 from the fixture gradation


def test_scour_pier_resolves_loaded_boring(diggs_file, capsys):
    ctx = CliContext(interactive=True)
    ctx.workspace.load(str(diggs_file))
    (name,) = ctx.workspace.objects
    assert execute([
        "hydro", "scour-pier", "--velocity", "6.2", "--depth", "8",
        "--pier-width", "3", "--boring", name,
    ], ctx=ctx) == 0
    assert "Local pier scour" in capsys.readouterr().out


def test_one_shot_line_skips_defaults():
    spec = find_spec("hydro", "scour-pier")
    line = one_shot_line(spec, {
        "velocity": 6.2, "depth": 8.0, "pier_width": 3.0,
        "shape": "round", "skew": 0.0, "boring": None,
        "bed_depth": 0.0, "pier_length": None,
    }, out=None)
    assert line == (
        "civilpy hydro scour-pier --velocity 6.2 --depth 8.0 --pier-width 3.0"
    )
