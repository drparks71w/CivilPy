#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see the module header for the full notice)

"""Cantilever retaining walls / abutments (civilpy.structural.abutment):
external stability and the stem / toe / heel RC design checks."""

import math

import pytest

from civilpy.structural.abutment import RetainingWall, StabilityResult


def _stable_wall(**kw):
    """A well-proportioned wall (wide base) that passes the checks."""
    base = dict(
        stem_height=10.0, stem_thickness=1.5, toe_length=3.0, heel_length=5.0,
        footing_thickness=2.0, backfill_gamma=120.0, backfill_phi=32.0,
        base_friction_deg=22.0,
    )
    base.update(kw)
    return RetainingWall(**base)


def _tall_wall():
    return RetainingWall(
        stem_height=18.0, stem_thickness=1.5, toe_length=3.0, heel_length=4.0,
        footing_thickness=2.0, backfill_gamma=117.0, backfill_phi=30.0,
        base_friction_deg=20.0,
    )


class TestGeometry:
    def test_base_width(self):
        assert _stable_wall().base_width == pytest.approx(9.5)

    def test_total_height_level(self):
        assert _stable_wall().total_height == pytest.approx(12.0)

    def test_total_height_sloped(self):
        w = _stable_wall(backfill_slope=18.0)
        assert w.total_height > 12.0

    def test_ka_rankine(self):
        assert _stable_wall().ka == pytest.approx(
            (1 - math.sin(math.radians(32))) / (1 + math.sin(math.radians(32))),
            rel=1e-6,
        )

    def test_ka_coulomb(self):
        w = _stable_wall(method="coulomb", wall_friction_deg=20.0)
        assert 0 < w.ka < 1

    def test_ka_unknown(self):
        with pytest.raises(ValueError):
            _stable_wall(method="bogus").ka

    def test_kp(self):
        assert _stable_wall().kp > 1


class TestVerticalLoads:
    def test_base_three_loads(self):
        loads = _stable_wall()._vertical_loads()
        labels = {lab for _, _, lab in loads}
        assert {"footing", "stem", "heel_soil"} <= labels

    def test_sloped_adds_wedge(self):
        loads = _stable_wall(backfill_slope=18.0)._vertical_loads()
        assert any(lab == "wedge_soil" for _, _, lab in loads)

    def test_surcharge_adds_load(self):
        loads = _stable_wall(surcharge=250.0)._vertical_loads()
        assert any(lab == "surcharge" for _, _, lab in loads)

    def test_toe_soil(self):
        loads = _stable_wall(embedment=3.0)._vertical_loads()
        assert any(lab == "toe_soil" for _, _, lab in loads)

    def test_toe_soil_excluded(self):
        loads = _stable_wall(embedment=3.0, include_toe_soil=False)._vertical_loads()
        assert not any(lab == "toe_soil" for _, _, lab in loads)


class TestStability:
    def test_stable_wall_passes(self):
        s = _stable_wall().stability()
        assert s.ok_overturning
        assert s.ok_sliding
        assert s.resultant_in_middle_third
        assert s.q_min > 0

    def test_tall_wall_marginal(self):
        s = _tall_wall().stability()
        # narrow base -> outside middle third, triangular pressure
        assert not s.resultant_in_middle_third
        assert s.q_min == 0.0
        assert not s.ok_sliding

    def test_hand_calc_thrust(self):
        s = _tall_wall().stability()
        ka = _tall_wall().ka
        assert s.sum_h == pytest.approx(0.5 * ka * 117.0 * 20.0 ** 2, rel=1e-3)

    def test_passive_increases_sliding(self):
        no_p = _stable_wall(embedment=3.0).stability()
        with_p = _stable_wall(embedment=3.0, include_passive=True).stability()
        assert with_p.passive > 0
        assert with_p.fs_sliding > no_p.fs_sliding

    def test_default_friction_uses_phi(self):
        w = RetainingWall(
            stem_height=10.0, stem_thickness=1.5, toe_length=3.0,
            heel_length=5.0, footing_thickness=2.0, backfill_gamma=120.0,
            backfill_phi=32.0,
        )
        s = w.stability()
        assert s.details["delta"] == 32.0

    def test_surcharge_reduces_fs(self):
        plain = _stable_wall().stability()
        sur = _stable_wall(surcharge=400.0).stability()
        assert sur.fs_overturning < plain.fs_overturning

    def test_custom_fs_targets(self):
        s = _stable_wall().stability(fs_sliding=2.0, fs_overturning=3.0)
        assert s.fs_required_sliding == 2.0
        assert s.fs_required_overturning == 3.0

    def test_bearing_ok(self):
        s = _stable_wall().stability()
        assert s.bearing_ok(s.q_max + 1.0)
        assert not s.bearing_ok(s.q_max - 1.0)

    def test_qmax_qmin_proxies(self):
        s = _stable_wall().stability()
        assert s.q_max == s.contact.q_max
        assert s.q_min == s.contact.q_min


class TestStructuralDesign:
    def test_stem_design(self):
        d = _stable_wall().stem_design(a_s=1.0)
        assert d["flexure"].article == "5.6.3.2"
        assert d["shear"].article == "5.7.3.3"
        assert d["flexure"].ratio is not None

    def test_heel_design(self):
        w = _stable_wall()
        s = w.stability()
        d = w.heel_design(q_avg=s.q_min, a_s=1.2)
        assert d["flexure"].ratio is not None

    def test_heel_net_uplift_uses_abs(self):
        # huge upward pressure flips the net sign; abs keeps the demand valid
        w = _stable_wall()
        d = w.heel_design(q_avg=50000.0, a_s=1.2)
        assert d["shear"].demand >= 0

    def test_toe_design(self):
        w = _stable_wall()
        s = w.stability()
        d = w.toe_design(q_avg=s.q_max, a_s=0.8)
        assert d["flexure"].ratio is not None


class TestWingwall:
    def test_average_height(self):
        ww = RetainingWall.wingwall(
            high_height=18.0, low_height=6.0, stem_thickness=1.5,
            toe_length=3.0, heel_length=4.0, footing_thickness=2.0,
            backfill_gamma=117.0, backfill_phi=30.0,
        )
        assert ww.stem_height == pytest.approx(12.0)

    def test_bad_heights(self):
        with pytest.raises(ValueError):
            RetainingWall.wingwall(
                high_height=0.0, low_height=6.0, stem_thickness=1.5,
                toe_length=3.0, heel_length=4.0, footing_thickness=2.0,
                backfill_gamma=117.0, backfill_phi=30.0,
            )
        with pytest.raises(ValueError):
            RetainingWall.wingwall(
                high_height=18.0, low_height=-1.0, stem_thickness=1.5,
                toe_length=3.0, heel_length=4.0, footing_thickness=2.0,
                backfill_gamma=117.0, backfill_phi=30.0,
            )


def test_stability_result_is_dataclass():
    s = _stable_wall().stability()
    assert isinstance(s, StabilityResult)
