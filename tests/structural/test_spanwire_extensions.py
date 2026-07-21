#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Span-wire extensions: H builder, per-segment wire weights, load
elevations, and pole combinations.

Symmetric-H closed form: tails at 45 degrees off the crossbar axis give
tail tension = crossbar / sqrt(2) by ring equilibrium.
"""

import math

import pytest

from civilpy.structural.spanwire import (
    SegmentDef,
    SimpleSpan,
    SpanLoad,
    SpanWireSystem,
    combine_pole,
)


def symmetric_h(**kwargs):
    # crossbar along +y from R1(0,0) to R2(0,40); four 45-degree tails
    return SpanWireSystem.h(
        ring_positions=((0.0, 0.0), (0.0, 40.0)),
        tail_lengths=(20.0, 20.0, 20.0, 20.0),
        tail_bearings_deg=(225.0, 315.0, 135.0, 45.0),
        loads={"R1R2": [SpanLoad(20.0, 100.0)]},
        **kwargs,
    )


def test_h_builder_closed_form():
    system = symmetric_h()
    relations, rotation, warped = system.tension_relations()
    assert rotation == 0.0 and warped is None          # determinate shape
    assert relations["R1R2"] == 1.0                    # default reference
    for tail in ("P1R1", "P2R1", "P3R2", "P4R2"):
        assert relations[tail] == pytest.approx(math.sqrt(2) / 2, abs=1e-9)

    sol = system.solve(4.0)
    assert sol.sag_ft == pytest.approx(4.0, abs=1e-6)
    assert sol.balance_pole is None
    # symmetry: all four poles see the same stringing tension
    tensions = sol.pole_tensions()
    assert len(set(round(t, 6) for t in tensions.values())) == 1
    # global vertical balance
    pole_total = sum(
        s.start_reaction_lb for s in sol.segments if s.name.startswith("P"))
    assert pole_total == pytest.approx(100.0, abs=1e-6)


def test_h_ring_count_validation():
    with pytest.raises(ValueError, match="2 ring positions"):
        SpanWireSystem.h(((0, 0),), (1, 1, 1, 1), (0, 0, 0, 0))


def test_per_segment_wire_weights():
    system = SpanWireSystem.wye(
        (100.0, 100.0, 100.0), (90.0, 210.0, 330.0),
        wire_weight_plf=1.0,
        wire_weights={"P1R1": 2.5},
    )
    weights = {s.name: s.wire_weight_plf for s in system.segments}
    assert weights == {"P1R1": 2.5, "P2R1": 1.0, "P3R1": 1.0}
    with pytest.raises(ValueError, match="unknown segments"):
        SpanWireSystem.wye(
            (100.0, 100.0, 100.0), (90.0, 210.0, 330.0),
            wire_weights={"NOPE": 2.0},
        )


def test_load_elevations_simple_closed_form():
    # W = 100 lb at midspan, sag 5 -> the load hangs at exactly -5 ft
    system = SpanWireSystem(
        {"P1": (0.0, 0.0), "P2": (100.0, 0.0)}, {},
        [SegmentDef("P1P2", "P1", "P2",
                    loads=(SpanLoad(50.0, 100.0, label="mid"),))],
    )
    sol = system.solve(5.0)
    records = system.load_elevations(sol)
    assert len(records) == 1
    assert records[0]["elevation_ft"] == pytest.approx(-5.0, abs=1e-6)
    assert records[0]["height_above_lowest_ft"] == 0.0
    assert records[0]["label"] == "mid"


def test_load_elevations_match_independent_profile():
    system = SpanWireSystem.wye(
        (100.0, 100.0, 100.0), (90.0, 210.0, 330.0),
        loads={
            "P1R1": [SpanLoad(30.0, 55.0, label="a"),
                     SpanLoad(70.0, 90.0, label="b")],
            "P2R1": [SpanLoad(50.0, 100.0, label="c")],
            "P3R1": [SpanLoad(50.0, 100.0, label="d")],
        },
        wire_weight_plf=1.0,
    )
    sol = system.solve(5.0)
    records = system.load_elevations(sol)
    assert len(records) == 4
    # cross-check every record against an independently built profile
    by_name = {s.name: s for s in sol.segments}
    for record in records:
        seg = next(s for s in system.segments if s.name == record["segment"])
        res = by_name[seg.name]
        span = SimpleSpan(
            system.plan_length(seg), seg.wire_weight_plf,
            res.start_elevation_ft, res.end_elevation_ft, seg.loads)
        assert record["elevation_ft"] == pytest.approx(
            span.wire_elevation(record["x_ft"], res.horizontal_tension_lb))
    lowest = min(r["elevation_ft"] for r in records)
    assert all(
        r["height_above_lowest_ft"] == pytest.approx(r["elevation_ft"] - lowest)
        for r in records)
    assert min(r["height_above_lowest_ft"] for r in records) == 0.0


def test_load_elevations_empty_without_loads():
    bare = SpanWireSystem.wye(
        (100.0, 100.0, 100.0), (90.0, 210.0, 330.0), wire_weight_plf=1.0)
    assert bare.load_elevations(bare.solve(5.0)) == []


# ── combinations ─────────────────────────────────────────────────────────────


def test_combine_pole_degenerate_angles():
    # collinear pulls add; opposite pulls subtract; square pulls hypot
    inline = combine_pole(1000.0, 30.0, 500.0, 30.0, angle_deg=0.0)
    assert inline.resultant_moment_ftlb == pytest.approx(45000.0)
    assert inline.resultant_tension_lb == pytest.approx(1500.0)
    assert inline.line_of_action_deg == pytest.approx(0.0)

    opposed = combine_pole(1000.0, 30.0, 500.0, 30.0, angle_deg=180.0)
    assert opposed.resultant_moment_ftlb == pytest.approx(15000.0)
    assert opposed.resultant_tension_lb == pytest.approx(500.0)

    square = combine_pole(1000.0, 30.0, 1000.0, 30.0, angle_deg=90.0)
    assert square.resultant_moment_ftlb == pytest.approx(
        math.hypot(30000.0, 30000.0))
    assert square.line_of_action_deg == pytest.approx(45.0)


def test_combine_pole_factor_and_elevations():
    result = combine_pole(
        1267.0, 32.73, 1290.0, 29.48, angle_deg=110.0, factor=1.8,
        attachment_elevation_1_ft=767.48, attachment_elevation_2_ft=768.60,
    )
    assert result.moment_1_ftlb == pytest.approx(1267.0 * 32.73 * 1.8)
    assert result.moment_2_ftlb == pytest.approx(1290.0 * 29.48 * 1.8)
    # pole height rides the higher attachment (manual's rule)
    assert result.governing_attachment_elevation_ft == 768.60
    assert 0.0 < result.line_of_action_deg < 110.0

    with pytest.raises(ValueError, match="negative"):
        combine_pole(-1.0, 30.0, 500.0, 30.0, angle_deg=90.0)


def test_combine_pole_without_elevations_uses_heights():
    result = combine_pole(1000.0, 30.0, 800.0, 34.0, angle_deg=90.0)
    assert result.governing_attachment_elevation_ft == 34.0
