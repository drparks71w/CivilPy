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