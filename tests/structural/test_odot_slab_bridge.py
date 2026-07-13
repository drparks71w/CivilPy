#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT SB-1-24 single span slab bridge catalog
(rev. 01-16-2026)."""

import math

import pytest

from civilpy.structural.odot import slab_bridge as sb
from civilpy.structural.odot.slab_bridge import (
    SlabBridgeInput,
    bridge_length_ft,
    edge_beam_design,
    layout_slab_bridge,
    slab_design,
    standard_hook_bar_length_ft,
)


def test_provenance():
    assert sb.SCD == "SB-1-24"
    assert sb.REVISION == "01-16-2026"
    assert "SB-1-24" in sb.__doc__


def test_design_data_matches_notes():
    assert sb.ROADWAY_WIDTH_MIN_FT == 24.0
    assert sb.SKEW_MAX_DEG == 25.0
    assert sb.FUTURE_WEARING_SURFACE_PSF == 60.0
    assert sb.WEARING_SURFACE_THICKNESS_IN == 1.0
    assert sb.CONCRETE_STRENGTH_PSI == 4500.0
    assert sb.REBAR_YIELD_PSI == 60000.0
    assert sb.LAP_SPLICE_FT[5]["top"] == pytest.approx(3 + 10 / 12.0)
    assert sb.LAP_SPLICE_FT[10]["bot"] == pytest.approx(10 + 11 / 12.0)


def test_table_spans_11_to_38():
    assert set(sb.SLAB_DESIGNS) == set(range(11, 39))
    assert set(sb.EDGE_BEAM_DESIGNS) == set(range(11, 39))


def test_slab_data_spot_check():
    d11 = slab_design(11)
    assert d11.thickness_in == pytest.approx(11 + 1 / 4.0)
    assert (d11.a_bar.spacing_in, d11.a_bar.size) == (6, 7)
    assert (d11.b_bar.spacing_in, d11.b_bar.size) == (12.0, 5)
    assert (d11.m_bar.spacing_in, d11.m_bar.size) == (10.0, 5)
    assert (d11.n_bar.spacing_in, d11.n_bar.size) == (12.0, 5)

    d38 = slab_design(38)
    assert d38.thickness_in == pytest.approx(26.0)
    assert (d38.a_bar.spacing_in, d38.a_bar.size) == (7, 10)

    d26 = slab_design(26)
    assert (d26.a_bar.spacing_in, d26.a_bar.size) == (7, 9)


def test_edge_beam_data_spot_check():
    e11 = edge_beam_design(11)
    assert e11.over_the_side == sb.EdgeBarSpec(20, 45, 7, 8)
    assert e11.parapet == sb.EdgeBarSpec(18, 57, 7, 8)

    e38 = edge_beam_design(38)
    assert e38.over_the_side == sb.EdgeBarSpec(26, 48, 10, 10)
    assert e38.parapet == sb.EdgeBarSpec(26, 63, 10, 12)

    e24 = edge_beam_design(24)
    assert e24.parapet.depth_in == pytest.approx(18 + 1 / 4.0)


def test_lookup_guards_untabulated_span():
    with pytest.raises(ValueError, match="11-38"):
        slab_design(10)
    with pytest.raises(ValueError, match="11-38"):
        edge_beam_design(39)


def test_standard_hook_bar_length():
    assert standard_hook_bar_length_ft(24) == pytest.approx(24 + 10 / 12.0)


def test_bridge_length_formula():
    assert bridge_length_ft(24, 0.0) == pytest.approx(25.5)
    cos30 = math.cos(math.radians(30.0))
    assert bridge_length_ft(24, 30.0) == pytest.approx(24 + 1.5 / cos30)


def test_layout_guards():
    with pytest.raises(ValueError, match="11-38"):
        layout_slab_bridge(SlabBridgeInput(span_ft=9, width_ft=30.0))
    with pytest.raises(ValueError, match="edge_condition"):
        layout_slab_bridge(
            SlabBridgeInput(span_ft=24, width_ft=30.0, edge_condition="nope"))
    with pytest.raises(ValueError, match="25"):
        layout_slab_bridge(
            SlabBridgeInput(span_ft=24, width_ft=30.0, skew_deg=30.0))


def test_layout_square_bridge():
    lay = layout_slab_bridge(SlabBridgeInput(span_ft=24, width_ft=30.0))
    assert lay.outline == ((0.0, 0.0, 0.0), (0.0, 30.0, 0.0),
                           (25.5, 30.0, 0.0), (25.5, 0.0, 0.0))
    assert lay.thickness_in == pytest.approx(18 + 1 / 4.0)
    assert lay.bridge_length_ft == pytest.approx(25.5)
    assert lay.edge_beam == sb.EdgeBarSpec(20, 48, 9, 9)
    marks = {b.mark for b in lay.bars}
    assert marks == {"A", "B", "M", "N"}


def test_layout_parapet_edge_condition():
    lay = layout_slab_bridge(
        SlabBridgeInput(span_ft=24, width_ft=30.0, edge_condition="parapet"))
    assert lay.edge_beam == sb.EdgeBarSpec(18 + 1 / 4.0, 60, 9, 10)


def test_layout_skewed_shears_outline():
    lay = layout_slab_bridge(SlabBridgeInput(span_ft=24, width_ft=30.0, skew_deg=20.0))
    tan20 = math.tan(math.radians(20.0))
    assert lay.outline[1][0] == pytest.approx(30.0 * tan20)
    L = bridge_length_ft(24, 20.0)
    assert lay.outline[2][0] == pytest.approx(L + 30.0 * tan20)


def test_layout_bar_counts_scale_with_width_and_spacing():
    lay = layout_slab_bridge(SlabBridgeInput(span_ft=24, width_ft=30.0))
    a_bars = [b for b in lay.bars if b.mark == "A"]
    d = slab_design(24)
    usable = 30.0 - 0.5
    expected_min = usable * 12.0 / d.a_bar.spacing_in
    assert len(a_bars) >= expected_min


def test_layout_top_bars_above_bottom_bars():
    lay = layout_slab_bridge(SlabBridgeInput(span_ft=24, width_ft=30.0))
    a_z = next(b for b in lay.bars if b.mark == "A").points[0][2]
    b_z = next(b for b in lay.bars if b.mark == "B").points[0][2]
    assert b_z > a_z
