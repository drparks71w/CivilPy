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

"""AASHTO LRFD 5.8.2 — strut-and-tie method capacity checks.

The geometry/force side (truss solution and diagram) lives in
:mod:`civilpy.structural.strut_and_tie`; these functions check the solved
member forces.  Note BrR performs no STM checks — like the Section 13
railing provisions, these have no BrR counterpart to validate against.
Units: kip, inch, ksi.  Pass strut forces as magnitudes (positive).
"""

from civilpy.structural.aashto.lrfd.core import CheckResult, article

PHI_STM_TENSION = 0.90  # ties (5.5.4.2)
PHI_STM_COMPRESSION = 0.70  # struts and nodes (5.5.4.2)

# Concrete efficiency factor nu (Table 5.8.2.5.3a-1) by node type, for
# node regions WITH crack-control reinforcement per 5.8.2.6.  Without it,
# nu = 0.45 regardless of node type.
NODE_EFFICIENCY = {"CCC": 0.85, "CCT": 0.70, "CTT": 0.65}


@article("5.8.2.4", "STM Tie Resistance")
def stm_tie_resistance(
    a_st: float,
    f_y: float = 60.0,
    a_ps: float = 0.0,
    f_pe: float = 0.0,
    p_u: float | None = None,
) -> CheckResult:
    """Nominal resistance of a tie (5.8.2.4.1-1):
    Pn = fy*Ast + Aps*(fpe + fy), phi = 0.90.

    The prestressing term caps the usable strand stress at fpe plus one
    mild-steel yield increment so tie strain stays compatible with the
    surrounding reinforcement.  ``p_u`` is the solved tie force (kip)."""
    p_n = f_y * a_st + a_ps * (f_pe + f_y)
    return CheckResult(
        article="5.8.2.4",
        name="STM Tie Resistance",
        capacity=p_n,
        demand=p_u,
        phi=PHI_STM_TENSION,
        details={"Ast": a_st, "Aps": a_ps},
    )


@article("5.8.2.5", "STM Node Face / Strut Resistance")
def stm_node_resistance(
    a_cn: float,
    f_c: float,
    node_type: str = "CCC",
    crack_control: bool = True,
    m_confinement: float = 1.0,
    p_u: float | None = None,
    nu: float | None = None,
) -> CheckResult:
    """Crushing resistance of a node face or the strut bearing on it
    (5.8.2.5.3): Pn = fcu*Acn with fcu = m*nu*f'c.

    ``node_type`` is the joint classification (CCC, CCT, CTT) setting the
    efficiency factor nu from Table 5.8.2.5.3a-1; without crack-control
    reinforcement per 5.8.2.6, nu drops to 0.45.  ``m_confinement`` is the
    sqrt(A2/A1) <= 2 bearing modification; pass ``nu`` directly to
    override the table.  phi = 0.70."""
    if nu is None:
        nu = NODE_EFFICIENCY[node_type] if crack_control else 0.45
    f_cu = min(m_confinement, 2.0) * nu * f_c
    p_n = f_cu * a_cn
    return CheckResult(
        article="5.8.2.5",
        name="STM Node Face / Strut Resistance",
        capacity=p_n,
        demand=p_u,
        phi=PHI_STM_COMPRESSION,
        details={"fcu": f_cu, "nu": nu, "node_type": node_type,
                 "crack_control": crack_control},
    )


@article("5.8.2.6", "STM Crack Control Reinforcement")
def stm_crack_control_reinforcement(
    b_w: float,
    s_h: float,
    s_v: float,
    a_s_horizontal: float | None = None,
    a_s_vertical: float | None = None,
) -> CheckResult:
    """Orthogonal crack-control reinforcement in the D-region (5.8.2.6):
    a ratio of at least 0.003 in each direction, spacing <= min(d/4, 12in)
    checked by the caller.

    Pass the provided bar areas per grid spacing (in^2 at ``s_h``/``s_v``
    in); the check compares each direction's ratio against 0.003.  This
    is what qualifies the nodes for the full Table 5.8.2.5.3a-1 nu."""
    required = 0.003
    ratios = {}
    if a_s_horizontal is not None:
        ratios["horizontal"] = a_s_horizontal / (b_w * s_v)
    if a_s_vertical is not None:
        ratios["vertical"] = a_s_vertical / (b_w * s_h)
    governing = min(ratios.values()) if ratios else 0.0
    return CheckResult(
        article="5.8.2.6",
        name="STM Crack Control Reinforcement",
        capacity=governing,
        demand=required,
        details={**ratios, "required_ratio": required},
    )
