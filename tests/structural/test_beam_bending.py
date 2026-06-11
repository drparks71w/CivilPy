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
import numpy as np
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
    CantileverBeam,
    ProppedCantileverBeam,
    FixedFixedBeam,
    ContinuousBeam,
)
from sympy.abc import x


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


class TestAISCManualCases:
    def test_case_2_triangular_load(self):
        """AISC Case 2: Simple Beam - Load Increasing Uniformly to One End.
        R1 = V1 = W/3, R2 = V2 = 2W/3
        Max Moment = 0.1283 * W * L at x = L / sqrt(3)
        Total Load W = w_max * L / 2
        """
        L = 15.0
        w_max = 2.0
        W = w_max * L / 2.0  # Total load

        b = Beam(L)
        b.pinned_support = 0
        b.rolling_support = L
        # Load expr: w_max * x / L
        # Since DistributedLoadV shifts by default, and we start at x=0, expr is w_max * x / L
        b.add_loads([DistributedLoadV(f"{w_max} * x / {L}", (0, L))])

        F_Ax, F_Ay, F_By = b.get_reaction_forces()

        assert pytest.approx(F_Ay, rel=1e-3) == W / 3.0
        assert pytest.approx(F_By, rel=1e-3) == 2.0 * W / 3.0

        # Max Moment
        M = b.get_moment_function()
        x_max_m = L / np.sqrt(3)
        M_max = float(M.subs(x, x_max_m))
        # AISC M_max = 0.1283 * W * L
        assert pytest.approx(M_max, rel=1e-3) == 0.1283 * W * L

    def test_case_4_partial_uniform_load(self):
        """AISC Case 4: Simple Beam - Uniform Load Partially Distributed.
        R1 = V1 = (wb / 2L) * (2c + b)
        R2 = V2 = (wb / 2L) * (2a + b)
        """
        L = 20.0
        w = 1.5
        a = 5.0
        b_len = 10.0
        c = L - a - b_len  # 5.0

        beam = Beam(L)
        beam.pinned_support = 0
        beam.rolling_support = L
        beam.add_loads([DistributedLoadV(f"{w}", (a, a + b_len))])

        F_Ax, F_Ay, F_By = beam.get_reaction_forces()

        expected_R1 = (w * b_len / (2 * L)) * (2 * c + b_len)
        expected_R2 = (w * b_len / (2 * L)) * (2 * a + b_len)

        assert pytest.approx(F_Ay, rel=1e-3) == expected_R1
        assert pytest.approx(F_By, rel=1e-3) == expected_R2


class TestBeamReactions:
    def test_simple_point_load(self):
        b = Beam(9)
        b.pinned_support = 2
        b.rolling_support = 7
        b.add_loads([PointLoadV(20, 3)])
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
        b.add_loads([DistributedLoadV("10", (0, 10))])
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
        b.add_loads([PointLoadV(20, 3)])
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
        b.add_loads([DistributedLoadV("10", (0, 10))])
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


class TestSpecializedBeams:
    def _make_loaded_beam(self):
        b = Beam(9)
        b.pinned_support = 2
        b.rolling_support = 7
        b.add_loads([PointLoadV(20, 3)])
        return b

    def test_cantilever_beam(self):
        cb = CantileverBeam(10)
        cb.add_loads([PointLoadV(5, 10)])  # 5 kip downward at free end
        V, M = cb.get_reaction_forces()
        assert abs(V - 5.0) < 1e-3
        assert abs(M - 50.0) < 1e-3

        # Test deflection
        defl = cb.get_deflection_function(29000, 100)
        # Max deflection at free end x=10: PL^3/(3EI) = 5*10^3/(3*29000*100/1728) = 5000 / (16782.4) = 0.2979 in
        # Wait, the 1728 factor is handled in get_deflection_function.
        # AISC says deflection is negative downward. My code might be returning negative.
        d_max = defl.subs(x, 10)
        assert abs(float(d_max) - (-0.9931)) < 1e-3

        # Test plotting
        fig = cb.plot_beam_diagram()
        assert fig is not None
        plt.close("all")

    def test_propped_cantilever_beam(self):
        # AISC Case 12: Uniform load w on propped cantilever
        # R_A (fixed) = 5wl/8, R_B (roller) = 3wl/8
        pb = ProppedCantileverBeam(10)
        pb.add_loads([DistributedLoadV("1", (0, 10))])
        # Reactions return (F_Ax, V_A, M_A, R_B)
        # Formula says R_B = 3*1*10/8 = 3.75, R_A = 5*1*10/8 = 6.25, M_A = 1*10^2/8 = 12.5
        rxns = pb.get_reaction_forces()
        assert abs(rxns[1] - 6.25) < 1e-3  # V_A
        assert abs(rxns[2] - 12.5) < 1e-3  # M_A
        assert abs(rxns[3] - 3.75) < 1e-3  # R_B

        # Test deflection
        defl = pb.get_deflection_function(29000, 100)
        assert defl is not None

        # Test plotting
        fig = pb.plot()
        assert fig is not None
        plt.close("all")

    def test_fixed_fixed_beam(self):
        # AISC Case 15: Point load P at center
        # R_A = R_B = P/2, M_A = M_B = PL/8
        ff = FixedFixedBeam(10)
        ff.add_loads([PointLoadV(10, 5)])
        # Reactions return (F_Ax, V_A, M_A, V_B, M_B)
        # P=10, L=10 => R=5, M=10*10/8 = 12.5
        rxns = ff.get_reaction_forces()
        assert abs(rxns[1] - 5.0) < 1e-3   # V_A
        assert abs(rxns[2] - 12.5) < 1e-3  # M_A
        assert abs(rxns[3] - 5.0) < 1e-3   # V_B
        assert abs(rxns[4] - 12.5) < 1e-3  # M_B

        # Test deflection
        defl = ff.get_deflection_function(29000, 100)
        assert defl is not None

        # Test plotting
        fig = ff.plot()
        assert fig is not None
        plt.close("all")


    def test_plot_analytical_inverted(self):
        # Covers line 379: y_vec *= -1
        b = self._make_loaded_beam()
        fig, ax = plt.subplots()
        b._plot_analytical(ax, Integer(10), inverted=True)
        plt.close("all")

    def test_plot_analytical_yspan_zero(self):
        # Covers line 418: else branch for yspan > 0 (if yspan == 0)
        b = Beam(10)
        fig, ax = plt.subplots()
        # For a beam with no loads, y_vec is all zeros, yspan is 0
        b._plot_analytical(ax, Integer(0))
        plt.close("all")

    def test_plot_analytical_yspan_nonzero(self):
        # Covers line 418: if yspan > 0
        b = Beam(10)
        fig, ax = plt.subplots()
        # y = x, so yspan = 10. ymax=10, ymin=0.
        b._plot_analytical(ax, x)
        # Smoke test: check that ylim was modified (at least it shouldn't be default 0,1)
        ymin, ymax = ax.get_ylim()
        assert ymax > ymin
        plt.close("all")

    def test_plot_beam_diagram_vertical_loads_both_directions(self):
        # Covers 475 and 472
        b = Beam(10)
        # PointLoadV(10, 3) -> stored as -10 (upward in schematic)
        # PointLoadV(-10, 7) -> stored as +10 (downward in schematic)
        b.add_loads([PointLoadV(10, 3), PointLoadV(-10, 7)])
        fig = b.plot_beam_diagram()
        plt.close("all")

    def test_propped_cantilever_plot_negative_load_v(self):
        # Covers line 1026: if load[0] < 0
        pb = ProppedCantileverBeam(10)
        pb.add_loads([PointLoadV(10, 5)]) # stored as -10
        fig = pb.plot_beam_diagram()
        plt.close("all")

    def test_plot_deflection_no_ax(self):
        # Covers line 660: if ax is None
        b = Beam(10)
        b.pinned_support = 0
        b.rolling_support = 10
        b.add_loads([PointLoadV(10, 5)])
        fig = b.plot_deflection(29000, 100, ax=None)
        assert fig is not None
        plt.close("all")

    def test_cantilever_plot_no_ax(self):
        # Covers 767-769: if ax is None in CantileverBeam.plot_beam_diagram
        cb = CantileverBeam(10)
        fig = cb.plot_beam_diagram()
        assert fig is not None
        plt.close("all")

    def test_cantilever_plot_with_ax(self):
        # Covers line 767: else branch (ax is not None)
        cb = CantileverBeam(10)
        fig, ax = plt.subplots()
        fig2 = cb.plot_beam_diagram(ax)
        assert fig2 == fig
        plt.close("all")

    def test_cantilever_plot_positive_load(self):
        # Covers line 814: else branch for vertical point load (downward)
        cb = CantileverBeam(10)
        # add_loads(PointLoadV(10, 5)) -> stored as -10.
        # Cantilever _draw_cantilever_schematic: if load[0] < 0: ... else: (line 814)
        # So we need load[0] > 0.
        # add_loads(PointLoadV(-10, 5)) -> stored as +10.
        cb.add_loads([PointLoadV(-10, 5)])
        fig = cb.plot_beam_diagram()
        plt.close("all")

    def test_plot_beam_full_with_title(self):
        # Covers line 841: if title:
        from civilpy.structural.beam_bending import plot_beam_full
        b = Beam(10)
        fig = plot_beam_full(b, title="Full Beam Plot")
        plt.close("all")

    def test_plot_beam_full_no_I(self):
        # Covers line 850: if I: (else branch)
        from civilpy.structural.beam_bending import plot_beam_full
        b = Beam(10)
        fig = plot_beam_full(b, I=None)
        plt.close("all")

    def test_propped_cantilever_plot_positive_load(self):
        # Covers line 1029: else branch for vertical point load
        pb = ProppedCantileverBeam(10)
        pb.add_loads([PointLoadV(-10, 5)]) # stored as +10
        fig = pb.plot_beam_diagram()
        plt.close("all")

    def test_fixed_fixed_plot_positive_load(self):
        # Covers line 1180: else branch for vertical point load
        ff = FixedFixedBeam(10)
        ff.add_loads([PointLoadV(-10, 5)]) # stored as +10
        fig = ff.plot_beam_diagram()
        plt.close("all")
class TestBeamEdgeCases:
    def test_beam_length_setter(self):
        b = Beam(10)
        b.length = 20
        assert b.length == 20
        with pytest.raises(ValueError):
            b.length = -5

    def test_pinned_support_setter(self):
        b = Beam(10)
        with pytest.raises(ValueError):
            b.pinned_support = 15

    def test_deflection_with_pint_quantity(self):
        class MockQuantity:
            def __init__(self, magnitude):
                self.magnitude = magnitude
        b = Beam(10)
        b.pinned_support = 0
        b.rolling_support = 10
        b.add_loads([PointLoadV(10, 5)])
        # Just check it doesn't crash
        defl = b.get_deflection_function(29000, MockQuantity(100))
        assert defl is not None

    def test_plot_all(self):
        b = Beam(10)
        b.add_loads([PointLoadV(10, 5)])
        fig = b.plot_all()
        assert fig is not None
        plt.close("all")

    def test_plot_beam_full(self):
        from civilpy.structural.beam_bending import plot_beam_full
        b = Beam(10)
        b.add_loads([PointLoadV(10, 5)])
        fig = plot_beam_full(b, I=100)
        assert fig is not None
        plt.close("all")


class TestContinuousBeam:
    def test_continuous_beam_two_spans_uniform(self):
        # AISC Case 29: Two equal spans, uniform load w on entire length
        L = 10
        w = 1
        beam = ContinuousBeam(2 * L, intermediate_supports=[L])
        beam.pinned_support = 0
        beam.rolling_support = 2 * L
        beam.add_loads([DistributedLoadV(w, (0, 2 * L))])

        R2 = beam._redundant_reactions[L]
        _, R1, R3 = beam.get_reaction_forces()

        assert pytest.approx(R2) == 1.25 * w * L
        assert pytest.approx(R1) == 0.375 * w * L
        assert pytest.approx(R3) == 0.375 * w * L

    def test_continuous_beam_three_spans_uniform(self):
        # AISC Case 30: Three equal spans, uniform load w
        L = 10
        w = 1
        beam = ContinuousBeam(3 * L, intermediate_supports=[L, 2 * L])
        beam.pinned_support = 0
        beam.rolling_support = 3 * L
        beam.add_loads([DistributedLoadV(w, (0, 3 * L))])

        R2 = beam._redundant_reactions[L]
        R3 = beam._redundant_reactions[2 * L]
        _, R1, R4 = beam.get_reaction_forces()

        assert pytest.approx(R1) == 0.4 * w * L
        assert pytest.approx(R4) == 0.4 * w * L
        assert pytest.approx(R2) == 1.1 * w * L
        assert pytest.approx(R3) == 1.1 * w * L

    def test_continuous_beam_two_spans_point_load(self):
        # AISC Case 31: Two equal spans, point load P at center of one span
        L = 10
        P = 32
        beam = ContinuousBeam(2 * L, intermediate_supports=[L])
        beam.pinned_support = 0
        beam.rolling_support = 2 * L
        beam.add_loads([PointLoadV(P, L / 2)])

        R2 = beam._redundant_reactions[L]
        _, R1, R3 = beam.get_reaction_forces()

        assert pytest.approx(R1) == 13
        assert pytest.approx(R2) == 22
        assert pytest.approx(R3) == -3

    def test_continuous_beam_no_intermediate(self):
        beam = ContinuousBeam(10)
        beam.add_loads([PointLoadV(10, 5)])
        _, R1, R2 = beam.get_reaction_forces()
        assert R1 == 5.0
        assert R2 == 5.0
        assert beam._redundant_reactions == {}

    def test_continuous_beam_plot(self):
        beam = ContinuousBeam(20, intermediate_supports=[10])
        beam.add_loads([PointLoadV(10, 5)])
        fig = beam.plot_beam_diagram()
        assert fig is not None
        plt.close("all")

    def test_continuous_beam_solve_branches(self):
        # Trigger different branches in _solve_indeterminate_reactions
        # dict branch (already covered by uniform loads mostly, but let's be sure)
        # solve with one symbol returning list: already covered by Case 29.
        # list of lists branch:
        L = 10
        beam = ContinuousBeam(3*L, intermediate_supports=[L, 2*L])
        beam.add_loads([PointLoadV(10, L/2)])
        assert len(beam._redundant_reactions) == 2


class TestMovingLoads:
    def test_moving_load_single(self):
        # AISC Case 43: Simple beam, single moving load P
        # Max Moment = PL/4 at x=L/2
        # Max Shear = P at ends
        L = 20
        P = 10
        beam = Beam(L)
        beam.pinned_support = 0
        beam.rolling_support = L

        # Case 43: single moving load
        loads = [PointLoadV(P, 0)]
        x_vec, max_v, min_v, max_m, min_m = beam.get_envelope(loads, step_size=0.1)

        assert np.isclose(max(max_m), P * L / 4, atol=0.1)
        assert np.isclose(max(max_v), P, atol=0.1)
        assert np.isclose(min(min_v), -P, atol=0.1)

    def test_moving_load_hs20(self):
        from civilpy.structural.aashto.vehicles import HS20Load
        L = 50
        beam = Beam(L)
        beam.pinned_support = 0
        beam.rolling_support = L

        hs20 = HS20Load()
        loads = []
        for k, a in hs20.axles.items():
            if isinstance(k, int):
                loads.append(PointLoadV(a['load_kip'], a['dist_ft']))

        x_vec, max_v, min_v, max_m, min_m = beam.get_envelope(loads, step_size=1.0)

        assert max(max_m) > 0
        assert max(max_v) > 0
        assert min(min_v) < 0

    def test_plot_envelope(self):
        L = 20
        beam = Beam(L)
        beam.pinned_support = 0
        beam.rolling_support = L
        loads = [PointLoadV(10, 0)]
        res = beam.get_envelope(loads)
        fig = beam.plot_envelope(*res)
        assert fig is not None
        plt.close("all")

        # Test with ax provided
        fig, ax = plt.subplots()
        res_ax = beam.plot_envelope(*res, ax=ax)
        assert res_ax is None
        plt.close("all")

