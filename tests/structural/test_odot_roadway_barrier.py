#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Spot-checks of the ODOT roadway single-slope barrier catalog (RM-4.3,
RM-4.5, RM-4.8, RM-4.9)."""

import pytest

from civilpy.structural.odot.roadway_barrier import (
    ROADWAY_BARRIERS,
    RoadwayBarrier,
    RoadwayBarrierInput,
    layout_roadway_barrier,
    roadway_barrier,
)


def test_designation_keys_match():
    for key, b in ROADWAY_BARRIERS.items():
        assert key == b.designation


def test_all_entries_are_roadway_barriers():
    assert all(isinstance(b, RoadwayBarrier) for b in ROADWAY_BARRIERS.values())


def test_lookup_guards_unknown_name():
    with pytest.raises(ValueError, match="Type B"):
        roadway_barrier("Type Z")


def test_shape_contains_single_slope():
    # so civilpy.structural.rhino_barrier.shape_family routes these through
    # the "single slope" profile family.
    for b in ROADWAY_BARRIERS.values():
        assert "single slope" in b.shape


class TestTypeB_B1:
    def test_type_b(self):
        b = roadway_barrier("Type B")
        assert b.scd == "RM-4.3"
        assert b.height == 42.0
        assert b.top_width == 12.0
        assert b.base_width == 28.0
        assert b.joint_spacing_ft == 20.0

    def test_type_b1_taller(self):
        b1 = roadway_barrier("Type B1")
        assert b1.height == 57.0
        assert b1.base_width == 33.75

    def test_slope_is_consistent_with_dimensions(self):
        # half-offset = height / slope_h_to_v (5.25 : 1 rise:run)
        for name in ("Type B", "Type B1", "Type D", "Type N"):
            b = roadway_barrier(name)
            half_offset = (b.base_width - b.top_width) / 2.0
            assert half_offset == pytest.approx(b.height / b.slope_h_to_v, abs=0.05)


class TestTypeC_C1:
    def test_variable_height_siblings_share_b_b1_base_body(self):
        c, b = roadway_barrier("Type C"), roadway_barrier("Type B")
        assert c.height == b.height
        assert c.base_width == b.base_width
        assert "variable" in c.notes.lower() or "Variable" in c.notes

        c1, b1 = roadway_barrier("Type C1"), roadway_barrier("Type B1")
        assert c1.height == b1.height
        assert c1.base_width == b1.base_width


class TestTypeD:
    def test_founded_on_compacted_soil(self):
        d = roadway_barrier("Type D")
        assert d.scd == "RM-4.5"
        assert d.foundation == "compacted soil"
        assert d.height == 42.0
        assert d.base_width == 28.0  # same 5.25:1 body as Type B


class TestTypeN:
    def test_general_design_tallest(self):
        n = roadway_barrier("Type N")
        assert n.scd == "RM-4.8"
        assert n.height == 81.0
        assert n.base_width == pytest.approx(42.875)
        assert n.foundation == "leveling pad"
        assert n.joint_spacing_ft == 10.0


class TestTypeE:
    def test_moment_slab_no_dimensioned_envelope(self):
        e = roadway_barrier("Type E")
        assert e.scd == "RM-4.9"
        assert e.foundation == "moment slab"
        assert e.height == 36.0
        assert e.top_width is None
        assert e.base_width is None

    def test_layout_refuses_undimensioned_profile(self):
        with pytest.raises(ValueError, match="does not have a dimensioned"):
            layout_roadway_barrier(RoadwayBarrierInput(designation="Type E", length_ft=50.0))


class TestLayout:
    def test_layout_profile_is_symmetric_trapezoid(self):
        lay = layout_roadway_barrier(RoadwayBarrierInput(designation="Type B", length_ft=100.0))
        offsets = [o for o, _ in lay.profile]
        assert min(offsets) == pytest.approx(-14.0)
        assert max(offsets) == pytest.approx(14.0)
        zs = [z for _, z in lay.profile]
        assert max(zs) == pytest.approx(42.0)
        assert lay.length_ft == 100.0

    def test_layout_guards_bad_length(self):
        with pytest.raises(ValueError, match="length_ft"):
            layout_roadway_barrier(RoadwayBarrierInput(designation="Type B", length_ft=0.0))
