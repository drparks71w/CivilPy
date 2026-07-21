#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ratio-matrix governing-case identification: synthetic bridges whose RFs
are generated from a known action (and span ratio) must be recovered, and
the scaled predictions must reproduce the ground truth exactly."""

import numpy as np
import pytest

from civilpy.structural.rating_ratios import (
    NEW_LEGAL_TRUCKS,
    OHIO_KNOWN_VEHICLES,
    demand_ratio_matrix,
    identify_governing_case,
    predict_rating_factors,
    relative_rf_matrix,
    residual_norm,
    simple_span_demands,
    three_span_demands,
)

ALL = OHIO_KNOWN_VEHICLES + NEW_LEGAL_TRUCKS


def synthetic_rfs(basis, action, capacity):
    """Ground-truth RFs: capacity over effect for the known vehicles."""
    effects = basis.effects(action, OHIO_KNOWN_VEHICLES)
    return dict(zip(OHIO_KNOWN_VEHICLES, capacity / effects))


class TestMatrices:
    def test_relative_rf_matrix_properties(self):
        r = relative_rf_matrix([2.0, 4.0, 1.0])
        assert np.allclose(np.diag(r), 1.0)
        assert np.allclose(r * r.T, 1.0)          # reciprocal symmetry
        assert r[0, 1] == pytest.approx(0.5)

    def test_demand_matrix_predicts_rf_matrix(self):
        # RF_i = C/E_i  =>  R and T are identical by construction
        effects = np.array([100.0, 250.0, 40.0])
        rfs = 1234.5 / effects
        assert np.allclose(relative_rf_matrix(rfs),
                           demand_ratio_matrix(effects))
        assert residual_norm(rfs, effects) == pytest.approx(0.0, abs=1e-12)


class TestDemandBasis:
    def test_magnitudes_and_ordering(self):
        basis = simple_span_demands(80.0, ALL)
        assert basis.vehicles == ALL
        assert np.all(basis.positive_moment > 0)
        assert np.all(basis.shear > 0)
        # simple spans do not hog
        assert np.all(basis.negative_moment == pytest.approx(0.0, abs=1e-9))
        # heavier truck, larger effect: HS20 > 2F1 everywhere
        hs20, f21 = (basis.effects("positive_moment", (n,))[0]
                     for n in ("HS20", "2F1"))
        assert hs20 > f21

    def test_effects_reorders(self):
        basis = simple_span_demands(60.0, ("HS20", "Type 3"))
        fwd = basis.effects("shear", ("HS20", "Type 3"))
        rev = basis.effects("shear", ("Type 3", "HS20"))
        assert fwd[0] == rev[1] and fwd[1] == rev[0]

    def test_hl93_lane_load_included(self):
        # HL-93 = HS20 axles + 0.64 klf lane, so its M+ must exceed HS20's
        # by the simple-span lane moment wL^2/8
        basis = simple_span_demands(100.0, ("HL-93", "HS20"))
        hl93, hs20 = basis.effects("positive_moment", ("HL-93", "HS20"))
        assert hl93 - hs20 == pytest.approx(0.64 * 100.0**2 / 8.0, rel=2e-3)

    def test_three_span_negative_moment_at_ratio(self):
        basis = three_span_demands(100.0, 1.2, ("Type 3-3",))
        assert basis.span_ratio == 1.2
        assert basis.negative_moment[0] > 0

    def test_caching_returns_same_object(self):
        a = simple_span_demands(75.0, ("HS20", "SU4"))
        b = simple_span_demands(75.0, ("HS20", "SU4"))
        assert a is b


class TestSimpleIdentification:
    def test_recovers_shear_governed(self):
        basis = simple_span_demands(60.0, ALL)
        rfs = synthetic_rfs(basis, "shear", capacity=250.0)
        case = identify_governing_case(rfs, 60.0)
        assert case.action == "shear"
        assert case.norm == pytest.approx(0.0, abs=1e-9)
        assert case.norms["positive_moment"] > 0.01
        assert case.span_ratio is None
        for name in NEW_LEGAL_TRUCKS:
            truth = 250.0 / basis.effects("shear", (name,))[0]
            assert case.predictions[name].rf == pytest.approx(truth)
            assert case.predictions[name].spread == pytest.approx(0.0,
                                                                  abs=1e-9)

    def test_recovers_moment_governed(self):
        basis = simple_span_demands(110.0, ALL)
        rfs = synthetic_rfs(basis, "positive_moment", capacity=4000.0)
        case = identify_governing_case(rfs, 110.0)
        assert case.action == "positive_moment"
        truth = 4000.0 / basis.effects("positive_moment", ("Type 3S2",))[0]
        assert case.predictions["Type 3S2"].rf == pytest.approx(truth)

    def test_robust_to_rf_noise(self):
        basis = simple_span_demands(90.0, ALL)
        rng = np.random.default_rng(42)
        rfs = {n: rf * (1.0 + rng.uniform(-0.03, 0.03))
               for n, rf in synthetic_rfs(basis, "positive_moment",
                                          3000.0).items()}
        case = identify_governing_case(rfs, 90.0)
        assert case.action == "positive_moment"
        assert case.norm > 0.0                      # noise leaves residue
        truth = 3000.0 / basis.effects("positive_moment", ("Type 3",))[0]
        assert case.predictions["Type 3"].rf == pytest.approx(truth, rel=0.03)

    def test_known_vehicle_prediction_round_trips(self):
        # Predicting a vehicle whose RF is already known returns that RF
        basis = simple_span_demands(70.0, ALL)
        rfs = synthetic_rfs(basis, "shear", 400.0)
        case = identify_governing_case(rfs, 70.0, targets=("HS20", "Type 3"))
        assert case.predictions["HS20"].rf == pytest.approx(rfs["HS20"])

    def test_drops_missing_and_validates(self):
        basis = simple_span_demands(60.0, ALL)
        rfs = synthetic_rfs(basis, "shear", 250.0)
        rfs["HS20"] = None
        rfs["SU7"] = float("nan")
        case = identify_governing_case(rfs, 60.0)
        assert "HS20" not in case.known_vehicles
        assert "SU7" not in case.known_vehicles
        assert case.action == "shear"
        with pytest.raises(ValueError):
            identify_governing_case({"HS20": 1.2}, 60.0)
        with pytest.raises(KeyError):
            identify_governing_case({"HS20": 1.2, "NOPE": 1.0}, 60.0)


class TestContinuousIdentification:
    RATIOS = (1.0, 1.2, 1.4, 1.6)

    def test_recovers_action_and_span_ratio(self):
        basis = three_span_demands(80.0, 1.4, ALL)
        rfs = synthetic_rfs(basis, "negative_moment", 900.0)
        case = identify_governing_case(rfs, 80.0, continuous=True,
                                       span_ratios=self.RATIOS)
        assert case.action == "negative_moment"
        assert case.span_ratio == pytest.approx(1.4)
        assert case.norm == pytest.approx(0.0, abs=1e-9)
        assert case.sweep["negative_moment"].shape == (4,)
        # wrong ratios fit worse than the true one
        k = list(self.RATIOS).index(1.4)
        others = np.delete(case.sweep["negative_moment"], k)
        assert np.all(others > case.norm + 1e-6)
        truth = 900.0 / basis.effects("negative_moment", ("Type 3-3",))[0]
        assert case.predictions["Type 3-3"].rf == pytest.approx(truth)

    def test_recovers_shear_governed_continuous(self):
        basis = three_span_demands(60.0, 1.2, ALL)
        rfs = synthetic_rfs(basis, "shear", 300.0)
        case = identify_governing_case(rfs, 60.0, continuous=True,
                                       span_ratios=self.RATIOS)
        assert case.action == "shear"
        assert case.span_ratio == pytest.approx(1.2)


class TestCriticalSectionAlignment:
    def test_long_span_nearly_all_aligned(self):
        # Figure 6: beyond ~60 ft nearly all pairings converge inside
        # +/-5% (5C1's split axle groups are the lone straggler)
        basis = simple_span_demands(120.0, ALL)
        rfs = synthetic_rfs(basis, "positive_moment", 5000.0)
        case = identify_governing_case(rfs, 120.0)
        for p in case.predictions.values():
            assert p.alignment_ok
            assert len(p.aligned) >= len(OHIO_KNOWN_VEHICLES) - 1
        assert set(case.predictions["Type 3"].aligned) == \
            set(OHIO_KNOWN_VEHICLES)

    def test_short_span_excludes_misaligned_known(self):
        # At 40 ft the HL-93 M+ peak sits >5% of the span from Type 3-3's,
        # so HL-93 must not contaminate that prediction
        basis = simple_span_demands(40.0, ALL)
        rfs = synthetic_rfs(basis, "positive_moment", 800.0)
        rfs["HL-93"] *= 2.0                     # corrupt an excluded known
        preds = predict_rating_factors(rfs, basis, "positive_moment")
        p = preds["Type 3-3"]
        assert "HL-93" not in p.aligned
        assert p.misalignment["HL-93"] > 0.05
        truth = 800.0 / basis.effects("positive_moment", ("Type 3-3",))[0]
        assert p.rf == pytest.approx(truth)     # unaffected by corruption
        unchecked = predict_rating_factors(rfs, basis, "positive_moment",
                                           alignment_tol=None)
        assert unchecked["Type 3-3"].rf > truth # corruption leaks without it

    def test_shear_case_carries_no_alignment_info(self):
        basis = simple_span_demands(60.0, ALL)
        rfs = synthetic_rfs(basis, "shear", 250.0)
        case = identify_governing_case(rfs, 60.0)
        p = case.predictions["Type 3"]
        assert p.misalignment is None and p.aligned is None
        assert p.alignment_ok

    def test_none_aligned_falls_back_to_all_and_flags(self):
        basis = simple_span_demands(40.0, ALL)
        rfs = synthetic_rfs(basis, "positive_moment", 800.0)
        preds = predict_rating_factors(rfs, basis, "positive_moment",
                                       alignment_tol=1e-12)
        for p in preds.values():
            exact = tuple(n for n, m in p.misalignment.items() if m <= 1e-12)
            assert p.aligned == exact
            if not exact:
                assert not p.alignment_ok
                assert p.rf == pytest.approx(
                    np.mean(list(p.per_known.values())))

    def test_disabled_check_matches_plain_mean(self):
        basis = simple_span_demands(40.0, ALL)
        rfs = synthetic_rfs(basis, "positive_moment", 800.0)
        preds = predict_rating_factors(rfs, basis, "positive_moment",
                                       alignment_tol=None)
        for p in preds.values():
            assert p.misalignment is None
            assert p.rf == pytest.approx(np.mean(list(p.per_known.values())))


class TestPredictionHelper:
    def test_predict_from_explicit_basis(self):
        basis = simple_span_demands(85.0, ALL)
        rfs = synthetic_rfs(basis, "positive_moment", 2000.0)
        preds = predict_rating_factors(rfs, basis, "positive_moment")
        assert set(preds) == set(NEW_LEGAL_TRUCKS)
        for name, p in preds.items():
            truth = 2000.0 / basis.effects("positive_moment", (name,))[0]
            assert p.rf == pytest.approx(truth)
            assert set(p.per_known) == set(OHIO_KNOWN_VEHICLES)
