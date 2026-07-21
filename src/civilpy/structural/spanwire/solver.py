#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Span-wire sag-tension solver.

Replicates the gravity statics of ODOT's legacy SWISS ("Span Wire Signal
Support") program: a messenger wire strung between two poles carries
concentrated loads (signal heads, signs) and its own distributed weight;
the horizontal tension is found so the system sag — the elevation
difference between the highest attachment and the lowest point of the wire
— matches the designer's required sag (typically 3%–5% of the pole
spacing).

Units: lb, ft.  Elevations are relative; positive up.

Method: for a wire with horizontal tension ``H`` under vertical loads, the
drop below the attachment chord equals ``M(x)/H`` where ``M`` is the moment
of the equivalent simply-supported beam (the cable–beam analogy, exact for
shallow spans with vertical loads).  ``solve`` adjusts ``H`` by bisection
until the system sag matches — the same iterate-tension-to-sag scheme the
SWISS manual describes, so results can be validated golden-file style
against the legacy executable.

Multi-segment configurations (Wye, H, Delta, Hybrid, Box — segments joined
at bullrings, with plan-geometry tension relations) are the next layer and
will build on this single-span solver.

The legacy ASD wind treatment (flat pressure folded into a "design factor")
is provided only for parity checks via :func:`swiss_design_factor`; new
design should factor loads per :mod:`civilpy.structural.aashto.lts`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SpanLoad:
    """A concentrated load hung on the span (signal head or sign)."""

    x_ft: float
    weight_lb: float
    area_sqft: float = 0.0
    label: str = ""


@dataclass(frozen=True)
class SpanSolution:
    """Result of a sag-tension solve.

    ``horizontal_tension_lb`` is the SWISS "stringing tension" — the
    horizontal, dead-load-only pull on each pole.  Reactions are the
    vertical forces the supports apply to the wire, positive up; a low
    point exists strictly inside the span only when both are positive.
    """

    horizontal_tension_lb: float
    sag_ft: float
    start_reaction_lb: float
    end_reaction_lb: float
    low_point_x_ft: float
    low_point_elevation_ft: float


class SimpleSpan:
    """A single span segment between two attachment points."""

    def __init__(
        self,
        length_ft: float,
        wire_weight_plf: float = 0.0,
        start_elevation_ft: float = 0.0,
        end_elevation_ft: float = 0.0,
        loads: tuple[SpanLoad, ...] | list[SpanLoad] = (),
    ):
        if length_ft <= 0:
            raise ValueError("span length must be positive")
        if wire_weight_plf < 0:
            raise ValueError("wire weight cannot be negative")
        for load in loads:
            if not 0.0 <= load.x_ft <= length_ft:
                raise ValueError(f"load at x = {load.x_ft} ft is outside the span")
            if load.weight_lb < 0:
                raise ValueError("load weights cannot be negative")
        self.length_ft = length_ft
        self.wire_weight_plf = wire_weight_plf
        self.start_elevation_ft = start_elevation_ft
        self.end_elevation_ft = end_elevation_ft
        self.loads = tuple(sorted(loads, key=lambda p: p.x_ft))

    # -- equivalent-beam statics ------------------------------------------

    @property
    def total_load_lb(self) -> float:
        return sum(p.weight_lb for p in self.loads) + self.wire_weight_plf * self.length_ft

    @property
    def _beam_start_reaction(self) -> float:
        length = self.length_ft
        r0 = sum(p.weight_lb * (length - p.x_ft) / length for p in self.loads)
        return r0 + self.wire_weight_plf * length / 2.0

    def _beam_moment(self, x: float) -> float:
        m = self._beam_start_reaction * x - self.wire_weight_plf * x * x / 2.0
        for p in self.loads:
            if p.x_ft < x:
                m -= p.weight_lb * (x - p.x_ft)
        return m

    @property
    def _chord_slope(self) -> float:
        return (self.end_elevation_ft - self.start_elevation_ft) / self.length_ft

    # -- wire geometry at a trial tension ---------------------------------

    def wire_elevation(self, x: float, horizontal_tension_lb: float) -> float:
        """Elevation of the wire at ``x`` for a trial horizontal tension."""
        chord = self.start_elevation_ft + self._chord_slope * x
        return chord - self._beam_moment(x) / horizontal_tension_lb

    def _low_point(self, h: float) -> tuple[float, float]:
        """(x, elevation) of the lowest point of the wire at tension ``h``."""
        candidates = [0.0, self.length_ft] + [p.x_ft for p in self.loads]
        w = self.wire_weight_plf
        if w > 0.0:
            # Within each segment the profile is a parabola; its vertex is
            # where the wire slope (chord slope minus beam shear / H) is 0.
            bounds = sorted({0.0, self.length_ft, *(p.x_ft for p in self.loads)})
            slope = self._chord_slope
            for a, b in zip(bounds, bounds[1:]):
                shear_a = self._beam_start_reaction - sum(
                    p.weight_lb for p in self.loads if p.x_ft <= a
                )
                # shear(x) = shear_a - w*(x - a) within (a, b)
                x_v = a + (shear_a - slope * h) / w
                if a < x_v < b:
                    candidates.append(x_v)
        return min(
            ((x, self.wire_elevation(x, h)) for x in candidates),
            key=lambda pair: pair[1],
        )

    def system_sag(self, horizontal_tension_lb: float) -> float:
        """Highest attachment minus lowest wire point, ft."""
        high = max(self.start_elevation_ft, self.end_elevation_ft)
        return high - self._low_point(horizontal_tension_lb)[1]

    # -- the solve ---------------------------------------------------------

    def solve(self, required_sag_ft: float, tol_ft: float = 1e-6) -> SpanSolution:
        """Find the horizontal tension that produces the required sag."""
        elevation_span = abs(self.start_elevation_ft - self.end_elevation_ft)
        if required_sag_ft <= elevation_span:
            raise ValueError(
                f"required sag ({required_sag_ft} ft) must exceed the "
                f"attachment elevation difference ({elevation_span} ft)"
            )
        if self.total_load_lb <= 0.0:
            raise ValueError("span carries no load; sag is undefined")

        # Bracket: sag decreases monotonically with H.
        h_hi = max(self.total_load_lb, 1.0)
        while self.system_sag(h_hi) > required_sag_ft:
            h_hi *= 2.0
        h_lo = h_hi / 2.0
        while self.system_sag(h_lo) < required_sag_ft:
            h_lo /= 2.0

        while h_hi - h_lo > max(1e-9, 1e-12 * h_hi):
            h_mid = (h_lo + h_hi) / 2.0
            if self.system_sag(h_mid) > required_sag_ft:
                h_lo = h_mid
            else:
                h_hi = h_mid
            if abs(self.system_sag(h_mid) - required_sag_ft) < tol_ft:
                h_lo = h_hi = h_mid
        h = (h_lo + h_hi) / 2.0

        slope = self._chord_slope
        beam_r0 = self._beam_start_reaction
        start_reaction = beam_r0 - h * slope
        end_reaction = (self.total_load_lb - beam_r0) + h * slope
        low_x, low_y = self._low_point(h)
        return SpanSolution(
            horizontal_tension_lb=h,
            sag_ft=self.system_sag(h),
            start_reaction_lb=start_reaction,
            end_reaction_lb=end_reaction,
            low_point_x_ft=low_x,
            low_point_elevation_ft=low_y,
        )

    # -- design conveniences ----------------------------------------------

    def attachment_elevations(
        self,
        solution: SpanSolution,
        clearance_ft: float,
        pavement_elevation_ft: float = 0.0,
    ) -> tuple[float, float]:
        """Absolute attachment elevations so the wire's lowest point sits
        exactly ``clearance_ft`` above the pavement."""
        shift = pavement_elevation_ft + clearance_ft - solution.low_point_elevation_ft
        return (self.start_elevation_ft + shift, self.end_elevation_ft + shift)


def swiss_design_factor(
    total_weight_lb: float, total_area_sqft: float, wind_pressure_psf: float = 42.0
) -> float:
    """The legacy SWISS/ASD "design factor" — for parity checks only.

    ``sqrt(DL^2 + (area * q)^2) / DL * 1.1``: the ratio of the dead+wind
    resultant to dead load, plus 10%.  ODOT's legacy default inputs were
    42 psf and a 1.80 floor.  New design should factor wind per LRFD-LTS
    instead (:mod:`civilpy.structural.aashto.lts`).
    """
    if total_weight_lb <= 0:
        raise ValueError("dead load must be positive")
    wind = total_area_sqft * wind_pressure_psf
    return math.hypot(total_weight_lb, wind) / total_weight_lb * 1.1


def pole_base_moment(
    horizontal_tension_lb: float, attachment_height_ft: float, factor: float = 1.0
) -> float:
    """Pole base moment, ft-lb: stringing tension times attachment height,
    times an optional amplification factor (the legacy design factor, or a
    load factor from an LRFD combination)."""
    return horizontal_tension_lb * attachment_height_ft * factor


__all__ = [
    "SpanLoad",
    "SpanSolution",
    "SimpleSpan",
    "swiss_design_factor",
    "pole_base_moment",
]
