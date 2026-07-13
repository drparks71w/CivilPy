#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Continuous-beam analysis for line girders (the offline substitute for a live
MIDAS run when producing dead-load and moving-load moment envelopes).

A prismatic (or piecewise-``EI``) beam on simple supports is solved by the
direct-stiffness / slope-deflection method with the support rotations as the
only unknowns (every support pins the vertical translation).  From the solved
member-end moments the support reactions follow, and the bending moment at any
section is then pure statics.

Moving-load envelopes come from **influence lines**: a unit load is walked
across the span and the moment at the section of interest recorded, giving an
:class:`~civilpy.structural.influence_lines.InfluenceLine` that the existing
``hl93_effect`` / ``maximize_axle_train`` machinery turns into an HL-93 envelope.

Sign convention: downward loads positive; sagging bending moment positive.
Lengths in feet, loads in kips / kip-ft, ``ei`` in consistent units (its
absolute value cancels for statically-determinate reactions but sets the
distribution across an indeterminate beam, so only relative ``ei`` matters)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from civilpy.structural.influence_lines import (
    InfluenceLine, influence_line_from_ordinates,
)


@dataclass
class _UDL:
    w: float
    x0: float
    x1: float


@dataclass
class _Point:
    p: float
    x: float


@dataclass
class ContinuousBeam:
    """A continuous beam defined by its ordered support positions (ft).

    >>> b = ContinuousBeam([0.0, 20.0, 40.0])   # two 20-ft spans
    >>> b.add_udl(2.0)                            # 2 klf everywhere
    >>> round(b.moment_at(20.0), 3)               # interior support: -wL^2/8
    -100.0
    """

    supports: list[float]
    ei: float = 1.0
    _loads: list = field(default_factory=list)

    def __post_init__(self):
        self.supports = [float(s) for s in self.supports]
        if list(self.supports) != sorted(self.supports):
            raise ValueError("support positions must be increasing")
        if len(self.supports) < 2:
            raise ValueError("need at least two supports")

    @property
    def length(self) -> float:
        return self.supports[-1] - self.supports[0]

    # ---- load application --------------------------------------------------
    def add_udl(self, w: float, x0: float | None = None,
                x1: float | None = None) -> "ContinuousBeam":
        """Add a uniform load ``w`` (kip/ft, down +) over ``[x0, x1]`` (default
        the whole beam)."""
        self._loads.append(_UDL(w, self.supports[0] if x0 is None else x0,
                                self.supports[-1] if x1 is None else x1))
        return self

    def add_point(self, p: float, x: float) -> "ContinuousBeam":
        """Add a point load ``p`` (kip, down +) at station ``x`` (ft)."""
        self._loads.append(_Point(p, x))
        return self

    # ---- fixed-end moments -------------------------------------------------
    def _span_fem(self, a: float, b: float, loads) -> tuple[float, float]:
        """Fixed-end moments (M_ab, M_ba) for span ``[a, b]`` under ``loads``,
        sagging-positive member-end-moment convention
        (``FEM_ab = -wL^2/12``, ``FEM_ba = +wL^2/12`` for a full UDL)."""
        span = b - a
        m_ab = m_ba = 0.0
        for ld in loads:
            if isinstance(ld, _UDL):
                lo, hi = max(ld.x0, a), min(ld.x1, b)
                if hi <= lo:
                    continue
                # discretize a partial UDL into point loads (exact enough at
                # the sampling below); a full-span UDL hits the closed form.
                if abs(lo - a) < 1e-9 and abs(hi - b) < 1e-9:
                    m_ab += -ld.w * span ** 2 / 12.0
                    m_ba += ld.w * span ** 2 / 12.0
                else:
                    n = max(2, int((hi - lo) / span * 50) + 2)
                    dx = (hi - lo) / n
                    for i in range(n):
                        xc = lo + (i + 0.5) * dx
                        fab, fba = self._point_fem(xc - a, span, ld.w * dx)
                        m_ab += fab
                        m_ba += fba
            elif isinstance(ld, _Point) and a - 1e-9 <= ld.x <= b + 1e-9:
                fab, fba = self._point_fem(ld.x - a, span, ld.p)
                m_ab += fab
                m_ba += fba
        return m_ab, m_ba

    @staticmethod
    def _point_fem(dist: float, span: float, p: float) -> tuple[float, float]:
        """FEM for a point load ``p`` at ``dist`` from the left end of a span of
        length ``span``: ``M_ab = -P a b^2 / L^2``, ``M_ba = +P a^2 b / L^2``."""
        a = min(max(dist, 0.0), span)
        b = span - a
        return (-p * a * b ** 2 / span ** 2, p * a ** 2 * b / span ** 2)

    # ---- solve -------------------------------------------------------------
    def _end_moments(self, loads):
        """Solve support rotations and return per-span (M_left, M_right)
        member-end moments (sagging positive)."""
        n = len(self.supports)
        k = np.zeros((n, n))
        f = np.zeros(n)
        fems = []
        for e in range(n - 1):
            a, b = self.supports[e], self.supports[e + 1]
            span = b - a
            r = 2.0 * self.ei / span
            # slope-deflection rotational stiffness for the span
            k[e, e] += 2.0 * r
            k[e, e + 1] += r
            k[e + 1, e] += r
            k[e + 1, e + 1] += 2.0 * r
            m_ab, m_ba = self._span_fem(a, b, loads)
            fems.append((m_ab, m_ba))
            # nodal equilibrium: sum of member-end moments at a node = 0
            f[e] -= m_ab
            f[e + 1] -= m_ba
        theta = np.linalg.solve(k, f)
        end_moments = []
        for e in range(n - 1):
            a, b = self.supports[e], self.supports[e + 1]
            r = 2.0 * self.ei / (b - a)
            m_ab = r * (2.0 * theta[e] + theta[e + 1]) + fems[e][0]
            m_ba = r * (theta[e] + 2.0 * theta[e + 1]) + fems[e][1]
            end_moments.append((m_ab, m_ba))
        return end_moments

    def reactions(self, loads=None) -> list[float]:
        """Support reactions (kip, up +) under the applied (or supplied) loads."""
        loads = self._loads if loads is None else loads
        ends = self._end_moments(loads)
        n = len(self.supports)
        r = [0.0] * n
        for e in range(n - 1):
            a, b = self.supports[e], self.supports[e + 1]
            span = b - a
            m_ab, m_ba = ends[e]
            # simple-span shear at each end from the span loads, then the
            # end-moment couple (m_ab + m_ba)/L redistributes it.
            w_tot, m_about_a = self._span_load_resultant(a, b, loads)
            # Support bending moments (sagging +) are M_A = m_ab, M_B = -m_ba in
            # the slope-deflection (clockwise-positive) convention, so the end
            # moments add a constant shear (M_B - M_A)/L = -(m_ab + m_ba)/L to
            # the simple-span left reaction.
            v_a = m_about_a_to_shear(w_tot, m_about_a, span) - (m_ab + m_ba) / span
            v_b = w_tot - v_a
            r[e] += v_a
            r[e + 1] += v_b
        return r

    @staticmethod
    def _span_load_resultant(a, b, loads):
        """Total downward load on span ``[a,b]`` and its moment about ``a``."""
        w_tot = 0.0
        m_a = 0.0
        for ld in loads:
            if isinstance(ld, _UDL):
                lo, hi = max(ld.x0, a), min(ld.x1, b)
                if hi <= lo:
                    continue
                w = ld.w * (hi - lo)
                xc = 0.5 * (lo + hi)
                w_tot += w
                m_a += w * (xc - a)
            elif isinstance(ld, _Point) and a - 1e-9 <= ld.x <= b + 1e-9:
                w_tot += ld.p
                m_a += ld.p * (ld.x - a)
        return w_tot, m_a

    def moment_at(self, x: float, loads=None) -> float:
        """Bending moment (kip-ft, sagging +) at station ``x`` by statics from
        the solved reactions and the loads to the left of ``x``."""
        loads = self._loads if loads is None else loads
        r = self.reactions(loads)
        m = 0.0
        for xi, ri in zip(self.supports, r):
            if xi < x - 1e-12:
                m += ri * (x - xi)
        for ld in loads:
            if isinstance(ld, _UDL):
                lo, hi = ld.x0, min(ld.x1, x)
                if hi > lo:
                    w = ld.w * (hi - lo)
                    xc = 0.5 * (lo + hi)
                    m -= w * (x - xc)
            elif isinstance(ld, _Point) and ld.x < x - 1e-12:
                m -= ld.p * (x - ld.x)
        return m

    def moment_diagram(self, n: int = 201, loads=None):
        """``(stations, moments)`` sampled ``n`` points along the beam."""
        xs = list(np.linspace(self.supports[0], self.supports[-1], n))
        return xs, [self.moment_at(x, loads) for x in xs]

    def moment_influence_line(self, x_section: float, *, n: int = 201
                              ) -> InfluenceLine:
        """Influence line for the bending moment at ``x_section``: a unit
        downward load walked across the beam.  Feed the result to
        ``InfluenceLine.hl93_effect`` for the HL-93 live-load envelope."""
        positions = list(np.linspace(self.supports[0], self.supports[-1], n))
        etas = [self.moment_at(x_section, [_Point(1.0, p)]) for p in positions]
        return influence_line_from_ordinates(
            positions, etas, length=self.length,
            label=f"M @ {x_section:.1f}")


def m_about_a_to_shear(w_tot, m_about_a, span):
    """Simple-span left reaction share: ``V_a = w_tot - m_about_a/span`` (the
    part of the load carried by the left end before the end-moment couple)."""
    if span == 0:
        return 0.0
    return w_tot - m_about_a / span
