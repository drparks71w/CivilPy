#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""The ODOT Midas bridge workflow.

These run entirely against a fake client: the point is to pin the *bodies*
this module sends, because every field name here was paid for with a
"Wrong Field" round trip against a live Civil NX and there is nothing in
the error to tell you which field was wrong.
"""

import pytest

from civilpy.state.ohio.dot import (
    GirderModel,
    add_moving_load_case,
    check_nonzero_envelopes,
    generate_lane_load,
    moving_load_envelopes,
    set_moving_load_control,
)


class FakeClient:
    """Records what would be sent; serves back what was stored."""

    ANALYSIS_TIMEOUT = 600

    def __init__(self, tables=None):
        self.tables = {k: dict(v) for k, v in (tables or {}).items()}
        self.sent = []
        self.deleted = []
        self.result = None

    def request(self, method, command, body=None, **kw):
        table = command.strip("/").split("/")[1]
        if method == "GET":
            return {table.upper(): self.tables.get(table.upper(), {})} \
                if self.tables.get(table.upper()) else {"message": ""}
        if method == "DELETE":
            self.deleted.append(command)
            return {}
        self.sent.append((method, table, body))
        if body and "Assign" in body:
            self.tables.setdefault(table.upper(), {}).update(body["Assign"])
        return {}

    def result_table(self, *a, **kw):
        return self.result

    def last(self, table):
        for method, t, body in reversed(self.sent):
            if t.upper() == table.upper():
                return body["Assign"]
        raise AssertionError(f"nothing sent to {table}")


@pytest.fixture
def girder():
    return GirderModel(designation="CB27-48", family="box", span_ft=70.0,
                       n_beams=3,
                       elements_by_line={0: [1, 2], 1: [3, 4], 2: [5, 6]})


class TestTrafficLanes:
    def test_one_lane_per_girder_line(self, girder):
        c = FakeClient()
        names = generate_lane_load(c, girder)
        assert names == ["Lane1", "Lane2", "Lane3"]
        assert len(c.last("llan")) == 3

    def test_lane_body_matches_the_verified_schema(self, girder):
        """Name lives at COMMON.LL_NAME, not top level; LOAD_DIST is
        'LANE'; items are ELEM/ECC/FACT/SPAN_START/ECCEN_VERT_LOAD/CENT_F."""
        c = FakeClient()
        generate_lane_load(c, girder)
        lane = c.last("llan")["1"]
        assert set(lane) == {"COMMON", "LANE_ITEMS"}
        assert "LANE_NAME" not in lane
        assert lane["COMMON"]["LL_NAME"] == "Lane1"
        assert lane["COMMON"]["LOAD_DIST"] == "LANE"
        item = lane["LANE_ITEMS"][0]
        assert set(item) == {"ELEM", "ECC", "FACT", "SPAN_START",
                             "ECCEN_VERT_LOAD", "CENT_F"}
        # CENT_F must be strictly inside (0, 1) -- 0.0 is rejected live
        assert 0.0 < item["CENT_F"] < 1.0

    def test_widths_convert_feet_to_inches(self, girder):
        c = FakeClient()
        generate_lane_load(c, girder, width_ft=12.0, wheel_spacing_ft=6.0)
        common = c.last("llan")["1"]["COMMON"]
        assert common["WIDTH"] == 144.0
        assert common["WHEEL_SPACE"] == 72.0

    def test_requires_elements(self):
        with pytest.raises(ValueError, match="no girder elements"):
            generate_lane_load(FakeClient())


class TestMovingLoadCases:
    def test_case_body_matches_the_manual(self):
        """COMB_OPTION is the STRING 'INDEPENDENT' and the lane counts are
        MIN_LOADED_LANE / MAX_LOADED_LANE (db/MVLD manual)."""
        c = FakeClient({"MVHL": {"1": {"VEHICLE_LOAD_NAME": "EV3"}}})
        add_moving_load_case(c, ["Lane1"])
        case = c.last("mvld")["1"]
        assert case["LCNAME"] == "EV3"
        d = case["DEFAULT"]
        assert d["COMB_OPTION"] == "INDEPENDENT"
        assert isinstance(d["COMB_OPTION"], str)
        sub = d["SUB_LOAD_DATAS"][0]
        assert "MIN_NUM" not in sub and "MAX_NUM" not in sub
        assert sub["MIN_LOADED_LANE"] == 1
        assert sub["MAX_LOADED_LANE"] == 1
        assert sub["VEHICLE_TYPE"] == "VL"
        assert sub["LANE_NAMES"] == ["Lane1"]

    def test_multiple_presence_factors_sent_in_full(self):
        c = FakeClient({"MVHL": {"1": {"VEHICLE_LOAD_NAME": "SU4"}}})
        add_moving_load_case(c, ["Lane1", "Lane2"])
        d = c.last("mvld")["1"]["DEFAULT"]
        assert d["SCALE_FACTORS"] == [1.2, 1.0, 0.85, 0.65, 0.65, 0.65]
        assert d["SUB_LOAD_DATAS"][0]["MAX_LOADED_LANE"] == 2

    def test_defaults_to_every_vehicle_in_the_model(self):
        c = FakeClient({"MVHL": {
            "1": {"VEHICLE_LOAD_NAME": "2F1"},
            "2": {"VEHICLE_LOAD_NAME": "EV2"}}})
        cases = add_moving_load_case(c, "Lane1")
        assert set(cases) == {"2F1", "EV2"}

    def test_errors_when_no_vehicles_loaded(self):
        with pytest.raises(ValueError, match="midas_ohio_legal_loads"):
            add_moving_load_case(FakeClient(), "Lane1")


class TestMovingLoadControl:
    def test_control_body(self):
        c = FakeClient()
        set_moving_load_control(c)
        body = c.last("MVCT")["1"]
        assert body["METHOD"] == "EXACT"
        assert body["POINT"] == "INF"
        assert body["FRAME"] == "AXIAL"
        assert body["PLATE"] == "NODAL"


class TestEnvelopes:
    def _resp(self, rows):
        return {"BeamForce": {"HEAD": ["Elem", "Load", "Moment-y"],
                              "DATA": rows}}

    def test_strips_the_moving_load_suffix(self, monkeypatch):
        c = FakeClient()
        c.result = self._resp([])
        monkeypatch.setattr(
            "civilpy.structural.midas.parse_result_table",
            lambda resp: [{"Elem": 7, "Load": "SU5(MV:all)", "Moment-y": -120.0},
                          {"Elem": 8, "Load": "SU5(MV:all)", "Moment-y": 95.0},
                          {"Elem": 7, "Load": "EV3(MV:all)", "Moment-y": 200.0}])
        env = moving_load_envelopes(c)
        assert env == {"SU5": 120.0, "EV3": 200.0}   # absolute max per case

    def test_flags_vehicles_that_produced_no_load(self):
        env = {"SU4": 1000.0, "EV3": 0.0}
        assert check_nonzero_envelopes(env) == ["EV3"]
        assert check_nonzero_envelopes(env, ["SU4", "EV3", "Type 3"]) == [
            "EV3", "Type 3"]
