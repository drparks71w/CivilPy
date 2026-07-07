#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT CS-1-24 continuous slab bridge catalog
(rev. 01-16-2026)."""

import math

import pytest

from civilpy.structural.odot import continuous_slab_bridge as csb
from civilpy.structural.odot.continuous_slab_bridge import (
    ContinuousSlabInput,
    cs_slab_design,
    interior_span_ft,
    layout_continuous_slab,
    m_bar_offset_in,
)


def test_provenance():
    assert csb.SCD == "CS-1-24"
    assert csb.REVISION == "01-16-2026"
    assert "CS-1-24" in csb.__doc__


def test_design_data_matches_notes():
    assert csb.ROADWAY_WIDTH_MIN_FT == 24.0
    assert csb.SKEW_MAX_DEG == 25.0
    assert csb.FUTURE_WEARING_SURFACE_PSF == 60.0
    assert csb.CONCRETE_STRENGTH_PSI == 4500.0
    assert csb.REBAR_YIELD_PSI == 60000.0
    assert csb.INTERIOR_SPAN_RATIO == 1.25


def test_lap_splice_table():
    assert csb.LAP_SPLICE_FT[4]["single"] == 3.0
    assert csb.LAP_SPLICE_FT[6]["single"] == pytest.approx(4 + 4 / 12.0)
    assert csb.LAP_SPLICE_FT[9]["top"] == pytest.approx(7 + 4 / 12.0)
    assert csb.LAP_SPLICE_FT[10]["bot"] == pytest.approx(10 + 11 / 12.0)


def test_interior_span_ratio():
    assert interior_span_ft(14) == pytest.approx(17.5)
    assert interior_span_ft(46) == pytest.approx(57.5)


def test_m_bar_offset_formula():
    # Y = 1/2 * [bridge limits - (n_m_bars - 1) * spacing] * 12
    y = m_bar_offset_in(100.0, 11, 9.0)
    assert y == pytest.approx(0.5 * (100.0 - 10 * 9.0) * 12.0)


def test_table_has_all_end_spans_14_to_46():
    assert set(csb.CS_SLAB_DESIGNS) == set(range(14, 47))


def test_slab_data_spot_check_row14():
    d = cs_slab_design(14)
    assert d.thickness_in == 11
    assert (d.a_bar.spacing_in, d.a_bar.size) == (7, 8)
    assert d.a_bar.a_ft == "16'-7\""
    assert d.a_bar.length_ft == pytest.approx(17.5)
    assert (d.b_bar.spacing_in, d.b_bar.size, d.b_bar.length_ft) == (7, 8, 21.5)
    assert (d.c_bar.spacing_in, d.c_bar.size) == (7, 5)
    assert d.e_bar is None
    assert (d.n_bar.spacing_in, d.n_bar.size, d.n_bar.count) == (15.0, 6, 47)
    assert (d.m_bar.spacing_in, d.m_bar.size, d.m_bar.count) == (12.0, 4, 47)
    assert d.u_bar_count == 78


def test_slab_data_e_bar_appears_starting_span22():
    assert cs_slab_design(21).e_bar is None
    e22 = cs_slab_design(22).e_bar
    assert (e22.size, e22.spacing_in) == (5, 7)
    assert e22.length_ft == pytest.approx(9 + 11 / 12.0)


def test_slab_data_d_bar_size_steps_independently_of_thickness():
    # D-bar size steps 8 -> 9 -> 10 at spans 30 and 38, which do NOT line
    # up with the A/B-bar thickness-based size thresholds (span 35, 45).
    assert cs_slab_design(29).d_bar.size == 8
    assert cs_slab_design(30).d_bar.size == 9
    assert cs_slab_design(37).d_bar.size == 9
    assert cs_slab_design(38).d_bar.size == 10
    assert cs_slab_design(46).d_bar.size == 10
    # meanwhile A/B are still size 8 at span 30 (their own threshold is 35)
    assert cs_slab_design(30).a_bar.size == 8


def test_slab_data_m_bar_size_steps_at_span32():
    assert cs_slab_design(31).m_bar.size == 4
    assert cs_slab_design(32).m_bar.size == 5


def test_slab_data_spot_check_row46():
    d = cs_slab_design(46)
    assert d.thickness_in == 27
    assert (d.a_bar.spacing_in, d.a_bar.size) == (7, 10)
    assert d.a_bar.a_ft == "49'-1\""
    assert d.d_bar.size == 10
    assert d.d_bar.length_ft == pytest.approx(47 + 9 / 12.0)
    assert d.e_bar.length_ft == pytest.approx(20 + 8 / 12.0)
    assert d.u_bar_count == 244


def test_lookup_guards_untabulated_span():
    with pytest.raises(ValueError, match="14-46"):
        cs_slab_design(13)
    with pytest.raises(ValueError, match="14-46"):
        cs_slab_design(47)


def test_layout_guards():
    with pytest.raises(ValueError, match="14-46"):
        layout_continuous_slab(ContinuousSlabInput(end_span_ft=10, width_ft=30.0))
    with pytest.raises(ValueError, match="25"):
        layout_continuous_slab(
            ContinuousSlabInput(end_span_ft=24, width_ft=30.0, skew_deg=30.0))


def test_layout_square_bridge():
    lay = layout_continuous_slab(ContinuousSlabInput(end_span_ft=24, width_ft=30.0))
    interior = interior_span_ft(24)
    total = 2 * 24 + interior
    assert lay.total_length_ft == pytest.approx(total)
    assert lay.pier_stations == (24, 24 + interior)
    assert lay.outline == ((0.0, 0.0, 0.0), (0.0, 30.0, 0.0),
                           (total, 30.0, 0.0), (total, 0.0, 0.0))
    assert lay.thickness_in == cs_slab_design(24).thickness_in
    marks = {b.mark for b in lay.bars}
    assert "E" in marks  # span 24 >= 22, has an E-bar

    lay18 = layout_continuous_slab(ContinuousSlabInput(end_span_ft=18, width_ft=30.0))
    assert "E" not in {b.mark for b in lay18.bars}  # span 18 < 22, no E-bar


def test_layout_has_e_bars_for_longer_spans():
    lay = layout_continuous_slab(ContinuousSlabInput(end_span_ft=30, width_ft=30.0))
    marks = {b.mark for b in lay.bars}
    assert "E" in marks


def test_layout_skewed_shears_outline():
    lay = layout_continuous_slab(
        ContinuousSlabInput(end_span_ft=24, width_ft=30.0, skew_deg=15.0))
    tan15 = math.tan(math.radians(15.0))
    assert lay.outline[1][0] == pytest.approx(30.0 * tan15)


def test_layout_d_bars_centered_over_first_pier():
    lay = layout_continuous_slab(ContinuousSlabInput(end_span_ft=24, width_ft=30.0))
    d_bars = [b for b in lay.bars if b.mark == "D"]
    pier1 = lay.pier_stations[0]
    for b in d_bars:
        x0, x1 = b.points[0][0], b.points[1][0]
        assert (x0 + x1) / 2.0 == pytest.approx(pier1)
