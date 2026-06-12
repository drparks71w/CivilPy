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

"""AASHTO LRFD 6.13.6.1 — bolted field splices for flexural members
(8th Edition simplified method).

These functions produce the splice *design forces*; the plates and bolts
are then checked with the existing primitives (
:func:`~civilpy.structural.aashto.lrfd.steel.tension_member_resistance`,
``bolt_shear_resistance``, ``bolt_slip_resistance``,
``block_shear_resistance``).  Units: kip, inch, ksi.
"""

import math
from dataclasses import dataclass

from civilpy.structural.aashto.lrfd.core import CheckResult, article


@article("6.13.6.1.3b", "Flange Splice Design Force")
def flange_splice_design_force(
    a_n: float,
    a_g: float,
    f_y: float,
    f_u: float,
) -> CheckResult:
    """Design force for a flange splice (6.13.6.1.3b-1): Pfy = Fyf*Ae with
    the effective flange area Ae = (phi_u*Fu)/(phi_y*Fy)*An <= Ag
    (6.13.6.1.3b-2); phi_u = 0.80, phi_y = 0.95.

    The splice plates, their bolts, and the flange itself are then checked
    against Pfy.  ``capacity`` holds Pfy (kip)."""
    a_e = min(0.80 * f_u / (0.95 * f_y) * a_n, a_g)
    p_fy = f_y * a_e
    return CheckResult(
        article="6.13.6.1.3b",
        name="Flange Splice Design Force",
        capacity=p_fy,
        details={"Ae": a_e, "An": a_n, "Ag": a_g},
    )


@dataclass
class WebSpliceForces:
    """Design forces for a web splice (6.13.6.1.3c): the vertical design
    shear Vuw, the horizontal force Hw from the moment not carried by the
    flanges, and the resultant per-bolt force to compare against the bolt
    shear/slip resistance."""

    v_uw: float
    h_w: float
    per_bolt: float
    n_bolts: int


@article("6.13.6.1.3c", "Web Splice Design Forces")
def web_splice_design_forces(
    v_r_web: float,
    n_bolts: int,
    m_u: float = 0.0,
    m_flange: float = 0.0,
    moment_arm: float | None = None,
) -> WebSpliceForces:
    """Web splice design forces (6.13.6.1.3c, 8th Ed. method).

    ``v_r_web`` is the smaller factored shear resistance phi_v*Vn of the
    webs on either side of the splice (6.10.9) — the web splice is designed
    for the full web capacity, not the applied shear.  When the factored
    moment ``m_u`` (kip-in) exceeds the moment the flange splices can carry
    ``m_flange``, the excess is resisted by a horizontal force couple in
    the web: Hw = (|Mu| - Mrf)/arm.  Each of the ``n_bolts`` (one side of
    the splice) sees the vector sum of Vuw/Nb and Hw/Nb."""
    v_uw = v_r_web
    h_w = 0.0
    excess = abs(m_u) - m_flange
    if excess > 0.0:
        if moment_arm is None:
            raise ValueError(
                "moment_arm is required when |Mu| exceeds the "
                "flange-resisted moment"
            )
        h_w = excess / moment_arm
    per_bolt = math.hypot(v_uw / n_bolts, h_w / n_bolts)
    return WebSpliceForces(v_uw=v_uw, h_w=h_w, per_bolt=per_bolt,
                           n_bolts=n_bolts)
