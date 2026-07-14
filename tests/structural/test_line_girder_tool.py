#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Verification of the basic line-girder tool against the AISC Steel
Construction Manual Table 3-23 beam cases (shears, moments, deflections,
and moving-load maxima), plus checks that the tool's load derivation
matches hand statics."""

import numpy as np
import pytest

from civilpy.structural.continuous_beam import ContinuousBeam
from civilpy.structural.line_girder_tool import (
    BARRIER_CHOICES,
    BridgeConfig,
    analyze,
    barrier_weight_klf,
    compute_loads,
    lane_load_envelope,
    moving_load_envelope,
)

E, I = 29000.0, 100.0  # ksi, in^4 — arbitrary but consistent


class TestAISCTable323Diagrams:
    """Static cases: exact shears/moments, deflections vs the AISC
    coefficients (which are rounded to ~3 significant figures)."""

    def test_case_1_simple_span_uniform(self):
        # AISC Case 1: R = V = wl/2, Mmax = wl^2/8, Dmax = 5wl^4/384EI
        L, w = 20.0, 1.0
        b = ContinuousBeam([0.0, L]).add_udl(w)
        xs, v, m = b.diagrams(n=2001)
        assert pytest.approx(b.shear_at(1e-9), rel=1e-6) == w * L / 2
        assert pytest.approx(max(v), rel=2e-3) == w * L / 2
        assert pytest.approx(max(m), rel=1e-4) == w * L**2 / 8
        _, d = b.deflection_diagram(E, I, n=2001)
        exact = 5 * (w / 12.0) * (L * 12.0) ** 4 / (384 * E * I)
        assert pytest.approx(-min(d), rel=1e-3) == exact

    def test_case_29_two_equal_spans_uniform(self):
        # AISC Case 29: R1 = R3 = 0.375wl, R2 = 1.25wl, V(interior) = 0.625wl,
        # M(support) = -wl^2/8, M(0.375l) = 0.0703wl^2,
        # Dmax = wl^4/185EI at 0.4215l
        L, w = 20.0, 1.0
        b = ContinuousBeam([0.0, L, 2 * L]).add_udl(w)
        r = b.reactions()
        assert pytest.approx(r[0], rel=1e-6) == 0.375 * w * L
        assert pytest.approx(r[1], rel=1e-6) == 1.25 * w * L
        xs, v, m = b.diagrams(n=4001)
        assert pytest.approx(max(np.abs(v)), rel=1e-3) == 0.625 * w * L
        assert pytest.approx(min(m), rel=1e-4) == -w * L**2 / 8
        assert pytest.approx(max(m), rel=1e-3) == 0.0703 * w * L**2
        xs, d = b.deflection_diagram(E, I, n=4001)
        exact = (w / 12.0) * (L * 12.0) ** 4 / (185 * E * I)
        assert pytest.approx(-min(d), rel=3e-3) == exact
        assert pytest.approx(xs[int(np.argmin(d))] / L, abs=0.005) == 0.4215

    def test_case_30_three_equal_spans_uniform(self):
        # AISC Case 30: RA = RD = 0.4wl, RB = RC = 1.1wl,
        # M(support) = -0.10wl^2, M(0.4l) = 0.08wl^2,
        # Dmax = 0.0069wl^4/EI at 0.446l
        L, w = 20.0, 1.0
        b = ContinuousBeam([0.0, L, 2 * L, 3 * L]).add_udl(w)
        r = b.reactions()
        assert pytest.approx(r[0], rel=1e-6) == 0.4 * w * L
        assert pytest.approx(r[1], rel=1e-6) == 1.1 * w * L
        xs, v, m = b.diagrams(n=6001)
        assert pytest.approx(min(m), rel=1e-4) == -0.10 * w * L**2
        assert pytest.approx(max(m), rel=1e-4) == 0.08 * w * L**2
        xs, d = b.deflection_diagram(E, I, n=6001)
        exact = 0.0069 * (w / 12.0) * (L * 12.0) ** 4 / (E * I)
        assert pytest.approx(-min(d), rel=5e-3) == exact
        assert pytest.approx(xs[int(np.argmin(d))] / L, abs=0.005) == 0.446

    def test_shear_at_matches_diagram(self):
        L, w = 20.0, 2.0
        b = ContinuousBeam([0.0, L, 2 * L]).add_udl(w)
        # left-limit shear just before the interior support = -0.625wl
        assert pytest.approx(b.shear_at(L - 1e-6), rel=1e-4) == -0.625 * w * L
        xs, v = b.shear_diagram(n=1001)
        assert pytest.approx(min(v), rel=1e-3) == -0.625 * w * L


class TestAISCTable323MovingLoads:
    def test_case_43_single_moving_load(self):
        # AISC Case 43: Mmax = Pl/4 (load at midspan), Vmax = P (load at
        # support)
        P, L = 10.0, 20.0
        env = moving_load_envelope([0.0, L], [([P], [0.0])], n=801, step=0.05)
        assert pytest.approx(max(env["m_max"]), rel=1e-3) == P * L / 4
        assert pytest.approx(max(env["v_max"]), rel=5e-3) == P
        assert pytest.approx(-min(env["v_min"]), rel=5e-3) == P

    def test_case_44_two_equal_moving_loads(self):
        # AISC Case 44 (a < 0.586l): Mmax = (P/2l)(l - a/2)^2,
        # Vmax = P(2 - a/l)
        P, a, L = 10.0, 5.0, 20.0
        env = moving_load_envelope([0.0, L], [([P, P], [0.0, a])],
                                   n=801, step=0.05)
        assert pytest.approx(max(env["m_max"]), rel=1e-3) == \
            P / (2 * L) * (L - a / 2) ** 2
        assert pytest.approx(max(env["v_max"]), rel=5e-3) == P * (2 - a / L)

    def test_hs20_simple_span_moment(self):
        # Classic HS-20 check: 50 ft simple span Mmax = 627.9 kip-ft
        env = moving_load_envelope(
            [0.0, 50.0], [([8.0, 32.0, 32.0], [0.0, 14.0, 28.0])],
            n=401, step=0.1)
        assert pytest.approx(max(env["m_max"]), rel=2e-3) == 627.9

    def test_axle_exactly_on_interior_support(self):
        # regression: a point load at an interior support must be counted
        # once (it used to land in both adjacent spans' statics)
        b = ContinuousBeam([0.0, 50.0, 100.0, 150.0]).add_point(32.0, 50.0)
        r = b.reactions()
        assert pytest.approx(sum(r), abs=1e-9) == 32.0
        assert pytest.approx(r[1], abs=1e-9) == 32.0
        _, _, m = b.diagrams(n=301)
        assert np.allclose(m, 0.0, atol=1e-9)

    def test_lane_load_patterning_beats_full_length(self):
        # patterned lane load must give a larger positive moment than the
        # full-length placement on a continuous beam
        sup = [0.0, 50.0, 100.0]
        env = lane_load_envelope(sup, 0.64, n=401)
        full = ContinuousBeam(sup).add_udl(0.64)
        _, _, m_full = full.diagrams(n=401)
        assert max(env["m_max"]) > max(m_full) + 1e-6
        # and the all-spans pattern is included, so the negative envelope
        # is at least as severe as the full-length case
        assert min(env["m_min"]) <= min(m_full) + 1e-9


class TestToolLoads:
    def test_barrier_catalog_weights(self):
        # SBR-1 (42 in): 588 in^2 * 150 pcf = 0.6125 klf
        assert pytest.approx(barrier_weight_klf("SBR-1 (42 in)"),
                             rel=1e-6) == 588.0 / 144.0 * 0.150
        # steel tube railing comes from the catalog plf
        assert pytest.approx(barrier_weight_klf(
            "TST-2 (three steel tube)")) == 0.080
        assert all(barrier_weight_klf(b) > 0 for b in BARRIER_CHOICES)
        with pytest.raises(KeyError):
            barrier_weight_klf("not a barrier")

    def test_load_derivation_matches_hand_statics(self):
        cfg = BridgeConfig(n_spans=3, span_ft=50.0, girder="W24X104",
                           n_girders=5, spacing_ft=7.0, overhang_ft=2.5,
                           deck_t_in=8.5, barrier="SBR-1 (42 in)",
                           fws_ksf=0.060)
        loads = compute_loads(cfg)
        i, e = loads["interior"], loads["exterior"]
        # tributary widths
        assert i.trib_ft == 7.0
        assert e.trib_ft == 7.0 / 2 + 2.5
        # deck: trib * t/12 * 0.150
        assert pytest.approx(i.deck_klf, rel=1e-6) == 7.0 * 8.5 / 12 * 0.150
        # both barriers shared by 5 girders
        assert pytest.approx(i.dc2_klf, rel=1e-4) == 2 * 0.6125 / 5
        assert i.dc2_klf == e.dc2_klf
        # FWS on the tributary width
        assert pytest.approx(e.dw_klf, rel=1e-6) == 0.060 * 6.0
        # lever rule by hand: de = 2.5 - 1.5 = 1.0 ft; wheels at 1 and 7 ft
        # from the exterior girder -> g = (6 + 0)/(2*7) * 1.2
        lever = (7.0 - 1.0) / (2 * 7.0) * 1.2
        assert e.df_moment >= lever - 1e-9
        # deflection DF: roadway = 33 - 2*1.5 = 30 ft -> 2 lanes, m = 1.0
        assert pytest.approx(i.df_deflection, rel=1e-6) == 1.0 * 2 / 5

    def test_hs20_impact_from_span(self):
        cfg = BridgeConfig(vehicle="HS20-44 (truck only, Std. Spec. impact)",
                           span_ft=50.0)
        loads = compute_loads(cfg)
        assert pytest.approx(loads["interior"].im, rel=1e-6) == 50 / 175
        assert loads["interior"].lane_klf == 0.0

    def test_analyze_single_span_totals(self):
        # dead-load diagram of the assembled tool must match wl^2/8 by hand
        cfg = BridgeConfig(n_spans=1, span_ft=40.0)
        res = analyze(cfg, n=201)
        g = res.girders["interior"]
        w = g.loads.dead_total_klf
        assert pytest.approx(max(g.m_dead), rel=1e-3) == w * 40.0**2 / 8
        # live load adds, in the right directions
        assert max(g.m_total_pos) > max(g.m_dead)
        assert min(g.d_total) < min(g.d_dead) < 0.0
        # single span: no negative live-load moment away from the supports
        mid = len(g.stations) // 2
        assert g.m_ll_neg[mid] >= -1e-6

    def test_analyze_continuous_has_negative_regions(self):
        res = analyze(BridgeConfig(n_spans=2, span_ft=40.0), n=201)
        g = res.girders["exterior"]
        assert min(g.m_total_neg) < min(g.m_dead) < 0.0
        assert max(g.v_ll_pos) > 0.0 > min(g.v_ll_neg)
