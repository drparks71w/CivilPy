#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT AS-2-15 sleeper slab / installation catalog
(rev. 01-20-2023)."""

import math

import pytest

from civilpy.structural.odot import sleeper_slab as ss
from civilpy.structural.odot.sleeper_slab import (
    INSTALLATION_INDEX,
    SleeperSlabInput,
    installations,
    layout_sleeper_slab,
    ss501_length_ft,
    ss502_count,
    ss502_length_ft,
)


def test_sleeper_constants_match_sheet():
    assert ss.SLEEPER_WIDTH_FT == 8.0
    assert ss.SLEEPER_THICKNESS_IN == 9.0
    # 8 - SS501 @ 1'-0" = 7'-0" with 6 in edges spans the 8 ft width
    assert (ss.SS501_COUNT - 1) * ss.SS501_SPACING_IN / 12.0 == 7.0
    assert 7.0 + 2 * ss.SS501_EDGE_IN / 12.0 == ss.SLEEPER_WIDTH_FT
    assert ss.UNDERDRAIN_PIPE_DIA_IN == 6.0
    assert ss.UNDERDRAIN_TRENCH_WIDTH_IN == 15.0
    assert ss.UNDERDRAIN_TRENCH_DEPTH_IN == 10.0
    assert ss.PMA_JOINT_WIDTH_IN == 20.0
    assert ss.PMA_JOINT_THICKNESS_IN == 3.0
    assert ss.FLEXIBLE_PAVEMENT_LENGTH_FT == 25.0
    assert ss.CONCRETE_STRENGTH_KSI == 4.5


def test_bar_length_formulas():
    # A = (W - 0.5)/cos(theta), B = 7.5/cos(theta)
    assert ss501_length_ft(24.0) == pytest.approx(23.5)
    assert ss502_length_ft() == pytest.approx(7.5)
    sec30 = 1.0 / math.cos(math.radians(30.0))
    assert ss501_length_ft(24.0, 30.0) == pytest.approx(23.5 * sec30)
    assert ss502_length_ft(30.0) == pytest.approx(7.5 * sec30)


def test_ss502_count():
    assert ss502_count(24.0) == 25       # 23.5 spaces -> 24 + 1
    assert ss502_count(12.5) == 13       # exact 12 spaces
    with pytest.raises(ValueError):
        ss502_count(0.4)


def test_installation_index():
    types = {i.type for i in INSTALLATION_INDEX}
    assert types == {"A", "B", "C"}
    # Type B never has a sleeper slab; A and C always do
    for i in INSTALLATION_INDEX:
        assert i.has_sleeper_slab == (i.type != "B")
    assert len(installations("C")) == 4
    with pytest.raises(ValueError, match="'A', 'B', and 'C'"):
        installations("D")


def test_layout_guards():
    with pytest.raises(ValueError, match="Type B"):
        layout_sleeper_slab(SleeperSlabInput(24.0, installation="B"))
    with pytest.raises(ValueError, match="'A', 'B', and 'C'"):
        layout_sleeper_slab(SleeperSlabInput(24.0, installation="X"))
    with pytest.raises(ValueError, match="width"):
        layout_sleeper_slab(SleeperSlabInput(0.4))
    with pytest.raises(ValueError, match="skew"):
        layout_sleeper_slab(SleeperSlabInput(24.0, skew_deg=60.0))


def test_layout_geometry_square():
    lay = layout_sleeper_slab(SleeperSlabInput(24.0))
    assert lay.outline == ((-4.0, 0.0, 0.0), (-4.0, 24.0, 0.0),
                           (4.0, 24.0, 0.0), (4.0, 0.0, 0.0))
    assert lay.thickness_in == 9.0
    # underdrain pipe centered in the trench beyond the +u edge
    (x0, y0, z0), (x1, y1, z1) = lay.underdrain
    assert x0 == x1 == pytest.approx(4.0 + 15.0 / 24.0)
    assert z0 == z1 == pytest.approx(-(0.75 + 10.0 / 12.0 - 3.0 / 12.0))
    # PMA joint 20 in wide centered on the joint
    assert lay.pma_joint[0][0] == pytest.approx(-10.0 / 12.0)
    assert lay.pma_joint[3][0] == pytest.approx(10.0 / 12.0)
    # aggregate drain 2 ft wide below the slab
    assert lay.aggregate_drain[0] == (-1.0, 0.0, -0.75)
    assert lay.measured_length_ft == pytest.approx(24.0)


def test_layout_bars():
    W = 24.0
    lay = layout_sleeper_slab(SleeperSlabInput(W))
    s501 = [b for b in lay.bars if b.mark == "SS501"]
    s502 = [b for b in lay.bars if b.mark == "SS502"]
    assert len(s501) == 8
    assert len(s502) == ss502_count(W)
    # SS501 at u = -3.5 .. +3.5 on 1 ft centers
    us = sorted(b.points[0][0] for b in s501)
    assert us == pytest.approx([-3.5 + i for i in range(8)])
    # bottom cover 3 in: #5 centerline
    z = s501[0].points[0][2]
    assert z == pytest.approx(-(9.0 - 3.0 - 0.625 / 2.0) / 12.0)
    # SS502 tied above the SS501 layer, spanning 7.5 ft
    b = s502[0]
    assert b.points[0][2] > z
    assert b.points[1][0] - b.points[0][0] == pytest.approx(7.5)


def test_layout_skewed():
    lay = layout_sleeper_slab(SleeperSlabInput(24.0, skew_deg=30.0))
    tan30 = math.tan(math.radians(30.0))
    assert lay.outline[1][0] == pytest.approx(-4.0 + 24.0 * tan30)
    # sleeper measured along the skew
    assert lay.measured_length_ft == pytest.approx(
        24.0 / math.cos(math.radians(30.0)))
    # SS502 length shortens in plan to B*cos = 7.5 exactly longitudinally
    s502 = [b for b in lay.bars if b.mark == "SS502"][0]
    dx = s502.points[1][0] - s502.points[0][0]
    assert dx == pytest.approx(7.5)   # B/cos * cos... plan run stays 7.5
    # SS501 parallel to the skewed centerline
    s501 = [b for b in lay.bars if b.mark == "SS501"][0]
    (x0, y0, _), (x1, y1, _) = s501.points
    assert (x1 - x0) / (y1 - y0) == pytest.approx(tan30)


def test_provenance():
    assert ss.SCD == "AS-2-15"
    assert ss.REVISION == "01-20-2023"
    assert "AS-2-15" in ss.__doc__
