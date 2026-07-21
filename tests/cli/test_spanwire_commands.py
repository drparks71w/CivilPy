#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""End-to-end ``spanwire`` command runs through the batch front end."""

import json

import pytest

from civilpy.cli.batch import execute


def test_catalog_lists_signals(capsys):
    assert execute(["spanwire", "catalog"]) == 0
    out = capsys.readouterr().out
    assert "3BA" in out and "Aluminum" in out


def test_catalog_filter_and_kinds(capsys):
    assert execute(["spanwire", "catalog", "--kind", "wires",
                    "--match", "messenger"]) == 0
    out = capsys.readouterr().out
    assert "WM3" in out and "SS1" not in out

    assert execute(["spanwire", "catalog", "--kind", "signs"]) == 0
    assert "Blankout" in capsys.readouterr().out

    assert execute(["spanwire", "catalog", "--match", "zzz-no-match"]) == 0
    assert "no catalog entries" in capsys.readouterr().out


def test_simple_span_closed_form(capsys):
    # W = 100 at midspan of 100 ft, weightless, sag 5 -> H = 500 lb
    assert execute([
        "spanwire", "simple", "100", "--sag", "5",
        "--wire-weight", "0", "--loads", "50:100",
    ]) == 0
    out = capsys.readouterr().out
    assert "500.00" in out
    assert "legacy design factor" in out


def test_simple_span_with_catalog_signals_and_clearance(capsys):
    assert execute([
        "spanwire", "simple", "100", "--sag", "5",
        "--signals", "30:3BA,60:5CA", "--clearance", "20.5",
    ]) == 0
    out = capsys.readouterr().out
    assert "attachment elevation" in out.lower()
    assert "base moment" in out.lower()
    assert "3BA" in out


def test_simple_bad_specs_exit_2(capsys):
    assert execute(["spanwire", "simple", "100", "--sag", "5",
                    "--loads", "nope"]) == 2
    assert "bad load spec" in capsys.readouterr().out
    assert execute(["spanwire", "simple", "100", "--sag", "5",
                    "--signals", "30:XXX"]) == 2
    assert "unknown signal code" in capsys.readouterr().out
    assert execute(["spanwire", "simple", "100", "--sag", "5",
                    "--signals", "bad"]) == 2
    assert "use x:CODE" in capsys.readouterr().out
    # no load at all -> solver error surfaced as CLI error
    assert execute(["spanwire", "simple", "100", "--sag", "5",
                    "--wire-weight", "0"]) == 2
    assert "no load" in capsys.readouterr().out


def test_wye_symmetric(capsys):
    assert execute([
        "spanwire", "wye", "100,100,100", "--bearings", "90,210,330",
        "--sag", "5", "--wire-weight", "0",
        "--loads", "1:50:100;2:50:100;3:50:100",
        "--clearance", "20.5",
    ]) == 0
    out = capsys.readouterr().out
    assert "1000.0" in out          # stringing tension on every pole
    assert "1.00000" in out         # tension relations
    assert "25.50" in out           # attachment elevation


def test_wye_signal_spec_and_errors(capsys):
    assert execute([
        "spanwire", "wye", "100,100,100", "--bearings", "90,210,330",
        "--sag", "5", "--signals", "1:30:3BA;2:30:3BA;3:30:3BA",
    ]) == 0
    assert "P1R1" in capsys.readouterr().out

    assert execute(["spanwire", "wye", "100,100", "--bearings", "90,210,330",
                    "--sag", "5"]) == 2
    assert "exactly 3" in capsys.readouterr().out
    assert execute(["spanwire", "wye", "a,b,c", "--bearings", "90,210,330",
                    "--sag", "5"]) == 2
    assert "bad lengths" in capsys.readouterr().out
    assert execute(["spanwire", "wye", "100,100,100",
                    "--bearings", "90,210,330", "--sag", "5",
                    "--loads", "9:50:100"]) == 2
    assert "unknown segments" in capsys.readouterr().out
    assert execute(["spanwire", "wye", "100,100,100",
                    "--bearings", "90,210,330", "--sag", "5",
                    "--loads", "x:50:100"]) == 2
    assert "bad leg prefix" in capsys.readouterr().out


BOX_CONFIG = {
    "configuration": "box",
    "rings": [[0, 0], [40, 0], [40, 40], [0, 40]],
    "tail_lengths": [20, 20, 20, 20],
    "tail_bearings": [225, 325, 45, 135],   # tail 2 mis-set 10 degrees
    "wire_weight_plf": 0.0,
    "required_sag_ft": 4.0,
    "loads": {
        "R1R2": [{"x_ft": 20, "signal": "3BA"}],
        "R3R4": [{"x_ft": 20, "weight_lb": 90, "area_sqft": 2.3}],
    },
    "clearance_ft": 20.5,
}


@pytest.fixture()
def box_file(tmp_path):
    path = tmp_path / "box.json"
    path.write_text(json.dumps(BOX_CONFIG))
    return path


def test_system_box_reports_balance_rotation(box_file, capsys):
    assert execute(["spanwire", "system", str(box_file)]) == 0
    out = capsys.readouterr().out
    assert "rotate P2 10.0 degrees clockwise" in out
    assert "P2R2" in out and "R4R1" in out


def test_system_wye_and_custom(tmp_path, capsys):
    wye = {"configuration": "wye", "lengths": [100, 100, 100],
           "bearings": [90, 210, 330], "required_sag_ft": 5.0,
           "loads": {"P1R1": [{"x_ft": 50, "weight_lb": 100}]}}
    path = tmp_path / "wye.json"
    path.write_text(json.dumps(wye))
    assert execute(["spanwire", "system", str(path)]) == 0
    assert "in balance" not in capsys.readouterr().out  # open shape: no note

    custom = {
        "configuration": "custom",
        "poles": {"P1": [0, 0], "P2": [100, 0]},
        "segments": [{"name": "S1", "start": "P1", "end": "P2"}],
        "loads": {"S1": [{"x_ft": 50, "weight_lb": 100}]},
        "required_sag_ft": 5.0,
    }
    path2 = tmp_path / "custom.json"
    path2.write_text(json.dumps(custom))
    assert execute(["spanwire", "system", str(path2)]) == 0
    assert "500.0" in capsys.readouterr().out


def test_system_error_paths(tmp_path, capsys):
    assert execute(["spanwire", "system", "missing.json"]) == 2
    assert "no such file" in capsys.readouterr().out

    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert execute(["spanwire", "system", str(bad)]) == 2
    assert "invalid JSON" in capsys.readouterr().out

    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(json.dumps({"configuration": "wye"}))
    assert execute(["spanwire", "system", str(incomplete)]) == 2
    assert "missing key" in capsys.readouterr().out

    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps({"configuration": "octagon",
                                   "required_sag_ft": 3}))
    assert execute(["spanwire", "system", str(unknown)]) == 2
    assert "unknown configuration" in capsys.readouterr().out

    bad_signal = tmp_path / "sig.json"
    config = dict(BOX_CONFIG, loads={"R1R2": [{"x_ft": 20, "signal": "XX"}]})
    bad_signal.write_text(json.dumps(config))
    assert execute(["spanwire", "system", str(bad_signal)]) == 2
    assert "unknown signal code" in capsys.readouterr().out
