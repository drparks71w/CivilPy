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


# ------------------------------------------------- shared encoders (S4)

def test_unit_block_defaults_kips_ft():
    u = mm.unit_block()
    assert u["1"] == {"FORCE": "KIPS", "DIST": "FT",
                      "HEAT": "BTU", "TEMPER": "F"}


def test_unit_block_for_maps_hub_labels():
    from civilpy.structural.structural_model import Units
    assert mm.unit_block_for(Units(force="kips", length="ft"))["1"]["FORCE"] == "KIPS"
    metric = mm.unit_block_for(Units(force="kN", length="m"))["1"]
    assert (metric["FORCE"], metric["DIST"]) == ("KN", "M")


def test_steel_material_block_shape():
    m = mm.steel_material_block("A709-50")["1"]
    assert m["TYPE"] == "USER" and m["NAME"] == "A709-50"
    assert m["PARAM"][0]["ELAST"] == mm.STEEL_PROPS["ELAST"]


def test_constraint_assign_wraps_flag_string():
    body = mm.constraint_assign({3: "1100000"})
    assert body["3"]["ITEMS"][0]["CONSTRAINT"] == "1100000"


# ------------------------------------------------- hub serializer (S4)

def _hub_truss():
    """A 3-node truss with a pin, a vertical roller, and a 600-kip load."""
    from civilpy.structural.structural_model import StructuralModel
    m = StructuralModel()
    a = m.add_node(0, 0, 0, label="A")
    b = m.add_node(8, 0, 0, label="B")
    c = m.add_node(4, 0, 4, label="C")
    for ni, nj in [(a, b), (b, c), (a, c)]:
        m.add_element(ni.id, nj.id)
    m.add_restraint(a.id, preset="pin")
    m.add_restraint(b.id, preset="roller-v")
    m.add_load(c.id, fz=-600)
    return m, {"A": a.id, "B": b.id, "C": c.id}


def test_midas_payloads_table_set_and_order():
    m, _ = _hub_truss()
    p = mm.midas_payloads(m)
    assert list(p) == ["UNIT", "MATL", "SECT", "NODE", "ELEM", "CONS",
                       "STLD", "CNLD"]
    assert len(p["NODE"]) == 3
    assert len(p["ELEM"]) == 3


def test_midas_payloads_nodes_carry_3d_coords():
    m, _ = _hub_truss()
    p = mm.midas_payloads(m)
    zs = {n["Z"] for n in p["NODE"].values()}
    assert 4.0 in zs                      # out-of-plane / height survives


def test_midas_payloads_constraints_from_full_6dof():
    m, _ = _hub_truss()
    p = mm.midas_payloads(m)
    constraints = sorted(s["ITEMS"][0]["CONSTRAINT"]
                         for s in p["CONS"].values())
    assert constraints == ["0100000", "1100000"]   # roller-v, pin


def test_midas_payloads_fixed_support_keeps_moment_dof():
    from civilpy.structural.structural_model import StructuralModel
    m = StructuralModel()
    a = m.add_node(0, 0, 0)
    b = m.add_node(10, 0, 0)
    m.add_element(a.id, b.id)
    m.add_restraint(a.id, preset="fixed")
    p = mm.midas_payloads(m)
    assert p["CONS"][str(1)]["ITEMS"][0]["CONSTRAINT"] == "1100010"


def test_midas_payloads_load_lands_in_cnld_and_stld():
    m, ids = _hub_truss()
    p = mm.midas_payloads(m)
    assert {c["NAME"] for c in p["STLD"].values()} == {"default"}
    item = next(iter(p["CNLD"].values()))["ITEMS"][0]
    assert item["FZ"] == pytest.approx(-600.0)
    assert item["LCNAME"] == "default"


def test_midas_payloads_element_references_section_and_material():
    m, _ = _hub_truss()
    p = mm.midas_payloads(m)
    elem = next(iter(p["ELEM"].values()))
    assert elem["SECT"] == 1 and elem["MATL"] == 1
    assert "1" in p["SECT"] and "1" in p["MATL"]


def test_push_midas_reports_per_table():
    """push_midas reports {table: {"sent": n}} against a fake client,
    mirroring TrussBridge.to_midas (no live session)."""
    m, _ = _hub_truss()

    class FakeMidas:
        def __init__(self):
            self.calls = []

        def put_db(self, table, assign):
            self.calls.append(table)
            return {"ok": True}

    fake = FakeMidas()
    report = mm.push_midas(m, midas=fake)
    assert fake.calls == list(mm.midas_payloads(m))
    assert report["NODE"] == {"sent": 3}
    assert report["CONS"] == {"sent": 2}


def test_push_midas_keeps_going_on_table_error():
    m, _ = _hub_truss()

    class FlakyMidas:
        def put_db(self, table, assign):
            if table == "CONS":
                raise RuntimeError("CONS rejected")
            return {}

    report = mm.push_midas(m, midas=FlakyMidas())
    assert "error" in report["CONS"]
    assert report["NODE"] == {"sent": 3}     # other tables still sent
