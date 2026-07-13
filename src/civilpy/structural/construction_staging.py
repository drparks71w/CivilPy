#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Staged / phased-construction helpers for the refined-grillage bridge model.

Maintenance-of-traffic (MOT) staged construction, deck replacement, and
widening all share the same moves this module supports on top of
:func:`civilpy.structural.bridge_layout.grillage_model_from_layout`:

* **shift traffic onto a subset of the girders** -- during a phase, the open
  lanes are squeezed over the girder lines that are carrying traffic
  (:func:`lanes_over_girders`), and the live/lane load is applied there;
* **place an anchored portable concrete barrier** as a temporary dead load at
  the work-zone edge (:data:`PORTABLE_BARRIERS`, :func:`add_barrier_dead_load`);
* **analyze a construction phase in isolation** -- a stage-1 (or stage-2)
  structure carrying only the girders built so far, via the
  ``girder_subset`` phase model, so a **closure pour** can be checked: the wet
  concrete of the closure strip (:func:`closure_pour_line_load_plf`) loads each
  half before it cures, and the differential deflection at the joint governs
  the pour geometry/timing.

Everything is applied as named load *cases* (``"MOT-LANE"``, ``"PCB"``,
``"CLOSURE"``, ...) on the hub, so the phases go to MIDAS through the ordinary
:func:`civilpy.structural.midas_models.midas_payloads` path and can be combined
or run as construction stages there.  Loads are placed on the girders by the
transverse **lever rule** (the standard line-girder distribution) -- a
preliminary-level idealization; the deck plates still provide the real
transverse distribution in the solved grillage.

Units: transverse offsets and widths in feet (layout ``Y``, girder 1 at
``Y = 0``); barrier/line weights in lb/ft (plf); beam loads on the hub in
kip/ft, negative ``GZ`` = downward (matching the DC/DW convention).
"""

from __future__ import annotations

from dataclasses import dataclass

from civilpy.structural.bridge_layout import CONCRETE_UNIT_WT_KCF

#: HL-93 design lane load (AASHTO LRFD 3.6.1.2.4), kip/ft per 10 ft lane.
LANE_LOAD_KLF = 0.64

#: AASHTO LRFD 3.6.1.1.2 multiple-presence factor m by number of loaded lanes.
MULTIPLE_PRESENCE = {1: 1.20, 2: 1.00, 3: 0.85}


def multiple_presence(n_lanes: int) -> float:
    """Multiple-presence factor ``m`` for ``n_lanes`` loaded design lanes."""
    return MULTIPLE_PRESENCE.get(n_lanes, 0.65 if n_lanes >= 4 else 1.20)


@dataclass(frozen=True)
class PortableBarrier:
    """A temporary/portable concrete barrier used for work-zone separation.

    ``weight_plf`` is the self-weight per foot of run (lb/ft); ``anchored``
    notes whether it is pinned/bolted to the deck (which changes overturning
    and the deck anchor design, not the gravity load this module applies).
    Values are nominal catalog figures -- confirm against the governing ODOT
    SCD / shop drawing for a specific product.
    """

    designation: str
    height_in: float
    weight_plf: float
    anchored: bool = True
    note: str = ""


#: Nominal portable-barrier catalog (confirm weights against the ODOT SCD).
PORTABLE_BARRIERS: dict[str, PortableBarrier] = {
    "PCB-32": PortableBarrier("PCB-32", 32.0, 470.0, True,
                              "32 in F-shape portable concrete barrier, anchored"),
    "PCB-42": PortableBarrier("PCB-42", 42.0, 650.0, True,
                              "42 in tall single-slope portable barrier, anchored"),
    "JERSEY-PORTABLE": PortableBarrier("JERSEY-PORTABLE", 32.0, 400.0, False,
                                       "unanchored precast Jersey segments"),
}


def portable_barrier(designation: str = "PCB-32") -> PortableBarrier:
    """Look up a :class:`PortableBarrier` by designation."""
    try:
        return PORTABLE_BARRIERS[designation]
    except KeyError:
        raise ValueError(
            f"unknown portable barrier {designation!r}; choose from "
            f"{sorted(PORTABLE_BARRIERS)}") from None


# ── girder helpers ──────────────────────────────────────────────────────────

def girder_elements(model, line_no: int) -> list:
    """The girder beam elements of one girder line (1-based ``line_no``)."""
    return [e for e in model.elements.values()
            if e.role == "girder" and e.metadata.get("gdr.line") == str(line_no)]


def _girder_offsets(layout) -> list[float]:
    """Transverse offset (ft, ``Y``) of each girder line, girder 1 at 0."""
    s = layout.inputs.girder_spacing_ft
    return [g * s for g in range(layout.inputs.girder_count)]


def add_line_load_at_offset(model, layout, offset_ft: float, w_plf: float, *,
                            case: str, downward: bool = True) -> dict[int, float]:
    """Apply a longitudinal line load (``w_plf`` lb/ft) at a transverse
    ``offset_ft`` to the girders it sits between, by the lever rule.

    A load between girders *k* and *k+1* splits to each in inverse proportion
    to its distance; a load outboard of a fascia girder goes fully to it (an
    overhang load's cantilever moment is not added here -- preliminary).
    Returns ``{girder_line_no: applied_klf}`` (negative = downward), and adds
    the loads to every element of those girder lines in load case ``case``.
    """
    ys = _girder_offsets(layout)
    n = len(ys)
    w_klf = w_plf / 1000.0
    if downward:
        w_klf = -abs(w_klf)
    if offset_ft <= ys[0]:
        shares = {0: 1.0}
    elif offset_ft >= ys[-1]:
        shares = {n - 1: 1.0}
    else:
        k = max(i for i in range(n) if ys[i] <= offset_ft)
        k = min(k, n - 2)
        f = (offset_ft - ys[k]) / (ys[k + 1] - ys[k])
        shares = {k: 1.0 - f, k + 1: f}
    applied: dict[int, float] = {}
    for g, share in shares.items():
        if abs(share) < 1e-9:               # a load landing on a girder line
            continue                        # gives the neighbour a 0 share
        elems = girder_elements(model, g + 1)
        if not elems:                       # girder not in this phase's subset
            continue
        for e in elems:
            model.add_beam_load(e.id, w_klf * share, case=case)
        applied[g + 1] = w_klf * share
    return applied


# ── maintenance of traffic: lanes over a subset of girders ──────────────────

def lanes_over_girders(layout, girder_lines: list[int], *,
                       n_lanes: int | None = None,
                       lane_width_ft: float = 12.0) -> list[float]:
    """Transverse center offsets for design lanes shifted over ``girder_lines``.

    During a construction phase the open roadway is carried on a subset of the
    girders; this centers ``n_lanes`` design lanes over the span of those
    girder lines (1-based).  With ``n_lanes`` omitted, as many 12 ft lanes as
    fit between the outermost of ``girder_lines`` are used (at least one).
    Returns the lane center offsets (ft, ``Y``) -- feed each to
    :func:`add_lane_load` (static lane load) or use them as MIDAS traffic-line
    lane reference positions for a moving-load run.
    """
    ys = [(g - 1) * layout.inputs.girder_spacing_ft for g in girder_lines]
    lo, hi = min(ys), max(ys)
    if n_lanes is None:
        n_lanes = max(1, int((hi - lo) // lane_width_ft) or 1)
    span = n_lanes * lane_width_ft
    start = (lo + hi) / 2.0 - span / 2.0 + lane_width_ft / 2.0
    return [start + i * lane_width_ft for i in range(n_lanes)]


def add_lane_load(model, layout, lane_centers: list[float], *,
                  case: str = "MOT-LANE",
                  lane_load_klf: float = LANE_LOAD_KLF) -> dict[int, float]:
    """Apply the HL-93 static lane load at each lane center (lever rule).

    The AASHTO multiple-presence factor is **not** applied here (one or two
    staged lanes are usually ``m = 1.0``/``1.0``); scale ``lane_load_klf`` if a
    different ``m`` governs.  Returns the per-girder total applied klf.
    """
    total: dict[int, float] = {}
    for y in lane_centers:
        for line, w in add_line_load_at_offset(
                model, layout, y, lane_load_klf * 1000.0, case=case).items():
            total[line] = total.get(line, 0.0) + w
    return total


# ── roadway: centerline + lane edge lines from a lane-width variable ────────

@dataclass(frozen=True)
class RoadwayLanes:
    """The traffic-lane layout of the roadway, in the layout transverse frame
    (``Y``, ft; girder 1 at ``Y = 0``).

    Built from a **lane-width variable** and the curb-to-curb roadway width:
    ``cl_offset`` is the roadway centerline, ``curb_lines`` the two roadway
    edges, ``lane_edges`` every design-lane boundary (``n_lanes + 1`` of them),
    and ``lane_centers`` the design-lane centers.  These are the lines a Rhino
    grip interface edits (drag the CL / lane edges) and the reference positions
    handed to MIDAS for the lane-load live load.  ``n_lanes`` follows AASHTO
    LRFD 3.6.1.1.1 (``int(roadway_width / 12)``).
    """

    roadway_width_ft: float
    lane_width_ft: float
    cl_offset: float
    n_lanes: int
    curb_lines: tuple[float, float]
    lane_edges: tuple[float, ...]
    lane_centers: tuple[float, ...]


def design_lanes(layout, *, roadway_width_ft: float, lane_width_ft: float = 12.0,
                 cl_offset: float | None = None,
                 n_lanes: int | None = None) -> RoadwayLanes:
    """Lay out design traffic lanes across the roadway from the lane width.

    ``cl_offset`` defaults to the girder-group center; ``n_lanes`` defaults to
    ``int(roadway_width_ft / 12)`` (AASHTO number of design lanes).  The
    ``n_lanes`` lanes of width ``lane_width_ft`` are centered on the roadway
    centerline.  Returns a :class:`RoadwayLanes`.
    """
    inp = layout.inputs
    if cl_offset is None:
        cl_offset = (inp.girder_count - 1) * inp.girder_spacing_ft / 2.0
    if n_lanes is None:
        n_lanes = max(1, int(roadway_width_ft // 12.0))
    block = n_lanes * lane_width_ft
    left = cl_offset - block / 2.0
    edges = tuple(round(left + i * lane_width_ft, 4) for i in range(n_lanes + 1))
    centers = tuple(round(left + (i + 0.5) * lane_width_ft, 4)
                    for i in range(n_lanes))
    curbs = (cl_offset - roadway_width_ft / 2.0,
             cl_offset + roadway_width_ft / 2.0)
    return RoadwayLanes(roadway_width_ft, lane_width_ft, cl_offset, n_lanes,
                        curbs, edges, centers)


def add_design_lane_load(model, layout, lanes: RoadwayLanes, *,
                         n_loaded: int | None = None, case: str = "LL-LANE",
                         lane_load_klf: float = LANE_LOAD_KLF,
                         apply_multiple_presence: bool = True) -> dict[int, float]:
    """Apply the HL-93 lane load to ``n_loaded`` of the design lanes (default:
    all), with the AASHTO multiple-presence factor.

    The lane load is placed at each loaded lane's center (lever rule to the
    girders beneath) -- the distributed **lane-load** portion of HL-93, the
    piece handed to MIDAS from the Rhino-defined lanes.  Returns per-girder klf.
    The design **truck/tandem** and its longitudinal positioning for the
    governing per-support reaction are a MIDAS moving-load run (see the notebook
    note) -- this static lane load is the preliminary live-load reaction.
    """
    n = lanes.n_lanes if n_loaded is None else min(n_loaded, lanes.n_lanes)
    m = multiple_presence(n) if apply_multiple_presence else 1.0
    total: dict[int, float] = {}
    for y in lanes.lane_centers[:n]:
        for line, w in add_line_load_at_offset(
                model, layout, y, lane_load_klf * m * 1000.0, case=case).items():
            total[line] = total.get(line, 0.0) + w
    return total


# ── temporary dead load: anchored portable barrier ──────────────────────────

def add_barrier_dead_load(model, layout, offset_ft: float, *,
                          designation: str = "PCB-32",
                          case: str = "PCB") -> dict[int, float]:
    """Place an anchored portable concrete barrier as a dead load at
    ``offset_ft`` (lever rule to the straddling girders).  Returns the
    per-girder applied klf."""
    b = portable_barrier(designation)
    return add_line_load_at_offset(model, layout, offset_ft, b.weight_plf,
                                   case=case)


# ── closure pour ────────────────────────────────────────────────────────────

def closure_pour_line_load_plf(layout, *, closure_width_ft: float = 2.0,
                               wet_factor: float = 1.0) -> float:
    """Self-weight (lb/ft of bridge length) of the wet closure-pour strip.

    A staged deck is cast in phases with a longitudinal gap left between them;
    the **closure pour** fills that ``closure_width_ft`` strip last.  Before it
    cures it is dead weight the already-built phases carry -- half to each side.
    ``wet_factor`` scales for over-pour / screed surcharge.  Uses the deck
    thickness and the concrete unit weight
    (:data:`~civilpy.structural.bridge_layout.CONCRETE_UNIT_WT_KCF`).
    """
    t_ft = layout.deck.thickness_in / 12.0
    return CONCRETE_UNIT_WT_KCF * 1000.0 * t_ft * closure_width_ft * wet_factor


def add_closure_pour_load(model, layout, edge_girder_line: int, *,
                          closure_width_ft: float = 2.0,
                          share: float = 0.5, case: str = "CLOSURE",
                          wet_factor: float = 1.0) -> float:
    """Apply the wet closure-pour weight carried by one phase to that phase's
    closure-edge girder line.

    ``share`` is the fraction of the strip weight this phase carries (0.5 when
    the joint is centered between the two phases).  Applied to every element of
    ``edge_girder_line`` in case ``case``.  Returns the applied line load
    (kip/ft, negative = downward).  The load sits on the deck cantilever
    outboard of the edge girder, so in a refined grillage it also induces a
    small torsion the plates carry -- for the girder demand this vertical line
    load is the preliminary quantity.
    """
    w_plf = closure_pour_line_load_plf(
        layout, closure_width_ft=closure_width_ft, wet_factor=wet_factor) * share
    w_klf = -abs(w_plf) / 1000.0
    elems = girder_elements(model, edge_girder_line)
    if not elems:
        raise ValueError(
            f"girder line {edge_girder_line} is not in this phase model")
    for e in elems:
        model.add_beam_load(e.id, w_klf, case=case)
    return w_klf
