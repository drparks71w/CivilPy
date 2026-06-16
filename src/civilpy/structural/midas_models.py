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

"""Payload builders for the bridge model types MIDAS Civil NX is built for.

These are **pure** functions: each returns the ``{id: {...}}`` *assign*
dictionaries the MIDAS API expects, so they can be unit-tested with no live
session and then pushed with
``civilpy.structural.midas.MidasCivil.put_db(table, assign)``.  They cover
the geometries a line-girder framing plan cannot express:

* :func:`curved_girder_model` -- horizontally curved girders, modelled as
  concentric chorded beam lines with optional transverse diaphragms (the
  grid action that makes a curved bridge behave is in the diaphragms).
* :func:`bifurcated_girder_model` -- a girder line that splits at a gore
  node into diverging branches (ramp splits, Y-piers).
* :func:`abutment_connection` -- the super-/substructure connection for
  **integral** (monolithic, moment-continuous via a rigid link) and
  **semi-integral** (girders on bearings, deck continuous) abutments.
* :func:`soil_spring_supports` -- nodal foundation springs from the p-y /
  t-z / q-z stiffnesses in :mod:`civilpy.geotech.lateral_pile` and
  :mod:`civilpy.geotech.axial_load_transfer`, so a pier or integral pile
  bent rests on soil rather than on fixed points.

Table schemas (NODE, ELEM, CONS, FRLS, ELNK, RIGD) follow the
``/db/*`` manual pages.  **The point-spring table name is not yet verified
against a live release** -- :func:`soil_spring_supports` returns the body and
takes the table name as an argument; capture a real one per the live-capture
checklist before relying on it.

Units: geometry in the model's length unit (feet in the civilpy/BrR default
KIPS/FT system); spring stiffnesses are passed through in model units -- use
:func:`lb_per_in_to_kip_per_ft` to convert the geotech curves' lb/in values.
Constraint/release flag strings are DX DY DZ RX RY RZ RW ('1' = fixed for
CONS, '1' = released for FRLS), matching the rest of the API client.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional


def lb_per_in_to_kip_per_ft(k_lb_per_in: float) -> float:
    """Convert a spring constant from lb/in (the geotech curve unit) to
    kip/ft (the KIPS/FT model unit): ``k[kip/ft] = k[lb/in] * 12 / 1000``."""
    return k_lb_per_in * 12.0 / 1000.0


# ============================================================ curved girders


def circular_curve_nodes(
    radius: float,
    central_angle_deg: float,
    n_segments: int,
    girder_offsets: Iterable[float],
    *,
    z: float = 0.0,
    node_start: int = 1,
) -> tuple[dict, dict]:
    """Nodes for girders following a horizontal circular curve.

    Each girder is a concentric arc: girder ``g`` at radial ``offset`` rides
    radius ``radius + offset`` (offset positive toward the outside of the
    curve).  The arc sweeps ``central_angle_deg`` in ``n_segments`` equal
    steps; the curve centre is at the origin and station 0 lies on the +Y
    axis, so ``X = r*sin(theta)`` and ``Y = r*cos(theta)``.

    Returns ``(assign, grid)`` where ``assign`` is the ``/db/NODE`` body
    ``{id: {"X", "Y", "Z"}}`` and ``grid`` maps ``(girder_index,
    station_index) -> node_id`` for wiring elements.
    """
    offsets = list(girder_offsets)
    dtheta = math.radians(central_angle_deg) / n_segments
    assign: dict = {}
    grid: dict = {}
    nid = node_start
    for g, offset in enumerate(offsets):
        r = radius + offset
        for i in range(n_segments + 1):
            theta = i * dtheta
            assign[str(nid)] = {
                "X": round(r * math.sin(theta), 6),
                "Y": round(r * math.cos(theta), 6),
                "Z": z,
            }
            grid[(g, i)] = nid
            nid += 1
    return assign, grid


def curved_girder_model(
    radius: float,
    central_angle_deg: float,
    n_segments: int,
    girder_offsets: Iterable[float],
    *,
    matl: int = 1,
    sect: int = 1,
    diaphragm_sect: Optional[int] = None,
    node_start: int = 1,
    elem_start: int = 1,
) -> dict:
    """A horizontally curved multi-girder model: concentric chorded girder
    lines plus, when ``diaphragm_sect`` is given, a transverse diaphragm
    between adjacent girders at every station.

    Returns ``{"NODE": ..., "ELEM": ..., "grid": ..., "meta": ...}`` where
    ``NODE``/``ELEM`` are ``/db/*`` assign bodies.  Chorded straight beams
    approximate the curve (standard practice); refine ``n_segments`` until
    the chord offset is acceptable.
    """
    offsets = list(girder_offsets)
    nodes, grid = circular_curve_nodes(
        radius, central_angle_deg, n_segments, offsets, node_start=node_start
    )
    elems: dict = {}
    eid = elem_start
    # Longitudinal girder beams.
    for g in range(len(offsets)):
        for i in range(n_segments):
            elems[str(eid)] = {
                "TYPE": "BEAM", "MATL": matl, "SECT": sect,
                "NODE": [grid[(g, i)], grid[(g, i + 1)]], "ANGLE": 0,
            }
            eid += 1
    # Transverse diaphragms / cross-frames between adjacent girders.
    if diaphragm_sect is not None:
        for g in range(len(offsets) - 1):
            for i in range(n_segments + 1):
                elems[str(eid)] = {
                    "TYPE": "BEAM", "MATL": matl, "SECT": diaphragm_sect,
                    "NODE": [grid[(g, i)], grid[(g + 1, i)]], "ANGLE": 0,
                }
                eid += 1
    return {
        "NODE": nodes, "ELEM": elems, "grid": grid,
        "meta": {"radius": radius, "central_angle_deg": central_angle_deg,
                 "n_segments": n_segments, "n_girders": len(offsets),
                 "arc_length": math.radians(central_angle_deg) * radius},
    }


# ============================================================ bifurcated girders


def bifurcated_girder_model(
    stem_length: float,
    stem_segments: int,
    branches: list[dict],
    *,
    stem_offset: float = 0.0,
    matl: int = 1,
    sect: int = 1,
    node_start: int = 1,
    elem_start: int = 1,
) -> dict:
    """A girder line that runs straight for ``stem_length`` then splits at a
    gore node into diverging branches.

    The stem runs along +X from ``(0, stem_offset)`` to ``(stem_length,
    stem_offset)`` in ``stem_segments`` beams; the last stem node is the
    **gore**.  Each entry in ``branches`` is
    ``{"length", "end_offset", "segments"}`` -- a branch from the gore to
    ``(stem_length + length, end_offset)``, straight-line interpolated.

    Returns ``{"NODE", "ELEM", "gore_node", "branch_end_nodes", "meta"}``.
    """
    nodes: dict = {}
    elems: dict = {}
    nid = node_start
    eid = elem_start

    # Stem.
    stem_ids = []
    for i in range(stem_segments + 1):
        x = stem_length * i / stem_segments
        nodes[str(nid)] = {"X": round(x, 6), "Y": stem_offset, "Z": 0.0}
        stem_ids.append(nid)
        nid += 1
    for i in range(stem_segments):
        elems[str(eid)] = {
            "TYPE": "BEAM", "MATL": matl, "SECT": sect,
            "NODE": [stem_ids[i], stem_ids[i + 1]], "ANGLE": 0,
        }
        eid += 1
    gore_node = stem_ids[-1]

    # Branches diverging from the gore.
    branch_end_nodes = []
    for br in branches:
        length = br["length"]
        end_offset = br["end_offset"]
        segments = br.get("segments", stem_segments)
        prev = gore_node
        for j in range(1, segments + 1):
            f = j / segments
            x = stem_length + length * f
            y = stem_offset + (end_offset - stem_offset) * f
            nodes[str(nid)] = {"X": round(x, 6), "Y": round(y, 6), "Z": 0.0}
            elems[str(eid)] = {
                "TYPE": "BEAM", "MATL": matl, "SECT": sect,
                "NODE": [prev, nid], "ANGLE": 0,
            }
            prev = nid
            nid += 1
            eid += 1
        branch_end_nodes.append(prev)

    return {
        "NODE": nodes, "ELEM": elems, "gore_node": gore_node,
        "branch_end_nodes": branch_end_nodes,
        "meta": {"stem_length": stem_length, "n_branches": len(branches)},
    }


# ============================================================ abutments


def abutment_connection(
    kind: str,
    girder_end_nodes: Iterable[int],
    seat_node: int,
    *,
    bearing_stiffness: Optional[list[float]] = None,
    link_start: int = 1,
) -> dict:
    """Super-/substructure connection at an abutment.

    ``kind="integral"`` -- girders are cast monolithically into the abutment
    cap: a **rigid link** (``/db/RIGD``) makes ``seat_node`` the master and
    every girder end a slave for all six DOF, so the connection is
    moment-continuous and thermal movement is taken by the (flexible) pile
    bent below -- give that bent :func:`soil_spring_supports`, not fixed
    bases.

    ``kind="semi-integral"`` -- the deck/backwall is continuous but the
    girders bear on bearings at the seat: an **elastic link** (``/db/ELNK``,
    ``LINK="GEN"``) per girder carries vertical load stiffly and frees
    longitudinal translation and rotation.  ``bearing_stiffness`` is the
    ``SDR`` vector ``[kdx, kdy, kdz, krx, kry, krz]`` in model units;
    the default is a near-rigid vertical (kdz) bearing, soft elsewhere.

    Returns a dict of ``/db/*`` assign bodies to merge into the model
    (``{"RIGD": ...}`` or ``{"ELNK": ...}``).
    """
    ends = list(girder_end_nodes)
    if kind == "integral":
        return {"RIGD": {str(seat_node): {
            "ITEMS": [{"ID": 1, "DOF": 111111, "S_NODE": ends}],
        }}}
    if kind == "semi-integral":
        sdr = bearing_stiffness or [10.0, 10.0, 1.0e7, 0.0, 0.0, 0.0]
        elnk: dict = {}
        for i, end in enumerate(ends):
            elnk[str(link_start + i)] = {
                "NODE": [end, seat_node], "LINK": "GEN", "ANGLE": 0,
                "SDR": list(sdr),
            }
        return {"ELNK": elnk}
    raise ValueError(f"unknown kind {kind!r} (use 'integral' or 'semi-integral')")


# ============================================================ soil springs


def soil_spring_supports(
    node_springs: dict[int, list[float]],
    *,
    table: str = "SPRING",
    spring_type: str = "LINEAR",
) -> dict:
    """Nodal foundation springs from per-node stiffness vectors.

    ``node_springs`` maps ``node_id -> [kdx, kdy, kdz, krx, kry, krz]`` in
    model units (convert the geotech curves' lb/in values with
    :func:`lb_per_in_to_kip_per_ft`).  Typically ``kdx``/``kdy`` come from
    the p-y secant modulus (:mod:`civilpy.geotech.lateral_pile`), ``kdz``
    from the t-z springs and the q-z tip spring
    (:mod:`civilpy.geotech.axial_load_transfer`).

    Returns the assign body ``{node_id: {"ITEMS": [{"ID": 1, "TYPE": ...,
    "SDR": [...]}]}}``.  **The MIDAS point-spring table name is unverified**
    -- pass the live-confirmed ``table`` to
    ``MidasCivil.put_db(table, body)`` (see the live-capture checklist).
    """
    assign: dict = {}
    for node_id, sdr in node_springs.items():
        if len(sdr) != 6:
            raise ValueError(
                f"node {node_id}: expected 6 stiffnesses [kdx,kdy,kdz,krx,kry,krz], "
                f"got {len(sdr)}")
        assign[str(node_id)] = {
            "ITEMS": [{"ID": 1, "TYPE": spring_type, "SDR": list(sdr)}],
        }
    return assign
