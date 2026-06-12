#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Mohr's circle, strut-and-tie, and P-M plotting: hand-checked mechanics
plus figure smoke tests."""

import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from civilpy.structural.mohrs_circle import MohrsCircle
from civilpy.structural.strut_and_tie import StrutAndTieModel
from civilpy.structural.aashto import lrfd
from civilpy.structural.aashto.lrfd import RebarLayer


class TestMohrsCircle:
    # Hibbeler-style example: sx=80, sy=20, txy=30 (any units)
    MC = MohrsCircle(80.0, 20.0, 30.0)

    def test_principal_stresses(self):
        assert self.MC.center == pytest.approx(50.0)
        assert self.MC.radius == pytest.approx(math.hypot(30.0, 30.0))
        assert self.MC.sigma_1 == pytest.approx(50.0 + 30.0 * math.sqrt(2))
        assert self.MC.sigma_2 == pytest.approx(50.0 - 30.0 * math.sqrt(2))

    def test_principal_angle(self):
        assert self.MC.theta_p_deg == pytest.approx(22.5)
        # rotating to theta_p kills the shear and recovers sigma_1
        sx, sy, txy = self.MC.stresses_at(self.MC.theta_p_deg)
        assert txy == pytest.approx(0.0, abs=1e-9)
        assert sx == pytest.approx(self.MC.sigma_1)
        assert sy == pytest.approx(self.MC.sigma_2)

    def test_max_shear_orientation(self):
        _, _, txy = self.MC.stresses_at(self.MC.theta_s_deg)
        assert abs(txy) == pytest.approx(self.MC.tau_max)

    def test_invariants_hold_at_any_angle(self):
        for theta in (0.0, 15.0, 37.0, 90.0):
            sx, sy, txy = self.MC.stresses_at(theta)
            assert sx + sy == pytest.approx(100.0)  # first invariant

    def test_rotation_by_90_swaps_faces(self):
        sx, sy, txy = self.MC.stresses_at(90.0)
        assert sx == pytest.approx(20.0)
        assert sy == pytest.approx(80.0)
        assert txy == pytest.approx(-30.0)

    def test_abs_max_shear_plane_stress(self):
        # both principals positive -> out-of-plane governs: sigma_1/2
        mc = MohrsCircle(80.0, 40.0, 10.0)
        assert mc.tau_abs_max == pytest.approx(mc.sigma_1 / 2.0)

    def test_plots_return_figures(self):
        fig = self.MC.plot(show_out_of_plane=True, theta_deg=30.0)
        assert fig is not None
        fig2 = self.MC.plot_element(theta_deg=22.5)
        assert fig2 is not None
        plt.close("all")


class TestStrutAndTie:
    def _deep_beam(self):
        stm = StrutAndTieModel()
        stm.add_node("A", 0, 0)
        stm.add_node("B", 8, 0)
        stm.add_node("C", 4, 4)
        stm.add_member("A", "C")
        stm.add_member("B", "C")
        stm.add_member("A", "B")
        stm.add_support("A", fix_x=True, fix_y=True)
        stm.add_support("B", fix_y=True)
        stm.add_load("C", fy=-100.0)
        return stm

    def test_triangle_truss_forces(self):
        stm = self._deep_beam()
        f = stm.solve()
        # 45-degree diagonals: strut = -P/(2 sin45) = -70.71, tie = +50
        assert f[("A", "C")] == pytest.approx(-100.0 / (2 * math.sin(math.pi / 4)))
        assert f[("B", "C")] == pytest.approx(f[("A", "C")])
        assert f[("A", "B")] == pytest.approx(50.0)

    def test_reactions(self):
        stm = self._deep_beam()
        stm.solve()
        assert stm.reactions["A"][1] == pytest.approx(50.0)
        assert stm.reactions["B"][1] == pytest.approx(50.0)

    def test_indeterminate_raises(self):
        stm = self._deep_beam()
        stm.add_support("C", fix_x=True)  # extra restraint
        with pytest.raises(ValueError):
            stm.solve()

    def test_unknown_node_raises(self):
        stm = StrutAndTieModel()
        stm.add_node("A", 0, 0)
        with pytest.raises(KeyError):
            stm.add_member("A", "Z")

    def test_plot_returns_figure(self):
        stm = self._deep_beam()
        fig = stm.plot()
        assert fig is not None
        plt.close("all")


class TestSTMChecks:
    def test_tie_resistance(self):
        # 4 #8 = 3.16 in^2: Pn = 60*3.16 = 189.6; phi*Pn = 170.6
        r = lrfd.stm_tie_resistance(a_st=3.16, p_u=150.0)
        assert r.capacity == pytest.approx(189.6)
        assert r.phi == 0.90
        assert r.ok

    def test_tie_with_prestress(self):
        r = lrfd.stm_tie_resistance(a_st=0.0, a_ps=1.53, f_pe=160.0)
        assert r.capacity == pytest.approx(1.53 * 220.0)

    def test_node_efficiency_ordering(self):
        ccc = lrfd.stm_node_resistance(a_cn=100.0, f_c=4.0, node_type="CCC")
        cct = lrfd.stm_node_resistance(a_cn=100.0, f_c=4.0, node_type="CCT")
        ctt = lrfd.stm_node_resistance(a_cn=100.0, f_c=4.0, node_type="CTT")
        assert ccc.capacity > cct.capacity > ctt.capacity
        assert ccc.capacity == pytest.approx(0.85 * 4.0 * 100.0)

    def test_no_crack_control_penalty(self):
        r = lrfd.stm_node_resistance(a_cn=100.0, f_c=4.0,
                                     crack_control=False)
        assert r.details["nu"] == 0.45

    def test_confinement_capped(self):
        r = lrfd.stm_node_resistance(a_cn=100.0, f_c=4.0, m_confinement=3.0)
        assert r.details["fcu"] == pytest.approx(2.0 * 0.85 * 4.0)

    def test_crack_control_ratio(self):
        # 12" web, #5 at 10" each way: 0.31/(12*10) = 0.00258 < 0.003
        r = lrfd.stm_crack_control_reinforcement(
            b_w=12.0, s_h=10.0, s_v=10.0,
            a_s_horizontal=0.31, a_s_vertical=0.31,
        )
        assert not r.ok

    def test_stm_workflow_composition(self):
        """Solve the truss, then check its worst tie and strut."""
        stm = StrutAndTieModel()
        stm.add_node("A", 0, 0)
        stm.add_node("B", 8, 0)
        stm.add_node("C", 4, 4)
        stm.add_member("A", "C")
        stm.add_member("B", "C")
        stm.add_member("A", "B")
        stm.add_support("A", fix_x=True, fix_y=True)
        stm.add_support("B", fix_y=True)
        stm.add_load("C", fy=-100.0)
        forces = stm.solve()
        tie = max(forces.values())
        strut = min(forces.values())
        assert lrfd.stm_tie_resistance(a_st=2.0, p_u=tie).ok
        assert lrfd.stm_node_resistance(
            a_cn=80.0, f_c=4.0, node_type="CCT", p_u=abs(strut)
        ).ok


class TestPMPlot:
    def test_plot_returns_figure(self):
        layers = [RebarLayer(4.0, 2.5), RebarLayer(4.0, 21.5)]
        pts = lrfd.rc_pm_interaction_diagram(
            layers=layers, f_c=4.0, f_y=60.0, b=16.0, h=24.0
        )
        fig = lrfd.plot_pm_interaction(pts, p_u=600.0, m_u=3000.0)
        assert fig is not None
        plt.close("all")


class TestRegistry:
    def test_stm_articles_registered(self):
        for num in ("5.8.2.4", "5.8.2.5", "5.8.2.6"):
            assert num in lrfd.ARTICLES
