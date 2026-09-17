"""Permit route screening (civilpy.state.ohio.DOT.permit_route) — no network:
the router, the road inventory and the bridge source are all stubbed."""
import math
from unittest.mock import patch

import pytest

from civilpy.state.ohio.DOT import permit_route as pr
from civilpy.state.ohio.DOT.permit_route import BridgeRecord, FeatureRecord


# ── tokens, LRS ids, names ───────────────────────────────────────────────────
def test_route_tokens_from_refs_and_names():
    assert pr.route_tokens("US 36; SR 37", "State Route 37 East") == {"2:36", "3:37"}
    assert pr.route_tokens("I 71", "") == {"1:71"}
    assert pr.route_tokens("", "Interstate 70") == {"1:70"}
    assert pr.route_tokens("RAMP FROM RA 25609 TO IR 71", "") == {"1:71"}
    assert pr.route_tokens("", "Wilson Road") == set()


def test_nlf_id_parsing():
    p = pr.parse_nlf("SFRAIR00071**C")
    assert (p["jurisdiction"], p["county"], p["type"], p["number"], p["cardinal"]) == \
        ("S", "FRA", "IR", 71, "C")
    assert pr.nlf_base("SFRAIR00071**N") == pr.nlf_base("SFRAIR00071**C") == "SFRAIR00071**"
    assert pr.nlf_token("TDELTR00056**C") == "5:56"
    assert pr.nlf_token("SFRARA25507**C") is None          # ramps have no B.RT type
    assert pr.parse_nlf("99") is None and pr.parse_nlf("") is None


def test_bridge_route_tokens_and_names():
    assert pr.bridge_route_tokens([("1", "0071"), ("4", "25"), (None, "9"), ("3", "")]) == {"1:71", "4:25"}
    assert pr.names_match("Wilson Rd.", "Wilson Road")
    assert pr.names_match("SB I-71", "I-71 NB")
    assert not pr.names_match("Cooke Rd.", "Morse Road")
    assert not pr.names_match("", "Morse Road")


# ── geometry ─────────────────────────────────────────────────────────────────
def test_polyline_nearest_and_heading():
    frame = pr.LocalFrame(40.0, -83.0)
    line = pr.Polyline([frame.xy(40.0, -83.0), frame.xy(40.0, -82.99)])   # due east, ~853 m
    assert line.length == pytest.approx(853, abs=5)
    d, s, h = line.nearest(*frame.xy(40.0001, -82.995))
    assert d == pytest.approx(11.06, abs=0.1) and s == pytest.approx(426, abs=3)
    assert abs(h) < 1e-6 and pr.heading_diff(h, math.pi) < 1e-6      # undirected


# ── checks ───────────────────────────────────────────────────────────────────
def test_status_and_checks():
    assert pr.status_for(None) == "unknown" and pr.status_for(0.99) == "fail"
    assert pr.status_for(1.05) == "marginal" and pr.status_for(1.1) == "pass"
    assert pr.vertical_check(99.9, 13.5, "x") is None
    v = pr.vertical_check(14.0, 13.5, "x")
    assert v.ratio == pytest.approx(14 / 13.5) and "+6 in" in v.note
    assert pr.vertical_check(None, 13.5, "x").ratio is None
    assert pr.width_check(24.0, 8.5, "x").ratio == pytest.approx(24 / 8.5)
    assert pr.width_check(99.9, 8.5, "x").ratio is None        # sentinel
    assert pr.width_check(135.0, 8.5, "x").ratio == pytest.approx(135 / 8.5)   # 8 lanes is real


def test_posting_labels():
    assert pr.posting_label("PO") == ("open (not posted)", False)
    assert pr.posting_label("PP-T") == ("posted", True)
    assert pr.posting_label("C") == ("closed", True)
    assert pr.posting_label("5") == ("open (at or above legal loads)", False)
    assert pr.posting_label("3")[1] is True


def test_rating_factor_paths():
    known = pr.rating_factor("SU6", {"SU6": (1.23, "B.EP.02")}, "HS20", 1.5, 80.0, False)
    assert (known.ratio, known.estimated) == (1.23, False)
    design = pr.rating_factor("HS20", {}, "HS20M", 1.42, 80.0, False)
    assert design.ratio == 1.42 and "HS20M" in design.source
    est = pr.rating_factor("SU7", {"SU6": (1.20, "B.EP.02")}, None, None, 80.0, False)
    assert est.estimated and 0.9 < est.ratio < 1.20 and "simple-span M+" in est.note
    # the design-load RF joins the knowns for an estimate
    est2 = pr.rating_factor("SU7", {}, "HS20", 1.6, 80.0, False)
    assert est2.estimated and est2.ratio is not None
    assert pr.rating_factor("SU7", {}, None, None, 80.0, False).ratio is None
    assert pr.rating_factor("SU7", {"SU6": (1.2, "x")}, None, None, 12.0, False).ratio is None


def test_vehicle_catalog():
    names = {v["name"] for v in pr.list_vehicles()}
    assert {"HL-93", "Type 3S2", "SU7", "EV3", "5C1", "S-PL65T"} <= names
    assert set(pr.VEHICLES) == names


# ── the screen with a canned route and a fake source ────────────────────────
ROUTE = {"coords": [[40.0, -83.00], [40.0, -82.99], [40.0, -82.98]],
         "distance_m": 1706.0, "duration_s": 120.0, "source": "test",
         "steps": [{"name": "State Route 99", "ref": "SR 99", "distance_m": 1706.0,
                    "d0": 0.0, "d1": 1706.0}]}


class FakeSource:
    def __init__(self, bridges):
        self.bridges = bridges
        self.hydrated = []

    def bridges_in(self, bbox):
        return list(self.bridges)

    def by_sfn(self, sfn):
        return next((b for b in self.bridges if b.sfn == sfn), None)

    def hydrate(self, b):
        self.hydrated.append(b.sfn)
        return b


def corridor():
    on = BridgeRecord("0000001", 40.0, -82.995, name="FRA-00099-0123", max_span_ft=80.0,
                      curb_width_ft=26.0, design_load="HS20", design_opr_rf=1.6,
                      known_rfs={"SU6": (1.2, "B.EP.02 (SU6)")}, posting_code="PO",
                      features=[FeatureRecord("H", "C", "SR 99", "SFRASR00099**C", 99.9, 26.0, [("3", "0099")]),
                                FeatureRecord("W", "B", "BIG RUN")])
    over = BridgeRecord("0000002", 40.0001, -82.985, max_span_ft=60.0, posting_code="PP",
                        features=[FeatureRecord("H", "C", "CR 12", "CFRACR00012**C", routes=[("4", "12")]),
                                  FeatureRecord("H", "B", "SR 99", "SFRASR00099**C", 14.0, 30.0)])
    far = BridgeRecord("0000003", 40.0036, -82.99)          # 400 m north
    return on, over, far


def test_screen_scores_each_bridge():
    on, over, far = corridor()
    src = FakeSource([on, over, far])
    with patch.object(pr, "roads_near", return_value=[]):
        out = pr.screen_route((40.0, -83.0), (40.0, -82.98), "SU7", 13.5, 8.5, source=src,
                              router=lambda s, e: ROUTE)
    assert src.hydrated == ["0000001", "0000002"]           # only the hits
    by = {b["sfn"]: b for b in out["bridges"]}
    assert set(by) == {"0000001", "0000002"}
    a, b = by["0000001"], by["0000002"]
    assert (a["relation"], a["matched_by"]) == ("over", "route")
    kinds = {c["kind"]: c for c in a["checks"]}
    assert kinds["load"]["estimated"] and kinds["load"]["ratio"] < 1.2
    assert "vertical" not in kinds and kinds["width"]["ratio"] == pytest.approx(26 / 8.5, abs=1e-3)
    assert a["posting"]["flag"] is False
    assert (b["relation"], b["matched_by"]) == ("under", "route")
    vk = {c["kind"]: c for c in b["checks"]}
    assert vk["vertical"]["ratio"] == pytest.approx(14 / 13.5, abs=1e-3) and "load" not in vk
    assert b["posting"] is None
    assert out["worst"]["sfn"] == "0000002" and out["counts"]["fail"] == 0
    assert out["matching"]["by"]["route"] == 2


def test_lrs_conflation_wins_and_flags_neighbours():
    on, over, far = corridor()
    # a third structure 20 m off the line carrying a different, fully-coded road
    neighbour = BridgeRecord("0000004", 40.00018, -82.9905,
                             features=[FeatureRecord("H", "C", "Main St", "MFRAMR00500**C", routes=[]),
                                       FeatureRecord("H", "B", "Elm St", "MFRAMR00600**C")])
    seg = {"nlf_id": "SFRASR00099**C", "street": "SR 99", "route_type": "SR", "route_nbr": "00099",
           "divided": False, "truck_route": True,
           "paths": [[[40.0, -83.0], [40.0, -82.98]]]}
    with patch.object(pr, "roads_near", return_value=[seg]):
        out = pr.screen_route((40.0, -83.0), (40.0, -82.98), "SU6", 13.5, 8.5,
                              source=FakeSource([on, over, neighbour]), router=lambda s, e: ROUTE)
    by = {b["sfn"]: b for b in out["bridges"]}
    assert by["0000001"]["matched_by"] == "lrs" and by["0000001"]["road_lrs"] == "SFRASR00099**C"
    assert by["0000002"]["matched_by"] == "lrs" and by["0000002"]["relation"] == "under"
    assert by["0000004"]["relation"] == "adjacent" and by["0000004"]["checks"] == []
    assert out["matching"]["adjacent"] == 1 and out["bridge_count"] == 3
    assert sum(out["counts"].values()) == 2                  # adjacent is not tallied


def test_bridge_name_fills_a_missing_carried_feature():
    b = BridgeRecord("0000009", 40.0, -82.995, name="FRA-00099-1234", max_span_ft=50.0,
                     design_load="HL93", design_opr_rf=1.4,
                     features=[FeatureRecord("H", "B", "Ramp A", "SFRARA25000**C", 15.0, 24.0)])
    with patch.object(pr, "roads_near", return_value=[]):
        out = pr.screen_route((40.0, -83.0), (40.0, -82.98), "HL-93", 13.5, 8.5,
                              source=FakeSource([b]), router=lambda s, e: ROUTE)
    r = out["bridges"][0]
    assert (r["relation"], r["matched_by"]) == ("over", "name")
    assert next(c for c in r["checks"] if c["kind"] == "load")["ratio"] == 1.4


def test_unknown_vehicle_rejected():
    with pytest.raises(ValueError):
        pr.screen_route((40, -83), (40, -82), "Bigfoot", source=FakeSource([]), router=lambda s, e: ROUTE)


# ── TIMS record mapping (a real row, no network) ────────────────────────────
TIMS_ROW = {"SFN": "2102374", "STR_LOC_CARRIED": "I-71 NB", "NLFID": "SDELIR00071**C",
            "INVENT_ON_UND_CD": "1", "INVENT_FEAT": "TR 105 (PLUMB RD.)", "LATITUDE_DD": 40.209175,
            "LONGITUDE_DD": -82.930444, "DESIGN_LOAD_CD": "6", "RAT_OPR_LOAD_FACT": "1700",
            "BRG_POSTING": "5", "MAX_SPAN_LEN": 35.0, "BRG_RDW_WD": 64.0, "MIN_HORIZ_CLR_C": 41.0,
            "MINVRT_UNDCLR_C": 13.9, "ROUTE_TYPE": "IR", "ROUTE_NBR": "00071",
            "YR_BUILT": -331516800000, "TYPE_SERV1_CD": "1", "TYPE_SERV2_CD": "1"}


def test_tims_record_mapping():
    b = pr.TIMSBridgeSource.to_record(TIMS_ROW)
    assert (b.sfn, b.design_load, b.design_opr_rf, b.max_span_ft, b.curb_width_ft) == \
        ("2102374", "HS20M", 1.7, 35.0, 64.0)
    assert b.year_built == 1959 and b.posting_code == "5"
    carried, under = b.features
    assert carried.carried and carried.lrs_id == "SDELIR00071**C" and carried.routes == [("1", "00071")]
    assert under.under and under.is_highway and under.min_vert_clearance_ft == 13.9
    assert under.lrs_id == ""                                 # the inventory route is the one on top
    # 9999 / 0 are fillers
    assert pr.TIMSBridgeSource.to_record({**TIMS_ROW, "RAT_OPR_LOAD_FACT": "9999",
                                          "MINVRT_UNDCLR_C": 0.0}).design_opr_rf is None
    assert pr.TIMSBridgeSource.to_record({**TIMS_ROW, "LATITUDE_DD": None}) is None
