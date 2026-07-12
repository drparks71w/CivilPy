#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Substructure geometry placement: the executed design becomes the model.

:func:`substructure_from_layout` closes the loop the substructure design
notebook opens.  The superstructure hands its factored reactions to
:func:`~civilpy.structural.stm_topology.design.optimize_pier_cap` (pier and
abutment caps), :class:`~civilpy.structural.pier.MultiColumnBent` (columns),
and :class:`~civilpy.structural.abutment.RetainingWall` (wingwalls); this
module reads the dimensions **out of those design objects** — never free
parameters — and places them under the bridge in the layout's coordinate
frame, mirroring how :class:`~civilpy.structural.bridge_layout.BridgeInput`
drives the superstructure.

Placement conventions (all feet, the hub frame: X = stations along the
centerline, Y transverse with girder 1 at y = 0, Z = 0 at top of deck at
the crown):

* Each support line runs along the skew: plan direction
  ``u = (sin(skew), cos(skew))``, so a cap's local coordinate ``s`` is the
  distance *along the cap* with ``s = 0`` at girder 1 — the same frame the
  ``load_xs`` / ``column_xs`` fed to ``optimize_pier_cap`` are measured in.
* The cap top is a level plane set one minimum seat below the lowest
  bearing-stack bottom on that support line; each girder then gets a
  **beam seat** block making up its own stack height, so the seats step
  across the width following the deck cross slope.
* The cap is centered on the girder group: its length comes from the
  design (``PierCapDesign.span`` — girders plus the sweep's edge
  distance), so the start offset is recovered as
  ``(width_along_cap - span) / 2`` without re-entering the edge parameter.

Everything here is a plain geometry record; :mod:`civilpy.structural
.rhino_bim` turns it into tagged emit objects on the ``Substructure::*``
layers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from civilpy.structural.substructure import SubstructureUnit, substructure_units

Point = tuple[float, float, float]

#: Bearing-stack height (in) under a girder bottom flange — load plate plus
#: elastomeric pad, matching the ``rhino_bim`` hardware defaults
#: (1.5 in plate + 5 x 0.6 in plies).
DEFAULT_BEARING_STACK_IN = 4.5

SEAT_MIN_IN = 3.0            #: minimum beam-seat (pedestal) height
SEAT_SIDE_IN = 27.0          #: seat plan side: 21 in load plate + 3 in edges
PILE_EMBED_IN = 12.0         #: pile head embedment into a capped-pile cap


# ── geometry records ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class BeamSeat:
    """One stepped bearing seat: a square pedestal from the cap top up to
    the bottom of that girder's bearing stack."""

    girder_line: int
    center: Point            # plan center at the SEAT TOP (= pad bottom)
    side_in: float
    height_in: float


@dataclass(frozen=True)
class CapBeam:
    """A cap beam along a (possibly skewed) support line.  ``origin`` is
    the cap-top centerline point at ``s = s0``; ``axis`` the unit vector
    along the cap.  ``tie_bar_*`` carry the governing STM tie's bar
    schedule for the rebar emit (None when no design was attached)."""

    origin: Point
    axis: Point
    length_ft: float
    width_ft: float
    depth_ft: float
    tie_bar_size: int | None = None
    tie_bar_count: int | None = None

    @property
    def volume_cy(self) -> float:
        return self.length_ft * self.width_ft * self.depth_ft / 27.0


@dataclass(frozen=True)
class ColumnGeometry:
    """One pier column, cap soffit to footing top.  Circular when
    ``diameter_in`` is set, else rectangular ``b_in x h_in`` (``b`` along
    the cap axis)."""

    center: tuple[float, float]      # plan (x, y)
    z_top: float
    z_bot: float
    diameter_in: float | None = None
    b_in: float | None = None
    h_in: float | None = None
    bars_area_in2: float = 0.0       # longitudinal steel from the design

    @property
    def height_ft(self) -> float:
        return self.z_top - self.z_bot

    @property
    def volume_cy(self) -> float:
        if self.diameter_in is not None:
            area_sf = math.pi * (self.diameter_in / 12.0) ** 2 / 4.0
        else:
            area_sf = (self.b_in / 12.0) * (self.h_in / 12.0)
        return area_sf * self.height_ft / 27.0


@dataclass(frozen=True)
class FootingGeometry:
    """Spread/pile-cap footing under one column, aligned with the cap
    axes (``length_ft`` along the cap)."""

    center: tuple[float, float]
    z_top: float
    length_ft: float
    width_ft: float
    thickness_ft: float
    axis: Point

    @property
    def volume_cy(self) -> float:
        return self.length_ft * self.width_ft * self.thickness_ft / 27.0


@dataclass(frozen=True)
class PileGeometry:
    """One driven HP pile.  ``head`` is the butt at the embedment plane
    inside the cap; the pay length runs below the cutoff."""

    head: Point
    shape: str
    length_ft: float


@dataclass(frozen=True)
class WallPanel:
    """A rectangular wall run (backwall or wingwall stem/footing).
    ``origin`` is the bottom-centerline start point; the panel extends
    ``length_ft`` along ``axis``, ``thickness_ft`` centered on the line,
    ``height_ft`` up."""

    origin: Point
    axis: Point
    length_ft: float
    thickness_ft: float
    height_ft: float

    @property
    def volume_cy(self) -> float:
        return self.length_ft * self.thickness_ft * self.height_ft / 27.0


@dataclass(frozen=True)
class PierGeometry:
    """One pier: a multi-column bent carries ``columns`` (+ optional
    ``footings``); a capped-pile bent carries ``piles`` instead."""

    unit: SubstructureUnit
    cap: CapBeam
    seats: tuple[BeamSeat, ...]
    columns: tuple[ColumnGeometry, ...] = ()
    footings: tuple[FootingGeometry, ...] = ()
    piles: tuple[PileGeometry, ...] = ()


@dataclass(frozen=True)
class AbutmentGeometry:
    """One abutment.  ``kind`` is ``"seat"`` (bearings on a stepped-seat
    cap), ``"semi-integral"`` (seat cap plus an end diaphragm that moves
    with the superstructure), or ``"integral"`` (a full-height end
    diaphragm on a single pile row — no bearings, so ``seats`` is
    empty)."""

    unit: SubstructureUnit
    cap: CapBeam
    seats: tuple[BeamSeat, ...]
    piles: tuple[PileGeometry, ...]
    backwall: WallPanel | None = None
    wingwalls: tuple[WallPanel, ...] = ()
    kind: str = "seat"
    diaphragm: WallPanel | None = None


@dataclass(frozen=True)
class SubstructureLayout:
    """Every substructure unit of one bridge, placed under its layout."""

    layout: object                   # BridgeLayout
    abutments: tuple[AbutmentGeometry, ...]
    piers: tuple[PierGeometry, ...]

    @property
    def units(self) -> tuple:
        return tuple(sorted((*self.abutments, *self.piers),
                            key=lambda g: g.unit.index))


# ── caller-supplied specs (only what no design object carries) ────────────

@dataclass(frozen=True)
class FootingSpec:
    """Per-column footing plan dims (a geotech deliverable — no civilpy
    footing designer exists yet, so these stay explicit inputs)."""

    length_ft: float
    width_ft: float
    thickness_ft: float


@dataclass(frozen=True)
class AbutmentSpec:
    """Capped-pile abutment parameters that live outside the cap design:
    the pile layout the cap STM was solved on (``pile_xs_ft`` in the same
    girder-1-origin frame as its ``column_xs``), the driven length from
    the geotech recommendation, and the wingwall design.

    ``wingwall`` is the executed :class:`~civilpy.structural.abutment
    .RetainingWall` whose stem/footing dimensions the wingwall panels are
    read from; ``wingwall_length_ft`` its run along the roadway."""

    pile_xs_ft: tuple[float, ...]
    pile_shape: str = "HP10X42"
    pile_length_ft: float = 40.0
    backwall_thickness_in: float = 18.0
    wingwall: object | None = None       # RetainingWall
    wingwall_length_ft: float = 0.0


# ── placement ─────────────────────────────────────────────────────────────

def _support_frame(layout, station_ft: float):
    """Plan frame of a support line: point-at-s and the unit axis."""
    skew = math.radians(layout.inputs.skew_deg)
    u = (math.sin(skew), math.cos(skew), 0.0)

    def at(s: float, z: float) -> Point:
        return (station_ft + s * u[0], s * u[1], z)

    return at, u


def _seat_plane(layout, station_index: int, *, bearing_stack_in: float,
                seat_min_in: float, seat_side_in: float):
    """Cap-top elevation and the stepped seats for one support line."""
    pads = [(bp.line_no, bp.location) for bp in layout.bearings
            if bp.station_index == station_index]
    if not pads:
        raise ValueError(f"no bearings at support index {station_index}")
    stack_ft = bearing_stack_in / 12.0
    bottoms = {line: (loc[0], loc[1], loc[2] - stack_ft)
               for line, loc in pads}
    cap_top = min(z for _, _, z in bottoms.values()) - seat_min_in / 12.0
    seats = tuple(BeamSeat(girder_line=line, center=pt, side_in=seat_side_in,
                           height_in=(pt[2] - cap_top) * 12.0)
                  for line, pt in sorted(bottoms.items()))
    return cap_top, seats


def _governing_tie(cap_design):
    """Bar schedule of the highest-force tie in a solved cap design."""
    report = cap_design.report
    if report is None or not report.ties:
        return None, None
    t = max(report.ties, key=lambda t: t.force)
    return t.bar_size, t.bar_count


def _cap_from_design(layout, station_ft: float, cap_top: float, cap_design):
    """Center the designed cap on the girder group along the support
    line and hang its depth from the seat plane."""
    if cap_design.optimal is None:
        raise ValueError("cap design has no feasible depth; nothing to place")
    inp = layout.inputs
    cos_skew = math.cos(math.radians(inp.skew_deg))
    width_along_cap = (inp.girder_count - 1) * inp.girder_spacing_ft / cos_skew
    s0 = (width_along_cap - cap_design.span) / 2.0
    at, u = _support_frame(layout, station_ft)
    bar_size, bar_count = _governing_tie(cap_design)
    return CapBeam(origin=at(s0, cap_top), axis=u,
                   length_ft=cap_design.span,
                   width_ft=cap_design.thickness,
                   depth_ft=cap_design.optimal.depth,
                   tie_bar_size=bar_size, tie_bar_count=bar_count), s0


def _piles_along_cap(at, z_cap_bot: float, xs, shape: str, length_ft: float,
                     embed_in: float) -> tuple[PileGeometry, ...]:
    """Driven piles at ``xs`` (girder-frame ft along the cap), heads
    embedded ``embed_in`` into the cap."""
    return tuple(
        PileGeometry(head=at(s, z_cap_bot + embed_in / 12.0),
                     shape=shape, length_ft=length_ft)
        for s in xs)


def pier_geometry(layout, unit: SubstructureUnit, cap_design, bent, *,
                  footing: FootingSpec | None = None,
                  bearing_stack_in: float = DEFAULT_BEARING_STACK_IN,
                  seat_min_in: float = SEAT_MIN_IN,
                  seat_side_in: float = SEAT_SIDE_IN) -> PierGeometry:
    """Place one pier from its executed designs: the cap from
    ``cap_design`` (:class:`~civilpy.structural.stm_topology.design
    .PierCapDesign`), the columns from ``bent``
    (:class:`~civilpy.structural.pier.MultiColumnBent`, whose
    ``cap.column_positions`` are inches from the left end of the cap)."""
    cap_top, seats = _seat_plane(layout, unit.index,
                                 bearing_stack_in=bearing_stack_in,
                                 seat_min_in=seat_min_in,
                                 seat_side_in=seat_side_in)
    cap, s0 = _cap_from_design(layout, unit.station_ft, cap_top, cap_design)
    at, _ = _support_frame(layout, unit.station_ft)
    z_cap_bot = cap_top - cap.depth_ft

    columns, footings = [], []
    for pos_in, col in zip(bent.cap.column_positions, bent.columns):
        s = s0 + pos_in / 12.0
        x, y, _ = at(s, z_cap_bot)
        z_bot = z_cap_bot - col.height / 12.0
        columns.append(ColumnGeometry(
            center=(x, y), z_top=z_cap_bot, z_bot=z_bot,
            diameter_in=col.diameter, b_in=col.b, h_in=col.h,
            bars_area_in2=sum(l.area for l in col.layers)))
        if footing is not None:
            footings.append(FootingGeometry(
                center=(x, y), z_top=z_bot, length_ft=footing.length_ft,
                width_ft=footing.width_ft,
                thickness_ft=footing.thickness_ft, axis=cap.axis))
    return PierGeometry(unit=unit, cap=cap, seats=seats,
                        columns=tuple(columns), footings=tuple(footings))


def pile_bent_geometry(layout, unit: SubstructureUnit, cap_design,
                       pile_xs_ft, *, pile_shape: str = "HP12X53",
                       pile_length_ft: float = 40.0,
                       bearing_stack_in: float = DEFAULT_BEARING_STACK_IN,
                       seat_min_in: float = SEAT_MIN_IN,
                       seat_side_in: float = SEAT_SIDE_IN,
                       pile_embed_in: float = PILE_EMBED_IN
                       ) -> PierGeometry:
    """Place one capped-pile pier (pile bent): the cap from ``cap_design``
    (an :func:`optimize_pier_cap` run with the piles as supports, same as
    the abutment cap) directly on driven piles at ``pile_xs_ft`` — the
    CPP-1-08 pattern generalized off the continuous-slab sheet, whose
    ``HP12X53`` default the pile shape keeps
    (:mod:`civilpy.structural.odot.capped_pile_pier` carries the SCD's
    own limits for the standard-drawing case)."""
    cap_top, seats = _seat_plane(layout, unit.index,
                                 bearing_stack_in=bearing_stack_in,
                                 seat_min_in=seat_min_in,
                                 seat_side_in=seat_side_in)
    cap, s0 = _cap_from_design(layout, unit.station_ft, cap_top, cap_design)
    at, _ = _support_frame(layout, unit.station_ft)
    piles = _piles_along_cap(at, cap_top - cap.depth_ft, pile_xs_ft,
                             pile_shape, pile_length_ft, pile_embed_in)
    return PierGeometry(unit=unit, cap=cap, seats=seats, piles=piles)


def abutment_geometry(layout, unit: SubstructureUnit, cap_design,
                      spec: AbutmentSpec, *,
                      bearing_stack_in: float = DEFAULT_BEARING_STACK_IN,
                      seat_min_in: float = SEAT_MIN_IN,
                      seat_side_in: float = SEAT_SIDE_IN,
                      pile_embed_in: float = PILE_EMBED_IN
                      ) -> AbutmentGeometry:
    """Place one capped-pile abutment: the cap from its ``cap_design``
    (an :func:`optimize_pier_cap` run with the piles as supports), the
    piles from ``spec``, the backwall from the cap top to the low deck
    edge, and wingwall stem+footing panels from the executed
    :class:`~civilpy.structural.abutment.RetainingWall`."""
    cap_top, seats = _seat_plane(layout, unit.index,
                                 bearing_stack_in=bearing_stack_in,
                                 seat_min_in=seat_min_in,
                                 seat_side_in=seat_side_in)
    cap, s0 = _cap_from_design(layout, unit.station_ft, cap_top, cap_design)
    at, u = _support_frame(layout, unit.station_ft)
    z_cap_bot = cap_top - cap.depth_ft

    piles = _piles_along_cap(at, z_cap_bot, spec.pile_xs_ft,
                             spec.pile_shape, spec.pile_length_ft,
                             pile_embed_in)

    # backwall on the approach side of the cap, up to the low deck edge
    # (crown-following top is a later refinement)
    inp = layout.inputs
    back = -1.0 if unit.index == 0 else 1.0     # away from the spans
    y_edges = (-inp.overhang_ft,
               (inp.girder_count - 1) * inp.girder_spacing_ft
               + inp.overhang_ft)
    z_bw_top = min(layout.deck_top_z(y) for y in y_edges)
    bw_t = spec.backwall_thickness_in / 12.0
    bw_shift = back * (cap.width_ft - bw_t) / 2.0
    ox, oy, _ = cap.origin
    backwall = WallPanel(
        origin=(ox + bw_shift, oy, cap_top), axis=u,
        length_ft=cap.length_ft, thickness_ft=bw_t,
        height_ft=z_bw_top - cap_top)

    wingwalls: list[WallPanel] = []
    if spec.wingwall is not None and spec.wingwall_length_ft > 0.0:
        wall = spec.wingwall
        w_axis = (back, 0.0, 0.0)               # along the roadway
        z_stem_top = z_bw_top
        z_stem_bot = z_stem_top - wall.stem_height
        for s_end in (s0, s0 + cap.length_ft):
            x, y, _ = at(s_end, 0.0)
            wingwalls.append(WallPanel(              # stem
                origin=(x, y, z_stem_bot), axis=w_axis,
                length_ft=spec.wingwall_length_ft,
                thickness_ft=wall.stem_thickness,
                height_ft=wall.stem_height))
            wingwalls.append(WallPanel(              # footing
                origin=(x, y, z_stem_bot - wall.footing_thickness),
                axis=w_axis, length_ft=spec.wingwall_length_ft,
                thickness_ft=wall.base_width,
                height_ft=wall.footing_thickness))

    return AbutmentGeometry(unit=unit, cap=cap, seats=seats, piles=piles,
                            backwall=backwall, wingwalls=tuple(wingwalls))


# ── per-unit type specs (mix substructure types on one bridge) ────────────

@dataclass(frozen=True)
class BentPierSpec:
    """Multi-column bent: cap from ``cap_design``, columns from ``bent``
    (see :func:`pier_geometry`)."""

    cap_design: object
    bent: object
    footing: FootingSpec | None = None

    def build(self, layout, unit, **frame_kw) -> PierGeometry:
        return pier_geometry(layout, unit, self.cap_design, self.bent,
                             footing=self.footing, **frame_kw)


@dataclass(frozen=True)
class PileBentSpec:
    """Capped-pile pier (see :func:`pile_bent_geometry`)."""

    cap_design: object
    pile_xs_ft: tuple[float, ...]
    pile_shape: str = "HP12X53"        # CPP-1-08 default
    pile_length_ft: float = 40.0

    def build(self, layout, unit, **frame_kw) -> PierGeometry:
        return pile_bent_geometry(layout, unit, self.cap_design,
                                  self.pile_xs_ft,
                                  pile_shape=self.pile_shape,
                                  pile_length_ft=self.pile_length_ft,
                                  **frame_kw)


@dataclass(frozen=True)
class SeatAbutmentSpec:
    """Conventional seat abutment: the Phase-4 :class:`AbutmentSpec`
    plus its cap design, buildable per unit."""

    cap_design: object
    spec: AbutmentSpec

    def build(self, layout, unit, **frame_kw) -> AbutmentGeometry:
        return abutment_geometry(layout, unit, self.cap_design, self.spec,
                                 **frame_kw)


def assemble_substructure(layout, assignments: dict, *,
                          bearing_stack_in: float = DEFAULT_BEARING_STACK_IN,
                          seat_min_in: float = SEAT_MIN_IN,
                          seat_side_in: float = SEAT_SIDE_IN
                          ) -> SubstructureLayout:
    """Place a substructure that mixes unit types.

    ``assignments`` maps a support-line index (0 at the start abutment)
    to its typed spec (:class:`BentPierSpec`, :class:`PileBentSpec`,
    :class:`SeatAbutmentSpec`, ...); the string keys ``"pier"`` and
    ``"abutment"`` supply defaults for unassigned units of that role."""
    frame_kw = dict(bearing_stack_in=bearing_stack_in,
                    seat_min_in=seat_min_in, seat_side_in=seat_side_in)
    abutments, piers = [], []
    for unit in substructure_units(layout):
        role = ("abutment" if unit.name.startswith("Abutment") else "pier")
        spec = assignments.get(unit.index, assignments.get(role))
        if spec is None:
            raise ValueError(f"no spec assigned for {unit.name} "
                             f"(index {unit.index})")
        geom = spec.build(layout, unit, **frame_kw)
        (abutments if isinstance(geom, AbutmentGeometry)
         else piers).append(geom)
    return SubstructureLayout(layout=layout, abutments=tuple(abutments),
                              piers=tuple(piers))


def substructure_from_layout(layout, *, pier_cap, pier_bent,
                             abutment_cap, abutment: AbutmentSpec,
                             footing: FootingSpec | None = None,
                             bearing_stack_in: float =
                             DEFAULT_BEARING_STACK_IN,
                             seat_min_in: float = SEAT_MIN_IN,
                             seat_side_in: float = SEAT_SIDE_IN
                             ) -> SubstructureLayout:
    """Place the full substructure under ``layout`` from the executed
    designs: every pier gets ``pier_cap`` + ``pier_bent`` and every
    abutment gets ``abutment_cap`` + ``abutment`` (one design reused
    across identical units, the way the notebook designs them — pass the
    per-unit builders directly for units that differ)."""
    abutments, piers = [], []
    for unit in substructure_units(layout):
        if unit.name.startswith("Abutment"):
            abutments.append(abutment_geometry(
                layout, unit, abutment_cap, abutment,
                bearing_stack_in=bearing_stack_in,
                seat_min_in=seat_min_in, seat_side_in=seat_side_in))
        else:
            piers.append(pier_geometry(
                layout, unit, pier_cap, pier_bent, footing=footing,
                bearing_stack_in=bearing_stack_in,
                seat_min_in=seat_min_in, seat_side_in=seat_side_in))
    return SubstructureLayout(layout=layout, abutments=tuple(abutments),
                              piers=tuple(piers))
