#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
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

"""
Tests for civilpy.structural.concrete.AnchorBolts.

Reference values are taken from AISC Design Guide 1, 3rd Edition (2024),
Examples 4.7-3 and 4.7-4, which use ACI 318-19 Chapter 17.

All loads in lb, lengths in inches, stresses in psi.
"""

import math
import pytest
from civilpy.structural.concrete import AnchorBolts, ShearLugCheck, _unc_stress_area


# ─────────────────────────────────────────────────────────────────────────────
# Helper tolerance
# ─────────────────────────────────────────────────────────────────────────────

TOL = 0.015  # ±1.5 % to allow for published rounding


def close(value, expected, tol=TOL):
    return abs(value - expected) / expected <= tol


# ─────────────────────────────────────────────────────────────────────────────
# UNC thread area helper
# ─────────────────────────────────────────────────────────────────────────────

class TestUncStressArea:
    def test_7_8_dia(self):
        # ASTM F1554 Table: 7/8-in rod → A_se = 0.462 in²
        assert close(_unc_stress_area(0.875), 0.462)

    def test_3_4_dia(self):
        # 3/4-in rod → A_se ≈ 0.334 in²
        assert close(_unc_stress_area(0.75), 0.334)

    def test_1_in_dia(self):
        # 1-in rod → A_se ≈ 0.606 in²
        assert close(_unc_stress_area(1.00), 0.606)


# ─────────────────────────────────────────────────────────────────────────────
# Example 4.7-3 — Concentric Axial Tension Load
# AISC DG1 p. 70–75
#
# Given:
#   W10×45 column, large spread footing (no edge effects)
#   4 rods in 4"×4" pattern (2×2 group, s=4" each direction)
#   7/8"-dia ASTM F1554 Gr 36: f_ya=36 ksi, f_uta=58 ksi
#   f'c = 4,000 psi, h_ef = 15 in
#   N_ua = 70,000 lb (total uplift, LRFD)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def ex473():
    """Example 4.7-3 anchor group (no edge effects)."""
    return AnchorBolts(
        f_c=4_000,
        h_a=48.0,           # large footing depth
        d_a=0.875,          # 7/8 in
        h_ef=15.0,
        f_ya=36_000,
        f_uta=58_000,
        n_x=2, n_y=2,
        s_x=4.0, s_y=4.0,
        c_a1=100.0,         # far from edges
        c_a2=100.0,
        A_se_N=0.462,       # per AISC DG1 Table 4-1
        is_cracked=True,
        has_supp_reinf=False,
        is_ductile=True,
        N_ua=70_000,
    )


class TestEx473SteelTension:
    def test_N_sa_per_rod(self, ex473):
        # R_n = F_u * A_se = 58 ksi * 0.462 in² = 26.8 kips (per rod)
        r = ex473.steel_tension_strength()
        N_sa_per_rod = r.N_n / 4   # total / 4 rods
        assert close(N_sa_per_rod, 26_800)

    def test_phi_N_sa_per_rod(self, ex473):
        # phi = 0.75, phi*N_sa = 0.75 * 26.8 = 20.1 kips per rod
        r = ex473.steel_tension_strength()
        phi_Nn_per_rod = r.phi_Sn / 4
        assert close(phi_Nn_per_rod, 20_100)

    def test_steel_tension_ok(self, ex473):
        # 70 kips demand < 4 * 20.1 = 80.4 kips capacity
        r = ex473.steel_tension_strength()
        assert r.ok


class TestEx473ProjectedArea:
    def test_A_Nco(self, ex473):
        # A_Nco = 9 * h_ef² = 9 * 15² = 2,025 in²
        assert close(ex473._A_Nco(), 2_025)

    def test_A_Nc_group(self, ex473):
        # A_Nc = (1.5*15 + 4 + 1.5*15)² = 49² = 2,401 in²  (DG1 rounds to 2,400)
        assert close(ex473._A_Nc, 2_401, tol=0.002)


class TestEx473BreakoutTension:
    def test_N_b_formula(self, ex473):
        # 11 ≤ h_ef ≤ 25 → Eq. 17.6.2.2.3
        # N_b = 16 * 1.0 * sqrt(4000) * 15^(5/3) / 1000 = 92.3 kips
        N_b = ex473._N_b()
        assert close(N_b, 92_300)

    def test_psi_ed_N_no_edge(self, ex473):
        # c_a_min >> 1.5*h_ef → psi_ed,N = 1.0
        assert ex473._psi_ed_N() == pytest.approx(1.0)

    def test_N_cbg(self, ex473):
        # N_cbg = (2400/2025) * 1.0 * 1.0 * 1.0 * 1.0 * 92,300 = 109,300 lb ≈ 109 kips
        r = ex473.breakout_strength_tension()
        assert close(r.N_n, 109_000)

    def test_phi_N_cbg(self, ex473):
        # phi = 0.70, phi*N_cbg = 0.70 * 109 = 76.3 kips
        r = ex473.breakout_strength_tension()
        assert close(r.phi_Sn, 76_300)

    def test_breakout_tension_ok(self, ex473):
        # 70 kips < 76.3 kips
        assert ex473.breakout_strength_tension().ok


class TestEx473PulloutHooked:
    """Example 4.7-3 also checks a 3.5-in hook (NOT adequate, showing N.G.)."""

    def test_hooked_pullout_ng(self):
        # 7/8" rod, e_h = 3.5 - 7/8 = 2.625 in (inside hook to bearing)
        # N_p = 0.9 * 4000 * 2.625 * 0.875 = 8,269 lb ≈ 8.28 kips (per rod)
        # phi*N_pn = 0.70 * 8.28 = 5.80 kips < 17.5 kips demand per rod → N.G.
        ab = AnchorBolts(
            f_c=4_000, h_a=48.0, d_a=0.875, h_ef=15.0,
            f_ya=36_000, f_uta=58_000,
            n_x=2, n_y=2, s_x=4.0, s_y=4.0,
            c_a1=100.0, c_a2=100.0,
            A_se_N=0.462,
            e_h=2.625,   # hook length
            is_cracked=True, has_supp_reinf=False,
            N_ua=70_000,
        )
        r = ab.pullout_strength()
        assert r is not None
        # phi=0.70 for cast-in anchors (ACI 318 Table 17.5.3(c))
        # phi*N_pn per rod = 0.70 * 8.28 = 5.80 kips
        phi_Nn_per_rod = r.phi_Sn / 4
        assert close(phi_Nn_per_rod, 5_800)
        assert not r.ok   # NOT adequate

    def test_hook_length_validation(self):
        # e_h outside [3*d_a, 4.5*d_a] should raise
        with pytest.raises(ValueError):
            ab = AnchorBolts(
                f_c=4_000, h_a=48.0, d_a=0.875, h_ef=15.0,
                f_ya=36_000, f_uta=58_000,
                n_x=1, n_y=1,
                c_a1=100.0, c_a2=100.0,
                e_h=1.0,    # too short: < 3*0.875 = 2.625
                N_ua=10_000,
            )
            ab.pullout_strength()


# ─────────────────────────────────────────────────────────────────────────────
# Example 4.7-4 — Concentric Shear Load (Limited by Edge Distance)
# AISC DG1 p. 76–78
#
# Given:
#   4 rods, 3/4"-dia ASTM F1554 Gr 36: f_ua=58 ksi
#   4"×4" pattern, f'c=4,000 psi
#   c_a1=12 in (edge in shear direction), c_a2 >= 18 in, h_a >= 18 in
#   Only 2 rods nearest to edge resist shear (Case 3 — not welded to plate)
#   V_ua = 17,300 lb (2 × φR_nv = 2 × 8.63 kips per rod)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def ex474():
    """Example 4.7-4 shear group (2 rods controlling; modeled as 2-rod group)."""
    # Model the 2 critical rods in a 1×2 configuration
    return AnchorBolts(
        f_c=4_000,
        h_a=36.0,       # large member, h_a >> 1.5*c_a1
        d_a=0.75,
        h_ef=8.0 * 0.75,   # h_ef >= 8*d_a per example condition
        f_ya=36_000,
        f_uta=58_000,
        n_x=1, n_y=2,
        s_x=0.0, s_y=4.0,
        c_a1=12.0,
        c_a2=18.0,          # c_a2 >= 1.5*c_a1 = 18 in (no perpendicular edge reduction)
        A_se_N=0.334,       # 3/4" rod threaded area
        A_se_V=0.334,
        is_cracked=True,
        has_supp_reinf=False,
        is_ductile=True,
        V_ua=17_300,
    )


class TestEx474ProjectedAreaShear:
    def test_A_Vco(self, ex474):
        # A_Vco = 4.5 * c_a1² = 4.5 * 144 = 648 in²
        assert close(ex474._A_Vco(), 648.0)

    def test_A_Vc_group(self, ex474):
        # A_Vc = 1.5*c_a1 * (1.5*c_a1 + s + 1.5*c_a1) = 18*(18+4+18) = 720 in²
        ab = AnchorBolts(
            f_c=4_000, h_a=36.0, d_a=0.75, h_ef=6.0,
            f_ya=36_000, f_uta=58_000,
            n_x=1, n_y=2, s_y=4.0,
            c_a1=12.0, c_a2=18.0,
            V_ua=17_300,
        )
        assert close(ab._A_Vc, 720.0)


class TestEx474BreakoutShear:
    def test_V_b_upper_bound(self, ex474):
        # h_ef = 6 in >= 8*d_a = 6 in, so use upper bound Eq. 17.7.2.2.1b
        # V_b = 9 * 1.0 * sqrt(4000) * 12^1.5 = 23,700 lb ≈ 23.7 kips
        V_b = ex474._V_b
        assert close(V_b, 23_700)

    def test_psi_ed_V_no_reduction(self, ex474):
        # c_a2=18 >= 1.5*c_a1=18 → psi_ed,V = 1.0
        assert ex474._psi_ed_V() == pytest.approx(1.0)

    def test_psi_h_V_no_reduction(self, ex474):
        # h_a=36 >> 1.5*c_a1=18 → psi_h,V = 1.0
        assert ex474._psi_h_V() == pytest.approx(1.0)

    def test_V_cbg(self, ex474):
        # V_cbg = (720/648) * 1.0*1.0*1.0*1.0 * 23,700 = 26,333 lb ≈ 26.3 kips
        r = ex474.breakout_strength_shear()
        assert close(r.N_n + r.V_n, 26_300)

    def test_phi_V_cbg(self, ex474):
        # phi = 0.70, phi*V_cbg = 0.70 * 26.3 = 18.4 kips > 17.3 kips
        r = ex474.breakout_strength_shear()
        assert close(r.phi_Sn, 18_400)

    def test_shear_breakout_ok(self, ex474):
        assert ex474.breakout_strength_shear().ok


# ─────────────────────────────────────────────────────────────────────────────
# Phi factor tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPhiFactors:
    def test_ductile_steel_phi(self):
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, is_ductile=True)
        assert ab.phi_steel_tension == pytest.approx(0.75)
        assert ab.phi_steel_shear   == pytest.approx(0.65)

    def test_brittle_steel_phi(self):
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, is_ductile=False)
        assert ab.phi_steel_tension == pytest.approx(0.65)
        assert ab.phi_steel_shear   == pytest.approx(0.60)

    def test_no_supp_reinf_phi_concrete(self):
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, has_supp_reinf=False)
        assert ab.phi_concrete == pytest.approx(0.70)

    def test_supp_reinf_phi_concrete(self):
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, has_supp_reinf=True)
        assert ab.phi_concrete == pytest.approx(0.75)

    def test_f_c_cap_10000(self):
        # ACI 318 17.3.1 caps f'c at 10,000 psi for cast-in anchors
        ab = AnchorBolts(12_000, 24, 0.75, 12, 36000, 58000)
        assert ab.f_c == pytest.approx(10_000)

    def test_f_uta_cap(self):
        # f_uta capped at min(1.9*f_ya, 125,000)
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 200_000)
        assert ab.f_uta == pytest.approx(min(1.9 * 36_000, 125_000))


# ─────────────────────────────────────────────────────────────────────────────
# Modification factor unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestModificationFactors:
    def test_psi_ec_N_concentric(self):
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, e_N_prime=0.0)
        assert ab._psi_ec_N() == pytest.approx(1.0)

    def test_psi_ec_N_eccentric(self):
        # e_N' = 6, h_ef = 12 → 1/(1 + 6/18) = 1/1.333 = 0.75
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, e_N_prime=6.0)
        assert ab._psi_ec_N() == pytest.approx(0.75)

    def test_psi_ed_N_no_edge(self):
        # c_a_min = 100 >> 1.5*12 = 18 → 1.0
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, c_a1=100, c_a2=100)
        assert ab._psi_ed_N() == pytest.approx(1.0)

    def test_psi_ed_N_near_edge(self):
        # c_a_min=9, h_ef=12 → 0.7 + 0.3*(9/18) = 0.7+0.15 = 0.85
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, c_a1=9, c_a2=9)
        assert ab._psi_ed_N() == pytest.approx(0.85)

    def test_psi_c_N_cracked(self):
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, is_cracked=True)
        assert ab._psi_c_N() == pytest.approx(1.0)

    def test_psi_c_N_uncracked(self):
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, is_cracked=False)
        assert ab._psi_c_N() == pytest.approx(1.25)

    def test_psi_ec_V_concentric(self):
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, c_a1=12, e_V_prime=0.0)
        assert ab._psi_ec_V() == pytest.approx(1.0)

    def test_psi_ec_V_eccentric(self):
        # e_V' = 3, c_a1 = 6 → 1/(1+3/9) = 0.75
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, c_a1=6, e_V_prime=3.0)
        assert ab._psi_ec_V() == pytest.approx(0.75)

    def test_psi_ed_V_no_reduction(self):
        # c_a2 >= 1.5*c_a1 → 1.0
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, c_a1=8, c_a2=12)
        assert ab._psi_ed_V() == pytest.approx(1.0)

    def test_psi_ed_V_reduced(self):
        # c_a2=6, c_a1=8 → 0.7 + 0.3*(6/12) = 0.85
        ab = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, c_a1=8, c_a2=6)
        assert ab._psi_ed_V() == pytest.approx(0.85)

    def test_psi_h_V_applies(self):
        # h_a=12 < 1.5*c_a1=18 → sqrt(18/12) = sqrt(1.5) ≈ 1.225
        ab = AnchorBolts(4000, 12, 0.75, 12, 36000, 58000, c_a1=12)
        assert ab._psi_h_V() == pytest.approx(math.sqrt(1.5))

    def test_psi_h_V_no_effect(self):
        # h_a >> 1.5*c_a1 → 1.0
        ab = AnchorBolts(4000, 36, 0.75, 12, 36000, 58000, c_a1=12)
        assert ab._psi_h_V() == pytest.approx(1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Interaction check
# ─────────────────────────────────────────────────────────────────────────────

class TestInteraction:
    def test_tension_only_no_interaction(self):
        ab = AnchorBolts(
            4000, 36, 0.75, 12, 36000, 58000,
            c_a1=100, c_a2=100,
            N_ua=20_000, V_ua=0,
        )
        checks = ab.check_all()
        assert "Tension-shear interaction" not in checks

    def test_shear_only_no_interaction(self):
        ab = AnchorBolts(
            4000, 36, 0.75, 12, 36000, 58000,
            c_a1=12, c_a2=18,
            N_ua=0, V_ua=10_000,
        )
        checks = ab.check_all()
        assert "Tension-shear interaction" not in checks

    def test_both_triggers_interaction(self):
        ab = AnchorBolts(
            4000, 36, 0.75, 12, 36000, 58000,
            c_a1=12, c_a2=18,
            N_ua=10_000, V_ua=5_000,
        )
        checks = ab.check_all()
        assert "Tension-shear interaction" in checks

    def test_interaction_limit_1_2(self):
        # If both ratios are 0.4 each, sum = 0.8 < 1.2 → OK
        ab = AnchorBolts(
            4000, 48, 1.0, 12, 36000, 58000,
            n_x=2, n_y=2, s_x=6.0, s_y=6.0,
            c_a1=100, c_a2=100,
            A_se_N=0.606, A_se_V=0.606,
            N_ua=10_000, V_ua=5_000,
        )
        r = ab.tension_shear_interaction()
        assert r.phi_Sn == pytest.approx(1.2)


# ─────────────────────────────────────────────────────────────────────────────
# Side-face blowout (triggered / not triggered)
# ─────────────────────────────────────────────────────────────────────────────

class TestSideFaceBlowout:
    def test_not_triggered_shallow(self):
        # h_ef = 10, c_a1 = 5 → h_ef = 2.0*c_a1 < 2.5*c_a1 → not triggered
        ab = AnchorBolts(
            4000, 24, 0.75, 10, 36000, 58000,
            c_a1=5.0, c_a2=20.0, A_brg=0.60,
        )
        assert ab.side_face_blowout() is None

    def test_triggered_deep(self):
        # h_ef = 20, c_a1 = 6 → h_ef = 3.33*c_a1 > 2.5*c_a1 → triggered
        ab = AnchorBolts(
            4000, 36, 0.75, 20, 36000, 58000,
            c_a1=6.0, c_a2=30.0, A_brg=0.60,
            N_ua=50_000,
        )
        r = ab.side_face_blowout()
        assert r is not None

    def test_no_A_brg_returns_none(self):
        ab = AnchorBolts(4000, 24, 0.75, 20, 36000, 58000, c_a1=6.0)
        assert ab.side_face_blowout() is None


# ─────────────────────────────────────────────────────────────────────────────
# Pryout
# ─────────────────────────────────────────────────────────────────────────────

class TestPryout:
    def test_kcp_shallow(self):
        # h_ef < 2.5 → k_cp = 1.0
        ab = AnchorBolts(4000, 24, 0.75, 2.0, 36000, 58000, c_a1=12, c_a2=18)
        # V_cp = 1.0 * N_cb
        result_N = ab.breakout_strength_tension()
        result_V = ab.pryout_strength()
        assert close(result_V.V_n, result_N.N_n)

    def test_kcp_deep(self):
        # h_ef >= 2.5 → k_cp = 2.0
        ab = AnchorBolts(4000, 24, 0.75, 8.0, 36000, 58000, c_a1=12, c_a2=18)
        result_N = ab.breakout_strength_tension()
        result_V = ab.pryout_strength()
        assert close(result_V.V_n, 2.0 * result_N.N_n)


# ─────────────────────────────────────────────────────────────────────────────
# Grout pad reduction
# ─────────────────────────────────────────────────────────────────────────────

class TestGroutPad:
    def test_grout_pad_reduces_shear(self):
        ab_no  = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, grout_pad=False)
        ab_yes = AnchorBolts(4000, 24, 0.75, 12, 36000, 58000, grout_pad=True)
        Vn_no  = ab_no.steel_shear_strength().V_n
        Vn_yes = ab_yes.steel_shear_strength().V_n
        assert close(Vn_yes, 0.80 * Vn_no)


# ─────────────────────────────────────────────────────────────────────────────
# Summary / repr
# ─────────────────────────────────────────────────────────────────────────────

class TestSummary:
    def test_summary_runs(self, ex473):
        s = ex473.summary()
        assert "Steel strength (tension)" in s
        assert "Concrete breakout (tension)" in s

    def test_repr(self, ex473):
        r = repr(ex473)
        assert "AnchorBolts" in r
        assert "n=4" in r


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — ACI 318-19 Code Expansions
# ─────────────────────────────────────────────────────────────────────────────

class TestShearDirection:
    """shear_direction parameter: perpendicular (default), parallel, away."""

    def _base(self, **kw):
        return AnchorBolts(
            4_000, 36, 0.75, 8.0, 36_000, 58_000,
            c_a1=12.0, c_a2=18.0, V_ua=10_000, **kw
        )

    def test_away_returns_none(self):
        ab = self._base(shear_direction="away")
        assert ab.breakout_strength_shear() is None

    def test_perpendicular_is_default(self):
        ab = self._base()
        r = ab.breakout_strength_shear()
        assert r is not None
        assert "17.7.2.1" in r.reference

    def test_parallel_doubles_capacity(self):
        perp = self._base(shear_direction="perpendicular")
        para = self._base(shear_direction="parallel")
        # parallel sets psi_ed=1.0 and doubles; if psi_ed was already 1.0
        # (c_a2=18 >= 1.5*c_a1=18) the result is exactly 2× perpendicular
        assert close(para.breakout_strength_shear().V_n,
                     2.0 * perp.breakout_strength_shear().V_n)

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError):
            self._base(shear_direction="diagonal")

    def test_corner_check_triggers_when_c_a2_close(self):
        # c_a2=10 < 1.5*c_a1=18 → corner check active
        ab = AnchorBolts(
            4_000, 36, 0.75, 8.0, 36_000, 58_000,
            c_a1=12.0, c_a2=10.0, V_ua=10_000,
        )
        r = ab.breakout_strength_shear()
        assert r is not None
        assert "corner" in r.reference

    def test_corner_check_inactive_when_c_a2_far(self):
        # c_a2=18 == 1.5*c_a1 → no corner suffix
        ab = self._base()
        r = ab.breakout_strength_shear()
        assert "corner" not in r.reference


class TestPostInstalled:
    """anchor_type="post_installed" uses k_c=17 in _N_b."""

    def test_kc_17_reduces_N_b(self):
        cast_in = AnchorBolts(4_000, 36, 0.75, 8.0, 36_000, 58_000,
                               anchor_type="cast_in")
        post    = AnchorBolts(4_000, 36, 0.75, 8.0, 36_000, 58_000,
                               anchor_type="post_installed")
        # 17 / 24 ≈ 0.708
        assert close(post._N_b(), 17.0 / 24.0 * cast_in._N_b())

    def test_invalid_anchor_type_raises(self):
        with pytest.raises(ValueError):
            AnchorBolts(4_000, 36, 0.75, 8.0, 36_000, 58_000, anchor_type="screw")


class TestAdhesiveBond:
    """anchor_type="adhesive" + tau values enables bond_strength_tension."""

    def _adhesive(self, **kw):
        return AnchorBolts(
            4_000, 24, 0.75, 8.0, 36_000, 58_000,
            anchor_type="adhesive",
            tau_cr=800.0, tau_uncr=1_400.0,
            c_a1=100.0, c_a2=100.0,
            N_ua=20_000, **kw
        )

    def test_bond_check_present(self):
        ab = self._adhesive()
        r = ab.bond_strength_tension()
        assert r is not None
        assert "Bond strength" in r.label

    def test_bond_check_absent_for_cast_in(self):
        ab = AnchorBolts(4_000, 24, 0.75, 8.0, 36_000, 58_000,
                         tau_cr=800, N_ua=10_000)
        assert ab.bond_strength_tension() is None

    def test_bond_check_absent_without_tau(self):
        ab = AnchorBolts(4_000, 24, 0.75, 8.0, 36_000, 58_000,
                         anchor_type="adhesive", N_ua=10_000)
        assert ab.bond_strength_tension() is None

    def test_bond_uses_tau_cr_when_cracked(self):
        ab = self._adhesive(is_cracked=True)
        r = ab.bond_strength_tension()
        # tau_cr=800 → N_ba = 800 * π * 0.75 * 8 = 15,080 lb per anchor
        N_ba_expected = 800.0 * math.pi * 0.75 * 8.0
        assert close(r.N_n / ab.n, N_ba_expected, tol=0.05)


class TestSeismic:
    """sdc parameter applies 0.75 factor to concrete failure modes for SDC C–F."""

    def _pair(self, sdc_str):
        kw = dict(f_c=4_000, h_a=36, d_a=0.75, h_ef=12, f_ya=36_000, f_uta=58_000,
                  c_a1=100, c_a2=100, N_ua=30_000)
        return (AnchorBolts(**kw, sdc="A"),
                AnchorBolts(**kw, sdc=sdc_str))

    def test_no_reduction_sdc_a(self):
        ab_a, ab_b = self._pair("B")
        # Both A and B → no reduction
        assert ab_a._phi_seismic == pytest.approx(1.0)
        assert ab_b._phi_seismic == pytest.approx(1.0)

    def test_reduction_sdc_c(self):
        ab_base, ab_c = self._pair("C")
        assert ab_c._phi_seismic == pytest.approx(0.75)

    def test_concrete_breakout_reduced_for_sdc_c(self):
        ab_base, ab_c = self._pair("C")
        ratio = ab_c.breakout_strength_tension().phi_Sn / ab_base.breakout_strength_tension().phi_Sn
        assert ratio == pytest.approx(0.75)

    def test_steel_not_reduced(self):
        ab_base, ab_c = self._pair("C")
        # Steel limit state is NOT affected by seismic
        ratio = ab_c.steel_tension_strength().phi_Sn / ab_base.steel_tension_strength().phi_Sn
        assert ratio == pytest.approx(1.0)

    def test_sdc_case_insensitive(self):
        ab = AnchorBolts(4_000, 36, 0.75, 12, 36_000, 58_000, sdc="d")
        assert ab._phi_seismic == pytest.approx(0.75)


class TestAnchorReinforcement:
    """anchor_reinf_tension / anchor_reinf_shear replaces concrete breakout."""

    def test_reinf_tension_replaces_breakout(self):
        ab = AnchorBolts(
            4_000, 36, 0.75, 12, 36_000, 58_000,
            c_a1=100, c_a2=100, N_ua=20_000,
            anchor_reinf_tension=50_000,
        )
        checks = ab.check_all()
        assert "Anchor reinforcement (tension)" in checks
        assert "Concrete breakout (tension)" not in checks

    def test_reinf_shear_replaces_breakout(self):
        ab = AnchorBolts(
            4_000, 36, 0.75, 12, 36_000, 58_000,
            c_a1=12, c_a2=18, V_ua=10_000,
            anchor_reinf_shear=30_000,
        )
        checks = ab.check_all()
        assert "Anchor reinforcement (shear)" in checks
        assert "Concrete breakout (shear)" not in checks

    def test_reinf_tension_capacity(self):
        ab = AnchorBolts(
            4_000, 36, 0.75, 12, 36_000, 58_000,
            N_ua=20_000, anchor_reinf_tension=50_000,
        )
        r = ab.check_all()["Anchor reinforcement (tension)"]
        assert r.phi_Sn == pytest.approx(50_000)

    def test_pryout_still_present_with_shear_reinf(self):
        # Pryout is independent of anchor reinforcement (not a breakout substitute)
        ab = AnchorBolts(
            4_000, 36, 0.75, 12, 36_000, 58_000,
            c_a1=12, c_a2=18, V_ua=10_000,
            anchor_reinf_shear=30_000,
        )
        checks = ab.check_all()
        assert "Pryout (shear)" in checks


class TestShearLugCheck:
    """ShearLugCheck: bearing and breakout per ACI 318-19 Section 17.11."""

    def _lug(self, **kw):
        return ShearLugCheck(
            f_c=4_000, h_a=24.0, n_sl=1,
            A_ef_sl=6.0, h_sl=3.0,
            c_a1=12.0, c_a2=float("inf"),
            V_ua=20_000, **kw
        )

    def test_bearing_strength_formula(self):
        lug = self._lug()
        r = lug.bearing_strength()
        # V_brg = 1 * 1.7 * 1.0 * 4000 * 6.0 = 40,800 lb
        assert close(r.V_n, 40_800)

    def test_bearing_phi_applied(self):
        lug = self._lug()
        r = lug.bearing_strength()
        assert close(r.phi_Sn, 0.70 * 40_800)

    def test_breakout_returns_none_when_no_edge(self):
        lug = ShearLugCheck(4_000, 24, 1, 6.0, 3.0, c_a1=float("inf"), V_ua=10_000)
        assert lug.breakout_strength() is None

    def test_breakout_present_near_edge(self):
        lug = self._lug()
        r = lug.breakout_strength()
        assert r is not None
        assert r.V_n > 0

    def test_seismic_reduces_bearing(self):
        lug_a = self._lug(sdc="A")
        lug_c = self._lug(sdc="C")
        ratio = lug_c.bearing_strength().phi_Sn / lug_a.bearing_strength().phi_Sn
        assert ratio == pytest.approx(0.75)

    def test_summary_runs(self):
        s = self._lug().summary()
        assert "Shear lug bearing" in s


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — AASHTO Highway Structures & Modifiers
# ─────────────────────────────────────────────────────────────────────────────

class TestFromCircular:
    """from_circular() classmethod for pole/luminaire/sign bolt circles."""

    def _pole(self, **kw):
        return AnchorBolts.from_circular(
            n_bolts=8,
            bolt_circle_radius=9.0,   # 9-in radius, 18-in bolt circle
            f_c=4_000, h_a=36.0, d_a=1.0, h_ef=18.0,
            f_ya=36_000, f_uta=58_000,
            N_ua=20_000, **kw
        )

    def test_bolt_count_stored(self):
        ab = self._pole()
        assert ab.n == 8

    def test_circular_A_Nc_annular(self):
        ab = self._pole()
        # r_bc=9, cone=1.5*18=27, far from edges (c_a_min=inf)
        # R_out = 9 + 27 = 36, R_in = max(0, 9-27) = 0
        # A_Nc = π * 36² = 4071.5
        expected = math.pi * 36.0 ** 2
        assert close(ab._A_Nc, expected)

    def test_circular_A_Nc_with_inner_ring(self):
        # Large bolt circle where r_bc > 1.5*h_ef → inner hole in projection
        ab = AnchorBolts.from_circular(
            n_bolts=12, bolt_circle_radius=24.0,
            f_c=4_000, h_a=48.0, d_a=1.0, h_ef=10.0,
            f_ya=36_000, f_uta=58_000,
        )
        # cone=15, R_out=24+15=39, R_in=max(0,24-15)=9
        expected = math.pi * (39.0 ** 2 - 9.0 ** 2)
        assert close(ab._A_Nc, expected)

    def test_circular_A_Nc_edge_limited(self):
        # c_a_min = 10 in, cone = 27 in → outer extension is only 10 in
        ab = AnchorBolts.from_circular(
            n_bolts=8, bolt_circle_radius=9.0,
            f_c=4_000, h_a=36.0, d_a=1.0, h_ef=18.0,
            f_ya=36_000, f_uta=58_000,
            c_a1=10.0, c_a2=10.0, c_a_min=10.0,
        )
        # R_out = 9 + min(10, 27) = 19, R_in = 0
        expected = math.pi * 19.0 ** 2
        assert close(ab._A_Nc, expected)


class TestDrilledShaft:
    """shaft_radius + bolt_circle_radius auto-derive c_a1."""

    def test_c_a1_derived_from_shaft(self):
        ab = AnchorBolts.from_circular(
            n_bolts=8, bolt_circle_radius=9.0,
            f_c=4_000, h_a=36.0, d_a=1.0, h_ef=18.0,
            f_ya=36_000, f_uta=58_000,
            shaft_radius=12.0,   # c_a1 = 12 - 9 = 3 in
        )
        assert ab.c_a1 == pytest.approx(3.0)

    def test_c_a1_c_a2_equal_for_round_shaft(self):
        ab = AnchorBolts.from_circular(
            n_bolts=8, bolt_circle_radius=9.0,
            f_c=4_000, h_a=36.0, d_a=1.0, h_ef=18.0,
            f_ya=36_000, f_uta=58_000,
            shaft_radius=12.0,
        )
        assert ab.c_a1 == pytest.approx(ab.c_a2)

    def test_invalid_shaft_raises(self):
        with pytest.raises(ValueError):
            AnchorBolts.from_circular(
                n_bolts=8, bolt_circle_radius=12.0,
                f_c=4_000, h_a=36.0, d_a=1.0, h_ef=18.0,
                f_ya=36_000, f_uta=58_000,
                shaft_radius=10.0,   # r_bolt > r_shaft → invalid
            )

    def test_circular_A_Vc_uses_bolt_circle_diameter(self):
        # c_a1 = 3 in, r_bc = 9 in, h_a = 36 in
        # height = min(1.5*3, 36) = 4.5
        # c_a2_eff = min(3, 1.5*3) = 3
        # width = 3 + 2*9 + 3 = 24
        # A_Vc = 4.5 * 24 = 108
        ab = AnchorBolts.from_circular(
            n_bolts=8, bolt_circle_radius=9.0,
            f_c=4_000, h_a=36.0, d_a=1.0, h_ef=18.0,
            f_ya=36_000, f_uta=58_000,
            shaft_radius=12.0, V_ua=10_000,
        )
        assert close(ab._A_Vc, 108.0)


class TestCouplerDepth:
    """coupler_depth reduces effective h_ef for field repour scenarios."""

    def test_h_ef_reduced(self):
        ab = AnchorBolts(4_000, 36, 0.75, 18.0, 36_000, 58_000,
                         coupler_depth=4.0)
        assert ab.h_ef == pytest.approx(14.0)

    def test_coupler_depth_stored(self):
        ab = AnchorBolts(4_000, 36, 0.75, 18.0, 36_000, 58_000,
                         coupler_depth=4.0)
        assert ab.coupler_depth == pytest.approx(4.0)

    def test_reduced_h_ef_lowers_breakout(self):
        ab_full   = AnchorBolts(4_000, 36, 0.75, 18.0, 36_000, 58_000, N_ua=10_000)
        ab_coupler = AnchorBolts(4_000, 36, 0.75, 18.0, 36_000, 58_000,
                                  coupler_depth=4.0, N_ua=10_000)
        # h_ef goes from 18 → 14; N_b ∝ h_ef^(5/3) (cast-in, 11≤h_ef≤25)
        assert ab_coupler.breakout_strength_tension().N_n < ab_full.breakout_strength_tension().N_n

    def test_invalid_coupler_depth_raises(self):
        with pytest.raises(ValueError):
            AnchorBolts(4_000, 36, 0.75, 18.0, 36_000, 58_000, coupler_depth=18.0)


class TestBoltDemandsFromPole:
    """bolt_demands_from_pole() elastic circular method."""

    def test_pure_moment_tension(self):
        # N_ua = 2*M / (n*r) = 2*100_000 / (8*9) = 2778 lb
        N, V = AnchorBolts.bolt_demands_from_pole(8, 9.0, M_u=100_000)
        assert close(N, 2_778, tol=0.01)
        assert V == pytest.approx(0.0)

    def test_uplift_adds_to_tension(self):
        # Axial: P_u/n = 16_000/8 = 2_000 lb per bolt
        N_no_axial, _ = AnchorBolts.bolt_demands_from_pole(8, 9.0, M_u=100_000)
        N_with_axial, _ = AnchorBolts.bolt_demands_from_pole(8, 9.0, M_u=100_000,
                                                               P_u=16_000)
        assert close(N_with_axial - N_no_axial, 2_000, tol=0.01)

    def test_shear_from_v_u(self):
        # V_ua = V_u/n = 32_000/8 = 4_000 lb per bolt
        _, V = AnchorBolts.bolt_demands_from_pole(8, 9.0, M_u=0, V_u=32_000)
        assert close(V, 4_000, tol=0.01)

    def test_torsion_adds_to_shear(self):
        # V_torsion = T_u/(n*r) = 72_000/(8*9) = 1_000 lb
        _, V_base    = AnchorBolts.bolt_demands_from_pole(8, 9.0, M_u=0, V_u=32_000)
        _, V_with_T  = AnchorBolts.bolt_demands_from_pole(8, 9.0, M_u=0,
                                                           V_u=32_000, T_u=72_000)
        assert close(V_with_T - V_base, 1_000, tol=0.01)

    def test_compression_clamps_tension_at_zero(self):
        # Large downward P_u dominates → max(0, ...) clamps to 0
        N, _ = AnchorBolts.bolt_demands_from_pole(8, 9.0, M_u=10_000, P_u=-200_000)
        assert N == pytest.approx(0.0)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — plot() and from_dxf()
# ─────────────────────────────────────────────────────────────────────────────

import math as _math


class TestPlot:
    """plot() returns (fig, ax) and draws without errors — uses Agg (headless)."""

    @pytest.fixture(autouse=True)
    def _use_agg(self):
        import matplotlib
        matplotlib.use("Agg")

    def _rect(self, **kw):
        defaults = dict(f_c=4_000, h_a=24, d_a=0.75, h_ef=12, f_ya=36_000, f_uta=58_000)
        defaults.update(kw)
        return AnchorBolts(**defaults)

    def test_returns_fig_ax_rectangular(self):
        ab = self._rect()
        result = ab.plot()
        assert isinstance(result, tuple) and len(result) == 2

    def test_axes_is_matplotlib_axes(self):
        from matplotlib.axes import Axes
        _, ax = self._rect().plot()
        assert isinstance(ax, Axes)

    def test_rectangular_with_edges(self):
        ab = self._rect(n_x=2, n_y=2, s_x=6, s_y=6, c_a1=9.0, c_a2=9.0)
        fig, ax = ab.plot(title="edge test")
        assert ax.get_title() == "edge test"

    def test_rectangular_with_demands(self):
        ab = self._rect(N_ua=5_000, V_ua=3_000)
        fig, ax = ab.plot()
        # Two demand annotations → V arrow (annotate) + N label (text)
        # Just confirm it doesn't raise; check at least one text present
        assert len(ax.texts) > 0

    def test_circular_pattern(self):
        ab = AnchorBolts.from_circular(
            n_bolts=8, bolt_circle_radius=9.0,
            f_c=4_000, h_a=24, d_a=0.75, h_ef=12,
            f_ya=36_000, f_uta=58_000,
        )
        fig, ax = ab.plot()
        import matplotlib.pyplot as plt
        plt.close(fig)  # clean up

    def test_circular_with_finite_edges(self):
        ab = AnchorBolts.from_circular(
            n_bolts=6, bolt_circle_radius=9.0,
            f_c=4_000, h_a=24, d_a=0.75, h_ef=12,
            f_ya=36_000, f_uta=58_000,
            c_a1=12.0, c_a2=15.0,
        )
        fig, ax = ab.plot()
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_no_demands_no_text_overlap(self):
        # When neither N_ua nor V_ua is set, no demand text should be present
        ab = self._rect()
        _, ax = ab.plot()
        demand_texts = [t for t in ax.texts
                        if "Nu" in t.get_text() or "Vu" in t.get_text()]
        assert demand_texts == []

    def test_figure_size(self):
        ab = self._rect()
        fig, _ = ab.plot(figsize=(10, 5))
        w, h = fig.get_size_inches()
        assert _math.isclose(w, 10.0) and _math.isclose(h, 5.0)


class TestFromDxf:
    """from_dxf() parses geometry from a DXF and builds AnchorBolts correctly."""

    @pytest.fixture()
    def tmp_dxf(self, tmp_path):
        """Returns a factory: tmp_dxf(bolt_pts, concrete_bbox, bolt_r=0.5)."""
        import ezdxf

        def _make(bolt_pts, concrete_bbox, bolt_r=0.5, path=None):
            doc = ezdxf.new("R2010")
            msp = doc.modelspace()
            for x, y in bolt_pts:
                msp.add_circle((x, y, 0), radius=bolt_r,
                               dxfattribs={"layer": "BOLTS"})
            x0, y0, x1, y1 = concrete_bbox
            pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "CONCRETE"})
            out = path or tmp_path / "test.dxf"
            doc.saveas(str(out))
            return str(out)

        return _make

    def test_circular_detection(self, tmp_dxf):
        # 8 bolts on a 9-in bolt circle centred at origin
        n = 8
        r = 9.0
        pts = [(r * _math.cos(2 * _math.pi * k / n),
                r * _math.sin(2 * _math.pi * k / n)) for k in range(n)]
        path = tmp_dxf(pts, (-20, -20, 20, 20))
        ab = AnchorBolts.from_dxf(path, f_c=4_000, h_a=24, h_ef=12,
                                   f_ya=36_000, f_uta=58_000)
        assert ab.n == n
        assert _math.isclose(ab._bolt_circle_radius, r, rel_tol=0.02)

    def test_rectangular_detection(self, tmp_dxf):
        # 2×3 grid (6-in x-spacing, 4-in y-spacing) — radii vary → not circular
        pts = [(x, y) for x in (-3.0, 3.0) for y in (-4.0, 0.0, 4.0)]
        path = tmp_dxf(pts, (-15, -15, 15, 15))
        ab = AnchorBolts.from_dxf(path, f_c=4_000, h_a=24, h_ef=12,
                                   f_ya=36_000, f_uta=58_000)
        assert ab.n_x == 2 and ab.n_y == 3
        assert _math.isclose(ab.s_x, 6.0, rel_tol=0.01)
        assert _math.isclose(ab.s_y, 4.0, rel_tol=0.01)
        assert ab._bolt_circle_radius is None

    def test_edge_distances_extracted(self, tmp_dxf):
        # Single bolt at origin; concrete box from -12 to +24 in x, -9 to +9 in y
        path = tmp_dxf([(0, 0)], (-12, -9, 24, 9), bolt_r=0.375)
        ab = AnchorBolts.from_dxf(path, f_c=4_000, h_a=18, h_ef=10,
                                   f_ya=36_000, f_uta=58_000)
        # Vertical edges (x=-12 and x=+24) → c_a1; nearest is 12 in
        assert _math.isclose(ab.c_a1, 12.0, rel_tol=0.02)
        # Horizontal edges (y=±9) → c_a2; distance is 9 in
        assert _math.isclose(ab.c_a2, 9.0, rel_tol=0.02)

    def test_bolt_diameter_from_dxf_radius(self, tmp_dxf):
        # Circle radius 0.5 → d_a = 1.0
        path = tmp_dxf([(0, 0)], (-10, -10, 10, 10), bolt_r=0.5)
        ab = AnchorBolts.from_dxf(path, f_c=4_000, h_a=18, h_ef=10,
                                   f_ya=36_000, f_uta=58_000)
        assert _math.isclose(ab.d_a, 1.0, rel_tol=0.01)

    def test_no_bolts_raises(self, tmp_dxf):
        # DXF with no CIRCLE entities on BOLTS layer → ValueError
        import ezdxf as _ezdxf
        doc = _ezdxf.new()
        msp = doc.modelspace()
        msp.add_lwpolyline([(-5, -5), (5, -5), (5, 5), (-5, 5)], close=True,
                           dxfattribs={"layer": "CONCRETE"})
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            p = f.name
        doc.saveas(p)
        try:
            with pytest.raises(ValueError, match="No CIRCLE entities"):
                AnchorBolts.from_dxf(p, f_c=4_000, h_a=18, h_ef=10,
                                     f_ya=36_000, f_uta=58_000)
        finally:
            os.unlink(p)

    def test_missing_ezdxf_raises_import_error(self, monkeypatch):
        import builtins, sys
        real_import = builtins.__import__

        def _block_ezdxf(name, *args, **kwargs):
            if name == "ezdxf":
                raise ImportError("No module named 'ezdxf'")
            return real_import(name, *args, **kwargs)

        # Remove cached module so the lazy import runs fresh
        monkeypatch.setitem(sys.modules, "ezdxf", None)
        monkeypatch.setattr(builtins, "__import__", _block_ezdxf)

        with pytest.raises(ImportError, match="ezdxf"):
            AnchorBolts.from_dxf("dummy.dxf", f_c=4_000, h_a=18, h_ef=10,
                                  f_ya=36_000, f_uta=58_000)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5 — Post-installed uncracked, c_ac splitting factor, stretch length,
#            and from_circular with global pole loads
# ─────────────────────────────────────────────────────────────────────────────

class TestPostInstalledUncracked:
    """psi_c_N = 1.40 and psi_cp_N uses c_ac for post-installed in uncracked concrete."""

    def _post(self, **kw):
        return AnchorBolts(
            4_000, 36, 0.75, 12.0, 36_000, 58_000,
            anchor_type="post_installed",
            is_cracked=False,
            c_a1=100.0, c_a2=100.0,
            **kw,
        )

    def test_psi_c_N_post_installed_uncracked(self):
        ab = self._post()
        assert ab._psi_c_N() == pytest.approx(1.40)

    def test_psi_c_N_cast_in_uncracked_still_1_25(self):
        ab = AnchorBolts(4_000, 36, 0.75, 12.0, 36_000, 58_000,
                         anchor_type="cast_in", is_cracked=False)
        assert ab._psi_c_N() == pytest.approx(1.25)

    def test_psi_c_N_post_installed_cracked_is_1_0(self):
        ab = AnchorBolts(4_000, 36, 0.75, 12.0, 36_000, 58_000,
                         anchor_type="post_installed", is_cracked=True)
        assert ab._psi_c_N() == pytest.approx(1.0)

    def test_c_ac_default_is_2_5_h_ef(self):
        ab = self._post()
        assert ab.c_ac == pytest.approx(2.5 * ab.h_ef)

    def test_c_ac_explicit_overrides_default(self):
        ab = self._post(c_ac=20.0)
        assert ab.c_ac == pytest.approx(20.0)

    def test_psi_cp_N_post_uncracked_far_from_edge(self):
        # c_a_min >> c_ac → ratio >= 1 → psi_cp = 1.0
        ab = self._post(c_a_min=100.0)
        assert ab._psi_cp_N() == pytest.approx(1.0)

    def test_psi_cp_N_post_uncracked_near_edge(self):
        # c_a_min = 10, h_ef = 12 → c_ac default = 30; ratio = 10/30 = 0.333
        # floored at 1/1.5 = 0.667 (Eq. 17.6.2.6.1b lower bound)
        ab = AnchorBolts(
            4_000, 36, 0.75, 12.0, 36_000, 58_000,
            anchor_type="post_installed", is_cracked=False,
            c_a1=10.0, c_a2=10.0, c_a_min=10.0,
        )
        # ACI lower bound is min(c_a_min / c_ac, 1.0) but ≥ 1/1.5
        expected = min(1.0, max(10.0 / (2.5 * 12.0), 1.0 / 1.5))
        assert ab._psi_cp_N() == pytest.approx(expected)

    def test_psi_cp_N_cast_in_is_always_1_0(self):
        ab = AnchorBolts(4_000, 36, 0.75, 12.0, 36_000, 58_000,
                         anchor_type="cast_in", is_cracked=False,
                         c_a1=5.0, c_a2=5.0)
        assert ab._psi_cp_N() == pytest.approx(1.0)

    def test_psi_cp_N_post_cracked_is_1_0(self):
        ab = AnchorBolts(4_000, 36, 0.75, 12.0, 36_000, 58_000,
                         anchor_type="post_installed", is_cracked=True,
                         c_a1=5.0, c_a2=5.0)
        assert ab._psi_cp_N() == pytest.approx(1.0)

    def test_uncracked_breakout_exceeds_cracked(self):
        # Both uncracked factors (1.40 × psi_cp) should give higher N_cb than cracked
        ab_cr = AnchorBolts(4_000, 36, 0.75, 12.0, 36_000, 58_000,
                             anchor_type="post_installed", is_cracked=True,
                             c_a1=100.0, c_a2=100.0)
        ab_un = self._post()
        assert ab_un.breakout_strength_tension().N_n > ab_cr.breakout_strength_tension().N_n


class TestFromCircularWithLoads:
    """from_circular() auto-computes N_ua / V_ua from global pole reactions."""

    def test_auto_N_ua_from_moment(self):
        # 8 bolts, r=9: N_ua = 2*M/(n*r) = 2*100_000/(8*9) ≈ 2778 lb
        ab = AnchorBolts.from_circular(
            n_bolts=8, bolt_circle_radius=9.0,
            f_c=4_000, h_a=36.0, d_a=1.0, h_ef=18.0,
            f_ya=36_000, f_uta=58_000,
            M_u=100_000,
        )
        expected_N = 2.0 * 100_000 / (8 * 9.0)
        assert close(ab.N_ua, expected_N, tol=0.01)

    def test_auto_V_ua_from_shear(self):
        # V_ua = V_u/n = 32_000/8 = 4_000 lb
        ab = AnchorBolts.from_circular(
            n_bolts=8, bolt_circle_radius=9.0,
            f_c=4_000, h_a=36.0, d_a=1.0, h_ef=18.0,
            f_ya=36_000, f_uta=58_000,
            V_u=32_000,
        )
        assert close(ab.V_ua, 4_000, tol=0.01)

    def test_explicit_N_ua_takes_precedence(self):
        # Explicit N_ua kwarg should override computed value
        ab = AnchorBolts.from_circular(
            n_bolts=8, bolt_circle_radius=9.0,
            f_c=4_000, h_a=36.0, d_a=1.0, h_ef=18.0,
            f_ya=36_000, f_uta=58_000,
            M_u=100_000, N_ua=99_999,
        )
        assert ab.N_ua == pytest.approx(99_999)

    def test_no_global_loads_no_auto(self):
        # Without M_u/V_u, N_ua/V_ua default to 0
        ab = AnchorBolts.from_circular(
            n_bolts=8, bolt_circle_radius=9.0,
            f_c=4_000, h_a=36.0, d_a=1.0, h_ef=18.0,
            f_ya=36_000, f_uta=58_000,
        )
        assert ab.N_ua == pytest.approx(0.0)
        assert ab.V_ua == pytest.approx(0.0)


class TestStretchLength:
    """stretch_length_check() for SDC C–F seismic ductile designs."""

    def test_not_sdc_cf_returns_none(self):
        for sdc in ("A", "B"):
            ab = AnchorBolts(4_000, 36, 1.0, 18.0, 36_000, 58_000, sdc=sdc)
            assert ab.stretch_length_check() is None

    def test_sdc_c_returns_result(self):
        ab = AnchorBolts(4_000, 36, 1.0, 18.0, 36_000, 58_000, sdc="C")
        r = ab.stretch_length_check()
        assert r is not None

    def test_demand_is_8_d_a(self):
        # required minimum = 8 * d_a = 8.0 in; demand field holds the required value
        ab = AnchorBolts(4_000, 36, 1.0, 18.0, 36_000, 58_000, sdc="C")
        r = ab.stretch_length_check()
        assert r.demand == pytest.approx(8.0 * 1.0)

    def test_stretch_ok_when_h_ef_adequate(self):
        # h_ef = 18 >> 8*d_a = 8 → OK
        ab = AnchorBolts(4_000, 36, 1.0, 18.0, 36_000, 58_000, sdc="D")
        r = ab.stretch_length_check()
        assert r.ok

    def test_stretch_ng_when_coupler_too_short(self):
        # d_a=1.0, coupler_depth=6.0 → L_stretch=6 < 8*1.0=8 → NG
        ab = AnchorBolts(4_000, 36, 1.0, 18.0, 36_000, 58_000,
                         sdc="C", coupler_depth=6.0)
        r = ab.stretch_length_check()
        assert not r.ok

    def test_stretch_in_check_all_for_sdc_c(self):
        ab = AnchorBolts(4_000, 36, 1.0, 18.0, 36_000, 58_000,
                         sdc="C", N_ua=10_000)
        checks = ab.check_all()
        assert "Stretch length (seismic)" in checks

    def test_stretch_absent_for_sdc_a(self):
        ab = AnchorBolts(4_000, 36, 1.0, 18.0, 36_000, 58_000,
                         sdc="A", N_ua=10_000)
        checks = ab.check_all()
        assert "Stretch length (seismic)" not in checks