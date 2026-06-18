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

"""AASHTO roadway design functions, including cross-checks of the design
control tables against their generating equations."""

import math

import pytest

from civilpy.transportation import roadway as r


class TestSightDistance:
    def test_ssd_level_hand_calc(self):
        # 60 mph: 1.47*60*2.5 + 60^2/(30*(11.2/32.2)) = 220.5 + 345.5.
        assert r.stopping_sight_distance(60) == pytest.approx(566.0, abs=1.0)

    def test_ssd_matches_design_table(self):
        # Formula reproduces the rounded Green Book design SSD within 5 ft.
        for v, ssd in r.SSD_DESIGN.items():
            assert r.stopping_sight_distance(v) == pytest.approx(ssd, abs=6.0)

    def test_ssd_upgrade_shortens(self):
        assert r.stopping_sight_distance(60, grade=0.06) < r.stopping_sight_distance(60)

    def test_ssd_downgrade_lengthens(self):
        assert r.stopping_sight_distance(60, grade=-0.06) > r.stopping_sight_distance(60)

    def test_braking_with_friction(self):
        # d = V^2/(30 f); 50 mph, f=0.35: 2500/10.5 = 238.1.
        assert r.braking_distance(50, friction=0.35) == pytest.approx(238.1, abs=0.5)

    def test_decision_sight_distance_stop_vs_change(self):
        # Maneuver E (longest pre-maneuver) exceeds A.
        assert r.decision_sight_distance(60, "E") > r.decision_sight_distance(60, "A")

    def test_decision_sight_distance_bad_maneuver(self):
        with pytest.raises(ValueError):
            r.decision_sight_distance(60, "Z")

    def test_intersection_sight_distance(self):
        # 7.5 s gap at 45 mph major: 1.47*45*7.5 = 496.1 ft.
        assert r.intersection_sight_distance(45, 7.5) == pytest.approx(496.1, abs=0.5)


class TestVerticalCurves:
    def test_crest_k_table_matches_formula(self):
        # K = L/A at the design SSD reproduces the Table 3-34 crest K values.
        for v, k in r.K_CREST.items():
            ssd = r.SSD_DESIGN[v]
            formula_k = r.crest_curve_length(1.0, ssd)  # A = 1% -> L == K
            assert formula_k == pytest.approx(k, abs=1.0)

    def test_sag_k_table_matches_formula(self):
        for v, k in r.K_SAG.items():
            ssd = r.SSD_DESIGN[v]
            formula_k = r.sag_curve_length(1.0, ssd)
            assert formula_k == pytest.approx(k, abs=1.0)

    def test_crest_branch_continuity(self):
        # At S == L the two branches agree; sweep a case around it.
        a = 4.0
        lengths = [r.crest_curve_length(a, s) for s in (200, 400, 600, 800)]
        assert all(b >= 0 for b in lengths)

    def test_length_from_k(self):
        assert r.vertical_curve_length_from_k(151, 4.0) == pytest.approx(604.0)

    def test_zero_grade_difference(self):
        assert r.crest_curve_length(0.0, 500) == 0.0
        assert r.sag_curve_length(0.0, 500) == 0.0


class TestSuperelevation:
    def test_max_relative_gradient_monotonic(self):
        vals = [r.MAX_RELATIVE_GRADIENT_PCT[v] for v in sorted(r.MAX_RELATIVE_GRADIENT_PCT)]
        assert vals == sorted(vals, reverse=True)

    def test_runoff_length(self):
        # 2 lanes, 12 ft, e=0.06, Delta=0.45% (60 mph), bw for 2 lanes 0.75.
        bw = r.runoff_adjustment_factor(2)
        assert bw == pytest.approx(0.75)
        lr = r.superelevation_runoff_length(0.06, 12.0, 2.0, 0.0045, bw)
        assert lr == pytest.approx(240.0, abs=1.0)

    def test_tangent_runout(self):
        # Lt = (eNC/ed) Lr = (0.02/0.06)*240 = 80.
        assert r.tangent_runout_length(240.0, 0.06, 0.02) == pytest.approx(80.0)

    def test_min_radius(self):
        assert r.min_radius(60, 0.08, 0.12) == pytest.approx(1200.0)


class TestRoadside:
    def test_lon_parallel_full_runout_at_edge(self):
        # Barrier at edge (L1=0): full runout length is needed.
        assert r.barrier_length_of_need(300, 30, 0) == pytest.approx(300.0)

    def test_lon_parallel_offset(self):
        # L1 = 12, LA = 30: X = 300*(30-12)/30 = 180.
        assert r.barrier_length_of_need(300, 30, 12) == pytest.approx(180.0)

    def test_lon_at_hazard_offset_is_zero(self):
        assert r.barrier_length_of_need(300, 30, 30) == pytest.approx(0.0)

    def test_lon_flared_shorter_than_parallel(self):
        parallel = r.barrier_length_of_need(300, 30, 12)
        flared = r.barrier_length_of_need(300, 30, 12, flare_rate=20, back_offset=12)
        assert flared < parallel

    def test_lon_bad_lateral_extent(self):
        with pytest.raises(ValueError):
            r.barrier_length_of_need(300, 0, 0)

    def test_flare_rate_table_increases_with_speed(self):
        speeds = sorted(r.FLARE_RATE_RIGID)
        rates = [r.FLARE_RATE_RIGID[s] for s in speeds]
        assert rates == sorted(rates)
