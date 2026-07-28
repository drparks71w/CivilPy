#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Appendix D6 tests: the Table D6.1-1 / D6.1-2 plastic-moment solver is
verified against an independent exact equilibrium solver (bisection on the
PNA over the clipped rectangles), the D6.2.2 yield moment against hand
algebra, and D6.3.1 / 6.10.6.2 against limiting geometry."""

import math

import pytest

from civilpy.structural.aashto.lrfd import (
    ARTICLES,
    classify_composite_positive,
    classify_web_negative,
    plastic_moment,
    web_compression_depth_elastic,
    yield_moment_composite,
)


# ---------------------------------------------------------------------------
# independent oracle: exact plastic equilibrium over clipped rectangles
# ---------------------------------------------------------------------------

def _oracle(rects, bars, compression="top"):
    """Exact fully plastic Mp for rectangles [(force_per_depth? no —
    (y_top, y_bot, width_stress)), ...] plus discrete bars [(y, force)].

    ``rects`` entries are (y0, y1, s) with y measured DOWN from a datum,
    y0 < y1, and s = stress * width (kip/in of depth); compression-only
    rectangles (the slab block) get s_comp with s_tens = 0 via a 4th
    element.  Bars are (y, force).  Returns (y_pna, mp).
    """
    def net(y):
        n = 0.0
        for r in rects:
            y0, y1, s, *rest = r
            s_t = rest[0] if rest else s
            above = max(0.0, min(y, y1) - y0)
            below = max(0.0, y1 - max(y, y0))
            if compression == "top":
                n += s * above - s_t * below
            else:
                n += -s_t * above + s * below
        for yb, f in bars:
            if compression == "top":
                n += f if yb < y else -f
            else:
                n += -f if yb < y else f
        return n

    lo = min(r[0] for r in rects)
    hi = max(r[1] for r in rects)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if (net(lo) > 0) == (net(mid) > 0):
            lo = mid
        else:
            hi = mid
    y = 0.5 * (lo + hi)

    mp = 0.0
    for r in rects:
        y0, y1, s, *rest = r
        s_t = rest[0] if rest else s
        a0, a1 = y0, min(y, y1)          # part above the PNA
        if a1 > a0:
            stress = s if compression == "top" else s_t
            mp += stress * (a1 - a0) * abs(y - 0.5 * (a0 + a1))
        b0, b1 = max(y, y0), y1          # part below the PNA
        if b1 > b0:
            stress = s_t if compression == "top" else s
            mp += stress * (b1 - b0) * abs(0.5 * (b0 + b1) - y)
    for yb, f in bars:
        mp += f * abs(yb - y)
    return y, mp


def _positive_rects(*, ts, th, tc, dw, tt, bc, bw_tw, bt, fyc, fyw, fyt,
                    fc, bs):
    """Rectangle list for a positive-flexure composite stack: slab
    (compression-only 0.85 f'c), then the three steel plates."""
    y = 0.0
    rects = [(0.0, ts, 0.85 * fc * bs, 0.0)]      # slab: no tension
    y = ts + th
    rects.append((y, y + tc, fyc * bc))
    rects.append((y + tc, y + tc + dw, fyw * bw_tw))
    rects.append((y + tc + dw, y + tc + dw + tt, fyt * bt))
    return rects


DEMO_FIELD = dict(b_c=16.0, t_c=1.0, f_yc=50.0,
                  d_web=54.0, t_w=0.5, f_yw=50.0,
                  b_t=18.0, t_t=1.375, f_yt=50.0,
                  f_c=4.5, b_s=108.0, t_s=8.5, t_haunch=2.0)


class TestPlasticMomentPositive:
    def test_demo_field_section_case_iii(self):
        res = plastic_moment(flexure="positive", **DEMO_FIELD)
        assert res.case == "III"
        assert res.dcp == 0.0
        y, mp = _oracle(
            _positive_rects(ts=8.5, th=2.0, tc=1.0, dw=54.0, tt=1.375,
                            bc=16.0, bw_tw=0.5, bt=18.0, fyc=50.0,
                            fyw=50.0, fyt=50.0, fc=4.5, bs=108.0), [])
        assert res.y_pna == pytest.approx(y, abs=1e-6)
        assert res.mp == pytest.approx(mp, rel=1e-9)
        # Dp is the PNA depth from the top of the slab (used by 6.10.7.3)
        assert res.dp == pytest.approx(y)
        assert res.dt == pytest.approx(8.5 + 2.0 + 1.0 + 54.0 + 1.375)

    def test_case_i_pna_in_web(self):
        args = dict(DEMO_FIELD, b_s=24.0, t_s=6.0, f_c=3.0,
                    b_t=18.0, t_t=2.5)   # big tension flange, small slab
        res = plastic_moment(flexure="positive", **args)
        assert res.case == "I"
        y, mp = _oracle(
            _positive_rects(ts=6.0, th=2.0, tc=1.0, dw=54.0, tt=2.5,
                            bc=16.0, bw_tw=0.5, bt=18.0, fyc=50.0,
                            fyw=50.0, fyt=50.0, fc=3.0, bs=24.0), [])
        assert res.y_pna == pytest.approx(y, abs=1e-6)
        assert res.mp == pytest.approx(mp, rel=1e-9)
        # Dcp is Y-bar itself for the in-web case
        assert res.dcp == pytest.approx(res.y_bar)

    def test_case_ii_pna_in_top_flange(self):
        args = dict(DEMO_FIELD, b_s=90.0, t_s=8.0, f_c=4.0, t_c=2.0)
        res = plastic_moment(flexure="positive", **args)
        assert res.case == "II"
        y, mp = _oracle(
            _positive_rects(ts=8.0, th=2.0, tc=2.0, dw=54.0, tt=1.375,
                            bc=16.0, bw_tw=0.5, bt=18.0, fyc=50.0,
                            fyw=50.0, fyt=50.0, fc=4.0, bs=90.0), [])
        assert res.y_pna == pytest.approx(y, abs=1e-6)
        assert res.mp == pytest.approx(mp, rel=1e-9)
        assert res.dcp == 0.0

    def test_case_v_between_rebar_layers(self):
        res = plastic_moment(
            flexure="positive",
            b_c=12.0, t_c=1.0, f_yc=50.0, d_web=30.0, t_w=0.5, f_yw=50.0,
            b_t=12.0, t_t=1.0, f_yt=50.0,
            f_c=10.0, b_s=200.0, t_s=8.0, t_haunch=1.0,
            a_rt=1.0, c_rt=1.0, a_rb=1.0, c_rb=6.5, f_yr=60.0)
        assert res.case == "V"
        rects = _positive_rects(ts=8.0, th=1.0, tc=1.0, dw=30.0, tt=1.0,
                                bc=12.0, bw_tw=0.5, bt=12.0, fyc=50.0,
                                fyw=50.0, fyt=50.0, fc=10.0, bs=200.0)
        y, mp = _oracle(rects, [(1.0, 60.0), (6.5, 60.0)])
        assert res.y_pna == pytest.approx(y, abs=1e-6)
        assert res.mp == pytest.approx(mp, rel=1e-9)

    def test_case_vii_above_top_rebar(self):
        res = plastic_moment(
            flexure="positive",
            b_c=8.0, t_c=0.5, f_yc=50.0, d_web=20.0, t_w=0.375, f_yw=50.0,
            b_t=8.0, t_t=0.5, f_yt=50.0,
            f_c=10.0, b_s=200.0, t_s=8.0, t_haunch=1.0,
            a_rt=1.0, c_rt=1.5, a_rb=1.0, c_rb=6.5, f_yr=60.0)
        assert res.case == "VII"
        rects = _positive_rects(ts=8.0, th=1.0, tc=0.5, dw=20.0, tt=0.5,
                                bc=8.0, bw_tw=0.375, bt=8.0, fyc=50.0,
                                fyw=50.0, fyt=50.0, fc=10.0, bs=200.0)
        y, mp = _oracle(rects, [(1.5, 60.0), (6.5, 60.0)])
        assert res.y_pna == pytest.approx(y, abs=1e-6)
        assert res.mp == pytest.approx(mp, rel=1e-9)
        assert res.y_pna < 1.5

    def test_rebar_contribution_is_small_in_positive_flexure(self):
        # the guide's stated justification for neglecting deck rebar in
        # positive flexure: adding a full 6.10.1.7 layout moves Mp by
        # under 2% on the demo section (1.4% here)
        bare = plastic_moment(flexure="positive", **DEMO_FIELD)
        with_bars = plastic_moment(
            flexure="positive", **DEMO_FIELD,
            a_rt=6.2, c_rt=2.81, a_rb=3.41, c_rb=7.19, f_yr=60.0)
        assert abs(with_bars.mp - bare.mp) / bare.mp < 0.02


DEMO_PIER = dict(b_c=20.0, t_c=1.75, f_yc=50.0,
                 d_web=54.0, t_w=0.5625, f_yw=50.0,
                 b_t=18.0, t_t=1.5, f_yt=50.0,
                 t_s=8.5, t_haunch=2.0,
                 a_rt=6.2, c_rt=2.81, a_rb=3.41, c_rb=7.19, f_yr=60.0)


def _negative_rects(*, ts, th, tt, dw, tc, bt, bw_tw, bc, fyt, fyw, fyc):
    y = ts + th
    return [
        (y, y + tt, fyt * bt),
        (y + tt, y + tt + dw, fyw * bw_tw),
        (y + tt + dw, y + tt + dw + tc, fyc * bc),
    ]


class TestPlasticMomentNegative:
    def test_demo_pier_section_case_i(self):
        res = plastic_moment(flexure="negative", **DEMO_PIER)
        assert res.case == "I"
        rects = _negative_rects(ts=8.5, th=2.0, tt=1.5, dw=54.0, tc=1.75,
                                bt=18.0, bw_tw=0.5625, bc=20.0,
                                fyt=50.0, fyw=50.0, fyc=50.0)
        y, mp = _oracle(rects, [(2.81, 6.2 * 60.0), (7.19, 3.41 * 60.0)],
                        compression="bottom")
        assert res.y_pna == pytest.approx(y, abs=1e-6)
        assert res.mp == pytest.approx(mp, rel=1e-9)
        # web below the PNA is in compression at Mp
        assert res.dcp == pytest.approx(54.0 - res.y_bar)

    def test_case_ii_pna_in_tension_flange(self):
        args = dict(DEMO_PIER, b_t=24.0, t_t=3.0,
                    a_rt=10.0, a_rb=8.0)   # top-heavy: PNA leaves the web
        res = plastic_moment(flexure="negative", **args)
        assert res.case == "II"
        rects = _negative_rects(ts=8.5, th=2.0, tt=3.0, dw=54.0, tc=1.75,
                                bt=24.0, bw_tw=0.5625, bc=20.0,
                                fyt=50.0, fyw=50.0, fyc=50.0)
        y, mp = _oracle(rects, [(2.81, 10.0 * 60.0), (7.19, 8.0 * 60.0)],
                        compression="bottom")
        assert res.y_pna == pytest.approx(y, abs=1e-6)
        assert res.mp == pytest.approx(mp, rel=1e-9)
        assert res.dcp == pytest.approx(54.0)   # whole web in compression

    def test_pna_above_steel_raises(self):
        with pytest.raises(ValueError, match="D6.1-2"):
            plastic_moment(flexure="negative", **dict(
                DEMO_PIER, b_c=2.0, t_c=0.25, b_t=2.0, t_t=0.25,
                d_web=10.0, t_w=0.1875, a_rt=50.0, a_rb=50.0))

    def test_bad_flexure_raises(self):
        with pytest.raises(ValueError, match="flexure"):
            plastic_moment(flexure="sideways", **DEMO_FIELD)


class TestYieldMoment:
    def test_hand_algebra(self):
        # bottom flange: MAD = S_st*(Fy - MD1/S_nc - MD2/S_lt)
        res = yield_moment_composite(
            m_d1=12000.0, m_d2=6000.0,
            s_nc_top=1000.0, s_nc_bot=1500.0,
            s_lt_top=2000.0, s_lt_bot=1800.0,
            s_st_top=3000.0, s_st_bot=2000.0,
            f_y_top=50.0, f_y_bot=50.0)
        m_ad_bot = 2000.0 * (50.0 - 12000.0 / 1500.0 - 6000.0 / 1800.0)
        m_ad_top = 3000.0 * (50.0 - 12000.0 / 1000.0 - 6000.0 / 2000.0)
        assert res.m_ad_bot == pytest.approx(m_ad_bot)
        assert res.m_ad_top == pytest.approx(m_ad_top)
        assert res.my_bot == pytest.approx(18000.0 + m_ad_bot)
        assert res.my == min(res.my_top, res.my_bot)
        assert res.governing_flange == "bottom"

    def test_negative_flexure_uses_one_cracked_modulus(self):
        # D6.2.3: pass the cracked modulus for both stages; with no
        # composite staging difference the top/bottom split still governs
        res = yield_moment_composite(
            m_d1=10000.0, m_d2=5000.0,
            s_nc_top=1200.0, s_nc_bot=1200.0,
            s_lt_top=1400.0, s_lt_bot=1400.0,
            s_st_top=1400.0, s_st_bot=1400.0,
            f_y_top=50.0, f_y_bot=50.0)
        assert res.my_top == pytest.approx(res.my_bot)


class TestWebCompressionDepth:
    def test_symmetric_equal_stress(self):
        # equal flange stresses on a symmetric section: NA at middepth
        assert web_compression_depth_elastic(
            25.0, 25.0, 56.0, 1.0) == pytest.approx(27.0)

    def test_floor_at_zero(self):
        # composite positive flexure often puts the whole web in tension
        assert web_compression_depth_elastic(1.0, 50.0, 56.0, 2.0) == 0.0


class TestClassification:
    def test_positive_compact_trivially_when_pna_above_web(self):
        res = classify_composite_positive(
            d_cp=0.0, t_w=0.5, f_yc=50.0, f_yt=50.0, d_web=54.0)
        assert res.ok
        assert res.details["classification"] == "compact"

    def test_positive_hybrid_over_70_is_noncompact(self):
        res = classify_composite_positive(
            d_cp=0.0, t_w=0.5, f_yc=100.0, f_yt=50.0, d_web=54.0)
        assert not res.ok
        assert not res.details["fy_flanges_le_70"]

    def test_positive_web_slenderness_governs(self):
        lam_pw = 3.76 * math.sqrt(29000.0 / 50.0)
        d_cp = 0.51 * lam_pw * 0.5   # just over the limit at tw = 0.5
        res = classify_composite_positive(
            d_cp=d_cp, t_w=0.5, f_yc=50.0, f_yt=50.0, d_web=54.0)
        assert not res.ok
        assert not res.details["web_slenderness_2Dcp_tw"]

    def test_negative_a6_eligibility(self):
        res = classify_web_negative(
            d_c=27.0, t_w=0.5625, f_yc=50.0, f_yt=50.0,
            i_yc=1166.7, i_yt=729.0)
        # 2*27/0.5625 = 96 < 5.7*sqrt(E/50) = 137.3
        assert res.ok
        assert res.details["2Dc/tw"] == pytest.approx(96.0)

    def test_negative_slender_web(self):
        res = classify_web_negative(
            d_c=45.0, t_w=0.5, f_yc=50.0, f_yt=50.0,
            i_yc=1000.0, i_yt=1000.0)
        assert not res.ok
        assert "slender" in res.details["classification"]


def test_articles_registered():
    for number in ("D6.1", "D6.2.2", "D6.3.1", "6.10.6.2.2", "6.10.6.2.3"):
        assert number in ARTICLES
