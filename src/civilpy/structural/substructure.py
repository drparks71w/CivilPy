#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Substructure reactions from a solved bridge grillage -- the hand-off from
superstructure analysis to pier/abutment and foundation design.

A refined-grillage superstructure (from
:func:`civilpy.structural.bridge_layout.grillage_model_from_layout`) sits on
bearings at every support line.  Those bearing reactions, **summed across the
girders of each support line and factored into the AASHTO load combinations**,
are exactly the loads a substructure unit (abutment or pier) and its foundation
are designed for.  This module pulls the per-node reactions MIDAS solved, bins
them onto their substructure unit by station, and applies the combinations.

Sign/units: reactions in the model's units (kips, ft) as MIDAS reports them --
``FZ`` up-positive vertical, ``FX`` longitudinal (along stations), ``FY``
transverse, ``MX/MY/MZ`` the moments.  The vertical ``FZ`` and the horizontals
size the bearings and the pier; the total ``FZ`` per unit sizes the foundation.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Map a load-case name to its AASHTO load type (for the combinations).
LOAD_TYPE = {
    "DC1": "DC", "DC2": "DC", "DW": "DW", "LL-LANE": "LL",
    "MOT-LANE": "LL", "PCB": "DC", "CLOSURE": "DC",
}

#: Vertical AASHTO LRFD strength/service combinations (max load factors).
DEFAULT_COMBOS = {
    "Strength I": {"DC": 1.25, "DW": 1.50, "LL": 1.75},
    "Service I": {"DC": 1.00, "DW": 1.00, "LL": 1.00},
}

COMPONENTS = ("FX", "FY", "FZ", "MX", "MY", "MZ")


@dataclass(frozen=True)
class SubstructureUnit:
    """One support line: an abutment or pier the superstructure bears on."""

    index: int            # support-line index, 0 at the start abutment
    name: str             # "Abutment 1", "Pier 2", ...
    station_ft: float     # station along the layout centerline


def substructure_units(layout) -> list[SubstructureUnit]:
    """The abutments and piers of ``layout``, one per support line."""
    stations = [0.0]
    for s in layout.inputs.spans_ft:
        stations.append(stations[-1] + s)
    last = len(stations) - 1
    units = []
    for i, st in enumerate(stations):
        if i == 0:
            name = "Abutment 1"
        elif i == last:
            name = "Abutment 2"
        else:
            name = f"Pier {i + 1}"
        units.append(SubstructureUnit(i, name, st))
    return units


def _midas_node_ids(model) -> dict[str, int]:
    """Map each hub node id to its 1-based MIDAS id (node insertion order,
    matching :func:`civilpy.structural.midas_models.midas_payloads`)."""
    return {nid: k for k, nid in enumerate(model.nodes, start=1)}


def restrained_node_midas_ids(model) -> list[int]:
    """MIDAS ids of the restrained (support) nodes."""
    ids = _midas_node_ids(model)
    return [ids[nid] for nid in model.restraints if nid in ids]


def fetch_support_reactions(midas, model, cases: list[str], *,
                            suffix: str = "(ST)") -> dict[str, dict[int, tuple]]:
    """Pull the support reactions for each static ``case`` from a solved MIDAS
    model: ``{case: {midas_node_id: (FX, FY, FZ, MX, MY, MZ)}}``.

    ``suffix`` is the result-case suffix MIDAS appends (``"(ST)"`` static,
    ``"(CB)"`` combination).  Call :meth:`MidasCivil.analyze` first.
    """
    from civilpy.structural.midas import parse_result_table
    node_ids = restrained_node_midas_ids(model)
    out: dict[str, dict[int, tuple]] = {}
    for case in cases:
        resp = midas.result_table(
            "Reaction", table_type="REACTIONG",
            components=["Node", *COMPONENTS],
            node_elems={"KEYS": node_ids},
            load_case_names=[f"{case}{suffix}"])
        by_node: dict[int, tuple] = {}
        for row in parse_result_table(resp):
            try:
                nid = int(row.get("Node"))
            except (TypeError, ValueError):
                continue
            by_node[nid] = tuple(float(row.get(c) or 0.0) for c in COMPONENTS)
        out[case] = by_node
    return out


def group_support_reactions(model, layout, reactions_by_case: dict[str, dict[int, tuple]]
                            ) -> dict[str, dict[str, tuple]]:
    """Sum per-node reactions onto their substructure unit, per case.

    ``reactions_by_case`` is ``{case: {midas_node_id: 6-tuple}}`` (from
    :func:`fetch_support_reactions`).  Each node is binned to the nearest
    support line by its station (``X``).  Returns
    ``{unit_name: {case: (FX..MZ) sum}}``.
    """
    id_to_str = {k: nid for nid, k in _midas_node_ids(model).items()}
    units = substructure_units(layout)
    stations = [u.station_ft for u in units]

    def unit_of(x: float) -> str:
        i = min(range(len(stations)), key=lambda j: abs(stations[j] - x))
        return units[i].name

    grouped: dict[str, dict[str, list]] = {
        u.name: {} for u in units}
    for case, by_node in reactions_by_case.items():
        for nid, comps in by_node.items():
            hub_id = id_to_str.get(nid)
            if hub_id is None:
                continue
            x = model.nodes[hub_id].coords[0]
            acc = grouped[unit_of(x)].setdefault(
                case, [0.0] * len(COMPONENTS))
            for j, v in enumerate(comps):
                acc[j] += v
    return {u: {c: tuple(v) for c, v in cases.items()}
            for u, cases in grouped.items()}


def design_reactions(grouped: dict[str, dict[str, tuple]], *,
                     combos: dict[str, dict[str, float]] | None = None
                     ) -> dict[str, dict[str, tuple]]:
    """Apply the AASHTO load combinations to grouped per-unit reactions.

    Returns ``{unit_name: {combo_name: (FX..MZ)}}`` -- the factored reactions
    each substructure unit and foundation is designed for.  Cases are mapped to
    DC/DW/LL by :data:`LOAD_TYPE`; a case with an unknown name is treated as DC.
    """
    combos = combos or DEFAULT_COMBOS
    out: dict[str, dict[str, tuple]] = {}
    for unit, cases in grouped.items():
        out[unit] = {}
        for combo, factors in combos.items():
            acc = [0.0] * len(COMPONENTS)
            for case, comps in cases.items():
                f = factors.get(LOAD_TYPE.get(case, "DC"), 0.0)
                for j, v in enumerate(comps):
                    acc[j] += f * v
            out[unit][combo] = tuple(acc)
    return out


def substructure_reaction_report(midas, model, layout, cases: list[str], *,
                                 combos: dict[str, dict[str, float]] | None = None
                                 ) -> dict:
    """Solve-side convenience: fetch, group, and combine in one call on a
    **solved** MIDAS model.  Returns
    ``{"by_case": grouped, "design": design_reactions, "units": [...]}``.
    """
    raw = fetch_support_reactions(midas, model, cases)
    grouped = group_support_reactions(model, layout, raw)
    return {
        "by_case": grouped,
        "design": design_reactions(grouped, combos=combos),
        "units": [u.name for u in substructure_units(layout)],
    }
