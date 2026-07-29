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
    # 60 ft: end diaphragms 2.5 / 57.5 inside the 3'-3" end blocks, two
    # intermediates at the third points of the length between them, each
    # with its own 18 in solid block
    assert stations == [0.0, 2.5, 3.25,
                        20.0833, 20.8333, 21.5833,
                        38.4167, 39.1667, 39.9167,
                        56.75, 57.5, 60.0]
    girders = [e for e in m.elements.values() if e.role == "girder"]
    rods = [e for e in m.elements.values() if e.role == "tie-rod"]
    assert len(girders) == 9 * (len(stations) - 1)
    assert len(rods) == 8 * n_dia                # one rod run per diaphragm
    assert len(m.restraints) == 18
    # the void stops at the end blocks
    solid = [e for e in girders if e.metadata["gdr.cell"] == "solid"]
    assert {e.section for e in solid} == {"CB27-48-SOLID"}
    # 2 elements inside each of the 4 solid blocks (2 end + 2 intermediate)
    assert len(solid) == 9 * 8
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
        # packed against the railing -- the governing placement, not
        # centred (LRFD 3.6.1.1.1 leaves the position open)
        assert m.metadata["lane.offsets_ft"] == [7.5, 19.5, 31.5]
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


class TestDesignLanePlacement:
    """LRFD 3.6.1.1.1 fixes the lane COUNT; the position is open, and the
    two extremes govern different beams."""

    def test_count_from_the_clear_roadway(self):
        from civilpy.structural.box_beam_pipeline import design_lane_offsets_ft

        # 11 x 4 ft = 44 ft out-to-out, less two 1.75 ft parapets = 40.5 clear
        assert len(design_lane_offsets_ft(44.0)) == 3        # INT(40.5 / 12)
        assert len(design_lane_offsets_ft(28.0)) == 2        # 24.5 clear
        assert len(design_lane_offsets_ft(16.0)) == 1        # 12.5 clear

    def test_alignment_slides_the_lanes_within_the_slack(self):
        from civilpy.structural.box_beam_pipeline import design_lane_offsets_ft

        left = design_lane_offsets_ft(44.0, align="left")
        centre = design_lane_offsets_ft(44.0, align="center")
        right = design_lane_offsets_ft(44.0, align="right")
        assert centre == [10.0, 22.0, 34.0]
        # 4.5 ft of slack on a 40.5 ft roadway, so 4.5 ft of travel
        assert left == [7.75, 19.75, 31.75]
        assert right == [12.25, 24.25, 36.25]
        assert right[0] - left[0] == pytest.approx(4.5)
        # every lane stays inside the barriers whichever way they slide
        for lanes in (left, centre, right):
            assert lanes[0] - 6.0 >= 1.75 - 1e-9
            assert lanes[-1] + 6.0 <= 44.0 - 1.75 + 1e-9

    def test_lanes_never_overlap(self):
        from civilpy.structural.box_beam_pipeline import design_lane_offsets_ft

        for align in ("left", "center", "right"):
            lanes = design_lane_offsets_ft(44.0, align=align)
            assert all(b - a == pytest.approx(12.0)
                       for a, b in zip(lanes, lanes[1:])), align


class TestDeckSizedFromTraffic:
    """The designer says how much traffic; civilpy sizes the deck."""

    def test_lanes_shoulders_and_railing_drive_the_beam_count(self):
        from civilpy.structural.box_beam_pipeline import layout_deck

        L = layout_deck(2)                       # 2 lanes, 8 ft shoulders
        assert L.roadway_ft == 2 * 12 + 8 + 8    # 40 ft face to face
        assert L.barrier_width_ft == 1.5         # BR-1 base width, 18 in
        assert L.required_ft == 43.0
        assert L.n_beams == 11                   # ceil(43 / 4)
        assert L.deck_width_ft == 44.0
        assert L.spare_ft == 1.0

    def test_beam_count_rounds_up_never_down(self):
        from civilpy.structural.box_beam_pipeline import layout_deck

        for n in range(1, 6):
            L = layout_deck(n)
            assert L.deck_width_ft >= L.required_ft
            assert L.deck_width_ft - L.required_ft < L.beam_width_ft

    def test_designer_values_flow_through(self):
        from civilpy.structural.box_beam_pipeline import layout_deck

        narrow = layout_deck(2, shoulder_ft=2.0, barrier=None)
        assert narrow.barrier_width_ft == 0.0
        assert narrow.required_ft == 2 * 12 + 4
        assert narrow.n_beams == 7               # ceil(28 / 4)
        # a wider railing costs deck
        wide = layout_deck(2, barrier="SBR-2 (57 in median)")
        assert wide.barrier_width_ft > 1.5
        assert wide.n_beams >= 11

    def test_asymmetric_shoulders(self):
        from civilpy.structural.box_beam_pipeline import layout_deck

        L = layout_deck(2, shoulder_ft=(10.0, 4.0))
        assert L.shoulder_ft == (10.0, 4.0)
        assert L.roadway_ft == 2 * 12 + 14

    def test_rejects_a_bridge_with_no_lanes(self):
        from civilpy.structural.box_beam_pipeline import layout_deck

        with pytest.raises(ValueError, match="at least one lane"):
            layout_deck(0)


class TestWorstLanePlacement:
    """LRFD 3.6.1.1.1 leaves the transverse position open; the analysis
    has to be run at the one that governs, not at a tidy centred layout."""

    def test_lanes_end_up_packed_against_a_barrier(self):
        from civilpy.structural.box_beam_pipeline import worst_lane_placement

        lanes, n_loaded, frac = worst_lane_placement(
            3, 14, barrier_width=1.5)
        # first lane centre sits half a lane in from the railing face
        assert lanes[0] == pytest.approx(1.5 + 6.0)
        assert all(b - a == pytest.approx(12.0)
                   for a, b in zip(lanes, lanes[1:]))
        assert 1 <= n_loaded <= 3 and frac > 0

    def test_packed_beats_centred_on_the_fascia_beam(self):
        """The point of the search: a centred layout understates the
        exterior beam and no amount of lane combination recovers it."""
        from civilpy.structural.box_beam_pipeline import (
            _exterior_lane_fraction, design_lane_offsets_ft,
            worst_lane_placement)

        packed = worst_lane_placement(3, 14, barrier_width=1.5)
        centred = design_lane_offsets_ft(56.0, barrier_width_ft=1.5)
        assert packed[2] > _exterior_lane_fraction(centred, 14, 4.0)

    def test_two_lanes_can_govern_over_three(self):
        """Multiple presence drops from 1.00 to 0.85 at the third lane."""
        from civilpy.structural.box_beam_pipeline import worst_lane_placement

        _, n_loaded, _ = worst_lane_placement(3, 14, barrier_width=1.5)
        assert n_loaded == 2

    def test_refuses_lanes_that_do_not_fit(self):
        from civilpy.structural.box_beam_pipeline import worst_lane_placement

        with pytest.raises(ValueError, match="do not fit"):
            worst_lane_placement(4, 8, barrier_width=1.5)   # 32 ft deck


class TestLaneDrivenModel:
    def test_n_lanes_sizes_the_model(self):
        from civilpy.structural.box_beam_pipeline import (
            layout_deck, structural_model_from_box)

        m = structural_model_from_box("CB27-48", 70.0, n_lanes=3)
        lines = {e.metadata["gdr.line"] for e in m.elements.values()
                 if e.role == "girder"}
        assert len(lines) == layout_deck(3).n_beams == 14
        assert m.metadata["lane.offsets_ft"] == [7.5, 19.5, 31.5]

    def test_conflicting_inputs_are_refused(self):
        from civilpy.structural.box_beam_pipeline import (
            structural_model_from_box)

        with pytest.raises(ValueError, match="not both"):
            structural_model_from_box("CB27-48", 70.0, 9, n_lanes=3)

    def test_one_of_the_two_is_required(self):
        from civilpy.structural.box_beam_pipeline import (
            structural_model_from_box)

        with pytest.raises(ValueError, match="either n_lanes"):
            structural_model_from_box("CB27-48", 70.0)


def test_narrow_roadway_still_gets_one_design_lane():
    """LRFD 3.6.1.1.1: a roadway under 12 ft does not lose its design
    lane -- the lane narrows to the roadway.  A 3-box deck is 12 ft out
    to out, 9 ft between BR-1 railings."""
    from civilpy.structural.box_beam_pipeline import (
        structural_model_from_box, worst_lane_placement)

    lanes, n_loaded, frac = worst_lane_placement(1, 3, barrier_width=1.5)
    assert lanes == (6.0,)                  # centred in the 9 ft roadway
    assert n_loaded == 1 and frac > 0
    m = structural_model_from_box("CB27-48", 70.0, 3, mesh_ft=0)
    assert m.metadata["lane.offsets_ft"] == [6.0]
