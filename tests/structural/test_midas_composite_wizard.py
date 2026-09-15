"""Property tests for the Steel Composite Girder Bridge wizard payload
builder: the geometry RULES (skewed reference lines, strip layout, edge
chains, cross-frame arrangement, bearings, groups, tables) hold for any
bridge, not just the tutorial the rules were learned from.  Pure functions,
no MIDAS session, no fixture."""
import math
from collections import Counter, defaultdict

import pytest

from civilpy.structural import midas_composite_wizard as wiz

TUTORIAL = wiz.WizardInputs()
TWO_SPAN_STRAIGHTISH = wiz.WizardInputs(
    spans=(80.0, 80.0), radius=5000.0, skews_deg=(0.0, 0.0, 0.0), deck_width=36.0,
    layout_offset=0.0, superelevation=0.0, profile=((0.0, 10.0), (160.0, 12.0)), vertical_curve=None,
    girder_offsets=(-13.5, -4.5, 4.5, 13.5), deck_strip_spacing=4.0, bracing_divisions=(4, 4),
    splices=(30.0, 55.0, 105.0, 130.0), negative_zones=((55.0, 105.0),),
    pier_heights=(20.0,), lane_centres_from_left_edge=(9.0, 21.0, 30.0),
    barrier_widths=(2.0, 15.0, 2.0, 15.0, 2.0))
FOUR_SPAN_SKEWED = wiz.WizardInputs(
    spans=(50.0, 70.0, 70.0, 50.0), radius=800.0, skews_deg=(5.0, 10.0, 15.0, 20.0, 25.0), deck_width=40.0,
    layout_offset=3.0, superelevation=-0.04, vertical_curve=(-0.02, 0.01, 100.0, 20.0, 5.0),
    girder_offsets=(-14.0, -7.0, 0.0, 7.0, 14.0, 21.0), deck_strip_spacing=5.0, bracing_divisions=(3, 4, 4, 3),
    splices=(30.0, 62.0, 128.0, 165.0, 208.0), negative_zones=((30.0, 62.0), (128.0, 165.0)),
    pier_heights=(15.0, 22.0, 18.0), lane_centres_from_left_edge=(8.0, 20.0, 32.0),
    barrier_widths=(1.5, 18.0, 1.0, 18.0, 1.5))
CASES = [pytest.param(TUTORIAL, id="tutorial"), pytest.param(TWO_SPAN_STRAIGHTISH, id="two-span"),
         pytest.param(FOUR_SPAN_SKEWED, id="four-span")]


@pytest.fixture(scope="module", params=CASES)
def case(request):
    w = request.param
    payload, info = wiz.build(w)
    return w, payload, info


def _groups(payload):
    return {v["NAME"]: v for v in payload["GRUP"].values()}


def _station(w, node):
    return w.radius * math.atan2(node["X"], node["Y"] + w.radius)


def _offset(w, node):
    return w.radius - math.hypot(node["X"], node["Y"] + w.radius)


# ------------------------------------------------------------ reference lines
@pytest.mark.parametrize("s", [0.0, 12.5, 60.0, 100.0, 216.0])
def test_skew_interpolates_between_supports(s):
    w = TUTORIAL
    a = wiz.skew_at(w, s)
    S, A = w.support_stations, w.skews_deg
    if s in S:
        assert a == A[S.index(s)]
    else:
        k = next(i for i in range(len(S) - 1) if S[i] < s < S[i + 1])
        lo, hi = sorted((A[k], A[k + 1]))
        assert lo < a < hi


@pytest.mark.parametrize("s, offset", [(0.0, -22.0), (35.0, 5.0), (108.0, -7.0), (216.0, 8.0)])
def test_line_theta_is_the_skewed_line_through_the_station(s, offset):
    """The crossing lies on the straight line through the reference point
    at ``s`` with the interpolated skew: its station shift equals
    offset * tan(skew) to first order, exactly zero at zero skew."""
    w = TUTORIAL
    th = wiz.line_theta(w, s, offset)
    x, y = wiz.plan_xy(w, th, offset)
    px, py = wiz.plan_xy(w, s / w.radius, 0.0)
    a = math.radians(wiz.skew_at(w, s))
    # the line through the pivot: the radial direction rotated by the skew
    th0 = s / w.radius
    dx, dy = -math.sin(th0 - a), -math.cos(th0 - a)
    cross = (x - px) * dy - (y - py) * dx
    assert abs(cross) < 1e-6 * max(1.0, abs(offset))
    flat = wiz.WizardInputs(skews_deg=(0, 0, 0, 0))
    assert math.isclose(wiz.line_theta(flat, s, offset), s / w.radius, rel_tol=1e-12, abs_tol=1e-12)


# --------------------------------------------------------------- girders
def test_girder_nodes_are_exactly_the_reference_line_crossings(case):
    w, payload, info = case
    strips, braces, tenth = wiz.reference_stations(w)
    lines = set(strips) | set(braces) | set(w.splices) | set(tenth) | set(w.support_stations)
    nodes = payload["NODE"]
    for i, o in enumerate(w.girder_offsets):
        want = {round(wiz.line_theta(w, s, o) * w.radius, 3) for s in lines}
        lo, hi = wiz.support_theta(w, 0, o), wiz.support_theta(w, len(w.support_stations) - 1, o)
        want = {s for s in want if lo * w.radius - 1e-3 <= s <= hi * w.radius + 1e-3}
        got = {round(_station(w, nodes[str(n)]), 3) for n in info["girder_chains"][i]}
        assert got == want, f"girder {i}"
        # one element between each consecutive pair, no gaps, no overlaps
        assert len(info["girder_elems"][i]) == len(info["girder_chains"][i]) - 1


def test_girder_section_follows_the_negative_zones(case):
    w, payload, info = case
    nodes = payload["NODE"]
    for i in range(len(w.girder_offsets)):
        for e in info["girder_elems"][i]:
            a, b = payload["ELEM"][str(e)]["NODE"]
            smid = (_station(w, nodes[str(a)]) + _station(w, nodes[str(b)])) / 2
            # the section is decided at the element midpoint on the reference line, allow the skew shift
            sect = payload["ELEM"][str(e)]["SECT"]
            shift = abs(w.girder_offsets[i] * math.tan(math.radians(wiz.skew_at(w, smid)))) + 1e-6
            inside = any(a0 + shift < smid < b0 - shift for a0, b0 in w.negative_zones)
            outside = not any(a0 - shift < smid < b0 + shift for a0, b0 in w.negative_zones)
            if inside:
                assert sect == w.sect_girder_neg
            elif outside:
                assert sect == w.sect_girder_pos


# ---------------------------------------------------------------- deck
def test_strip_lines_have_one_element_per_bay_and_three_per_overhang(case):
    w, payload, info = case
    strips, _, _ = wiz.reference_stations(w)
    per_line = Counter(tag[1] for (kind, e), tag in info["tags"].items() if kind == "E" and tag[0] == "STRIP")
    n_bays = len(w.girder_offsets) - 1
    overhang = (3 if w.barrier_widths[0] > 0 else 1) + (3 if w.barrier_widths[-1] > 0 else 1)
    assert set(per_line) == set(strips)
    assert set(per_line.values()) == {n_bays + overhang}
    groups = _groups(payload)
    d1, d2 = set(groups["Dummy Beam-D1"]["E_LIST"]), set(groups["Dummy Beam-D2"]["E_LIST"])
    assert d1 | d2 == set(groups["Dummy Beam"]["E_LIST"]) and not d1 & d2
    for (kind, e), tag in info["tags"].items():
        if kind == "E" and tag[0] == "STRIP":
            negative = any(a <= tag[1] < b for a, b in w.negative_zones)
            assert (e in d2) == negative


def test_overhang_nodes_sit_at_edge_half_barrier_and_barrier(case):
    w, payload, info = case
    left, right = w.deck_edges
    offsets = Counter(round(tag[2], 4) for (kind, n), tag in info["tags"].items() if kind == "N" and tag[0] == "DECK")
    want = {round(left, 4), round(right, 4)}
    if w.barrier_widths[0] > 0:
        want |= {round(left + w.barrier_widths[0] / 2, 4), round(left + w.barrier_widths[0], 4)}
    if w.barrier_widths[-1] > 0:
        want |= {round(right - w.barrier_widths[-1] / 2, 4), round(right - w.barrier_widths[-1], 4)}
    assert set(offsets) == want
    n_lines = len(wiz.reference_stations(w)[0])
    assert set(offsets.values()) == {n_lines}


def test_edge_chains_have_a_node_at_every_line_reaching_the_edge(case):
    w, payload, info = case
    strips, _, tenth = wiz.reference_stations(w)
    stations = set(strips) | set(w.splices) | set(tenth) | set(w.support_stations)
    groups = _groups(payload)
    edge_elems = groups["Dummy Beam2"]["E_LIST"]
    for offset in w.deck_edges:
        want = {round(wiz.line_theta(w, s, offset) * w.radius, 2) for s in stations}
        chain_nodes = {n for e in edge_elems for n in payload["ELEM"][str(e)]["NODE"]
                       if abs(_offset(w, payload["NODE"][str(n)]) - offset) < 1e-3}
        got = {round(_station(w, payload["NODE"][str(n)]), 2) for n in chain_nodes}
        assert got == want
    # a chain: every node has degree 2 except the two ends
    degree = Counter(n for e in edge_elems for n in payload["ELEM"][str(e)]["NODE"])
    assert Counter(degree.values()) == {2: len(degree) - 4, 1: 4}
    assert {payload["ELEM"][str(e)]["SECT"] for e in edge_elems} == {w.sect_edge}
    assert len(edge_elems) == len(degree) - 2


# ------------------------------------------------------------ cross frames
def test_cross_frames_v_down_with_rigid_slaves_at_chord_depths(case):
    w, payload, info = case
    slab = (w.deck_thickness_in + w.haunch_in) / 12
    _, braces, _ = wiz.reference_stations(w)
    n_lines = len(braces) + len(w.support_stations) - 2      # interior supports carry V-braces too
    n_bays = len(w.girder_offsets) - 1
    apex = [n for (kind, n), tag in info["tags"].items() if kind == "N" and tag[0] == "APEX"]
    assert len(apex) == n_lines * n_bays
    elems = payload["ELEM"]
    nodes = payload["NODE"]
    by_node = defaultdict(list)
    for e, v in elems.items():
        for n in v["NODE"]:
            by_node[n].append(v)
    for a in apex:
        members = by_node[a]
        assert Counter(m["TYPE"] for m in members) == {"BEAM": 2, "TRUSS": 2}   # split bottom chord + 2 diagonals
        assert {m["SECT"] for m in members if m["TYPE"] == "TRUSS"} == {w.sect_brace}
    # slaves of a girder node on a bracing line: top and bottom chord depths
    for m, v in payload["RIGD"].items():
        z0 = nodes[m]["Z"]
        depths = sorted(round(z0 - nodes[str(s)]["Z"], 4) for s in v["ITEMS"][0]["S_NODE"])
        assert depths[0] > slab                                # everything hangs below the slab
        assert v["ITEMS"][0]["DOF"] == 111111
    truss = sum(1 for v in elems.values() if v["TYPE"] == "TRUSS")
    assert truss == n_lines * n_bays * 2 + 2 * n_bays          # diagonals + the two truss diaphragms


# ---------------------------------------------------------------- bearings
def test_bearings_seat_link_support(case):
    w, payload, info = case
    ng, ns = len(w.girder_offsets), len(w.support_stations)
    assert len(payload["ELNK"]) == ng * ns
    nodes = payload["NODE"]
    seats = {n for (kind, n), tag in info["tags"].items() if kind == "N" and tag[0] == "SEAT"}
    slaves = {s for v in payload["RIGD"].values() for s in v["ITEMS"][0]["S_NODE"]}
    assert seats <= slaves                                      # every seat is rigid-slaved to its girder node
    for v in payload["ELNK"].values():
        seat, sup = v["NODE"]
        assert seat in seats
        assert math.isclose(nodes[str(seat)]["Z"] - nodes[str(sup)]["Z"], w.link_length)
        assert nodes[str(seat)]["X"] == nodes[str(sup)]["X"] and nodes[str(seat)]["Y"] == nodes[str(sup)]["Y"]
        assert v["bSHEAR"] and v["SDR"][3:] == [0, 0, 0]
    angles = {round(v["ANGLE"], 6) for v in payload["ELNK"].values()}
    want = {round(math.degrees(s / w.radius) - a, 6) for s, a in zip(w.support_stations, w.skews_deg)}
    assert angles == want
    # abutment support nodes and column bases are the only constraints
    assert len(payload["CONS"]) == 2 * ng + (ns - 2)
    assert {v["ITEMS"][0]["CONSTRAINT"] for v in payload["CONS"].values()} == {"1111110"}


def test_pier_caps_reach_the_deck_edges_and_columns_hang_off_them(case):
    w, payload, info = case
    left, right = w.deck_edges
    for k, elems in info["cap_elements"].items():
        assert len(elems) == len(w.girder_offsets) + 2       # tips + seats + the zero-length column element
        cap_nodes = {n for e in elems for n in payload["ELEM"][str(e)]["NODE"]}
        offsets = {round(_offset(w, payload["NODE"][str(n)]), 3) for n in cap_nodes}
        assert round(left, 3) in offsets and round(right, 3) in offsets
        assert info["col_base"][k] not in cap_nodes
        column = next(v for v in payload["ELEM"].values() if info["col_base"][k] in v["NODE"])
        assert set(column["NODE"]) & cap_nodes
        assert math.isclose(payload["NODE"][str(info["col_base"][k])]["Z"],
                            payload["NODE"][str(next(iter(set(column["NODE"]) & cap_nodes)))]["Z"] - w.pier_heights[k - 1])


# --------------------------------------------------------------- elevation
def test_deck_elevation_banks_about_the_reference_line(case):
    w, _, _ = case
    for s in (0.0, sum(w.spans) / 3, sum(w.spans)):
        base = wiz.deck_elevation(w, s, 0.0)
        for o in (-10.0, 4.0):
            assert math.isclose(wiz.deck_elevation(w, s, o) - base, w.superelevation * o)


def test_vertical_curve_profile():
    g1, g2, L, s0, z0 = -0.05, -0.08, 50.0, 0.0, 0.0
    w = wiz.WizardInputs(vertical_curve=(g1, g2, L, s0, z0))
    assert math.isclose(wiz._z_ref(w, s0), z0)
    assert math.isclose(wiz._z_ref(w, s0 + L), z0 + (g1 + g2) / 2 * L)          # parabola end
    assert math.isclose(wiz._z_ref(w, s0 + L + 40) - wiz._z_ref(w, s0 + L), g2 * 40)   # tangent beyond
    assert math.isclose(wiz._z_ref(w, s0 - 10) - z0, -10 * g1)                 # tangent before
    poly = wiz.WizardInputs(vertical_curve=None, profile=((0.0, 1.0), (100.0, 3.0)))
    assert math.isclose(wiz._z_ref(poly, 50.0), 2.0)


# ------------------------------------------------------------------ tables
def test_groups_partition_the_model_and_ids_resolve(case):
    w, payload, info = case
    groups = _groups(payload)
    main = ["Substructure", "Coping", "Bracing", "Girder", "Dummy Beam", "Dummy Beam2"]
    covered = Counter(e for name in main for e in groups[name]["E_LIST"])
    assert set(covered) == set(map(int, payload["ELEM"])) and max(covered.values()) == 1
    for name, g in groups.items():
        member_nodes = {n for e in g["E_LIST"] for n in payload["ELEM"][str(e)]["NODE"]}
        assert member_nodes <= set(g["N_LIST"]), name
    for v in payload["ELEM"].values():
        assert str(v["SECT"]) in payload["SECT"] and str(v["MATL"]) in payload["MATL"]
        assert all(str(n) in payload["NODE"] for n in v["NODE"])
    assert set(payload) <= set(wiz.TABLE_ORDER)
    for i in range(1, len(w.girder_offsets) + 1):
        assert len(groups[f"10th Point Girder-{i}-i"]["E_LIST"]) == len(groups[f"10th Point Girder-{i}-j"]["E_LIST"]) \
            == 9 * len(w.spans) + (len(w.support_stations) - 1)


def test_span_information(case):
    w, payload, _ = case
    spans = payload["SPAN"]
    assert len(spans) == len(w.girder_offsets) * len(w.spans)
    first = spans["1"]["SPAN_BASE_ITEMS"]
    assert first[0]["SUPPORT"] in (1, 2) and first[-1]["SUPPORT"] in (1, 2)
    assert all(it["SUPPORT"] == 0 for it in first[1:-1])


def test_composite_stage_parts_positive(case):
    _, payload, _ = case
    for row in payload["CSCS"].values():
        for part in row["vPARTINFO"]:
            assert part["PARTINFO_VS"] > 0 and part["PARTINFO_H"] > 0
        assert row["vPARTINFO"][1]["AGE"] == 28 and row["vPARTINFO"][0]["AGE"] == 1


def test_stage_names_and_durations(case):
    _, payload, _ = case
    assert [(v["NAME"], v["DURATION"]) for v in payload["STAG"].values()] == list(wiz.STAGE_DURATIONS)


def test_tapered_section_is_user_dimension_type(case):
    w, payload, _ = case
    cap = payload["SECT"][str(w.sect_cap)]["SECT_BEFORE"]
    assert cap["TYPE"] == 2 and cap["OFFSET_PT"] == "CT"
