"""Tests for the multicell-box, spread-box, and box-shear distribution
factors and the timber adjustment-factor tables."""

import pytest

from civilpy.structural.aashto.lrfd.distribution import (
    moment_df_interior_multicell, shear_df_interior_multicell,
    moment_df_interior_spread_box, shear_df_interior_spread_box,
    shear_df_interior_box)
from civilpy.structural.aashto.lrfd.timber import (
    wet_service_cm, flat_use_cfu, deck_factor_cd,
    timber_tension_resistance, timber_compression_resistance,
    column_stability_cp)


# ── Distribution factors ───────────────────────────────────────────────────


def test_multicell_moment_df_hand_check():
    df = moment_df_interior_multicell(s_ft=9.0, l_ft=120.0, n_cells=4)
    one = (1.75 + 9.0 / 3.6) * (1.0 / 120.0) ** 0.35 * (1.0 / 4) ** 0.45
    multi = (13.0 / 4) ** 0.3 * (9.0 / 5.8) * (1.0 / 120.0) ** 0.25
    assert df.one_lane == pytest.approx(one)
    assert df.multi_lane == pytest.approx(multi)
    assert df.applicable
    # the Nc > 8 note caps the cell count used in the formula
    capped = moment_df_interior_multicell(9.0, 120.0, n_cells=10)
    assert capped.one_lane == pytest.approx(
        moment_df_interior_multicell(9.0, 120.0, n_cells=8).one_lane)


def test_multicell_shear_df_hand_check():
    df = shear_df_interior_multicell(s_ft=9.0, l_ft=120.0, d_in=72.0)
    depth = 72.0 / (12.0 * 120.0)
    assert df.one_lane == pytest.approx((9.0 / 9.5) ** 0.6 * depth**0.1)
    assert df.multi_lane == pytest.approx((9.0 / 7.3) ** 0.9 * depth**0.1)


def test_spread_box_dfs_hand_check():
    m = moment_df_interior_spread_box(s_ft=8.0, l_ft=80.0, d_in=39.0)
    term = 8.0 * 39.0 / (12.0 * 80.0**2)
    assert m.one_lane == pytest.approx((8.0 / 3.0) ** 0.35 * term**0.25)
    assert m.multi_lane == pytest.approx((8.0 / 6.3) ** 0.6 * term**0.125)
    assert m.applicable
    v = shear_df_interior_spread_box(s_ft=8.0, l_ft=80.0, d_in=39.0)
    depth = 39.0 / (12.0 * 80.0)
    assert v.one_lane == pytest.approx((8.0 / 10.0) ** 0.6 * depth**0.1)
    assert v.multi_lane == pytest.approx((8.0 / 7.4) ** 0.8 * depth**0.1)
    # past S = 18 ft the table defers to the lever rule
    wide = moment_df_interior_spread_box(s_ft=20.0, l_ft=80.0, d_in=39.0)
    assert not wide.applicable


def test_box_beam_shear_df_hand_check():
    df = shear_df_interior_box(b_in=48.0, l_ft=80.0,
                               i_beam=170000.0, j_beam=200000.0)
    stiff = (170000.0 / 200000.0) ** 0.05
    assert df.one_lane == pytest.approx(
        (48.0 / (130.0 * 80.0)) ** 0.15 * stiff)
    assert df.multi_lane == pytest.approx(
        (48.0 / 156.0) ** 0.4 * (48.0 / 960.0) ** 0.1 * stiff * 1.0)
    # wider beams pick up the b/48 amplifier; narrower ones don't drop
    wide = shear_df_interior_box(60.0, 80.0, 170000.0, 200000.0)
    narrow = shear_df_interior_box(36.0, 80.0, 170000.0, 200000.0)
    assert wide.multi_lane > (60.0 / 156.0) ** 0.4 * (60.0 / 960.0) ** 0.1 \
        * stiff
    assert narrow.multi_lane == pytest.approx(
        (36.0 / 156.0) ** 0.4 * (36.0 / 960.0) ** 0.1 * stiff)


# ── Timber adjustment factors ──────────────────────────────────────────────


def test_wet_service_sawn_values_and_waivers():
    assert wet_service_cm("flexure") == pytest.approx(0.85)
    assert wet_service_cm("shear") == pytest.approx(0.97)
    assert wet_service_cm("bearing") == pytest.approx(0.67)
    assert wet_service_cm("compression") == pytest.approx(0.80)
    assert wet_service_cm("modulus") == pytest.approx(0.90)
    assert wet_service_cm("tension") == pytest.approx(1.0)
    # footnotes: low reference values are not reduced
    assert wet_service_cm("flexure", f_o_cf=1.10) == pytest.approx(1.0)
    assert wet_service_cm("flexure", f_o_cf=1.30) == pytest.approx(0.85)
    assert wet_service_cm("compression", f_o_cf=0.70) == pytest.approx(1.0)
    # dry service: no reduction at all
    assert wet_service_cm("bearing", wet=False) == pytest.approx(1.0)


def test_wet_service_glulam_values():
    assert wet_service_cm("flexure", glulam=True) == pytest.approx(0.80)
    assert wet_service_cm("shear", glulam=True) == pytest.approx(0.875)
    assert wet_service_cm("bearing", glulam=True) == pytest.approx(0.53)
    assert wet_service_cm("compression", glulam=True) == pytest.approx(0.73)
    assert wet_service_cm("modulus", glulam=True) == pytest.approx(0.833)
    with pytest.raises(ValueError):
        wet_service_cm("torsion")


def test_flat_use_sawn_table():
    assert flat_use_cfu(3.0) == pytest.approx(1.00)
    assert flat_use_cfu(4.0) == pytest.approx(1.10)
    assert flat_use_cfu(6.0) == pytest.approx(1.15)
    assert flat_use_cfu(10.0) == pytest.approx(1.20)
    assert flat_use_cfu(14.0) == pytest.approx(1.20)   # above-10 row
    # 4-in-thick column
    assert flat_use_cfu(4.0, thickness_nominal=4.0) == pytest.approx(1.00)
    assert flat_use_cfu(6.0, thickness_nominal=4.0) == pytest.approx(1.05)
    assert flat_use_cfu(10.0, thickness_nominal=4.0) == pytest.approx(1.10)


def test_flat_use_glulam_formula():
    assert flat_use_cfu(2.5, glulam=True) == pytest.approx(
        (12.0 / 2.5) ** (1.0 / 9.0))
    assert flat_use_cfu(6.75, glulam=True) == pytest.approx(
        (12.0 / 6.75) ** (1.0 / 9.0))
    assert flat_use_cfu(12.0, glulam=True) == pytest.approx(1.0)


def test_deck_factor():
    assert deck_factor_cd("stressed wood") == pytest.approx(1.15)
    assert deck_factor_cd("spike-laminated", 3.0) == pytest.approx(1.15)
    assert deck_factor_cd("nail_laminated") == pytest.approx(1.15)
    assert deck_factor_cd("plank") == pytest.approx(1.0)
    # laminated decks of lumber thicker than 4 in get no increase
    assert deck_factor_cd("spike-laminated", 6.0) == pytest.approx(1.0)


def test_timber_member_resistances():
    t = timber_tension_resistance(f_t_adj=0.9, a_n=30.25, p_u=18.0)
    assert t.capacity == pytest.approx(0.9 * 30.25)
    assert t.phi == pytest.approx(0.80)
    assert t.factored_capacity == pytest.approx(0.8 * 0.9 * 30.25)
    cp = column_stability_cp(f_co_adj=1.5, e_adj=580.0,
                             l_e=120.0, d=5.5).capacity
    c = timber_compression_resistance(f_c_adj=1.5, a_g=30.25,
                                      c_p=cp, p_u=25.0)
    assert c.phi == pytest.approx(0.90)
    assert c.capacity == pytest.approx(1.5 * 30.25 * cp)
    assert 0.0 < cp < 1.0


# ── 5.12.7.3 box culvert slab shear ───────────────────────────────────────


def test_box_culvert_slab_shear_hand_check():
    import math
    from civilpy.structural.aashto.lrfd.concrete import box_culvert_slab_shear
    # 12-in design strip, de = 9 in, f'c = 4 ksi, #6 @ 8 -> 0.66 in^2/ft
    r = box_culvert_slab_shear(b=12.0, d_e=9.0, f_c=4.0, a_s=0.66,
                               v_u=8.0, m_u=200.0)
    ratio = min(8.0 * 9.0 / 200.0, 1.0)
    expected = (0.0676 * math.sqrt(4.0)
                + 4.6 * 0.66 / (12.0 * 9.0) * ratio) * 12.0 * 9.0
    assert r.capacity == pytest.approx(expected)
    assert r.phi == pytest.approx(0.90)
    assert r.details["applicable"]
    # the moment ratio never exceeds 1.0
    high_v = box_culvert_slab_shear(12.0, 9.0, 4.0, 0.66, v_u=50.0,
                                    m_u=100.0)
    assert high_v.details["Vu*de/Mu"] == pytest.approx(1.0)


def test_box_culvert_slab_shear_cap_and_floors():
    import math
    from civilpy.structural.aashto.lrfd.concrete import box_culvert_slab_shear
    # heavy reinforcement pushes Vc to the 0.126*sqrt(f'c) cap
    capped = box_culvert_slab_shear(12.0, 9.0, 4.0, a_s=8.0, v_u=50.0,
                                    m_u=100.0)
    assert capped.capacity == pytest.approx(
        0.126 * math.sqrt(4.0) * 12.0 * 9.0)
    # single-cell floor governs over a lightly reinforced slab
    light = box_culvert_slab_shear(12.0, 9.0, 4.0, a_s=0.1, v_u=2.0,
                                   m_u=500.0, single_cell=True,
                                   monolithic=False)
    assert light.capacity == pytest.approx(
        0.0791 * math.sqrt(4.0) * 12.0 * 9.0)
    mono = box_culvert_slab_shear(12.0, 9.0, 4.0, a_s=0.1, v_u=2.0,
                                  m_u=500.0, single_cell=True)
    assert mono.capacity == pytest.approx(
        0.0948 * math.sqrt(4.0) * 12.0 * 9.0)
    shallow = box_culvert_slab_shear(12.0, 9.0, 4.0, 0.66, 8.0, 200.0,
                                     fill_ft=1.0)
    assert not shallow.details["applicable"]
