#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Spot-checks of the bonus ODOT tables: structural steel rockers/bolsters
(RB-1-55) and cast-in-place circular headwalls (HW-2.1)."""

import pytest

from civilpy.structural.odot import (
    HEADWALLS_BY_DIAMETER,
    HEADWALLS_CIRCULAR,
    MAX_MOVEMENT,
    ROCKER_BOLSTERS,
    headwall_for_diameter,
    rocker_bolster,
    smallest_for_load,
)
from civilpy.structural.odot.rocker_bolster import (
    layout_rocker_bolster,
    top_bearing_plate_radius_in,
    top_bearing_web_radius_in,
)


class TestRockerBolster:
    """Rockers and bolsters (RB-1-55)."""

    def test_capacities_present(self):
        assert set(ROCKER_BOLSTERS) == {
            75, 100, 125, 150, 175, 200, 225, 250, 275, 300
        }

    def test_max_load_matches_designation(self):
        # The number in B-xxx / R-xxx is the capacity in kips.
        for cap, rb in ROCKER_BOLSTERS.items():
            assert rb.max_load_lb == cap * 1000.0

    def test_r75_has_no_bolster(self):
        rb = rocker_bolster(75)
        assert rb.bolster_no == ""
        assert rb.weight_bolster_lb is None
        assert rb.weight_rocker_lb == 205.0

    def test_b150_dimensions(self):
        rb = rocker_bolster(150)
        assert rb.bolster_no == "B-150"
        assert rb.rocker_no == "R-150"
        assert rb.dims["B"] == 12.0
        assert rb.dims["H"] == 13.375   # 13-3/8 in overall height
        assert rb.dims["K"] == 11.5
        assert rb.dims["T"] == 1.75
        assert rb.weight_bolster_lb == 360.0
        assert rb.weight_rocker_lb == 400.0

    def test_b300_largest(self):
        rb = rocker_bolster(300)
        assert rb.dims["H"] == 19.125
        assert rb.dims["M"] == 25.0
        assert rb.weight_rocker_lb == 1050.0
        assert rb.max_load_lb == 300_000.0

    def test_height_increases_with_capacity(self):
        heights = [ROCKER_BOLSTERS[c].dims["H"] for c in sorted(ROCKER_BOLSTERS)]
        assert heights == sorted(heights)

    def test_smallest_for_load(self):
        assert smallest_for_load(120_000).capacity_kips == 125
        assert smallest_for_load(125_000).capacity_kips == 125  # exact match
        assert smallest_for_load(126_000).capacity_kips == 150

    def test_smallest_for_load_overflow(self):
        with pytest.raises(ValueError):
            smallest_for_load(400_000)

    def test_movement_limit(self):
        assert MAX_MOVEMENT == 2.0

    def test_top_bearing_detail_formulas(self):
        assert top_bearing_web_radius_in(3.0) == pytest.approx(1.5 + 1 / 16.0)
        assert top_bearing_plate_radius_in(3.0) == pytest.approx(1.5 + 3 / 32.0)

    def test_layout_base_plate_matches_dims(self):
        rb = rocker_bolster(150)
        lay = layout_rocker_bolster(rb)
        assert lay.base_outline[0] == (-6.0, -11.0, 0.0)
        assert lay.base_outline[2] == (6.0, 11.0, 0.0)
        assert lay.base_thickness_in == rb.dims["T"]

    def test_layout_bolster_top_narrower_than_base(self):
        rb = rocker_bolster(150)
        lay = layout_rocker_bolster(rb)
        base_width = lay.base_outline[1][0] - lay.base_outline[0][0]
        top_width = lay.bolster_top[1][0] - lay.bolster_top[0][0]
        assert top_width < base_width
        assert top_width == pytest.approx(rb.dims["A"])

    def test_layout_rocker_radius_from_a(self):
        rb = rocker_bolster(150)
        lay = layout_rocker_bolster(rb)
        assert lay.rocker_top_radius_in == pytest.approx(
            top_bearing_plate_radius_in(rb.dims["A"]))

    def test_layout_r75_has_no_bolster_but_still_lays_out(self):
        rb = rocker_bolster(75)
        lay = layout_rocker_bolster(rb)
        assert "no bolster" in lay.notes[0]
        assert lay.rocker_height_in > 0


class TestHeadwall:
    """Cast-in-place circular headwalls (HW-2.1)."""

    def test_row_count(self):
        assert len(HEADWALLS_CIRCULAR) == 46

    def test_smallest_12in(self):
        h = headwall_for_diameter(12)
        assert h.width == 24.0      # 2 ft-0 in
        assert h.height == 36.0     # 3 ft-0 in
        assert h.thickness == 12.0
        assert h.concrete_cy == pytest.approx(0.21)

    def test_36in(self):
        h = headwall_for_diameter(36)
        assert h.width == 72.0      # 6 ft-0 in
        assert h.height == 48.0     # 4 ft-0 in
        assert h.concrete_cy == pytest.approx(0.76)

    def test_largest_252in(self):
        h = headwall_for_diameter(252)
        assert h.width == 544.0     # 45 ft-4 in
        assert h.height == 162.0    # 13 ft-6 in
        assert h.thickness == 54.0
        assert h.concrete_cy == pytest.approx(47.44)

    def test_special_note_row(self):
        # D = 126 in falls between end treatments A and B.
        assert "between" in headwall_for_diameter(126).note.lower()

    def test_dimensions_monotonic(self):
        widths = [h.width for h in HEADWALLS_CIRCULAR]
        heights = [h.height for h in HEADWALLS_CIRCULAR]
        assert widths == sorted(widths)
        assert heights == sorted(heights)

    def test_lookup_by_diameter_map(self):
        assert HEADWALLS_BY_DIAMETER[60].width == 126.0  # 10 ft-6 in

    def test_unknown_diameter_raises(self):
        with pytest.raises(KeyError):
            headwall_for_diameter(13)
