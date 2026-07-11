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
    # soffit parallels the top between the overhang tapers, which start at
    # the outboard flange edges so the haunches land flush (BDM 309.3.5)
    half_bf = basic.section.flange_width / 2.0 / 12.0
    soffit_at = {y: z for y, z in prof[3:]}
    assert soffit_at[16.0] == pytest.approx(-8.5 / 12.0)
    assert soffit_at[-half_bf] == pytest.approx(
        basic.deck_top_z(-half_bf) - 8.5 / 12.0)
    assert soffit_at[32.0 + half_bf] == pytest.approx(
        basic.deck_top_z(32.0 + half_bf) - 8.5 / 12.0)


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
