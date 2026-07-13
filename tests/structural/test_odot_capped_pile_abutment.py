#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT CPA-1-08 capped pile abutment catalog
(rev. 01-19-2024)."""

import math

import pytest

from civilpy.structural.odot import capped_pile_abutment as cpa
from civilpy.structural.odot.capped_pile_abutment import (
    AbutmentInput,
    bend_shape,
    layout_capped_pile_abutment,
    rebar_mark,
    s_bar_length_ft,
)


def test_provenance():
    assert cpa.SCD == "CPA-1-08"
    assert cpa.REVISION == "01-19-2024"
    assert "CPA-1-08" in cpa.__doc__


def test_fixed_constants():
    assert cpa.CAP_WIDTH_FT == 3.0
    assert cpa.CAP_HALF_ZONE_FT == 1.5
    assert cpa.MAX_A_BAR_SPACING_FT == 1.5
    assert cpa.MAX_S_BAR_SPACING_FT == 1.0
    assert cpa.EMBANKMENT_SLOPE == 2.0


def test_rebar_mark_fixed_lengths():
    (a401,) = rebar_mark("A401")
    assert a401.length_ft == pytest.approx(8 + 10 / 12.0)
    assert a401.bend_type == 2
    (a501,) = rebar_mark("A501")
    assert a501.length_ft == pytest.approx(10 + 7 / 12.0)


def test_rebar_mark_a801_has_two_variants():
    rows = rebar_mark("A801")
    assert len(rows) == 2
    types = {r.bend_type for r in rows}
    assert types == {3, 4}


def test_rebar_mark_project_variable_is_none():
    (a502,) = rebar_mark("A502")
    assert a502.length_ft is None


def test_rebar_mark_guards_unknown():
    with pytest.raises(ValueError, match="A401"):
        rebar_mark("Z999")


def test_d801_cross_references_approach_slab():
    (d801,) = rebar_mark("D801")
    assert d801.bend_type == 6
    assert "approach_slab" in d801.note


def test_s_bar_length_formula():
    assert s_bar_length_ft(1 + 5 / 12.0, 0.0) == pytest.approx(1 + 5 / 12.0)
    cos30 = math.cos(math.radians(30.0))
    assert s_bar_length_ft(1 + 5 / 12.0, 30.0) == pytest.approx(
        (1 + 5 / 12.0) / cos30)


def test_bend_shape_guards_unknown_type():
    with pytest.raises(ValueError, match="1-5"):
        bend_shape(9, A=1.0)


def test_bend_shape_guards_missing_legs():
    with pytest.raises(ValueError, match="missing"):
        bend_shape(1, A=2.0)


def test_type_1_closed_stirrup():
    pts = bend_shape(1, A=2.0, B=3.0)
    assert pts[0] == pts[-1]   # closed shape
    assert pts[2] == (2.0, 3.0)


def test_type_2_u_shape():
    pts = bend_shape(2, A=3.0, B=1.5)
    assert pts[0] == (0.0, 0.0)
    assert pts[-1] == (3.0, 0.0)
    assert pts[1][1] == pts[2][1] == 1.5


def test_layout_guards():
    base = dict(wingwall_length_ft=10.0, skew_deg=0.0, n_piles=5,
                pile_spacing_ft=4.0, footing_depth_ft=3.0)
    layout_capped_pile_abutment(AbutmentInput(**base))  # sanity
    with pytest.raises(ValueError, match="wingwall_length_ft"):
        layout_capped_pile_abutment(AbutmentInput(**dict(base, wingwall_length_ft=0.0)))
    with pytest.raises(ValueError, match="n_piles"):
        layout_capped_pile_abutment(AbutmentInput(**dict(base, n_piles=1)))


def test_layout_square_abutment():
    inp = AbutmentInput(wingwall_length_ft=10.0, skew_deg=0.0, n_piles=5,
                        pile_spacing_ft=4.0, footing_depth_ft=3.0)
    lay = layout_capped_pile_abutment(inp)
    cap_len = 4 * 4.0 + 2 * 1.5
    assert lay.cap_outline[0] == (-cap_len / 2.0, -1.5, 0.0)
    assert lay.cap_outline[2] == (cap_len / 2.0, 1.5, 0.0)
    assert len(lay.pile_points) == 5
    assert lay.pile_points[0][2] == pytest.approx(-3.0)
    # piles run along y = 0, evenly spaced at 4 ft
    xs = [p[0] for p in lay.pile_points]
    assert xs[1] - xs[0] == pytest.approx(4.0)


def test_layout_skewed_shears_cap():
    inp = AbutmentInput(wingwall_length_ft=10.0, skew_deg=20.0, n_piles=5,
                        pile_spacing_ft=4.0, footing_depth_ft=3.0)
    lay = layout_capped_pile_abutment(inp)
    tan20 = math.tan(math.radians(20.0))
    cap_len = 4 * 4.0 + 2 * 1.5
    assert lay.cap_outline[1][0] == pytest.approx(-cap_len / 2.0 + 1.5 * tan20)


def test_layout_wingwall_flares_from_cap_end():
    inp = AbutmentInput(wingwall_length_ft=10.0, skew_deg=0.0, n_piles=5,
                        pile_spacing_ft=4.0, footing_depth_ft=3.0)
    lay = layout_capped_pile_abutment(inp)
    near = lay.wingwall_outline[0]
    assert near == lay.cap_outline[2]
    far = lay.wingwall_outline[2]
    run = math.hypot(far[0] - near[0], far[1] - near[1])
    assert run == pytest.approx(10.0)
