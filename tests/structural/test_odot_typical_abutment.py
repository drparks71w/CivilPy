#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT A-1-20 typical abutment catalog (rev. 01-19-2024)."""

import math

import pytest

from civilpy.structural.odot import typical_abutment as ta
from civilpy.structural.odot.typical_abutment import (
    AbutmentInput,
    bearing_seat_dim_a_ft,
    layout_typical_abutment,
)


def test_provenance():
    assert ta.SCD == "A-1-20"
    assert ta.REVISION == "01-19-2024"
    assert "A-1-20" in ta.__doc__


def test_design_data():
    assert ta.CONCRETE_STRENGTH_KSI == 4.0
    assert ta.REBAR_YIELD_KSI == 60.0
    assert ta.DEFAULT_BAR_SIZE == 5
    assert ta.MAX_BAR_SPACING_FT == 1.5
    assert ta.CLEAR_COVER_IN == 2.0
    assert ta.WINGWALL_UNSUPPORTED_MAX_FT == 8.0
    assert ta.WINGWALL_MIN_HEIGHT_FT == 3.0


def test_bearing_seat_dim_a_formula():
    assert bearing_seat_dim_a_ft(0.0) == pytest.approx(2.0)
    cos30 = math.cos(math.radians(30.0))
    assert bearing_seat_dim_a_ft(30.0) == pytest.approx(2.0 / cos30)


def test_layout_guards():
    base = dict(width_ft=30.0, skew_deg=0.0, wingwall_length_ft=6.0,
                footing_depth_ft=3.0, backwall_height_ft=5.0)
    layout_typical_abutment(AbutmentInput(**base))  # sanity
    with pytest.raises(ValueError, match="width_ft"):
        layout_typical_abutment(AbutmentInput(**dict(base, width_ft=0.0)))
    with pytest.raises(ValueError, match="wingwall_length_ft"):
        layout_typical_abutment(AbutmentInput(**dict(base, wingwall_length_ft=-1.0)))


def test_layout_square_abutment():
    inp = AbutmentInput(width_ft=30.0, skew_deg=0.0, wingwall_length_ft=6.0,
                        footing_depth_ft=3.0, backwall_height_ft=5.0)
    lay = layout_typical_abutment(inp)
    half_t = ta.BACKWALL_TOP_WIDTH_FT / 2.0
    assert lay.backwall_outline[0] == (-half_t, 0.0, 0.0)
    assert lay.backwall_outline[2] == (half_t, 30.0, 0.0)
    assert lay.footing_outline[0][2] == pytest.approx(-3.0)
    assert lay.dim_a_ft == pytest.approx(2.0)


def test_layout_wingwall_flares_from_backwall_end():
    inp = AbutmentInput(width_ft=30.0, skew_deg=0.0, wingwall_length_ft=6.0,
                        footing_depth_ft=3.0, backwall_height_ft=5.0)
    lay = layout_typical_abutment(inp)
    near = lay.wingwall_outline[0]
    assert near == lay.backwall_outline[2]
    far = lay.wingwall_outline[2]
    run = math.hypot(far[0] - near[0], far[1] - near[1])
    assert run == pytest.approx(6.0)
    assert lay.wingwall_outline[1][2] == pytest.approx(ta.WINGWALL_MIN_HEIGHT_FT)


def test_layout_skewed_shears_backwall():
    inp = AbutmentInput(width_ft=30.0, skew_deg=20.0, wingwall_length_ft=6.0,
                        footing_depth_ft=3.0, backwall_height_ft=5.0)
    lay = layout_typical_abutment(inp)
    tan20 = math.tan(math.radians(20.0))
    half_t = ta.BACKWALL_TOP_WIDTH_FT / 2.0
    assert lay.backwall_outline[1][0] == pytest.approx(-half_t + 30.0 * tan20)
