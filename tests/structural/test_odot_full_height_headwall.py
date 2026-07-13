#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT HW-1.1 full-height headwall catalog (rev. 07-18-2025)."""

import math

import pytest

from civilpy.structural.odot import full_height_headwall as fhh
from civilpy.structural.odot.full_height_headwall import (
    FULL_HEIGHT_HEADWALLS,
    HeadwallInput,
    full_height_headwall_design,
    layout_full_height_headwall,
    nearest_skew_bucket,
)


def test_provenance():
    assert fhh.SCD == "HW-1.1"
    assert fhh.REVISION == "07-18-2025"
    assert "HW-1.1" in fhh.__doc__


def test_design_data_matches_notes():
    assert fhh.BACKFILL_FRICTION_ANGLE_DEG == 30.0
    assert fhh.BACKFILL_UNIT_WEIGHT_PCF == 120.0
    assert fhh.FOUNDATION_FRICTION_ANGLE_DEG == 28.0
    assert fhh.FOUNDATION_UNDRAINED_SHEAR_STRENGTH_PSF == 1500.0
    assert fhh.CONCRETE_UNIT_WEIGHT_PCF == 150.0
    assert fhh.BACKFILL_SLOPE == 2.0
    assert fhh.CONCRETE_STRENGTH_PSI == 4000.0
    assert fhh.REBAR_YIELD_KSI == 60.0


def test_table_has_all_tabulated_diameters():
    assert set(FULL_HEIGHT_HEADWALLS) == {42.0, 48.0, 54.0, 60.0, 72.0, 84.0}


def test_table_spot_check_42in():
    d = full_height_headwall_design(42.0)
    assert d.height_ft == pytest.approx(5 + 4 / 12.0)
    assert d.bar_size == 5
    s0 = d.skew(0.0)
    assert s0.L1 is None and s0.h1 is None
    assert s0.L2 == pytest.approx(3 + 7 / 12.0)
    assert s0.h2 == pytest.approx(3 + 6 / 12.0)
    assert (s0.concrete_cmp_cy, s0.concrete_rcp_cy, s0.steel_lb) == (7.2, 7.1, 695)
    s45 = d.skew(45.0)
    assert s45.L1 == pytest.approx(7 + 10 / 12.0)
    assert s45.L2 == pytest.approx(7 + 9 / 12.0)
    assert (s45.concrete_cmp_cy, s45.concrete_rcp_cy, s45.steel_lb) == (9.0, 8.9, 794)


def test_table_spot_check_84in_bar_size_8():
    d = full_height_headwall_design(84.0)
    assert d.bar_size == 8
    assert d.height_ft == pytest.approx(9 + 4 / 12.0)
    s30 = d.skew(30.0)
    assert s30.L1 == pytest.approx(14 + 7 / 12.0)
    assert s30.h2 == pytest.approx(5 + 10 / 12.0)
    assert s30.steel_lb == 2559


def test_lookup_guards_untabulated_diameter():
    with pytest.raises(ValueError, match=r"42\.0.*84\.0"):
        full_height_headwall_design(50.0)


def test_nearest_skew_bucket():
    assert nearest_skew_bucket(0.0) == 0.0
    assert nearest_skew_bucket(9.0) == 0.0
    assert nearest_skew_bucket(10.0) == 0.0     # sheet's own Type A/B cutoff
    assert nearest_skew_bucket(11.0) == 15.0
    assert nearest_skew_bucket(22.0) == 15.0
    assert nearest_skew_bucket(23.0) == 30.0
    assert nearest_skew_bucket(37.0) == 30.0
    assert nearest_skew_bucket(39.0) == 45.0
    assert nearest_skew_bucket(45.0) == 45.0
    assert nearest_skew_bucket(-22.0) == 15.0
    with pytest.raises(ValueError, match="45 deg"):
        nearest_skew_bucket(90.0)


def test_layout_guards():
    with pytest.raises(ValueError, match=r"42\.0.*84\.0"):
        layout_full_height_headwall(HeadwallInput(50.0))
    with pytest.raises(ValueError, match="45 deg"):
        layout_full_height_headwall(HeadwallInput(60.0, skew_deg=90.0))


def test_layout_type_a_symmetric_square():
    lay = layout_full_height_headwall(HeadwallInput(60.0, skew_deg=0.0))
    assert lay.type_ == "A"
    assert lay.skew_bucket_deg == 0.0
    D = 60.0 / 12.0
    H = 7.0
    assert lay.center_face == ((-D / 2, 0.0, 0.0), (D / 2, 0.0, 0.0),
                              (D / 2, 0.0, H), (-D / 2, 0.0, H))
    # both wingwalls use the skew-0 L2/h2 data and are mirror images
    s0 = full_height_headwall_design(60.0).skew(0.0)
    assert lay.wing1[2][0] == pytest.approx(-lay.wing2[2][0])
    assert lay.wing1[2][1] == pytest.approx(lay.wing2[2][1])
    L_plan = math.hypot(lay.wing2[2][0] - D / 2, lay.wing2[2][1])
    assert L_plan == pytest.approx(s0.L2)
    assert lay.wing2[3][2] == pytest.approx(s0.h2)
    assert lay.concrete_cy == s0.concrete_rcp_cy
    assert lay.steel_lb == s0.steel_lb


def test_layout_type_b_asymmetric_skew():
    lay = layout_full_height_headwall(HeadwallInput(60.0, skew_deg=15.0))
    assert lay.type_ == "B"
    s15 = full_height_headwall_design(60.0).skew(15.0)
    D = 60.0 / 12.0
    L1_plan = math.hypot(lay.wing1[2][0] + D / 2, lay.wing1[2][1])
    L2_plan = math.hypot(lay.wing2[2][0] - D / 2, lay.wing2[2][1])
    assert L1_plan == pytest.approx(s15.L1)
    assert L2_plan == pytest.approx(s15.L2)
    assert lay.wing1[3][2] == pytest.approx(s15.h1)
    assert lay.wing2[3][2] == pytest.approx(s15.h2)


def test_layout_snaps_intermediate_skew_to_bucket():
    lay = layout_full_height_headwall(HeadwallInput(60.0, skew_deg=12.0))
    assert lay.skew_bucket_deg == 15.0
    assert lay.type_ == "B"
