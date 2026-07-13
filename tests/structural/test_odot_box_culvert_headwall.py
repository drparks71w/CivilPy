#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT BCHW box culvert headwall/wingwall plan insert
(rev. 01-21-2022)."""

import math

import pytest

from civilpy.structural.odot import box_culvert_headwall as bchw
from civilpy.structural.odot.box_culvert_headwall import (
    WingwallInput,
    bend_shape,
    layout_wingwall,
)


def test_provenance():
    assert bchw.SCD == "BCHW"
    assert bchw.REVISION == "01-21-2022"
    assert "BCHW" in bchw.__doc__


def test_general_notes():
    assert bchw.LAP_SPLICE_FT[5] == pytest.approx(2 + 5 / 12.0)
    assert bchw.LAP_SPLICE_FT[6] == pytest.approx(2 + 11 / 12.0)
    assert bchw.PEJF_THICKNESS_IN == 1.0
    assert bchw.POROUS_BACKFILL_THICKNESS_IN == 18.0
    assert bchw.WEEPHOLE_DIA_IN == 4.0
    assert bchw.WEEPHOLE_MAX_SPACING_FT == 10.0
    assert bchw.CLEAR_COVER_IN == 3.0


def test_bend_shape_guards_unknown_type():
    with pytest.raises(ValueError, match="TYPE-1"):
        bend_shape("TYPE-9", A=1.0)


def test_bend_shape_guards_missing_legs():
    with pytest.raises(ValueError, match="missing"):
        bend_shape("TYPE-1", A=12.0)


def test_type_1_right_angle_hook():
    pts = bend_shape("TYPE-1", A=12.0, B=18.0)
    assert pts[0] == (0.0, 0.0)
    assert pts[-1] == (12.0, -18.0)
    # a right-angle bend: the middle point shares an axis with each end
    assert pts[1][0] == pts[0][0]
    assert pts[1][1] == pts[-1][1]


def test_type_5_symmetric_u():
    pts = bend_shape("TYPE-5", A=10.0, B=6.0)
    assert pts[0][1] == pts[-1][1] == 0.0
    assert pts[1][1] == pts[2][1] == -10.0
    assert pts[2][0] - pts[1][0] == pytest.approx(6.0)


def test_type_6_hat_total_length():
    pts = bend_shape("TYPE-6", A=3.0, B=2.0, C=5.0)
    total = pts[-1][0] - pts[0][0]
    assert total == pytest.approx(3 + 2 + 5 + 2 + 3)


def test_type_8_corner_bar_skew_dependent():
    flat = bend_shape("TYPE-8", A=12.0, B=18.0, skew_deg=0.0)
    skewed = bend_shape("TYPE-8", A=12.0, B=18.0, skew_deg=30.0)
    assert flat[-1] != skewed[-1]
    # hook extension: the far leg is longer than B alone
    far_len = math.hypot(flat[-1][0] - flat[1][0], flat[-1][1] - flat[1][1])
    assert far_len == pytest.approx(18.0 + 3.0)


def test_layout_guards_nonpositive_dims():
    base = dict(length_ft=10.0, skew_deg=0.0, wall_height_ft=8.0,
                foreslope_height_ft=4.0, cutoff_wall_height_ft=2.0,
                footing_width_ft=6.0, box_wall_thickness_in=12.0)
    layout_wingwall(WingwallInput(**base))  # sanity: valid input passes
    bad = dict(base, length_ft=0.0)
    with pytest.raises(ValueError, match="length_ft"):
        layout_wingwall(WingwallInput(**bad))


def test_layout_square_wingwall():
    inp = WingwallInput(length_ft=10.0, skew_deg=0.0, wall_height_ft=8.0,
                        foreslope_height_ft=4.0, cutoff_wall_height_ft=2.0,
                        footing_width_ft=6.0, box_wall_thickness_in=12.0)
    lay = layout_wingwall(inp)
    assert lay.wingwall_outline[0] == (0.0, 0.0, 0.0)
    assert lay.wingwall_outline[1] == (0.0, 0.0, 8.0)
    assert lay.wingwall_outline[2] == (0.0, 10.0, 4.0)
    # footing sits at -hcw, centered on the box wall at y=0
    assert lay.footing_outline[0] == (-3.0, 0.0, -2.0)
    assert lay.footing_outline[3] == (3.0, 0.0, -2.0)


def test_layout_skewed_wingwall_shears():
    inp = WingwallInput(length_ft=10.0, skew_deg=20.0, wall_height_ft=8.0,
                        foreslope_height_ft=4.0, cutoff_wall_height_ft=2.0,
                        footing_width_ft=6.0, box_wall_thickness_in=12.0)
    lay = layout_wingwall(inp)
    tan20 = math.tan(math.radians(20.0))
    # far end (y = L) is sheared by y*tan(skew) relative to the near end
    assert lay.wingwall_outline[2][0] == pytest.approx(10.0 * tan20)
    assert lay.footing_outline[1][0] == pytest.approx(-3.0 + 10.0 * tan20)
