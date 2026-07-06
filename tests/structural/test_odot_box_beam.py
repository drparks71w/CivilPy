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
    BOX_BEAM_DEPTHS,
    BOX_SECTION_PROPERTIES,
    BOX_WALL_THICKNESS_IN,
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
        assert s.area == pytest.approx(713.8)
        assert s.i == pytest.approx(66222)
        assert s.yb == pytest.approx(13.39)
        assert s.zt == pytest.approx(4866)
        assert s.zb == pytest.approx(4945)

    def test_cb27_48_composite(self):
        s = box_section_properties(27)
        assert s.ic == pytest.approx(109704)
        assert s.ybc == pytest.approx(17.13)
        assert s.ztc == pytest.approx(11119)
        assert s.zbc == pytest.approx(6403)

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
        # void width = 48 - 2 x 5.5 = 37 in; void height = D - 2 x 5.5
        for d in BOX_BEAM_DEPTHS:
            w, h = box_void_dimensions(d)
            assert w == pytest.approx(BOX_WIDTH_IN - 2 * BOX_WALL_THICKNESS_IN)
            assert h == pytest.approx(d - 2 * BOX_WALL_THICKNESS_IN)

    def test_void_dimensions_spot_values(self):
        assert box_void_dimensions(27) == pytest.approx((37.0, 16.0))
        assert box_void_dimensions(17) == pytest.approx((37.0, 6.0))
        assert box_void_dimensions(42) == pytest.approx((37.0, 31.0))


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
