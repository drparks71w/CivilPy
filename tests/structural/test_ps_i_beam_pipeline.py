#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the PSID-1-13 prestressed I-beam design pipeline (L1)."""

import math

import pytest

from civilpy.structural.ps_i_beam_pipeline import (
    DECK_FC_KSI,
    F_PJ_KSI,
    PSIBeamLineChecks,
    composite_section,
    ps_i_beam_line_checks,
    structural_model_from_ps_i,
)


@pytest.fixture(scope="module")
def wf48_line():
    """A realistic passing WF48-49 line: 95 ft span, 9 ft spacing."""
    return ps_i_beam_line_checks(
        "WF48-49", 95.0, 5, spacing_ft=9.0, barrier_klf=0.9,
        fci_ksi=5.0, fc_ksi=7.0)


def test_composite_section_geometry():
    comp = composite_section("WF48-49", 9.0, t_struct_in=7.5,
                             haunch_in=2.0, fc_beam_ksi=7.0)
    assert comp.b_eff_in == 108.0
    assert 0.7 < comp.n_deck_beam < 0.9          # deck softer than beam
    # composite centroid sits above the beam's own (24 in of 48)
    assert comp.ybc_in > 24.0
    assert comp.i_in4 > 305_994                   # stiffer than bare beam
    assert comp.sbc_in3 > 12_750


def test_designer_finds_passing_pattern(wf48_line):
    r = wf48_line
    assert isinstance(r, PSIBeamLineChecks)
    assert r.all_ok
    assert r.debond_note == ""
    d = r.design
    assert d.n_strands % 2 == 0
    assert 20 <= d.n_strands <= 50
    assert 0 <= d.n_debonded <= 0.45 * d.n_strands
    assert len(d.pattern) == d.n_strands
    assert d.e_in == pytest.approx(d.section.yb_in - d.ybar_in)


def test_check_articles_and_stresses(wf48_line):
    r = wf48_line
    assert set(r.checks) == {
        "transfer compression", "transfer tension",
        "service compression", "service III tension",
        "Strength I flexure"}
    assert r.checks["Strength I flexure"].article == "5.6.3.2.2"
    # transfer bottom compression is the big number at release
    assert r.stresses["transfer_bot_mid"] > r.stresses["transfer_top_mid"]
    # Service III bottom fiber stays above the tension limit
    limit = min(0.19 * math.sqrt(7.0), 0.6)
    assert r.stresses["service_bot_serviceIII"] >= -limit - 1e-9


def test_losses_are_ordered(wf48_line):
    lo = wf48_line.losses
    assert 0 < lo["elastic_shortening"] < 30.0
    assert 0 < lo["longterm"] < 45.0
    assert lo["f_pe"] == pytest.approx(
        F_PJ_KSI - lo["elastic_shortening"] - lo["longterm"])
    assert lo["f_pe"] > 0.5 * F_PJ_KSI


def test_distribution_factors_type_k(wf48_line):
    # 9 ft spacing, 95 ft span: multi-lane governs, sensible band
    assert 0.6 < wf48_line.df_moment < 0.9
    assert 0.7 < wf48_line.df_shear < 1.0


def test_camber_hogs_upward(wf48_line):
    assert wf48_line.camber_release_in > 0.0
    assert wf48_line.camber_release_in < 6.0


def test_summary_mentions_pattern_and_checks(wf48_line):
    s = wf48_line.summary()
    assert "WF48-49" in s
    assert "PASS" in s and "FAIL" not in s
    assert "4.6.2.2.2b" in s


def test_verify_mode_takes_given_count():
    r = ps_i_beam_line_checks(
        "AASHTO Type 3", 60.0, 6, spacing_ft=7.5, barrier_klf=0.9,
        n_strands=14)
    assert r.design.n_strands == 14
    with pytest.raises(ValueError, match="n_strands"):
        ps_i_beam_line_checks("AASHTO Type 2", 40.0, 5, spacing_ft=6.0,
                              n_strands=99)


def test_debonding_engages_on_long_spans():
    r = ps_i_beam_line_checks(
        "WF72-49", 130.0, 5, spacing_ft=9.0, barrier_klf=0.9,
        fci_ksi=5.0, fc_ksi=7.0)
    assert r.all_ok
    assert r.design.n_debonded > 0
    assert r.design.n_debonded % 2 == 0


def test_impossible_line_raises():
    with pytest.raises(ValueError, match="no .*pattern|no straight"):
        ps_i_beam_line_checks("AASHTO Type 2", 90.0, 5, spacing_ft=9.0)


def test_transfer_flag_when_fully_bonded_forced():
    # forbid debonding: a long line flags rather than silently passing
    r = ps_i_beam_line_checks(
        "WF48-49", 100.0, 5, spacing_ft=9.0, barrier_klf=0.9,
        max_debond_fraction=0.0)
    assert not r.all_ok
    assert "5.9.4.3.3" in r.debond_note


def test_structural_model_matches_checks():
    m = structural_model_from_ps_i(
        "WF48-49", 95.0, 5, spacing_ft=9.0, barrier_klf=0.9)
    girders = [e for e in m.elements.values() if e.role == "girder"]
    diaphragms = [e for e in m.elements.values() if e.role == "diaphragm"]
    # 95 ft span -> 3 diaphragm stations -> 4 segments per line
    assert len(girders) == 5 * 4
    assert len(diaphragms) == 4 * 3
    g = girders[0]
    assert g.section == "WF48-49"
    assert g.metadata["section.i_in4"] == 305_994
    # every girder element carries DC1 + DC2 + DW loads
    cases = {ld.case for ld in m.beam_loads}
    assert cases == {"DC1", "DC2", "DW"}


def test_model_short_span_single_diaphragm():
    m = structural_model_from_ps_i(
        "AASHTO Type 3", 60.0, 4, spacing_ft=7.5, dead_loads=False)
    diaphragms = [e for e in m.elements.values() if e.role == "diaphragm"]
    assert len(diaphragms) == 3          # one station, 3 bays


def test_deck_fc_constant():
    assert DECK_FC_KSI == 4.5
