#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the calculation-package records (calc_spec)."""

import json

import pytest

from civilpy.structural.aashto.lrfd import CheckResult
from civilpy.structural.calc_spec import (
    ArticleCheckRecord,
    CalcPackageRecord,
)


def _check(article="6.10.9", ratio_target=1.25, demand=100.0):
    return ArticleCheckRecord(
        article=article, name="shear", capacity=demand * ratio_target,
        demand=demand, ratio=ratio_target, ok=ratio_target >= 1.0)


class TestArticleCheckRecord:
    def test_from_check_freezes_a_live_result(self):
        cr = CheckResult(article="6.10.9", name="Shear resistance",
                         capacity=250.0, demand=200.0, phi=1.0,
                         details={"Vp": 431.2, "C": (0.58,)})
        rec = ArticleCheckRecord.from_check(cr)
        assert rec.ratio == pytest.approx(1.25)
        assert rec.ok is True
        assert rec.details == {"Vp": 431.2, "C": [0.58]}   # JSON-safe
        assert rec.validate() == []
        json.dumps(rec.details)

    def test_capacity_only_check(self):
        cr = CheckResult(article="6.10.11.2.3", name="Bearing stiffener",
                         capacity=800.0)
        rec = ArticleCheckRecord.from_check(cr)
        assert rec.demand is None and rec.ratio is None and rec.ok is None
        assert rec.validate() == []

    def test_demand_without_ratio_flagged(self):
        rec = ArticleCheckRecord(article="6.10.9", capacity=1.0, demand=1.0)
        assert any("ratio" in p for p in rec.validate())

    def test_ok_without_demand_flagged(self):
        rec = ArticleCheckRecord(article="6.10.9", capacity=1.0, ok=True)
        assert any("ok" in p for p in rec.validate())


class TestCalcPackageRecord:
    def _package(self, **kw):
        base = dict(title="Girder shear rating", engine="civilpy",
                    engine_version="9.9", sfn="1234567",
                    checks=(_check("6.10.9", 1.25),
                            _check("6.10.8.2.2", 1.05)),
                    prepared_by="dane")
        base.update(kw)
        return CalcPackageRecord(**base)

    def test_round_trip(self):
        pkg = self._package()
        doc = json.loads(json.dumps(pkg.to_dict()))
        assert doc["bim.type"] == "calc" and doc["subtype"] == "package"
        back = CalcPackageRecord.from_dict(doc)
        assert back == pkg
        assert back.validate() == []

    def test_governing_is_worst_rated_check(self):
        pkg = self._package()
        assert pkg.governing().article == "6.10.8.2.2"
        assert pkg.all_ok is True
        failing = self._package(checks=(_check("6.10.9", 0.92),))
        assert failing.all_ok is False

    def test_capacity_tabulation_has_no_governing(self):
        cap_only = ArticleCheckRecord(article="6.10.11.2.3", capacity=800.0)
        pkg = self._package(checks=(cap_only,))
        assert pkg.governing() is None and pkg.all_ok is None

    def test_empty_checks_invalid(self):
        assert any("checks" in p for p in
                   self._package(checks=()).validate())

    def test_nested_check_problems_surface(self):
        bad = ArticleCheckRecord(article="", capacity=1.0)
        assert any(p.startswith("checks[0].article")
                   for p in self._package(checks=(bad,)).validate())

    def test_status_cannot_outrun_signatures(self):
        assert any("checked_by" in p for p in
                   self._package(status="checked").validate())
        assert any("approved_by" in p for p in
                   self._package(status="released",
                                 checked_by="qa").validate())
        released = self._package(status="released", checked_by="qa",
                                 approved_by="chief")
        assert released.validate() == []
