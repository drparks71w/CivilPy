#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the ODOT PCB-91 portable concrete barrier geometry
(rev. 07-17-2020)."""

import pytest

from civilpy.structural.odot import portable_barrier as pb
from civilpy.structural.odot.bridge_railing import BRIDGE_RAILINGS


def test_section_constants_match_sheet():
    assert pb.HEIGHT_IN == 32.0
    assert pb.BASE_WIDTH_IN == 24.0
    assert pb.TOP_WIDTH_IN == 6.0
    # view A-A: 7 + 2 + 6 + 2 + 7 across, 19 + 10 + 3 up
    assert 2 * (pb.LOWER_FACE_RUN_IN + pb.UPPER_FACE_RUN_IN) \
        + pb.TOP_WIDTH_IN == pb.BASE_WIDTH_IN
    assert pb.TOE_HEIGHT_IN + pb.LOWER_FACE_RISE_IN \
        + pb.UPPER_FACE_RISE_IN == pb.HEIGHT_IN
    # section B-B base: 5" | 1'-2" | 5"
    assert pb.SLOT_WIDTH_IN == 14.0
    assert pb.BASE_WIDTH_IN - pb.SLOT_WIDTH_IN == 10.0


def test_profile_closed_and_symmetric():
    pts = pb.profile_points_in()
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert max(ys) == pb.HEIGHT_IN
    assert min(ys) == 0.0
    assert max(xs) == pb.BASE_WIDTH_IN / 2.0
    assert min(xs) == -pb.BASE_WIDTH_IN / 2.0
    # mirror symmetry about x = 0
    mirrored = sorted((round(-x, 6), round(y, 6)) for x, y in pts)
    assert mirrored == sorted((round(x, 6), round(y, 6)) for x, y in pts)
    # slope break at (5, 13) per the 7 in / 10 in dims
    assert (5.0, 13.0) in pts
    # chamfered top: no corner at full top half-width and full height
    assert (3.0, 32.0) not in pts
    assert (3.0, 31.25) in pts and (2.25, 32.0) in pts


def test_profile_unchamfered():
    pts = pb.profile_points_in(chamfered=False)
    assert (3.0, 32.0) in pts and (-3.0, 32.0) in pts


def test_anchor_hole_stations():
    # 1'-0" from each end @ 2'-0" c/c: 5 holes on 10 ft, 6 on 12 ft
    assert pb.anchor_hole_stations_ft(10.0) == (1.0, 3.0, 5.0, 7.0, 9.0)
    assert pb.anchor_hole_stations_ft(12.0) == (
        1.0, 3.0, 5.0, 7.0, 9.0, 11.0)
    with pytest.raises(ValueError, match="10"):
        pb.anchor_hole_stations_ft(8.0)


def test_barrier_run_layout():
    run = pb.barrier_run(3, 12.0, joint_gap_in=1.75)
    assert len(run) == 3
    assert run[0].start_ft == 0.0
    assert run[0].length_ft == 12.0
    gap_ft = 1.75 / 12.0
    assert run[1].start_ft == pytest.approx(12.0 + gap_ft)
    assert pb.run_length_ft(run) == pytest.approx(36.0 + 2 * gap_ft)


def test_barrier_run_guards():
    with pytest.raises(ValueError, match="at least one"):
        pb.barrier_run(0)
    with pytest.raises(ValueError, match="10"):
        pb.barrier_run(2, 11.0)
    with pytest.raises(ValueError, match="1.75"):
        pb.barrier_run(2, 10.0, joint_gap_in=2.0)
    # closed and fully-open joints both allowed
    pb.barrier_run(2, 10.0, joint_gap_in=pb.CLOSED_JOINT_GAP_IN)
    pb.barrier_run(2, 10.0, joint_gap_in=pb.OPEN_JOINT_MAX_GAP_IN)


def test_joint_and_anchor_hardware():
    assert pb.CLOSED_JOINT_GAP_IN == 0.25
    assert pb.OPEN_JOINT_MAX_GAP_IN == 1.75
    assert pb.HINGE_BAR_DIAMETER_IN == 0.75
    assert pb.JOINT_BOLT_DIAMETER_IN == 1.25
    assert pb.ANCHOR_BOLT_DIAMETER_IN == 1.0
    assert pb.ANCHOR_HOLE_DIAMETER_IN == 1.25
    assert pb.ANCHOR_MIN_EMBED_IN == 6.5
    assert pb.CONCRETE_MIN_FC_PSI == 4_000


def test_consistent_with_bridge_railing_catalog():
    """The geometry module must agree with the existing catalog entries."""
    pcbs = [r for r in BRIDGE_RAILINGS.values() if r.scd == "PCB-91"]
    assert len(pcbs) == 2
    for r in pcbs:
        assert r.height == pb.HEIGHT_IN
        assert r.base_width == pb.BASE_WIDTH_IN
        assert tuple(r.segment_length_ft) == pb.SEGMENT_LENGTHS_FT
        assert r.f_c * 1000 == pb.CONCRETE_MIN_FC_PSI
    levels = {r.test_level for r in pcbs}
    assert levels == {"TL-3", "TL-4"}


def test_provenance():
    assert pb.SCD == "PCB-91"
    assert pb.REVISION == "07-17-2020"
    assert "PCB-91" in pb.__doc__
