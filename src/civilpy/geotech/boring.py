#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Canonical, library-neutral data model for a subsurface boring.

A geotechnical boring log is the hub object the rest of CivilPy reads from:
the same :class:`Borehole` can drive scour grain-size lookups in the
hydraulics library, axial capacity in the foundations modules, and soil
zone moduli for CANDE.  Ingestion (DIGGS XML, PDF logs, ...) lives in
:mod:`civilpy.geotech.boring_io` and produces these objects; nothing here
depends on how the data was read.

Units are US customary: depths and elevations in feet, particle sizes in
millimetres (the geotechnical convention for gradations), recovery in
inches.  Blow counts are dimensionless.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------- SPT

#: A single 6-inch drive increment of a Standard Penetration Test: the
#: number of hammer ``blows`` to advance ``penetration_in`` inches.  A
#: refusal increment advances less than its nominal length.
@dataclass(frozen=True)
class DriveIncrement:
    blows: int
    penetration_in: float = 6.0


@dataclass(frozen=True)
class SPTResult:
    """One Standard Penetration Test at ``depth_ft`` (top of the 18-inch
    drive).  ``increments`` are the successive 6-inch drives in order
    (seating, then the two that count)."""

    depth_ft: float
    increments: tuple[DriveIncrement, ...]
    hammer_type: str | None = None
    hammer_efficiency: str | None = None

    @property
    def total_blows(self) -> int:
        return sum(i.blows for i in self.increments)

    @property
    def total_penetration_in(self) -> float:
        return sum(i.penetration_in for i in self.increments)

    @property
    def refusal(self) -> bool:
        """True if the spoon did not advance the full nominal length
        (driven penetration short of 6 in per recorded increment)."""
        return any(i.penetration_in < 6.0 for i in self.increments)

    @property
    def n_value(self) -> int | None:
        """Field SPT blow count N: the sum of the second and third 6-inch
        increments (ASTM D1586).  With only two increments their sum is
        used; with fewer than two, ``None``."""
        n = len(self.increments)
        if n >= 3:
            return self.increments[1].blows + self.increments[2].blows
        if n == 2:
            return self.increments[0].blows + self.increments[1].blows
        return None

    def n60(self, energy_ratio: float = 0.60, rod_length_ft: float | None = None,
            borehole_diameter_in: float = 4.0, liner: bool = False) -> float | None:
        """Energy-corrected blow count N60 (Skempton 1986):
        N60 = N * (Em/0.60) * Cr * Cb * Cs, where ``energy_ratio`` Em is the
        measured/rated hammer efficiency as a decimal.  Rod-length Cr is
        applied from ``rod_length_ft`` (taken as ``depth_ft`` when omitted),
        borehole Cb from ``borehole_diameter_in``, sampler Cs from
        ``liner``."""
        n = self.n_value
        if n is None:
            return None
        rod = rod_length_ft if rod_length_ft is not None else self.depth_ft
        if rod < 13:
            cr = 0.75
        elif rod < 20:
            cr = 0.85
        elif rod < 33:
            cr = 0.95
        else:
            cr = 1.0
        if borehole_diameter_in <= 4.7:
            cb = 1.0
        elif borehole_diameter_in <= 6.0:
            cb = 1.05
        else:
            cb = 1.15
        cs = 1.2 if liner else 1.0
        return n * (energy_ratio / 0.60) * cr * cb * cs


# --------------------------------------------------------------- gradation

@dataclass(frozen=True)
class GradingPoint:
    """One point on a particle-size distribution: ``percent_passing`` finer
    than ``particle_size_mm``."""

    particle_size_mm: float
    percent_passing: float


@dataclass(frozen=True)
class GradingResult:
    """A particle-size (sieve + hydrometer) analysis on a sample taken at
    ``depth_ft``.  ``points`` are stored sorted coarse-to-fine."""

    depth_ft: float
    points: tuple[GradingPoint, ...]

    #: US No. 200 sieve opening, mm (the silt/sand fines boundary).
    FINES_SIZE_MM = 0.075

    def percent_passing_at(self, size_mm: float) -> float | None:
        """Percent finer than ``size_mm`` by log-linear interpolation on
        the gradation curve; ``None`` if outside the measured range."""
        pts = sorted(self.points, key=lambda p: p.particle_size_mm)
        if not pts or size_mm < pts[0].particle_size_mm or size_mm > pts[-1].particle_size_mm:
            # allow exact endpoints
            for p in pts:
                if abs(p.particle_size_mm - size_mm) < 1e-12:  # pragma: no cover
                    return p.percent_passing
            return None
        import math
        for a, b in zip(pts, pts[1:]):
            if a.particle_size_mm <= size_mm <= b.particle_size_mm:
                if b.particle_size_mm == a.particle_size_mm:
                    return a.percent_passing
                t = (math.log10(size_mm) - math.log10(a.particle_size_mm)) / (
                    math.log10(b.particle_size_mm) - math.log10(a.particle_size_mm))
                return a.percent_passing + t * (b.percent_passing - a.percent_passing)
        return None

    def d_size(self, percent: float) -> float | None:
        """Particle size (mm) at which ``percent`` of the sample is finer
        (e.g. ``d_size(50)`` is D50), log-linearly interpolated; ``None`` if
        the curve does not bracket that percentage."""
        pts = sorted(self.points, key=lambda p: p.percent_passing)
        if not pts or percent < pts[0].percent_passing or percent > pts[-1].percent_passing:
            return None
        import math
        for a, b in zip(pts, pts[1:]):
            if a.percent_passing <= percent <= b.percent_passing:
                if b.percent_passing == a.percent_passing:
                    return a.particle_size_mm
                t = (percent - a.percent_passing) / (b.percent_passing - a.percent_passing)
                log_d = math.log10(a.particle_size_mm) + t * (
                    math.log10(b.particle_size_mm) - math.log10(a.particle_size_mm))
                return 10 ** log_d
        return None

    @property
    def d10(self) -> float | None:
        return self.d_size(10)

    @property
    def d30(self) -> float | None:
        return self.d_size(30)

    @property
    def d50(self) -> float | None:
        """Median grain size D50, mm -- the key input to HEC-18 scour."""
        return self.d_size(50)

    @property
    def d60(self) -> float | None:
        return self.d_size(60)

    @property
    def fines_percent(self) -> float | None:
        """Percent finer than the No. 200 sieve (0.075 mm)."""
        return self.percent_passing_at(self.FINES_SIZE_MM)

    @property
    def coefficient_of_uniformity(self) -> float | None:
        """Cu = D60 / D10."""
        d10, d60 = self.d10, self.d60
        return d60 / d10 if d10 and d60 else None

    @property
    def coefficient_of_curvature(self) -> float | None:
        """Cc = D30^2 / (D10 * D60)."""
        d10, d30, d60 = self.d10, self.d30, self.d60
        return d30 ** 2 / (d10 * d60) if d10 and d30 and d60 else None


# --------------------------------------------------------------- sample / borehole

@dataclass(frozen=True)
class Sample:
    """A recovered sample interval (split spoon, Shelby tube, rock core)."""

    depth_top_ft: float
    depth_bottom_ft: float
    method: str | None = None
    recovery_in: float | None = None

    @property
    def length_in(self) -> float:
        return (self.depth_bottom_ft - self.depth_top_ft) * 12.0

    @property
    def recovery_percent(self) -> float | None:
        if self.recovery_in is None or self.length_in <= 0:
            return None
        return 100.0 * self.recovery_in / self.length_in


@dataclass
class Borehole:
    """A single subsurface boring: header location/geometry plus the
    depth-indexed sample, SPT, and gradation records read from a log."""

    boring_id: str
    project: str | None = None
    ground_elevation_ft: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    station: str | None = None
    offset_ft: float | None = None
    offset_direction: str | None = None
    total_depth_ft: float | None = None
    water_strike_depth_ft: float | None = None
    date: str | None = None
    purpose: str | None = None
    samples: list[Sample] = field(default_factory=list)
    spt: list[SPTResult] = field(default_factory=list)
    grading: list[GradingResult] = field(default_factory=list)

    def elevation_at(self, depth_ft: float) -> float | None:
        """Ground-surface elevation minus ``depth_ft`` (None if the collar
        elevation is unknown)."""
        if self.ground_elevation_ft is None:
            return None
        return self.ground_elevation_ft - depth_ft

    def spt_profile(self) -> list[tuple[float, int]]:
        """``(depth_ft, N)`` pairs sorted by depth, skipping tests whose N
        is undefined."""
        out = [(s.depth_ft, s.n_value) for s in self.spt if s.n_value is not None]
        return sorted(out)

    def n_at(self, depth_ft: float) -> int | None:
        """SPT N of the test nearest ``depth_ft`` (None if no SPT data)."""
        if not self.spt:
            return None
        nearest = min(self.spt, key=lambda s: abs(s.depth_ft - depth_ft))
        return nearest.n_value

    def grading_at(self, depth_ft: float) -> GradingResult | None:
        """Gradation analysis nearest ``depth_ft`` (None if none present)."""
        if not self.grading:
            return None
        return min(self.grading, key=lambda g: abs(g.depth_ft - depth_ft))

    def d50_at(self, depth_ft: float) -> float | None:
        """D50 (mm) of the gradation nearest ``depth_ft`` -- the scour
        input."""
        g = self.grading_at(depth_ft)
        return g.d50 if g else None
