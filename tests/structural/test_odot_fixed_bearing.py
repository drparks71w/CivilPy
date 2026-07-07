#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT FB-1-82 fixed bearing catalog (rev. 07-19-2024)."""

import pytest

# NOTE: fixed_bearing.py defines a lookup function also named
# `fixed_bearing`, and civilpy.structural.odot's __init__ imports that
# function into the package namespace -- so `from civilpy.structural.odot
# import fixed_bearing as fb` (or `import civilpy.structural.odot.
# fixed_bearing as fb`) silently binds `fb` to the *function*, not the
# module (the package attribute gets overwritten after the submodule
# import side effect). Import the module's names directly instead.
from civilpy.structural.odot.fixed_bearing import (
    ALLOWABLE_BEARING_STRESS_PSI,
    ANCHOR_ROD_DIA_IN,
    ANCHOR_ROD_LENGTH_IN,
    FIXED_BEARINGS,
    REVISION,
    SCD,
    __doc__ as _MODULE_DOC,
    fixed_bearing,
    lateral_clearance_in,
    layout_fixed_bearing,
    smallest_for_load,
)


def test_provenance():
    assert SCD == "FB-1-82"
    assert REVISION == "07-19-2024"
    assert "FB-1-82" in _MODULE_DOC


def test_design_data():
    assert ANCHOR_ROD_DIA_IN == 1.25
    assert ANCHOR_ROD_LENGTH_IN == pytest.approx(19.0)
    assert ALLOWABLE_BEARING_STRESS_PSI == 30000.0


def test_designations_present():
    assert set(FIXED_BEARINGS) == {
        "F-50", "F-100", "F-150", "F-200", "F-250", "F-300", "F-350", "F-400",
    }


def test_f50_two_anchor_rods():
    r = fixed_bearing("F-50")
    assert r.two_anchor_rods
    assert r.max_load_lb == 50_000
    assert r.dims["DIA"] == 2.0
    assert r.weight_lb == 100


def test_f150_no_special_notes():
    r = fixed_bearing("F-150")
    assert not r.two_anchor_rods
    assert not r.stiffeners_required
    assert r.dims["K"] == pytest.approx(6 + 7 / 8.0)


def test_f350_f400_require_stiffeners():
    assert fixed_bearing("F-350").stiffeners_required
    assert fixed_bearing("F-400").stiffeners_required
    assert not fixed_bearing("F-300").stiffeners_required


def test_lookup_guards_unknown_designation():
    with pytest.raises(ValueError, match="F-50"):
        fixed_bearing("F-999")


def test_smallest_for_load():
    assert smallest_for_load(120_000).designation == "F-150"
    assert smallest_for_load(150_000).designation == "F-150"  # exact match
    assert smallest_for_load(151_000).designation == "F-200"


def test_smallest_for_load_overflow():
    with pytest.raises(ValueError):
        smallest_for_load(500_000)


def test_lateral_clearance():
    assert lateral_clearance_in(30.0) == pytest.approx(0.125)
    assert lateral_clearance_in(90.0) == pytest.approx(0.25)


def test_layout_stack_is_self_consistent():
    r = fixed_bearing("F-150")
    lay = layout_fixed_bearing(r)
    pin_bottom = lay.pin_center[2] - lay.pin_diameter_in / 2.0
    assert pin_bottom >= lay.base_thickness_in - 1e-9
    assert lay.top_z_in > lay.pin_center[2]


def test_layout_base_outline_matches_f_g():
    r = fixed_bearing("F-200")
    lay = layout_fixed_bearing(r)
    F, G = r.dims["F"], r.dims["G"]
    assert lay.base_outline[1][0] - lay.base_outline[0][0] == pytest.approx(F)
    assert lay.base_outline[2][1] - lay.base_outline[1][1] == pytest.approx(G)


def test_layout_top_outline_matches_a_b():
    r = fixed_bearing("F-300")
    lay = layout_fixed_bearing(r)
    A, B = r.dims["A"], r.dims["B"]
    assert lay.top_outline[1][0] - lay.top_outline[0][0] == pytest.approx(A)
    assert lay.top_outline[2][1] - lay.top_outline[1][1] == pytest.approx(B)


def test_layout_notes_flag_stiffeners():
    lay = layout_fixed_bearing(fixed_bearing("F-400"))
    assert any("stiffeners" in n for n in lay.notes)
