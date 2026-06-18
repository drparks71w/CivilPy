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

"""Axial capacity of deep foundations from a boring log.

Two methods share one boring-driven integrator:

* **Drilled shafts** -- FHWA / AASHTO LRFD Article 10.8 (O'Neill & Reese,
  FHWA GEC-10): the alpha method for side and tip resistance in cohesive
  soil and the beta method for cohesionless soil.
* **Driven piles** -- the Meyerhof (1976) SPT method for cohesionless soil
  (unit skin friction and end bearing from N60) plus the alpha method in
  clay, consistent with AASHTO 10.7.3.8.6.

The unit-resistance functions are the citable core; the
:func:`drilled_shaft_capacity` and :func:`driven_pile_capacity` drivers
discretise the element, pull soil properties at each depth from a
:class:`~civilpy.geotech.boring.Borehole` (blow counts via
:mod:`civilpy.geotech.spt`), integrate side resistance, and add tip
resistance.

Soil parameters derived from SPT are estimates; a foundation for final
design should be checked against a project-specific subsurface
characterisation.  The Meyerhof method in particular is known to be
unconservative for end bearing in dense sand.

Units: lengths in feet, unit weights in pcf, stresses and unit
resistances in ksf, capacities in kips, angles in degrees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from civilpy.geotech.boring import Borehole
from civilpy.geotech.spt import (
    undrained_shear_strength_from_n,
    unit_weight_from_n,
)

#: Atmospheric pressure, ksf (used to normalise Su for the alpha factor).
PA_KSF = 2.116
#: Unit weight of water, pcf.
GAMMA_WATER_PCF = 62.4

# ---------------------------------------------------------------- cohesive


def alpha_factor(su_ksf: float) -> float:
    """Adhesion factor alpha for drilled-shaft side resistance in clay
    (AASHTO LRFD 10.8.3.5.1b, O'Neill & Reese):

    alpha = 0.55                          for Su/pa <= 1.5
    alpha = 0.55 - 0.1 (Su/pa - 1.5)      for 1.5 < Su/pa <= 2.5
    """
    ratio = su_ksf / PA_KSF
    if ratio <= 1.5:
        return 0.55
    return max(0.0, 0.55 - 0.1 * (ratio - 1.5))


def unit_side_resistance_clay(su_ksf: float) -> float:
    """Nominal unit side resistance in cohesive soil (ksf):
    q_s = alpha * Su (AASHTO 10.8.3.5.1b)."""
    return alpha_factor(su_ksf) * su_ksf


def unit_tip_resistance_clay(
    su_ksf: float, depth_ft: float, diameter_ft: float, limit_ksf: float = 80.0
) -> float:
    """Nominal unit tip resistance in cohesive soil (ksf), AASHTO
    10.8.3.5.1c: q_p = Nc * Su, Nc = 6[1 + 0.2 (Z/D)] <= 9, capped at
    ``limit_ksf``."""
    nc = min(9.0, 6.0 * (1.0 + 0.2 * (depth_ft / diameter_ft)))
    return min(limit_ksf, nc * su_ksf)


# ------------------------------------------------------------- cohesionless


def beta_factor(depth_ft: float, n60: float) -> float:
    """Side-resistance factor beta for sand (AASHTO 10.8.3.5.2b,
    O'Neill & Reese): beta = 1.5 - 0.135 sqrt(z), 0.25 <= beta <= 1.2, with
    a linear reduction by N60/15 for loose sand (N60 < 15).  ``z`` in feet."""
    beta = 1.5 - 0.135 * math.sqrt(max(0.0, depth_ft))
    beta = min(1.2, max(0.25, beta))
    if n60 < 15.0:
        beta *= n60 / 15.0
    return beta


def unit_side_resistance_sand(
    sigma_v_eff_ksf: float, depth_ft: float, n60: float, limit_ksf: float = 4.0
) -> float:
    """Nominal unit side resistance in cohesionless soil (ksf):
    q_s = beta * sigma'_v, capped at ``limit_ksf`` (AASHTO 10.8.3.5.2b)."""
    return min(limit_ksf, beta_factor(depth_ft, n60) * sigma_v_eff_ksf)


def unit_tip_resistance_sand(n60: float, limit_ksf: float = 60.0) -> float:
    """Nominal unit tip resistance in cohesionless soil (ksf), AASHTO
    10.8.3.5.2c (O'Neill & Reese): q_p = 1.2 N60 for N60 <= 50, capped at
    ``limit_ksf`` (60 ksf)."""
    n = min(n60, 50.0)
    return min(limit_ksf, 1.2 * n)


# ---------------------------------------------------------------- driver


@dataclass
class ShaftCapacity:
    """Result of :func:`drilled_shaft_capacity`: nominal resistances (kips)
    and the shaft geometry that produced them."""

    diameter_ft: float
    tip_depth_ft: float
    side_nominal_kips: float
    tip_nominal_kips: float

    @property
    def total_nominal_kips(self) -> float:
        return self.side_nominal_kips + self.tip_nominal_kips

    def factored_kips(self, phi_side: float = 0.45, phi_tip: float = 0.40) -> float:
        """Factored axial resistance (kips).  Defaults are conservative
        AASHTO 10.5.5.2.4 drilled-shaft resistance factors (clay side 0.45,
        clay tip 0.40); pass the values matching the controlling soil."""
        return phi_side * self.side_nominal_kips + phi_tip * self.tip_nominal_kips


@dataclass
class _SoilPoint:
    gamma_pcf: float
    cohesive: bool
    n60: float
    su_ksf: float


def _props_at(
    borehole: Borehole, depth_ft: float, energy_ratio: float, su_factor_psf: float
) -> _SoilPoint:
    """Soil properties for the shaft element centred at ``depth_ft``,
    derived from the nearest SPT and gradation in the boring."""
    spt = min(borehole.spt, key=lambda s: abs(s.depth_ft - depth_ft))
    n = spt.n_value if spt.n_value is not None else 0
    n60 = spt.n60(energy_ratio, rod_length_ft=depth_ft) or float(n)
    grading = borehole.grading_at(depth_ft)
    fines = grading.fines_percent if grading else None
    cohesive = fines is not None and fines >= 50.0
    gamma = unit_weight_from_n(n, coarse=not cohesive)
    su_ksf = undrained_shear_strength_from_n(n60, su_factor_psf) / 1000.0
    return _SoilPoint(gamma_pcf=gamma, cohesive=cohesive, n60=n60, su_ksf=su_ksf)


def drilled_shaft_capacity(
    borehole: Borehole,
    diameter_ft: float,
    tip_depth_ft: float,
    water_table_ft: float | None = None,
    energy_ratio: float = 0.60,
    step_ft: float = 0.5,
    su_factor_psf: float = 92.0,
    exclude_top_ft: float = 5.0,
    exclude_bottom_diameters: float = 1.0,
) -> ShaftCapacity:
    """Nominal axial (compression) capacity of a straight drilled shaft.

    Discretises the shaft into ``step_ft`` elements, derives soil
    properties at each from ``borehole`` (cohesive vs cohesionless by
    gradation fines, blow counts energy-corrected to N60), integrates the
    effective vertical stress, and sums side resistance -- excluding the
    top ``exclude_top_ft`` and the bottom ``exclude_bottom_diameters``
    diameters per AASHTO 10.8.3.5 -- then adds tip resistance at the base.

    ``water_table_ft`` overrides the boring's recorded water strike; with
    neither, fully drained (no pore pressure) is assumed.
    """
    if not borehole.spt:
        raise ValueError(f"boring {borehole.boring_id} has no SPT data")
    if tip_depth_ft <= 0 or diameter_ft <= 0:
        raise ValueError("diameter and tip depth must be positive")

    wt = water_table_ft if water_table_ft is not None else borehole.water_strike_depth_ft
    perimeter = math.pi * diameter_ft
    bottom_exclusion = tip_depth_ft - exclude_bottom_diameters * diameter_ft

    sigma_total_psf = 0.0
    z = 0.0
    side_kips = 0.0
    while z < tip_depth_ft - 1e-9:
        dz = min(step_ft, tip_depth_ft - z)
        z_mid = z + dz / 2.0
        p = _props_at(borehole, z_mid, energy_ratio, su_factor_psf)
        sigma_mid_total = sigma_total_psf + p.gamma_pcf * (dz / 2.0)
        u = GAMMA_WATER_PCF * max(0.0, z_mid - wt) if wt is not None else 0.0
        sigma_mid_eff_ksf = max(0.0, sigma_mid_total - u) / 1000.0

        excluded = z_mid < exclude_top_ft or z_mid > bottom_exclusion
        if not excluded:
            if p.cohesive:
                q_s = unit_side_resistance_clay(p.su_ksf)
            else:
                q_s = unit_side_resistance_sand(sigma_mid_eff_ksf, z_mid, p.n60)
            side_kips += q_s * perimeter * dz

        sigma_total_psf += p.gamma_pcf * dz
        z += dz

    tip = _props_at(borehole, tip_depth_ft - step_ft / 2.0, energy_ratio, su_factor_psf)
    area = math.pi * diameter_ft ** 2 / 4.0
    if tip.cohesive:
        q_p = unit_tip_resistance_clay(tip.su_ksf, tip_depth_ft, diameter_ft)
    else:
        q_p = unit_tip_resistance_sand(tip.n60)
    tip_kips = q_p * area

    return ShaftCapacity(
        diameter_ft=diameter_ft,
        tip_depth_ft=tip_depth_ft,
        side_nominal_kips=side_kips,
        tip_nominal_kips=tip_kips,
    )


# ----------------------------------------------------- driven piles (Meyerhof)


def meyerhof_unit_skin_friction_sand(
    n60: float, displacement: bool = True, pa_ksf: float = PA_KSF
) -> float:
    """Nominal unit skin friction (ksf) of a driven pile in cohesionless
    soil (Meyerhof 1976): fs = m * Pa * N60, with m = 0.02 for large-
    displacement piles (closed-end pipe, precast) and 0.01 for small-
    displacement piles (H-piles, open-end pipe)."""
    m = 0.02 if displacement else 0.01
    return m * pa_ksf * n60


def meyerhof_unit_end_bearing_sand(
    n60: float, embedment_ratio: float, pa_ksf: float = PA_KSF
) -> float:
    """Nominal unit end bearing (ksf) of a driven pile in cohesionless soil
    (Meyerhof 1976): qp = 0.4 Pa N60 (Lb/D) <= 4 Pa N60, where
    ``embedment_ratio`` Lb/D is the embedment in the bearing stratum over
    the pile width."""
    qp = 0.4 * pa_ksf * n60 * embedment_ratio
    return min(qp, 4.0 * pa_ksf * n60)


def pile_unit_skin_friction_clay(su_ksf: float, alpha: float = 0.55) -> float:
    """Nominal unit skin friction (ksf) of a driven pile in cohesive soil
    by the alpha (total-stress) method: fs = alpha * Su.  ``alpha`` follows
    Tomlinson/API and ranges from ~0.5 (stiff clay) to 1.0 (soft clay)."""
    return alpha * su_ksf


@dataclass
class PileCapacity:
    """Result of :func:`driven_pile_capacity`: nominal resistances (kips)
    and the pile geometry that produced them."""

    width_ft: float
    tip_depth_ft: float
    side_nominal_kips: float
    tip_nominal_kips: float

    @property
    def total_nominal_kips(self) -> float:
        return self.side_nominal_kips + self.tip_nominal_kips

    def factored_kips(self, phi_side: float = 0.45, phi_tip: float = 0.45) -> float:
        """Factored axial resistance (kips).  Defaults are representative
        AASHTO 10.5.5.2.3 driven-pile resistance factors for the SPT-based
        methods; pass the values for the controlling soil and method."""
        return phi_side * self.side_nominal_kips + phi_tip * self.tip_nominal_kips


def driven_pile_capacity(
    borehole: Borehole,
    width_ft: float,
    tip_depth_ft: float,
    perimeter_ft: float | None = None,
    area_ft2: float | None = None,
    displacement: bool = True,
    alpha_clay: float = 0.55,
    water_table_ft: float | None = None,
    energy_ratio: float = 0.60,
    step_ft: float = 0.5,
    su_factor_psf: float = 92.0,
) -> PileCapacity:
    """Nominal axial (compression) capacity of a driven pile.

    Discretises the pile, derives soil properties at each element from
    ``borehole`` (cohesive vs cohesionless by gradation fines), and sums
    skin friction over the full embedded length -- Meyerhof fs = m Pa N60
    in sand, alpha * Su in clay -- then adds end bearing at the tip
    (Meyerhof in sand, 9 Su in clay).

    ``width_ft`` is the pile diameter/width.  By default a solid round/
    square section is assumed (``perimeter`` pi*B, ``area`` pi*B^2/4);
    pass ``perimeter_ft`` and ``area_ft2`` for H-piles or open sections.
    ``displacement`` selects the Meyerhof skin-friction coefficient.
    """
    if not borehole.spt:
        raise ValueError(f"boring {borehole.boring_id} has no SPT data")
    if tip_depth_ft <= 0 or width_ft <= 0:
        raise ValueError("width and tip depth must be positive")

    wt = water_table_ft if water_table_ft is not None else borehole.water_strike_depth_ft
    perimeter = perimeter_ft if perimeter_ft is not None else math.pi * width_ft
    area = area_ft2 if area_ft2 is not None else math.pi * width_ft ** 2 / 4.0

    z = 0.0
    side_kips = 0.0
    while z < tip_depth_ft - 1e-9:
        dz = min(step_ft, tip_depth_ft - z)
        z_mid = z + dz / 2.0
        p = _props_at(borehole, z_mid, energy_ratio, su_factor_psf)
        if p.cohesive:
            f_s = pile_unit_skin_friction_clay(p.su_ksf, alpha_clay)
        else:
            f_s = meyerhof_unit_skin_friction_sand(p.n60, displacement)
        side_kips += f_s * perimeter * dz
        z += dz

    tip = _props_at(borehole, tip_depth_ft - step_ft / 2.0, energy_ratio, su_factor_psf)
    if tip.cohesive:
        q_p = 9.0 * tip.su_ksf
    else:
        q_p = meyerhof_unit_end_bearing_sand(tip.n60, tip_depth_ft / width_ft)
    tip_kips = q_p * area

    return PileCapacity(
        width_ft=width_ft,
        tip_depth_ft=tip_depth_ft,
        side_nominal_kips=side_kips,
        tip_nominal_kips=tip_kips,
    )
