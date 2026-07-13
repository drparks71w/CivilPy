#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT EXJ-5-93 strip seal expansion joint (box beam)
catalog (rev. 01-19-2024)."""

import math

import pytest

from civilpy.structural.odot import strip_seal_joint_box_beam as bbj
from civilpy.structural.odot.strip_seal_joint_box_beam import (
    BoxBeamJointInput,
    joint_length_ft,
    layout_box_beam_joint,
    plate_spacing,
)


def test_provenance():
    assert bbj.SCD == "EXJ-5-93"
    assert bbj.REVISION == "01-19-2024"
    assert "EXJ-5-93" in bbj.__doc__


def test_plate_spacing_table():
    p36 = plate_spacing(36.0)
    assert (p36.dim_a_in, p36.dim_b_in, p36.dim_c_in) == (6.0, pytest.approx(12.25), 12.0)
    p48 = plate_spacing(48.0)
    assert (p48.dim_a_in, p48.dim_b_in, p48.dim_c_in) == (8.0, pytest.approx(16.25), 16.0)


def test_plate_spacing_guards_unknown_width():
    with pytest.raises(ValueError, match="36.*48"):
        plate_spacing(40.0)


def test_joint_length_formula():
    assert joint_length_ft(5, 48.0, 0.0) == pytest.approx(
        (4 * 0.5 + 5 * 48.0) / 12.0)
    cos20 = math.cos(math.radians(20.0))
    assert joint_length_ft(5, 48.0, 20.0) == pytest.approx(
        (4 * 0.5 + 5 * 48.0) / 12.0 / cos20)


def test_layout_guards():
    with pytest.raises(ValueError, match="n_beams"):
        layout_box_beam_joint(BoxBeamJointInput(n_beams=1, beam_width_in=48.0))
    with pytest.raises(ValueError, match="36.*48"):
        layout_box_beam_joint(BoxBeamJointInput(n_beams=5, beam_width_in=40.0))


def test_layout_square_joint():
    inp = BoxBeamJointInput(n_beams=5, beam_width_in=48.0, skew_deg=0.0)
    lay = layout_box_beam_joint(inp)
    assert lay.length_ft == pytest.approx(joint_length_ft(5, 48.0, 0.0))
    assert lay.joint_line == ((0.0, 0.0, 0.0), (0.0, lay.length_ft, 0.0))
    assert lay.beam_gap_stations_ft == (4.0, 8.0, 12.0, 16.0)


def test_layout_skewed_shears_joint_line():
    inp = BoxBeamJointInput(n_beams=5, beam_width_in=48.0, skew_deg=15.0)
    lay = layout_box_beam_joint(inp)
    tan15 = math.tan(math.radians(15.0))
    assert lay.joint_line[1][0] == pytest.approx(lay.length_ft * tan15)


def test_layout_spacing_matches_beam_width():
    inp = BoxBeamJointInput(n_beams=3, beam_width_in=36.0)
    lay = layout_box_beam_joint(inp)
    assert lay.spacing.beam_width_in == 36.0
