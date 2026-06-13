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

"""Spot-checks of the ODOT box-beam standard designs and load ratings
against PSBDD-1-25."""

import pytest

from civilpy.structural.odot import (
    BOX_BEAM_DESIGNS,
    BOX_BEAM_RATINGS,
    BOX_DESIGNATIONS,
    RATING_VEHICLES,
    box_beam_design,
    box_beam_rating,
    designs_for_box,
)


class TestDesignTableIntegrity:
    def test_row_counts(self):
        # 35 composite + 28 non-composite spans (PSBDD-1-25 sheets 1 & 3).
        assert len(BOX_BEAM_DESIGNS) == 63
        comp = [d for d in BOX_BEAM_DESIGNS if d.beam_type == "composite"]
        nc = [d for d in BOX_BEAM_DESIGNS if d.beam_type == "non_composite"]
        assert len(comp) == 35
        assert len(nc) == 28

    def test_box_designations(self):
        assert BOX_DESIGNATIONS == (
            "CB17-48", "CB21-48", "CB27-48", "CB33-48", "CB42-48",
            "B17-48", "B21-48", "B27-48", "B33-48", "B42-48",
        )

    def test_strand_placement_sums_to_total(self):
        # The 2/4/6 in rows must account for every strand.
        for d in BOX_BEAM_DESIGNS:
            assert d.strands_2in + d.strands_4in + d.strands_6in == d.n_strands

    def test_bearing_types_known(self):
        assert {d.bearing_type for d in BOX_BEAM_DESIGNS} == {"B1", "B2"}

    def test_composite_has_composite_eccentricity(self):
        for d in BOX_BEAM_DESIGNS:
            if d.beam_type == "composite":
                assert d.e_composite is not None and d.e_composite > d.e_beam
            else:
                assert d.e_composite is None


class TestDesignValues:
    """Spot values read off PSBDD-1-25 sheets 1 & 3."""

    def test_cb17_48_span20(self):
        d = box_beam_design("CB17-48", 20)
        assert d.depth == 17 and d.width == 48
        assert d.e_beam == 5.78
        assert d.e_composite == 8.07
        assert d.n_strands == 12
        assert (d.strands_2in, d.strands_4in, d.strands_6in) == (8, 4, 0)
        assert d.camber_d0 == 0.125
        assert d.camber_d30 == 0.250
        assert d.bearing_type == "B1"

    def test_cb42_48_span95(self):
        d = box_beam_design("CB42-48", 95)
        assert d.n_strands == 36
        assert (d.strands_2in, d.strands_4in, d.strands_6in) == (16, 18, 2)
        assert d.e_composite == 22.33
        assert d.deflection == 1.000
        assert d.bearing_type == "B2"

    def test_b27_48_span65_non_composite(self):
        d = box_beam_design("B27-48", 65)
        assert d.beam_type == "non_composite"
        assert d.e_beam == 10.45
        assert d.e_composite is None
        assert d.n_strands == 30
        assert d.camber_d0 == 1.500

    def test_designs_for_box_sorted(self):
        spans = [d.span for d in designs_for_box("CB21-48")]
        assert spans == [30, 35, 40, 45, 50, 55, 60]

    def test_missing_design_raises(self):
        with pytest.raises(KeyError):
            box_beam_design("CB17-48", 100)


class TestLoadRating:
    """Spot values read off PSBDD-1-25 sheets 2 & 4."""

    def test_row_count(self):
        # 63 designs x 3 bridge widths.
        assert len(BOX_BEAM_RATINGS) == 189

    def test_vehicle_count(self):
        assert len(RATING_VEHICLES) == 16

    def test_operating_exceeds_inventory_everywhere(self):
        for r in BOX_BEAM_RATINGS:
            assert r.operating > r.inventory

    def test_cb17_48_span20_24ft(self):
        r = box_beam_rating("CB17-48", 20, 24)
        assert r.n_beams == 6
        assert r.inventory == 2.30
        assert r.operating == 2.98
        assert r.rating_factors["type3s2"] == 4.76
        assert r.rating_factors["s2f1"] == 5.57

    def test_b42_48_span90_32ft(self):
        r = box_beam_rating("B42-48", 90, 32)
        assert r.beam_type == "non_composite"
        assert r.n_beams == 8
        assert r.inventory == 1.64
        assert r.operating == 2.13
        assert r.rating_factors["type3s2"] == 2.98

    def test_widths_present_for_each_design(self):
        assert {r.width_ft for r in BOX_BEAM_RATINGS} == {24, 28, 32}

    def test_missing_rating_raises(self):
        with pytest.raises(KeyError):
            box_beam_rating("CB17-48", 20, 40)
