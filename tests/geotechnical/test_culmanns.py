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

import pytest
from civilpy.geotech.culmanns import (
    CulmannsMethod,
    find_key_for_value_in_tuple_range,
)
from civilpy.general import units
from civilpy.structural.arema import CooperE80EqStrip
import numpy as np
import pandas as pd

coopers_e80 = CooperE80EqStrip()

# Sample data to use in tests
sample_data = {
    "soil_unit_weight": 117.7 * units("lbf/ft^3"),
    "soil_angle_int_friction": 29.8 * units("degrees"),
    "angle_back_wall_with_horizontal": 0 * units("degrees"),
    "angle_of_wall_friction_delta": 0 * units("degrees"),
    "angle_of_wall_friction_gamma": 90 * units("degrees"),
    "load_scale": 2.9059 * units("kips/ft"),
    "wall_height": 19.5,
    "soil_height_above_wall": 4.4,
    "num_slices": 19,
    "total_length": 38,
    "track_offset": 2,
    "coordinates_list": {
        "A": (0, 23.9, "LS1"),
        "B": (0, 0, None),
        "C_1": (2.0, 23.9, "LS1"),
        "C_2": (4.0, 23.9, "LS1"),
        "C_3": (6.0, 23.9, "LS1"),
        "C_4": (8.0, 23.9, "LS1"),
        "C_5": (10.0, 23.9, "LS1"),
        "C_6": (12.0, 23.9, "LS1"),
        "C_7": (14.0, 23.9, "LS1"),
        "C_8": (16.0, 23.9, "LS1"),
        "C_9": (18.0, 23.9, "LS1"),
        "C_10": (20.0, 23.9, "LS1"),
        "C_11": (22.0, 23.9, None),
        "C_12": (24.0, 23.9, None),
        "C_13": (26.0, 23.9, "LS2"),
        "C_14": (28.0, 23.9, "LS2"),
        "C_15": (30.0, 23.9, "LS2"),
        "C_16": (32.0, 23.9, "LS2"),
        "C_17": (34.0, 23.9, "LS2"),
        "C_18": (36.0, 23.9, "LS2"),
        "C_19": (38.0, 23.9, "LS2"),
    },
}
culmans_obj = CulmannsMethod(**sample_data)


def test_find_key_for_value_in_tuple_range():
    result = find_key_for_value_in_tuple_range(coopers_e80.linear_loads, 36.0)
    expected = "LS2"
    assert result == expected


class TestCulmansMethod:
    def test_init(self):
        assert culmans_obj.soil_unit_weight == sample_data["soil_unit_weight"]

    def test_calculate_a_i(self):
        x_val, y_val, _ = sample_data["coordinates_list"]["C_1"]
        result = culmans_obj.calculate_a_i(x_val, y_val)
        expected_result = 23.9835 * units.foot
        assert result == expected_result

    def test_calculate_c_i(self):
        keys = list(sample_data["coordinates_list"].keys())
        result = culmans_obj.calculate_c_i("C_1", keys, sample_data["coordinates_list"])
        assert isinstance(result, units.Quantity)

    def test_calculate_c_i_not_first(self):
        keys = list(sample_data["coordinates_list"].keys())
        result = culmans_obj.calculate_c_i("C_2", keys, sample_data["coordinates_list"])
        assert isinstance(result, units.Quantity)

    def test_calculate_b_i(self):
        keys = list(sample_data["coordinates_list"].keys())
        x_val, y_val, _ = sample_data["coordinates_list"]["C_1"]
        result = culmans_obj.calculate_b_i("C_1", keys, sample_data["coordinates_list"], x_val, y_val)
        assert isinstance(result, units.Quantity)

    def test_calculate_b_i_not_first(self):
        keys = list(sample_data["coordinates_list"].keys())
        x_val, y_val, _ = sample_data["coordinates_list"]["C_2"]
        result = culmans_obj.calculate_b_i("C_2", keys, sample_data["coordinates_list"], x_val, y_val)
        assert isinstance(result, units.Quantity)

    def test_calculate_s_i(self):
        a_i = 23.9835 * units.foot
        b_i = 2.0 * units.foot
        c_i = 23.9835 * units.foot
        result = culmans_obj.calculate_s_i(a_i, b_i, c_i)
        assert isinstance(result, units.Quantity)

    def test_calculate_A_i(self):
        s_i = 25.0 * units.foot
        a_i = 23.9835 * units.foot
        b_i = 2.0 * units.foot
        c_i = 23.9835 * units.foot
        result = culmans_obj.calculate_A_i(s_i, a_i, b_i, c_i)
        assert isinstance(result, units.Quantity)

    def test_calculate_A_i_degenerate_triangle(self):
        # Degenerate triangle: numpy returns NaN (not ValueError) for negative sqrt
        s_i = 1.0 * units.foot
        a_i = 23.9835 * units.foot
        b_i = 2.0 * units.foot
        c_i = 23.9835 * units.foot
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = culmans_obj.calculate_A_i(s_i, a_i, b_i, c_i)
        import math
        assert math.isnan(result.magnitude)

    def test_calculate_x_cgi(self):
        result = culmans_obj.calculate_x_cgi(2.0, 4.0)
        assert isinstance(result, units.Quantity)

    def test_calculate_y_cgi(self):
        result = culmans_obj.calculate_y_cgi(10.0, 20.0)
        assert isinstance(result, units.Quantity)

    def test_calculate_running_total(self):
        values = [1.0 * units.foot, 2.0 * units.foot, 3.0 * units.foot]
        result = culmans_obj.calculate_running_total(values)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_calculate_w_i(self):
        A_i = 10.0 * units.foot**2
        soil_unit_weight = 117.7 * units("lbf/ft^3")
        result = culmans_obj.calculate_w_i(A_i, soil_unit_weight)
        assert isinstance(result, units.Quantity)

    def test_calculate_cumulative_weights(self):
        values = [100.0 * units("lbf/ft"), 200.0 * units("lbf/ft")]
        result = culmans_obj.calculate_cumulative_weights(values)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_calculate_ll_surcharge(self):
        b_i = 2.0 * units.foot
        result = culmans_obj.calculate_ll_surcharge(b_i)
        assert isinstance(result, units.Quantity)

    def test_sort_keys(self):
        result = culmans_obj.sort_keys(["C_3", "C_1", "C_2"])
        assert result == ["C_1", "C_2", "C_3"]

    def test_generate_spreadsheet(self):
        df = culmans_obj.generate_spreadsheet(
            sample_data["coordinates_list"],
            sample_data["soil_unit_weight"],
            sample_data["load_scale"],
            sample_data["soil_angle_int_friction"],
            sample_data["angle_back_wall_with_horizontal"],
            sample_data["angle_of_wall_friction_delta"],
        )
        assert isinstance(df, pd.DataFrame)

    def test_plot_results(self):
        from unittest.mock import patch
        import matplotlib
        matplotlib.use("Agg")
        with patch("matplotlib.pyplot.show"):
            culmans_obj.plot_results()
