#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT CPP-1-08 capped pile pier catalog (rev. 07-21-2017)."""

import math

import pytest

from civilpy.structural.odot import capped_pile_pier as cpp
from civilpy.structural.odot.capped_pile_pier import (
    PierInput,
    layout_capped_pile_pier,
    pier_bar,
    pier_length_ft,
    q_bend_height_ft,
)


def test_provenance():
    assert cpp.SCD == "CPP-1-08"
    assert cpp.REVISION == "07-21-2017"
    assert "CPP-1-08" in cpp.__doc__


def test_design_data_and_limits():
    assert cpp.CONCRETE_STRENGTH_KSI == 4.5
    assert cpp.REBAR_YIELD_KSI == 60.0
    assert cpp.STEEL_PILE_SHAPE == "HP12X53"
    assert cpp.STEEL_PILE_YIELD_KSI == 50.0
    assert cpp.CONCRETE_PILE_MIN_DIAMETER_IN == 16.0
    assert cpp.MAX_SKEW_DEG == 30.0
    assert cpp.MAX_UNSUPPORTED_PILE_LENGTH_FT == 20.0
    assert cpp.MAX_SPAN_FT == 57.5
    assert cpp.MAX_PILE_SPACING_FT == 7.5


def test_fixed_cap_geometry():
    assert cpp.CAP_WIDTH_FT == 3.0
    assert cpp.CAP_END_RADIUS_FT == pytest.approx(cpp.CAP_WIDTH_FT / 2.0)
    assert cpp.CAP_DEPTH_FT == 2.0


def test_pier_length_formula():
    assert pier_length_ft(30.0, 0.0) == pytest.approx(
        3.0 + (30.0 - (4 + 4 / 12.0)))
    cos15 = math.cos(math.radians(15.0))
    assert pier_length_ft(30.0, 15.0) == pytest.approx(
        3.0 + (30.0 - (4 + 4 / 12.0)) / cos15)


def test_q_bend_height_formula():
    assert q_bend_height_ft(18.25) == pytest.approx(18.25 / 12.0 + 1 + 4 / 12.0)


def test_pier_bar_table():
    p501 = pier_bar("P501")
    assert p501.width_ft == pytest.approx(2 + 8 / 12.0)
    assert p501.height_is_q
    p504 = pier_bar("P504")
    assert p504.width_ft == pytest.approx(2 + 6 / 12.0)
    assert p504.inside_radius_ft == pytest.approx(1 + (2 + 3 / 8.0) / 12.0)
    assert not p504.height_is_q


def test_pier_bar_guards_unknown_mark():
    with pytest.raises(ValueError, match="P501"):
        pier_bar("P999")


def test_layout_guards():
    base = dict(slab_width_ft=30.0, skew_deg=0.0, n_piles=6, pile_spacing_ft=5.0)
    layout_capped_pile_pier(PierInput(**base))  # sanity
    with pytest.raises(ValueError, match="slab_width_ft"):
        layout_capped_pile_pier(PierInput(**dict(base, slab_width_ft=0.0)))
    with pytest.raises(ValueError, match="n_piles"):
        layout_capped_pile_pier(PierInput(**dict(base, n_piles=1)))
    with pytest.raises(ValueError, match="pile spacing"):
        layout_capped_pile_pier(PierInput(**dict(base, pile_spacing_ft=8.0)))
    with pytest.raises(ValueError, match="30"):
        layout_capped_pile_pier(PierInput(**dict(base, skew_deg=45.0)))


def test_layout_square_pier():
    inp = PierInput(slab_width_ft=30.0, skew_deg=0.0, n_piles=6, pile_spacing_ft=5.0)
    lay = layout_capped_pile_pier(inp)
    assert lay.length_ft == pytest.approx(pier_length_ft(30.0, 0.0))
    assert len(lay.pile_points) == 6
    assert lay.pile_points[0][2] == pytest.approx(-cpp.CAP_DEPTH_FT)
    # pile line is centered along the cap length
    xs = [p[0] for p in lay.pile_points]
    assert xs[1] - xs[0] == pytest.approx(5.0)
    span = xs[-1] - xs[0]
    assert (lay.length_ft - span) / 2.0 > cpp.CAP_END_RADIUS_FT - 1e-6


def test_layout_cap_outline_is_closed_and_symmetric():
    inp = PierInput(slab_width_ft=30.0, skew_deg=0.0, n_piles=4, pile_spacing_ft=5.0)
    lay = layout_capped_pile_pier(inp)
    ys = [p[1] for p in lay.cap_outline]
    assert max(ys) == pytest.approx(cpp.CAP_WIDTH_FT / 2.0)
    assert min(ys) == pytest.approx(-cpp.CAP_WIDTH_FT / 2.0)


def test_layout_skewed_shears_cap():
    inp = PierInput(slab_width_ft=30.0, skew_deg=20.0, n_piles=4, pile_spacing_ft=5.0)
    lay = layout_capped_pile_pier(inp)
    tan20 = math.tan(math.radians(20.0))
    # outline[0] = (u=0, y=-half_w); outline[10] = (u=0, y=+half_w) -- both
    # at the near cap end, so their X difference is the pure shear term.
    x_at_neg = lay.cap_outline[0]
    x_at_pos = lay.cap_outline[10]
    assert x_at_neg[1] == pytest.approx(-cpp.CAP_WIDTH_FT / 2.0)
    assert x_at_pos[1] == pytest.approx(cpp.CAP_WIDTH_FT / 2.0)
    assert x_at_pos[0] - x_at_neg[0] == pytest.approx(
        cpp.CAP_WIDTH_FT * tan20, abs=1e-6)
