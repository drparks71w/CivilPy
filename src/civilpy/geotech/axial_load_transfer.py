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

"""Axial pile load-transfer (t-z and q-z) curves.

The lateral-pile module (:mod:`civilpy.geotech.lateral_pile`) gives the p-y
springs that resist horizontal pile movement; this module is the axial
companion, supplying the **t-z** curves (mobilised side / skin friction per
unit length versus axial displacement) and the **q-z** curve (mobilised end
bearing at the tip versus tip settlement).  Together the three families give
the full set of foundation springs a structural model needs to support a
pier or an integral-abutment pile bent on soil rather than on fixed points.

The backbone shapes are the American Petroleum Institute recommendation
(API RP 2A-WSD, §6.7): normalised ``t/t_max`` and ``Q/Q_p`` tables against
``z/D`` (clay) or absolute displacement (sand), linearly interpolated.  The
ultimate values ``t_max`` (unit skin friction times perimeter) and ``Q_p``
(tip area times unit end bearing) come from the capacity routines in
:mod:`civilpy.geotech.deep_foundation`, so a single boring drives capacity,
settlement, and the spring model consistently.

These are normalised design curves; a settlement-sensitive structure should
be checked against a project-specific load-transfer analysis.

Units: displacements in inches, forces in pounds, diameters in inches (so a
t-z secant modulus is lb/in per inch of pile = lb/in^2 and a spring constant
is lb/in) -- matching :mod:`civilpy.geotech.lateral_pile`.  Use
:func:`spring_constant_kip_per_in` when handing values to a kip-unit model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

#: A small displacement floor (in) so a secant modulus stays finite at w = 0.
_W_FLOOR = 1.0e-6

# API RP 2A-WSD normalised backbones --------------------------------------
#: Clay t-z: (z/D, t/t_max).  Residual taken equal to peak (no softening).
_API_TZ_CLAY = ((0.0, 0.0), (0.0016, 0.30), (0.0031, 0.50), (0.0057, 0.75),
                (0.0080, 0.90), (0.0100, 1.00), (0.0200, 1.00))
#: Sand t-z: (z [in], t/t_max).  Peak mobilised at z = 0.10 in.
_API_TZ_SAND = ((0.0, 0.0), (0.10, 1.00))
#: q-z (clay and sand): (z/D, Q/Q_p).  Peak mobilised at z = 0.10 D.
_API_QZ = ((0.0, 0.0), (0.002, 0.25), (0.013, 0.50), (0.042, 0.75),
           (0.073, 0.90), (0.100, 1.00))


def _interp_ratio(table, x: float) -> float:
    """Linear interpolation on a normalised ``((x, ratio), ...)`` backbone,
    clamped flat beyond the last point."""
    xs = [p[0] for p in table]
    ys = [p[1] for p in table]
    return float(np.interp(abs(x), xs, ys))


# ============================================================ t-z curves


class TZCurve:
    """Base class for axial side-resistance (t-z) curves.  Subclasses
    implement :meth:`t` and expose ``t_max``; the secant modulus follows."""

    t_max: float

    def t(self, w: float) -> float:  # pragma: no cover - interface
        """Mobilised skin friction per unit length (lb/in) at axial
        displacement ``w`` (in)."""
        raise NotImplementedError

    def secant_modulus(self, w: float) -> float:
        """Secant load-transfer modulus ``t/w`` (lb/in^2) at displacement
        ``w`` (in); uses a displacement floor so it stays finite at w = 0."""
        ww = max(abs(w), _W_FLOOR)
        return self.t(ww) / ww


@dataclass
class APITZCurve(TZCurve):
    """API RP 2A-WSD t-z curve.

    ``t_max`` is the ultimate side resistance per unit pile length (lb/in) --
    the unit skin friction times the pile perimeter.  ``soil`` selects the
    normalised backbone: ``"clay"`` uses the z/D table (so ``diameter`` in
    inches is required), ``"sand"`` mobilises ``t_max`` at a fixed 0.10 in.
    """

    t_max: float
    soil: str = "clay"
    diameter: float = 12.0

    def t(self, w: float) -> float:
        if self.soil == "sand":
            ratio = _interp_ratio(_API_TZ_SAND, abs(w))
        elif self.soil == "clay":
            ratio = _interp_ratio(_API_TZ_CLAY, abs(w) / self.diameter)
        else:
            raise ValueError(f"unknown soil {self.soil!r} (use 'clay' or 'sand')")
        return math.copysign(ratio * self.t_max, w) if w else 0.0


# ============================================================ q-z curve


class QZCurve:
    """Base class for end-bearing (q-z) curves.  Subclasses implement
    :meth:`q` and expose ``q_max``."""

    q_max: float

    def q(self, w: float) -> float:  # pragma: no cover - interface
        """Mobilised tip resistance (lb) at tip settlement ``w`` (in)."""
        raise NotImplementedError

    def secant_modulus(self, w: float) -> float:
        """Secant tip stiffness ``Q/w`` (lb/in) at settlement ``w`` (in)."""
        ww = max(abs(w), _W_FLOOR)
        return self.q(ww) / ww


@dataclass
class APIQZCurve(QZCurve):
    """API RP 2A-WSD q-z curve.  ``q_max`` is the ultimate tip resistance
    (lb) = tip area times unit end bearing; ``diameter`` (in) sets the z/D
    normalisation (full mobilisation at a tip settlement of 0.10 D)."""

    q_max: float
    diameter: float = 12.0

    def q(self, w: float) -> float:
        ratio = _interp_ratio(_API_QZ, abs(w) / self.diameter)
        # q-z is one-sided: the tip bears only in compression (downward +).
        return ratio * self.q_max if w > 0 else 0.0


# ============================================================ helpers


def spring_constant_kip_per_in(force_lb_per_in_or_lb: float) -> float:
    """Convert a lb/in (or lb) spring constant to kip/in (or kip)."""
    return force_lb_per_in_or_lb / 1000.0


def axial_pile_springs(
    curve: TZCurve,
    embedded_length: float,
    n_nodes: int,
    design_disp: float,
) -> list[tuple[float, float]]:
    """Discretise an embedded pile into ``n_nodes`` equally spaced axial
    (t-z) springs and return ``(depth_in, k_lb_per_in)`` for each.

    The spring constant at a node is the t-z secant modulus at ``design_disp``
    (in) times the tributary length (in) the node represents -- a linearised
    Winkler spring suitable for a MIDAS nodal spring support.  ``end`` nodes
    carry half the tributary length.  ``embedded_length`` is in inches.
    """
    if n_nodes < 2:
        raise ValueError("need at least two nodes to span the embedment")
    h = embedded_length / (n_nodes - 1)
    es = curve.secant_modulus(design_disp)
    out = []
    for i in range(n_nodes):
        trib = h if 0 < i < n_nodes - 1 else h / 2.0
        depth = i * h
        out.append((round(depth, 6), es * trib))
    return out
