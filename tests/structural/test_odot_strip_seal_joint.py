#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT EXJ-4-87 strip seal expansion joint catalog
(rev. 01-19-2024)."""

import math

import pytest

from civilpy.structural.odot import strip_seal_joint as ssj
from civilpy.structural.odot.strip_seal_joint import (
    StripSealJointInput,
    layout_strip_seal_joint,
    support_angle_lengths_in,
)


def test_provenance():
    assert ssj.SCD == "EXJ-4-87"
    assert ssj.REVISION == "01-19-2024"
    assert "EXJ-4-87" in ssj.__doc__


def test_hardware_constants():
    assert ssj.PLATE_MAX_SPACING_FT == 1.5
    assert ssj.JOINT_GAP_60F_IN == 3.0
    assert ssj.MIN_SUPPORT_ANGLE_LENGTH_FT == 2.5


def test_support_angle_formula_zero_skew():
    a1, a2, a3, a4 = support_angle_lengths_in(12.0, 0.0)
    assert a1 == pytest.approx(12.0 - 2.0 * 1.0 - 0.0)
    assert a2 == pytest.approx(1.0 + 0.5 * 12.0)
    assert a3 == pytest.approx(1.0 + 12.0 + 0.0 + 1.0)
    assert a4 == pytest.approx(a3 - a2)


def test_support_angle_formula_with_skew():
    theta = math.radians(30.0)
    cos_t, tan_t = math.cos(theta), math.tan(theta)
    a1, a2, a3, a4 = support_angle_lengths_in(12.0, 30.0)
    assert a1 == pytest.approx(12.0 / cos_t - 2.0 / cos_t - 4.0 * tan_t)
    assert a2 == pytest.approx(1.0 + 0.5 * 12.0 / cos_t)
    assert a3 == pytest.approx(1.0 + 12.0 / cos_t + 4.0 * tan_t + 1.0)
    assert a4 == pytest.approx(a3 - a2)


def test_layout_guards():
    with pytest.raises(ValueError, match="width_ft"):
        layout_strip_seal_joint(
            StripSealJointInput(width_ft=0.0, skew_deg=0.0,
                                stringer_stations_ft=(0.0, 5.0)))
    with pytest.raises(ValueError, match="stringer_stations_ft"):
        layout_strip_seal_joint(
            StripSealJointInput(width_ft=30.0, skew_deg=0.0,
                                stringer_stations_ft=()))


def test_layout_square_joint():
    inp = StripSealJointInput(width_ft=30.0, skew_deg=0.0,
                              stringer_stations_ft=(0.0, 10.0, 20.0, 30.0))
    lay = layout_strip_seal_joint(inp)
    assert lay.joint_line == ((0.0, 0.0, 0.0), (0.0, 30.0, 0.0))
    assert len(lay.support_angles) == 4
    assert lay.support_angles[0].station_ft == 0.0


def test_layout_skewed_shears_joint_line():
    inp = StripSealJointInput(width_ft=30.0, skew_deg=15.0,
                              stringer_stations_ft=(0.0, 15.0))
    lay = layout_strip_seal_joint(inp)
    tan15 = math.tan(math.radians(15.0))
    assert lay.joint_line[1][0] == pytest.approx(30.0 * tan15)


def test_layout_support_angle_matches_formula():
    inp = StripSealJointInput(width_ft=30.0, skew_deg=20.0,
                              stringer_stations_ft=(5.0,),
                              top_flange_width_in=14.0)
    lay = layout_strip_seal_joint(inp)
    run = lay.support_angles[0]
    a1, a2, a3, a4 = support_angle_lengths_in(14.0, 20.0)
    assert run.a1_in == pytest.approx(a1)
    length = run.points[1][0] - run.points[0][0]
    assert length == pytest.approx(a1 / 12.0)
