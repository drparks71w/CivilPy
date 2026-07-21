#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""AASHTO LRFD-LTS checks.

Reference values come from the validated ``Notebooks/Wind Load Calc.ipynb``
LTS-1 worked problem (the ODOT vandal-fence sign retrofit): a 2.880-in OD x
0.160-in wall Grade 2 pipe post, Fy = 50 ksi, and Ohio's 115-mph 700-yr
wind.  (Kz there used a 2.00 coefficient; the library uses the spec's 2.01,
so pressure-side values shift by 0.5%.)
"""

import math

import pytest

from civilpy.structural.aashto import lts


# ── wind (Art. 3.8) ──────────────────────────────────────────────────────────


def test_height_factor_floor_and_growth():
    assert lts.height_factor(16.0) == pytest.approx(0.8605, abs=1e-3)
    # below 16 ft rides the floor
    assert lts.height_factor(5.0) == lts.height_factor(16.0)
    assert lts.height_factor(50.0) > lts.height_factor(16.0)
    # at the gradient height the profile closes out at 2.01
    assert lts.height_factor(900.0) == pytest.approx(2.01)


def test_velocity_and_design_pressure():
    q = lts.velocity_pressure(115.0, 16.0, kd=0.95, g=1.14)
    assert q == pytest.approx(31.55, abs=0.05)   # notebook printed 31.4 w/ 2.00
    pz = lts.design_wind_pressure(115.0, 16.0, cd=1.167, kd=0.95, g=1.14)
    assert pz == pytest.approx(q * 1.167)


def test_directionality_factors():
    assert lts.directionality_factor("round") == 0.95
    assert lts.directionality_factor() == 1.00
    with pytest.raises(KeyError):
        lts.directionality_factor("dodecagonal")


def test_cd_cylinder_regimes():
    # 2.880-in post at 115 mph: CvVd = 0.8*115*0.24 = 22.1 -> 1.10
    assert lts.cd_cylinder(2.880 / 12.0, 115.0) == pytest.approx(1.10)
    # transition regime, and continuity at both edges
    mid = lts.cd_cylinder(50.0 / (0.8 * 115.0), 115.0)
    assert mid == pytest.approx(129.0 / 50.0**1.3)
    at_39 = lts.cd_cylinder(39.0 / (0.8 * 115.0), 115.0)
    just_past = lts.cd_cylinder(39.1 / (0.8 * 115.0), 115.0)
    assert at_39 == pytest.approx(1.10)
    assert just_past == pytest.approx(129.0 / 39.1**1.3, rel=1e-6)
    assert abs(just_past - 1.10) < 0.01
    # supercritical
    assert lts.cd_cylinder(100.0 / (0.8 * 115.0), 115.0) == pytest.approx(0.45)


def test_cd_sign_panel():
    # notebook: 5 ft x 3 ft panel, L/W = 1.67 -> 1.167
    assert lts.cd_sign_panel(5.0, 3.0) == pytest.approx(1.1667, abs=1e-3)
    # orientation-independent, clamped at both table ends, exact at knots
    assert lts.cd_sign_panel(3.0, 5.0) == lts.cd_sign_panel(5.0, 3.0)
    assert lts.cd_sign_panel(1.0, 1.0) == 1.12
    assert lts.cd_sign_panel(40.0, 1.0) == 1.30
    assert lts.cd_sign_panel(10.0, 1.0) == pytest.approx(1.23)
    with pytest.raises(ValueError):
        lts.cd_sign_panel(0.0, 3.0)


def test_mri_and_ohio_speeds():
    assert lts.MRI_YEARS["typical"] == 700
    assert lts.OHIO_WIND_SPEEDS[700] == 115.0
    assert lts.OHIO_WIND_SPEEDS[10] == 76.0


def test_load_combinations_table():
    extreme = lts.LTS_LOAD_COMBINATIONS["Extreme I"]
    assert extreme["W"] == 1.0
    assert extreme["DC_max"] == 1.1
    assert extreme["DC_min"] == 0.9
    fatigue = lts.LTS_LOAD_COMBINATIONS["Fatigue I"]
    assert fatigue["galloping"] == fatigue["natural_wind_gust"] == 1.0


# ── steel (Section 5) ────────────────────────────────────────────────────────


VPF_POST = lts.RoundTube(od=2.880, t=0.160)


def test_round_tube_properties_match_notebook():
    assert VPF_POST.area == pytest.approx(1.367, abs=1e-3)
    assert VPF_POST.inertia == pytest.approx(1.269, abs=1e-3)
    assert VPF_POST.section_modulus == pytest.approx(0.881, abs=1e-3)
    assert VPF_POST.plastic_modulus == pytest.approx(1.185, abs=1e-3)
    assert VPF_POST.radius_of_gyration == pytest.approx(0.963, abs=1e-3)
    with pytest.raises(ValueError):
        lts.RoundTube(od=1.0, t=0.5)


def test_flexure_compact_matches_notebook():
    result = lts.round_tube_flexural_resistance(VPF_POST, f_y=50.0, m_u=31.5)
    assert result.details["slenderness"] == "compact"
    assert result.details["D/t"] == pytest.approx(18.0)
    assert result.details["lambda_p"] == pytest.approx(40.6, abs=0.1)
    # phi*Mn = 0.9 * 50 * 1.185 = 53.3 kip-in; D/C = 0.59
    assert result.factored_capacity == pytest.approx(53.3, abs=0.1)
    assert result.ok
    assert result.demand / result.factored_capacity == pytest.approx(0.59, abs=0.01)


def test_flexure_noncompact_and_slender_branches():
    thin = lts.RoundTube(od=10.0, t=0.10)          # D/t = 100, between 40.6 and 179.8
    r = lts.round_tube_flexural_resistance(thin, f_y=50.0)
    assert r.details["slenderness"] == "noncompact"
    assert r.capacity == pytest.approx((0.021 * 29000.0 / 100.0 + 50.0) * thin.section_modulus)

    slender = lts.RoundTube(od=20.0, t=0.10)       # D/t = 200 > 179.8
    r2 = lts.round_tube_flexural_resistance(slender, f_y=50.0)
    assert r2.details["slenderness"] == "slender"
    assert r2.capacity == pytest.approx(0.33 * 29000.0 / 200.0 * slender.section_modulus)

    with pytest.raises(ValueError, match="0.45E/Fy"):
        lts.round_tube_flexural_resistance(lts.RoundTube(od=30.0, t=0.10), f_y=50.0)


def test_compression_matches_notebook():
    # 6-ft cantilever, K = 2.1: KL/r = 157, Fe = 11.6 ksi, Pr = 12.5 kip
    result = lts.compression_resistance(
        area=VPF_POST.area,
        radius_of_gyration=VPF_POST.radius_of_gyration,
        unbraced_length=72.0,
        f_y=50.0,
        p_u=0.188,
    )
    assert result.details["KL/r"] == pytest.approx(157.0, abs=0.5)
    assert result.details["Fe"] == pytest.approx(11.6, abs=0.1)
    assert result.factored_capacity == pytest.approx(12.54, abs=0.05)
    assert result.ok


def test_compression_inelastic_branch():
    # stubby column: Fy/Fe <= 2.25 -> 0.658^(Fy/Fe) curve
    result = lts.compression_resistance(
        area=VPF_POST.area,
        radius_of_gyration=VPF_POST.radius_of_gyration,
        unbraced_length=12.0,
        f_y=50.0,
        k=1.0,
    )
    fe = result.details["Fe"]
    assert 50.0 / fe <= 2.25
    assert result.details["Fcr"] == pytest.approx(0.658 ** (50.0 / fe) * 50.0)


def test_interaction_matches_notebook():
    # Pu = 0.188 k, Pr = 12.54 k, Mu = 31.5 k-in, Mr = 53.3 k-in, Pe from KL = 2.1*72
    p_e = math.pi**2 * 29000.0 * VPF_POST.inertia / (2.1 * 72.0) ** 2
    assert p_e == pytest.approx(15.9, abs=0.1)
    assert lts.moment_magnifier(0.188, p_e) == pytest.approx(1.012, abs=1e-3)
    result = lts.combined_force_interaction(
        p_u=0.188, p_r=12.54, m_u=31.5, m_r=53.3, p_e=p_e
    )
    assert result.details["equation"] == "5.12.1-3"
    assert result.demand == pytest.approx(0.60, abs=0.01)
    assert result.ok


def test_interaction_high_axial_branch_and_instability():
    result = lts.combined_force_interaction(p_u=5.0, p_r=12.5, m_u=10.0, m_r=53.3)
    assert result.details["equation"] == "5.12.1-2"
    assert result.demand == pytest.approx(5.0 / 12.5 + (8.0 / 9.0) * 10.0 / 53.3)
    with pytest.raises(ValueError, match="unstable"):
        lts.moment_magnifier(20.0, 15.9)


def test_article_registry_populated():
    for number in ("5.8.2", "5.10", "5.12.1"):
        assert number in lts.LTS_ARTICLES


# ── fatigue (Section 11) ─────────────────────────────────────────────────────


def test_fatigue_pressures_match_notebook():
    assert lts.galloping_pressure() == 21.0
    assert lts.galloping_pressure(0.5) == 10.5
    # notebook: Cd = 1.167 -> P_NW = 6.1 psf
    assert lts.natural_wind_gust_pressure(1.167) == pytest.approx(6.07, abs=0.01)


def test_tube_to_plate_caft_bands():
    assert lts.tube_to_plate_caft(3.0) == 7.0
    assert lts.tube_to_plate_caft(4.0) == 7.0
    assert lts.tube_to_plate_caft(5.0) == 4.5
    assert lts.tube_to_plate_caft(7.0) == 2.6
    # geometry outside the K_I calibration window -> the 2.6-ksi floor
    assert lts.tube_to_plate_caft(None) == 2.6
    assert lts.tube_to_plate_caft() == 2.6
    with pytest.raises(ValueError, match="7.7"):
        lts.tube_to_plate_caft(8.0)
    assert lts.ANCHOR_ROD_CAFT == 7.0
