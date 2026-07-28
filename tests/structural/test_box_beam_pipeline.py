#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the box-beam L1 verification pipeline."""

import math

import pytest

from civilpy.structural.box_beam_pipeline import (
    BoxBeamLineChecks,
    box_beam_line_checks,
    box_torsion_constant_in4,
)
from civilpy.structural.odot import (
    BOX_FLANGE_THICKNESS_IN,
    BOX_WEB_THICKNESS_IN,
)


@pytest.fixture(scope="module")
def checks() -> BoxBeamLineChecks:
    return box_beam_line_checks("CB27-48", 60.0, 9,
                                barrier_klf=1.0, fws_klf=0.54)


def test_standard_design_passes(checks):
    assert checks.all_ok, checks.summary()
    assert set(checks.checks) == {
        "transfer compression", "transfer tension", "service compression",
        "service III tension", "Strength I flexure"}


def test_torsion_constant_thin_wall():
    tw, tf = BOX_WEB_THICKNESS_IN, BOX_FLANGE_THICKNESS_IN
    b0, d0 = 48.0 - tw, 27.0 - tf
    expected = 4.0 * (b0 * d0) ** 2 / (2.0 * d0 / tw + 2.0 * b0 / tf)
    assert box_torsion_constant_in4(27.0) == pytest.approx(expected)


def test_distribution_factors_are_adjacent_box(checks):
    # range spot-check (the 4.6.2.2.2b/3c formulas have their own tests
    # in the distribution module); shear always exceeds moment for
    # adjacent boxes
    assert 0.2 < checks.df_moment < 0.5
    assert checks.df_moment < checks.df_shear < 0.7


def test_losses_are_ordered(checks):
    lo = checks.losses
    assert 5.0 < lo["elastic_shortening"] < 20.0
    assert 15.0 < lo["longterm"] < 35.0
    assert lo["f_pe"] == pytest.approx(202.5 - lo["total"])
    assert lo["f_pe"] > 0.5 * 270.0 * 0.75        # sane effective prestress


def test_midspan_moments(checks):
    m = checks.midspan_moments
    # self weight: w = A/144 * 0.150 klf on a 60 ft simple span
    from civilpy.structural.odot import box_section_properties

    w = box_section_properties(27).area / 144.0 * 0.150
    assert m["sw"] == pytest.approx(w * 60.0 ** 2 / 8.0, rel=1e-6)
    assert m["topping"] > 0                        # composite box
    assert m["ll"] > m["sw"] * 0.5                 # distributed HL-93


def test_transfer_evaluated_at_transfer_length(checks):
    s = checks.stresses
    # with the moment relief at 60 strand diameters the standard design
    # passes; at the bare end (M = 0) the top tension would exceed the
    # 5.9.2.3.1b limit for this line
    assert s["transfer_top_end"] > -0.24 * math.sqrt(4.0)
    assert s["transfer_bot_end"] > s["transfer_bot_mid"]


def test_camber_passthrough(checks):
    assert checks.camber_release_in == checks.design.camber_d0
    assert checks.camber_erection_in == checks.design.camber_d30


def test_non_composite_line_passes():
    r = box_beam_line_checks("B33-48", 70.0, 9, barrier_klf=1.0,
                             fws_klf=0.54)
    assert r.all_ok, r.summary()
    assert r.midspan_moments["topping"] == 0.0


def test_short_span_small_box_passes():
    r = box_beam_line_checks("B17-48", 30.0, 9, barrier_klf=1.0,
                             fws_klf=0.54)
    assert r.all_ok, r.summary()


def test_longest_span_governed_by_transfer_tension():
    """At the catalog's edge, fully bonded, transfer tension is the
    governing check and lands essentially exactly on its limit — the
    condition the sheet's strand debonding exists to relieve.  Everything
    else passes with range-top strengths.

    (Against the published PSBD-1-25 sheet 4/6 properties this sits a hair
    above 1.0; it read as a failure only while the tabulated section
    properties were wrong.)
    """
    r = box_beam_line_checks("CB42-48", 90.0, 9, barrier_klf=1.0,
                             fws_klf=0.54, fci_ksi=5.0, fc_ksi=7.0)
    assert r.all_ok, r.summary()
    ratios = {n: c.ratio for n, c in r.checks.items()}
    assert min(ratios, key=ratios.get) == "transfer tension"
    assert ratios["transfer tension"] == pytest.approx(1.0, abs=0.02)


def test_structural_model_spoke():
    from civilpy.structural.box_beam_pipeline import structural_model_from_box
    from civilpy.structural.odot import (
        box_beam_design, box_section_properties, diaphragm_stations_ft)

    m = structural_model_from_box("CB27-48", 60.0, 9,
                                  barrier_klf=1.0, fws_klf=0.54)
    n_sta = len(diaphragm_stations_ft(60.0, 27)) + 2
    assert len(m.nodes) == 9 * n_sta
    girders = [e for e in m.elements.values() if e.role == "girder"]
    ties = [e for e in m.elements.values() if e.role == "diaphragm"]
    assert len(girders) == 9 * (n_sta - 1)
    assert len(ties) == 8 * (n_sta - 2)          # interior stations only
    assert len(m.restraints) == 18
    g = girders[0]
    assert g.section == "CB27-48"
    sec = box_section_properties(27)
    assert g.metadata["section.area_in2"] == sec.area
    # DC1 = self weight + topping, applied per girder element
    dc1 = [bl for bl in m.beam_loads if bl.case == "DC1"]
    assert len(dc1) == len(girders)
    w = sec.area / 144.0 * 0.150 + 4.0 * 0.5 * 0.150
    assert dc1[0].w_start == pytest.approx(-w)
    cases = {bl.case for bl in m.beam_loads}
    assert cases == {"DC1", "DC2", "DW"}


def test_summary_readable(checks):
    text = checks.summary()
    assert "CB27-48 @ 60 ft" in text
    assert "PASS" in text and "losses" in text
