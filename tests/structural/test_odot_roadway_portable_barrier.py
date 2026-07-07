#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Spot-checks of the ODOT roadway portable concrete barrier catalog
(RM-4.1, RM-4.2)."""

import pytest

rhino3dm = pytest.importorskip("rhino3dm")

from civilpy.structural.odot.bridge_railing import BridgeRailing
from civilpy.structural.odot.roadway_portable_barrier import (
    ROADWAY_PORTABLE_BARRIERS,
    TRANSITION_50_TO_32,
    roadway_portable_barrier,
)
from civilpy.structural.rhino_barrier import barrier_profile, shape_family


def test_designation_keys_match():
    for key, b in ROADWAY_PORTABLE_BARRIERS.items():
        assert key == b.designation


def test_all_entries_are_bridge_railing_compatible():
    assert all(isinstance(b, BridgeRailing) for b in ROADWAY_PORTABLE_BARRIERS.values())


def test_lookup_guards_unknown_name():
    with pytest.raises(ValueError, match="RM Portable"):
        roadway_portable_barrier("does-not-exist")


def test_shape_family_routes_as_portable():
    # "portable" appears in the catalog `name`, so shape_family must
    # classify these as the freestanding symmetric F-shape family (not
    # "new jersey", which would draw a one-sided asymmetric section).
    for b in ROADWAY_PORTABLE_BARRIERS.values():
        assert shape_family(b) == "portable"


class TestRM42_32in:
    def test_dimensions(self):
        b = roadway_portable_barrier("RM Portable (32 in, pin & loop)")
        assert b.scd == "RM-4.2"
        assert b.height == 32.0
        assert b.base_width == 24.0
        assert b.segment_length_ft == (10.0, 12.0, 20.0)

    def test_profile_is_symmetric_f_shape(self):
        b = roadway_portable_barrier("RM Portable (32 in, pin & loop)")
        prof = barrier_profile(b, b.height / 12.0, side=0)
        offs = [o for o, _ in prof]
        assert min(offs) == pytest.approx(-max(offs))
        assert max(offs) == pytest.approx(1.0)  # 24 in base, half = 1 ft


class TestRM41_50in:
    def test_dimensions_and_test_level(self):
        b = roadway_portable_barrier("RM Portable (50 in, hinge bar)")
        assert b.scd == "RM-4.1"
        assert b.height == 50.0
        assert b.top_width == 12.0
        assert b.test_level == "TL-3"
        assert b.segment_length_ft == (12.0, 14.0)

    def test_not_for_bridge_deck_edges_documented(self):
        b = roadway_portable_barrier("RM Portable (50 in, hinge bar)")
        assert "dropoff" in b.notes.lower()


def test_transition_section_ties_50_to_32():
    t = TRANSITION_50_TO_32
    assert t.height_from_in == 50.0
    assert t.height_to_in == 32.0
    assert t.length_ft == 6.0
