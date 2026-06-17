"""
CivilPy
Copyright (C) 2019 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

import requests

import civilpy.structural.midas as midas_module
from civilpy.structural.midas import (
    get_api_key,
    midas_api,
    get_elements,
    get_nodes,
    get_materials,
    get_sections,
    get_static_loads,
    get_units,
    get_supports,
    get_elements_by_section_index,
    get_elements_by_material_index,
    setup_output_directory,
    convert_node_units,
    MidasCivil,
    MidasApiError,
    MidasConnectionError,
    MidasTimeoutError,
    MidasLicenseError,
)


class TestGetApiKey:
    def test_file_not_found_default_path(self):
        with patch("builtins.open", side_effect=FileNotFoundError("no file")):
            get_api_key()
        # No exception raised, prints message

    def test_file_not_found_custom_path(self):
        with patch("builtins.open", side_effect=FileNotFoundError("no file")):
            get_api_key(secrets_path="/nonexistent/path.json")

    def test_reads_key_from_file(self, tmp_path):
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"MIDAS_API_KEY": "test_key_123"}))
        get_api_key(secrets_path=str(secrets_file))
        assert midas_module.MIDAS_API_KEY == "test_key_123"

    def test_reads_key_default_path(self, tmp_path, monkeypatch):
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"MIDAS_API_KEY": "default_key"}))
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        get_api_key()
        assert midas_module.MIDAS_API_KEY == "default_key"


class TestMidasApi:
    def _mock_response(self, data):
        mock = MagicMock()
        mock.json.return_value = data
        return mock

    def test_get_method(self):
        midas_module.MIDAS_API_KEY = "test_key"
        with patch("requests.get", return_value=self._mock_response({"result": "ok"})) as mock_get:
            result = midas_api("GET", "db/node")
            mock_get.assert_called_once()
            assert result == {"result": "ok"}

    def test_post_method(self):
        midas_module.MIDAS_API_KEY = "test_key"
        with patch("requests.post", return_value=self._mock_response({"created": True})) as mock_post:
            result = midas_api("POST", "db/node", {"data": 1})
            mock_post.assert_called_once()

    def test_put_method(self):
        midas_module.MIDAS_API_KEY = "test_key"
        with patch("requests.put", return_value=self._mock_response({"updated": True})) as mock_put:
            result = midas_api("PUT", "db/node", {"data": 1})
            mock_put.assert_called_once()

    def test_delete_method(self):
        midas_module.MIDAS_API_KEY = "test_key"
        with patch("requests.delete", return_value=self._mock_response({"deleted": True})) as mock_del:
            result = midas_api("DELETE", "db/node")
            mock_del.assert_called_once()

    def test_invalid_method(self):
        midas_module.MIDAS_API_KEY = "test_key"
        with pytest.raises(AttributeError):
            midas_api("INVALID", "db/node")

    def test_no_api_key_calls_get_api_key(self):
        midas_module.MIDAS_API_KEY = ""
        with patch("civilpy.structural.midas.get_api_key") as mock_get_key:
            with patch("requests.get", return_value=self._mock_response({})):
                midas_api("GET", "db/node")
            mock_get_key.assert_called_once()


class TestMidasHelpers:
    def setup_method(self):
        midas_module.MIDAS_API_KEY = "test_key"

    def _mock_elements(self):
        return {"ELEM": {"1": {"SECT": 1, "MATL": 2}, "2": {"SECT": 2, "MATL": 1}}}

    def test_get_elements(self):
        with patch("civilpy.structural.midas.midas_api", return_value=self._mock_elements()):
            result = get_elements()
            assert "ELEM" in result

    def test_get_nodes(self):
        with patch("civilpy.structural.midas.midas_api", return_value={"NODE": {}}):
            result = get_nodes()
            assert "NODE" in result

    def test_get_materials(self):
        with patch("civilpy.structural.midas.midas_api", return_value={"MATL": {}}):
            result = get_materials()
            assert "MATL" in result

    def test_get_sections(self):
        with patch("civilpy.structural.midas.midas_api", return_value={"SECT": {}}):
            result = get_sections()
            assert "SECT" in result

    def test_get_static_loads(self):
        with patch("civilpy.structural.midas.midas_api", return_value={"STLD": {}}):
            result = get_static_loads()
            assert "STLD" in result

    def test_get_units(self):
        with patch("civilpy.structural.midas.midas_api", return_value={"UNIT": {}}):
            result = get_units()
            assert "UNIT" in result

    def test_get_supports(self):
        with patch("civilpy.structural.midas.midas_api", return_value={"CONS": {}}):
            result = get_supports()
            assert "CONS" in result

    def test_get_elements_by_section_index(self):
        with patch("civilpy.structural.midas.get_elements", return_value=self._mock_elements()):
            result = get_elements_by_section_index(section_index=1)
            assert "1" in result["ELEM"]
            assert "2" not in result["ELEM"]

    def test_get_elements_by_section_index_none(self):
        with patch("civilpy.structural.midas.get_elements", return_value=self._mock_elements()):
            result = get_elements_by_section_index(section_index=None)
            assert result == {"ELEM": {}}

    def test_get_elements_by_material_index(self):
        with patch("civilpy.structural.midas.get_elements", return_value=self._mock_elements()):
            result = get_elements_by_material_index(material_index=2)
            assert "1" in result["ELEM"]

    def test_get_elements_by_material_index_none(self):
        with patch("civilpy.structural.midas.get_elements", return_value=self._mock_elements()):
            result = get_elements_by_material_index(material_index=None)
            assert result == {"ELEM": {}}

    def test_setup_output_directory_existing(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        setup_output_directory(str(tmp_path))

    def test_setup_output_directory_new(self, tmp_path):
        # Regression: previously mkdir'd the parent (which exists) instead of
        # the output/ subdirectory, raising FileExistsError on the normal path
        setup_output_directory(str(tmp_path))
        assert (tmp_path / "output").is_dir()

    def test_convert_node_units_values(self):
        # 12 inches converted to feet must become 1.0 (regression: the factor
        # was previously divided instead of multiplied, producing 144)
        mock_nodes = {
            "NODE": {"1": {"X": 12.0, "Y": 24.0, "Z": 0.0}}
        }
        mock_units_resp = {"UNIT": {"1": {"DIST": "inch"}}}
        with patch("civilpy.structural.midas.midas_api") as mock_api:
            mock_api.side_effect = [mock_nodes, mock_units_resp, None]
            result = convert_node_units(to_units="feet", in_place=False)
        assert result["Assign"]["1"]["X"] == pytest.approx(1.0)
        assert result["Assign"]["1"]["Y"] == pytest.approx(2.0)

    def test_convert_node_units_to_none_returns_early(self):
        mock_nodes = {"NODE": {"1": {"X": 12.0}}}
        with patch("civilpy.structural.midas.midas_api", return_value=mock_nodes):
            result = convert_node_units(from_units="feet", to_units=None, in_place=False)
        assert result is None

    def test_convert_node_units_both_provided(self):
        mock_nodes = {"NODE": {"1": {"X": 12.0}}}
        with patch("civilpy.structural.midas.midas_api") as mock_api:
            mock_api.side_effect = [mock_nodes, None]
            convert_node_units(from_units="inch", to_units="feet", in_place=True)
            put_body = mock_api.call_args_list[1].args[2]
            assert put_body["Assign"]["1"]["X"] == pytest.approx(1.0)

    def test_convert_node_units_in_place_pushes_to_midas(self):
        mock_nodes = {"NODE": {"1": {"X": 12.0}}}
        mock_units_resp = {"UNIT": {"1": {"DIST": "inch"}}}
        with patch("civilpy.structural.midas.midas_api") as mock_api:
            mock_api.side_effect = [mock_nodes, mock_units_resp, None]
            convert_node_units(to_units="feet", in_place=True)
            assert mock_api.call_args_list[-1].args[0] == "PUT"


def _response(data=None, ok=True, status_code=200):
    mock = MagicMock()
    mock.ok = ok
    mock.status_code = status_code
    payload = {} if data is None else data
    mock.content = json.dumps(payload).encode()
    mock.json.return_value = payload
    mock.text = json.dumps(payload)
    return mock


def _client(**kwargs):
    kwargs.setdefault("base_url", "http://localhost:5000")
    kwargs.setdefault("mapi_key", "test_key")
    return MidasCivil(**kwargs)


class TestMidasCivilInit:
    def test_explicit_credentials_skip_secrets(self):
        midas = MidasCivil(base_url="http://localhost:5000/", mapi_key="abc")
        assert midas.base_url == "http://localhost:5000"  # trailing / stripped
        assert midas.mapi_key == "abc"

    def test_reads_secrets_file(self, tmp_path):
        secrets = tmp_path / "secrets.json"
        secrets.write_text(json.dumps({
            "MIDAS_API_KEY": "from_secrets",
            "MIDAS_BASE_URL": "http://10.0.0.5:5000",
        }))
        midas = MidasCivil(secrets_path=str(secrets))
        assert midas.mapi_key == "from_secrets"
        assert midas.base_url == "http://10.0.0.5:5000"

    def test_default_base_url_when_secrets_lack_it(self, tmp_path):
        secrets = tmp_path / "secrets.json"
        secrets.write_text(json.dumps({"MIDAS_API_KEY": "k"}))
        midas = MidasCivil(secrets_path=str(secrets))
        assert midas.base_url == MidasCivil.DEFAULT_BASE_URL

    def test_missing_key_raises(self, tmp_path):
        with pytest.raises(MidasApiError, match="key missing"):
            MidasCivil(secrets_path=str(tmp_path / "nope.json"))


class TestMidasCivilRequest:
    def test_success_sends_headers_and_url(self):
        midas = _client()
        with patch("requests.request", return_value=_response({"NODE": {}})) as mock_req:
            data = midas.request("get", "db/NODE")
        assert data == {"NODE": {}}
        args, kwargs = mock_req.call_args
        assert args == ("GET", "http://localhost:5000/db/NODE")
        assert kwargs["headers"]["MAPI-Key"] == "test_key"
        assert kwargs["timeout"] == 60          # default request timeout

    def test_request_timeout_override(self):
        midas = _client()
        with patch("requests.request", return_value=_response({})) as mock_req:
            midas.request("post", "doc/ANAL", {}, timeout=600)
        assert mock_req.call_args.kwargs["timeout"] == 600

    def test_analyze_uses_long_timeout(self):
        midas = _client()
        with patch("requests.request", return_value=_response({})) as mock_req:
            midas.analyze()
        assert mock_req.call_args.kwargs["timeout"] == MidasCivil.ANALYSIS_TIMEOUT

    def test_beam_forces_sends_confirmed_shape(self):
        midas = _client()
        with patch("requests.request", return_value=_response({"BeamForce": {}})) as mock_req:
            midas.beam_forces([1, 2, 3], ["DC1(ST)", "HL(MV:all)"])
        arg = mock_req.call_args.kwargs["json"]["Argument"]
        assert arg["NODE_ELEMS"] == {"KEYS": [1, 2, 3]}   # integer ids
        assert "UNIT" in arg and "STYLES" in arg and arg["PARTS"] == ["Part I", "Part J"]

    def test_http_error_raises(self):
        midas = _client()
        resp = _response({"message": "bad"}, ok=False, status_code=404)
        with patch("requests.request", return_value=resp):
            with pytest.raises(MidasApiError, match="HTTP 404"):
                midas.request("GET", "/db/NODE")

    def test_error_payload_raises_even_on_200(self):
        midas = _client()
        resp = _response({"error": {"code": 1, "message": "no model"}})
        with patch("requests.request", return_value=resp):
            with pytest.raises(MidasApiError, match="rejected") as exc_info:
                midas.request("PUT", "/db/NODE", {"Assign": {}})
        assert exc_info.value.response == {"error": {"code": 1, "message": "no model"}}

    def test_unreachable_raises_midas_error(self):
        midas = _client(reconnect_retries=0)
        with patch("requests.request", side_effect=requests.ConnectionError("refused")):
            with pytest.raises(MidasConnectionError, match="Could not reach"):
                midas.request("GET", "/db/NODE")

    def test_ping_true_false(self):
        midas = _client(reconnect_retries=0)
        with patch("requests.request", return_value=_response({"UNIT": {}})):
            assert midas.ping() is True
        with patch("requests.request", side_effect=requests.ConnectionError("down")):
            assert midas.ping() is False


class TestMidasCivilResilience:
    """Connection retry, error taxonomy, license + timeout classification."""

    def test_analysis_timeout_override(self):
        midas = _client(analysis_timeout=1800)
        assert midas.ANALYSIS_TIMEOUT == 1800
        with patch("requests.request", return_value=_response({})) as mock_req:
            midas.analyze()
        assert mock_req.call_args.kwargs["timeout"] == 1800

    def test_connection_error_retries_then_succeeds(self):
        midas = _client(reconnect_retries=2)
        flaky = [requests.ConnectionError("blip"),
                 requests.ConnectionError("blip"),
                 _response({"NODE": {}})]
        with patch("requests.request", side_effect=flaky) as mock_req:
            with patch("time.sleep") as mock_sleep:
                data = midas.request("GET", "/db/NODE")
        assert data == {"NODE": {}}
        assert mock_req.call_count == 3            # two failures, one success
        assert mock_sleep.call_count == 2          # backoff between retries

    def test_connection_error_exhausts_retries(self):
        midas = _client(reconnect_retries=2)
        with patch("requests.request", side_effect=requests.ConnectionError("dead")):
            with patch("time.sleep") as mock_sleep:
                with pytest.raises(MidasConnectionError, match="Could not reach"):
                    midas.request("GET", "/db/NODE")
        assert mock_sleep.call_count == 2          # retried twice before giving up

    def test_timeout_raises_timeout_error_not_retried(self):
        midas = _client(reconnect_retries=3)
        with patch("requests.request", side_effect=requests.Timeout("slow")) as mock_req:
            with pytest.raises(MidasTimeoutError, match="timed out"):
                midas.request("POST", "/doc/ANAL", {})
        assert mock_req.call_count == 1            # timeouts are not retried
        assert issubclass(MidasTimeoutError, MidasConnectionError)

    def test_license_400_raises_license_error(self):
        midas = _client(reconnect_retries=0)
        resp = _response({"message": "Construction stage count exceeds license"},
                         ok=False, status_code=400)
        with patch("requests.request", return_value=resp):
            with pytest.raises(MidasLicenseError, match="license tier"):
                midas.open("C:/models/staged.mcb")

    def test_plain_400_stays_generic(self):
        midas = _client(reconnect_retries=0)
        resp = _response({"message": "bad request"}, ok=False, status_code=400)
        with patch("requests.request", return_value=resp):
            with pytest.raises(MidasApiError, match="HTTP 400") as exc:
                midas.request("GET", "/db/NODE")
        assert not isinstance(exc.value, MidasLicenseError)


class TestMidasCivilTriage:
    """summarize / capability / can_analyze model triage."""

    def _client_with_tables(self, tables):
        """A client whose get_db returns canned ``{TABLE: {...}}`` payloads."""
        midas = _client()
        def fake_get_db(table):
            t = table.upper()
            return {t: tables.get(t, {"message": "no data exist"})}
        midas.get_db = fake_get_db
        return midas

    def test_summarize_counts_ingredients(self):
        midas = self._client_with_tables({
            "NODE": {"1": {}, "2": {}},
            "ELEM": {"1": {"TYPE": "BEAM"}, "2": {"TYPE": "BEAM"}, "3": {"TYPE": "TRUSS"}},
            "SECT": {"1": {"SECTTYPE": "I"}},
            "CONS": {"1": {}},
            "STLD": {"1": {}},
            "MVLD": {},                      # empty -> {"message": ...} -> 0
            "LCOM-GEN": {"1": {}, "2": {}},
        })
        s = midas.summarize()
        assert s["nodes"] == 2
        assert s["elems"] == 3
        assert s["elem_types"] == {"BEAM": 2, "TRUSS": 1}
        assert s["sect_types"] == {"I": 1}
        assert s["supports"] == 1
        assert s["static_loads"] == 1
        assert s["moving_loads"] == 0
        assert s["combinations"] == 2

    def test_grab_handles_missing_table_and_api_error(self):
        midas = _client()
        midas.get_db = lambda table: {"MVLD": {"message": "no data exist"}}
        assert midas._grab("MVLD") == {}
        def boom(table):
            raise MidasApiError("nope")
        midas.get_db = boom
        assert midas._grab("NODE") == {}

    def test_capability_rateable(self):
        s = {"nodes": 10, "elems": 9, "supports": 2,
             "static_loads": 1, "moving_loads": 1}
        can, ll, note = _client().capability(summary=s)
        assert (can, ll) == (True, True)
        assert "rateable" in note

    def test_capability_flags_each_gap(self):
        midas = _client()
        cases = [
            ({"nodes": 0, "elems": 0, "supports": 0, "static_loads": 0, "moving_loads": 0},
             (False, False, "empty model")),
            ({"nodes": 5, "elems": 4, "supports": 0, "static_loads": 1, "moving_loads": 1},
             (False, False, "no supports — won't solve")),
            ({"nodes": 5, "elems": 4, "supports": 2, "static_loads": 0, "moving_loads": 0},
             (False, False, "no load cases")),
            ({"nodes": 5, "elems": 4, "supports": 2, "static_loads": 1, "moving_loads": 0},
             (True, False, None)),
            ({"nodes": 5, "elems": 4, "supports": 2, "static_loads": 0, "moving_loads": 1},
             (True, False, None)),
        ]
        for summary, (can, ll, note) in cases:
            res = midas.capability(summary=summary)
            assert (res[0], res[1]) == (can, ll), summary
            if note:
                assert res[2] == note

    def test_can_analyze_uses_capability(self):
        midas = self._client_with_tables({
            "NODE": {"1": {}}, "ELEM": {"1": {"TYPE": "BEAM"}},
            "CONS": {"1": {}}, "STLD": {"1": {}},
        })
        assert midas.can_analyze() is True


class TestMidasCivilBeamForceValidation:
    def test_duplicate_columns_detects_aliasing(self):
        resp = {"BeamForce": {"HEAD": ["Elem", "Axial", "Shear-z", "Axial"],
                              "DATA": []}}
        assert MidasCivil.duplicate_columns(resp) == ["Axial"]

    def test_duplicate_columns_clean_table(self):
        resp = {"BeamForce": {"HEAD": ["Elem", "Axial", "Shear-z"], "DATA": []}}
        assert MidasCivil.duplicate_columns(resp) == []
        assert MidasCivil.duplicate_columns("not a dict") == []

    def test_beam_forces_warns_on_duplicate_headers(self):
        midas = _client()
        dup = _response({"BeamForce": {"HEAD": ["Axial", "Axial"], "DATA": []}})
        with patch("requests.request", return_value=dup):
            with pytest.warns(UserWarning, match="duplicate column headers"):
                midas.beam_forces([1, 2], ["DC(ST)"])

    def test_beam_forces_no_warning_when_clean(self):
        import warnings as _w
        midas = _client()
        clean = _response({"BeamForce": {"HEAD": ["Elem", "Axial"], "DATA": []}})
        with patch("requests.request", return_value=clean):
            with _w.catch_warnings():
                _w.simplefilter("error")        # any warning fails the test
                midas.beam_forces([1], ["DC(ST)"], validate=True)

    def test_beam_forces_validate_false_skips_check(self):
        import warnings as _w
        midas = _client()
        dup = _response({"BeamForce": {"HEAD": ["Axial", "Axial"], "DATA": []}})
        with patch("requests.request", return_value=dup):
            with _w.catch_warnings():
                _w.simplefilter("error")        # would-be-duplicate, but unchecked
                resp = midas.beam_forces([1], ["DC(ST)"], validate=False)
        assert "BeamForce" in resp

    def test_repr_shows_base_url(self):
        assert repr(_client()) == "<MidasCivil http://localhost:5000>"


class TestMidasCivilDb:
    def setup_method(self):
        self.midas = _client()

    def test_get_db_uppercases_table(self):
        with patch("requests.request", return_value=_response({"ELEM": {}})) as mock_req:
            self.midas.get_db("elem")
        assert mock_req.call_args.args[1].endswith("/db/ELEM")

    def test_put_db_wraps_assign(self):
        with patch("requests.request", return_value=_response({})) as mock_req:
            self.midas.put_db("NODE", {"1": {"X": 0, "Y": 0, "Z": 0}})
        assert mock_req.call_args.kwargs["json"] == {
            "Assign": {"1": {"X": 0, "Y": 0, "Z": 0}}
        }

    def test_delete_db_builds_id_path(self):
        with patch("requests.request", return_value=_response({})) as mock_req:
            self.midas.delete_db("NODE", ids=[1, 2, 3])
        assert mock_req.call_args.args == ("DELETE", "http://localhost:5000/db/NODE/1,2,3")

    def test_delete_db_without_ids(self):
        with patch("requests.request", return_value=_response({})) as mock_req:
            self.midas.delete_db("NODE")
        assert mock_req.call_args.args[1].endswith("/db/NODE")

    def test_typed_getters_hit_expected_tables(self):
        expected = {
            "nodes": "NODE", "elements": "ELEM", "materials": "MATL",
            "sections": "SECT", "supports": "CONS", "static_loads": "STLD",
            "groups": "GRUP", "load_combinations": "LCOM-GEN", "units": "UNIT",
        }
        for method, table in expected.items():
            with patch("requests.request", return_value=_response({table: {}})) as mock_req:
                getattr(self.midas, method)()
            assert mock_req.call_args.args[1].endswith(f"/db/{table}"), method

    def test_set_units_defaults_to_kips_ft(self):
        with patch("requests.request", return_value=_response({})) as mock_req:
            self.midas.set_units()
        body = mock_req.call_args.kwargs["json"]
        assert body["Assign"]["1"]["FORCE"] == "KIPS"
        assert body["Assign"]["1"]["DIST"] == "FT"


class TestMidasCivilDocAndResults:
    def setup_method(self):
        self.midas = _client()

    def test_doc_ops_post_expected_endpoints(self):
        expected = {
            "new": ("/doc/NEW", {}),
            "save": ("/doc/SAVE", {}),
            "analyze": ("/doc/ANAL", {}),
        }
        for method, (endpoint, body) in expected.items():
            with patch("requests.request", return_value=_response({})) as mock_req:
                getattr(self.midas, method)()
            assert mock_req.call_args.args == ("POST", f"http://localhost:5000{endpoint}"), method
            assert mock_req.call_args.kwargs["json"] == body, method

    def test_doc_ops_with_path_argument(self):
        expected = {
            "open": "/doc/OPEN",
            "save_as": "/doc/SAVEAS",
            "import_file": "/doc/IMPORT",
            "export_file": "/doc/EXPORT",
        }
        for method, endpoint in expected.items():
            with patch("requests.request", return_value=_response({})) as mock_req:
                getattr(self.midas, method)("C:/models/bridge.mcb")
            assert mock_req.call_args.args[1].endswith(endpoint), method
            assert mock_req.call_args.kwargs["json"] == {
                "Argument": "C:/models/bridge.mcb"
            }, method

    def test_result_table_assembles_argument(self):
        with patch("requests.request", return_value=_response({})) as mock_req:
            self.midas.result_table(
                "BeamForce", table_type="BEAMFORCE",
                components=["Elem", "Load", "Moment-y"],
                node_elems={"KEYS": ["1to20"]},
                load_case_names=["DL(CB)"],
                parts=["PartI"],
                unit={"FORCE": "kips"},
                styles={"FORMAT": "Fixed"},
            )
        assert mock_req.call_args.args == ("POST", "http://localhost:5000/post/TABLE")
        argument = mock_req.call_args.kwargs["json"]["Argument"]
        assert argument == {
            "TABLE_NAME": "BeamForce",
            "TABLE_TYPE": "BEAMFORCE",
            "UNIT": {"FORCE": "kips"},
            "STYLES": {"FORMAT": "Fixed"},
            "COMPONENTS": ["Elem", "Load", "Moment-y"],
            "NODE_ELEMS": {"KEYS": ["1to20"]},
            "LOAD_CASE_NAMES": ["DL(CB)"],
            "PARTS": ["PartI"],
        }

    def test_result_table_minimal(self):
        with patch("requests.request", return_value=_response({})) as mock_req:
            self.midas.result_table("Reaction")
        assert mock_req.call_args.kwargs["json"] == {
            "Argument": {"TABLE_NAME": "Reaction"}
        }