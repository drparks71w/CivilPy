#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT AS-1-15 approach slab catalog and layout.

Table values are spot-checked against the rendered sheet (rev.
01-20-2023); everything the sheet computes from a formula is re-derived.
"""

import math

import pytest

from civilpy.structural.odot import approach_slab as ap
from civilpy.structural.odot.approach_slab import (
    APPROACH_SLAB_DESIGNS,
    ApproachSlabInput,
    JOINT_DETAILS,
    JOINT_NOTES,
    SEAT_CONFIGURATIONS,
    a_bar_count,
    anchor_bar_mark,
    approach_slab_design,
    b501_length_ft,
    c_bar_count,
    d801_length_ft,
    d802_length_ft,
    d_bar_count,
    layout_approach_slab,
    pay_area_sy,
)


# ── table integrity ──────────────────────────────────────────────────────

def test_table_rows_match_sheet():
    """Every cell of the reinforcing steel table as printed."""
    rows = {
        # L: (T, K, A mark, A len, dim A, N, n_bot, n_top, C mark, C len)
        15.0: (12.0, 10.0, "A1001", "15-11", 14.5, 9.0, 22, 30, "C501", 14.5),
        20.0: (13.0, 7.5, "A1002", "20-11", 19.5, 8.0, 31, 40, "C502", 19.5),
        25.0: (15.0, 7.0, "A1003", "25-11", 24.5, 8.0, 39, 50, "C503", 24.5),
        30.0: (17.0, 6.5, "A1004", "30-11", 29.5, 8.5, 44, 60, "C504", 29.5),
    }
    assert set(APPROACH_SLAB_DESIGNS) == set(rows)
    for length, (t, k, amark, alen, dima, n, nbot, ntop, cmark, clen) \
            in rows.items():
        d = APPROACH_SLAB_DESIGNS[length]
        ft, inches = (int(x) for x in alen.split("-"))
        assert d.thickness_in == t
        assert d.a_bar_spacing_in == k
        assert d.a_bar_mark == amark
        assert d.a_bar_length_ft == pytest.approx(ft + inches / 12.0)
        assert d.a_bar_dimension_ft == dima
        assert d.b501_bottom_spacing_in == n
        assert d.b501_bottom_count == nbot
        assert d.b501_top_count == ntop
        assert d.c_bar_mark == cmark
        assert d.c_bar_length_ft == clen


def test_table_internal_relations():
    """Relations the sheet's dimensions imply, re-derived for every row."""
    for d in APPROACH_SLAB_DESIGNS.values():
        # DIMENSION A and the C bar length are the slab length less the
        # 3 in end clearance at each end.
        assert d.a_bar_dimension_ft == pytest.approx(d.length_ft - 0.5)
        assert d.c_bar_length_ft == pytest.approx(d.a_bar_dimension_ft)
        # A bar total length = out-to-out dimension + 1'-5" of end bends.
        assert d.a_bar_length_ft - d.a_bar_dimension_ft == pytest.approx(
            17.0 / 12.0)
        # B501 top count is exactly 6 in c/c over (L - 0.5): 2(L-0.5)+1.
        assert d.b501_top_count == int(2 * (d.length_ft - 0.5)) + 1
        # B501 bottom: 5 end spaces @ 6 in + (count-6) @ N spans the same
        # (L - 0.5) run within the sheet's "+/-" spacing tolerance (4 in).
        run = 2.5 + (d.b501_bottom_count - 6) * d.b501_bottom_spacing_in / 12
        assert run == pytest.approx(d.length_ft - 0.5, abs=4.0 / 12.0)
        # thickness increases with span
        assert d.thickness_in >= 12.0


def test_lookup_guard_names_valid_lengths():
    with pytest.raises(ValueError, match=r"15\.0.*20\.0.*25\.0.*30\.0"):
        approach_slab_design(18.0)
    assert approach_slab_design(25).length_ft == 25.0


# ── formula functions ────────────────────────────────────────────────────

def test_bar_counts_per_sheet_formulas():
    d = approach_slab_design(15.0)
    # [12(W-0.5)/K]+1 with W=24, K=10 -> 28.2 spaces -> 29 + 1
    assert a_bar_count(24.0, d) == 30
    # exact multiple: 12*23.5/10 with W=10.5 -> 12 spaces exactly
    assert a_bar_count(10.5, d) == 13
    assert c_bar_count(24.0) == 48        # 12*23.5/6 = 47 exactly
    assert d_bar_count(24.0) == 17        # 12*23.5/18 = 15.67 -> 16 + 1


def test_b501_length_includes_skew():
    assert b501_length_ft(24.0) == pytest.approx(23.5)
    assert b501_length_ft(24.0, 30.0) == pytest.approx(
        23.5 / math.cos(math.radians(30.0)))


def test_anchor_bar_lengths():
    # X = 1.0 ft, no skew: 1'-0" + (1.414*1 + 0.823)
    assert d801_length_ft(1.0) == pytest.approx(3.237)
    # D802: 1'-0" + (1.414*1 + 0.202) + 1'-0"
    assert d802_length_ft(1.0) == pytest.approx(3.616)
    sec30 = 1.0 / math.cos(math.radians(30.0))
    assert d801_length_ft(1.0, 30.0) == pytest.approx(1.0 + 2.237 * sec30)
    assert d802_length_ft(1.0, 30.0) == pytest.approx(2.0 + 1.616 * sec30)


def test_anchor_bar_selection():
    assert anchor_bar_mark(14.0) == "D801"
    assert anchor_bar_mark(16.0) == "D801"
    assert anchor_bar_mark(11.0) == "D802"
    assert anchor_bar_mark(13.9) == "D802"
    with pytest.raises(ValueError, match="11"):
        anchor_bar_mark(10.0)


def test_pay_area():
    assert pay_area_sy(25.0, 24.0) == pytest.approx(66.667, abs=1e-3)


# ── sheet 2 catalog ──────────────────────────────────────────────────────

def test_seat_configurations_reference_valid_details_and_notes():
    for cfg in SEAT_CONFIGURATIONS:
        for det in cfg.details:
            assert det in JOINT_DETAILS
    for det, notes in JOINT_DETAILS.items():
        assert det in "ABCDEF"
        for n in notes:
            assert n in JOINT_NOTES
    # every construction type appears
    supports = {c.support for c in SEAT_CONFIGURATIONS}
    assert supports == {"slab bridge", "abutment backwall", "ps box beam",
                        "integral"}


# ── layout guards ────────────────────────────────────────────────────────

def test_layout_input_guards():
    ok = dict(length_ft=25.0, width_ft=24.0)
    with pytest.raises(ValueError, match="15"):
        layout_approach_slab(ApproachSlabInput(18.0, 24.0))
    with pytest.raises(ValueError, match="width"):
        layout_approach_slab(ApproachSlabInput(25.0, 0.4))
    with pytest.raises(ValueError, match="skew"):
        layout_approach_slab(ApproachSlabInput(25.0, 24.0, skew_deg=60.0))
    with pytest.raises(ValueError, match="seat"):
        layout_approach_slab(
            ApproachSlabInput(25.0, 24.0, seat_length_in=5.0))
    with pytest.raises(ValueError, match="seat"):
        layout_approach_slab(
            ApproachSlabInput(25.0, 24.0, seat_length_in=13.0))
    with pytest.raises(ValueError, match="never be less than T"):
        layout_approach_slab(
            ApproachSlabInput(25.0, 24.0, end_thickness_in=14.0))
    with pytest.raises(ValueError, match="backwall"):
        layout_approach_slab(
            ApproachSlabInput(25.0, 24.0, backwall_thickness_in=10.0))
    layout_approach_slab(ApproachSlabInput(**ok))  # no raise


# ── layout geometry ──────────────────────────────────────────────────────

def test_layout_outline_square():
    lay = layout_approach_slab(ApproachSlabInput(25.0, 24.0))
    assert lay.outline == (
        (0.0, 0.0, 0.0), (0.0, 24.0, 0.0), (25.0, 24.0, 0.0),
        (25.0, 0.0, 0.0))


def test_layout_outline_skewed():
    lay = layout_approach_slab(ApproachSlabInput(25.0, 24.0, skew_deg=30.0))
    shift = 24.0 * math.tan(math.radians(30.0))
    assert lay.outline[1] == pytest.approx((shift, 24.0, 0.0))
    assert lay.outline[2] == pytest.approx((25.0 + shift, 24.0, 0.0))


def test_profile_uniform_thickness_when_x_equals_t():
    lay = layout_approach_slab(ApproachSlabInput(25.0, 24.0))
    t = 15.0 / 12.0
    # X = T: flat bottom (the taper collapses to the collinear seat point;
    # no duplicate vertices remain)
    assert lay.profile == (
        (0.0, 0.0), (25.0, 0.0), (25.0, -t), (0.75, -t), (0.0, -t))
    assert len(lay.profile) == len(set(lay.profile))


def test_profile_thickened_end():
    lay = layout_approach_slab(
        ApproachSlabInput(25.0, 24.0, end_thickness_in=21.0,
                          seat_length_in=6.0))
    t, x = 15.0 / 12.0, 21.0 / 12.0
    # seat 6 in, then a 2:1 taper over 2*(X-T) = 12 in
    assert lay.profile == (
        (0.0, 0.0), (25.0, 0.0), (25.0, -t),
        (0.5 + 2.0 * (x - t), -t), (0.5, -x), (0.0, -x))


def test_layout_bar_counts_match_formulas():
    W = 24.0
    lay = layout_approach_slab(ApproachSlabInput(25.0, W))
    d = lay.design
    by_mark = {}
    for b in lay.bars:
        by_mark.setdefault(b.mark, []).append(b)
    assert len(by_mark[d.a_bar_mark]) == a_bar_count(W, d)
    assert len(by_mark[d.c_bar_mark]) == c_bar_count(W)
    assert len(by_mark["B501"]) == d.b501_bottom_count + d.b501_top_count
    assert len(by_mark["D801"]) == d_bar_count(W)


def test_layout_bar_elevations_stack_correctly():
    lay = layout_approach_slab(ApproachSlabInput(25.0, 24.0))
    t_ft = 15.0 / 12.0
    zs = {}
    for b in lay.bars:
        zs.setdefault(b.mark, set()).add(round(b.points[0][2], 6))
    (z_a,) = zs["A1003"]
    (z_c,) = zs["C503"]
    z_b = sorted(zs["B501"])          # bottom, top
    # bottom: A bars on the 3 in cover, B501 stacked above them
    assert z_a == pytest.approx(-(15.0 - 3.0 - 1.27 / 2.0) / 12.0, abs=1e-5)
    assert z_b[0] > z_a
    # top: B501 on the 3 in cover, C bars below
    assert z_b[1] == pytest.approx(-(3.0 + 0.625 / 2.0) / 12.0, abs=1e-5)
    assert z_c < z_b[1]
    # everything inside the slab
    for z in [z_a, z_c] + z_b:
        assert -t_ft < z < 0.0


def test_layout_b501_bottom_end_spacing():
    lay = layout_approach_slab(ApproachSlabInput(25.0, 24.0))
    z_bot = min(b.points[0][2] for b in lay.bars if b.mark == "B501")
    us = sorted(b.points[0][0] for b in lay.bars
                if b.mark == "B501" and b.points[0][2] == z_bot)
    # first bar 3 in from the bridge end, then 5 spaces @ 6 in
    assert us[0] == pytest.approx(0.25)
    for i in range(1, 6):
        assert us[i] - us[i - 1] == pytest.approx(0.5)
    # last bar 3 in from the approach end
    assert us[-1] == pytest.approx(24.75)
    # remaining spaces near the tabulated N = 8 in
    rest = [us[i + 1] - us[i] for i in range(5, len(us) - 1)]
    for sp in rest:
        assert sp == pytest.approx(8.0 / 12.0, abs=0.5 / 12.0)


def test_layout_longitudinal_bars_follow_skew_offset():
    lay = layout_approach_slab(ApproachSlabInput(25.0, 24.0, skew_deg=30.0))
    tan30 = math.tan(math.radians(30.0))
    for b in lay.bars:
        if b.mark == "A1003":
            (x0, y0, _), (x1, y1, _) = b.points
            assert y0 == y1                       # parallel to CL roadway
            assert x0 == pytest.approx(0.25 + y0 * tan30)
            assert x1 == pytest.approx(24.75 + y0 * tan30)
        if b.mark == "B501":
            (x0, y0, _), (x1, y1, _) = b.points
            # parallel to the abutment: x tracks the skew across the width
            assert x1 - x0 == pytest.approx((y1 - y0) * tan30)


def test_layout_anchor_bars():
    lay = layout_approach_slab(
        ApproachSlabInput(25.0, 24.0, backwall_thickness_in=11.0))
    assert lay.anchor_mark == "D802"
    d_bars = [b for b in lay.bars if b.mark == "D802"]
    assert len(d_bars) == d_bar_count(24.0)
    assert lay.anchor_length_ft == pytest.approx(d802_length_ft(15.0 / 12.0))
    p1, p2, p3 = d_bars[0].points
    # 1'-0" horizontal backwall leg
    assert p2[0] - p1[0] == pytest.approx(1.0)
    assert p1[2] == p2[2]
    # 45-degree diagonal rising to the top-cover plane
    assert p3[0] - p2[0] == pytest.approx(p3[2] - p2[2])
    assert p3[2] == pytest.approx(-3.0 / 12.0)
    # low end embedded below the slab bottom
    assert p2[2] < -15.0 / 12.0


def test_layout_report_notes_disclose_unmodeled_content():
    lay = layout_approach_slab(ApproachSlabInput(25.0, 24.0))
    joined = " ".join(lay.notes).lower()
    for phrase in ("hook", "widened", "crown"):
        assert phrase in joined


def test_module_provenance():
    assert ap.SCD == "AS-1-15"
    assert ap.REVISION == "01-20-2023"
    assert "AS-1-15" in ap.__doc__
