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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sympy import Integer

from civilpy.structural.beam_bending import (
    Beam,
    PointLoadV,
    PointLoadH,
    DistributedLoadV,
    DistributedLoadH,
    PointTorque,
)


class TestLoadTypes:
    def test_point_load_v(self):
        load = PointLoadV(-20, 3)
        assert load.force == -20
        assert load.coord == 3

    def test_point_load_h(self):
        load = PointLoadH(10, 5)
        assert load.force == 10
        assert load.coord == 5

    def test_distributed_load_v(self):
        load = DistributedLoadV("10*x+5", (0, 2))
        assert load.expr == "10*x+5"
        assert load.span == (0, 2)

    def test_distributed_load_h(self):
        load = DistributedLoadH("5", (1, 3))
        assert load.span == (1, 3)

    def test_point_torque(self):
        torque = PointTorque(30, 4)
        assert torque.torque == 30
        assert torque.coord == 4


class TestBeamInit:
    def test_default_span(self):
        b = Beam()
        assert b.length == 10

    def test_custom_span(self):
        b = Beam(20)
        assert b.length == 20

    def test_length_setter_valid(self):
        b = Beam()
        b.length = 15
        assert b.length == 15

    def test_length_setter_invalid(self):
        b = Beam()
        with pytest.raises(ValueError):
            b.length = -5

    def test_pinned_support_setter_valid(self):
        b = Beam(10)
        b.pinned_support = 3
        assert b.pinned_support == 3

    def test_pinned_support_setter_invalid(self):
        b = Beam(10)
        with pytest.raises(ValueError):
            b.pinned_support = 15

    def test_rolling_support_setter_valid(self):
        b = Beam(10)
        b.rolling_support = 7
        assert b.rolling_support == 7

    def test_rolling_support_setter_invalid(self):
        b = Beam(10)
        with pytest.raises(ValueError):
            b.rolling_support = 20


class TestBeamReactions:
    def test_simple_point_load(self):
        b = Beam(9)
        b.pinned_support = 2
        b.rolling_support = 7
        b.add_loads([PointLoadV(-20, 3)])
        F_Ax, F_Ay, F_By = b.get_reaction_forces()
        assert abs(F_Ax) < 1e-6
        assert abs(F_Ay - 16.0) < 1e-3
        assert abs(F_By - 4.0) < 1e-3

    def test_horizontal_load(self):
        b = Beam(10)
        b.pinned_support = 2
        b.rolling_support = 8
        b.add_loads([PointLoadH(10, 5)])
        F_Ax, F_Ay, F_By = b.get_reaction_forces()
        assert abs(F_Ax + 10.0) < 1e-3

    def test_distributed_load(self):
        b = Beam(10)
        b.pinned_support = 2
        b.rolling_support = 8
        b.add_loads([DistributedLoadV("-10", (0, 10))])
        F_Ax, F_Ay, F_By = b.get_reaction_forces()
        assert abs(F_Ay + F_By - 100) < 1e-3

    def test_distributed_load_h(self):
        b = Beam(10)
        b.pinned_support = 2
        b.rolling_support = 8
        b.add_loads([DistributedLoadH("5", (0, 10))])
        F_Ax, F_Ay, F_By = b.get_reaction_forces()
        assert abs(F_Ax + 50) < 1e-3

    def test_point_torque(self):
        b = Beam(10)
        b.pinned_support = 2
        b.rolling_support = 8
        b.add_loads([PointTorque(30, 4)])
        F_Ax, F_Ay, F_By = b.get_reaction_forces()
        assert isinstance(float(F_Ay), float)

    def test_invalid_load_type(self):
        b = Beam(10)
        with pytest.raises(TypeError):
            b.add_loads(["not_a_load"])


class TestBeamPlots:
    def _make_loaded_beam(self):
        b = Beam(9)
        b.pinned_support = 2
        b.rolling_support = 7
        b.add_loads([PointLoadV(-20, 3)])
        return b

    def test_plot_returns_figure(self):
        b = self._make_loaded_beam()
        fig = b.plot()
        assert fig is not None
        plt.close("all")

    def test_plot_beam_diagram(self):
        b = self._make_loaded_beam()
        fig, ax = plt.subplots()
        b.plot_beam_diagram(ax)
        plt.close("all")

    def test_plot_normal_force(self):
        b = self._make_loaded_beam()
        fig, ax = plt.subplots()
        b.plot_normal_force(ax)
        plt.close("all")

    def test_plot_shear_force(self):
        b = self._make_loaded_beam()
        fig, ax = plt.subplots()
        b.plot_shear_force(ax)
        plt.close("all")

    def test_plot_bending_moment(self):
        b = self._make_loaded_beam()
        fig, ax = plt.subplots()
        b.plot_bending_moment(ax)
        plt.close("all")

    def test_plot_with_distributed_load(self):
        b = Beam(10)
        b.pinned_support = 2
        b.rolling_support = 8
        b.add_loads([DistributedLoadV("-10", (0, 10))])
        fig = b.plot()
        assert fig is not None
        plt.close("all")

    def test_plot_with_h_load(self):
        b = Beam(10)
        b.pinned_support = 2
        b.rolling_support = 8
        b.add_loads([DistributedLoadH("5", (0, 5))])
        fig = b.plot()
        assert fig is not None
        plt.close("all")

    def test_plot_beam_diagram_no_ax(self):
        b = self._make_loaded_beam()
        fig = b.plot_beam_diagram()
        assert fig is not None
        plt.close("all")

    def test_plot_normal_force_no_ax(self):
        b = self._make_loaded_beam()
        fig = b.plot_normal_force()
        assert fig is not None
        plt.close("all")

    def test_plot_shear_force_no_ax(self):
        b = self._make_loaded_beam()
        fig = b.plot_shear_force()
        assert fig is not None
        plt.close("all")

    def test_plot_bending_moment_no_ax(self):
        b = self._make_loaded_beam()
        fig = b.plot_bending_moment()
        assert fig is not None
        plt.close("all")

    def test_plot_with_point_load_h(self):
        # PointLoadH(10, 5) covers else branch (line 428), PointLoadH(-10, 5) covers if branch (line 426)
        b = Beam(10)
        b.pinned_support = 2
        b.rolling_support = 8
        b.add_loads([PointLoadH(10, 5), PointLoadH(-10, 7)])
        fig, ax = plt.subplots()
        b.plot_beam_diagram(ax)
        plt.close("all")

    def test_plot_with_positive_point_load_v(self):
        # Covers line 415: else branch for positive vertical point load drawing
        b = Beam(10)
        b.pinned_support = 2
        b.rolling_support = 8
        b.add_loads([PointLoadV(20, 5)])
        fig, ax = plt.subplots()
        b.plot_beam_diagram(ax)
        plt.close("all")

    def test_plot_analytical_no_color_no_maxmin(self):
        # Covers 332->338 (color=None) and 338->359 (maxmin_hline=False)
        b = self._make_loaded_beam()
        fig, ax = plt.subplots()
        b._plot_analytical(ax, Integer(0), color=None, maxmin_hline=False)
        plt.close("all")

    def test_plot_analytical_with_title_no_ylabel(self):
        # Covers line 365 (title truthy) and 370->373 (ylabel="" and yunits="")
        b = self._make_loaded_beam()
        fig, ax = plt.subplots()
        b._plot_analytical(ax, Integer(0), title="Test Title", ylabel="", yunits="")
        plt.close("all")

