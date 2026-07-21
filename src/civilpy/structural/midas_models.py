#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

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
from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:                                    # avoid an import cycle / hard dep
    from civilpy.structural.structural_model import StructuralModel


def lb_per_in_to_kip_per_ft(k_lb_per_in: float) -> float:
    """Convert a spring constant from lb/in (the geotech curve unit) to
    kip/ft (the KIPS/FT model unit): ``k[kip/ft] = k[lb/in] * 12 / 1000``."""
    return k_lb_per_in * 12.0 / 1000.0


# ===================================================== shared MIDAS encoders
#
# The NODE/ELEM/CONS/UNIT/MATL encodings below are the *single* source of
# those payload fragments: both the hub serializer in
# this module and ``TrussBridge.midas_payloads`` build them here so the two
# Midas exporters cannot drift.

#: A709 Grade 50 steel in KIPS/FT model units (E in ksf, density in kcf) --
#: the structural-steel property block both exporters share.
STEEL_PROPS = {"ELAST": 4_176_000.0, "POISN": 0.3,
               "THERMAL": 6.5e-06, "DEN": 0.490}

#: Map civilpy ``Units`` labels onto the MIDAS ``UNIT`` enum values.
_FORCE_UNIT = {"kips": "KIPS", "kip": "KIPS", "kn": "KN", "n": "N",
               "lbf": "LBF", "tonf": "TONF", "kgf": "KGF"}
_DIST_UNIT = {"ft": "FT", "feet": "FT", "in": "IN", "inch": "IN", "m": "M",
              "mm": "MM", "cm": "CM"}


def unit_block(force: str = "KIPS", dist: str = "FT",
               heat: str = "BTU", temper: str = "F") -> dict:
    """The ``/db/UNIT`` assign body ``{"1": {FORCE, DIST, HEAT, TEMPER}}``."""
    return {"1": {"FORCE": force, "DIST": dist, "HEAT": heat, "TEMPER": temper}}


def unit_block_for(units) -> dict:
    """``unit_block`` from a hub :class:`~civilpy.structural.structural_model.Units`
    (maps the kips/ft labels to the MIDAS enum; unknown labels pass through
    upper-cased)."""
    force = _FORCE_UNIT.get(units.force.lower(), units.force.upper())
    dist = _DIST_UNIT.get(units.length.lower(), units.length.upper())
    return unit_block(force, dist)


def steel_material_block(name: str = "A709-50", *, matl_id: int = 1,
                         props: Optional[dict] = None) -> dict:
    """The ``/db/MATL`` assign body for a USER-defined steel material."""
    return {str(matl_id): {
        "TYPE": "USER", "NAME": name, "THMAL_UNIT": "F",
        "bMASS_DENS": False, "DAMP_RAT": 0.0,
        "PARAM": [{"P_TYPE": 2, "MASS": 0.0, **(props or STEEL_PROPS)}],
    }}


def concrete_elastic_modulus_ksf(fc_psi: float, unit_wt_pcf: float = 145.0) -> float:
    """Concrete elastic modulus in **kips/ft^2** from ``f'c`` (psi).

    AASHTO LRFD 5.4.2.4 / ACI 318:
    ``Ec = 33000 * K1 * (wc/1000)^1.5 * sqrt(f'c)`` with ``wc`` in kcf and
    ``f'c`` in ksi gives ``Ec`` in ksi; convert to ksf (x144) for a model
    whose DIST unit is feet. For ``f'c`` = 4500 psi, ``wc`` = 145 pcf this is
    ~3952 ksi, the value MIDAS should hold for an SB-1-24 slab -- not the
    ~29000 ksi steel modulus ``midas_payloads`` otherwise defaults to.
    """
    wc_kcf = unit_wt_pcf / 1000.0
    fc_ksi = fc_psi / 1000.0
    ec_ksi = 33000.0 * (wc_kcf ** 1.5) * (fc_ksi ** 0.5)
    return ec_ksi * 144.0


def concrete_material_block(name: str = "Class-S-4500", *, matl_id: int = 1,
                            fc_psi: float = 4500.0,
                            unit_wt_pcf: float = 145.0) -> dict:
    """A ``/db/MATL`` USER concrete material with ``Ec`` from :func:`concrete_elastic_modulus_ksf`.

    ``DEN`` (weight density) is carried in the model's force/length^3 unit
    (kips/ft^3 in the civilpy default), so 145 pcf -> 0.145 kcf.
    """
    return {str(matl_id): {
        "TYPE": "USER", "NAME": name, "THMAL_UNIT": "F",
        "bMASS_DENS": False, "DAMP_RAT": 0.0,
        "PARAM": [{"P_TYPE": 2, "MASS": 0.0,
                   "ELAST": round(concrete_elastic_modulus_ksf(fc_psi, unit_wt_pcf), 3),
                   "POISN": 0.2, "THERMAL": 6.0e-06,
                   "DEN": round(unit_wt_pcf / 1000.0, 6)}],
    }}


def solid_rect_section_block(width: float, height: float, *, sect_id: int = 1,
                             name: str | None = None) -> dict:
    """A solid-rectangle (``SB``) ``/db/SECT`` body, ``width`` x ``height`` in
    the model's length unit.

    This is the honest section for an equivalent-strip slab beam (a 1 ft wide
    x thickness deep concrete strip), where an AISC I-shape reference makes no
    sense. Dimension order matches the placeholder square: ``vSIZE = [H, B]``
    is MIDAS's [depth, width] for the SB shape.
    """
    name = name or f"RECT-{width:g}x{height:g}"
    return {str(sect_id): {
        "SECTTYPE": "DBUSER", "SECT_NAME": name,
        "SECT_BEFORE": {"SHAPE": "SB", "DATATYPE": 2,
                        "SECT_I": {"vSIZE": [round(height, 6),
                                             round(width, 6)]}},
    }}


def thickness_block(t_ft: float, *, thik_id: int = 1,
                    name: str | None = None) -> dict:
    """A ``/db/THIK`` value-thickness body (``t_ft`` in the model length unit),
    the plate-element analogue of a beam ``SECT``.  A plate ``ELEM`` references
    this id through its **``SECT`` field** (verified against a live Civil NX
    release: the plate body is ``{"TYPE":"PLATE","MATL":m,"SECT":<thik id>,
    "NODE":[n1..n4,0,0,0,0],"ANGLE":0,"STYPE":1}``)."""
    return {str(thik_id): {
        "NAME": name or str(thik_id), "TYPE": "VALUE", "bINOUT": False,
        "T_IN": round(t_ft, 6), "T_OUT": round(t_ft, 6), "O_VALUE": 0,
    }}


def _thickness_ft_from_label(label: str) -> float:
    """Parse a deck-thickness label like ``"DECK-8.5in"`` to feet (default 8 in)."""
    import re
    m = re.search(r"([\d.]+)\s*in", label or "")
    return (float(m.group(1)) if m else 8.0) / 12.0


def _fc_psi_from_label(label: str) -> float:
    """Parse an f'c out of a concrete label like ``"Deck-4500psi"`` (default 4500)."""
    import re
    m = re.search(r"([\d.]+)\s*psi", label or "")
    return float(m.group(1)) if m else 4500.0


def placeholder_section_block(*, sect_id: int = 1, side_ft: float = 1.0,
                              name: str = "PLACEHOLDER-1ft-SQ") -> dict:
    """A solid-square ``/db/SECT`` placeholder so exported elements reference a
    valid section.  Swap to the real shape inside Civil NX for flexure -- the
    equal-area square keeps axial stiffness honest meanwhile (same convention
    as ``TrussBridge``)."""
    return {str(sect_id): {
        "SECTTYPE": "DBUSER", "SECT_NAME": name,
        "SECT_BEFORE": {"SHAPE": "SB", "DATATYPE": 2,
                        "SECT_I": {"vSIZE": [round(side_ft, 6),
                                             round(side_ft, 6)]}},
    }}


def rolled_i_section_block(shape_label: str, *, sect_id: int = 1,
                          length_unit: str = "in",
                          db_name: str | None = "AISC10(US)") -> dict:
    """A ``/db/SECT`` body for a rolled I/H shape.

    By default this references the shape directly out of MIDAS's own
    section database (``db_name="AISC10(US)"``, ``DATATYPE=1``) rather than
    re-entering dimensions as a user-input section: ``shape_label`` (e.g.
    ``"W24X104"``) must match a name in that database, and MIDAS -- not
    civilpy -- is then the source of truth for the section properties used
    in analysis.  This is the correct choice for standard rolled shapes;
    civilpy's own ``steel.W`` dimensions are not sent at all in this path.
    Confirmed against a live Civil NX round-trip: ``GET /db/SECT`` echoed
    back exactly this ``SECT_BEFORE`` shape for a section entered as
    "DB/Shape -> AISC10(US) -> W24X104" in the Civil NX UI.

    Pass ``db_name=None`` for a built-up or historic shape with no library
    entry -- this falls back to a user-input (``DATATYPE=2``) section with
    dimensions pulled from ``steel.W`` (the AISC database module), the
    previous default behavior.  ``length_unit`` is a Pint unit string
    (``"in"``, ``"ft"``, ...) and **must match the model's own ``UNIT``
    table DIST** in that fallback -- MIDAS applies one length unit to every
    geometric quantity in the model, section dimensions included, so a
    mismatch silently scales the section by the conversion factor (inches
    sent while the model is in feet gives a 12x oversized, self-intersecting
    section). Callers building a full model payload should pass the model's
    own ``units.length`` (see :func:`hub_section_material_blocks`); the
    ``"in"`` default is only for standalone use."""
    common = {
        "OFFSET_PT": "CC", "OFFSET_CENTER": 0, "USER_OFFSET_REF": 0,
        "HORZ_OFFSET_OPT": 0, "USERDEF_OFFSET_YI": 0,
        "VERT_OFFSET_OPT": 0, "USERDEF_OFFSET_ZI": 0,
        "USE_SHEAR_DEFORM": True, "USE_WARPING_EFFECT": False,
        "SHAPE": "H",
    }
    if db_name is not None:
        sect_before = {**common, "DATATYPE": 1,
                       "SECT_I": {"DB_NAME": db_name,
                                  "SECT_NAME": shape_label}}
    else:
        from civilpy.structural import steel
        w = steel.W(shape_label)

        def _conv(q):
            return round(float(q.to(length_unit).magnitude), 6)

        h, b, tw, tf = (_conv(w.depth), _conv(w.flange_width),
                        _conv(w.web_thickness), _conv(w.flange_thickness))
        sect_before = {**common, "DATATYPE": 2,
                       "SECT_I": {"vSIZE": [h, b, tw, tf, b, tf]}}
    return {str(sect_id): {
        "SECTTYPE": "DBUSER", "SECT_NAME": shape_label,
        "SECT_BEFORE": sect_before,
    }}


def hub_section_material_blocks(model, *, sect_start: int = 1,
                                matl_start: int = 1,
                                default_grade: str = "Grade 50",
                                length_unit: str | None = None,
                                db_name: str | None = "AISC10(US)") -> dict:
    """Assign a real ``SECT`` per distinct AISC shape and a ``MATL`` per
    distinct grade from the hub's elements (stage **G5** -- replaces the single
    placeholder SECT/MATL that ``midas_payloads`` emits by default).

    Every shape is sent as a reference into MIDAS's own ``db_name`` section
    database (default ``"AISC10(US)"``) rather than a re-entered set of
    dimensions -- see :func:`rolled_i_section_block`.  Pass ``db_name=None``
    if the model's shapes are built-up/historic sections with no library
    entry; ``length_unit`` (defaulting to the model's own ``units.length``)
    only matters in that fallback, to keep section dimensions consistent
    with the ``NODE`` coordinates and the ``UNIT`` table's DIST.

    Returns ``{"SECT", "MATL", "sect_by_shape", "matl_by_grade",
    "elem_assign"}`` where ``elem_assign`` maps each ``Element.id`` to its
    ``(sect_id, matl_id)`` so the caller can wire real sections onto elements.
    Elements with no ``section`` label get ``sect_id=None`` (keep the
    placeholder for those).
    """
    length_unit = length_unit or model.units.length
    shapes: dict[str, int] = {}
    grades: dict[str, int] = {}
    sect: dict = {}
    matl: dict = {}
    elem_assign: dict = {}
    for elem in model.elements.values():
        if elem.midas_type == "PLATE":
            continue                 # plates carry a THIK + concrete, not a SECT
        label = elem.section
        grade = elem.material or default_grade
        if label and label not in shapes:
            sid = sect_start + len(shapes)
            shapes[label] = sid
            sect.update(rolled_i_section_block(label, sect_id=sid,
                                                length_unit=length_unit,
                                                db_name=db_name))
        if grade not in grades:
            mid = matl_start + len(grades)
            grades[grade] = mid
            matl.update(steel_material_block(name=grade, matl_id=mid))
        elem_assign[elem.id] = (shapes.get(label), grades[grade])
    return {"SECT": sect, "MATL": matl, "sect_by_shape": shapes,
            "matl_by_grade": grades, "elem_assign": elem_assign}


def constraint_assign(cons_by_id: dict[int, str]) -> dict:
    """Wrap ``{node_id: "DX..RW" flag string}`` into the ``/db/CONS`` body
    ``{node_id: {"ITEMS": [{"ID": 1, "CONSTRAINT": flags}]}}``."""
    return {str(i): {"ITEMS": [{"ID": 1, "CONSTRAINT": flags}]}
            for i, flags in cons_by_id.items()}


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


# ============================================ canonical hub -> MIDAS
#
# The Rhino -> Midas adapter: read a tagged ``.3dm`` into the canonical
# ``StructuralModel`` (``rhino_stm.read_structural_model``), then serialize that
# hub straight to MIDAS -- *without* routing through the lossy 2D
# ``StrutAndTieModel`` (which drops fix_z/rx/ry/rz).  Mirrors
# ``TrussBridge.midas_payloads`` / ``.to_midas`` in shape and report so the two
# exporters behave identically.


def midas_payloads(model: "StructuralModel", *, node_start: int = 1,
                   elem_start: int = 1, material_name: str = "A709-50",
                   db_name: str | None = "AISC10(US)") -> dict:
    """Serialize a :class:`~civilpy.structural.structural_model.StructuralModel`
    to MIDAS ``PUT /db/*`` assign bodies -- the **Rhino -> Midas** payload step.

    Pure (no live session): returns ``{table: assign}`` in send order
    ``UNIT, MATL, SECT, NODE, ELEM, CONS, STLD, CNLD``.  The hub's stable string
    ids are mapped to the 1-based integer ids MIDAS uses (node insertion order);
    full 6-DOF restraints become the 7-char ``CONS`` flag string via
    :meth:`Restraint.to_constraint_string`, so ``fix_z/rx/ry/rz`` reach MIDAS
    intact.  Loads are grouped into ``STLD`` cases with their nodal forces and
    moments in ``CNLD``.

    Every element gets a real ``SECT`` per distinct AISC shape label
    (:func:`hub_section_material_blocks`) and a real ``MATL`` per distinct
    grade; an element with no shape label falls back to the placeholder
    square section (still real steel material) so it always references a
    valid section.  By default each ``SECT`` references the shape directly
    out of MIDAS's own ``db_name`` database (``"AISC10(US)"``) instead of
    re-entering dimensions; pass ``db_name=None`` for built-up/historic
    shapes with no library entry.

    .. note::
       The ``CNLD`` concentrated-nodal-load layout follows the API manual but is
       **unverified against a live Civil NX release** -- check the send report's
       errors first when debugging (same caveat as the ``midas_models`` builders).
    """
    node_int: dict[str, int] = {}
    coords_by_id: dict[int, tuple] = {}
    for k, node in enumerate(model.nodes.values(), start=node_start):
        node_int[node.id] = k
        coords_by_id[k] = node.coords

    nodes = {str(i): {"X": round(x, 6), "Y": round(y, 6), "Z": round(z, 6)}
             for i, (x, y, z) in coords_by_id.items()}

    blocks = hub_section_material_blocks(model, default_grade=material_name,
                                          db_name=db_name)
    sect = dict(blocks["SECT"])
    matl = dict(blocks["MATL"])
    elem_assign = blocks["elem_assign"]

    # Elements with no gdr.shape label (or no elements at all) get the
    # placeholder square so every ELEM still references a valid SECT.
    placeholder_id = None
    if not sect or any(sid is None for sid, _ in elem_assign.values()):
        placeholder_id = max((int(k) for k in sect), default=0) + 1
        sect.update(placeholder_section_block(sect_id=placeholder_id))

    # Plate (deck) elements: a THIK per distinct thickness label and a concrete
    # MATL per distinct concrete label (steel MATL ids are already taken).
    plate_elems = [e for e in model.elements.values()
                   if e.midas_type == "PLATE"]
    thik: dict = {}
    thik_by_label: dict[str, int] = {}
    conc_by_label: dict[str, int] = {}
    next_matl = max((int(k) for k in matl), default=0)
    for e in plate_elems:
        tlabel = e.section or "DECK-8in"
        if tlabel not in thik_by_label:
            tid = len(thik_by_label) + 1
            thik_by_label[tlabel] = tid
            thik.update(thickness_block(_thickness_ft_from_label(tlabel),
                                        thik_id=tid, name=tlabel))
        clabel = e.material or "Deck-4500psi"
        if clabel not in conc_by_label:
            next_matl += 1
            conc_by_label[clabel] = next_matl
            matl.update(concrete_material_block(
                name=clabel, matl_id=next_matl,
                fc_psi=_fc_psi_from_label(clabel)))

    elements: dict[str, dict] = {}
    for j, elem in enumerate(model.elements.values(), start=elem_start):
        node_ids = [node_int[nid] for nid in elem.nodes]
        if elem.midas_type == "PLATE":
            # 3- or 4-node area element; NODE list padded to 8 ids with zeros.
            node_ids = (node_ids + [0, 0, 0, 0, 0, 0, 0, 0])[:8]
            elements[str(j)] = {
                "TYPE": "PLATE",
                "MATL": conc_by_label[elem.material or "Deck-4500psi"],
                "SECT": thik_by_label[elem.section or "DECK-8in"],
                "NODE": node_ids, "ANGLE": 0, "STYPE": 1,
            }
        else:
            sid, mid = elem_assign[elem.id]
            elements[str(j)] = {
                "TYPE": elem.midas_type, "MATL": mid,
                "SECT": sid if sid is not None else placeholder_id,
                "NODE": node_ids, "ANGLE": 0,
            }

    cons = {node_int[r.node_id]: r.to_constraint_string()
            for r in model.restraints.values()
            if any(r.flags())}

    # Static load cases (one STLD per named case) and their nodal point loads.
    # A case counts if it carries *either* nodal or distributed beam loads --
    # a distributed-load-only model (e.g. an equivalent-strip slab) otherwise
    # emits no STLD, and MIDAS then rejects the solve with "Load information
    # has not been entered for Analysis."
    cases = [c for c in model.cases()
             if model.loads_in_case(c) or model.beam_loads_in_case(c)]
    static_loads = {
        str(i): {"NAME": name, "TYPE": "USER", "DESC": ""}
        for i, name in enumerate(cases, start=1)
    }
    nodal_loads: dict[str, dict] = {}
    for load in model.loads:
        if not any((load.fx, load.fy, load.fz, load.mx, load.my, load.mz)):
            continue
        body = nodal_loads.setdefault(str(node_int[load.node_id]), {"ITEMS": []})
        body["ITEMS"].append({
            "ID": len(body["ITEMS"]) + 1, "LCNAME": load.case, "GROUP_NAME": "",
            "FX": load.fx, "FY": load.fy, "FZ": load.fz,
            "MX": load.mx, "MY": load.my, "MZ": load.mz,
        })

    payloads = {
        "UNIT": unit_block_for(model.units),
        "MATL": matl,
        "SECT": sect,
    }
    if thik:                       # THIK before ELEM: plates reference it
        payloads["THIK"] = thik
    payloads["NODE"] = nodes
    payloads["ELEM"] = elements
    # Rigid (master-slave) links -> /db/RIGD. The DOF flag string is sent as an
    # integer; MIDAS right-aligns it to the 6 DOF positions (DX DY DZ RX RY RZ),
    # so "011111" (free longitudinal slip, non-composite) rides as 11111.
    if model.rigid_links:
        rigd: dict = {}
        for link in model.rigid_links:
            m = str(node_int[link.master])
            body = rigd.setdefault(m, {"ITEMS": []})
            body["ITEMS"].append({
                "ID": len(body["ITEMS"]) + 1,
                "GROUP_NAME": "",
                "DOF": int(link.dof),
                "S_NODE": [node_int[s] for s in link.slaves],
            })
        payloads["RIGD"] = rigd
    if cons:
        payloads["CONS"] = constraint_assign(cons)
    if static_loads:
        payloads["STLD"] = static_loads
    if nodal_loads:
        payloads["CNLD"] = nodal_loads

    # Element distributed loads -> /db/BMLD (verified against a live Civil NX
    # release). The table is BMLD, not "BEAM" (which the API rejects), and the
    # uniform-load body uses CMD="BEAM", TYPE="UNILOAD", relative distances in
    # D=[d_i, d_j, 0, 0] (0..1 along the element) and magnitudes in
    # P=[w_i, w_j, 0, 0] -- not flat D1/D2/W1/W2 fields ("Wrong Field").
    if model.beam_loads:
        elem_int: dict[str, int] = {elem.id: j for j, elem in enumerate(model.elements.values(), start=elem_start)}
        beam_loads: dict[str, dict] = {}
        for bload in model.beam_loads:
            body = beam_loads.setdefault(str(elem_int[bload.element_id]), {"ITEMS": []})
            w_end = bload.w_end if bload.w_end is not None else bload.w_start
            body["ITEMS"].append({
                "ID": len(body["ITEMS"]) + 1,
                "LCNAME": bload.case,
                "GROUP_NAME": "",
                "CMD": "BEAM",
                "TYPE": "UNILOAD",
                "DIRECTION": bload.direction,
                "USE_PROJECTION": False,
                "USE_ECCEN": False,
                "D": [0.0, 1.0, 0.0, 0.0],   # full length, relative
                "P": [bload.w_start, w_end, 0.0, 0.0],
            })
        payloads["BMLD"] = beam_loads

    return payloads


def push_midas(model: "StructuralModel", midas=None, **client_kwargs) -> dict:
    """Send a hub to a live Civil NX session (built from ``~/secrets.json`` when
    ``midas`` is not given).  Pushes each :func:`midas_payloads` table in order,
    keeps going on errors, and returns ``{table: {"sent": n} | {"error": msg}}``
    -- the same report shape as ``TrussBridge.to_midas``."""
    if midas is None:
        from civilpy.structural.midas import MidasCivil
        midas = MidasCivil(**client_kwargs)
    report = {}
    for table, assign in midas_payloads(model).items():
        try:
            midas.put_db(table, assign)
            report[table] = {"sent": len(assign)}
        except Exception as exc:            # MidasApiError, transport, etc.
            report[table] = {"error": str(exc)}
    return report
