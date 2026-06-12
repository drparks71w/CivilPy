"""Tests for Appendix B6 moment redistribution and LRFR permit factors."""

import math

import pytest

from civilpy.structural.aashto.lrfd import ARTICLES
from civilpy.structural.aashto.lrfd.appendix_b6 import (
    b6_web_proportions, b6_flange_proportions, b6_bracing_limit,
    b6_effective_plastic_moment, b6_redistribution_moment)
from civilpy.structural.aashto.lrfd.lrfr import permit_load_factor

E = 29000.0


# ── B6.2 scope checks ──────────────────────────────────────────────────────


def test_web_proportions_pass_and_fail():
    ok = b6_web_proportions(d=60.0, t_w=0.5625, d_c=30.0, d_cp=28.0,
                            f_yc=50.0)
    assert ok.details["satisfied"]
    assert ok.details["2Dc/tw (limit)"] == pytest.approx(
        6.8 * math.sqrt(E / 50.0))
    # slender web: 2Dc/tw over the limit
    bad = b6_web_proportions(d=90.0, t_w=0.5, d_c=50.0, d_cp=40.0,
                             f_yc=50.0)
    assert not bad.details["satisfied"]
    assert bad.details["governing"] == "2Dc/tw"
    # deep plastic compression zone trips B6.2.1-3
    deep = b6_web_proportions(d=60.0, t_w=0.625, d_c=28.0, d_cp=50.0,
                              f_yc=50.0)
    assert not deep.details["satisfied"]
    assert deep.details["governing"] == "Dcp"


def test_flange_proportions():
    ok = b6_flange_proportions(b_fc=16.0, t_fc=1.5, d=60.0, f_yc=50.0)
    assert ok.details["satisfied"]
    assert ok.capacity == pytest.approx(0.38 * math.sqrt(E / 50.0))
    # narrow flange fails bfc >= D/4.25 even when not slender
    narrow = b6_flange_proportions(b_fc=12.0, t_fc=1.5, d=60.0, f_yc=50.0)
    assert not narrow.details["satisfied"]
    assert narrow.details["bfc_min"] == pytest.approx(60.0 / 4.25)


def test_bracing_limit_single_vs_reverse_curvature():
    # reverse curvature (M1/M2 < 0) allows longer unbraced lengths
    single = b6_bracing_limit(r_t=3.5, f_yc=50.0, m1=4000.0, m2=8000.0)
    reverse = b6_bracing_limit(r_t=3.5, f_yc=50.0, m1=-4000.0, m2=8000.0)
    assert single.capacity == pytest.approx(
        (0.1 - 0.06 * 0.5) * 3.5 * E / 50.0)
    assert reverse.capacity > single.capacity


# ── B6.5 effective plastic moment ──────────────────────────────────────────

SECTION = dict(b_fc=16.0, t_fc=1.5, d=60.0, f_yc=50.0)


def hand_mpe(coeff, m_n=10000.0, **kw):
    beta = kw["b_fc"] / kw["t_fc"] * math.sqrt(kw["f_yc"] / E)
    delta = kw["d"] / kw["b_fc"]
    return min((coeff - 2.3 * beta - 0.35 * delta + 0.39 * beta * delta)
               * m_n, m_n)


def test_mpe_ordinary_sections_use_b652():
    service = b6_effective_plastic_moment(10000.0, **SECTION,
                                          limit_state="service")
    strength = b6_effective_plastic_moment(10000.0, **SECTION,
                                           limit_state="strength")
    assert service.capacity == pytest.approx(hand_mpe(2.90, **SECTION))
    assert strength.capacity == pytest.approx(hand_mpe(2.63, **SECTION))
    assert service.details["equation"] == "B6.5.2-1"
    assert strength.details["equation"] == "B6.5.2-2"
    assert strength.capacity < service.capacity <= 10000.0


def test_mpe_enhanced_sections_use_b651():
    service = b6_effective_plastic_moment(
        10000.0, **SECTION, limit_state="service",
        stiffener_within_d_over_2=True)
    assert service.capacity == pytest.approx(10000.0)     # Mpe = Mn
    assert service.details["equation"] == "B6.5.1-2"
    strength = b6_effective_plastic_moment(
        10000.0, **SECTION, limit_state="strength",
        stiffener_within_d_over_2=True)
    assert strength.capacity == pytest.approx(hand_mpe(2.78, **SECTION))
    # ultracompact web qualifies without the stiffener
    ultra = b6_effective_plastic_moment(
        10000.0, **SECTION, limit_state="service",
        d_cp=12.0, t_w=0.5625)
    assert ultra.details["ultracompact_web"]
    assert ultra.capacity == pytest.approx(10000.0)


def test_mpe_never_exceeds_mn():
    stocky = b6_effective_plastic_moment(
        10000.0, b_fc=18.0, t_fc=2.5, d=40.0, f_yc=36.0,
        limit_state="service")
    assert stocky.capacity <= 10000.0 + 1e-9


# ── B6.3.3.1 / B6.4.2.1 redistribution moments ─────────────────────────────


def test_redistribution_moment_service_and_strength():
    service = b6_redistribution_moment(-12000.0, m_pe=11000.0,
                                       limit_state="service")
    assert service.capacity == pytest.approx(1000.0)
    assert service.article == "B6.3.3.1"
    strength = b6_redistribution_moment(-12000.0, m_pe=11000.0,
                                        limit_state="strength")
    assert strength.capacity == pytest.approx(12000.0 - 1.0 * 11000.0)
    # flange lateral bending raises the demand side
    with_fl = b6_redistribution_moment(-12000.0, m_pe=11000.0,
                                       limit_state="strength",
                                       f_l=6.0, s_x=300.0)
    assert with_fl.capacity == pytest.approx(1000.0 + 6.0 * 300.0 / 3.0)


def test_redistribution_clamped_and_capped():
    # Mpe above |Me|: nothing to shed
    none = b6_redistribution_moment(10000.0, m_pe=12000.0)
    assert none.capacity == 0.0
    assert none.details["permitted"]
    # over the 20% cap: redistribution not permitted at all
    over = b6_redistribution_moment(10000.0, m_pe=7000.0)
    assert not over.details["permitted"]
    assert over.capacity == 0.0
    assert over.details["0.2|Me|"] == pytest.approx(2000.0)


def test_b6_articles_registered():
    for art in ("B6.2.1", "B6.2.2", "B6.2.4", "B6.5", "B6.4.2.1"):
        assert art in ARTICLES


# ── 6A.4.5.4.2a permit load factors ────────────────────────────────────────


def test_routine_permit_band_lookup():
    assert permit_load_factor("routine", adtt=6000.0,
                              gvw_over_al=1.5) == pytest.approx(1.40)
    assert permit_load_factor("routine", adtt=6000.0,
                              gvw_over_al=2.5) == pytest.approx(1.35)
    assert permit_load_factor("routine", adtt=6000.0,
                              gvw_over_al=3.5) == pytest.approx(1.30)
    # low-volume route, heavy intensity
    assert permit_load_factor("routine", adtt=50.0,
                              gvw_over_al=4.0) == pytest.approx(1.15)
    # unknown ADTT defaults to the top row
    assert permit_load_factor("routine",
                              gvw_over_al=1.0) == pytest.approx(1.40)


def test_routine_permit_adtt_interpolation():
    # halfway between the 1000 (1.25) and 5000 (1.35) rows, middle band
    mid = permit_load_factor("routine", adtt=3000.0, gvw_over_al=2.5)
    assert mid == pytest.approx(1.30)
    # GVW/AL from the vehicle: 160 kips on 40 ft of axles = 4 k/ft
    f = permit_load_factor("routine", adtt=1000.0, gvw_kips=160.0,
                           axle_length_ft=40.0)
    assert f == pytest.approx(1.20)


def test_special_permit_types():
    assert permit_load_factor("single_trip_escorted") == pytest.approx(1.10)
    assert permit_load_factor("single_trip_mixed") == pytest.approx(1.20)
    assert permit_load_factor("multiple_trip_mixed") == pytest.approx(1.40)
    with pytest.raises(ValueError, match="unknown permit type"):
        permit_load_factor("daily_commute")
    with pytest.raises(ValueError, match="gvw_over_al"):
        permit_load_factor("routine", adtt=1000.0)


def test_agency_override_tables():
    custom = {"single_trip_escorted": 1.05}
    assert permit_load_factor("single_trip_escorted",
                              factors=custom) == pytest.approx(1.05)
