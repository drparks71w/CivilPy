#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Spot-checks of the Ohio DOT prestressed box beam construction details
against PSBD-1-25."""

import pytest

from civilpy.structural.odot import (
    ANCHOR_DOWEL,
    BEARING_DESIGN_DATA,
    BOX_BEAM_DEPTHS,
    DESIGN_DATA_SHEET,
    DESIGN_SPEC,
    SHEAR_KEY,
    TIE_ROD,
    bearing_pad,
    diaphragm_count,
    diaphragm_end_offset,
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
