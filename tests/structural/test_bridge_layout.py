#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the parametric bridge layout generator."""

import math

import pytest

from civilpy.structural.bridge_layout import (
    BridgeInput,
    default_fixity,
    effective_span_ft,
    girder_section,
    layout_bridge,
    railing_by_scd,
)


@pytest.fixture(scope="module")
def w36():
    return girder_section("W36X150")


@pytest.fixture(scope="module")
def basic():
    return layout_bridge(BridgeInput(
        spans_ft=(70.0, 90.0, 70.0),
        girder_count=5,
        girder_spacing_ft=8.0,
        girder_label="W36X150",
        overhang_ft=3.0,
        railing="SBR-1-20",
    ))


def test_section_resolves(w36):
    assert w36.depth == pytest.approx(35.9, abs=0.1)
    assert w36.flange_width == pytest.approx(12.0, abs=0.1)


def test_effective_span(w36):
    s = effective_span_ft(8.0, w36)
    expected = 8.0 - (w36.flange_width / 2 + w36.web_thickness / 2) / 12.0
    assert s == pytest.approx(expected)
    with pytest.raises(ValueError):
        effective_span_ft(0.5, w36)


def test_default_fixity_mirrors_plugin():
    assert default_fixity(0, 2) == "fixed"          # single span
    assert default_fixity(1, 2) == "expansion"
    assert [default_fixity(i, 4) for i in range(4)] == [
        "expansion", "expansion", "fixed", "expansion"]


def test_basic_counts_and_tags(basic):
    assert len(basic.girders) == 5
    assert len(basic.bearings) == 20  # 4 stations x 5 lines
    assert len(basic.haunches) == 5
    assert basic.total_length_ft == 230.0
    assert basic.deck_width_ft == 4 * 8.0 + 6.0

    g3 = basic.girders[2]
    assert g3.tags == {"gdr.kind": "girder", "gdr.line": "3",
                       "gdr.shape": "W36X150", "gdr.grade": "Grade 50"}
    lines = {g.tags["gdr.line"] for g in basic.girders}
    assert lines == {"1", "2", "3", "4", "5"}  # no duplicate numbering

    fixed = [b for b in basic.bearings if b.fixity == "fixed"]
    assert len(fixed) == 5 and all(b.station_index == 2 for b in fixed)
    assert all(b.tags["gdr.kind"] == "support" for b in basic.bearings)


def test_standard_design_drives_deck(basic):
    # eff span 7.47 ft rounds up to the 7.5 ft Figure 309-3 row
    assert basic.standard_design is not None
    assert basic.standard_design.effective_span_ft == 7.5
    assert basic.deck.thickness_in == 8.50
    assert basic.deck.overhang_thickness_in == 10.50
    assert basic.deck.structural_thickness_in == 7.50
    assert basic.doc_tags["gdr.deck_t"] == "7.5"
    assert basic.doc_tags["gdr.deck_weff"] == "96"


def test_elevations_stack_correctly(basic):
    # crown at mid-width (y = 16 ft), 2% cross slope: girder 1 (y = 0) hangs
    # from a deck surface 0.32 ft below the crown
    drop = 16.0 * 0.02
    z_soffit = -drop - 8.5 / 12.0
    z_top = z_soffit - 2.0 / 12.0
    z_bot = z_top - basic.section.depth / 12.0
    assert basic.crown_y_ft == pytest.approx(16.0)
    assert basic.deck_top_z(16.0) == 0.0
    assert basic.girders[0].start[2] == pytest.approx(z_top)
    assert basic.haunches[0].start[2] == pytest.approx(z_soffit)
    assert basic.bearings[0].location[2] == pytest.approx(z_bot)
    # center girder (y = 16) sits at the crown, 0.32 ft higher
    assert basic.girders[2].start[2] == pytest.approx(z_top + drop)
    # outline corners ride the crowned top surface
    assert basic.deck.outline[0][2] == pytest.approx(basic.deck_top_z(-3.0))


def test_flat_deck_recovers_level_frame():
    flat = layout_bridge(BridgeInput(
        spans_ft=(70.0, 90.0, 70.0), girder_count=5, girder_spacing_ft=8.0,
        girder_label="W36X150", overhang_ft=3.0, cross_slope_pct=0.0))
    z_top = -(8.5 + 2.0) / 12.0
    for g in flat.girders:
        assert g.start[2] == pytest.approx(z_top)
    assert all(p[2] == 0.0 for p in flat.deck.outline)


def test_deck_profile_yz(basic):
    prof = basic.deck_profile_yz()
    ys = [p[0] for p in prof]
    assert min(ys) == -3.0 and max(ys) == 35.0
    # crown appears on top and soffit; both edges thickened to 10.5 in
    top_at = dict(prof[:3])
    assert top_at[16.0] == 0.0
    edge = [p for p in prof if p[0] == 35.0]
    assert edge[0][1] - edge[1][1] == pytest.approx(10.5 / 12.0)
    # BDM Figure 309-4 overhang: soffit parallel to the top at t + 2 in
    # from the edge to the outboard flange tip, stepping up to the uniform
    # slab there (flush with the haunch bottom for a 2 in design haunch)
    half_bf = basic.section.flange_width / 2.0 / 12.0
    bot = prof[3:]
    soffit_at = {}
    for y, z in bot:
        soffit_at.setdefault(y, []).append(z)
    assert soffit_at[16.0] == [pytest.approx(-8.5 / 12.0)]
    # two z's at each flange tip: the 2 in step
    step_lo = sorted(soffit_at[-half_bf])
    assert step_lo[1] - step_lo[0] == pytest.approx(2.0 / 12.0)
    assert step_lo[1] == pytest.approx(
        basic.deck_top_z(-half_bf) - 8.5 / 12.0)
    # overhang thickness is constant (parallel to the crowned top)
    assert dict(bot)[-3.0] == pytest.approx(
        basic.deck_top_z(-3.0) - 10.5 / 12.0)
    assert step_lo[0] == pytest.approx(
        basic.deck_top_z(-half_bf) - 10.5 / 12.0)


def test_rebar_sets_from_standard_design(basic):
    names = [r.name for r in basic.deck.rebar]
    assert names == ["longitudinal top", "transverse top",
                     "transverse bottom", "longitudinal bottom",
                     "additional overhang"]
    by_name = {r.name: r for r in basic.deck.rebar}
    tt = by_name["transverse top"]
    assert (tt.size, tt.spacing_in) == (5, 6.0)
    # #4 longitudinal (dia 0.5) above the #5 transverse (dia 0.625):
    assert by_name["longitudinal top"].depth_in == pytest.approx(2.5 + 0.25)
    assert tt.depth_in == pytest.approx(2.5 + 0.5 + 0.3125)
    tb = by_name["transverse bottom"]
    assert tb.depth_in == pytest.approx(8.5 - 1.5 - 0.3125)
    oh = by_name["additional overhang"]
    assert oh.extent == "overhang" and oh.overhang_cutoff_in == 54.0
    # depths stay inside the slab
    assert all(0 < r.depth_in < 8.5 for r in basic.deck.rebar)


def test_skew_shifts_and_bar_angles():
    kwargs = dict(spans_ft=(80.0,), girder_count=4, girder_spacing_ft=9.0,
                  girder_label="W36X150", overhang_ft=2.5)
    skewed = layout_bridge(BridgeInput(skew_deg=30.0, **kwargs))
    tan30 = math.tan(math.radians(30.0))
    g4 = skewed.girders[3]  # y = 27 ft
    assert g4.start[0] == pytest.approx(27.0 * tan30)
    assert g4.end[0] == pytest.approx(80.0 + 27.0 * tan30)
    # transverse steel perpendicular to CL at skew >= 15 (BDM 309.3.4.2)
    angles = {r.angle_deg for r in skewed.deck.rebar
              if r.direction == "transverse"}
    assert angles == {0.0}

    mild = layout_bridge(BridgeInput(skew_deg=10.0, **kwargs))
    angles = {r.angle_deg for r in mild.deck.rebar
              if r.direction == "transverse"}
    assert angles == {10.0}

    # deck outline follows the skew
    lo = skewed.deck.outline[0]
    assert lo[0] == pytest.approx(-2.5 * tan30)


def test_custom_deck_thickness_path():
    inp = BridgeInput(spans_ft=(60.0,), girder_count=5,
                      girder_spacing_ft=8.0, girder_label="W36X150",
                      overhang_ft=3.0, deck_thickness_in=9.5)
    out = layout_bridge(inp)
    assert out.standard_design is None
    assert out.deck.thickness_in == 9.5
    assert out.deck.rebar == ()  # custom decks get designed, not tabulated
    assert out.doc_tags["gdr.deck_t"] == "8.5"

    with pytest.raises(ValueError, match="309.3.1 minimum"):
        layout_bridge(BridgeInput(
            spans_ft=(60.0,), girder_count=5, girder_spacing_ft=8.0,
            girder_label="W36X150", overhang_ft=3.0, deck_thickness_in=8.0))


def test_standard_design_guards_propagate():
    with pytest.raises(ValueError, match="beam/girder"):
        layout_bridge(BridgeInput(
            spans_ft=(60.0,), girder_count=3, girder_spacing_ft=8.0,
            girder_label="W36X150", overhang_ft=3.0))
    with pytest.raises(ValueError, match="overhang"):
        layout_bridge(BridgeInput(
            spans_ft=(60.0,), girder_count=5, girder_spacing_ft=8.0,
            girder_label="W36X150", overhang_ft=4.5))
    with pytest.raises(ValueError, match="railing"):
        layout_bridge(BridgeInput(
            spans_ft=(60.0,), girder_count=5, girder_spacing_ft=8.0,
            girder_label="W36X150", overhang_ft=3.0, railing="PCB-91"))


def test_geometry_input_guards():
    with pytest.raises(ValueError):
        layout_bridge(BridgeInput(spans_ft=(), girder_count=5,
                                  girder_spacing_ft=8.0,
                                  girder_label="W36X150", overhang_ft=3.0))
    with pytest.raises(ValueError):
        layout_bridge(BridgeInput(spans_ft=(60.0,), girder_count=1,
                                  girder_spacing_ft=8.0,
                                  girder_label="W36X150", overhang_ft=3.0))
    with pytest.raises(ValueError):
        layout_bridge(BridgeInput(spans_ft=(60.0,), girder_count=5,
                                  girder_spacing_ft=8.0,
                                  girder_label="W36X150", overhang_ft=3.0,
                                  skew_deg=75.0))


def test_rebar_segments_no_skew(basic):
    from civilpy.structural.bridge_layout import deck_rebar_segments

    segs = deck_rebar_segments(basic)
    assert segs, "expected instantiated bars"
    by_set = {}
    for s in segs:
        by_set.setdefault(s.rebar_set.name, []).append(s)

    # longitudinal bars run the full length minus end cover, hung from the
    # local (crowned) deck surface
    lt = by_set["longitudinal top"]
    c = 2.0 / 12.0
    for s in lt:
        assert s.start[1] == s.end[1]                       # constant y
        assert s.start[0] == pytest.approx(c)
        assert s.end[0] == pytest.approx(230.0 - c)
        assert s.start[2] == pytest.approx(
            basic.deck_top_z(s.start[1]) - (2.5 + 0.25) / 12.0)
    # bar count ~ inset width / spacing (7.5 ft row: #4 @ 12.0)
    spacing_ft = basic.standard_design.longitudinal_top.spacing / 12.0
    width = basic.deck_width_ft - 2 * c
    assert len(lt) == int(width / spacing_ft) + 1

    # transverse bars span the full inset width at zero skew and crank once
    # at the crown (three vertices), staying at constant depth below the top
    tt = by_set["transverse top"]
    depth_ft = tt[0].rebar_set.depth_in / 12.0
    for s in tt:
        assert s.start[0] == pytest.approx(s.end[0])        # constant x
        assert s.start[1] == pytest.approx(-3.0 + c)
        assert s.end[1] == pytest.approx(35.0 - c)
        assert len(s.points) == 3
        assert s.points[1][1] == pytest.approx(16.0)        # crank at crown
        for p in s.points:
            assert p[2] == pytest.approx(basic.deck_top_z(p[1]) - depth_ft)

    # overhang bars stop at the cutoff beyond the fascia girder CL
    oh = by_set["additional overhang"]
    cutoff = 54.0 / 12.0
    tops = [s for s in oh if s.end[1] > 17.0]
    bots = [s for s in oh if s.start[1] < 17.0 - 1e-9]
    assert tops and bots
    for s in tops:
        assert s.start[1] == pytest.approx(32.0 - cutoff)   # fascia y=32
    for s in bots:
        assert s.end[1] == pytest.approx(0.0 + cutoff)      # fascia y=0


def test_rebar_segments_stay_inside_skewed_deck():
    from civilpy.structural.bridge_layout import deck_rebar_segments

    out = layout_bridge(BridgeInput(
        spans_ft=(80.0,), girder_count=4, girder_spacing_ft=9.0,
        girder_label="W36X150", overhang_ft=2.5, skew_deg=30.0))
    tan30 = math.tan(math.radians(30.0))
    segs = deck_rebar_segments(out)
    assert segs
    for s in segs:
        for p in s.points:
            u = p[0] - p[1] * tan30
            assert -1e-6 <= u <= 80.0 + 1e-6
            assert -2.5 - 1e-6 <= p[1] <= 29.5 + 1e-6


def test_rebar_stays_inside_crowned_slab(basic):
    """Regression: bars used to be drawn level, so the bottom mat exited the
    soffit at the crown (over the center girder) and the top mat broke the
    top surface at the deck edges."""
    from civilpy.structural.bridge_layout import deck_rebar_segments

    t_ft = basic.deck.thickness_in / 12.0
    for s in deck_rebar_segments(basic):
        for a, b in zip(s.points[:-1], s.points[1:]):
            # sample along each leg, not just its ends: a straight leg on the
            # crowned surface only stays inside if it never crosses the crown
            for f in (0.0, 0.25, 0.5, 0.75, 1.0):
                y = a[1] + f * (b[1] - a[1])
                z = a[2] + f * (b[2] - a[2])
                top = basic.deck_top_z(y)
                assert z < top - 1e-9, s.rebar_set.name
                assert z > top - t_ft + 1e-9, s.rebar_set.name


def test_barriers_reference_scd_catalog():
    r = railing_by_scd("SBR-1-20")
    assert r.scd == "SBR-1-20"
    with pytest.raises(ValueError):
        railing_by_scd("XX-9-99")

    out = layout_bridge(BridgeInput(
        spans_ft=(60.0,), girder_count=5, girder_spacing_ft=8.0,
        girder_label="W36X150", overhang_ft=3.0))
    assert {b.edge for b in out.barriers} == {"left", "right"}
    assert all(b.designation == "SBR-1-20" for b in out.barriers)


# ── loads and analysis-model builders ─────────────────────────────────────

from civilpy.structural.bridge_layout import (  # noqa: E402
    NOMINAL_PARAPET_PLF_PER_FT,
    _barrier_weight_plf,
    _girder_weight_plf,
    _tributary_widths,
    girder_line_loads,
    grillage_model_from_layout,
    structural_model_from_layout,
)


class _Barrier:
    def __init__(self, weight_plf=None, height_in=None):
        self.weight_plf = weight_plf
        self.height_in = height_in


class TestBarrierWeight:
    def test_cataloged_weight_wins(self):
        assert _barrier_weight_plf(_Barrier(475.0, 42.0)) == 475.0

    def test_estimates_from_height_when_uncataloged(self):
        w = _barrier_weight_plf(_Barrier(None, 42.0))
        assert w == pytest.approx(NOMINAL_PARAPET_PLF_PER_FT * 42.0 / 12.0)

    def test_zero_weight_is_treated_as_missing(self):
        assert _barrier_weight_plf(_Barrier(0.0, 36.0)) == pytest.approx(
            NOMINAL_PARAPET_PLF_PER_FT * 3.0)

    def test_none_when_neither_known(self):
        assert _barrier_weight_plf(_Barrier(None, None)) is None


class TestGirderWeight:
    def test_parsed_from_aisc_label(self):
        assert _girder_weight_plf("W36X150") == 150.0
        assert _girder_weight_plf("w24x104") == 104.0

    def test_falls_back_to_shape_database(self):
        """A label not in WxxXyyy form resolves through steel.W instead."""
        assert _girder_weight_plf("W36X150 ") == 150.0
        w = _girder_weight_plf("HP12X53")
        assert w == pytest.approx(53.0)

    def test_non_numeric_suffix_uses_database(self):
        with pytest.raises(Exception):
            _girder_weight_plf("not-a-shape")


class TestTributaryWidths:
    def test_fascia_take_half_spacing_plus_overhang(self, basic):
        trib = _tributary_widths(basic.inputs)
        s, oh = basic.inputs.girder_spacing_ft, basic.inputs.overhang_ft
        assert len(trib) == basic.inputs.girder_count
        assert trib[0] == pytest.approx(oh + s / 2.0)
        assert trib[-1] == pytest.approx(oh + s / 2.0)
        assert all(t == pytest.approx(s) for t in trib[1:-1])

    def test_total_equals_deck_width(self, basic):
        inp = basic.inputs
        expected = (inp.girder_count - 1) * inp.girder_spacing_ft \
            + 2 * inp.overhang_ft
        assert sum(_tributary_widths(inp)) == pytest.approx(expected)


class TestGirderLineLoads:
    def test_interior_carries_no_barrier(self, basic):
        w = girder_line_loads(basic, 2)
        assert w["dc2"] == 0.0
        assert w["dc1"] > 0 and w["dw"] > 0

    def test_fascia_carries_barrier(self, basic):
        for idx in (0, basic.inputs.girder_count - 1):
            assert girder_line_loads(basic, idx)["dc2"] > 0

    def test_dc1_is_girder_plus_tributary_slab(self, basic):
        from civilpy.structural.bridge_layout import CONCRETE_UNIT_WT_KCF
        w = girder_line_loads(basic, 2)
        trib = _tributary_widths(basic.inputs)[2]
        expected = (_girder_weight_plf(basic.inputs.girder_label) / 1000.0
                    + CONCRETE_UNIT_WT_KCF
                    * basic.deck.thickness_in / 12.0 * trib)
        assert w["dc1"] == pytest.approx(expected)

    def test_fascia_dw_is_less_than_interior_when_overhang_is_short(self, basic):
        """DW scales with tributary width, so a 3 ft overhang on 8 ft spacing
        gives the fascia less wearing surface than an interior line."""
        assert girder_line_loads(basic, 0)["dw"] < \
            girder_line_loads(basic, 2)["dw"]

    @pytest.mark.parametrize("bad", [-1, 5, 99])
    def test_index_out_of_range(self, basic, bad):
        with pytest.raises(IndexError):
            girder_line_loads(basic, bad)


class TestStructuralModelFromLayout:
    def test_one_chain_per_girder_broken_at_supports(self, basic):
        model = structural_model_from_layout(basic)
        inp = basic.inputs
        n_stations = len(inp.spans_ft) + 1
        girders = [e for e in model.elements.values() if e.role == "girder"]
        assert len(girders) == inp.girder_count * (n_stations - 1)
        assert len(model.nodes) == inp.girder_count * n_stations

    def test_every_bearing_becomes_a_restraint(self, basic):
        model = structural_model_from_layout(basic)
        assert len(model.restraints) == len(basic.bearings)
        presets = {r.preset for r in model.restraints.values()}
        assert presets <= {"fixed", "expansion"}

    def test_fixed_restraint_locks_x_expansion_does_not(self, basic):
        model = structural_model_from_layout(basic)
        for r in model.restraints.values():
            assert r.fix_x is (r.preset == "fixed")
            assert r.fix_y and r.fix_z

    def test_diaphragms_tie_adjacent_girders_at_supports(self, basic):
        model = structural_model_from_layout(basic)
        dias = [e for e in model.elements.values() if e.role == "diaphragm"]
        n_stations = len(basic.inputs.spans_ft) + 1
        assert len(dias) == (basic.inputs.girder_count - 1) * n_stations
        assert all(e.metadata["gdr.kind"] == "diaphragm" for e in dias)

    def test_diaphragms_can_be_suppressed(self, basic):
        model = structural_model_from_layout(basic, diaphragms=False)
        assert not [e for e in model.elements.values()
                    if e.role == "diaphragm"]

    def test_dead_loads_are_downward_on_every_girder_element(self, basic):
        model = structural_model_from_layout(basic)
        cases = {ld.case for ld in model.beam_loads}
        assert {"DC1", "DW", "DC2"} <= cases
        assert all(ld.w_start < 0 for ld in model.beam_loads)
        assert all(ld.direction == "GZ" for ld in model.beam_loads)

    def test_dead_loads_can_be_suppressed(self, basic):
        model = structural_model_from_layout(basic, dead_loads=False)
        assert not model.beam_loads

    def test_dc2_only_on_fascia_lines(self, basic):
        model = structural_model_from_layout(basic)
        lines = set()
        for ld in model.beam_loads:
            if ld.case == "DC2":
                lines.add(model.elements[ld.element_id].metadata["gdr.line"])
        assert lines == {"1", str(basic.inputs.girder_count)}

    def test_skew_shifts_nodes_along_x(self):
        layout = layout_bridge(BridgeInput(
            spans_ft=(80.0,), girder_count=4, girder_spacing_ft=9.0,
            girder_label="W36X150", overhang_ft=3.0, skew_deg=30.0))
        model = structural_model_from_layout(layout)
        at_start = sorted((n.y, n.x) for n in model.nodes.values()
                          if n.label.endswith("_S0"))
        xs = [x for _, x in at_start]
        assert xs == sorted(xs) and xs[0] < xs[-1]
        tan = math.tan(math.radians(30.0))
        assert xs[-1] - xs[0] == pytest.approx(3 * 9.0 * tan)


class TestGrillageModelFromLayout:
    def test_deck_plates_and_bare_girders(self, basic):
        model = grillage_model_from_layout(basic)
        plates = [e for e in model.elements.values() if e.role == "deck"]
        girders = [e for e in model.elements.values() if e.role == "girder"]
        assert plates and girders
        assert all(e.midas_type == "PLATE" for e in plates)
        assert all(len(e.nodes) == 4 for e in plates)
        # bare steel: the girder section is the rolled shape, not composite
        assert all(e.section == basic.inputs.girder_label for e in girders)

    def test_rigid_links_tie_deck_to_every_girder_node(self, basic):
        model = grillage_model_from_layout(basic)
        assert model.rigid_links

    def test_composite_links_are_fully_rigid(self, basic):
        model = grillage_model_from_layout(basic, composite=True)
        assert {rl.dof for rl in model.rigid_links} == {"111111"}

    def test_non_composite_frees_longitudinal_slip_except_one_anchor(self,
                                                                    basic):
        model = grillage_model_from_layout(basic, composite=False)
        dofs = [rl.dof for rl in model.rigid_links]
        assert "011111" in dofs, "slip DOF expected off the anchor line"
        assert dofs.count("111111") > 0, "one anchored line expected"
        assert dofs.count("111111") < len(dofs)

    def test_composite_defaults_to_the_input_flag(self):
        inp = BridgeInput(spans_ft=(70.0,), girder_count=4,
                          girder_spacing_ft=8.0, girder_label="W36X150",
                          overhang_ft=3.0, composite=False)
        model = grillage_model_from_layout(layout_bridge(inp))
        assert "011111" in {rl.dof for rl in model.rigid_links}

    def test_seg_target_controls_plate_length(self, basic):
        coarse = grillage_model_from_layout(basic, seg_target_ft=40.0)
        fine = grillage_model_from_layout(basic, seg_target_ft=8.0)
        n_coarse = len([e for e in coarse.elements.values()
                        if e.role == "deck"])
        n_fine = len([e for e in fine.elements.values() if e.role == "deck"])
        assert n_fine > n_coarse

    def test_support_lines_always_get_a_node(self, basic):
        model = grillage_model_from_layout(basic, seg_target_ft=37.0)
        xs = {round(n.x, 6) for n in model.nodes.values()}
        station = 0.0
        for s in basic.inputs.spans_ft:
            station += s
            assert round(station, 6) in xs

    def test_deck_spans_overhang_to_overhang_for_the_full_bridge(self, basic):
        model = grillage_model_from_layout(basic)
        ys = {round(n.y, 6) for n in model.nodes.values()}
        inp = basic.inputs
        assert round(-inp.overhang_ft, 6) in ys
        assert round((inp.girder_count - 1) * inp.girder_spacing_ft
                     + inp.overhang_ft, 6) in ys

    def test_girder_subset_builds_a_construction_phase(self, basic):
        model = grillage_model_from_layout(basic, girder_subset=[0, 1])
        lines = {e.metadata["gdr.line"] for e in model.elements.values()
                 if e.role == "girder"}
        assert lines == {"1", "2"}

    def test_phase_deck_stops_at_the_mid_bay_closure_joint(self, basic):
        model = grillage_model_from_layout(basic, girder_subset=[0, 1])
        ys = {round(n.y, 6) for n in model.nodes.values()}
        s = basic.inputs.girder_spacing_ft
        assert round(-basic.inputs.overhang_ft, 6) in ys   # outer overhang
        assert round(1 * s + s / 2.0, 6) in ys             # closure joint
        assert round((basic.inputs.girder_count - 1) * s
                     + basic.inputs.overhang_ft, 6) not in ys

    def test_interior_phase_is_closure_joint_on_both_sides(self, basic):
        model = grillage_model_from_layout(basic, girder_subset=[1, 2])
        ys = {round(n.y, 6) for n in model.nodes.values()}
        s = basic.inputs.girder_spacing_ft
        assert round(1 * s - s / 2.0, 6) in ys
        assert round(2 * s + s / 2.0, 6) in ys
        assert round(-basic.inputs.overhang_ft, 6) not in ys

    @pytest.mark.parametrize("subset", [[], [0, 2], [2, 0, 3, 1, 4, 6]])
    def test_non_contiguous_subset_rejected(self, basic, subset):
        with pytest.raises(ValueError, match="contiguous"):
            grillage_model_from_layout(basic, girder_subset=subset)

    def test_dead_loads_optional(self, basic):
        assert not grillage_model_from_layout(basic,
                                              dead_loads=False).beam_loads
        assert grillage_model_from_layout(basic, dead_loads=True).beam_loads

    def test_girder_sits_below_the_deck_mid_plane(self, basic):
        model = grillage_model_from_layout(basic)
        gz = [n.z for n in model.nodes.values() if n.label.startswith("G")]
        dz = [n.z for n in model.nodes.values() if n.label.startswith("D")]
        assert max(gz) < min(dz)


# ── remaining geometry accessors and guard paths ──────────────────────────

class TestCrownAndSoffit:
    def test_crown_defaults_to_the_girder_group_centre(self, basic):
        inp = basic.inputs
        assert basic.crown_y_ft == pytest.approx(
            (inp.girder_count - 1) * inp.girder_spacing_ft / 2.0)

    def test_explicit_crown_offset_is_honoured(self):
        layout = layout_bridge(BridgeInput(
            spans_ft=(70.0,), girder_count=5, girder_spacing_ft=8.0,
            girder_label="W36X150", overhang_ft=3.0, crown_offset_ft=6.0))
        assert layout.crown_y_ft == 6.0
        # the crown is the high point of the deck surface
        assert layout.deck_top_z(6.0) > layout.deck_top_z(0.0)
        assert layout.deck_top_z(6.0) > layout.deck_top_z(20.0)

    def test_soffit_is_one_slab_thickness_below_the_top(self, basic):
        for y in (-2.0, 0.0, 7.5, 30.0):
            assert basic.deck_soffit_z(y) == pytest.approx(
                basic.deck_top_z(y) - basic.deck.thickness_in / 12.0)

    def test_soffit_is_parallel_to_the_crowned_top(self, basic):
        drop_top = basic.deck_top_z(0.0) - basic.deck_top_z(10.0)
        drop_bot = basic.deck_soffit_z(0.0) - basic.deck_soffit_z(10.0)
        assert drop_top == pytest.approx(drop_bot)


class TestRebarSegmentGeometry:
    def test_length_ft_sums_the_polyline(self, basic):
        from civilpy.structural.bridge_layout import deck_rebar_segments
        segs = deck_rebar_segments(basic)
        assert segs
        for s in segs[:25]:
            expected = sum(
                math.dist(a, b)
                for a, b in zip(s.points[:-1], s.points[1:]))
            assert s.length_ft == pytest.approx(expected)
            assert s.start == s.points[0]
            assert s.end == s.points[-1]

    def test_crowned_transverse_bars_crank_at_the_crown(self, basic):
        """A transverse bar crossing the crown gains an interior vertex."""
        from civilpy.structural.bridge_layout import deck_rebar_segments
        transverse = [s for s in deck_rebar_segments(basic)
                      if s.rebar_set.direction == "transverse"]
        assert transverse
        assert any(len(s.points) > 2 for s in transverse)

    def test_flat_deck_bars_stay_straight(self):
        layout = layout_bridge(BridgeInput(
            spans_ft=(70.0,), girder_count=5, girder_spacing_ft=8.0,
            girder_label="W36X150", overhang_ft=3.0, cross_slope_pct=0.0))
        from civilpy.structural.bridge_layout import deck_rebar_segments
        transverse = [s for s in deck_rebar_segments(layout)
                      if s.rebar_set.direction == "transverse"]
        assert transverse
        assert all(len(s.points) == 2 for s in transverse)


class TestLayoutGuards:
    @pytest.mark.parametrize("skew", [60.0, -60.0, 75.0, -90.0])
    def test_skew_beyond_60_degrees_rejected(self, skew):
        with pytest.raises(ValueError, match="skew"):
            layout_bridge(BridgeInput(
                spans_ft=(70.0,), girder_count=5, girder_spacing_ft=8.0,
                girder_label="W36X150", overhang_ft=3.0, skew_deg=skew))

    def test_skew_just_under_the_limit_is_accepted(self):
        layout = layout_bridge(BridgeInput(
            spans_ft=(70.0,), girder_count=5, girder_spacing_ft=8.0,
            girder_label="W36X150", overhang_ft=3.0, skew_deg=59.5))
        assert layout.inputs.skew_deg == 59.5


class TestGirderWeightDatabaseFallback:
    def test_label_without_a_weight_suffix_uses_the_shape_database(
            self, monkeypatch):
        """`W36` cannot be parsed, so the AISC database supplies the weight."""
        from civilpy.structural import steel

        class _Shape:
            weight = type("Q", (), {"magnitude": 271.0})()

        monkeypatch.setattr(steel, "W", lambda label: _Shape())
        assert _girder_weight_plf("W36") == pytest.approx(271.0)


class TestModelBuilderEdgeCases:
    def test_bearings_off_the_station_grid_are_skipped(self, basic):
        """A bearing whose station index has no node must not raise."""
        import dataclasses
        stray = dataclasses.replace(basic.bearings[0], station_index=99)
        patched = dataclasses.replace(
            basic, bearings=tuple(basic.bearings) + (stray,))
        model = structural_model_from_layout(patched)
        assert len(model.restraints) == len(basic.bearings)

    def test_grillage_skips_bearings_outside_the_phase(self, basic):
        """Phase 0-1 must ignore bearings on girders it does not build."""
        model = grillage_model_from_layout(basic, girder_subset=[0, 1])
        built = {"1", "2"}
        for r in model.restraints.values():
            node = model.nodes[r.node_id]
            assert node.label.split("_")[0].lstrip("G") in built


class TestGeometryGuardsAndProfileBranches:
    @pytest.mark.parametrize("spacing,overhang", [
        (0.0, 3.0), (-8.0, 3.0), (8.0, -0.5),
    ])
    def test_spacing_and_overhang_guards(self, spacing, overhang):
        with pytest.raises(ValueError,
                           match="spacing must be positive"):
            layout_bridge(BridgeInput(
                spans_ft=(70.0,), girder_count=5,
                girder_spacing_ft=spacing, girder_label="W36X150",
                overhang_ft=overhang))

    def test_design_without_an_overhang_bar(self):
        """BR-1-13 at 12.5 ft effective span needs no extra overhang bar, so
        the rebar schedule must simply omit that set."""
        layout = layout_bridge(BridgeInput(
            spans_ft=(70.0,), girder_count=5, girder_spacing_ft=13.5,
            girder_label="W36X150", overhang_ft=3.0, railing="BR-1-13"))
        names = {r.name for r in layout.deck.rebar}
        assert "additional overhang" not in names
        assert names, "the four standard mats are still scheduled"

    def test_profile_with_no_overhang_has_no_thickened_edge(self):
        """With the deck stopping at the fascia flange tips there is no
        overhang step in the soffit, so the profile is top + uniform slab."""
        layout = layout_bridge(BridgeInput(
            spans_ft=(70.0,), girder_count=5, girder_spacing_ft=8.0,
            girder_label="W36X150", overhang_ft=0.0))
        profile = layout.deck_profile_yz()
        assert profile
        t = layout.deck.thickness_in / 12.0
        t_oh = layout.deck.overhang_thickness_in / 12.0
        depths = [layout.deck_top_z(y) - z for y, z in profile]
        if t_oh > t:
            assert max(depths) == pytest.approx(t, abs=1e-9)

    def test_profile_when_the_crown_sits_outside_the_deck(self):
        """An off-deck crown means no crown break in the surface, so the
        top of the profile is just the two edges."""
        layout = layout_bridge(BridgeInput(
            spans_ft=(70.0,), girder_count=5, girder_spacing_ft=8.0,
            girder_label="W36X150", overhang_ft=3.0,
            crown_offset_ft=-50.0))
        profile = layout.deck_profile_yz()
        ys = [y for y, _ in profile]
        assert -50.0 not in ys
        # a one-way crossfall: the deck falls monotonically across the width
        zs = [layout.deck_top_z(y) for y in sorted({round(y, 6) for y in ys})]
        assert zs == sorted(zs, reverse=True)

    def test_barrier_on_the_far_edge_is_not_double_counted(self, basic):
        """Only the barrier matching the fascia's own edge loads that line."""
        import dataclasses
        left = [b for b in basic.barriers if b.edge == "left"]
        right = [b for b in basic.barriers if b.edge == "right"]
        assert left and right, "fixture should carry a barrier on each edge"
        n = basic.inputs.girder_count
        w0 = girder_line_loads(basic, 0)["dc2"]
        wn = girder_line_loads(basic, n - 1)["dc2"]
        single = dataclasses.replace(basic, barriers=tuple(right))
        assert girder_line_loads(single, 0)["dc2"] == pytest.approx(w0)
        assert girder_line_loads(single, n - 1)["dc2"] == 0.0
        assert wn > 0

    def test_barrier_with_neither_weight_nor_height_adds_nothing(self, basic):
        """An uncataloged barrier of unknown height contributes no DC2 rather
        than a guessed load."""
        import dataclasses
        blank = tuple(
            dataclasses.replace(b, weight_plf=None, height_in=None)
            for b in basic.barriers)
        layout = dataclasses.replace(basic, barriers=blank)
        for idx in (0, basic.inputs.girder_count - 1):
            assert girder_line_loads(layout, idx)["dc2"] == 0.0
        # the rest of the dead load is unaffected
        assert girder_line_loads(layout, 0)["dc1"] == pytest.approx(
            girder_line_loads(basic, 0)["dc1"])
