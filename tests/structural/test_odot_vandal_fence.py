#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT VPF-1-24 vandal protection fence catalog
(rev. 01-17-2025)."""

import pytest

from civilpy.structural.odot import vandal_fence as vf
from civilpy.structural.odot.vandal_fence import (
    FenceRunInput,
    layout_fence_run,
    post_section,
)


def test_provenance():
    assert vf.SCD == "VPF-1-24"
    assert vf.REVISION == "01-17-2025"
    assert "VPF-1-24" in vf.__doc__


def test_material_constants():
    assert vf.LINE_POST_OD_IN == 2.880
    assert vf.RAIL_OD_IN == 1.660
    assert vf.FABRIC_MESH_IN == 1.0
    assert vf.PAY_ITEM == ("607", "FOOT", "VANDAL PROTECTION FENCE")


def test_post_sections_present():
    assert set(vf.POST_SECTIONS) == {"PS-1", "PS-2/BP-1", "PS-2/BP-2"}


def test_ps1_curved_section():
    s = post_section("PS-1")
    assert s.curved
    assert s.max_spacing_ft == 7.0
    assert s.curve_radius_ft == pytest.approx(2 + 8 / 12.0)


def test_ps2_spacing_differs_by_base_plate():
    bp1 = post_section("PS-2/BP-1")
    bp2 = post_section("PS-2/BP-2")
    assert bp1.max_spacing_ft == 10.0
    assert bp2.max_spacing_ft == 5.0
    assert bp1.height_ft == bp2.height_ft == 6.0


def test_lookup_guards_unknown_name():
    with pytest.raises(ValueError, match="PS-1"):
        post_section("PS-99")


def test_layout_guards():
    with pytest.raises(ValueError, match="length_ft"):
        layout_fence_run(FenceRunInput(length_ft=0.0))
    with pytest.raises(ValueError, match="5 ft max"):
        layout_fence_run(FenceRunInput(length_ft=10.0, post_name="PS-2/BP-2",
                                       spacing_ft=8.0))


def test_layout_posts_never_exceed_max_spacing():
    lay = layout_fence_run(FenceRunInput(length_ft=63.0, post_name="PS-2/BP-1"))
    spacings = [b - a for a, b in zip(lay.post_stations_ft, lay.post_stations_ft[1:])]
    assert max(spacings) <= 10.0 + 1e-9
    assert lay.post_stations_ft[0] == 0.0
    assert lay.post_stations_ft[-1] == pytest.approx(63.0)


def test_layout_rails_span_full_length():
    lay = layout_fence_run(FenceRunInput(length_ft=40.0, post_name="PS-1"))
    assert lay.top_rail[1][0] == pytest.approx(40.0)
    assert lay.top_rail[0][2] == pytest.approx(lay.section.height_ft)
    assert lay.bottom_rail[0][2] == 0.0
