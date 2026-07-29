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
        box_section_properties, diaphragm_stations_ft)

    m = structural_model_from_box("CB27-48", 60.0, 9, barrier_klf=1.0,
                                  shear_keys=False, deck=False, mesh_ft=0)
    # a node at every section change: the two 3'-3" end blocks (PSBD sheet
    # 3) plus the diaphragm stations inside them
    n_dia = len(diaphragm_stations_ft(60.0, 27))
    stations = sorted({round(n.x, 4) for n in m.nodes.values()
                       if (n.label or "").startswith("BB")})
    assert stations == [0.0, 2.5, 3.25, 56.75, 57.5, 60.0]
    girders = [e for e in m.elements.values() if e.role == "girder"]
    rods = [e for e in m.elements.values() if e.role == "tie-rod"]
    assert len(girders) == 9 * (len(stations) - 1)
    assert len(rods) == 8 * n_dia                # one rod run per diaphragm
    assert len(m.restraints) == 18
    # the void stops at the end blocks
    solid = [e for e in girders if e.metadata["gdr.cell"] == "solid"]
    assert {e.section for e in solid} == {"CB27-48-SOLID"}
    assert len(solid) == 9 * 4          # 2 elements inside each end block
    g = next(e for e in girders if e.metadata["gdr.cell"] == "open")
    assert g.section == "CB27-48"
    sec = box_section_properties(27)
    assert g.metadata["section.area_in2"] == sec.area
    # a concrete girder must NOT be exported as an AISC database lookup
    assert g.metadata["sect.kind"] == "psc"
    assert g.metadata["matl.fc_psi"] == pytest.approx(5500.0)
    # DC1 = self weight + the full 6 in deck, applied per girder element
    dc1 = [bl for bl in m.beam_loads if bl.case == "DC1"]
    assert len(dc1) == len(girders)
    w = sec.area / 144.0 * 0.150 + 4.0 * 0.5 * 0.150
    assert dc1[0].w_start == pytest.approx(-w)
    cases = {bl.case for bl in m.beam_loads}
    assert cases == {"DC1", "DC2", "DW"}


class TestBDMDeadLoads:
    """The BDM decides the wearing surface -- it is not a free choice."""

    def test_composite_gets_a_concrete_deck_and_no_asphalt(self):
        from civilpy.structural.box_beam_pipeline import box_beam_dead_loads

        w = box_beam_dead_loads("CB27-48", 70, 6, barrier_klf=0.6)
        assert w.asphalt == 0.0
        # 6 in deck (5 structural + 1 monolithic WS) x 4 ft x 150 pcf
        assert w.deck == pytest.approx(4.0 * 0.5 * 0.150)
        assert w.fws == pytest.approx(0.060 * 4.0)      # BDM 303.1.2
        assert w.dc1 == pytest.approx(w.beam + w.deck)
        assert w.dw == pytest.approx(w.fws)
        assert w.barrier == pytest.approx(0.1)

    def test_non_composite_gets_asphalt_at_the_bdm_unit_weight(self):
        from civilpy.structural.box_beam_pipeline import box_beam_dead_loads

        w = box_beam_dead_loads("B21-48", 50, 6)
        assert w.deck == 0.0
        # BDM 909.A: 145 pcf, NOT the 140 pcf of LRFD Table 3.5.1-1
        assert w.asphalt == pytest.approx(4.0 * 3.0 / 12.0 * 0.145)
        assert w.dw == pytest.approx(w.asphalt + w.fws)

    def test_asphalt_on_a_composite_design_is_refused(self):
        from civilpy.structural.box_beam_pipeline import box_beam_dead_loads

        with pytest.raises(ValueError, match="309.1.B"):
            box_beam_dead_loads("CB27-48", 70, 6, asphalt_in=3.0)

    def test_asphalt_outside_the_bdm_range_is_refused(self):
        from civilpy.structural.box_beam_pipeline import box_beam_dead_loads

        with pytest.raises(ValueError, match="minimum"):
            box_beam_dead_loads("B21-48", 50, 6, asphalt_in=1.5)
        with pytest.raises(ValueError, match="maximum"):
            box_beam_dead_loads("B21-48", 50, 6, asphalt_in=10.0)

    def test_fws_can_be_zeroed_for_the_cases_that_exempt_it(self):
        from civilpy.structural.box_beam_pipeline import box_beam_dead_loads

        assert box_beam_dead_loads("CB27-48", 70, 6, fws_ksf=0.0).fws == 0.0

    def test_every_load_names_its_source(self):
        from civilpy.structural.box_beam_pipeline import box_beam_dead_loads

        w = box_beam_dead_loads("B21-48", 50, 6, barrier_klf=0.6)
        assert "909.A" in w.sources["asphalt"]
        assert "303.1.2" in w.sources["FWS"]
        assert "909.B" in w.sources["beam"]


class TestShearKeyAndDeck:
    def test_shear_key_line_per_joint(self):
        from civilpy.structural.box_beam_pipeline import (
            structural_model_from_box)

        m = structural_model_from_box("CB27-48", 70.0, 6, deck=False)
        keys = [e for e in m.elements.values() if e.role == "shear-key"]
        assert keys, "no shear key elements"
        assert {e.section for e in keys} == {"KEY-CB27-48"}
        assert keys[0].metadata["sect.family"] == "shear-key"

    def test_deck_is_composite_plates_of_the_structural_thickness_only(self):
        from civilpy.structural.box_beam_pipeline import (
            structural_model_from_box)

        m = structural_model_from_box("CB27-48", 70.0, 6)
        plates = [e for e in m.elements.values() if e.midas_type == "PLATE"]
        assert plates
        # BDM 309.1.A keeps the 1 in monolithic WS out of the composite
        # section -- the plates are the 5 in structural thickness
        assert {e.section for e in plates} == {"DECK-5in"}
        assert all(link.dof == "111111" for link in m.rigid_links)

    def test_deck_is_refused_on_a_non_composite_design(self):
        from civilpy.structural.box_beam_pipeline import (
            structural_model_from_box)

        with pytest.raises(ValueError, match="non-composite"):
            structural_model_from_box("B21-48", 50.0, 6, deck=True)

    def test_no_rigid_link_chaining(self):
        """A node may not be both master and slave.

        MIDAS rejects the chain without saying so: ``/doc/ANAL`` returns
        normally, writes no results, and leaves a modal "Analysis is not
        allowed" behind that blocks every later solve.  The lane lines
        therefore ride the deck's own nodes rather than hanging off them.
        """
        from civilpy.structural.box_beam_pipeline import (
            structural_model_from_box)

        for n_beams in (6, 11):
            m = structural_model_from_box("CB27-48", 70.0, n_beams)
            masters = {ln.master for ln in m.rigid_links}
            slaves = {s for ln in m.rigid_links for s in ln.slaves}
            assert not masters & slaves, n_beams

    def test_lane_lines_sit_on_design_lane_centrelines(self):
        from civilpy.structural.box_beam_pipeline import (
            structural_model_from_box)

        # 11 beams x 4 ft = 44 ft out-to-out, 40.5 ft clear -> 3 lanes
        m = structural_model_from_box("CB27-48", 70.0, 11)
        assert m.metadata["lane.offsets_ft"] == [10.0, 22.0, 34.0]
        lane_elems = [e for e in m.elements.values() if e.role == "lane-line"]
        assert {e.metadata["lane.index"] for e in lane_elems} == {1, 2, 3}
        # weightless dummies, and they share deck nodes (no extra constraint)
        assert all(e.metadata["matl.dummy"] for e in lane_elems)
        deck_nodes = {n for e in m.elements.values()
                      if e.midas_type == "PLATE" for n in e.nodes}
        assert all(n in deck_nodes for e in lane_elems for n in e.nodes)

    def test_no_node_is_left_unconnected(self):
        """A dangling key node makes the stiffness matrix singular."""
        from civilpy.structural.box_beam_pipeline import (
            structural_model_from_box)

        for kw in ({}, {"deck": False}):
            m = structural_model_from_box("CB27-48", 70.0, 6, **kw)
            used = {n for e in m.elements.values() for n in e.nodes}
            for link in m.rigid_links:
                used.add(link.master)
                used.update(link.slaves)
            assert not set(m.nodes) - used, kw


def test_summary_readable(checks):
    text = checks.summary()
    assert "CB27-48 @ 60 ft" in text
    assert "PASS" in text and "losses" in text
