#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""B5 -- the rolled-girder + splice optimizer.  Sweeps candidate shapes, gates
on girder plastic moment, auto-sizes + designs the splice, and ranks by cost."""

import pytest

from civilpy.structural.aashto.lrfd import SpliceLoads
from civilpy.structural.girder_optimizer import (
    weight_lb_ft, girder_plastic_moment, auto_splice_plates,
    optimize_splice_shape, cheapest_feasible,
)


def test_weight_from_label():
    assert weight_lb_ft("W24X104") == pytest.approx(104.0)
    assert weight_lb_ft("W30X99") == pytest.approx(99.0)


def test_plastic_moment_increases_with_weight():
    assert (girder_plastic_moment("W24X76")
            < girder_plastic_moment("W24X104")
            < girder_plastic_moment("W24X131"))


def test_auto_splice_plates_track_the_flange():
    plates, web = auto_splice_plates("W24X104", "W24X104")
    assert plates.outer_width == pytest.approx(12.8)      # = flange width
    assert plates.outer_thickness >= 0.75 / 2 + 0.0625    # 6.13.6.1.3b minimum
    assert web.thickness > 0


class TestOptimizer:
    def setup_method(self):
        loads = SpliceLoads(dc1_m=10.9, dc2_m=3.0, dw_m=4.7, ll_pos_m=337.1,
                            ll_neg_m=-212.8, ll_neg_v=-36.6)
        self.opts = optimize_splice_shape(
            loads, ["W24X76", "W24X104", "W24X131", "W27X102"],
            length_ft=90.0, max_factored_moment=900.0,
            deck_thickness=7.5, deck_eff_width=84.0, rebar_area=7.46)

    def test_girder_gate_rejects_undersized_shape(self):
        w76 = next(o for o in self.opts if o.shape == "W24X76")
        assert w76.girder_ok is False           # phi*Mp ~ 833 < 900 k-ft

    def test_feasible_options_pass_both_gates(self):
        for o in self.opts:
            if o.ok:
                assert o.girder_ok and o.splice_ok

    def test_ranked_feasible_first_then_cost(self):
        feas = [o for o in self.opts if o.ok]
        assert feas, "expected at least one feasible design"
        # feasible options come first and are sorted by ascending total cost
        costs = [o.total_cost for o in self.opts if o.ok]
        assert costs == sorted(costs)

    def test_beats_the_as_built(self):
        best = cheapest_feasible(self.opts)
        as_built = next(o for o in self.opts if o.shape == "W24X131")
        assert best is not None
        # the optimizer finds a design no more expensive than the heavy as-built
        assert best.total_cost <= as_built.total_cost

    def test_cost_is_steel_plus_splice(self):
        for o in self.opts:
            assert o.total_cost == pytest.approx(o.steel_cost + o.splice_cost)
            assert o.steel_lb == pytest.approx(o.weight_lb_ft * 90.0)
