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

"""AASHTO LRFD Section 13 / Appendix A13 — traffic railing and parapet
checks.

Yield-line analysis of concrete parapets (A13.3.1) and the deck-overhang
force effects it generates (A13.4.2), implemented directly from the
specification; validate against hand calcs or agency design aids.

Units: the yield-line equations are dimensionally consistent — use any one
length unit throughout.  Customary usage (and the test-level table below)
is kip and **ft**: H and Lt in ft, Mb and Mw in kip-ft, Mc in kip-ft/ft,
giving Rw in kip.

The crash test-level table reflects Table A13.2-1 as published in the 1st
through 9th Editions (NCHRP Report 350 / pre-MASH test levels).  The 10th
Edition (2024) revised Section 13 around MASH 2016 criteria — those revised
design forces are not tabulated here yet; pass explicit ``f_t``/``l_t``
values for MASH-era designs.
"""

import math
from dataclasses import dataclass

from civilpy.structural.aashto.lrfd.core import CheckResult, article


@dataclass(frozen=True)
class TestLevelLoad:
    """Design forces for one crash test level (Table A13.2-1, 1st–9th Ed.).

    ``f_t``/``f_l``/``f_v`` are the transverse, longitudinal, and vertical
    (down) forces in kip; ``l_t`` (= ``l_l``) and ``l_v`` their distribution
    lengths in ft; ``h_e_min`` the minimum effective height in inches;
    ``h_min`` the minimum rail height in inches (bottom row of Table A13.2-1).
    """

    f_t: float
    f_l: float
    f_v: float
    l_t: float
    l_v: float
    h_e_min: float
    h_min: float


# Table A13.2-1 (LRFD 1st-9th Ed., NCHRP 350 test levels)
TEST_LEVEL_LOADS: dict[str, TestLevelLoad] = {
    "TL-1": TestLevelLoad(13.5,  4.5,  4.5, 4.0, 18.0, 18.0, 27.0),
    "TL-2": TestLevelLoad(27.0,  9.0,  4.5, 4.0, 18.0, 20.0, 27.0),
    "TL-3": TestLevelLoad(54.0, 18.0,  4.5, 4.0, 18.0, 24.0, 27.0),
    "TL-4": TestLevelLoad(54.0, 18.0, 18.0, 3.5, 18.0, 32.0, 32.0),
    "TL-5": TestLevelLoad(124.0, 41.0, 80.0, 8.0, 40.0, 42.0, 42.0),
    "TL-6": TestLevelLoad(175.0, 58.0, 80.0, 8.0, 40.0, 56.0, 90.0),
}


@article("A13.3.1", "Concrete Railing Yield-Line Resistance")
def parapet_yield_line_capacity(
    m_c: float,
    m_w: float,
    h: float,
    l_t: float,
    m_b: float = 0.0,
    f_t: float | None = None,
    end_region: bool = False,
) -> CheckResult:
    """Total transverse resistance Rw of a concrete parapet by yield-line
    analysis (A13.3.1), compared against the rail design force Ft.

    ``m_c`` is the wall's flexural resistance about its longitudinal axis
    per unit length (kip-ft/ft), ``m_w`` its resistance about the vertical
    axis (kip-ft), ``m_b`` any additional beam/rail resistance at top
    (kip-ft), ``h`` the wall height (ft), ``l_t`` the load distribution
    length (ft).  ``end_region=True`` uses the end/joint mechanism, which
    mobilizes a single yield-line fan and gives a shorter critical length.
    """
    half_lt = l_t / 2.0
    if end_region:
        l_c = half_lt + math.sqrt(half_lt**2 + h * (m_b + m_w) / m_c)
        r_w = (2.0 / (2.0 * l_c - l_t)) * (m_b + m_w + m_c * l_c**2 / h)
    else:
        l_c = half_lt + math.sqrt(half_lt**2 + 8.0 * h * (m_b + m_w) / m_c)
        r_w = (2.0 / (2.0 * l_c - l_t)) * (8.0 * m_b + 8.0 * m_w + m_c * l_c**2 / h)

    return CheckResult(
        article="A13.3.1",
        name="Concrete Railing Yield-Line Resistance",
        capacity=r_w,
        demand=f_t,
        details={"Lc": l_c, "Mc": m_c, "Mw": m_w, "Mb": m_b,
                 "region": "end" if end_region else "interior"},
    )


def parapet_test_level_check(
    test_level: str,
    m_c: float,
    m_w: float,
    h_ft: float,
    m_b: float = 0.0,
    end_region: bool = False,
) -> CheckResult:
    """Convenience wrapper: yield-line capacity checked against a Table
    A13.2-1 test level (1st-9th Ed. forces).  ``h_ft`` is wall height in ft;
    the result's details flag whether the wall also meets the minimum
    effective height for the test level."""
    tl = TEST_LEVEL_LOADS[test_level]
    result = parapet_yield_line_capacity(
        m_c=m_c, m_w=m_w, h=h_ft, l_t=tl.l_t, m_b=m_b,
        f_t=tl.f_t, end_region=end_region,
    )
    result.details["test_level"] = test_level
    h_in = h_ft * 12.0
    result.details["h_e_ok"] = h_in >= tl.h_e_min
    result.details["h_min_ok"] = h_in >= tl.h_min
    result.details["height_ok"] = result.details["h_e_ok"] and result.details["h_min_ok"]
    return result


@article("A13.4.2", "Deck Overhang Collision Force Effects")
def deck_overhang_collision_tension(
    r_w: float,
    l_c: float,
    h: float,
) -> CheckResult:
    """Axial tensile force per unit length transmitted to the deck overhang
    when the parapet reaches its yield-line resistance (A13.4.2 Design Case
    1): T = Rw/(Lc + 2H), spread over the distribution length at the deck
    level.

    ``capacity`` holds T (kip/ft when Rw is kip and Lc/H are ft); the deck
    overhang reinforcement must then resist T concurrent with the overhang
    moment.
    """
    t = r_w / (l_c + 2.0 * h)
    return CheckResult(
        article="A13.4.2",
        name="Deck Overhang Collision Force Effects",
        capacity=t,
        details={"Rw": r_w, "Lc": l_c, "H": h,
                 "distribution_length": l_c + 2.0 * h},
    )
