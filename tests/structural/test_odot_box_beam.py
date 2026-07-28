#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Spot-checks of the Ohio DOT prestressed box beam construction details
against PSBD-1-25."""

import pytest

from civilpy.structural.odot import (
    ANCHOR_DOWEL,
    BEARING_DESIGN_DATA,
    BEVELED_LOAD_PLATE,
    BOX_BEAM_DEPTHS,
    BOX_SECTION_PROPERTIES,
    BOX_FLANGE_THICKNESS_IN,
    BOX_WEB_THICKNESS_IN,
    PSBD_2_07_SECTION_PROPERTIES,
    BOX_WIDTH_IN,
    DESIGN_DATA_SHEET,
    DESIGN_SPEC,
    SHEAR_KEY,
    TIE_ROD,
    bearing_pad,
    box_beam_design,
    box_section_properties,
    box_void_dimensions,
    diaphragm_count,
    diaphragm_end_offset,
    diaphragm_stations_ft,
    layout_load_plate,
    load_plate_bevel,
    strand_group_height_in,
)


class TestDesignSpec:
    """Design stresses and materials (PSBD-1-25 sheet 1/6)."""

    def test_concrete_ranges(self):
        assert DESIGN_SPEC.fc_28day_range == (5.5, 7.0)
        assert DESIGN_SPEC.fci_release_range == (4.0, 5.0)
        assert DESIGN_SPEC.fc_cast_in_place == 4.5

    def test_strand(self):
        assert DESIGN_SPEC.strand_grade == 270
        assert DESIGN_SPEC.strand_diameter == 0.5
        assert DESIGN_SPEC.strand_area_options == (0.153, 0.167)

    def test_reinforcing_yield(self):
        assert DESIGN_SPEC.fy_reinforcing == 60.0

    def test_beam_depths(self):
        assert BOX_BEAM_DEPTHS == (17, 21, 27, 33, 42)

    def test_design_data_sheet_is_referenced_not_transcribed(self):
        # The section/strand/load-rating tables live on PSBDD-1-25.
        assert DESIGN_DATA_SHEET == "PSBDD-1-25"


class TestTieRod:
    """Transverse tie rods (PSBD-1-25 sheets 1 & 4)."""

    def test_specs(self):
        assert TIE_ROD.diameter == 1.0
        assert TIE_ROD.torque_ft_lb == 250.0
        assert TIE_ROD.max_beams_per_rod == 3
        assert TIE_ROD.thread_root_min_diameter == 0.838
        assert TIE_ROD.hole_min_diameter == 2.0
        assert TIE_ROD.hole_max_diameter == 3.0

    def test_vertical_position_shallow(self):
        # 17-27 in deep beams -> 9 in.
        for d in (17, 21, 27):
            assert TIE_ROD.vertical_position(d) == 9.0

    def test_vertical_position_deep(self):
        # 33-42 in deep beams -> 14 in.
        for d in (33, 42):
            assert TIE_ROD.vertical_position(d) == 14.0

    def test_vertical_position_rejects_nonstandard(self):
        with pytest.raises(ValueError):
            TIE_ROD.vertical_position(24)


class TestAnchorDowelAndShearKey:
    def test_anchor_dowel(self):
        assert ANCHOR_DOWEL.diameter == 1.0
        assert ANCHOR_DOWEL.beam_hole_diameter == 2.0
        assert ANCHOR_DOWEL.beam_hole_diameter_compression_seal == 2.5
        assert ANCHOR_DOWEL.expansion_substructure_hole_min == 1.25

    def test_shear_key(self):
        assert SHEAR_KEY.grout_depth_from_top == 5.0
        assert SHEAR_KEY.end_shear_key_depth == 1.0
        assert SHEAR_KEY.end_shear_key_width == 38.0
        assert SHEAR_KEY.composite_backer_rod_min == 2.0


class TestDiaphragms:
    """Intermediate diaphragm placement (PSBD-1-25 sheet 4/6)."""

    def test_count_one_diaphragm(self):
        assert diaphragm_count(40.0) == 1
        assert diaphragm_count(50.0) == 1  # boundary inclusive

    def test_count_two_diaphragms(self):
        assert diaphragm_count(60.0) == 2
        assert diaphragm_count(75.0) == 2  # boundary inclusive

    def test_count_three_diaphragms(self):
        assert diaphragm_count(80.0) == 3

    def test_end_offset_shallow(self):
        assert diaphragm_end_offset(17) == 24.0
        assert diaphragm_end_offset(21) == 24.0

    def test_end_offset_deep(self):
        for d in (27, 33, 42):
            assert diaphragm_end_offset(d) == 30.0

    def test_end_offset_rejects_nonstandard(self):
        with pytest.raises(ValueError):
            diaphragm_end_offset(30)


class TestBearings:
    """Standard elastomeric bearing pads (PSBD-1-25 sheet 6/6)."""

    def test_b1(self):
        b = bearing_pad("B1")
        assert (b.length, b.width) == (7.0, 11.0)
        assert b.total_thickness == 1.409
        assert b.n_laminates == 2
        assert b.max_total_load == 36.0
        assert b.max_expansion_length == 92.0
        assert b.max_movement == 0.530

    def test_b2(self):
        b = bearing_pad("B2")
        assert (b.length, b.width) == (9.0, 14.0)
        assert b.total_thickness == 2.014
        assert b.n_laminates == 3
        assert b.max_total_load == 74.0
        assert b.max_movement == 0.847

    def test_b2_heavier_than_b1(self):
        assert bearing_pad("B2").max_total_load > bearing_pad("B1").max_total_load

    def test_design_data(self):
        d = BEARING_DESIGN_DATA
        assert d.durometer == 50
        assert d.allowable_compressive_stress == 1.25
        assert d.shear_modulus_compressive == 0.095
        assert d.shear_modulus_horizontal == 0.130
        assert d.creep_deflection_percent == 25.0
        assert d.bearings_per_beam == 4


class TestSectionProperties:
    """Cross-section geometry and tabulated properties (PSBD-1-25 sheets 3
    & 4/6)."""

    def test_all_standard_depths_present(self):
        assert set(BOX_SECTION_PROPERTIES) == set(BOX_BEAM_DEPTHS)

    def test_cb27_48_beam_only(self):
        s = box_section_properties(27)
        assert s.width == BOX_WIDTH_IN
        assert s.area == pytest.approx(689.3)
        assert s.i == pytest.approx(65398)
        assert s.yb == pytest.approx(13.38)
        assert s.zt == pytest.approx(4802)
        assert s.zb == pytest.approx(4888)

    def test_cb27_48_composite(self):
        s = box_section_properties(27)
        assert s.ic == pytest.approx(111083)
        assert s.ybc == pytest.approx(17.44)
        assert s.ztc == pytest.approx(11620)
        assert s.zbc == pytest.approx(6369)

    @pytest.mark.parametrize("depth", BOX_BEAM_DEPTHS)
    def test_tabulated_moduli_agree_with_inertia_and_centroid(self, depth):
        """The sheet's own values are self-consistent: S = I/c about both
        the beam-only and composite centroids.  This is what caught the
        table being wrong -- transcribe a value badly and it stops closing.
        """
        s = box_section_properties(depth)
        assert s.zb == pytest.approx(s.i / s.yb, rel=1e-3)
        assert s.zt == pytest.approx(s.i / (s.depth - s.yb), rel=1e-3)
        assert s.zbc == pytest.approx(s.ic / s.ybc, rel=1e-3)
        # composite top modulus is referenced to the top of the PRECAST
        # beam, not the top of the topping
        assert s.ztc == pytest.approx(s.ic / (s.depth - s.ybc), rel=1e-3)

    @pytest.mark.parametrize("depth", BOX_BEAM_DEPTHS)
    def test_legacy_psbd_2_07_table_self_consistent(self, depth):
        """The superseded 2007 table (5 1/2 in walls, 37 in void) must be
        equally self-consistent -- it's what existing bridges rate against."""
        s = PSBD_2_07_SECTION_PROPERTIES[depth]
        assert s.zb == pytest.approx(s.i / s.yb, rel=2e-3)
        assert s.zt == pytest.approx(s.i / (s.depth - s.yb), rel=2e-3)
        assert s.zbc == pytest.approx(s.ic / s.ybc, rel=2e-3)
        assert s.ztc == pytest.approx(s.ic / (s.depth - s.ybc), rel=2e-3)

    def test_legacy_table_is_the_2007_sheet(self):
        # spot values straight off PSBD-2-07 sheet 4/4 (the values civilpy
        # carried, mis-attributed to PSBD-1-25, until 2026-07-28)
        s = PSBD_2_07_SECTION_PROPERTIES[27]
        assert (s.area, s.i, s.yb) == (713.8, 66222, 13.39)
        assert (s.ic, s.ybc) == (109704, 17.13)

    @pytest.mark.parametrize("depth", BOX_BEAM_DEPTHS)
    def test_drawn_geometry_reproduces_published_table(self, depth):
        """The sheet 2/6 dimensions and the sheet 4/6 table agree.

        This is the check that matters: recomputing Ab / Yb / Ib from the
        drawn section lands within a fraction of a percent of the
        published values at every depth (residual = the small exterior
        corner chamfers, which the polygon omits).
        """
        import numpy as np

        from civilpy.structural.psc_section import box_beam_shape

        def moments(poly):
            p = np.asarray(poly, float)
            y, z = p[:, 0], p[:, 1]
            y2, z2 = np.roll(y, -1), np.roll(z, -1)
            cr = y * z2 - y2 * z
            return (abs(cr.sum() / 2.0),
                    abs(((z + z2) * cr).sum() / 6.0),
                    abs(((z ** 2 + z * z2 + z2 ** 2) * cr).sum() / 12.0))

        shape = box_beam_shape(f"B{depth}-48")
        a_o, q_o, i_o = moments(shape.outline)
        a_v, q_v, i_v = moments(shape.voids[0])
        area, q, i0 = a_o - a_v, q_o - q_v, i_o - i_v
        yb = q / area
        pub = box_section_properties(depth)
        assert area == pytest.approx(pub.area, rel=0.003)
        assert i0 - area * yb ** 2 == pytest.approx(pub.i, rel=0.003)
        # Yb lands within a hundredth at 17/21/27/42.  The 33 in row is
        # the one outlier: the sheet publishes Yb = 16.50 = D/2 exactly
        # (and St = Sb = 6646 with it), i.e. it was computed as if the
        # section were symmetric, where the drawn section gives 16.34.
        tol = 0.2 if depth == 33 else 0.02
        assert yb == pytest.approx(pub.yb, abs=tol)

    def test_deeper_beam_has_larger_area_and_inertia(self):
        depths = sorted(BOX_SECTION_PROPERTIES)
        areas = [box_section_properties(d).area for d in depths]
        inertias = [box_section_properties(d).i for d in depths]
        assert areas == sorted(areas)
        assert inertias == sorted(inertias)

    def test_rejects_nonstandard_depth(self):
        with pytest.raises(ValueError, match="non-standard beam depth"):
            box_section_properties(30)

    def test_void_dimensions_match_wall_thickness(self):
        # PSBD-1-25 sheet 2/6: 6 in webs -> 36 in void; 5 1/2 in flanges
        # -> void height = D - 11
        for d in BOX_BEAM_DEPTHS:
            w, h = box_void_dimensions(d)
            assert w == pytest.approx(BOX_WIDTH_IN - 2 * BOX_WEB_THICKNESS_IN)
            assert h == pytest.approx(d - 2 * BOX_FLANGE_THICKNESS_IN)

    def test_void_dimensions_spot_values(self):
        assert box_void_dimensions(27) == pytest.approx((36.0, 16.0))
        assert box_void_dimensions(17) == pytest.approx((36.0, 6.0))
        assert box_void_dimensions(42) == pytest.approx((36.0, 31.0))


class TestDiaphragmStations:
    def test_single_diaphragm_at_midspan(self):
        assert diaphragm_stations_ft(40.0, 27) == (20.0,)

    def test_two_diaphragms_symmetric(self):
        stations = diaphragm_stations_ft(60.0, 27)
        assert len(stations) == 2
        assert stations[0] == pytest.approx(60.0 - stations[1])
        offset_ft = 30.0 / 12.0
        assert stations[0] == pytest.approx(offset_ft)
        assert stations[1] == pytest.approx(60.0 - offset_ft)

    def test_three_diaphragms_include_midspan(self):
        stations = diaphragm_stations_ft(90.0, 33)
        assert len(stations) == 3
        assert stations[1] == pytest.approx(45.0)


class TestStrandGroupHeight:
    def test_matches_section_eccentricity(self):
        # strand_group_height = Yb - e_beam, within the sheet's rounding.
        d = box_beam_design("CB27-48", 50)
        s = box_section_properties(27)
        h = strand_group_height_in(d)
        assert h == pytest.approx(s.yb - d.e_beam, abs=0.05)

    def test_weighted_average(self):
        d = box_beam_design("CB17-48", 20)
        assert (d.strands_2in, d.strands_4in, d.strands_6in) == (8, 4, 0)
        assert strand_group_height_in(d) == pytest.approx((8 * 2 + 4 * 4) / 12)

    def test_rejects_zero_strands(self):
        from civilpy.structural.odot.box_beam_design import BoxBeamDesign
        d = BoxBeamDesign(
            beam_type="composite", box="X", depth=17, width=48, span=20,
            e_beam=1.0, e_composite=None, n_strands=0, strands_2in=0,
            strands_4in=0, strands_6in=0, stirrup_w_pairs=0, stirrup_zone_x=0,
            stirrup_y=0, stirrup_z=0, camber_d0=0, camber_d30=0, deflection=0,
            bearing_type="B1")
        with pytest.raises(ValueError, match="no strands"):
            strand_group_height_in(d)


class TestBeveledLoadPlate:
    """BD-1-11 beveled steel load plate."""

    def test_catalog_constants(self):
        assert BEVELED_LOAD_PLATE.min_thickness == 1.5
        assert BEVELED_LOAD_PLATE.anchor_rod_diameter == 0.75
        assert BEVELED_LOAD_PLATE.expansion_anchor_hole == 1.25

    def test_bevel_formula(self):
        import math
        trans, long_ = load_plate_bevel(0.04, 30.0)
        assert trans == pytest.approx(0.04 * math.sin(math.radians(30.0)))
        assert long_ == pytest.approx(0.04 * math.cos(math.radians(30.0)))

    def test_bevel_zero_skew_is_pure_longitudinal(self):
        trans, long_ = load_plate_bevel(0.04, 0.0)
        assert trans == pytest.approx(0.0)
        assert long_ == pytest.approx(0.04)

    def test_layout_sized_to_bearing_pad(self):
        pad = bearing_pad("B1")
        lay = layout_load_plate("B1")
        length = lay.bottom_face[1][0] - lay.bottom_face[0][0]
        width = lay.bottom_face[2][1] - lay.bottom_face[1][1]
        assert length == pytest.approx(pad.length)
        assert width == pytest.approx(pad.width)

    def test_layout_flat_when_no_grade(self):
        lay = layout_load_plate("B1", longitudinal_grade=0.0, skew_deg=0.0)
        zs = {round(p[2], 9) for p in lay.top_face}
        assert len(zs) == 1
        assert zs.pop() == pytest.approx(BEVELED_LOAD_PLATE.min_thickness)

    def test_layout_tilts_with_grade(self):
        lay = layout_load_plate("B1", longitudinal_grade=0.04, skew_deg=0.0)
        zs = [p[2] for p in lay.top_face]
        assert len(set(round(z, 6) for z in zs)) > 1
        # higher x (downstream in longitudinal grade direction) is higher
        by_x = sorted(lay.top_face, key=lambda p: p[0])
        assert by_x[-1][2] > by_x[0][2]

    def test_layout_rejects_unknown_pad(self):
        with pytest.raises(KeyError):
            layout_load_plate("B99")
