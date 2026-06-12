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

"""AASHTO LRFD 5.4.2.3 — concrete creep and shrinkage material models.

These feed the refined prestress-loss estimates (5.9.3.4) and
time-dependent deflections.  Units: ksi, inch, days; humidity in percent.

The time-development factor ktd was revised in the 2015 interim — pass
``design_year`` for designs between 2007 and 2014 to get the earlier form.
(The pre-2007 creep/shrinkage model is a different formulation entirely
and is not implemented.)
"""

from civilpy.structural.aashto.lrfd.core import article


def factor_vs_ratio(v_s: float) -> float:
    """ks, volume-to-surface ratio factor (5.4.2.3.2-2): 1.45 - 0.13*(V/S),
    not less than 1.0.  ``v_s`` in inches."""
    return max(1.45 - 0.13 * v_s, 1.0)


def factor_humidity_creep(humidity_pct: float) -> float:
    """khc, humidity factor for creep (5.4.2.3.2-3): 1.56 - 0.008*H."""
    return 1.56 - 0.008 * humidity_pct


def factor_humidity_shrinkage(humidity_pct: float) -> float:
    """khs, humidity factor for shrinkage (5.4.2.3.3-2): 2.00 - 0.014*H."""
    return 2.00 - 0.014 * humidity_pct


def factor_concrete_strength(f_ci: float) -> float:
    """kf, concrete strength factor (5.4.2.3.2-4): 5/(1 + f'ci)."""
    return 5.0 / (1.0 + f_ci)


def factor_time_development(
    t: float, f_ci: float, design_year: int | None = None
) -> float:
    """ktd, time-development factor (5.4.2.3.2-5).

    Current (2015 interim onward): t / (12*(100 - 4*f'ci)/(f'ci + 20) + t).
    2007-2014 designs used t / (61 - 4*f'ci + t).  ``t`` is the maturity of
    the concrete in days from loading (creep) or end of curing (shrinkage).
    """
    if design_year is not None and design_year < 2015:
        return t / (61.0 - 4.0 * f_ci + t)
    return t / (12.0 * (100.0 - 4.0 * f_ci) / (f_ci + 20.0) + t)


@article("5.4.2.3.2", "Creep Coefficient")
def creep_coefficient(
    t: float,
    t_i: float,
    f_ci: float,
    humidity_pct: float = 70.0,
    v_s: float = 3.5,
    design_year: int | None = None,
) -> float:
    """Creep coefficient psi(t, ti) (5.4.2.3.2-1):
    1.9 * ks * khc * kf * ktd * ti^-0.118.

    ``t`` is concrete age at the time of interest (days), ``t_i`` age at
    loading.  Returns a plain float since this is a material model, not a
    pass/fail check.
    """
    ktd = factor_time_development(t - t_i, f_ci, design_year)
    return (
        1.9
        * factor_vs_ratio(v_s)
        * factor_humidity_creep(humidity_pct)
        * factor_concrete_strength(f_ci)
        * ktd
        * t_i**-0.118
    )


@article("5.4.2.3.3", "Shrinkage Strain")
def shrinkage_strain(
    t: float,
    f_ci: float,
    humidity_pct: float = 70.0,
    v_s: float = 3.5,
    design_year: int | None = None,
) -> float:
    """Shrinkage strain eps_sh (5.4.2.3.3-1):
    ks * khs * kf * ktd * 0.48e-3 (in/in, returned positive for
    shortening).  ``t`` is drying time in days from the end of curing."""
    ktd = factor_time_development(t, f_ci, design_year)
    return (
        factor_vs_ratio(v_s)
        * factor_humidity_shrinkage(humidity_pct)
        * factor_concrete_strength(f_ci)
        * ktd
        * 0.48e-3
    )
