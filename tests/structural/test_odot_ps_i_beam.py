#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT PSID-1-13 prestressed I-beam catalog (rev. 07-18-2025)."""

import pytest

from civilpy.structural.odot import ps_i_beam as psi
from civilpy.structural.odot.ps_i_beam import (
    layout_ps_i_beam,
    ps_i_beam_section,
)


def test_provenance():
    assert psi.SCD == "PSID-1-13"
    assert psi.REVISION == "07-18-2025"
    assert "PSID-1-13" in psi.__doc__


def test_all_sections_present():
    assert set(psi.PS_I_BEAM_SECTIONS) == {
        "AASHTO Type 2", "AASHTO Type 3", "AASHTO Type 4",
        "Modified AASHTO Type 4 (60in)", "Modified AASHTO Type 4 (66in)",
        "Modified AASHTO Type 4 (72in)",
        "WF36-49", "WF42-49", "WF48-49", "WF54-49", "WF60-49",
        "WF66-49", "WF72-49",
    }


def test_type2_section_properties():
    s = ps_i_beam_section("AASHTO Type 2")
    assert s.depth_in == 36.0
    assert s.area_in2 == 369.0
    assert s.yb_in + s.yt_in == pytest.approx(36.0)
    assert s.top_flange_width_in == 12.0
    assert s.bottom_flange_width_in == 18.0
    assert s.max_bottom_flange_strands == 26
    assert s.web_in == 6.0


def test_modified_type4_depths_match_yb_plus_yt():
    # Sheet 1 gives the Modified Type 4s a wide, thin top flange (36 in
    # for the 60/66 in beams, 48 in for the 72), not Type 4's 20 in.
    for name, top_w in (("Modified AASHTO Type 4 (60in)", 36.0),
                        ("Modified AASHTO Type 4 (66in)", 36.0),
                        ("Modified AASHTO Type 4 (72in)", 48.0)):
        s = ps_i_beam_section(name)
        assert s.yb_in + s.yt_in == pytest.approx(s.depth_in)
        assert (s.top_flange_width_in, s.bottom_flange_width_in) == (top_w, 26.0)


def test_wf_sections_sheet3_table():
    wf48 = ps_i_beam_section("WF48-49")
    assert wf48.depth_in == 48.0
    assert wf48.area_in2 == pytest.approx(974.3)
    assert wf48.weight_plf == 1015.0
    assert wf48.i_in4 == 305_994
    assert wf48.sb_in3 == wf48.st_in3 == 12_750  # symmetric at 48 in
    for name in ("WF36-49", "WF42-49", "WF48-49", "WF54-49",
                 "WF60-49", "WF66-49", "WF72-49"):
        s = ps_i_beam_section(name)
        assert s.yb_in + s.yt_in == pytest.approx(s.depth_in, abs=0.11)
        assert (s.top_flange_width_in, s.bottom_flange_width_in) == (49.0, 40.0)
        assert s.max_bottom_flange_strands == 62
        assert s.web_in == 8.0
        # weight is the area at 150 pcf (sheet's own convention)
        assert s.weight_plf == pytest.approx(s.area_in2 / 144.0 * 150.0, rel=0.01)


def test_strand_grids_reconcile_with_permissible_counts():
    for name, s in psi.PS_I_BEAM_SECTIONS.items():
        n = sum(len(ys) for _, ys in s.strand_rows)
        assert n == s.max_bottom_flange_strands, name
        for z, ys in s.strand_rows:
            assert z >= 2.0
            assert len(set(ys)) == len(ys)


def test_strand_grid_fill_order_bottom_up():
    grid = psi.strand_grid("AASHTO Type 2")
    assert len(grid) == 26
    zs = [z for _, z in grid]
    assert zs == sorted(zs)          # rows fill bottom-up
    assert grid[0][1] == 2.0
    # WF draped-required web locations come last
    wf = psi.strand_grid("WF48-49")
    assert wf[-2:] == [(0.0, 14.0), (0.0, 16.0)]


def test_strand_pattern_and_centroid():
    pat = psi.strand_pattern("AASHTO Type 3", 12)
    assert len(pat) == 12
    ybar = psi.strand_centroid_in(pat)
    assert 2.0 < ybar < 5.0          # low in the bulb
    with pytest.raises(ValueError, match="permissible"):
        psi.strand_pattern("AASHTO Type 2", 40)


def test_profile_closes_and_matches_flanges():
    for name, s in psi.PS_I_BEAM_SECTIONS.items():
        prof = psi.ps_i_beam_profile(name)
        ys = [y for y, _ in prof]
        zs = [z for _, z in prof]
        assert max(zs) - min(zs) == pytest.approx(s.depth_in), name
        assert max(ys) - min(ys) == pytest.approx(
            max(s.top_flange_width_in, s.bottom_flange_width_in)), name
        # shoelace area within 5% of the published gross area
        area = 0.5 * abs(sum(
            prof[i][0] * prof[(i + 1) % len(prof)][1]
            - prof[(i + 1) % len(prof)][0] * prof[i][1]
            for i in range(len(prof))))
        assert area == pytest.approx(s.area_in2, rel=0.05), name


def test_aashto_profiles_close_exactly():
    # the AASHTO 2/3/4 outlines close on the published areas
    for name in ("AASHTO Type 2", "AASHTO Type 3", "AASHTO Type 4"):
        s = ps_i_beam_section(name)
        prof = psi.ps_i_beam_profile(name)
        area = 0.5 * abs(sum(
            prof[i][0] * prof[(i + 1) % len(prof)][1]
            - prof[(i + 1) % len(prof)][0] * prof[i][1]
            for i in range(len(prof))))
        assert area == pytest.approx(s.area_in2, abs=1.0), name


def test_shipping_strands_modified_and_wf_only():
    assert ps_i_beam_section("AASHTO Type 4").shipping_strand_locations == ()
    mt = ps_i_beam_section("Modified AASHTO Type 4 (60in)")
    assert len(mt.shipping_strand_locations) == 6
    assert all(z == 57.0 for _, z in mt.shipping_strand_locations)
    wf = ps_i_beam_section("WF72-49")
    assert sorted(y for y, _ in wf.shipping_strand_locations) == [
        -10, -8, -6, 6, 8, 10]


def test_diaphragm_stations_sheet5():
    assert psi.i_beam_diaphragm_stations_ft(60.0) == [30.0]
    assert psi.i_beam_diaphragm_stations_ft(80.0) == [40.0]
    assert psi.i_beam_diaphragm_stations_ft(120.0) == [30.0, 60.0, 90.0]
    with pytest.raises(ValueError):
        psi.i_beam_diaphragm_stations_ft(0.0)


def test_sheet10_design_constants():
    assert psi.STRAND_AREA_IN2 == 0.217
    assert psi.STRAND_DIAMETER_IN == 0.6
    assert psi.STRAND_FPU_KSI == 270.0
    assert psi.FC_RANGE_KSI == (5.5, 7.0)
    assert psi.FCI_RANGE_KSI == (4.0, 5.0)
    assert psi.FWS_PSF == 60.0
    assert psi.MAX_BEAM_SPACING_FT == 14.0
    assert psi.MAX_SKEW_DEG == 45.0


def test_lookup_guards_unknown_section():
    with pytest.raises(ValueError, match="AASHTO Type 2"):
        ps_i_beam_section("Bulb Tee")


def test_layout_guards_nonpositive_length():
    with pytest.raises(ValueError, match="length_ft"):
        layout_ps_i_beam("AASHTO Type 2", 0.0)


def test_layout_profile_matches_depth_and_flange_widths():
    lay = layout_ps_i_beam("AASHTO Type 4", 100.0)
    zs = [p[1] for p in lay.profile]
    ys = [p[0] for p in lay.profile]
    assert max(zs) - min(zs) == pytest.approx(54.0)
    assert max(ys) - min(ys) == pytest.approx(26.0)  # bottom flange is widest
    assert lay.length_ft == 100.0
