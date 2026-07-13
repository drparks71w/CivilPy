#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Spot-checks of the ODOT BP-5.1 concrete curb & combined curb-and-gutter
catalog."""

import pytest

from civilpy.structural.odot import concrete_curb as cc
from civilpy.structural.odot.concrete_curb import (
    CURB_TYPES,
    DEFAULT_GUTTER_PLATE_T_IN,
    curb_height_in,
    curb_profile_in,
    curb_type,
)


def test_provenance():
    assert cc.SCD == "BP-5.1"
    assert cc.REVISION == "01-16-2026"


def test_all_sheet_labels_present():
    expected = {
        "Type 1", "Type 2", "Type 2-A", "Type 2-B", "Type 3", "Type 3-A",
        "Type 3-B", "Type 4", "Type 4-A", "Type 4-B", "Type 4-C", "Type 6",
        "Type 7", "Type 8", "Type 9", "Type 10", "Type 10-A", "Type 10-B",
        "Type 11",
    }
    assert set(CURB_TYPES) == expected


def test_lookup_guards_unknown_label():
    with pytest.raises(ValueError, match="Type 1"):
        curb_type("Type 99")


def test_consolidated_substrate_variants_share_one_profile():
    for a, b in (("Type 2", "Type 2-A"), ("Type 2-A", "Type 2-B"),
                 ("Type 3", "Type 3-A"), ("Type 4", "Type 4-A")):
        assert curb_type(a) is curb_type(b)


def test_type1_asphalt_wedge():
    c = curb_type("Type 1")
    assert c.height == 6.0
    assert c.base_width == 9.0
    assert c.top_width == 4.0


def test_type2_curb_and_gutter_dims():
    c = curb_type("Type 2")
    assert c.height == 6.0
    assert c.top_width == 5.0
    assert c.toe_radius == 3.0


def test_variable_height_types_default_to_gutter_plate_t():
    for label in ("Type 9", "Type 10", "Type 11"):
        c = curb_type(label)
        assert c.height is None
        assert curb_height_in(label) == DEFAULT_GUTTER_PLATE_T_IN
        assert curb_height_in(label, gutter_plate_t_in=12.0) == 12.0


def test_fixed_height_types_ignore_gutter_plate_t():
    assert curb_height_in("Type 2", gutter_plate_t_in=99.0) == 6.0


def test_profile_is_a_closed_trapezoid():
    prof = curb_profile_in("Type 2")
    assert prof[0] == (0.0, 0.0)
    assert prof[1] == (6.0, 0.0)
    assert prof[2] == (5.0, 6.0)
    assert prof[3] == (0.0, 6.0)


def test_profile_uses_gutter_plate_t_for_variable_height():
    prof = curb_profile_in("Type 10", gutter_plate_t_in=12.0)
    zs = [z for _, z in prof]
    assert max(zs) == 12.0
