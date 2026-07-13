#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Geometry tests for the HW-2.1 cast-in-place headwall solid.

The dimension-table lookups are covered in test_odot_rocker_headwall.py;
this module tests the parametric ``layout_headwall`` generator behind the
HW-2.1 Grasshopper component."""

import pytest

from civilpy.structural.odot import headwall as hw
from civilpy.structural.odot.headwall import (
    HeadwallInput,
    layout_headwall,
    headwall_for_diameter,
)


def test_dimensions_from_table():
    lay = layout_headwall(HeadwallInput(24.0))
    row = headwall_for_diameter(24.0)
    assert lay.width_ft == pytest.approx(row.width / 12.0)
    assert lay.height_ft == pytest.approx(row.height / 12.0)
    assert lay.base_thickness_ft == pytest.approx(row.thickness / 12.0)
    assert lay.top_thickness_ft == pytest.approx(1.0)  # 12 in top
    assert lay.concrete_cy == pytest.approx(row.concrete_cy)


def test_front_outline_is_full_rectangle():
    lay = layout_headwall(HeadwallInput(24.0))
    W, H = lay.width_ft, lay.height_ft
    assert lay.front_outline == (
        (-W / 2.0, 0.0, 0.0), (W / 2.0, 0.0, 0.0),
        (W / 2.0, 0.0, H), (-W / 2.0, 0.0, H))
    # all points on the front face (y = 0)
    assert all(p[1] == 0.0 for p in lay.front_outline)


def test_side_profile_battered_back():
    lay = layout_headwall(HeadwallInput(24.0))
    T, Tt, H = lay.base_thickness_ft, lay.top_thickness_ft, lay.height_ft
    (base_f, top_f, top_b, base_b) = lay.side_profile
    # front face vertical at y = 0, base and top
    assert base_f[1] == 0.0 and top_f[1] == 0.0
    assert base_f[2] == pytest.approx(0.0) and top_f[2] == pytest.approx(H)
    # back face: 12 in (Tt) at the top, T at the base -> battered
    assert top_b[1] == pytest.approx(-Tt)
    assert base_b[1] == pytest.approx(-T)
    assert T >= Tt  # base is never thinner than the 12 in top


def test_pipe_opening_placement():
    lay = layout_headwall(HeadwallInput(24.0))
    D = 24.0 / 12.0
    assert lay.pipe_diameter_ft == pytest.approx(D)
    # centred on the wall, invert at the flow line (z = 0) -> centre at D/2
    assert lay.pipe_center[0] == pytest.approx(0.0)
    assert lay.pipe_center[2] == pytest.approx(D / 2.0)
    # centre buried mid-thickness
    assert lay.pipe_center[1] == pytest.approx(-lay.base_thickness_ft / 2.0)


def test_cover_equals_h_minus_d():
    lay = layout_headwall(HeadwallInput(24.0))
    assert lay.cover_in == pytest.approx(lay.table.height - 24.0)
    assert lay.cover_in >= hw.MIN_COVER_IN


def test_boundary_48in_is_exactly_min_cover():
    # D = 48 in is the last treatment-"A" circular size: cover = 6 in.
    lay = layout_headwall(HeadwallInput(48.0))
    assert lay.cover_in == pytest.approx(hw.MIN_COVER_IN)


def test_treatment_b_size_raises():
    # D = 54 in leaves 3 in cover -> end treatment "B", not modeled.
    with pytest.raises(ValueError, match="treatment 'B'"):
        layout_headwall(HeadwallInput(54.0))


def test_untabulated_diameter_raises():
    with pytest.raises(KeyError):
        layout_headwall(HeadwallInput(13.0))


def test_concrete_table_selected():
    lay = layout_headwall(HeadwallInput(24.0, concrete=True))
    assert lay.table is headwall_for_diameter(24.0, concrete=True)


def test_provenance():
    assert hw.SCD == "HW-2.1"
    assert "HW-2.1" in hw.__doc__
