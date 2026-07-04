#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Line-girder field-splice placement (stage **G6**).

Given a girder's moving-load moment envelope (per load case, sampled along the
span), decide **how many** field splices shipping length forces and **where**
to put them: in the low-moment windows near the dead-load contraflexure points,
subject to every field piece being no longer than the shippable length.

    n_splices = ceil(L / L_ship) - 1

Each candidate is returned with the unfactored per-case demand set at its
station, ready to hand to the splice designer as a
:class:`~civilpy.structural.aashto.lrfd.SpliceLoads`.  The engineer accepts or
drags the ``gdr.kind=splice`` markers G8 then stamps into the ``.3dm``.

This module is pure: it operates on sampled envelopes (from MIDAS via G5, or any
line-girder analysis) and never touches a live session.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from civilpy.structural.aashto.lrfd import SpliceLoads

# the load cases the placement + splice designer consume, in SpliceLoads order
_CASES = ("dc1", "dc2", "dw", "ll_pos", "ll_neg")


@dataclass
class SpliceCandidate:
    """A suggested field-splice location and the demand there."""
    station: float                 # ft from the girder's start
    factored_moment: float         # governing Strength I moment magnitude, k-ft
    loads: SpliceLoads             # unfactored per-case demands at the station


def n_field_splices(length_ft: float, ship_max_ft: float) -> int:
    """Number of field splices shipping length forces on a girder of
    ``length_ft`` when the longest shippable piece is ``ship_max_ft``."""
    if ship_max_ft <= 0:
        raise ValueError("ship_max_ft must be positive")
    return max(0, math.ceil(length_ft / ship_max_ft - 1e-9) - 1)


def _interp(stations, values, x):
    """Linear interpolation of ``values`` (aligned with ``stations``) at x."""
    if x <= stations[0]:
        return values[0]
    if x >= stations[-1]:
        return values[-1]
    for i in range(1, len(stations)):
        if x <= stations[i]:
            x0, x1 = stations[i - 1], stations[i]
            t = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
            return values[i - 1] + t * (values[i] - values[i - 1])
    return values[-1]


def _strength_magnitude(cases_at):
    """Governing Strength I moment magnitude from a per-case dict at a station:
    max of the positive and negative combinations (AASHTO 3.4.1)."""
    dc = cases_at["dc1"] + cases_at["dc2"]
    dw = cases_at["dw"]
    pos = 1.25 * dc + 1.50 * dw + 1.75 * cases_at["ll_pos"]
    neg = 0.90 * dc + 0.65 * dw + 1.75 * cases_at["ll_neg"]
    return max(abs(pos), abs(neg))


def place_splices(stations, moments, ship_max_ft, *, samples: int = 400):
    """Suggest field-splice stations for one girder.

    Parameters
    ----------
    stations : list[float]
        Increasing sample positions along the girder (ft), from 0 to L.
    moments : dict[str, list[float]]
        Per-case moments (k-ft) aligned with ``stations``.  Must include the
        keys ``dc1``, ``dc2``, ``dw``, ``ll_pos``, ``ll_neg``.  ``dc1`` (the
        non-composite dead load) locates the contraflexure the splice hides in.
    ship_max_ft : float
        Longest shippable field piece (``gdr.ship_max``).
    samples : int
        Search resolution across each splice's feasible shipping window.

    Returns
    -------
    list[SpliceCandidate]
        ``n_field_splices(L, ship_max)`` candidates, ordered along the span,
        each at the lowest-|Strength I| station within its shipping-feasible
        window (contraflexure wins, since dead + live both pass through zero
        there).
    """
    length = stations[-1]
    n = n_field_splices(length, ship_max_ft)
    if n == 0:
        return []
    missing = [k for k in _CASES if k not in moments]
    if missing:
        raise KeyError(f"moments is missing case(s): {missing}")

    picks = []
    prev = 0.0
    for k in range(1, n + 1):
        # feasible window: every preceding piece and every following piece must
        # be <= ship_max.  Lower bound keeps the *remaining* pieces shippable;
        # upper bound keeps the pieces *so far* (from prev cut) shippable.
        lo = max(prev + 1e-6, length - (n + 1 - k) * ship_max_ft)
        hi = min(length - 1e-6, prev + ship_max_ft)
        if hi < lo:                      # numerically forced cut
            lo = hi = 0.5 * (lo + hi)
        best_x, best_m = lo, math.inf
        step = (hi - lo) / max(samples, 1)
        x = lo
        while x <= hi + 1e-9:
            cases_at = {c: _interp(stations, moments[c], x) for c in _CASES}
            m = _strength_magnitude(cases_at)
            if m < best_m:
                best_x, best_m = x, m
            x += step if step > 0 else (hi - lo + 1.0)
        cases_at = {c: _interp(stations, moments[c], best_x) for c in _CASES}
        picks.append(SpliceCandidate(
            station=best_x, factored_moment=best_m,
            loads=SpliceLoads(
                dc1_m=cases_at["dc1"], dc2_m=cases_at["dc2"],
                dw_m=cases_at["dw"], ll_pos_m=cases_at["ll_pos"],
                ll_neg_m=cases_at["ll_neg"])))
        prev = best_x
    return picks
