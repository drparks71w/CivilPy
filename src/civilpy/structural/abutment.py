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

"""Cantilever retaining walls and stub / full-height abutments.

A :class:`RetainingWall` carries the geometry of a conventional cantilever
wall (toe, stem, heel, footing) and computes the three external-stability
checks every wall and spread-footing abutment must satisfy -- overturning,
sliding, and bearing -- driving the earth pressures from the Rankine and
Coulomb coefficients already in :mod:`civilpy.geotech.lateral_earth` and the
contact-pressure distribution from
:mod:`civilpy.geotech.shallow_foundation`.  The structural design of the
stem, toe, and heel as reinforced-concrete cantilevers reuses the AASHTO
LRFD resistance functions in
:mod:`civilpy.structural.aashto.lrfd.concrete`.  A wingwall is handled as a
retaining wall taken at its average exposed height.

Units: feet, pounds, pcf (pressures psf), everything per running foot of
wall; the structural helpers convert to the kip-inch-ksi LRFD convention.
Moments and lever arms are measured about the bottom front corner of the
toe.  Angles in degrees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.geotech.lateral_earth import coulomb_ka, rankine_ka, rankine_kp
from civilpy.geotech.shallow_foundation import contact_pressure
from civilpy.structural.aashto.lrfd.concrete import (
    rc_rectangular_flexural_resistance,
    rc_shear_resistance,
)
from civilpy.structural.aashto.lrfd.core import CheckResult


@dataclass
class StabilityResult:
    """External-stability summary for a retaining wall / abutment, per foot
    of wall."""

    sum_v: float            # total vertical load (lb/ft)
    sum_h: float            # total horizontal thrust (lb/ft)
    resisting_moment: float  # about the toe (lb-ft/ft)
    overturning_moment: float
    eccentricity: float     # of the base resultant (ft, + toward heel)
    base_width: float
    contact: object         # ContactPressure
    passive: float = 0.0
    fs_required_sliding: float = 1.5
    fs_required_overturning: float = 2.0
    details: dict = field(default_factory=dict)

    @property
    def fs_overturning(self) -> float:
        return self.resisting_moment / self.overturning_moment

    @property
    def fs_sliding(self) -> float:
        return self.details["sliding_resistance"] / self.sum_h

    @property
    def resultant_in_middle_third(self) -> bool:
        return abs(self.eccentricity) <= self.base_width / 6.0

    @property
    def q_max(self) -> float:
        return self.contact.q_max

    @property
    def q_min(self) -> float:
        return self.contact.q_min

    @property
    def ok_overturning(self) -> bool:
        return self.fs_overturning >= self.fs_required_overturning

    @property
    def ok_sliding(self) -> bool:
        return self.fs_sliding >= self.fs_required_sliding

    def bearing_ok(self, allowable: float) -> bool:
        """True if the peak contact pressure is within ``allowable`` (psf)."""
        return self.q_max <= allowable


@dataclass
class RetainingWall:
    """Cantilever retaining wall geometry and soil parameters.

    ``stem_height`` is the stem height above the footing, ``stem_thickness``
    its (rectangular) thickness; ``toe_length`` and ``heel_length`` are the
    footing projections in front of and behind the stem; ``footing_thickness``
    the base slab depth.  ``backfill_gamma``/``backfill_phi`` describe the
    retained soil; ``surcharge`` a uniform vertical surcharge (psf) over the
    heel; ``backfill_slope`` the surface slope behind the wall (deg).
    ``base_friction_deg`` the soil-footing interface friction angle and
    ``base_cohesion`` its adhesion (psf).  When ``include_passive`` the
    passive wedge over an ``embedment`` (ft) of soil on the toe is credited
    to sliding.
    """

    stem_height: float
    stem_thickness: float
    toe_length: float
    heel_length: float
    footing_thickness: float
    backfill_gamma: float
    backfill_phi: float
    concrete_gamma: float = 150.0
    surcharge: float = 0.0
    backfill_slope: float = 0.0
    base_friction_deg: float | None = None
    base_cohesion: float = 0.0
    embedment: float = 0.0
    include_passive: bool = False
    include_toe_soil: bool = True
    method: str = "rankine"
    wall_friction_deg: float = 0.0

    @property
    def base_width(self) -> float:
        return self.toe_length + self.stem_thickness + self.heel_length

    @property
    def total_height(self) -> float:
        """Height of the active-pressure plane through the heel, including
        the soil wedge above a sloping backfill."""
        h = self.stem_height + self.footing_thickness
        return h + self.heel_length * math.tan(math.radians(self.backfill_slope))

    @property
    def ka(self) -> float:
        if self.method == "coulomb":
            return coulomb_ka(
                self.backfill_phi, self.wall_friction_deg, self.backfill_slope
            )
        if self.method == "rankine":
            return rankine_ka(self.backfill_phi, self.backfill_slope)
        raise ValueError(f"unknown method {self.method!r}")

    @property
    def kp(self) -> float:
        return rankine_kp(self.backfill_phi)

    # ------------------------------------------------------------- weights

    def _vertical_loads(self) -> list[tuple[float, float, str]]:
        """List of (force lb/ft, lever arm from toe ft, label) for every
        vertical (resisting) load."""
        gc, gb = self.concrete_gamma, self.backfill_gamma
        ts, hs = self.stem_thickness, self.stem_height
        toe, heel, b = self.toe_length, self.heel_length, self.base_width
        tf = self.footing_thickness
        x_stem_back = toe + ts
        loads = [
            (b * tf * gc, b / 2.0, "footing"),
            (ts * hs * gc, toe + ts / 2.0, "stem"),
            (heel * hs * gb, x_stem_back + heel / 2.0, "heel_soil"),
        ]
        slope = math.tan(math.radians(self.backfill_slope))
        if slope > 0.0 and heel > 0.0:
            tri = 0.5 * heel * (heel * slope) * gb
            loads.append((tri, x_stem_back + 2.0 / 3.0 * heel, "wedge_soil"))
        if self.surcharge > 0.0 and heel > 0.0:
            loads.append((self.surcharge * heel, x_stem_back + heel / 2.0,
                          "surcharge"))
        if self.include_toe_soil and self.embedment > 0.0 and toe > 0.0:
            loads.append((toe * self.embedment * gb, toe / 2.0, "toe_soil"))
        return loads

    # ----------------------------------------------------------- stability

    def stability(
        self,
        fs_sliding: float = 1.5,
        fs_overturning: float = 2.0,
    ) -> StabilityResult:
        """Overturning, sliding, and bearing stability per foot of wall."""
        b = self.base_width
        h_eff = self.total_height
        ka, gamma = self.ka, self.backfill_gamma
        cos_b = math.cos(math.radians(self.backfill_slope))

        # Active thrust: soil triangle + surcharge rectangle.
        pa_soil = 0.5 * ka * gamma * h_eff ** 2
        pa_surch = ka * self.surcharge * h_eff
        ph = (pa_soil + pa_surch) * cos_b
        pv = (pa_soil + pa_surch) * math.sin(math.radians(self.backfill_slope))

        # Overturning about the toe (horizontal components only).
        mo = (pa_soil * cos_b) * (h_eff / 3.0) + (pa_surch * cos_b) * (h_eff / 2.0)

        loads = self._vertical_loads()
        sum_v = sum(w for w, _, _ in loads) + pv
        mr = sum(w * x for w, x, _ in loads) + pv * b

        x_bar = (mr - mo) / sum_v
        e = b / 2.0 - x_bar

        passive = 0.0
        if self.include_passive and self.embedment > 0.0:
            passive = 0.5 * self.kp * gamma * self.embedment ** 2
        delta = (
            self.base_friction_deg
            if self.base_friction_deg is not None
            else self.backfill_phi
        )
        sliding_resistance = (
            sum_v * math.tan(math.radians(delta))
            + self.base_cohesion * b
            + passive
        )

        contact = contact_pressure(p=sum_v, m=sum_v * abs(e), width=b, length=1.0)

        return StabilityResult(
            sum_v=sum_v, sum_h=ph, resisting_moment=mr, overturning_moment=mo,
            eccentricity=e, base_width=b, contact=contact, passive=passive,
            fs_required_sliding=fs_sliding, fs_required_overturning=fs_overturning,
            details={
                "Pa_soil": pa_soil, "Pa_surcharge": pa_surch, "Pv": pv,
                "sliding_resistance": sliding_resistance, "x_bar": x_bar,
                "loads": loads, "delta": delta,
            },
        )

    # ------------------------------------------------------ structural design

    def _factored_lateral(self, height: float, eh: float = 1.5, es: float = 1.5):
        """Factored horizontal thrust (kip) and its arm above the section
        (ft) for a cantilever of ``height`` ft -- soil (load factor ``eh``)
        plus surcharge (``es``)."""
        ka, gamma = self.ka, self.backfill_gamma
        cos_b = math.cos(math.radians(self.backfill_slope))
        p_soil = 0.5 * ka * gamma * height ** 2 * cos_b * eh
        p_surch = ka * self.surcharge * height * cos_b * es
        v = (p_soil + p_surch) / 1000.0  # kip
        m = (p_soil * height / 3.0 + p_surch * height / 2.0) / 1000.0  # kip-ft
        return v, m

    def stem_design(
        self,
        a_s: float,
        f_c: float = 4.0,
        f_y: float = 60.0,
        cover_in: float = 2.0,
        bar_dia_in: float = 1.0,
        eh: float = 1.5,
    ) -> dict[str, CheckResult]:
        """Flexure and shear at the base of the stem, reusing the LRFD RC
        functions.  ``a_s`` is the vertical reinforcement in a 12-in strip
        (in^2/ft); the stem height drives the cantilever moment."""
        t_in = self.stem_thickness * 12.0
        d_s = t_in - cover_in - bar_dia_in / 2.0
        v, m_ft = self._factored_lateral(self.stem_height, eh=eh)
        m_in = m_ft * 12.0
        dv = max(0.9 * d_s, 0.72 * t_in)
        return {
            "flexure": rc_rectangular_flexural_resistance(
                a_s=a_s, f_y=f_y, f_c=f_c, b=12.0, d_s=d_s, m_u=m_in
            ),
            "shear": rc_shear_resistance(b_v=12.0, d_v=dv, f_c=f_c, v_u=v),
        }

    def heel_design(
        self,
        q_avg: float,
        a_s: float,
        f_c: float = 4.0,
        f_y: float = 60.0,
        cover_in: float = 3.0,
        bar_dia_in: float = 1.0,
        load_factor: float = 1.35,
    ) -> dict[str, CheckResult]:
        """Heel cantilever: net downward pressure (soil + surcharge +
        self-weight, less the upward bearing ``q_avg`` psf averaged under the
        heel) produces tension in the top.  ``a_s`` is top steel per foot;
        ``q_avg`` is the contact pressure under the heel from
        :meth:`stability`."""
        gb, gc = self.backfill_gamma, self.concrete_gamma
        down = (
            gb * self.stem_height + self.surcharge + gc * self.footing_thickness
        )
        net = (down - q_avg) * load_factor  # psf, downward positive
        arm = self.heel_length
        v = abs(net) * arm / 1000.0
        m_in = abs(net) * arm ** 2 / 2.0 * 12.0 / 1000.0
        t_in = self.footing_thickness * 12.0
        d_s = t_in - cover_in - bar_dia_in / 2.0
        dv = max(0.9 * d_s, 0.72 * t_in)
        return {
            "flexure": rc_rectangular_flexural_resistance(
                a_s=a_s, f_y=f_y, f_c=f_c, b=12.0, d_s=d_s, m_u=m_in
            ),
            "shear": rc_shear_resistance(b_v=12.0, d_v=dv, f_c=f_c, v_u=v),
        }

    def toe_design(
        self,
        q_avg: float,
        a_s: float,
        f_c: float = 4.0,
        f_y: float = 60.0,
        cover_in: float = 3.0,
        bar_dia_in: float = 1.0,
        load_factor: float = 1.35,
    ) -> dict[str, CheckResult]:
        """Toe cantilever: the upward bearing pressure ``q_avg`` (psf, net of
        the toe self-weight) produces tension in the bottom.  ``a_s`` is
        bottom steel per foot."""
        net = (q_avg - self.concrete_gamma * self.footing_thickness) * load_factor
        arm = self.toe_length
        v = abs(net) * arm / 1000.0
        m_in = abs(net) * arm ** 2 / 2.0 * 12.0 / 1000.0
        t_in = self.footing_thickness * 12.0
        d_s = t_in - cover_in - bar_dia_in / 2.0
        dv = max(0.9 * d_s, 0.72 * t_in)
        return {
            "flexure": rc_rectangular_flexural_resistance(
                a_s=a_s, f_y=f_y, f_c=f_c, b=12.0, d_s=d_s, m_u=m_in
            ),
            "shear": rc_shear_resistance(b_v=12.0, d_v=dv, f_c=f_c, v_u=v),
        }

    # ------------------------------------------------------------- wingwall

    @classmethod
    def wingwall(
        cls, high_height: float, low_height: float, **kwargs
    ) -> "RetainingWall":
        """Build a wingwall as a retaining wall taken at the average of its
        high and low exposed stem heights (a common simplification for the
        tapering wing of an abutment).  Extra keyword arguments are passed
        through to :class:`RetainingWall`."""
        if high_height <= 0.0 or low_height < 0.0:
            raise ValueError("heights must be positive")
        return cls(stem_height=(high_height + low_height) / 2.0, **kwargs)
