#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT DS-1-92 drip strip catalog (rev. 07-15-22)."""

import math

import pytest

from civilpy.structural.odot import drip_strip as ds


def test_section_constants_match_sheet():
    assert ds.EMBED_WIDTH_IN == 4.5
    assert ds.LEG_LENGTH_IN == 3.0
    assert ds.FINAL_BEND_DEG == 45.0
    assert ds.MIN_GAGE == 22
    assert ds.HOLE_DIAMETER_IN == 1.5
    assert ds.HOLE_SPACING_IN == 4.0
    assert ds.HOLE_ROW_STAGGER_IN == 2.0
    assert ds.FASTENER_SPACING_MAX_IN == 18.0
    assert ds.SPIKE_SHANK_DIAMETER_IN == pytest.approx(3.0 / 32.0)


def test_placements_match_sheet():
    # upper strip 1'-6" for DBR-2-73 and TST-1-99, 2'-0" for TST-2-21
    assert ds.upper_strip_length_in("DBR-2-73") == 18.0
    assert ds.upper_strip_length_in("TST-1-99") == 18.0
    assert ds.upper_strip_length_in("TST-2-21") == 24.0
    # root depths: 2-1/2 in (DBR-2-73), 2 in (TST series)
    assert ds.placement("DBR-2-73").root_depth_in == 2.5
    assert ds.placement("TST-1-99").root_depth_in == 2.0
    assert ds.placement("TST-2-21").root_depth_in == 2.0


def test_placement_guard():
    with pytest.raises(ValueError, match="DBR-2-73"):
        ds.placement("SBR-1-20")


def test_profile_bent_upper():
    prof = ds.strip_profile_in("upper")
    assert prof[0] == (-4.5, 0.0)
    assert prof[1] == (0.0, 0.0)
    h, v = prof[2]
    assert h == pytest.approx(3.0 * math.cos(math.radians(45.0)))
    assert v == pytest.approx(3.0 * math.sin(math.radians(45.0)))
    # leg length preserved through the bend
    assert math.hypot(h, v) == pytest.approx(3.0)


def test_profile_lower_and_unbent():
    lower = ds.strip_profile_in("lower")
    assert lower[2][1] < 0.0                      # leg turns down
    formed = ds.strip_profile_in("upper", bent=False)
    assert formed[2] == (0.0, 3.0)                # vertical against form
    leg_only = ds.strip_profile_in("lower", include_embedded=False)
    assert leg_only[0] == (0.0, 0.0)
    with pytest.raises(ValueError, match="upper.*lower"):
        ds.strip_profile_in("sideways")


def test_hole_pattern():
    centers = ds.hole_centers_in(18.0)   # the 1'-6" upper strip
    rows = {w for _, w in centers}
    assert rows == {1.5, 3.0}            # 1-1/2 in from each plate edge
    near = sorted(s for s, w in centers if w == 1.5)
    far = sorted(s for s, w in centers if w == 3.0)
    # 4 in pitch, second row staggered 2 in
    assert near == [2.0, 6.0, 10.0, 14.0]
    assert far == [4.0, 8.0, 12.0, 16.0]
    # every hole fully on the strip
    for s, _ in centers:
        assert 0.75 <= s <= 18.0 - 0.75
    with pytest.raises(ValueError):
        ds.hole_centers_in(0.0)


def test_runs_lower_continuous_plus_upper_at_posts():
    runs = ds.drip_strip_runs(120.0, (10.0, 60.0, 110.0), "TST-2-21")
    lower = [r for r in runs if r.kind == "lower"]
    upper = [r for r in runs if r.kind == "upper"]
    assert len(lower) == 1 and lower[0].length_ft == 120.0
    assert len(upper) == 3
    for r, station in zip(upper, (10.0, 60.0, 110.0)):
        assert r.start_ft == pytest.approx(station - 1.0)   # 2'-0" strip
        assert r.end_ft == pytest.approx(station + 1.0)


def test_runs_clip_to_fascia_and_guard():
    runs = ds.drip_strip_runs(50.0, (0.25,), "DBR-2-73")
    up = [r for r in runs if r.kind == "upper"][0]
    assert up.start_ft == 0.0                     # clipped at the start
    assert up.end_ft == pytest.approx(1.0)        # 1'-6" strip, half = 0.75
    with pytest.raises(ValueError, match="outside"):
        ds.drip_strip_runs(50.0, (75.0,), "DBR-2-73")
    with pytest.raises(ValueError, match="positive"):
        ds.drip_strip_runs(0.0, (), "DBR-2-73")


def test_pay_length_totals_upper_and_lower():
    runs = ds.drip_strip_runs(100.0, (25.0, 75.0), "TST-1-99")
    # lower 100 + two 1.5 ft upper strips
    assert ds.pay_length_ft(runs) == pytest.approx(103.0)
    assert ds.pay_length_ft(runs, sides=2) == pytest.approx(206.0)


def test_provenance():
    assert ds.SCD == "DS-1-92"
    assert ds.REVISION == "07-15-22"
    assert "DS-1-92" in ds.__doc__
