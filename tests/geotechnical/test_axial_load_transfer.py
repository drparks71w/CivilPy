#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see the module header for the full notice)

"""Axial pile load-transfer curves (civilpy.geotech.axial_load_transfer):
the API RP 2A t-z / q-z backbones and the nodal-spring discretiser."""

import math

import pytest

from civilpy.geotech.axial_load_transfer import (
    APIQZCurve,
    APITZCurve,
    axial_pile_springs,
    spring_constant_kip_per_in,
)


# ---------------------------------------------------------------- t-z

def test_tz_sand_reaches_tmax_at_tenth_inch():
    tz = APITZCurve(t_max=750.0, soil="sand", diameter=24.0)
    assert tz.t(0.0) == 0.0
    assert tz.t(0.10) == pytest.approx(750.0)
    # bounded by t_max for any larger displacement
    assert tz.t(5.0) == pytest.approx(750.0)


def test_tz_clay_uses_z_over_d_table():
    tz = APITZCurve(t_max=1000.0, soil="clay", diameter=24.0)
    # z/D = 0.0100 -> full mobilisation
    assert tz.t(0.0100 * 24.0) == pytest.approx(1000.0)
    # z/D = 0.0016 -> 0.30 t_max
    assert tz.t(0.0016 * 24.0) == pytest.approx(300.0)


def test_tz_is_signed_and_bounded():
    tz = APITZCurve(t_max=500.0, soil="sand", diameter=12.0)
    assert tz.t(-1.0) == pytest.approx(-500.0)   # mobilises in either direction
    assert abs(tz.t(100.0)) <= 500.0 + 1e-9


def test_tz_secant_modulus_finite_at_zero():
    tz = APITZCurve(t_max=600.0, soil="sand", diameter=18.0)
    assert tz.secant_modulus(0.0) >= 0.0
    assert math.isfinite(tz.secant_modulus(0.0))


def test_tz_unknown_soil_raises():
    with pytest.raises(ValueError):
        APITZCurve(t_max=1.0, soil="silt").t(0.1)


# ---------------------------------------------------------------- q-z

def test_qz_full_mobilisation_at_tenth_diameter():
    qz = APIQZCurve(q_max=200.0, diameter=30.0)
    assert qz.q(0.10 * 30.0) == pytest.approx(200.0)
    assert qz.q(10.0 * 30.0) == pytest.approx(200.0)   # clamped flat


def test_qz_is_one_sided():
    qz = APIQZCurve(q_max=100.0, diameter=24.0)
    assert qz.q(-1.0) == 0.0          # the tip cannot resist uplift
    assert qz.q(0.0) == 0.0
    assert qz.q(1.0) > 0.0


def test_qz_secant_modulus_positive():
    qz = APIQZCurve(q_max=100.0, diameter=24.0)
    assert qz.secant_modulus(0.5) > 0.0


# ---------------------------------------------------------------- springs

def test_axial_pile_springs_tributary_lengths():
    tz = APITZCurve(t_max=750.0, soil="sand", diameter=24.0)
    springs = axial_pile_springs(tz, embedded_length=240.0, n_nodes=5,
                                 design_disp=0.10)
    assert len(springs) == 5
    depths = [d for d, _ in springs]
    assert depths == [0.0, 60.0, 120.0, 180.0, 240.0]
    # interior nodes carry twice the end nodes' tributary stiffness
    k_end, k_mid = springs[0][1], springs[1][1]
    assert k_mid == pytest.approx(2.0 * k_end)


def test_axial_pile_springs_needs_two_nodes():
    tz = APITZCurve(t_max=1.0, soil="sand", diameter=12.0)
    with pytest.raises(ValueError):
        axial_pile_springs(tz, embedded_length=100.0, n_nodes=1, design_disp=0.1)


def test_spring_constant_unit_conversion():
    # 1000 lb/in -> 12 kip/ft
    assert spring_constant_kip_per_in(1000.0) == pytest.approx(1.0)
