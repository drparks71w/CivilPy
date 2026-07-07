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
    }


def test_type2_section_properties():
    s = ps_i_beam_section("AASHTO Type 2")
    assert s.depth_in == 36.0
    assert s.area_in2 == 369.0
    assert s.yb_in + s.yt_in == pytest.approx(36.0)
    assert s.top_flange_width_in == 12.0
    assert s.bottom_flange_width_in == 18.0
    assert s.max_bottom_flange_strands == 26


def test_modified_type4_depths_match_yb_plus_yt():
    for name in ("Modified AASHTO Type 4 (60in)",
                 "Modified AASHTO Type 4 (66in)",
                 "Modified AASHTO Type 4 (72in)"):
        s = ps_i_beam_section(name)
        assert s.yb_in + s.yt_in == pytest.approx(s.depth_in)
        assert (s.top_flange_width_in, s.bottom_flange_width_in) == (20.0, 26.0)


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
