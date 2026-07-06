#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT BDM 309.3 deck design module (Figure 309-3)."""

import pytest

from civilpy.structural.odot import bridge_railing
from civilpy.structural.odot.deck_design import (
    MIN_OVERHANG_THICKNESS,
    POLICY,
    STANDARD_DECK_DESIGNS,
    VALID_RAILINGS,
    BarMat,
    minimum_deck_thickness,
    overhang_thickness,
    secondary_longitudinal_reinforcement,
    standard_deck_design,
    structural_design_thickness,
)


# ── BDM 309.3.1 minimum thickness ────────────────────────────────────────

def test_minimum_thickness_floor():
    # (S + 17)/3 governs only above 8.5 ft; below that the 8.5 in floor rules
    for span in (2.0, 5.0, 7.0, 8.0, 8.5):
        assert minimum_deck_thickness(span) == 8.5


def test_minimum_thickness_rounds_up_to_quarter_inch():
    # S = 9.0: (9+17)/3 = 8.667 -> 8.75; S = 9.5: 8.833 -> 9.00
    assert minimum_deck_thickness(9.0) == 8.75
    assert minimum_deck_thickness(9.5) == 9.00
    # exact quarter-inch results are not rounded further
    assert minimum_deck_thickness(10.0) == 9.00
    assert minimum_deck_thickness(13.0) == 10.00


def test_minimum_thickness_rejects_nonpositive_span():
    with pytest.raises(ValueError):
        minimum_deck_thickness(0.0)


def test_structural_thickness_excludes_monolithic_wearing_surface():
    assert structural_design_thickness(8.5) == 8.5 - 1.0
    assert POLICY.monolithic_wearing_surface == 1.0


# ── BDM Figure 309-3 table integrity ─────────────────────────────────────

def test_table_thickness_matches_bdm_formula():
    # The figure's deck-thickness column is the 309.3.1 formula evaluated at
    # each tabulated span — a transcription error in either would show here.
    for d in STANDARD_DECK_DESIGNS:
        assert d.deck_thickness == minimum_deck_thickness(d.effective_span_ft)


def test_table_overhang_is_two_inches_thicker():
    for d in STANDARD_DECK_DESIGNS:
        assert d.overhang_thickness == pytest.approx(d.deck_thickness + 2.0)


def test_table_transverse_mats_align():
    # BDM 309.3.4.2: top and bottom transverse bars at equal spacings so
    # they coincide in a vertical plane — true of every tabulated design.
    for d in STANDARD_DECK_DESIGNS:
        assert d.transverse_top.spacing == d.transverse_bottom.spacing


def test_table_spans_are_half_foot_grid():
    spans = [d.effective_span_ft for d in STANDARD_DECK_DESIGNS]
    assert spans == [7.0 + 0.5 * i for i in range(15)]


def test_table_overhang_bars_disappear_at_long_spans():
    for d in STANDARD_DECK_DESIGNS:
        has_bar = d.overhang_bar_size is not None
        assert has_bar == (d.effective_span_ft <= 12.0)
        assert (d.overhang_cutoff is not None) == has_bar


def test_spot_check_rows_against_figure():
    d = standard_deck_design(7.0)
    assert (d.deck_thickness, d.overhang_thickness) == (8.50, 10.50)
    assert str(d.transverse_top) == "#5 @ 6 in"
    assert (d.overhang_bar_size, d.overhang_cutoff) == (5, 54.0)
    assert str(d.longitudinal_top) == "#4 @ 12.5 in"
    assert str(d.longitudinal_bottom) == "#5 @ 10.75 in"

    d = standard_deck_design(11.5)
    assert (d.deck_thickness, d.overhang_thickness) == (9.50, 11.50)
    assert str(d.transverse_top) == "#6 @ 5.75 in"
    assert (d.overhang_bar_size, d.overhang_cutoff) == (4, 28.0)

    d = standard_deck_design(14.0)
    assert (d.deck_thickness, d.overhang_thickness) == (10.50, 12.50)
    assert d.overhang_bar_size is None


# ── standard_deck_design lookup rules ────────────────────────────────────

def test_effective_span_rounds_up_to_next_half_foot():
    assert standard_deck_design(7.2).effective_span_ft == 7.5
    assert standard_deck_design(10.01).effective_span_ft == 10.5
    assert standard_deck_design(10.0).effective_span_ft == 10.0
    # spans shorter than the table use the shortest tabulated design
    assert standard_deck_design(5.0).effective_span_ft == 7.0


def test_span_beyond_table_raises():
    with pytest.raises(ValueError, match="14.0 ft limit"):
        standard_deck_design(14.2)


def test_assumption_guards():
    standard_deck_design(9.0, railing="SBR-1-20", beam_lines=5,
                         beam_spacing_ft=9.0, overhang_ft=3.0)
    with pytest.raises(ValueError, match="railing"):
        standard_deck_design(9.0, railing="DBR-2-73")
    with pytest.raises(ValueError, match="beam/girder"):
        standard_deck_design(9.0, beam_lines=3)
    with pytest.raises(ValueError, match="spacing"):
        standard_deck_design(9.0, beam_spacing_ft=15.5)
    with pytest.raises(ValueError, match="overhang"):
        standard_deck_design(9.0, overhang_ft=4.5)


def test_valid_railings_exist_in_scd_catalog():
    cataloged = {r.scd for r in bridge_railing.BRIDGE_RAILINGS.values()}
    for scd in VALID_RAILINGS:
        assert scd in cataloged


def test_overhang_thickness_tst_minimums_govern():
    d = standard_deck_design(7.0)
    assert overhang_thickness(d) == 10.50
    assert overhang_thickness(d, railing="BR-1-13") == 10.50
    assert overhang_thickness(d, railing="TST-1-99") == 18.0
    assert overhang_thickness(d, railing="TST-2-21") == 20.0
    assert MIN_OVERHANG_THICKNESS["TST-2-21"] == 20.0


# ── reinforcement helpers ────────────────────────────────────────────────

def test_barmat_area_per_ft():
    assert BarMat(5, 6.0).area_per_ft == pytest.approx(0.62)
    assert BarMat(4, 12.0).area_per_ft == pytest.approx(0.20)


def test_secondary_longitudinal_reinforcement_third_rule():
    main = BarMat(5, 6.0)  # 0.62 in^2/ft -> required 0.2067
    sec = secondary_longitudinal_reinforcement(main)
    assert sec.size == 4
    assert sec.spacing == 11.5
    assert sec.area_per_ft >= main.area_per_ft / 3.0


def test_secondary_reinforcement_upsizes_below_3in_spacing():
    # an absurdly heavy main mat forces the #4s under 3 in -> next size up
    main = BarMat(11, 4.0)  # 4.68 in^2/ft -> required 1.56 in^2/ft
    sec = secondary_longitudinal_reinforcement(main)
    assert sec.size > 4
    assert sec.spacing >= 3.0 or sec.size == 6


# ── BDM 309.3.5 haunch ───────────────────────────────────────────────────

def test_haunch_minimum_and_geometry():
    from civilpy.structural.odot.deck_design import Haunch, haunch_depth_at

    h = Haunch(depth=2.0, flange_width=12.0)
    assert h.area == 24.0
    assert h.dead_load_klf() == pytest.approx(24.0 / 144.0 * 0.150)
    with pytest.raises(ValueError, match="309.3.5"):
        Haunch(depth=1.5, flange_width=12.0)
    with pytest.raises(ValueError):
        Haunch(depth=2.5, flange_width=0.0)
    # girder low by 0.75 in -> deeper haunch; high girder can flag violation
    assert haunch_depth_at(2.5, 0.75) == 3.25
    assert haunch_depth_at(2.5, -1.0) == 1.5  # below minimum -> redesign


# ── policy ───────────────────────────────────────────────────────────────

def test_policy_constants():
    assert POLICY.live_load == "HL-93"
    assert POLICY.future_wearing_surface_ksf == 0.06
    assert POLICY.top_cover == 2.5
    assert POLICY.bottom_cover == 1.5
    assert POLICY.exposure_factor == 0.75
    assert POLICY.f_c == 4.5
    assert POLICY.f_y == 60.0
    assert "9.7.3" in POLICY.method
    assert POLICY.concrete_class == "QC2"
