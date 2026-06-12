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

"""AASHTO LRFD 4.6.2.2 — approximate live-load distribution factors.

Implemented for the most common cross-section: concrete deck on steel or
precast concrete I-girders (Table 4.6.2.2.1-1 types (a), (e), (k)).  The
formulas return lanes/girder with multiple presence already embedded.

Units here follow the tables: S and de in **ft**, L in ft, ts in inches,
Kg in in^4.  Results carry the table's range-of-applicability flags in
``details`` — outside those ranges the spec requires refined analysis or
the lever rule, it does not extrapolate.
"""

import math
from dataclasses import dataclass, field

from civilpy.structural.aashto.lrfd.core import article


def longitudinal_stiffness_kg(
    n_modular: float, i_girder: float, a_girder: float, e_g: float
) -> float:
    """Kg = n*(I + A*eg^2) (4.6.2.2.1-1), in^4.  ``e_g`` is the distance
    between girder and deck centroids (in); ``n_modular`` the girder/deck
    modular ratio."""
    return n_modular * (i_girder + a_girder * e_g**2)


@dataclass
class DistributionFactor:
    """A distribution factor (lanes/girder) with its applicability flags."""

    one_lane: float
    multi_lane: float
    applicability: dict = field(default_factory=dict)

    @property
    def governing(self) -> float:
        return max(self.one_lane, self.multi_lane)

    @property
    def applicable(self) -> bool:
        return all(self.applicability.values())


@article("4.6.2.2.2b", "Distribution of Live Load Moment, Interior Girders")
def moment_df_interior(
    s_ft: float,
    l_ft: float,
    t_s: float,
    k_g: float,
    n_beams: int = 4,
) -> DistributionFactor:
    """Moment DF for interior I-girders (Table 4.6.2.2.2b-1, type a/e/k):

    one lane:  0.06 + (S/14)^0.4 * (S/L)^0.3 * (Kg/(12*L*ts^3))^0.1
    multi:     0.075 + (S/9.5)^0.6 * (S/L)^0.2 * (Kg/(12*L*ts^3))^0.1
    """
    stiffness = k_g / (12.0 * l_ft * t_s**3)
    one = 0.06 + (s_ft / 14.0) ** 0.4 * (s_ft / l_ft) ** 0.3 * stiffness**0.1
    multi = 0.075 + (s_ft / 9.5) ** 0.6 * (s_ft / l_ft) ** 0.2 * stiffness**0.1
    return DistributionFactor(
        one_lane=one,
        multi_lane=multi,
        applicability={
            "spacing": 3.5 <= s_ft <= 16.0,
            "slab_thickness": 4.5 <= t_s <= 12.0,
            "span": 20.0 <= l_ft <= 240.0,
            "n_beams": n_beams >= 4,
            "Kg": 10000.0 <= k_g <= 7.0e6,
        },
    )


@article("4.6.2.2.3a", "Distribution of Live Load Shear, Interior Girders")
def shear_df_interior(
    s_ft: float,
    l_ft: float = 80.0,
    t_s: float = 8.0,
    n_beams: int = 4,
) -> DistributionFactor:
    """Shear DF for interior I-girders (Table 4.6.2.2.3a-1, type a/e/k):
    one lane 0.36 + S/25; multi 0.2 + S/12 - (S/35)^2."""
    one = 0.36 + s_ft / 25.0
    multi = 0.2 + s_ft / 12.0 - (s_ft / 35.0) ** 2
    return DistributionFactor(
        one_lane=one,
        multi_lane=multi,
        applicability={
            "spacing": 3.5 <= s_ft <= 16.0,
            "slab_thickness": 4.5 <= t_s <= 12.0,
            "span": 20.0 <= l_ft <= 240.0,
            "n_beams": n_beams >= 4,
        },
    )


@article("4.6.2.2.2d", "Distribution of Live Load Moment, Exterior Girders")
def moment_df_exterior(
    interior_df: DistributionFactor,
    d_e_ft: float,
    one_lane_lever_rule: float | None = None,
) -> DistributionFactor:
    """Moment DF for exterior I-girders (Table 4.6.2.2.2d-1): multi-lane
    g = e * g_interior with e = 0.77 + de/9.1; the one-lane value comes
    from the lever rule (pass it in — it depends on the actual overhang
    and wheel placement).  ``d_e_ft`` is the distance from exterior web to
    the inside face of the barrier (ft, -1.0 <= de <= 5.5)."""
    e = 0.77 + d_e_ft / 9.1
    return DistributionFactor(
        one_lane=(one_lane_lever_rule if one_lane_lever_rule is not None
                  else interior_df.one_lane),
        multi_lane=e * interior_df.multi_lane,
        applicability={**interior_df.applicability,
                       "de": -1.0 <= d_e_ft <= 5.5},
    )


@article("4.6.2.2.3b", "Distribution of Live Load Shear, Exterior Girders")
def shear_df_exterior(
    interior_df: DistributionFactor,
    d_e_ft: float,
    one_lane_lever_rule: float | None = None,
) -> DistributionFactor:
    """Shear DF for exterior I-girders (Table 4.6.2.2.3b-1): multi-lane
    g = e * g_interior with e = 0.6 + de/10."""
    e = 0.6 + d_e_ft / 10.0
    return DistributionFactor(
        one_lane=(one_lane_lever_rule if one_lane_lever_rule is not None
                  else interior_df.one_lane),
        multi_lane=e * interior_df.multi_lane,
        applicability={**interior_df.applicability,
                       "de": -1.0 <= d_e_ft <= 5.5},
    )


@article("4.6.2.2.2e", "Skew Correction — Moment")
def skew_correction_moment(
    skew_deg: float,
    s_ft: float,
    l_ft: float,
    t_s: float,
    k_g: float,
) -> float:
    """Reduction of moment DF on skewed supports (Table 4.6.2.2.2e-1):
    1 - c1*(tan(theta))^1.5, with c1 = 0.25*(Kg/(12*L*ts^3))^0.25*(S/L)^0.5.
    No reduction below 30 degrees; theta capped at 60."""
    if skew_deg < 30.0:
        return 1.0
    theta = min(skew_deg, 60.0)
    c1 = 0.25 * (k_g / (12.0 * l_ft * t_s**3)) ** 0.25 * (s_ft / l_ft) ** 0.5
    return 1.0 - c1 * math.tan(math.radians(theta)) ** 1.5


@article("4.6.2.2.3c", "Skew Correction — Shear")
def skew_correction_shear(
    skew_deg: float,
    l_ft: float,
    t_s: float,
    k_g: float,
) -> float:
    """Increase of shear DF at the obtuse corner of skewed spans
    (Table 4.6.2.2.3c-1): 1 + 0.20*(12*L*ts^3/Kg)^0.3 * tan(theta)."""
    if skew_deg <= 0.0:
        return 1.0
    return 1.0 + 0.20 * (12.0 * l_ft * t_s**3 / k_g) ** 0.3 * math.tan(
        math.radians(skew_deg)
    )


@article("3.6.2", "Dynamic Load Allowance")
def dynamic_load_allowance(component: str = "general",
                           fatigue: bool = False) -> float:
    """IM (Table 3.6.2.1-1) as a multiplier on the truck portion of live
    load: 1.33 generally, 1.15 for fatigue, 1.75 for deck joints."""
    if component == "deck_joint":
        return 1.75
    return 1.15 if fatigue else 1.33
