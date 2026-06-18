#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see the module header for the full notice)

"""Functional tests for reinforced-concrete flexural design + rebar sizing
(civilpy.structural.aashto.lrfd.concrete).

Expected values are hand-computed from AASHTO LRFD 5.6.3 so the tests verify
the engine's numbers, not just its plumbing.  Worked example throughout: a
singly reinforced rectangular beam b = 12 in, d_s = 20 in, f'c = 4 ksi,
f_y = 60 ksi.
"""

import math

import pytest

from civilpy.structural.aashto.lrfd.concrete import (
    rc_rectangular_flexural_resistance,
    size_flexural_rebar,
)
from civilpy.structural.steel import Rebar


# ---------------------------------------------------------- concrete design

def test_flexural_resistance_hand_calc():
    """A_s = 2.0 in^2: a = 2*60/(0.85*4*12) = 2.941 in, Mn = 2*60*(20 - a/2)
    = 2223.5 kip-in; net tensile strain is tension-controlled so phi = 0.90."""
    r = rc_rectangular_flexural_resistance(a_s=2.0, f_y=60.0, f_c=4.0,
                                           b=12.0, d_s=20.0)
    a = 2.0 * 60.0 / (0.85 * 4.0 * 12.0)
    assert r.details["a"] == pytest.approx(a, rel=1e-6)
    assert r.capacity == pytest.approx(2.0 * 60.0 * (20.0 - a / 2.0), rel=1e-6)
    assert r.capacity == pytest.approx(2223.5, abs=0.5)
    assert r.phi == pytest.approx(0.90)
    assert r.details["tension_controlled"] is True


def test_flexural_demand_ratio():
    r = rc_rectangular_flexural_resistance(a_s=2.0, f_y=60.0, f_c=4.0,
                                           b=12.0, d_s=20.0, m_u=2001.2)
    # phi*Mn ~ 2001.2 kip-in, so the section is right at capacity (ratio ~ 1)
    assert r.factored_capacity == pytest.approx(2001.2, abs=1.0)
    assert r.ratio == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------- rebar table

@pytest.mark.parametrize("size, area", [(4, 0.20), (8, 0.79), (9, 1.00),
                                        (11, 1.56), (18, 4.00)])
def test_rebar_areas(size, area):
    assert float(Rebar(size).area.magnitude) == pytest.approx(area)


# ---------------------------------------------------------- rebar sizing

def test_sizes_to_strength_demand():
    """Mu = 2001 kip-in needs A_s ~ 2.0 in^2; 3-#8 (3*0.79 = 2.37) supplies it
    and the checked section passes."""
    d = size_flexural_rebar(m_u=2001.0, b=12.0, d_s=20.0, bar_size=8)
    assert d.governing == "strength"
    assert d.a_s_required == pytest.approx(2.0, abs=0.02)
    assert d.n_bars == 3
    assert d.a_s_provided == pytest.approx(2.37, abs=1e-6)
    assert d.check.ratio >= 1.0          # selected steel actually works


def test_sizing_is_monotonic_in_demand():
    light = size_flexural_rebar(m_u=2001.0, b=12.0, d_s=20.0, bar_size=8)
    heavy = size_flexural_rebar(m_u=4000.0, b=12.0, d_s=20.0, bar_size=8)
    assert heavy.a_s_required > light.a_s_required
    assert heavy.n_bars > light.n_bars


def test_selected_steel_always_satisfies_demand():
    for m_u in (500.0, 1500.0, 2500.0, 3500.0, 4500.0):
        d = size_flexural_rebar(m_u=m_u, b=12.0, d_s=20.0, bar_size=9)
        assert d.a_s_provided >= d.a_s_required
        assert d.check.ratio is not None and d.check.ratio >= 1.0


def test_minimum_reinforcement_governs_lightly_loaded():
    """Big section, tiny Mu: Mcr = 0.67*1.6*fr*(b h^2/6) and 1.33*Mu both
    exceed Mu, so 5.6.3.3 raises the target above strength."""
    d = size_flexural_rebar(m_u=200.0, b=12.0, d_s=22.0, h=24.0, bar_size=8)
    fr = 0.24 * math.sqrt(4.0)
    m_cr = 0.67 * 1.6 * fr * (12.0 * 24.0 ** 2 / 6.0)
    assert d.governing == "minimum reinforcement"
    # target = min(Mcr, 1.33*Mu) = 1.33*200 = 266 kip-in here
    assert min(m_cr, 1.33 * 200.0) == pytest.approx(266.0, abs=1.0)
    assert d.check.ratio >= 1.0


def test_larger_bars_need_fewer():
    by8 = size_flexural_rebar(m_u=4000.0, b=12.0, d_s=20.0, bar_size=8)
    by11 = size_flexural_rebar(m_u=4000.0, b=12.0, d_s=20.0, bar_size=11)
    assert by11.n_bars < by8.n_bars
    assert by11.a_s_provided >= by11.a_s_required


def test_invalid_bar_size_raises():
    with pytest.raises(ValueError):
        size_flexural_rebar(m_u=1000.0, b=12.0, d_s=20.0, bar_size=13)
