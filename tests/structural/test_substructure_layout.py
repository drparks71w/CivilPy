#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for substructure geometry placement from executed designs."""

import math
from types import SimpleNamespace

import pytest

from civilpy.structural.abutment import RetainingWall
from civilpy.structural.aashto.lrfd.columns import RebarLayer
from civilpy.structural.bridge_layout import BridgeInput, layout_bridge
from civilpy.structural.pier import MultiColumnBent, PierCap, PierColumn
from civilpy.structural.stm_topology.design import DepthCandidate, PierCapDesign
from civilpy.structural.substructure_layout import (
    AbutmentSpec,
    FootingSpec,
    abutment_geometry,
    pier_geometry,
    substructure_from_layout,
)
from civilpy.structural.substructure import substructure_units


def _cap_design(span: float, depth: float, thickness: float,
                *, tie_force: float = 700.0, bar_size: int = 10,
                bar_count: int = 12) -> PierCapDesign:
    """A PierCapDesign shaped like an optimize_pier_cap result without
    paying for the topology sweep (the optimizer itself is covered by
    the stm_topology tests and the substructure notebook)."""
    tie = SimpleNamespace(force=tie_force, bar_size=bar_size,
                          bar_count=bar_count)
    result = SimpleNamespace(report=SimpleNamespace(ties=[tie]))
    cand = DepthCandidate(depth=depth, cost=1.0, concrete_cost=1.0,
                          steel_lb=100.0, strut_angle=40.0, node_ratio=2.0,
                          max_tie=tie_force, complete=True, feasible=True,
                          result=result)
    return PierCapDesign(optimal=cand, candidates=[cand], span=span,
                         thickness=thickness)


@pytest.fixture(scope="module")
def layout():
    return layout_bridge(BridgeInput(
        spans_ft=(80.0, 80.0), girder_count=4, girder_spacing_ft=9.0,
        girder_label="W36X150", overhang_ft=2.5, railing="SBR-1-20"))


@pytest.fixture(scope="module")
def pier_cap():
    # girders span 27 ft along the cap; 2.5 ft edges -> 32 ft cap
    return _cap_design(span=32.0, depth=5.0, thickness=4.0)


@pytest.fixture(scope="module")
def bent(pier_cap):
    columns = [
        PierColumn(height=240.0, diameter=42.0,
                   layers=[RebarLayer(area=6.0, depth=6.0),
                           RebarLayer(area=6.0, depth=36.0)])
        for _ in range(2)]
    cap = PierCap(length=pier_cap.span * 12.0, width=48.0, depth=60.0,
                  column_positions=[138.0, 246.0])   # 9 / 18 ft girder frame
    return MultiColumnBent(cap, columns)


@pytest.fixture(scope="module")
def abutment_spec():
    wall = RetainingWall(
        stem_height=14.0, stem_thickness=1.5, toe_length=4.0,
        heel_length=8.0, footing_thickness=3.0, backfill_gamma=120.0,
        backfill_phi=32.0)
    return AbutmentSpec(pile_xs_ft=(1.5, 10.0, 18.5, 27.0),
                        pile_shape="HP10X42", pile_length_ft=40.0,
                        wingwall=wall, wingwall_length_ft=12.0)


@pytest.fixture(scope="module")
def sub(layout, pier_cap, bent, abutment_spec):
    abut_cap = _cap_design(span=32.0, depth=3.5, thickness=3.0,
                           tie_force=250.0, bar_size=8, bar_count=6)
    return substructure_from_layout(
        layout, pier_cap=pier_cap, pier_bent=bent, abutment_cap=abut_cap,
        abutment=abutment_spec,
        footing=FootingSpec(length_ft=10.0, width_ft=10.0, thickness_ft=3.0))


def test_unit_inventory(sub):
    assert len(sub.abutments) == 2
    assert len(sub.piers) == 1
    names = [g.unit.name for g in sub.units]
    assert names == ["Abutment 1", "Pier 2", "Abutment 2"]


def test_cap_top_hangs_from_bearing_stack(layout, sub):
    pier = sub.piers[0]
    pads = [bp.location[2] - 4.5 / 12.0 for bp in layout.bearings
            if bp.station_index == 1]
    assert pier.cap.origin[2] == pytest.approx(min(pads) - 3.0 / 12.0)
    # every seat tops out exactly at its own pad bottom
    for seat, z_pad in zip(pier.seats, sorted(
            (bp.line_no, bp.location[2] - 4.5 / 12.0) for bp in
            layout.bearings if bp.station_index == 1)):
        assert seat.center[2] == pytest.approx(z_pad[1])
        assert seat.height_in >= 3.0 - 1e-9


def test_seats_step_with_cross_slope(layout, sub):
    """Crown at mid-width: the fascia pads sit lowest, so the interior
    seats are taller by the cross-slope drop between girder lines."""
    heights = [s.height_in for s in sub.piers[0].seats]
    assert heights[0] == pytest.approx(heights[3])
    assert heights[1] == pytest.approx(heights[2])
    drop_in = (13.5 - 4.5) * (2.0 / 100.0) * 12.0
    assert heights[1] - heights[0] == pytest.approx(drop_in)
    assert min(heights) == pytest.approx(3.0)


def test_cap_centered_on_girders(layout, sub):
    cap = sub.piers[0].cap
    assert cap.length_ft == 32.0 and cap.depth_ft == 5.0
    # s0 = (27 - 32)/2 = -2.5 -> origin 2.5 ft before girder 1, at station 80
    assert cap.origin[0] == pytest.approx(80.0)
    assert cap.origin[1] == pytest.approx(-2.5)
    assert cap.axis == pytest.approx((0.0, 1.0, 0.0))
    assert cap.tie_bar_size == 10 and cap.tie_bar_count == 12


def test_columns_from_bent(sub):
    pier = sub.piers[0]
    assert len(pier.columns) == 2
    for col, y in zip(pier.columns, (9.0, 18.0)):
        assert col.center == pytest.approx((80.0, y))
        assert col.diameter_in == 42.0
        assert col.z_top == pytest.approx(pier.cap.origin[2] - 5.0)
        assert col.height_ft == pytest.approx(20.0)
        assert col.bars_area_in2 == pytest.approx(12.0)
    ftg = pier.footings[0]
    assert ftg.z_top == pytest.approx(pier.columns[0].z_bot)
    assert ftg.volume_cy == pytest.approx(10.0 * 10.0 * 3.0 / 27.0)


def test_abutment_piles_and_backwall(layout, sub):
    a1, a2 = sub.abutments
    assert len(a1.piles) == 4
    z_cap_bot = a1.cap.origin[2] - a1.cap.depth_ft
    for pile, s in zip(a1.piles, (1.5, 10.0, 18.5, 27.0)):
        assert pile.head == pytest.approx((0.0, s, z_cap_bot + 1.0))
        assert pile.length_ft == 40.0
    # backwall shifts to the approach side and rises to the low deck edge
    bw1, bw2 = a1.backwall, a2.backwall
    assert bw1.origin[0] < a1.cap.origin[0]
    assert bw2.origin[0] > a2.cap.origin[0]
    z_edge = layout.deck_top_z(-layout.inputs.overhang_ft)
    assert bw1.origin[2] + bw1.height_ft == pytest.approx(z_edge)
    assert bw1.height_ft > 0


def test_wingwalls_from_retaining_wall(sub):
    a1 = sub.abutments[0]
    stems = a1.wingwalls[0::2]
    footings = a1.wingwalls[1::2]
    assert len(stems) == len(footings) == 2
    for stem, ftg in zip(stems, footings):
        assert stem.height_ft == 14.0 and stem.thickness_ft == 1.5
        assert stem.axis == (-1.0, 0.0, 0.0)
        assert ftg.thickness_ft == pytest.approx(4.0 + 1.5 + 8.0)
        assert ftg.origin[2] + ftg.height_ft == pytest.approx(stem.origin[2])


def test_skewed_support_frame(pier_cap, bent):
    layout30 = layout_bridge(BridgeInput(
        spans_ft=(80.0, 80.0), girder_count=4, girder_spacing_ft=9.0,
        girder_label="W36X150", overhang_ft=2.5, skew_deg=30.0))
    unit = substructure_units(layout30)[1]
    cos30, sin30 = math.cos(math.radians(30)), math.sin(math.radians(30))
    cap32 = _cap_design(span=27.0 / cos30 + 5.0, depth=5.0, thickness=4.0)
    pier = pier_geometry(layout30, unit, cap32, bent)
    assert pier.cap.axis == pytest.approx((sin30, cos30, 0.0))
    # seats land exactly on the skewed bearing plan positions
    for seat, bp in zip(pier.seats, sorted(
            (bp for bp in layout30.bearings if bp.station_index == 1),
            key=lambda b: b.line_no)):
        assert seat.center[0] == pytest.approx(bp.location[0])
        assert seat.center[1] == pytest.approx(bp.location[1])


def test_pile_bent_pier(layout, abutment_spec):
    from civilpy.structural.substructure_layout import (
        PileBentSpec, SeatAbutmentSpec, assemble_substructure)

    abut_cap = _cap_design(span=32.0, depth=3.5, thickness=3.0)
    pier_cap = _cap_design(span=32.0, depth=3.0, thickness=3.0)
    sub2 = assemble_substructure(layout, {
        "pier": PileBentSpec(cap_design=pier_cap,
                             pile_xs_ft=(1.0, 9.5, 18.0, 26.5)),
        "abutment": SeatAbutmentSpec(cap_design=abut_cap,
                                     spec=abutment_spec)})
    assert len(sub2.piers) == 1 and len(sub2.abutments) == 2
    pier = sub2.piers[0]
    assert pier.columns == () and pier.footings == ()
    assert len(pier.piles) == 4
    assert pier.piles[0].shape == "HP12X53"          # CPP-1-08 default
    z_cap_bot = pier.cap.origin[2] - pier.cap.depth_ft
    for pile, s in zip(pier.piles, (1.0, 9.5, 18.0, 26.5)):
        assert pile.head == pytest.approx((80.0, s, z_cap_bot + 1.0))
    # the seat plane is the same regardless of what carries the cap
    assert [s.height_in for s in pier.seats] == pytest.approx(
        [s.height_in for s in sub2.abutments[0].seats])


def test_assemble_mixed_types_by_index(layout, pier_cap, bent,
                                       abutment_spec):
    from civilpy.structural.substructure_layout import (
        BentPierSpec, PileBentSpec, SeatAbutmentSpec, assemble_substructure)

    abut = SeatAbutmentSpec(
        cap_design=_cap_design(span=32.0, depth=3.5, thickness=3.0),
        spec=abutment_spec)
    three_span = layout_bridge(BridgeInput(
        spans_ft=(60.0, 80.0, 60.0), girder_count=4, girder_spacing_ft=9.0,
        girder_label="W36X150", overhang_ft=2.5))
    sub3 = assemble_substructure(three_span, {
        "abutment": abut,
        1: BentPierSpec(cap_design=pier_cap, bent=bent),
        2: PileBentSpec(cap_design=_cap_design(span=32.0, depth=3.0,
                                               thickness=3.0),
                        pile_xs_ft=(1.0, 14.0, 26.0)),
    })
    by_index = {p.unit.index: p for p in sub3.piers}
    assert by_index[1].columns and not by_index[1].piles
    assert by_index[2].piles and not by_index[2].columns


def test_assemble_missing_spec_raises(layout, abutment_spec):
    from civilpy.structural.substructure_layout import (
        SeatAbutmentSpec, assemble_substructure)

    with pytest.raises(ValueError, match="no spec assigned for Pier 2"):
        assemble_substructure(layout, {
            "abutment": SeatAbutmentSpec(
                cap_design=_cap_design(span=32.0, depth=3.5, thickness=3.0),
                spec=abutment_spec)})


def test_infeasible_design_raises(layout, bent, abutment_spec):
    bad = PierCapDesign(optimal=None, candidates=[], span=32.0, thickness=4.0)
    unit = substructure_units(layout)[1]
    with pytest.raises(ValueError, match="no feasible depth"):
        pier_geometry(layout, unit, bad, bent)
