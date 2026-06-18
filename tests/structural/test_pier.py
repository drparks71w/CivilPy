#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see the module header for the full notice)

"""Multi-column pier / bent (civilpy.structural.pier): the continuous-beam
cap solver and the per-column P-M distribution."""

import math

import pytest

from civilpy.structural import pier
from civilpy.structural.aashto.lrfd.columns import RebarLayer


def _circular_column(**kw):
    base = dict(height=240.0, diameter=48.0,
                layers=[RebarLayer(3.0, 3.0), RebarLayer(3.0, 45.0)],
                spiral=True)
    base.update(kw)
    return pier.PierColumn(**base)


def _cap(**kw):
    base = dict(
        length=360.0, width=42.0, depth=48.0, column_positions=[60.0, 180.0, 300.0],
        loads=[pier.PointLoad(x, 200.0) for x in (30, 90, 150, 210, 270, 330)],
    )
    base.update(kw)
    return pier.PierCap(**base)


class TestContinuousBeam:
    def test_simple_span_pl_over_4(self):
        sol = pier.solve_continuous_beam(
            120.0, 1e8, supports=[0.0, 120.0],
            point_loads=[pier.PointLoad(60.0, 10.0)],
        )
        assert sol.max_moment == pytest.approx(10 * 120 / 4, rel=1e-3)
        for r in sol.reactions.values():
            assert r == pytest.approx(5.0, rel=1e-3)

    def test_two_span_udl_reactions(self):
        sol = pier.solve_continuous_beam(240.0, 1e8, supports=[0, 120, 240], udl=1.0)
        assert sol.reactions[120] == pytest.approx(150.0, rel=1e-2)
        assert sol.reactions[0] == pytest.approx(45.0, rel=1e-2)
        assert sol.max_shear > 0

    def test_point_loads_default_none(self):
        sol = pier.solve_continuous_beam(120.0, 1e8, supports=[0, 120], udl=0.5)
        assert sol.max_moment > 0

    def test_bad_geometry(self):
        with pytest.raises(ValueError):
            pier.solve_continuous_beam(0, 1e8, supports=[0, 10])
        with pytest.raises(ValueError):
            pier.solve_continuous_beam(120, 0, supports=[0, 120])

    def test_requires_support(self):
        with pytest.raises(ValueError):
            pier.solve_continuous_beam(120, 1e8, supports=[])


class TestPierCap:
    def test_default_modulus(self):
        cap = _cap()
        assert cap.e_concrete == pytest.approx(57000 * math.sqrt(4000) / 1000, rel=1e-6)

    def test_explicit_modulus(self):
        cap = _cap(e_concrete=4000.0)
        assert cap.e_concrete == 4000.0

    def test_self_weight_and_ei(self):
        cap = _cap()
        assert cap.self_weight_udl > 0
        assert cap.ei == pytest.approx(cap.e_concrete * 42 * 48 ** 3 / 12)

    def test_column_reactions(self):
        cap = _cap()
        reac = cap.column_reactions()
        assert len(reac) == 3
        assert sum(reac.values()) == pytest.approx(
            6 * 200.0 + cap.self_weight_udl * cap.length, rel=1e-2
        )

    def test_flexure_check(self):
        cap = _cap()
        res = cap.flexure_check(a_s=12.0)
        assert res.article == "5.6.3.2"
        assert res.ratio is not None

    def test_flexure_check_with_solution(self):
        cap = _cap()
        sol = cap.analyze()
        res = cap.flexure_check(a_s=12.0, solution=sol)
        assert res.demand == pytest.approx(sol.max_moment)

    def test_shear_check_variants(self):
        cap = _cap()
        sol = cap.analyze()
        bare = cap.shear_check()
        stirruped = cap.shear_check(a_v=0.62, s=6.0, solution=sol)
        assert stirruped.factored_capacity > bare.factored_capacity


class TestPierColumn:
    def test_requires_section(self):
        with pytest.raises(ValueError):
            pier.PierColumn(240.0, [RebarLayer(2, 3)])

    def test_bad_fixity(self):
        with pytest.raises(ValueError):
            pier.PierColumn(240.0, [RebarLayer(2, 3)], diameter=36, fixity="pinned")

    def test_circular_properties(self):
        c = _circular_column()
        assert c.gross_area == pytest.approx(math.pi * 48 ** 2 / 4)
        assert c.moment_of_inertia == pytest.approx(math.pi * 48 ** 4 / 64)

    def test_rectangular_properties(self):
        c = pier.PierColumn(240.0, [RebarLayer(2, 3), RebarLayer(2, 33)],
                            b=36.0, h=36.0)
        assert c.gross_area == pytest.approx(1296.0)
        assert c.moment_of_inertia == pytest.approx(36 * 36 ** 3 / 12)

    def test_stiffness_fixity(self):
        ff = _circular_column(fixity="fixed-fixed").lateral_stiffness(3600)
        fc = _circular_column(fixity="fixed-free").lateral_stiffness(3600)
        assert fc / ff == pytest.approx(0.25)

    def test_lateral_moment(self):
        ff = _circular_column(fixity="fixed-fixed")
        cantilever = _circular_column(fixity="fixed-free")
        assert ff.lateral_moment(50.0) == pytest.approx(50 * 240 / 2)
        assert cantilever.lateral_moment(50.0) == pytest.approx(50 * 240)

    def test_axial_resistance(self):
        c = _circular_column()
        res = c.axial_resistance(p_u=400.0)
        assert res.article == "5.6.4.4"
        assert res.ratio is not None

    def test_pm_check(self):
        c = _circular_column()
        res = c.pm_check(p_u=470.0, m_u=6000.0)
        assert res.article == "5.6.4.5 check"

    def test_magnified_moment_default_modulus(self):
        c = _circular_column()
        m, mag = c.magnified_moment(p_u=470.0, m_u=6000.0)
        assert m >= 6000.0
        assert mag.capacity >= 1.0

    def test_magnified_moment_explicit_modulus(self):
        c = _circular_column()
        m, _ = c.magnified_moment(p_u=470.0, m_u=6000.0, e_concrete=3600.0)
        assert m >= 6000.0

    def test_magnified_zero_moment(self):
        c = _circular_column()
        m, mag = c.magnified_moment(p_u=470.0, m_u=0.0)
        assert m == 0.0


class TestMultiColumnBent:
    def test_column_count_mismatch(self):
        with pytest.raises(ValueError):
            pier.MultiColumnBent(_cap(), [_circular_column(), _circular_column()])

    def test_scalar_dead_load(self):
        bent = pier.MultiColumnBent(
            _cap(), [_circular_column() for _ in range(3)], column_dead_load=30.0
        )
        assert bent.column_dead_load == [30.0, 30.0, 30.0]

    def test_list_dead_load(self):
        bent = pier.MultiColumnBent(
            _cap(), [_circular_column() for _ in range(3)],
            column_dead_load=[10.0, 20.0, 30.0],
        )
        assert bent.column_dead_load == [10.0, 20.0, 30.0]

    def test_dead_load_list_mismatch(self):
        with pytest.raises(ValueError):
            pier.MultiColumnBent(
                _cap(), [_circular_column() for _ in range(3)],
                column_dead_load=[10.0, 20.0],
            )

    def test_lateral_distribution_equal_columns(self):
        bent = pier.MultiColumnBent(
            _cap(), [_circular_column() for _ in range(3)], lateral_force=150.0
        )
        shears = bent.lateral_distribution()
        assert shears == pytest.approx([50.0, 50.0, 50.0])

    def test_lateral_distribution_by_stiffness(self):
        cols = [_circular_column(), _circular_column(diameter=60.0),
                _circular_column()]
        bent = pier.MultiColumnBent(_cap(), cols, lateral_force=150.0)
        shears = bent.lateral_distribution()
        assert shears[1] > shears[0]  # stiffer middle column draws more

    def test_analyze(self):
        bent = pier.MultiColumnBent(
            _cap(), [_circular_column() for _ in range(3)],
            lateral_force=150.0, column_dead_load=30.0,
        )
        res = bent.analyze()
        assert len(res.column_axials) == 3
        assert all(a > 0 for a in res.column_axials)
        assert res.column_axials[0] == pytest.approx(res.column_axials[2], rel=1e-3)
        assert isinstance(res.all_columns_ok, bool)
        assert res.cap_solution.max_moment > 0
