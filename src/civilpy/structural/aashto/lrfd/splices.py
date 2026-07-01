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


# ---------------------------------------------------------------------------
# Splice-plate proportioning and per-plate design forces
# ---------------------------------------------------------------------------

@dataclass
class SplicePlateForces:
    """How the flange design force ``Pfy`` is apportioned to the inner and
    outer splice plates (C6.13.6.1.3b).  ``double_shear`` is True when the
    inner and outer plate areas are within 10% and the force is shared
    equally (each plate group works in double shear at Pfy/2); otherwise
    each plate carries the fraction of Pfy proportional to its area."""

    outer: float
    inner: float
    double_shear: bool
    ratio_outer: float


@article("6.13.6.1.3b", "Splice Plate Design Force")
def splice_plate_design_force(
    p_fy: float,
    a_g_outer: float,
    a_g_inner: float,
) -> SplicePlateForces:
    """Apportion the flange design force ``Pfy`` between the outer and inner
    splice plates (C6.13.6.1.3b).  If the plate areas differ by no more than
    10%, the force is divided equally (double shear, Pfy/2 each); otherwise
    it is split in proportion to plate area."""
    total = a_g_outer + a_g_inner
    pct_diff = abs(a_g_outer - a_g_inner) / max(a_g_outer, a_g_inner)
    if pct_diff <= 0.10:
        return SplicePlateForces(outer=0.5 * p_fy, inner=0.5 * p_fy,
                                 double_shear=True, ratio_outer=0.5)
    ratio_outer = a_g_outer / total
    return SplicePlateForces(
        outer=ratio_outer * p_fy,
        inner=(1.0 - ratio_outer) * p_fy,
        double_shear=False,
        ratio_outer=ratio_outer,
    )


@article("6.13.6.1.4", "Filler Plate Reduction Factor")
def filler_plate_reduction(
    a_f: float,
    a_p: float,
    total_filler_thickness: float = 1.0,
) -> CheckResult:
    """Bolt shear-resistance reduction for fillers (6.13.6.1.4).  When the
    total thickness of the fillers is 0.25 in or greater, the factored bolt
    shear resistance is multiplied by R = (1 + gamma)/(1 + 2*gamma), with
    gamma = Af/Ap; Af is the sum of the filler areas and Ap is the smaller of
    the connected-plate area or the sum of the splice-plate areas.  Below
    0.25 in of filler, R = 1.0.  ``capacity`` holds R."""
    if total_filler_thickness < 0.25 or a_f <= 0.0:
        r = 1.0
        gamma = 0.0
    else:
        gamma = a_f / a_p
        r = (1.0 + gamma) / (1.0 + 2.0 * gamma)
    return CheckResult(
        article="6.13.6.1.4",
        name="Filler Plate Reduction Factor",
        capacity=r,
        details={"gamma": gamma, "Af": a_f, "Ap": a_p},
    )


@article("6.13.5.2", "Net Section Reduction Limit")
def net_section_reduction_limit(a_n: float, a_g: float) -> CheckResult:
    """Effective net area limit for splice plates in tension (6.13.5.2):
    the net area used for the fracture check is taken as An but not more than
    0.85*Ag.  Reported as a NOTICE (not a strength failure): ``ok`` is True
    when An <= 0.85*Ag; ``details['An_eff']`` is the area to use downstream."""
    limit = 0.85 * a_g
    return CheckResult(
        article="6.13.5.2",
        name="Net Section Reduction Limit",
        capacity=limit,
        demand=a_n,
        details={"An": a_n, "An_eff": min(a_n, limit)},
    )


@article("D6.1", "Composite Slab Crushing Resistance")
def slab_crushing_resistance(
    f_c: float,
    b_eff: float,
    t_s: float,
    demand_force: float | None = None,
) -> CheckResult:
    """Plastic compressive force the composite deck can deliver at the splice
    (Appendix D6.1): Prb = 0.85*f'c*b_eff*t_s.  For a composite section the
    flange tension force plus the web horizontal force Hw must not exceed
    this, otherwise the deck is over-stressed and the splice should be
    designed as non-composite.  Pass ``demand_force`` = flange force + Hw."""
    p_rb = 0.85 * f_c * b_eff * t_s
    return CheckResult(
        article="D6.1",
        name="Composite Slab Crushing Resistance",
        capacity=p_rb,
        demand=demand_force,
        details={"b_eff": b_eff, "t_s": t_s},
    )


@article("6.13.6.1.3c", "Flange Moment Resistance")
def flange_moment_resistance(
    flange_force: float,
    moment_arm: float,
    m_u: float | None = None,
) -> CheckResult:
    """Moment the flange splices alone can resist as a force couple
    (6.13.6.1.3c): Mflange = Pfl * arm.  Compared against the factored
    design moment ``m_u``; any excess |Mu| - Mflange is carried by the web
    as the horizontal force Hw (see :func:`web_splice_design_forces`).
    Forces in kip, arm in inches, moments in kip-in."""
    m_flange = flange_force * moment_arm
    return CheckResult(
        article="6.13.6.1.3c",
        name="Flange Moment Resistance",
        capacity=m_flange,
        demand=None if m_u is None else abs(m_u),
        details={"flange_force": flange_force, "moment_arm": moment_arm},
    )


# ---------------------------------------------------------------------------
# Bolt spacing / edge / end distance limits (6.13.2.6)
# ---------------------------------------------------------------------------

# Table 6.13.2.6.6-1 minimum edge distance (in) for sheared vs rolled/gas-cut
# edges, keyed by bolt diameter (in).
MIN_EDGE_DISTANCE = {
    0.625: (1.125, 0.875), 0.75: (1.25, 1.0), 0.875: (1.5, 1.125),
    1.0: (1.75, 1.25), 1.125: (2.0, 1.5), 1.25: (2.25, 1.625),
    1.375: (2.4375, 1.71875),
}


@dataclass
class SpacingLimits:
    """Result of the 6.13.2.6 layout limit checks.  Each ``*_ok`` flag is
    True when the corresponding provided dimension is within the spec limit;
    the limit values are exposed for reporting."""

    min_spacing: float
    max_spacing_seal: float
    min_edge: float
    max_edge: float
    pitch_ok: bool | None
    gage_ok: bool | None
    edge_ok: bool | None
    end_ok: bool | None


@article("6.13.2.6", "Bolt Spacing and Edge Distance Limits")
def bolt_spacing_limits(
    d_bolt: float,
    plate_t: float,
    pitch: float | None = None,
    gage: float | None = None,
    edge_dist: float | None = None,
    end_dist: float | None = None,
    sheared_edge: bool = False,
) -> SpacingLimits:
    """Geometric layout limits for a bolt group (6.13.2.6):

    * minimum spacing (pitch and gage) = 3.0*d (6.13.2.6.1);
    * maximum spacing for sealing = min(4.0 + 4.0*t, 7.0) in (6.13.2.6.2);
    * minimum edge/end distance from Table 6.13.2.6.6-1;
    * maximum edge distance = min(8.0*t, 5.0) in (6.13.2.6.6).

    Any provided dimension is checked against its limit and the boolean flag
    set accordingly; ``None`` dimensions leave the flag ``None``."""
    min_spacing = 3.0 * d_bolt
    max_spacing_seal = min(4.0 + 4.0 * plate_t, 7.0)
    edges = MIN_EDGE_DISTANCE.get(round(d_bolt, 4), (2.0 * d_bolt, 1.5 * d_bolt))
    min_edge = edges[0] if sheared_edge else edges[1]
    max_edge = min(8.0 * plate_t, 5.0)
    return SpacingLimits(
        min_spacing=min_spacing,
        max_spacing_seal=max_spacing_seal,
        min_edge=min_edge,
        max_edge=max_edge,
        pitch_ok=None if pitch is None
        else min_spacing <= pitch <= max_spacing_seal,
        gage_ok=None if gage is None else gage >= min_spacing,
        edge_ok=None if edge_dist is None
        else min_edge <= edge_dist <= max_edge,
        end_ok=None if end_dist is None else end_dist >= min_edge,
    )
