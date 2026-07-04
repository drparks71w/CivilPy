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
