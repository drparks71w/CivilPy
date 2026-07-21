#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Multi-segment span-wire systems: Wye, H, Delta, Box.

Symmetric configurations have closed-form tension relations and ring
elevations, derived by hand from bullring equilibrium:

* symmetric wye (legs 120 deg apart, 100 lb at each midspan, sag 5 ft):
  relations 1:1:1, ring at -5000/H -> H = 1000 lb, pole reaction 100 lb.
* square box with diagonal tails: side tension = tail / sqrt(2); the
  required tail-2 direction is the diagonal regardless of input, so a
  10-degree mis-set reports a -10 degree balance rotation.
* equilateral delta with radial tails: side tension = tail / sqrt(3).
"""

import math

import pytest

from civilpy.structural.spanwire import (
    SegmentDef,
    SimpleSpan,
    SpanLoad,
    SpanWireSystem,
)


def symmetric_wye(**kwargs):
    return SpanWireSystem.wye(
        leg_lengths=(100.0, 100.0, 100.0),
        leg_bearings_deg=(90.0, 210.0, 330.0),
        loads={
            "P1R1": [SpanLoad(50.0, 100.0)],
            "P2R1": [SpanLoad(50.0, 100.0)],
            "P3R1": [SpanLoad(50.0, 100.0)],
        },
        **kwargs,
    )


def test_symmetric_wye_closed_form():
    system = symmetric_wye()
    relations, rotation, warped = system.tension_relations()
    assert rotation == 0.0 and warped is None
    assert relations == pytest.approx({"P1R1": 1.0, "P2R1": 1.0, "P3R1": 1.0})

    sol = system.solve(5.0)
    assert sol.reference_segment == "P3R1"
    assert sol.reference_tension_lb == pytest.approx(1000.0, rel=1e-6)
    assert sol.ring_elevations["R1"] == pytest.approx(-5.0, abs=1e-6)
    assert sol.sag_ft == pytest.approx(5.0, abs=1e-6)
    assert sol.in_balance
    for seg in sol.segments:
        assert seg.horizontal_tension_lb == pytest.approx(1000.0, rel=1e-6)
        assert seg.start_reaction_lb == pytest.approx(100.0, abs=1e-6)  # at pole
        assert seg.end_reaction_lb == pytest.approx(0.0, abs=1e-6)      # at ring
        assert seg.low_point_elevation_ft == pytest.approx(-5.0, abs=1e-6)
    assert sol.pole_tensions() == pytest.approx(
        {"P1": 1000.0, "P2": 1000.0, "P3": 1000.0}
    )


def test_asymmetric_wye_relations_are_pure_geometry():
    # legs at 0, 90, 225 degrees: T1 = T2 = T3 / sqrt(2), independent of loads
    system = SpanWireSystem.wye(
        leg_lengths=(80.0, 60.0, 100.0),
        leg_bearings_deg=(0.0, 90.0, 225.0),
        loads={"P1R1": [SpanLoad(40.0, 200.0)]},
    )
    relations, _, _ = system.tension_relations()
    assert relations["P1R1"] == pytest.approx(math.sqrt(2) / 2, abs=1e-9)
    assert relations["P2R1"] == pytest.approx(math.sqrt(2) / 2, abs=1e-9)
    assert relations["P3R1"] == 1.0


def test_wye_bad_geometry_raises():
    # all three legs on one side of the ring: the wire would have to push
    system = SpanWireSystem.wye(
        leg_lengths=(100.0, 100.0, 100.0),
        leg_bearings_deg=(0.0, 45.0, 90.0),
        loads={"P1R1": [SpanLoad(50.0, 100.0)]},
    )
    with pytest.raises(ValueError, match="cannot push"):
        system.tension_relations()


def square_box(tail2_bearing=315.0, **kwargs):
    return SpanWireSystem.box(
        ring_positions=((0.0, 0.0), (40.0, 0.0), (40.0, 40.0), (0.0, 40.0)),
        tail_lengths=(20.0, 20.0, 20.0, 20.0),
        tail_bearings_deg=(225.0, tail2_bearing, 45.0, 135.0),
        loads={
            "R1R2": [SpanLoad(20.0, 90.0)],
            "R3R4": [SpanLoad(20.0, 90.0)],
        },
        **kwargs,
    )


def test_symmetric_box_in_balance():
    relations, rotation, _ = square_box().tension_relations()
    assert abs(rotation) < 1e-9
    for side in ("R1R2", "R2R3", "R3R4", "R4R1"):
        assert relations[side] == pytest.approx(1.0, abs=1e-9)
    for tail in ("P1R1", "P2R2", "P3R3", "P4R4"):
        assert relations[tail] == pytest.approx(math.sqrt(2), abs=1e-9)


def test_box_balance_rotation_reported():
    # tail 2 mis-set 10 degrees CCW of the balancing diagonal
    system = square_box(tail2_bearing=325.0)
    relations, rotation, warped = system.tension_relations()
    assert rotation == pytest.approx(-10.0, abs=1e-9)
    # the balanced solution is the symmetric one regardless of the mis-set
    assert relations["P2R2"] == pytest.approx(math.sqrt(2), abs=1e-9)
    assert warped[0] == pytest.approx(40.0 + 20.0 * math.cos(math.radians(315.0)))
    assert warped[1] == pytest.approx(20.0 * math.sin(math.radians(315.0)))

    sol = system.solve(4.0)
    assert not sol.in_balance
    assert sol.balance_pole == "P2"
    assert sol.balance_rotation_deg == pytest.approx(-10.0, abs=1e-6)


def test_box_solve_statics_consistency():
    system = square_box()
    sol = system.solve(4.0)
    assert sol.sag_ft == pytest.approx(4.0, abs=1e-6)
    # by symmetry the two loaded sides hang identically
    r12 = next(s for s in sol.segments if s.name == "R1R2")
    r34 = next(s for s in sol.segments if s.name == "R3R4")
    assert r12.low_point_elevation_ft == pytest.approx(r34.low_point_elevation_ft)
    # vertical equilibrium: pole reactions carry the whole system
    pole_total = sum(
        seg.start_reaction_lb for seg in sol.segments if seg.name.startswith("P")
    )
    assert pole_total == pytest.approx(180.0, abs=1e-6)
    # every ring is in vertical equilibrium
    for ring in ("R1", "R2", "R3", "R4"):
        residual = 0.0
        for seg in sol.segments:
            if seg.start == ring:
                residual += seg.start_reaction_lb
            elif seg.end == ring:
                residual += seg.end_reaction_lb
        assert residual == pytest.approx(0.0, abs=1e-6)


def test_equilateral_delta():
    side = 40.0
    height = side * math.sqrt(3) / 2
    system = SpanWireSystem.delta(
        ring_positions=((0.0, 0.0), (side, 0.0), (side / 2, height)),
        tail_lengths=(15.0, 15.0, 15.0),
        tail_bearings_deg=(210.0, 330.0, 90.0),
        loads={"R1R2": [SpanLoad(20.0, 55.0)]},
    )
    relations, rotation, _ = system.tension_relations()
    assert abs(rotation) < 1e-9
    for tail in ("P1R1", "P2R2", "P3R3"):
        assert relations[tail] == pytest.approx(math.sqrt(3), abs=1e-9)
    for s in ("R1R2", "R2R3"):
        assert relations[s] == pytest.approx(1.0, abs=1e-9)

    sol = system.solve(3.0)
    assert sol.sag_ft == pytest.approx(3.0, abs=1e-6)
    assert sol.in_balance
    assert set(sol.ring_elevations) == {"R1", "R2", "R3"}


def test_h_configuration_through_generic_constructor():
    # two rings, a crossbar, four angled tails: statically determinate
    poles = {
        "P1": (-30.0, -10.0), "P2": (30.0, -10.0),
        "P3": (-30.0, 50.0), "P4": (30.0, 50.0),
    }
    rings = {"R1": (0.0, 0.0), "R2": (0.0, 40.0)}
    segments = [
        SegmentDef("P1R1", "P1", "R1", loads=(SpanLoad(15.0, 40.0),)),
        SegmentDef("P2R1", "P2", "R1"),
        SegmentDef("R1R2", "R1", "R2", loads=(SpanLoad(20.0, 60.0),)),
        SegmentDef("P3R2", "P3", "R2"),
        SegmentDef("P4R2", "P4", "R2"),
    ]
    system = SpanWireSystem(poles, rings, segments)
    relations, rotation, _ = system.tension_relations()
    assert rotation == 0.0
    assert all(rel > 0 for rel in relations.values())
    sol = system.solve(4.0)
    assert sol.sag_ft == pytest.approx(4.0, abs=1e-6)
    # global vertical balance
    pole_total = sum(
        seg.start_reaction_lb for seg in sol.segments if seg.name.startswith("P")
    )
    assert pole_total == pytest.approx(100.0, abs=1e-6)


def test_attachment_elevations_and_pole_tensions():
    system = symmetric_wye()
    sol = system.solve(5.0)
    elevations = system.attachment_elevations(sol, clearance_ft=20.5)
    assert elevations == pytest.approx({"P1": 25.5, "P2": 25.5, "P3": 25.5})


def test_elevated_poles_shift_ring():
    system = symmetric_wye(
        pole_attachment_elevations={"P1": 2.0, "P2": 2.0, "P3": 2.0}
    )
    sol = system.solve(5.0)
    # uniform +2 ft shift moves the whole solution rigidly
    assert sol.ring_elevations["R1"] == pytest.approx(-3.0, abs=1e-6)
    assert sol.sag_ft == pytest.approx(5.0, abs=1e-6)


def test_validation_errors():
    with pytest.raises(ValueError, match="distinct"):
        SpanWireSystem({"A": (0, 0)}, {"A": (1, 1)}, [])
    with pytest.raises(ValueError, match="unknown node"):
        SpanWireSystem(
            {"P1": (0, 0), "P2": (10, 0)}, {},
            [SegmentDef("S1", "P1", "NOPE")],
        )
    with pytest.raises(ValueError, match="exactly one segment"):
        SpanWireSystem({"P1": (0, 0), "P2": (10, 0)}, {}, [])
    with pytest.raises(ValueError, match="at least 3"):
        SpanWireSystem(
            {"P1": (0, 0), "P2": (20, 0)}, {"R1": (10, 0)},
            [SegmentDef("S1", "P1", "R1"), SegmentDef("S2", "R1", "P2")],
        )
    with pytest.raises(ValueError, match="unique"):
        SpanWireSystem(
            {"P1": (0, 0), "P2": (10, 0)}, {},
            [SegmentDef("S1", "P1", "P2"), SegmentDef("S1", "P2", "P1")],
        )
    with pytest.raises(ValueError, match="3 ring positions"):
        SpanWireSystem.delta(((0, 0), (1, 0)), (1, 1, 1), (0, 0, 0))
    with pytest.raises(ValueError, match="4 ring positions"):
        SpanWireSystem.box(((0, 0),), (1, 1, 1, 1), (0, 0, 0, 0))
    with pytest.raises(ValueError, match="unknown segments"):
        SpanWireSystem.wye(
            (100.0, 100.0, 100.0), (90.0, 210.0, 330.0),
            loads={"BOGUS": [SpanLoad(1.0, 1.0)]},
        )
    with pytest.raises(ValueError, match="tail lengths"):
        SpanWireSystem.wye((0.0, 100.0, 100.0), (90.0, 210.0, 330.0))


def test_reference_selection_rules():
    system = symmetric_wye()
    relations, _, _ = system.tension_relations(reference="P1R1")
    assert relations["P1R1"] == 1.0
    with pytest.raises(ValueError, match="unknown reference"):
        system.tension_relations(reference="XX")
    box = square_box()
    with pytest.raises(ValueError, match="cannot be the reference"):
        box.tension_relations(reference="P2R2")


def test_balance_pole_required_for_closed_shapes():
    # box builder defaults to P2; renaming it away must raise
    with pytest.raises(ValueError, match="balance_pole"):
        SpanWireSystem.box(
            ring_positions=((0, 0), (40, 0), (40, 40), (0, 40)),
            tail_lengths=(20, 20, 20, 20),
            tail_bearings_deg=(225, 315, 45, 135),
            balance_pole="P9",
        )


def test_no_load_and_unreachable_sag_errors():
    bare = SpanWireSystem.wye((100.0, 100.0, 100.0), (90.0, 210.0, 330.0))
    with pytest.raises(ValueError, match="no load"):
        bare.solve(5.0)
    lopsided = symmetric_wye(
        pole_attachment_elevations={"P1": 0.0, "P2": 0.0, "P3": 10.0}
    )
    with pytest.raises(ValueError, match="unreachable"):
        lopsided.solve(5.0)   # sag can never drop below the elevation spread


def test_simple_span_through_system_class_matches_solver():
    # two poles, no rings: the degenerate case must agree with SimpleSpan
    system = SpanWireSystem(
        {"P1": (0.0, 0.0), "P2": (100.0, 0.0)}, {},
        [SegmentDef("S1", "P1", "P2", loads=(SpanLoad(50.0, 100.0),))],
    )
    relations, rotation, warped = system.tension_relations()
    assert relations == {"S1": 1.0} and rotation == 0.0 and warped is None
    sol = system.solve(5.0)
    direct = SimpleSpan(100.0, loads=[SpanLoad(50.0, 100.0)]).solve(5.0)
    assert sol.reference_tension_lb == pytest.approx(
        direct.horizontal_tension_lb, rel=1e-9
    )
