#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the parametric PSC cross-section input module."""

import math

import matplotlib

matplotlib.use("Agg")

import pytest

import importlib

psbdd = importlib.import_module("civilpy.structural.odot.box_beam_design")

from civilpy.structural.odot import ps_i_beam as psid
from civilpy.structural.psc_section import (
    PSCShape,
    box_beam_shape,
    box_standard_bars,
    i_beam_shape,
    midas_rebar_coordinates,
    midas_strand_coordinates,
    perimeter_bars,
    plot_psc_section,
    point_in_solid,
    rebar_row,
    shipping_strands,
    solid_intervals,
    strands_by_count,
    strands_by_rows,
    strands_from_odot_design,
)


def _poly_area(poly):
    n = len(poly)
    return abs(sum(poly[i][0] * poly[(i + 1) % n][1]
                   - poly[(i + 1) % n][0] * poly[i][1]
                   for i in range(n))) / 2.0


# ── shapes ────────────────────────────────────────────────────────────────
def test_i_beam_shape_carries_the_sheet_data():
    s = i_beam_shape("WF72-49")
    assert s.family == "i-beam"
    assert s.depth_in == 72
    assert len(s.strand_grid) == 62
    assert s.draped_required == ((0.0, 14.0), (0.0, 16.0))
    # drawn outline reproduces the published area to a few percent
    assert _poly_area(s.outline) == pytest.approx(s.area_in2, rel=0.05)


def test_box_beam_shape_geometry():
    s = box_beam_shape("B21-48")
    assert s.family == "box"
    assert s.depth_in == 21 and s.yb_in == 10.40
    # The polygon reproduces the sheet 2/6 dimension chains, so it closes
    # against the PUBLISHED sheet 4/6 area to a fraction of a percent --
    # the residual is the small exterior corner chamfers, not drawn.
    area = _poly_area(s.outline) - sum(_poly_area(v) for v in s.voids)
    assert area == pytest.approx(s.area_in2, rel=0.003)
    # mid-depth scanline sees only the two side walls; at that height the
    # keyway recess has taken 1 1/4 in off each face, so the solid width
    # is 2 x (22.75 - 18) = 9.5 in rather than the nominal 2 x 6
    spans = solid_intervals(s, 10.5)
    assert len(spans) == 2
    assert sum(b - a for a, b in spans) == pytest.approx(9.5)
    # at the soffit the section is full width
    assert solid_intervals(s, 2.0) == [(-24.0, 24.0)]


def test_box_strand_grid_matches_psbd_sheet_2():
    # PSBD-1-25 sheet 2 "STRAND LAYOUT AND BAR SPACING": 2 in and 4 in
    # rows at y = +-2..+-20 (9 SPA @ 2" from 4 in off each face, 4 in gap
    # astride the centerline -- no centerline strand); 6 in row only at
    # the wall locations y = +-20.  In the 2 in row, y = +-16 (8 in off
    # each face) is one of the two minimum bottom #5 bars (note 2), not
    # a strand.  17 in beams get 1.5 in void fillets.
    s = box_beam_shape("B17-48")
    row2 = sorted(y for y, z in s.strand_grid if z == 2.0)
    row4 = sorted(y for y, z in s.strand_grid if z == 4.0)
    row6 = sorted(y for y, z in s.strand_grid if z == 6.0)
    expect = [y for y in range(-20, 21, 2) if y != 0]
    assert row2 == [y for y in expect if abs(y) != 16]
    assert row4 == expect
    assert row6 == [-20.0, 20.0]
    assert all(y != 0.0 for y, _ in s.strand_grid)
    assert len(s.strand_grid) == 40


def test_box_standard_bars_note_2():
    # PSBD-1-25 sheet 2 note 2: minimum longitudinal steel is (4) #5
    # across the top flange + (2) #5 in the bottom; the bottom pair
    # occupies the 2 in row's 8-in-off-face lattice points (y = +-16)
    s = box_beam_shape("CB27-48")
    bars = box_standard_bars(s)
    assert bars.n == 6
    assert all(b.size == 5 for b in bars.bars)
    bot = sorted((b.y, b.z) for b in bars.bars if b.z == 2.0)
    assert bot == [(-16.0, 2.0), (16.0, 2.0)]
    top = [b for b in bars.bars if b.z > 20.0]
    assert len(top) == 4
    assert all(b.z == pytest.approx(24.5) for b in top)
    # the displaced strand locations are not in the permissible grid
    assert (16.0, 2.0) not in s.strand_grid
    assert (-16.0, 2.0) not in s.strand_grid
    with pytest.raises(ValueError):
        box_standard_bars(i_beam_shape("WF36-49"))


def test_shipping_strands_layout_and_merge():
    wf = i_beam_shape("WF72-49")
    ship = shipping_strands(wf)
    assert ship.n == 6
    assert all(z == pytest.approx(69.25) for _, z in ship.points)
    combo = strands_by_count(wf, 30) + ship
    assert combo.n == 36
    assert combo.strand_diameter == pytest.approx(0.6)
    with pytest.raises(ValueError):
        shipping_strands(box_beam_shape("CB27-48"))
    with pytest.raises(ValueError):
        _ = combo + ship          # duplicate locations


def test_box_strand_defaults_are_half_inch():
    # PSBD-1-25 general notes: 0.5 in strand, 0.167 in^2 (vs the I-beam
    # 0.6 in / 0.217 in^2 from PSID-1-13)
    box = strands_by_count(box_beam_shape("B21-48"), 10)
    assert box.strand_area == pytest.approx(0.167)
    assert box.strand_diameter == pytest.approx(0.5)
    wf = strands_by_count(i_beam_shape("WF36-49"), 10)
    assert wf.strand_area == pytest.approx(0.217)
    assert wf.strand_diameter == pytest.approx(0.6)


def test_box_designation_parse_errors():
    with pytest.raises(ValueError):
        box_beam_shape("W21-48")


# ── strand input ─────────────────────────────────────────────────────────
def test_strands_by_count_matches_psid_fill_order():
    layout = strands_by_count(i_beam_shape("WF72-49"), 30)
    assert layout.points == tuple(psid.strand_pattern("WF72-49", 30))
    assert layout.centroid_in == pytest.approx(
        psid.strand_centroid_in(list(layout.points)))
    assert layout.a_ps == pytest.approx(30 * 0.217)


def test_strands_by_count_overflow():
    with pytest.raises(ValueError):
        strands_by_count(i_beam_shape("AASHTO Type 2"), 999)


def test_strands_by_rows_symmetric_and_solid():
    shape = box_beam_shape("B33-48")
    layout = strands_by_rows(shape, {2.0: 14, 4.0: 10})
    assert layout.n == 24
    assert sum(y for y, _ in layout.points) == pytest.approx(0.0)
    assert all(point_in_solid(shape, y, z) for y, z in layout.points)
    # outermost-first on the sheet grid: the 2 in row reaches y = +-20
    row2 = [y for y, z in layout.points if z == 2.0]
    assert max(row2) == 20.0


def test_strands_by_rows_center_fill():
    shape = box_beam_shape("B21-48")
    layout = strands_by_rows(shape, {2.0: 4}, fill="center")
    assert sorted(y for y, _ in layout.points) == [-4.0, -2.0, 2.0, 4.0]


def test_strands_by_rows_overflow():
    with pytest.raises(ValueError):
        strands_by_rows(box_beam_shape("B21-48"), {2.0: 21})


def test_six_inch_row_is_the_wall_locations():
    # PSBD-1-25 sheet 2: the 6 in row has exactly one permissible
    # location per side wall, directly above the row ends (y = +-20)
    shape = box_beam_shape("CB42-48")
    layout = strands_by_rows(shape, {6.0: 2})
    assert sorted(y for y, _ in layout.points) == [-20.0, 20.0]
    assert all(point_in_solid(shape, y, z) for y, z in layout.points)


def test_strands_from_odot_design_reconciles_with_the_table():
    d = psbdd.box_beam_design("CB27-48", 70)
    layout = strands_from_odot_design("CB27-48", 70)
    assert layout.n == d.n_strands
    assert layout.centroid_in == pytest.approx(
        psbdd.strand_group_height_in(d))
    # eccentricity agrees with the sheet's tabulated e to drawing rounding
    assert layout.eccentricity_in == pytest.approx(d.e_beam, abs=0.05)
    assert all(point_in_solid(layout.shape, y, z) for y, z in layout.points)


def test_strands_from_odot_design_unknown_span():
    with pytest.raises(KeyError):
        strands_from_odot_design("CB27-48", 200)


# ── rebar input ──────────────────────────────────────────────────────────
def test_rebar_row_even_spacing_and_cover():
    shape = i_beam_shape("WF48-49")
    row = rebar_row(shape, 5, 6, 45.0, side_cover=2.0)  # top flange band
    assert row.n == 6
    ys = sorted(b.y for b in row.bars)
    steps = {round(ys[i + 1] - ys[i], 6) for i in range(5)}
    assert len(steps) == 1  # even spacing
    (a, b), = [max(solid_intervals(shape, 45.0), key=lambda s: s[1] - s[0])]
    assert ys[0] >= a + 2.0 and ys[-1] <= b - 2.0
    assert row.a_s == pytest.approx(6 * 0.31)


def test_rebar_row_outside_section():
    with pytest.raises(ValueError):
        rebar_row(box_beam_shape("B17-48"), 5, 4, 40.0)


def test_perimeter_bars_land_in_solid():
    shape = box_beam_shape("B27-48")
    cage = perimeter_bars(shape, 4, 12.0, cover=1.5)
    assert cage.n > 8
    assert all(point_in_solid(shape, b.y, b.z) for b in cage.bars)


def test_perimeter_bars_band_filter():
    shape = box_beam_shape("B27-48")
    bottom = perimeter_bars(shape, 4, 12.0, z_max=5.0)
    assert bottom.n and all(b.z <= 5.0 for b in bottom.bars)


def test_rebar_layout_add():
    shape = box_beam_shape("B21-48")
    combo = rebar_row(shape, 5, 4, 2.5) + perimeter_bars(shape, 4, 12.0)
    assert combo.n > 4
    with pytest.raises(ValueError):
        combo + rebar_row(box_beam_shape("B17-48"), 5, 2, 2.5)


# ── preview & export ─────────────────────────────────────────────────────
def test_plot_smoke_i_beam_and_box():
    import matplotlib.pyplot as plt

    shape = i_beam_shape("AASHTO Type 4")
    fig = plot_psc_section(shape, strands_by_count(shape, 20),
                           rebar_row(shape, 5, 4, 50.0))
    plt.close(fig)
    box = box_beam_shape("CB27-48")
    fig = plot_psc_section(box, strands_from_odot_design("CB27-48", 70),
                           perimeter_bars(box, 4, 12.0))
    plt.close(fig)


def test_midas_strand_coordinates_origins():
    layout = strands_from_odot_design("CB27-48", 70)
    rows = midas_strand_coordinates(layout, origin="centroid")
    assert len(rows) == layout.n
    assert rows[0]["AREA"] == pytest.approx(0.167)
    zs_soffit = [r["Z"] for r in midas_strand_coordinates(layout,
                                                          origin="soffit")]
    assert min(zs_soffit) == pytest.approx(2.0)
    assert rows[0]["Z"] == pytest.approx(zs_soffit[0] - layout.shape.yb_in)


def test_midas_rebar_coordinates():
    shape = box_beam_shape("B21-48")
    rows = midas_rebar_coordinates(rebar_row(shape, 6, 4, 2.5),
                                   origin="soffit")
    assert len(rows) == 4
    assert rows[0]["SIZE"] == "#6"
    assert rows[0]["AREA"] == pytest.approx(0.44)


def test_midas_export_requires_yb_for_centroid_origin():
    shape = box_beam_shape("B21-36")  # non-standard width: no published Yb
    layout = strands_by_rows(shape, {2.0: 6})
    with pytest.raises(ValueError):
        midas_strand_coordinates(layout, origin="centroid")


# ── strain-compatibility flexure ─────────────────────────────────────────
from civilpy.structural.aashto.lrfd import prestressed  # noqa: E402
from civilpy.structural.psc_section import (  # noqa: E402
    FlexuralResult,
    PSCShape,
    extreme_fibers,
    flexural_strain_compatibility,
    strand_stress_270,
    StrandLayout,
)


def _rect(width=12.0, height=24.0):
    w2 = width / 2.0
    return PSCShape(name=f"{width:g}x{height:g} rect", family="custom",
                    outline=((-w2, 0.0), (w2, 0.0), (w2, height),
                             (-w2, height)), depth_in=height)


def test_extreme_fibers_from_coordinates():
    assert extreme_fibers(_rect()) == (0.0, 24.0)
    assert extreme_fibers(i_beam_shape("WF72-49")) == (0.0, 72.0)


def test_strand_stress_270_curve():
    # elastic branch: E_p = 28,500 ksi
    assert strand_stress_270(0.002) == pytest.approx(0.002 * 28500, rel=1e-3)
    # PCI handbook spot values for Grade 270 low-lax
    assert strand_stress_270(0.0075) == pytest.approx(205, abs=3)
    assert strand_stress_270(0.02) == pytest.approx(263, abs=3)
    assert strand_stress_270(0.10) == 270.0


def test_rc_rectangle_matches_hand_calc():
    # 12x24 beam, 3-#9 at d = 21 in, f'c = 4 ksi, fy = 60:
    #   a = As fy / (0.85 f'c b) = 4.412 in, c = a/0.85 = 5.19 in
    #   Mn = As fy (d - a/2) = 281.9 kip-ft
    rect = _rect()
    bars = rebar_row(rect, 9, 3, 3.0)
    r = flexural_strain_compatibility(rect, rebar=bars, f_c=4.0)
    assert abs(r.residual_kips) < 1e-3
    assert r.c_in == pytest.approx(5.19, abs=0.02)
    assert r.m_n_kipft == pytest.approx(281.9, rel=0.005)
    assert r.d_t_in == pytest.approx(21.0)
    assert r.eps_t == pytest.approx(0.003 * (21 - r.c_in) / r.c_in)
    assert r.phi == 1.0


def test_psc_rectangle_agrees_with_lrfd_approximate():
    # strain compatibility vs the 5.6.3.1.1 approximate fps -- the two
    # methods legitimately differ a little; agree within 5%
    rect = _rect()
    pts = tuple((y, 4.0) for y in (-5, -3, -1, 1, 3, 5))
    strands = StrandLayout(rect, pts)          # 6 x 0.217 at d_p = 20
    r = flexural_strain_compatibility(rect, strands, f_c=6.0, f_pe=160.0)
    approx = prestressed.ps_strand_stress_at_nominal(
        a_ps=6 * 0.217, f_pu=270.0, d_p=20.0, f_c=6.0, b=12.0)
    assert r.f_ps_extreme_ksi == pytest.approx(approx.capacity, rel=0.05)
    assert abs(r.residual_kips) < 1e-3


def test_box_sagging_tension_controlled():
    strands = strands_from_odot_design("CB27-48", 70)
    r = flexural_strain_compatibility(strands.shape, strands,
                                      f_c=7.0, f_pe=160.0)
    assert abs(r.residual_kips) < 1e-3
    # compression block stays in the 5.5 in top flange; c = a / beta1(7)
    assert r.a_in < 5.5 and r.a_in == pytest.approx(0.70 * r.c_in)
    assert r.d_t_in == pytest.approx(25.0)     # bottom row, 2 in up
    assert r.eps_t > 0.005 and r.phi == 1.0
    assert r.m_n_kipft > 0.0
    assert r.c_c_kips == pytest.approx(r.t_ps_kips, abs=1e-3)


def test_box_hogging_flips_the_compression_fiber():
    strands = strands_from_odot_design("CB27-48", 70)
    r = flexural_strain_compatibility(strands.shape, strands,
                                      f_c=7.0, f_pe=160.0,
                                      bending="hogging")
    assert abs(r.residual_kips) < 1e-3
    # all steel sits near the (now) compression fiber: this design has no
    # 6 in row, so d_t is the 4 in row and the section is
    # compression-controlled
    assert r.d_t_in == pytest.approx(4.0)
    assert r.eps_t < 0.002 and r.phi == 0.75


def test_strain_compatibility_needs_steel():
    with pytest.raises(ValueError):
        flexural_strain_compatibility(_rect(), f_c=4.0)


# ── per-component detail (guide eqs 1.3-1.6) and composite topping ───────
from civilpy.structural.psc_section import composite_topping  # noqa: E402


def test_bar_detail_matches_the_hand_calc_identities():
    # tension bars past yield report f_s = f_y and T_s = Sigma A_s*f_s
    rect = _rect()
    r = flexural_strain_compatibility(rect, rebar=rebar_row(rect, 9, 3, 3.0),
                                      f_c=4.0)
    assert len(r.bar_forces) == 3 and len(r.table()) == 3
    for b in r.bar_forces:
        assert b.eps == pytest.approx(0.003 * (b.d_in - r.c_in) / r.c_in)
        assert b.f_ksi == 60.0          # yielded: f_s = f_y
    assert r.t_s_tension_kips == pytest.approx(3 * 1.0 * 60.0)
    assert r.c_s_kips == 0.0
    assert r.t_s_kips == pytest.approx(r.t_s_tension_kips - r.c_s_kips)


def test_compression_steel_eps_and_bare_force():
    # top bars: eps_s' = (c - d_c)/c * eps_cu (compression), and with the
    # displaced-concrete credit off the force is the bare A_s'*f_s' of the
    # guide's eq 1.3
    rect = _rect()
    bars = rebar_row(rect, 9, 3, 3.0) + rebar_row(rect, 8, 2, 21.5)
    r = flexural_strain_compatibility(rect, rebar=bars, f_c=4.0,
                                      displaced_concrete_credit=False)
    top = [b for b in r.bar_forces if b.d_in == pytest.approx(2.5)]
    assert len(top) == 2
    for b in top:
        eps_prime = (r.c_in - b.d_in) / r.c_in * 0.003   # guide eq 1.4
        assert b.eps == pytest.approx(-eps_prime)
        f_prime = min(eps_prime * 29000.0, 60.0)         # guide eq 1.5
        assert b.f_ksi == pytest.approx(-f_prime)
        assert b.force_kips == pytest.approx(-0.79 * f_prime)  # eq 1.3
    assert r.c_s_kips == pytest.approx(2 * 0.79 * f_prime)


def test_tendon_force_is_the_per_strand_sum():
    # T_ps = Sigma A_p * f_ps (guide eq 1.6), every strand at its own
    # compatibility strain through the power formula
    strands = strands_from_odot_design("CB27-48", 70)
    r = flexural_strain_compatibility(strands.shape, strands,
                                      f_c=7.0, f_pe=160.0,
                                      displaced_concrete_credit=False)
    assert len(r.tendon_forces) == 32
    assert r.t_ps_kips == pytest.approx(
        sum(t.force_kips for t in r.tendon_forces))
    for t in r.tendon_forces:
        assert t.force_kips == pytest.approx(0.167 * t.f_ksi)
        assert t.f_ksi == pytest.approx(
            strand_stress_270(160.0 / 28500.0 + t.eps - 160.0 / 28500.0),
            rel=1e-6)


def test_composite_topping_deepens_and_strengthens():
    strands = strands_from_odot_design("CB27-48", 70)
    bare = flexural_strain_compatibility(strands.shape, strands,
                                         f_c=7.0, f_pe=160.0)
    top = composite_topping(strands.shape)          # 5 in x 48 in slab
    comp = flexural_strain_compatibility(strands.shape, strands,
                                         f_c=7.0, f_pe=160.0,
                                         topping=top, topping_f_c=4.5)
    assert abs(comp.residual_kips) < 1e-3
    # extreme fiber moves to the top of the topping: d_t grows by 5 in
    assert comp.d_t_in == pytest.approx(bare.d_t_in + 5.0)
    # beta1 comes from the topping concrete at the compression fiber
    assert comp.a_in == pytest.approx(0.825 * comp.c_in)
    # 4.5 ksi topping alone can't hold T_ps: block reaches the girder
    assert comp.a_in > 5.0
    assert comp.m_n_kipft > bare.m_n_kipft
    assert comp.phi == 1.0


def test_topping_requires_both_args():
    strands = strands_from_odot_design("CB27-48", 70)
    with pytest.raises(ValueError):
        flexural_strain_compatibility(
            strands.shape, strands, f_c=7.0,
            topping=composite_topping(strands.shape))


# ── torsion properties from geometry ─────────────────────────────────────
from civilpy.structural.psc_section import torsion_properties  # noqa: E402


def test_box_torsion_properties_hand_calc():
    # CB27-48 outer perimeter encloses 48 x 27 less the keyway recesses
    # and top setback; wall midlines: width (48+36)/2 = 42, height
    # (27+16)/2 = 21.5 -> Ao = 903;  be = min(webs 6, flanges 5.5, Acp/pc).
    tp = torsion_properties(box_beam_shape("CB27-48"))
    assert tp.a_cp == pytest.approx(1247.25, abs=0.05)
    assert tp.a_o == pytest.approx(42.0 * 21.5)
    assert tp.p_h == pytest.approx(2.0 * (42.0 + 21.5))
    assert tp.b_e == pytest.approx(5.5)


def test_solid_shape_has_no_flow_path():
    tp = torsion_properties(i_beam_shape("AASHTO Type 2"))
    assert tp.a_o is None and tp.p_h is None and tp.b_e is None
    assert tp.a_cp > 0 and tp.p_c > 0


# ── Midas payload builders (schemas verified live 2026-07-27) ────────────
from civilpy.structural.psc_section import (  # noqa: E402
    midas_section_payload,
    midas_tendon_payloads,
)


def test_midas_section_payload_carries_the_polygons():
    box = box_beam_shape("CB27-48")
    p = midas_section_payload(box)
    assert p["SECTTYPE"] == "PSC"
    assert p["SECT_BEFORE"]["SHAPE"] == "VALU"
    outer = p["SECT_BEFORE"]["SECT_I"]["OUTER_POLYGON"][0]["VERTEX"]
    assert len(outer) == len(box.outline)
    inner = p["SECT_BEFORE"]["SECT_I"]["INNER_POLYGON"][0]["VERTEX"]
    assert len(inner) == len(box.voids[0])
    # HT, BT and the summed webs.  The default web thickness is measured
    # from the geometry at mid-depth, where the keyway recess has taken
    # 1 1/4 in off each face -- 2 x 4.75 = 9.5 in, not the nominal 2 x 6.
    assert p["SECT_BEFORE"]["SECT_I"]["vSIZE"][:2] == [27.0, 48.0]
    assert p["SECT_BEFORE"]["WEB_THICK"][0] == pytest.approx(9.5)


class TestShearKey:
    """The grouted key between two adjacent boxes."""

    def test_mirrors_the_box_keyway(self):
        from civilpy.structural.odot import (
            KEYWAY_BOTTOM_BAND_IN, KEYWAY_RECESS_DEPTH_IN,
            KEYWAY_TOP_SETBACK_IN)
        from civilpy.structural.psc_section import shear_key_shape

        key = shear_key_shape("CB27-48")
        ys = [y for y, _ in key.outline]
        zs = [z for _, z in key.outline]
        # widest at the recess (both faces), narrowest at the top slot
        assert max(ys) == pytest.approx(KEYWAY_RECESS_DEPTH_IN)
        assert max(ys) - min(ys) == pytest.approx(2 * KEYWAY_RECESS_DEPTH_IN)
        assert sorted(set(ys))[-2] == pytest.approx(KEYWAY_TOP_SETBACK_IN)
        # starts at the top of the bearing band, runs to the beam top
        assert min(zs) == pytest.approx(KEYWAY_BOTTOM_BAND_IN)
        assert max(zs) == pytest.approx(27.0)

    def test_area_grows_with_depth(self):
        from civilpy.structural.psc_section import (
            _poly_area_perimeter, shear_key_shape)

        areas = [_poly_area_perimeter(shear_key_shape(b).outline)[0]
                 for b in ("B17-48", "B21-48", "CB27-48", "CB33-48",
                           "CB42-48")]
        assert areas == sorted(areas)
        assert areas[2] == pytest.approx(48.19, abs=0.01)   # CB27-48

    def test_centroid_matches_the_published_box_yb(self):
        """The same routine that places the key must reproduce Yb."""
        from civilpy.structural.psc_section import (
            box_beam_shape, shape_centroid_in)

        for b in ("B17-48", "B21-48", "CB27-48", "CB42-48"):
            shape = box_beam_shape(b)
            y_c, z_c = shape_centroid_in(shape)
            assert y_c == pytest.approx(0.0, abs=1e-9)
            assert z_c == pytest.approx(shape.yb_in, rel=0.002)

    def test_cb33_published_yb_is_the_known_outlier(self):
        """PSBD-1-25 publishes Yb = 16.50 for the 33 in box -- exactly
        D/2, which a singly-symmetric section does not have.  The drawn
        geometry gives 16.35, and the same geometry reproduces the
        published Ib and Ab at every depth including this one, so the
        table's Yb (and the St/Sb derived from it, by ~0.9%) is the thing
        out of step, not the model.  Raised with ODOT; pinned here so the
        discrepancy cannot be silently "fixed" by drifting geometry.
        """
        from civilpy.structural.psc_section import (
            box_beam_shape, shape_centroid_in)

        shape = box_beam_shape("CB33-48")
        assert shape.yb_in == 16.50
        assert shape_centroid_in(shape)[1] == pytest.approx(16.35, abs=0.01)

    def test_rejects_a_non_box_designation(self):
        from civilpy.structural.psc_section import shear_key_shape

        with pytest.raises(ValueError, match="not of the form"):
            shear_key_shape("WF72-49")


class TestSectionPayloadConstraints:
    """Both established by bisecting a rejected section live (2026-07-29);
    each surfaces only as "Section input data contain errors."."""

    def test_polygon_is_dropped_onto_z_zero(self):
        from civilpy.structural.psc_section import (
            midas_section_payload, shear_key_shape)

        key = shear_key_shape("CB27-48")          # drawn at z = 5 .. 27
        p = midas_section_payload(key)
        zs = [v["Y"] for v in
              p["SECT_BEFORE"]["SECT_I"]["OUTER_POLYGON"][0]["VERTEX"]]
        assert min(zs) == pytest.approx(0.0)
        assert max(zs) == pytest.approx(22.0)

    def test_winding_is_forced_counter_clockwise(self):
        from civilpy.structural.psc_section import (
            PSCShape, midas_section_payload)

        cw = ((0.0, 0.0), (0.0, 10.0), (4.0, 10.0), (4.0, 0.0))
        p = midas_section_payload(
            PSCShape(name="cw", family="box", outline=cw, depth_in=10.0))
        got = [(v["X"], v["Y"]) for v in
               p["SECT_BEFORE"]["SECT_I"]["OUTER_POLYGON"][0]["VERTEX"]]
        area = sum(y0 * z1 - y1 * z0 for (y0, z0), (y1, z1)
                   in zip(got, got[1:] + got[:1]))
        assert area > 0

    def test_scales_into_the_models_length_unit(self):
        from civilpy.structural.psc_section import (
            box_beam_shape, midas_section_payload)

        box = box_beam_shape("CB27-48")
        ft = midas_section_payload(box, length_unit="ft")
        assert ft["SECT_BEFORE"]["SECT_I"]["vSIZE"][:2] == [27.0 / 12,
                                                            48.0 / 12]

    def test_rejects_an_unknown_length_unit(self):
        from civilpy.structural.psc_section import (
            box_beam_shape, midas_section_payload)

        with pytest.raises(ValueError, match="unsupported model length unit"):
            midas_section_payload(box_beam_shape("CB27-48"),
                                  length_unit="furlong")


def test_midas_tendon_payloads_conventions():
    strands = strands_from_odot_design("CB27-48", 70)
    p = midas_tendon_payloads(strands, elems=list(range(1, 15)),
                              length_in=840.0, matl_id=2,
                              jack_stress_ksi=202.5)
    prop = p["TDNT"]["1"]
    assert prop["LT"] == "PRE" and prop["bBONDED"] is True
    assert prop["AREA"] == pytest.approx(0.167)
    assert prop["D_AREA"] > 0.0          # Civil NX rejects zero duct dims
    assert prop["RV"] == 45 and prop["US"] == 270.0
    assert len(p["TDNA"]) == 32 and len(p["TDPL"]) == 32
    t1 = p["TDNA"]["1"]
    assert t1["SHAPE"] == "STRAIGHT" and t1["LENG_OPT"] == "AUTO2"
    # z about the element axis (= centroid at 13.5 for this box):
    zs = {pt["PT"][2] for t in p["TDNA"].values() for pt in t["PROF"]}
    assert zs == {2.0 - 13.5, 4.0 - 13.5}
    assert p["TDPL"]["1"]["ITEMS"][0]["BEGIN"] == 202.5


# ── Midas vehicle payloads (schemas verified live 2026-07-27) ────────────
from civilpy.structural.aashto.vehicles import EMERGENCY_VEHICLES  # noqa: E402
from civilpy.structural.midas_models import (  # noqa: E402
    midas_standard_vehicle,
    midas_vehicle_payload,
)


def test_ev3_user_vehicle_payload():
    v = midas_vehicle_payload(EMERGENCY_VEHICLES["EV3"], im_percent=33.0)
    assert v["VEHICLE_LOAD_NUM"] == 2
    assert v["USER_LOAD_TYPE"] == "Truck/Lane"
    loads = [i["POINT_LOAD"] for i in v["LOAD_ITEMS"]]
    dists = [i["POINT_DIST"] for i in v["LOAD_ITEMS"]]
    assert loads == [24.0, 31.0, 31.0]
    assert dists == [15.0 * 12, 4.0 * 12, 0.0]   # spacings in inches
    assert v["VEH_DEFAULT"]["DYN_LOAD_ALLOWANCE"] == 33.0


def test_vehicle_spacings_follow_the_model_length_unit():
    """A truck built in inches and pushed to a model in feet is 12x too
    long, stores cleanly, and just produces the wrong envelope."""
    v = midas_vehicle_payload(EMERGENCY_VEHICLES["EV3"], length_unit="ft")
    assert [i["POINT_DIST"] for i in v["LOAD_ITEMS"]] == [15.0, 4.0, 0.0]
    lane = v["VEH_DEFAULT"]["UNIFORM_LOAD"]
    assert lane == pytest.approx(
        midas_vehicle_payload(EMERGENCY_VEHICLES["EV3"],
                              length_unit="in")["VEH_DEFAULT"]["UNIFORM_LOAD"]
        * 12.0)


def test_standard_vehicle_carries_standard_code():
    v = midas_standard_vehicle("HL-93TRK")
    assert v["STANDARD_CODE"] == "AASHTO-LRFD"   # required or zero load
    assert v["VEHICLE_LOAD_NUM"] == 1
    ohio = midas_standard_vehicle("OH Legal load 5C1",
                                  standard_code="OHDOT LOAD",
                                  im_percent=0.0)
    assert ohio["STANDARD_CODE"] == "OHDOT LOAD"
