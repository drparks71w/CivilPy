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

"""Phase 5 — reinforcement sizing, node checks, material take-off, and an ODOT
cost estimate for a solved strut-and-tie truss.

Forces come from the solved :class:`~civilpy.structural.strut_and_tie.\
StrutAndTieModel` (tension +, kips); ties are sized by inverting the AASHTO
5.8.2.4 tie resistance, struts/nodes are checked with 5.8.2.5.  Lengths are in
feet, areas in in^2; the cost model uses ODOT-style unit prices.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural.aashto.lrfd.stm import (
    stm_tie_resistance, stm_node_resistance, PHI_STM_TENSION,
)
from civilpy.structural.steel import Rebar


STEEL_DENSITY_PCF = 490.0   # lb/ft^3


# ── unit-price resolution ────────────────────────────────────────────────────
# civilpy ships order-of-magnitude ODOT-style defaults so the take-off works
# stand-alone.  A host application — e.g. the private snbi_ui ODOT estimator,
# which queries the DOT bid-data warehouse — registers a live provider with
# ``set_price_provider``.  civilpy never imports that engine, so the public
# package stays free of warehouse/bid data; if no provider is registered (or it
# is off-network and returns nothing) the defaults below are used.

DEFAULT_PRICES = {"concrete_cy": 850.0, "steel_lb": 1.20, "source": "civilpy-default"}
_PRICE_PROVIDER = None


def set_price_provider(provider):
    """Register a zero-argument callable that returns a unit-price mapping with
    keys ``concrete_cy`` ($/cy) and ``steel_lb`` ($/lb) — and optionally
    ``source``.  It is consulted whenever a take-off is requested without an
    explicit ``prices`` argument.  civilpy falls back to :data:`DEFAULT_PRICES`
    if the provider is unset, returns nothing, or raises.  Returns the previous
    provider (pass ``None`` to clear)."""
    global _PRICE_PROVIDER
    prev, _PRICE_PROVIDER = _PRICE_PROVIDER, provider
    return prev


def resolve_prices(prices=None) -> dict:
    """Resolve unit prices in priority order: explicit ``prices`` mapping > the
    registered provider > :data:`DEFAULT_PRICES`."""
    book = dict(DEFAULT_PRICES)
    if prices is None and _PRICE_PROVIDER is not None:
        try:
            prices = _PRICE_PROVIDER()
        except Exception:
            prices = None
    if prices:
        book.update({k: v for k, v in dict(prices).items() if v is not None})
    return book


@dataclass
class TieDesign:
    member: tuple
    force: float          # kips (tension, +)
    length: float         # ft
    a_st_required: float  # in^2
    bar_size: int
    bar_count: int
    a_st_provided: float  # in^2
    check: object         # CheckResult


@dataclass
class CostEstimate:
    concrete_cy: float
    steel_lb: float
    concrete_cost: float
    steel_cost: float
    total: float
    unit_prices: dict


@dataclass
class DesignReport:
    ties: list = field(default_factory=list)
    node_checks: list = field(default_factory=list)
    concrete_volume_cf: float = 0.0
    steel_volume_cf: float = 0.0
    cost: CostEstimate | None = None


def size_ties(model, *, f_y: float = 60.0, bar_size: int = 10) -> list[TieDesign]:
    """Size reinforcement for every tension member (tie).

    Required steel inverts AASHTO 5.8.2.4: ``Ast = Pu / (phi * fy)``; bars are
    rounded up to whole ``bar_size`` bars.
    """
    bar_area = float(Rebar(bar_size).area.magnitude)
    out = []
    for member, force in model.forces.items():
        if force <= 1e-6:
            continue  # struts handled by the node check
        a_req = force / (PHI_STM_TENSION * f_y)
        count = max(1, math.ceil(a_req / bar_area))
        a_prov = count * bar_area
        chk = stm_tie_resistance(a_st=a_prov, f_y=f_y, p_u=force)
        out.append(TieDesign(
            member=member, force=force, length=_length(model, member),
            a_st_required=a_req, bar_size=bar_size, bar_count=count,
            a_st_provided=a_prov, check=chk,
        ))
    return out


def check_nodes(model, problem) -> list:
    """Bearing/nodal-zone check (AASHTO 5.8.2.5) at each supported and loaded
    node where a bearing width is given.  Classifies the node CCC/CCT/CTT from
    the solved member signs meeting it."""
    f_c = problem.material.f_c
    thickness_in = problem.thickness * 12.0
    checks = []
    incident = _incident_members(model)
    for kind, label, demand, bearing in _bc_iter(model, problem):
        if not bearing:
            continue
        a_cn = (bearing * 12.0) * thickness_in
        node_type = _classify_node(model, label, incident)
        chk = stm_node_resistance(a_cn=a_cn, f_c=f_c, node_type=node_type,
                                  p_u=abs(demand))
        chk.details["node"] = label
        chk.details["kind"] = kind
        checks.append(chk)
    return checks


def material_takeoff(density_result, problem, ties, *, threshold: float = 0.3):
    """Concrete volume from the optimized density field and steel volume from
    the sized ties (cubic feet)."""
    mesh = density_result.mesh
    solid_area = float((density_result.density >= threshold).sum()) * mesh.h ** 2
    concrete_cf = solid_area * problem.thickness
    steel_cf = sum(t.a_st_provided * t.length / 144.0 for t in ties)  # in^2*ft -> ft^3
    return concrete_cf, steel_cf


def estimate_cost(concrete_cf, steel_cf, *, price_concrete_cy: float | None = None,
                  price_steel_lb: float | None = None, prices=None) -> CostEstimate:
    """ODOT-style cost: concrete by the cubic yard, reinforcing by the pound.

    Unit prices come from (highest priority first) the explicit ``price_*``
    arguments, then the ``prices`` mapping, then the registered price provider,
    then :data:`DEFAULT_PRICES` (see :func:`set_price_provider`)."""
    book = resolve_prices(prices)
    pcc = book["concrete_cy"] if price_concrete_cy is None else float(price_concrete_cy)
    psl = book["steel_lb"] if price_steel_lb is None else float(price_steel_lb)
    concrete_cy = concrete_cf / 27.0
    steel_lb = steel_cf * STEEL_DENSITY_PCF
    c_cost = concrete_cy * pcc
    s_cost = steel_lb * psl
    return CostEstimate(
        concrete_cy=concrete_cy, steel_lb=steel_lb,
        concrete_cost=c_cost, steel_cost=s_cost, total=c_cost + s_cost,
        unit_prices={"concrete_cy": pcc, "steel_lb": psl,
                     "source": book.get("source", "civilpy-default")},
    )


def design_report(model, problem, density_result, *, threshold: float = 0.3,
                  **price_kwargs) -> DesignReport:
    ties = size_ties(model)
    nodes = check_nodes(model, problem)
    concrete_cf, steel_cf = material_takeoff(density_result, problem, ties,
                                             threshold=threshold)
    cost = estimate_cost(concrete_cf, steel_cf, **price_kwargs)
    return DesignReport(ties=ties, node_checks=nodes,
                        concrete_volume_cf=concrete_cf, steel_volume_cf=steel_cf,
                        cost=cost)


# ── helpers ────────────────────────────────────────────────────────────────

def _length(model, member):
    (xa, ya), (xb, yb) = model.nodes[member[0]], model.nodes[member[1]]
    return math.hypot(xb - xa, yb - ya)


def _incident_members(model):
    inc = {n: [] for n in model.nodes}
    for m in model.members:
        inc[m[0]].append(m)
        inc[m[1]].append(m)
    return inc


def _classify_node(model, label, incident):
    """CCC (all struts), CCT (one tie), CTT (two+ ties) from member signs."""
    n_ties = sum(1 for m in incident.get(label, []) if model.forces.get(m, 0.0) > 1e-6)
    return {0: "CCC", 1: "CCT"}.get(n_ties, "CTT")


def _bc_iter(model, problem):
    """Yield ``(kind, node_label, demand, bearing)`` for each support/load."""
    from civilpy.structural.stm_topology.extract import _nearest_label
    for s in problem.supports:
        lab = _nearest_label(model, (s.x, s.y))
        if lab and lab in model.reactions:
            rx, ry = model.reactions[lab]
            yield "support", lab, math.hypot(rx, ry), s.bearing
    for ld in problem.loads:
        lab = _nearest_label(model, (ld.x, ld.y))
        if lab:
            yield "load", lab, ld.magnitude, ld.bearing
