#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see the module header for the full notice)

"""MIDAS advanced-model payload builders
(civilpy.structural.midas_models): curved girders, bifurcated girders,
abutment connections, and nodal soil springs."""

import math

import pytest

from civilpy.structural import midas_models as mm


# ---------------------------------------------------------------- curved

def test_circular_curve_nodes_geometry():
    assign, grid = mm.circular_curve_nodes(
        radius=500.0, central_angle_deg=30.0, n_segments=8,
        girder_offsets=[0.0, 24.0])
    assert len(assign) == 2 * 9
    # station 0 of girder 0 is on the +Y axis at the inner radius
    n0 = assign[str(grid[(0, 0)])]
    assert n0["X"] == pytest.approx(0.0)
    assert n0["Y"] == pytest.approx(500.0)
    # outer girder rides radius 524
    outer = assign[str(grid[(1, 0)])]
    assert outer["Y"] == pytest.approx(524.0)


def test_curved_girder_model_element_counts():
    model = mm.curved_girder_model(
        radius=500.0, central_angle_deg=30.0, n_segments=8,
        girder_offsets=[0.0, 8.0, 16.0, 24.0], diaphragm_sect=2)
    assert len(model["NODE"]) == 36
    # 4*8 girder beams + 3*9 diaphragms
    assert len(model["ELEM"]) == 32 + 27
    assert model["meta"]["arc_length"] == pytest.approx(500.0 * math.radians(30.0))


def test_curved_girder_model_no_diaphragms():
    model = mm.curved_girder_model(
        radius=300.0, central_angle_deg=20.0, n_segments=4,
        girder_offsets=[0.0, 10.0])
    assert len(model["ELEM"]) == 2 * 4   # girder beams only


# ---------------------------------------------------------------- bifurcated

def test_bifurcated_girder_model():
    bif = mm.bifurcated_girder_model(
        stem_length=80.0, stem_segments=8,
        branches=[{"length": 60.0, "end_offset": -15.0, "segments": 6},
                  {"length": 60.0, "end_offset": 15.0, "segments": 6}])
    assert bif["gore_node"] == 9
    assert len(bif["NODE"]) == 9 + 6 + 6
    assert len(bif["ELEM"]) == 8 + 6 + 6
    assert len(bif["branch_end_nodes"]) == 2
    end1 = bif["NODE"][str(bif["branch_end_nodes"][0])]
    assert end1["X"] == pytest.approx(140.0)
    assert end1["Y"] == pytest.approx(-15.0)


def test_bifurcated_branches_share_gore():
    bif = mm.bifurcated_girder_model(
        stem_length=40.0, stem_segments=4,
        branches=[{"length": 30.0, "end_offset": -10.0, "segments": 3},
                  {"length": 30.0, "end_offset": 10.0, "segments": 3}])
    gore = bif["gore_node"]
    # first element of each branch starts at the gore node
    first_branch_elems = [e for e in bif["ELEM"].values()
                          if e["NODE"][0] == gore]
    assert len(first_branch_elems) == 2


# ---------------------------------------------------------------- abutments

def test_integral_abutment_rigid_link():
    out = mm.abutment_connection("integral", girder_end_nodes=[1, 10, 19, 28],
                                 seat_node=100)
    link = out["RIGD"]["100"]["ITEMS"][0]
    assert link["DOF"] == 111111
    assert link["S_NODE"] == [1, 10, 19, 28]


def test_semi_integral_abutment_bearings():
    out = mm.abutment_connection("semi-integral", girder_end_nodes=[1, 2],
                                 seat_node=100)
    assert len(out["ELNK"]) == 2
    sdr = out["ELNK"]["1"]["SDR"]
    assert sdr[2] > 1e6        # stiff vertical
    assert sdr[0] < 100.0      # free longitudinal


def test_semi_integral_custom_bearing_stiffness():
    out = mm.abutment_connection("semi-integral", girder_end_nodes=[5],
                                 seat_node=9, bearing_stiffness=[1, 2, 3, 4, 5, 6])
    assert out["ELNK"]["1"]["SDR"] == [1, 2, 3, 4, 5, 6]
    assert out["ELNK"]["1"]["NODE"] == [5, 9]


def test_abutment_connection_unknown_kind():
    with pytest.raises(ValueError):
        mm.abutment_connection("floating", girder_end_nodes=[1], seat_node=2)


# ---------------------------------------------------------------- springs

def test_soil_spring_supports_body():
    body = mm.soil_spring_supports({201: [10, 10, 50, 0, 0, 0],
                                    202: [12, 12, 60, 0, 0, 0]})
    assert set(body) == {"201", "202"}
    item = body["201"]["ITEMS"][0]
    assert item["TYPE"] == "LINEAR"
    assert item["SDR"] == [10, 10, 50, 0, 0, 0]


def test_soil_spring_supports_validates_vector_length():
    with pytest.raises(ValueError):
        mm.soil_spring_supports({1: [1, 2, 3]})


def test_lb_per_in_to_kip_per_ft():
    assert mm.lb_per_in_to_kip_per_ft(1000.0) == pytest.approx(12.0)
