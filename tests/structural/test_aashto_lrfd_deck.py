#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the LRFD 9.7.3 deck strip design module (Table 4.6.2.1.3-1
and Appendix A4 Table A4-1)."""

import math

import pytest

from civilpy.structural.aashto.lrfd.deck import (
    A4_NEGATIVE_OFFSETS,
    A4_SPANS,
    _A4_ROWS,
    deck_dead_load_moment,
    deck_equivalent_strip,
    deck_ll_negative_moment,
    deck_ll_positive_moment,
    deck_strip_checks,
)


# ── Table 4.6.2.1.3-1 strips ─────────────────────────────────────────────

def test_strip_width_formulas():
    assert deck_equivalent_strip("positive", 8.0) == 26.0 + 6.6 * 8.0
    assert deck_equivalent_strip("negative", 8.0) == 48.0 + 3.0 * 8.0
    assert deck_equivalent_strip("overhang", 1.25) == 45.0 + 12.5


def test_strip_width_validation():
    with pytest.raises(ValueError):
        deck_equivalent_strip("positive", -1.0)
    with pytest.raises(ValueError):
        deck_equivalent_strip("torsional", 8.0)


# ── Table A4-1 ───────────────────────────────────────────────────────────

def test_a4_table_shape():
    assert A4_SPANS[0] == 4.0 and A4_SPANS[-1] == 15.0
    assert len(A4_SPANS) == 45  # 3 in increments
    for span, (pos, negs) in _A4_ROWS.items():
        assert pos > 0
        assert len(negs) == len(A4_NEGATIVE_OFFSETS)
        # negative moment must decay moving away from the girder CL
        assert all(a >= b for a, b in zip(negs, negs[1:])), span


def test_a4_spot_values_from_the_table():
    # values quoted in independent design aids
    assert deck_ll_positive_moment(8.0) == 5.69
    assert deck_ll_negative_moment(7.0, 3.0) == 5.17  # IDOT guide 3.2.1
    assert deck_ll_positive_moment(15.0) == 9.47
    assert deck_ll_negative_moment(4.0, 0.0) == 2.68
    assert deck_ll_negative_moment(15.0, 24.0) == 7.02


def test_a4_interpolation():
    # halfway between 8.00 (5.69) and 8.25 (5.83)
    assert deck_ll_positive_moment(8.125) == pytest.approx((5.69 + 5.83) / 2)
    # offset interpolation halfway between 12 in (3.43) and 18 in (2.49)
    assert deck_ll_negative_moment(8.0, 15.0) == pytest.approx((3.43 + 2.49) / 2)
    # both at once stays between the corner values
    m = deck_ll_negative_moment(8.1, 4.0)
    assert 4.90 < m < 5.74


def test_a4_positive_moment_monotonic_above_5ft():
    vals = [deck_ll_positive_moment(s) for s in A4_SPANS if s >= 5.0]
    assert all(a <= b for a, b in zip(vals, vals[1:]))


def test_a4_range_guards():
    with pytest.raises(ValueError):
        deck_ll_positive_moment(3.5)
    with pytest.raises(ValueError):
        deck_ll_positive_moment(15.5)
    with pytest.raises(ValueError):
        deck_ll_negative_moment(8.0, -1.0)
    # beyond-24in offsets clamp to the 24 in column
    assert deck_ll_negative_moment(8.0, 30.0) == 2.16


# ── dead-load helper ─────────────────────────────────────────────────────

def test_dead_load_moment():
    # 8.5 in slab of normal weight concrete: w = 0.10625 ksf/ft strip
    w = 8.5 / 12.0 * 0.150
    assert deck_dead_load_moment(w, 8.0) == pytest.approx(w * 64.0 / 10.0)
    assert deck_dead_load_moment(w, 8.0, coefficient=8.0) == pytest.approx(
        w * 64.0 / 8.0)
    with pytest.raises(ValueError):
        deck_dead_load_moment(w, 8.0, coefficient=0.0)


# ── strip check chain ────────────────────────────────────────────────────

def _odot_bottom_mat_checks(s_ft=8.0):
    """ODOT-style bottom-mat check: Figure 309-3 row S=8.0 (#5 @ 6 in,
    8.5 in deck -> 7.5 in structural, 1.5 in bottom cover)."""
    t_total = 8.5
    t_struct = t_total - 1.0
    w_slab = t_total / 12.0 * 0.150  # full thickness carries as dead load
    return deck_strip_checks(
        bar_size=5,
        spacing_in=6.0,
        t_structural=t_struct,
        cover_in=1.5,
        m_dc=deck_dead_load_moment(w_slab, s_ft),
        m_dw=deck_dead_load_moment(0.06, s_ft),
        m_ll=deck_ll_positive_moment(s_ft),
        f_c=4.5,
        f_y=60.0,
    )


def test_strip_checks_pass_for_odot_standard_design():
    flexure, minimum, crack = _odot_bottom_mat_checks()
    assert [c.article for c in (flexure, minimum, crack)] == [
        "5.6.3.2", "5.6.3.3", "5.6.7"]
    assert flexure.ok and minimum.ok and crack.ok
    # hand check of the flexure numbers: As = 0.62, ds = 7.5-1.5-0.3125
    a_s, d_s = 0.62, 7.5 - 1.5 - 0.3125
    a = a_s * 60.0 / (0.85 * 4.5 * 12.0)
    assert flexure.capacity == pytest.approx(a_s * 60.0 * (d_s - a / 2.0))
    assert flexure.details["tension_controlled"]


def test_strip_checks_fail_when_underreinforced():
    # a #4 @ 12 bottom mat on a 12 ft span cannot carry the strip moments
    checks = deck_strip_checks(
        bar_size=4,
        spacing_in=12.0,
        t_structural=7.5,
        cover_in=1.5,
        m_dc=deck_dead_load_moment(0.10625, 12.0),
        m_dw=deck_dead_load_moment(0.06, 12.0),
        m_ll=deck_ll_positive_moment(12.0),
    )
    assert not checks[0].ok


def test_strip_checks_service_stress_details():
    _, _, crack = _odot_bottom_mat_checks()
    f_ss = crack.details["f_ss"]
    assert 0.0 < f_ss < 36.0  # capped at 0.6*fy inside the 5.6.7 check
    assert crack.details["A_s_per_ft"] == pytest.approx(0.62)


def test_strip_checks_validation():
    with pytest.raises(ValueError):
        deck_strip_checks(bar_size=5, spacing_in=0.0, t_structural=7.5,
                          cover_in=1.5, m_dc=1, m_dw=0, m_ll=1)
    with pytest.raises(ValueError):
        deck_strip_checks(bar_size=5, spacing_in=6.0, t_structural=3.0,
                          cover_in=2.9, m_dc=1, m_dw=0, m_ll=1)
