#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see the module header for the full notice)

"""Laterally loaded piles (civilpy.geotech.lateral_pile): the p-y curve
library, the FE beam-on-p-y solver, Broms' method, and the closed-form
subgrade-reaction methods."""

import math

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from civilpy.geotech import lateral_pile as lp


class TestLinearPY:
    def test_resistance_and_sign(self):
        c = lp.LinearPY(k=100.0)
        assert c.p(0.5, 10) == pytest.approx(50.0)
        assert c.p(-0.5, 10) == pytest.approx(-50.0)

    def test_cap(self):
        c = lp.LinearPY(k=100.0, p_ult=10.0)
        assert c.p(1.0, 10) == pytest.approx(10.0)

    def test_pu(self):
        assert lp.LinearPY(k=100.0, p_ult=5.0).pu(10) == 5.0

    def test_secant_modulus_floor(self):
        c = lp.LinearPY(k=100.0)
        assert c.secant_modulus(0.0, 10) == pytest.approx(100.0)


class TestSoftClayPY:
    def setup_method(self):
        self.c = lp.SoftClayPY(cu=5.0, b=12.0, gamma=0.04, eps50=0.02)

    def test_y50(self):
        assert self.c.y50 == pytest.approx(2.5 * 0.02 * 12.0)

    def test_pu_shallow_vs_deep(self):
        shallow = self.c.pu(5.0)
        deep = self.c.pu(500.0)
        assert deep == pytest.approx(9.0 * 5.0 * 12.0)  # capped at 9
        assert shallow < deep

    def test_backbone_and_plateau(self):
        small = self.c.p(0.01, 60)
        plateau = self.c.p(100.0, 60)  # y >> 8*y50
        assert plateau == pytest.approx(self.c.pu(60))
        assert 0 < small < plateau

    def test_zero_deflection(self):
        assert self.c.p(0.0, 60) == 0.0

    def test_negative_symmetry(self):
        assert self.c.p(-0.5, 60) == pytest.approx(-self.c.p(0.5, 60))


class TestStiffClayPY:
    def setup_method(self):
        self.c = lp.StiffClayPY(cu=20.0, b=12.0, gamma=0.05, eps50=0.005)

    def test_y50(self):
        assert self.c.y50 == pytest.approx(0.005 * 12.0)

    def test_plateau_at_16_y50(self):
        assert self.c.p(100.0, 60) == pytest.approx(self.c.pu(60))

    def test_backbone(self):
        assert 0 < self.c.p(0.01, 60) < self.c.pu(60)

    def test_zero(self):
        assert self.c.p(0.0, 60) == 0.0


class TestSandPY:
    def test_reese_pu_positive(self):
        assert lp.reese_sand_pu(35, 0.0723, 12.0, 60.0) > 0

    def test_subgrade_modulus_bounds(self):
        assert lp.sand_subgrade_modulus(20) == 20.0       # below table
        assert lp.sand_subgrade_modulus(45) == 200.0      # above table
        mid = lp.sand_subgrade_modulus(33)
        assert 40.0 < mid < 60.0
        assert lp.sand_subgrade_modulus(33, submerged=True) < mid

    def test_default_k_assigned(self):
        c = lp.SandPY(phi_deg=35, gamma=0.0723, b=12.0)
        assert c.k == pytest.approx(lp.sand_subgrade_modulus(35))

    def test_explicit_k(self):
        c = lp.SandPY(phi_deg=35, gamma=0.0723, b=12.0, k=50.0)
        assert c.k == 50.0

    def test_a_factor_static_shallow_deep(self):
        c = lp.SandPY(phi_deg=35, gamma=0.0723, b=12.0)
        assert c.a_factor(0.0) == pytest.approx(3.0)
        assert c.a_factor(1000.0) == pytest.approx(0.9)

    def test_a_factor_cyclic(self):
        c = lp.SandPY(phi_deg=35, gamma=0.0723, b=12.0, static=False)
        assert c.a_factor(0.0) == 0.9

    def test_p_at_surface_zero(self):
        c = lp.SandPY(phi_deg=35, gamma=0.0723, b=12.0)
        assert c.p(0.5, 0.0) == 0.0

    def test_p_and_sign(self):
        c = lp.SandPY(phi_deg=35, gamma=0.0723, b=12.0)
        assert c.p(0.5, 60) > 0
        assert c.p(-0.5, 60) == pytest.approx(-c.p(0.5, 60))

    def test_p_zero_deflection(self):
        c = lp.SandPY(phi_deg=35, gamma=0.0723, b=12.0)
        assert c.p(0.0, 60) == 0.0


class TestSolver:
    def test_matches_hetenyi(self):
        ei, k, p, length = 1e9, 500.0, 10000.0, 400.0
        res = lp.solve_lateral_pile(lp.LinearPY(k=k), length, ei, shear=p, n_elem=200)
        beta = (k / (4 * ei)) ** 0.25
        assert res.converged
        assert res.head_deflection == pytest.approx(2 * p * beta / k, rel=0.01)
        assert res.max_moment == pytest.approx(0.3224 * p / beta, rel=0.03)

    def test_callable_layered(self):
        soft = lp.SoftClayPY(cu=5.0, b=12.0, gamma=0.04)
        stiff = lp.StiffClayPY(cu=30.0, b=12.0, gamma=0.05)
        res = lp.solve_lateral_pile(
            lambda z: soft if z < 120 else stiff,
            length=300, ei=1e9, shear=20000, n_elem=100,
        )
        assert res.converged
        assert res.head_deflection > 0

    def test_fixed_head_less_deflection(self):
        c = lp.SandPY(phi_deg=35, gamma=0.0723, b=12.0)
        free = lp.solve_lateral_pile(c, 300, 1e9, shear=15000, n_elem=120)
        fixed = lp.solve_lateral_pile(
            c, 300, 1e9, shear=15000, n_elem=120, fixed_head=True
        )
        assert fixed.head_deflection < free.head_deflection

    def test_moment_load(self):
        res = lp.solve_lateral_pile(
            lp.LinearPY(k=500.0), 400, 1e9, shear=0.0, moment=1e6, n_elem=200
        )
        assert res.converged
        assert abs(res.head_deflection) > 0

    def test_non_convergence_flag(self):
        c = lp.SandPY(phi_deg=35, gamma=0.0723, b=12.0)
        res = lp.solve_lateral_pile(c, 300, 1e9, shear=15000, max_iter=1)
        assert not res.converged

    def test_bad_args(self):
        c = lp.LinearPY(k=100.0)
        with pytest.raises(ValueError):
            lp.solve_lateral_pile(c, 0.0, 1e9, shear=1000)
        with pytest.raises(ValueError):
            lp.solve_lateral_pile(c, 100, 0.0, shear=1000)
        with pytest.raises(ValueError):
            lp.solve_lateral_pile(c, 100, 1e9, shear=1000, n_elem=1)

    def test_max_moment_depth(self):
        res = lp.solve_lateral_pile(lp.LinearPY(k=500.0), 400, 1e9, shear=10000, n_elem=80)
        assert 0.0 <= res.max_moment_depth <= 400.0

    def test_plot_default_and_provided_axes(self):
        res = lp.solve_lateral_pile(lp.LinearPY(k=500.0), 400, 1e9, shear=10000, n_elem=80)
        fig = res.plot()
        assert fig is not None
        import matplotlib.pyplot as plt
        _, axes = plt.subplots(1, 4)
        fig2 = res.plot(ax=axes)
        assert fig2 is not None


class TestPointOfFixity:
    def _result(self, depth, defl):
        n = len(depth)
        return lp.LateralPileResult(
            depth=np.array(depth, float), deflection=np.array(defl, float),
            moment=np.zeros(n), shear=np.zeros(n), soil_reaction=np.zeros(n),
            iterations=1, converged=True,
        )

    def test_sign_change_interpolated(self):
        r = self._result([0, 10, 20, 30], [1.0, 0.5, -0.5, -1.0])
        assert r.point_of_fixity == pytest.approx(15.0)

    def test_exact_zero_node(self):
        r = self._result([0, 10, 20], [1.0, 0.0, -1.0])
        # y[i-1]==0 branch at i where previous is zero; y1==y0 guard
        assert r.point_of_fixity is not None

    def test_flat_zero_pair(self):
        r = self._result([0, 10, 20], [0.0, 0.0, 1.0])
        assert r.point_of_fixity == pytest.approx(0.0)

    def test_never_reverses(self):
        r = self._result([0, 10, 20], [1.0, 0.8, 0.6])
        assert r.point_of_fixity is None


class TestBroms:
    def test_cohesive_modes(self):
        long_pile = lp.broms_cohesive(14.0, 12.0, 240.0, 3e6, e=12.0)
        assert long_pile.mode == "long"
        assert long_pile.h_ult == pytest.approx(long_pile.h_long)
        assert long_pile.f_maxmoment is not None
        short_pile = lp.broms_cohesive(14.0, 12.0, 60.0, 3e8, e=12.0)
        assert short_pile.mode == "short"
        assert short_pile.h_ult == pytest.approx(short_pile.h_short)

    def test_cohesive_short_floor_zero(self):
        # an extremely short pile gives a non-negative short capacity
        r = lp.broms_cohesive(14.0, 12.0, 18.1, 3e8, e=0.0)
        assert r.h_short >= 0.0

    def test_cohesionless_modes(self):
        long_pile = lp.broms_cohesionless(35, 0.0723, 12.0, 240.0, 3e6, e=12.0)
        assert long_pile.mode == "long"
        assert long_pile.f_maxmoment is not None
        short_pile = lp.broms_cohesionless(35, 0.0723, 12.0, 60.0, 3e9, e=12.0)
        assert short_pile.mode == "short"

    def test_short_equation(self):
        kp = math.tan(math.radians(45 + 35 / 2)) ** 2
        expected = 0.5 * kp * 0.0723 * 12.0 * 240.0 ** 3 / (12.0 + 240.0)
        r = lp.broms_cohesionless(35, 0.0723, 12.0, 240.0, 1e12, e=12.0)
        assert r.h_short == pytest.approx(expected)


class TestSubgrade:
    def test_constant_k(self):
        r = lp.subgrade_constant_k(k=500, ei=1e9, shear=10000)
        beta = (500 / (4e9)) ** 0.25
        assert r.head_deflection == pytest.approx(2 * 10000 * beta / 500)
        assert r.point_of_fixity == pytest.approx(1.4 / beta)
        assert r.max_moment > 0

    def test_constant_k_with_moment(self):
        r = lp.subgrade_constant_k(k=500, ei=1e9, shear=0.0, moment=1e6)
        assert r.head_deflection > 0
        assert r.head_slope != 0

    def test_constant_k_bad(self):
        with pytest.raises(ValueError):
            lp.subgrade_constant_k(k=0, ei=1e9, shear=1000)
        with pytest.raises(ValueError):
            lp.subgrade_constant_k(k=500, ei=0, shear=1000)

    def test_linear_nh(self):
        r = lp.subgrade_linear_nh(nh=20.0, ei=1e9, shear=10000)
        t = (1e9 / 20.0) ** 0.2
        assert r.characteristic_length == pytest.approx(t)
        assert r.point_of_fixity == pytest.approx(1.8 * t)
        assert r.head_deflection > 0

    def test_linear_nh_moment(self):
        r = lp.subgrade_linear_nh(nh=20.0, ei=1e9, shear=0.0, moment=1e6)
        assert r.max_moment == pytest.approx(1e6, rel=0.01) or r.max_moment > 0

    def test_linear_nh_bad(self):
        with pytest.raises(ValueError):
            lp.subgrade_linear_nh(nh=0, ei=1e9, shear=1000)
        with pytest.raises(ValueError):
            lp.subgrade_linear_nh(nh=20, ei=0, shear=1000)
