#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""G6 -- field-splice placement from a moment envelope.  Pure (synthetic
envelope, no live session)."""

import pytest

from civilpy.structural.girder_pipeline import (
    n_field_splices, place_splices, SpliceCandidate,
    girder_line_envelope, hl93_pos_neg,
)


@pytest.mark.parametrize("length, ship, n", [
    (200, 100, 1),      # exactly two pieces
    (200, 200, 0),      # ships whole
    (90, 100, 0),
    (200, 70, 2),       # ceil(2.857) - 1
    (200, 120, 1),
    (400, 100, 3),
])
def test_n_field_splices(length, ship, n):
    assert n_field_splices(length, ship) == n


def _notched_envelope(notch=110.0):
    """A moment envelope with a clear low-moment window at ``notch`` (both live
    extremes and the superimposed loads pass through ~zero there)."""
    stations = [float(x) for x in range(0, 205, 5)]
    moments = {
        "dc1": [0.5 * (x - 100.0) for x in stations],   # zero at x=100
        "dc2": [0.1 * abs(x - notch) for x in stations],
        "dw": [0.05 * abs(x - notch) for x in stations],
        "ll_pos": [5.0 * abs(x - notch) for x in stations],
        "ll_neg": [-3.0 * abs(x - notch) for x in stations],
    }
    return stations, moments


class TestPlacement:
    def test_one_splice_lands_in_the_low_moment_window(self):
        stations, moments = _notched_envelope(notch=110.0)
        picks = place_splices(stations, moments, ship_max_ft=120.0)
        assert len(picks) == 1
        assert isinstance(picks[0], SpliceCandidate)
        # the notch at 110 is inside the shipping window [80, 120]
        assert picks[0].station == pytest.approx(110.0, abs=1.0)
        # live extremes vanish at the notch; only the small dc1 residual
        # (0.5*(110-100)=5 -> 1.25*5=6.25 k-ft) remains
        assert picks[0].factored_moment == pytest.approx(6.25, abs=1.5)

    def test_shipping_constraint_forces_the_only_feasible_cut(self):
        stations, moments = _notched_envelope(notch=110.0)
        # L=200, ship=100 -> the sole feasible single cut is exactly x=100
        picks = place_splices(stations, moments, ship_max_ft=100.0)
        assert len(picks) == 1
        assert picks[0].station == pytest.approx(100.0, abs=0.5)

    def test_pieces_never_exceed_ship_max(self):
        stations, moments = _notched_envelope()
        picks = place_splices(stations, moments, ship_max_ft=70.0)
        assert len(picks) == 2
        cuts = [0.0] + [p.station for p in picks] + [200.0]
        pieces = [b - a for a, b in zip(cuts, cuts[1:])]
        assert all(p <= 70.0 + 1e-6 for p in pieces), pieces

    def test_demand_set_carried_to_splice_loads(self):
        stations, moments = _notched_envelope(notch=110.0)
        p = place_splices(stations, moments, ship_max_ft=120.0)[0]
        # at the notch the live demands are ~0 and dc1 ~ 0.5*(110-100)=5
        assert p.loads.dc1_m == pytest.approx(5.0, abs=0.6)
        assert p.loads.ll_pos_m == pytest.approx(0.0, abs=6.0)
        assert p.loads.ll_neg_m == pytest.approx(0.0, abs=4.0)

    def test_no_splice_when_it_ships_whole(self):
        stations, moments = _notched_envelope()
        assert place_splices(stations, moments, ship_max_ft=250.0) == []


class TestOfflineEndToEnd:
    """ContinuousBeam envelope -> place_splices -> design, on the placeholder
    60-80-60 benchmark (no live MIDAS)."""

    def setup_method(self):
        # interior girder, klf; DF ~ 0.65; coarse sampling keeps the test fast
        self.stations, self.M = girder_line_envelope(
            [0, 60, 140, 200], dc1_klf=0.85, dc2_klf=0.15, dw_klf=0.14,
            n_sections=15, gdf=0.65, il_samples=81)

    def test_envelope_is_physically_sensible(self):
        import numpy as np
        m = self.M
        # hogging over the piers, sagging at interior mid-span
        assert np.interp(60, self.stations, m["dc1"]) < 0
        assert np.interp(100, self.stations, m["dc1"]) > 0
        # live-load envelope brackets zero (positive and negative reach)
        assert max(m["ll_pos"]) > 0 and min(m["ll_neg"]) < 0

    def test_pipeline_places_and_designs_a_splice(self):
        from civilpy.structural.aashto.lrfd.composite import design_rolled_splice
        from civilpy.structural.aashto.lrfd import BoltSpec, PlatePair, WebPlate
        picks = place_splices(self.stations, self.M, ship_max_ft=130.0)
        assert len(picks) == 1
        p = picks[0]
        # placed in a low-moment window near the pier-60 contraflexure
        assert 60.0 < p.station < 90.0
        plates = PlatePair("Grade 50", 0.375, 5.5, 0.375, 12.75, 2)
        d = design_rolled_splice(
            "W24X131", "W24X104", p.loads, deck_thickness=7.5,
            deck_eff_width=84.0, rebar_area=7.46,
            bolts=BoltSpec("A325", 0.875, flange_threads_excluded=False,
                           web_threads_excluded=False, surface_class="C",
                           hole_type="oversize"),
            top_plates=plates, bottom_plates=plates,
            web_plate=WebPlate("Grade 50", 0.4375, 2),
            top_flange_rows=2, bottom_flange_rows=2, web_rows=4,
            bolt_spacing=3.0, flange_edge=1.5, flange_end=1.5,
            web_edge=1.5, web_end=1.5, design_year=2016)
        assert d.ok
        assert d.top_flange.total_bolts >= 10

