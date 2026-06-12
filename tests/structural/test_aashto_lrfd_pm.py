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

"""Strain-compatibility P-M interaction: cross-checked against the
closed-form axial (5.6.4.4) and beam-flexure (5.6.3.2) functions at the
diagram's anchor points."""

import math

import pytest

from civilpy.structural.aashto import lrfd
from civilpy.structural.aashto.lrfd import RebarLayer

# 16x24 tied column, 3 layers of #9s (4-2-4), 2.5" to bar centers
LAYERS = [
    RebarLayer(area=4.0, depth=2.5),
    RebarLayer(area=2.0, depth=12.0),
    RebarLayer(area=4.0, depth=21.5),
]
RECT = dict(layers=LAYERS, f_c=4.0, f_y=60.0, b=16.0, h=24.0)


class TestDiagramAnchors:
    def test_max_axial_matches_5644(self):
        diagram = lrfd.rc_pm_interaction_diagram(**RECT)
        closed_form = lrfd.rc_column_axial_resistance(
            a_g=16.0 * 24.0, a_st=10.0, f_c=4.0, f_y=60.0
        )
        assert max(pt.p_n for pt in diagram) == pytest.approx(
            closed_form.capacity, rel=1e-6
        )

    def test_pure_tension_anchor(self):
        diagram = lrfd.rc_pm_interaction_diagram(**RECT)
        assert diagram[0].p_n == pytest.approx(-60.0 * 10.0)
        assert diagram[0].m_n == 0.0

    def test_pure_bending_matches_beam_function(self):
        # Singly-reinforced section: the diagram's P = 0 crossing must
        # reproduce the closed-form beam solution (same Whitney block,
        # same yielded tension steel, no compression-steel bookkeeping)
        layers = [RebarLayer(area=4.0, depth=21.5)]
        diagram = lrfd.rc_pm_interaction_diagram(
            layers=layers, f_c=4.0, f_y=60.0, b=16.0, h=24.0
        )
        m_at_zero = None
        for lo, hi in zip(diagram, diagram[1:]):
            if lo.p_n <= 0.0 <= hi.p_n:
                f = -lo.p_n / (hi.p_n - lo.p_n)
                m_at_zero = lo.m_n + f * (hi.m_n - lo.m_n)
                break
        assert m_at_zero is not None
        beam = lrfd.rc_rectangular_flexural_resistance(
            a_s=4.0, f_y=60.0, f_c=4.0, b=16.0, d_s=21.5
        )
        assert m_at_zero == pytest.approx(beam.capacity, rel=0.02)

    def test_balanced_point_has_peak_moment(self):
        diagram = lrfd.rc_pm_interaction_diagram(**RECT)
        peak = max(diagram, key=lambda pt: pt.m_n)
        # balanced c = 0.003/(0.003+eps_y)*dt = 0.5917*21.5 = 12.72
        c_bal = 0.003 / (0.003 + 60.0 / 29000.0) * 21.5
        assert peak.c == pytest.approx(c_bal, rel=0.25)
        # moment at the peak exceeds both anchors
        assert peak.m_n > diagram[0].m_n
        assert peak.m_n > diagram[-1].m_n

    def test_phi_transitions_along_curve(self):
        diagram = lrfd.rc_pm_interaction_diagram(**RECT)
        phis = {round(pt.phi, 2) for pt in diagram}
        assert 0.75 in phis  # compression-controlled region
        assert 0.9 in phis   # tension-controlled region


class TestCircular:
    # 36" circular column, 12 #9 in a ring -> idealize as 4 layers
    R = 18.0
    BAR_RING = 14.5  # radius to bar centers
    CIRC_LAYERS = [
        RebarLayer(area=3.0, depth=18.0 - 14.5),
        RebarLayer(area=3.0, depth=18.0 - 14.5 * math.cos(math.radians(60))),
        RebarLayer(area=3.0, depth=18.0 + 14.5 * math.cos(math.radians(60))),
        RebarLayer(area=3.0, depth=18.0 + 14.5),
    ]

    def test_max_axial_matches_5644(self):
        diagram = lrfd.rc_pm_interaction_diagram(
            layers=self.CIRC_LAYERS, f_c=4.0, f_y=60.0, diameter=36.0,
            spiral=True,
        )
        a_g = math.pi * 18.0**2
        closed = lrfd.rc_column_axial_resistance(
            a_g=a_g, a_st=12.0, f_c=4.0, f_y=60.0, spiral=True
        )
        assert max(pt.p_n for pt in diagram) == pytest.approx(
            closed.capacity, rel=1e-6
        )

    def test_segment_geometry(self):
        from civilpy.structural.aashto.lrfd.columns import _circular_segment
        # full circle
        area, y = _circular_segment(18.0, 36.0)
        assert area == pytest.approx(math.pi * 18.0**2)
        assert y == pytest.approx(18.0)
        # half circle: centroid 4R/3pi above center -> depth from top
        area, y = _circular_segment(18.0, 18.0)
        assert area == pytest.approx(math.pi * 18.0**2 / 2.0)
        assert y == pytest.approx(18.0 - 4.0 * 18.0 / (3.0 * math.pi))


class TestCapacityCheck:
    def test_adequate_column(self):
        r = lrfd.rc_pm_capacity_check(
            p_u=500.0, m_u=2000.0, **RECT
        )
        assert r.capacity > 2000.0
        assert r.ok

    def test_moment_capacity_drops_at_high_axial(self):
        low = lrfd.rc_pm_capacity_check(p_u=200.0, m_u=0.0, **RECT)
        high = lrfd.rc_pm_capacity_check(p_u=1400.0, m_u=0.0, **RECT)
        assert high.capacity < low.capacity

    def test_axial_beyond_diagram_no_capacity(self):
        r = lrfd.rc_pm_capacity_check(p_u=10000.0, m_u=100.0, **RECT)
        assert r.capacity == 0.0
        assert not r.ok

    def test_design_loop_over_bar_sizes(self):
        """Size column verticals by looping bar areas."""
        passing = []
        for bar in (0.60, 0.79, 1.00, 1.27):  # #7..#10
            layers = [RebarLayer(4 * bar, 2.5), RebarLayer(4 * bar, 21.5)]
            r = lrfd.rc_pm_capacity_check(
                p_u=600.0, m_u=4500.0, layers=layers,
                f_c=4.0, f_y=60.0, b=16.0, h=24.0,
            )
            if r.ok:
                passing.append(bar)
        assert passing
        assert 0.60 not in passing  # 8 #7s shouldn't make it


class TestBiaxial:
    def test_low_axial_moment_contour(self):
        r = lrfd.rc_biaxial_check(
            p_u=50.0, m_ux=1000.0, m_uy=500.0, m_rx=3000.0, m_ry=2000.0,
            f_c=4.0, a_g=384.0,
        )
        assert r.details["method"] == "moment-contour"
        assert r.demand == pytest.approx(1000.0 / 3000.0 + 500.0 / 2000.0)
        assert r.ok

    def test_high_axial_reciprocal(self):
        r = lrfd.rc_biaxial_check(
            p_u=800.0, m_ux=1000.0, m_uy=500.0, m_rx=3000.0, m_ry=2000.0,
            p_rx=1200.0, p_ry=1500.0, phi_p_o=2000.0,
            f_c=4.0, a_g=384.0,
        )
        assert r.details["method"] == "reciprocal-load"
        p_rxy = 1.0 / (1.0 / 1200.0 + 1.0 / 1500.0 - 1.0 / 2000.0)
        assert r.capacity == pytest.approx(p_rxy)
        assert r.ok  # 1000 > 800

    def test_high_axial_requires_pr_inputs(self):
        with pytest.raises(ValueError):
            lrfd.rc_biaxial_check(
                p_u=800.0, m_ux=1.0, m_uy=1.0, m_rx=3.0, m_ry=2.0,
                f_c=4.0, a_g=384.0,
            )


class TestRegistry:
    def test_pm_articles_registered(self):
        for num in ("5.6.4.5", "5.6.4.5 P-M", "5.6.4.5 check"):
            assert num in lrfd.ARTICLES
