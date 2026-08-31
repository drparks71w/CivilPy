#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.
"""A built-up member as the pieces a shop made, not the section a designer
sized.  The distinction is the whole difference between LOD 300 and 400."""
import math

import pytest

from civilpy.structural import builtup
from civilpy.structural.laced_member import (
    LacedMember, LacingSpec, Piece, TiePlate, _angle_label, _frac,
    angle_designation,
)

SPEC = "2P24x3/8 4L4x4x3/8"          # span 3 upper chord, sheet L2
LEN = 23.9583                        # 23'-11 1/2"


def chord():
    """U11-U12 of span 3, exactly as the L2 shop bill lists it."""
    return LacedMember(
        spec=SPEC, length_ft=LEN,
        lacing=LacingSpec(2.5, 0.25, double=True, inclination_deg=45.0,
                          source="sheet L2 member bill: D.L. 2-1/2 x 1/4"),
        tie_plates=(TiePlate(21.0, 0.375, 3.8333, "top", 0.0, "L2 bill"),),
        source="Full Plan Set p604 sheet L2")


# --------------------------------------------------------------------------- #
# catalogue identity
# --------------------------------------------------------------------------- #
def test_angles_get_a_catalogue_designation_and_area():
    des, area, edition = angle_designation(4, 4, 0.375)
    assert des.upper() == "L4X4X3/8"
    assert area == pytest.approx(2.86)
    assert edition
    des6, area6, _e = angle_designation(6, 4, 0.5)
    assert des6.upper() == "L6X4X1/2"
    assert area6 == pytest.approx(4.75)


def test_the_sharp_cornered_decomposition_already_matches_the_catalogue_area():
    """Worth pinning: the fillet and the toe radii very nearly cancel, so the
    idealised two-rectangle angle is not an approximation of the area -- only
    of the shape.  If this ever drifts, the member weights drift with it."""
    for legs in ((4, 4, 0.5), (4, 4, 0.375), (6, 6, 0.375), (6, 4, 0.5)):
        a, b, t = legs
        _des, cat_area, _e = angle_designation(a, b, t)
        horiz, vert = max(a, b), min(a, b)
        modelled = horiz * t + t * (vert - t)
        assert modelled == pytest.approx(cat_area, rel=0.02), legs


def test_fraction_labels_read_like_the_sheets():
    assert _frac(0.375) == "3/8"
    assert _frac(0.4375) == "7/16"
    assert _frac(2.5) == "2-1/2"
    assert _frac(24) == "24"
    assert _angle_label(4, 4, 0.375) == "L4X4X3/8"


# --------------------------------------------------------------------------- #
# the pieces
# --------------------------------------------------------------------------- #
def test_the_bare_pieces_are_the_builtup_decomposition():
    m = chord()
    bare = m.bare_pieces()
    rects, _meta = builtup.rects(SPEC)
    assert len(bare) == len(rects) == 10
    kinds = {p.kind for p in bare}
    assert kinds == {"web plate", "angle"}
    assert sum(1 for p in bare if p.kind == "angle") == 8
    assert all(p.length_ft == LEN for p in bare)
    assert all(p.designation.upper() == "L4X4X3/8"
               for p in bare if p.kind == "angle")


def test_lacing_bars_are_real_pieces_at_the_right_length_and_pitch():
    m = chord()
    bars = m.lacing_pieces()
    gauge = m.lacing_gauge_in()
    assert gauge == pytest.approx(18.0 - 2 * 4.0)      # web spacing less a leg each side
    # a 45 degree bar spans the gauge diagonally
    want_len = (gauge / math.sin(math.radians(45.0))) / 12.0
    assert all(p.length_ft == pytest.approx(want_len) for p in bars)
    assert {p.face for p in bars} == {"top", "bottom"}
    # double lacing: both directions at every station
    assert {round(p.angle_deg) for p in bars} == {45, -45}
    stations = sorted({round(p.along_ft, 9) for p in bars})
    advance = gauge / math.tan(math.radians(45.0)) / 12.0
    assert stations[1] - stations[0] == pytest.approx(advance)
    assert len(bars) == 2 * 2 * len(stations)          # 2 faces x 2 directions


def test_a_covered_face_carries_no_lacing():
    """Cover plates close a face; lacing goes on the faces that are open."""
    covered = LacedMember("4P24x1/2 2P16x7/16 4L4x4x1/2", LEN,
                          lacing=LacingSpec(2.5, 0.25, source="test"))
    faces = {p.face for p in covered.lacing_pieces()}
    assert faces == {"bottom"}


def test_no_lacing_spec_means_no_lacing_drawn():
    plain = LacedMember(SPEC, LEN)
    assert plain.lacing_pieces() == []
    assert plain.weight_lb() == pytest.approx(plain.bare_weight_lb())
    assert plain.buildup_ratio() == pytest.approx(1.0)


def test_tie_plates_sit_on_a_face_at_their_station():
    m = chord()
    ties = m.tie_pieces()
    assert len(ties) == 1
    t = ties[0]
    assert t.kind == "tie plate" and t.face == "top"
    assert t.b_in == 21.0 and t.h_in == 0.375
    assert t.z_in == pytest.approx(24.0 / 2)           # on the face, not the axis
    assert t.length_ft == pytest.approx(3.8333)


# --------------------------------------------------------------------------- #
# weight
# --------------------------------------------------------------------------- #
def test_the_fabricated_member_weighs_more_than_its_bare_section():
    """The point of the module.  Drawing only the bare section understates a
    riveted member; the 2012 CUY-10-1613 rating carries a per-member
    multiplier of 1.06-2.87 covering lacing, tie plates, gussets and rivets,
    and what is *inside* the member is a real part of that."""
    m = chord()
    assert m.weight_lb() > m.bare_weight_lb()
    assert 1.15 < m.buildup_ratio() < 1.60
    lac = sum(p.weight_lb for p in m.lacing_pieces())
    assert 150 < lac < 500                              # a few hundred pounds


def test_weight_is_the_sum_of_the_pieces():
    m = chord()
    assert m.weight_lb() == pytest.approx(sum(p.weight_lb for p in m.pieces()))
    p = m.bare_pieces()[0]
    assert p.weight_lb == pytest.approx(
        p.b_in * p.h_in / 144.0 * 490.0 * p.length_ft)


def test_summary_groups_by_piece_kind():
    s = chord().summary()
    assert set(s["pieces"]) == {"web plate", "angle", "lacing bar", "tie plate"}
    assert s["pieces"]["angle"]["count"] == 8
    assert s["pieces"]["lacing bar"]["count"] == len(chord().lacing_pieces())
    assert s["fabricated_lb"] > s["bare_lb"]
    assert s["spec"] == SPEC


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #
def test_every_piece_records_where_its_dimension_came_from():
    """A value read off a 1930 sheet must be distinguishable from one that
    was not; the model should never pass a default off as as-built."""
    m = chord()
    for p in m.pieces():
        assert p.source, p.kind
    assert "L2" in [p.source for p in m.lacing_pieces()][0]
    assert "L2" in m.tie_pieces()[0].source


def test_lacing_label_says_single_or_double():
    assert "double" in LacingSpec(2.5, 0.25, double=True).label
    assert "single" in LacingSpec(2.5, 0.25, double=False).label
    assert "2-1/2" in LacingSpec(2.5, 0.25).label
