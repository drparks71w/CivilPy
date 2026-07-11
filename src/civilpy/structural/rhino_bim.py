#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""BrIM emit layer for the parametric steel-girder bridge.

Turns a :class:`~civilpy.structural.bridge_layout.BridgeLayout` into
*tagged, transport-neutral* geometry records — the full "source of truth"
model the Rhino document carries: girder solids with true k-fillets, the
crowned deck solid, haunches, welded shear studs, both deck rebar mats,
parapets, bearings, and load plates, each stamped with its
:mod:`civilpy.structural.bim` attribute set (``bim.type``/``bim.id``,
``bim.scd``/``bim.scd_year`` where the part is a standard detail, a
``pay.*`` pay-item block, and a ``mat.*`` material block).

The point of the neutral record (same architecture as
:mod:`~civilpy.structural.rhino_slab`) is that the engineering content is
described exactly once; a backend only decides *how* to draw a prism or a
cylinder and how to stamp a user string, never where a stud goes.  Known
backends:

* ``Notebooks/Rhino Components/draw_bim_emit.py`` — live-document driver
  (run inside Rhino 8, e.g. through an MCP agent) that consumes
  :func:`emit_to_json`.
* The ``odot_bridge_generator_ghpython.py`` Grasshopper component shares
  the same :func:`~civilpy.structural.bridge_layout.layout_bridge` layout
  for its preview geometry.

Coordinates are **feet** (the hub convention): X = stations along the
layout centerline, Y = transverse (girder 1 at y = 0), Z = 0 at the top
of deck **at the crown**.  Section dimensions in the tags stay in inches
(``_in`` suffixes).

Geometry record kinds
---------------------
``prism``
    A closed planar loop (``points``, unrepeated) extruded along
    ``vector``.  Every solid here is a prism: the bridge is prismatic
    along its length, so the deck (skew-cut ends), girders (square-cut
    ends), haunches, parapets, bearings, and plates all emit this way.
``polyline``
    Open polyline through ``points`` (rebar; girder centerlines).
``cylinder``
    ``points = (base, tip)`` plus ``radius_ft`` (shear studs).
``point``
    A marker.  The ``bim.type = bridge`` marker carries the bridge-wide
    parameters, because standalone ``rhino3dm`` cannot write or read the
    RhinoDoc string table (same G4 contract note as ``rhino_slab``); a
    live-document backend *additionally* mirrors them into
    ``doc.Strings`` for the ``rhino_gdr`` reader.

The ``gdr.*`` analysis contract is preserved untouched: girder
centerlines and bearing points still carry their ``gdr.*`` tags (plus a
``bim.id`` back-reference), so a document drawn from this emit remains
readable by :mod:`civilpy.structural.rhino_gdr` and the MIDAS pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural import bim
from civilpy.structural.bridge_layout import (
    BridgeInput,
    BridgeLayout,
    deck_rebar_segments,
    layout_bridge,
    railing_by_scd,
    _girder_weight_plf,
)
from civilpy.structural.rhino_layers import (
    LAYER_BARRIERS,
    LAYER_BEARINGS,
    LAYER_BRIDGE_DECK,
    LAYER_GIRDERS,
    LAYER_HAUNCHES,
    LAYER_LOAD_PLATES,
    LAYER_REBAR,
    LAYER_SHEAR_STUDS,
    LAYER_SUB_BACKWALLS,
    LAYER_SUB_CAPS,
    LAYER_SUB_COLUMNS,
    LAYER_SUB_FOOTINGS,
    LAYER_SUB_PILES,
    LAYER_SUB_REBAR,
    LAYER_SUB_SEATS,
    LAYER_SUB_WINGWALLS,
)

Point = tuple[float, float, float]

STEEL_PCF = 490.0
CONCRETE_FC_PSI = 4500.0

# ── as-detailed hardware defaults (preliminary; final design sizes these) ──

STUD_DIA_IN = 0.875          #: welded stud diameter, 7/8 in typical
STUD_LENGTH_IN = 6.0         #: stud length — embeds ~4 in into an 8.5 in deck
STUD_PITCH_IN = 24.0         #: longitudinal row pitch (preliminary)
STUDS_PER_ROW = 3            #: studs across the top flange per row
STUD_GAUGE_IN = 3.0          #: transverse c/c between studs in a row

BEARING_SIDE_IN = 20.0       #: square elastomeric pad plan side
BEARING_PLIES = 5
BEARING_PLY_IN = 0.6         #: internal elastomer ply thickness
PLATE_SIDE_IN = 21.0         #: load plate plan side
PLATE_THICKNESS_IN = 1.5

# ── SBR-1-20 standard-railing bar schedule (sheets 1 & 5 of the SCD) ──────
# Verticals are epoxy-coated steel #6 (Y601 traffic face / Y602 back face)
# at 12 in maximum spacing, embedded ``deck t - 1.5 in`` (9 in minimum)
# with 12 in horizontal legs lapping the bottom transverse deck steel.
# Horizontals are #4 GFRP: 5 bars per face at 7 in plus a 2-X401 pair at
# the top (C&MS 705.28).

SBR1_VERT_SIZE = 6
SBR1_VERT_SPACING_IN = 12.0
SBR1_COVER_IN = 2.0
SBR1_LEG_IN = 12.0            #: horizontal deck-lap leg of Y601/Y602
SBR1_EMBED_REDUCTION_IN = 1.5  #: embedment = deck thickness - this
SBR1_MIN_EMBED_IN = 9.0
SBR1_FACE_BAR_SIZE = 4
SBR1_FACE_BARS_PER_FACE = 5
SBR1_FACE_BAR_START_IN = 6.0
SBR1_FACE_BAR_SPACING_IN = 7.0
SBR1_TOP_BAR_DROP_IN = 3.0    #: X401 pair below the rail top
SBR1_Y602_HOOK_OVER_IN = 7.0  #: top hairpin: over toward traffic ...
SBR1_Y602_HOOK_DOWN_IN = 12.0  # ... then back down
SBR1_Y601_TOP_BEND_IN = 5.25  #: Y601 top bend toward the back face


# ── neutral emit records ──────────────────────────────────────────────────

@dataclass(frozen=True)
class EmitObject:
    """One drawable object, independent of any Rhino API (see the module
    docstring for the ``kind`` vocabulary)."""

    kind: str
    layer: str
    points: tuple[Point, ...]
    tags: dict[str, str] = field(default_factory=dict)
    vector: Point | None = None      # prism extrusion, ft
    radius_ft: float | None = None   # cylinder radius, ft

    KINDS = ("prism", "polyline", "cylinder", "point")


@dataclass(frozen=True)
class BridgeEmit:
    """Everything a backend needs to draw one steel-girder BrIM model."""

    inputs: BridgeInput
    layout: BridgeLayout
    objects: tuple[EmitObject, ...]
    doc_tags: dict[str, str]

    def of_type(self, bim_type: str) -> tuple[EmitObject, ...]:
        """The emitted objects whose ``bim.type`` matches."""
        return tuple(o for o in self.objects
                     if o.tags.get("bim.type") == bim_type)


# ── section profiles ──────────────────────────────────────────────────────

def _arc(cw: float, ch: float, r: float, a0: float, a1: float,
         n: int) -> list[tuple[float, float]]:
    """``n`` interior points of an arc (degrees, endpoints excluded — the
    straight segments supply them)."""
    return [(cw + r * math.cos(math.radians(a)),
             ch + r * math.sin(math.radians(a)))
            for a in (a0 + (a1 - a0) * k / (n + 1) for k in range(1, n + 1))]


def i_profile_wh(section, arc_pts: int = 4) -> list[tuple[float, float]]:
    """Closed W-shape outline as ``(w, h)`` pairs in **inches**, ``w``
    across the flange (0 at the web centerline), ``h`` up from the bottom
    face.  The web-to-flange k-fillets (work-plan 1.4 — no square
    re-entrant corners) are tessellated with ``arc_pts`` points each; a
    section without a cataloged ``fillet_k`` falls back to square
    corners."""
    d, bf = section.depth, section.flange_width
    tf, tw = section.flange_thickness, section.web_thickness
    r = max(section.fillet_k - tf, 0.0)
    hb, hw = bf / 2.0, tw / 2.0

    pts: list[tuple[float, float]] = [(-hb, d), (hb, d), (hb, d - tf)]
    if r > 1e-6:
        pts.append((hw + r, d - tf))
        pts += _arc(hw + r, d - tf - r, r, 90.0, 180.0, arc_pts)
        pts.append((hw, d - tf - r))
        pts.append((hw, tf + r))
        pts += _arc(hw + r, tf + r, r, 180.0, 270.0, arc_pts)
        pts.append((hw + r, tf))
    else:
        pts += [(hw, d - tf), (hw, tf)]
    pts += [(hb, tf), (hb, 0.0), (-hb, 0.0), (-hb, tf)]
    if r > 1e-6:
        pts.append((-(hw + r), tf))
        pts += _arc(-(hw + r), tf + r, r, 270.0, 360.0, arc_pts)
        pts.append((-hw, tf + r))
        pts.append((-hw, d - tf - r))
        pts += _arc(-(hw + r), d - tf - r, r, 0.0, 90.0, arc_pts)
        pts.append((-(hw + r), d - tf))
    else:
        pts += [(-hw, tf), (-hw, d - tf)]
    pts.append((-hb, d - tf))
    return pts


def _polygon_area(loop: list[tuple[float, float]]) -> float:
    """Absolute shoelace area of a closed 2D loop (unrepeated points)."""
    total = 0.0
    for i, (a0, b0) in enumerate(loop):
        a1, b1 = loop[(i + 1) % len(loop)]
        total += a0 * b1 - a1 * b0
    return abs(total) / 2.0


def _grade_label(grade: str) -> str:
    """``"Grade 50W"`` -> ``"50W"`` for the ``mat.grade`` tag."""
    return grade.split()[-1] if grade.upper().startswith("GRADE") else grade


# ── emit ──────────────────────────────────────────────────────────────────

def girder_bridge_emit(inp: BridgeInput, *,
                       scd_year: int | str = 2020,
                       stud_pitch_in: float = STUD_PITCH_IN,
                       studs_per_row: int = STUDS_PER_ROW,
                       stud_dia_in: float = STUD_DIA_IN,
                       stud_length_in: float = STUD_LENGTH_IN,
                       side_cover_in: float = 2.0,
                       rebar_coating: str = "epoxy") -> BridgeEmit:
    """Build the tagged BrIM geometry for one steel-girder bridge.

    Shear studs are emitted only for a ``composite`` layout — they *are*
    the physical composite connection, mirroring the toggle the analysis
    models use.  Raises whatever :func:`layout_bridge` raises for inputs
    that violate the ODOT standard-design assumptions.
    """
    layout = layout_bridge(inp)
    L = layout.total_length_ft
    tan_skew = math.tan(math.radians(inp.skew_deg))
    section = layout.section
    grade = _grade_label(inp.grade)
    rail = railing_by_scd(inp.railing)

    objects: list[EmitObject] = []

    # bridge marker: bridge-wide parameters ride here (G4 contract) and a
    # live backend mirrors them into doc.Strings for rhino_gdr
    doc_tags = dict(layout.doc_tags)
    doc_tags.update({
        "bim.scd_year": str(scd_year),
        "bim.units": "ft",
        "bim.spans_ft": ",".join(f"{s:g}" for s in inp.spans_ft),
        "bim.girder_count": str(inp.girder_count),
        "bim.girder_spacing_ft": f"{inp.girder_spacing_ft:g}",
        "bim.girder_label": inp.girder_label,
        "bim.overhang_ft": f"{inp.overhang_ft:g}",
        "bim.skew_deg": f"{inp.skew_deg:g}",
        "bim.cross_slope_pct": f"{inp.cross_slope_pct:g}",
        "bim.composite": str(inp.composite).lower(),
        "bim.railing": inp.railing,
    })
    objects.append(EmitObject(
        kind="point", layer=LAYER_BRIDGE_DECK, points=((0.0, 0.0, 0.0),),
        tags={"bim.type": "bridge", "bim.id": "BRIDGE", **doc_tags}))

    # ── deck: crowned closed prism, skew-cut ends ─────────────────────────
    prof = layout.deck_profile_yz()
    deck_loop = tuple((y * tan_skew, y, z) for y, z in prof)
    deck_area_sf = _polygon_area([(y, z) for y, z in prof])
    objects.append(EmitObject(
        kind="prism", layer=LAYER_BRIDGE_DECK, points=deck_loop,
        vector=(L, 0.0, 0.0),
        tags=bim.deck_tags(
            "DECK", thickness_in=layout.deck.thickness_in,
            slope_pct=inp.cross_slope_pct,
            crown_offset_ft=layout.crown_y_ft, fc_psi=CONCRETE_FC_PSI,
            volume_cy=deck_area_sf * L / 27.0)))

    # ── girders: I-prism with k-fillets, square-cut ends ──────────────────
    wh = i_profile_wh(section)
    plf = _girder_weight_plf(inp.girder_label)
    for g in layout.girders:
        bid = f"G{g.line_no}"
        y0, z_bot = g.start[1], g.start[2] - section.depth / 12.0
        loop = tuple((g.start[0], y0 + w / 12.0, z_bot + h / 12.0)
                     for w, h in wh)
        objects.append(EmitObject(
            kind="prism", layer=LAYER_GIRDERS, points=loop,
            vector=(L, 0.0, 0.0),
            tags=bim.girder_tags(bid, inp.girder_label, grade=grade,
                                 weight_lb=plf * L)))
        # analysis contract: the tagged centerline the gdr reader consumes
        objects.append(EmitObject(
            kind="polyline", layer=LAYER_GIRDERS, points=(g.start, g.end),
            tags={**g.tags, "bim.id": bid}))

    # ── haunches: vertical-sided prisms per BDM 309.3.5 ───────────────────
    for h in layout.haunches:
        half_w = h.width_in / 24.0
        y0, z_top = h.start[1], h.start[2]
        loop = tuple((h.start[0], y0 + dy, z_top + dz) for dy, dz in
                     ((-half_w, 0.0), (half_w, 0.0),
                      (half_w, -h.depth_in / 12.0),
                      (-half_w, -h.depth_in / 12.0)))
        objects.append(EmitObject(
            kind="prism", layer=LAYER_HAUNCHES, points=loop,
            vector=(L, 0.0, 0.0),
            tags=bim.haunch_tags(f"HNCH-G{h.line_no}", depth_in=h.depth_in,
                                 width_in=h.width_in,
                                 fc_psi=CONCRETE_FC_PSI,
                                 volume_cy=(h.width_in / 12.0)
                                 * (h.depth_in / 12.0) * L / 27.0)))

    # ── shear studs: the physical composite connection ────────────────────
    if inp.composite:
        gauge_ft = STUD_GAUGE_IN / 12.0
        offsets = [(k - (studs_per_row - 1) / 2.0) * gauge_ft
                   for k in range(studs_per_row)]
        pitch_ft = stud_pitch_in / 12.0
        r_ft = stud_dia_in / 24.0
        len_ft = stud_length_in / 12.0
        for g in layout.girders:
            y0, z_top = g.start[1], g.start[2]
            row, x = 0, g.start[0] + pitch_ft / 2.0
            while x <= g.end[0] - pitch_ft / 2.0 + 1e-9:
                row += 1
                for k, dy in enumerate(offsets):
                    objects.append(EmitObject(
                        kind="cylinder", layer=LAYER_SHEAR_STUDS,
                        points=((x, y0 + dy, z_top),
                                (x, y0 + dy, z_top + len_ft)),
                        radius_ft=r_ft,
                        tags=bim.shear_stud_tags(
                            f"STUD-G{g.line_no}-R{row}-{k + 1}",
                            dia_in=stud_dia_in, length_in=stud_length_in,
                            count=1)))
                x += pitch_ft

    # ── deck rebar: both mats, crown-following ────────────────────────────
    for i, seg in enumerate(deck_rebar_segments(layout,
                                                side_cover_in=side_cover_in)):
        rs = seg.rebar_set
        objects.append(EmitObject(
            kind="polyline", layer=LAYER_REBAR, points=seg.points,
            tags=bim.rebar_tags(
                f"BAR-{rs.direction[:4].upper()}-{rs.mat.upper()}-{i + 1}",
                size=rs.size, coating=rebar_coating, mat=rs.mat,
                bend="crown-crank" if len(seg.points) > 2 else "straight",
                length_ft=seg.length_ft)))

    # ── parapets on both deck edges: true single-slope SCD profile ────────
    if rail.height and rail.base_width:
        B, H = rail.base_width / 12.0, rail.height / 12.0
        # top width from the SCD's gross section area (trapezoid), e.g.
        # SBR-1-20: 2*588/42 - 18 = 10 in
        T = (2.0 * rail.section_area / rail.height / 12.0 - B
             if rail.section_area else B)
        area_sf = (rail.section_area / 144.0 if rail.section_area
                   else B * H)
        for br in layout.barriers:
            (x0, y0, z0), _ = br.line
            s = 1.0 if br.edge == "right" else -1.0   # body toward traffic
            # back face vertical on the deck edge; traffic face battered
            sect = ((0.0, 0.0), (s * B, 0.0), (s * T, H), (0.0, H))
            loop = tuple((x0 + dy * tan_skew, y0 + dy, z0 + dz)
                         for dy, dz in sect)
            objects.append(EmitObject(
                kind="prism", layer=LAYER_BARRIERS, points=loop,
                vector=(L, 0.0, 0.0),
                tags=bim.parapet_tags(
                    f"PAR-{br.edge}", inp.railing, scd_year=scd_year,
                    height_in=rail.height, fc_psi=CONCRETE_FC_PSI,
                    length_ft=L, volume_cy=area_sf * L / 27.0)))
            if rail.scd == "SBR-1-20":
                objects.extend(_sbr1_cage(
                    br, s, B, T, H, L, tan_skew,
                    t_deck_in=layout.deck.overhang_thickness_in,
                    scd_year=scd_year))

    # ── bearings + load plates under every bearing point ──────────────────
    pad_half = BEARING_SIDE_IN / 24.0
    plate_half = PLATE_SIDE_IN / 24.0
    plate_t_ft = PLATE_THICKNESS_IN / 12.0
    pad_t_ft = BEARING_PLIES * BEARING_PLY_IN / 12.0
    plate_wt = (PLATE_SIDE_IN ** 2 * PLATE_THICKNESS_IN) / 1728.0 * STEEL_PCF
    for bp in layout.bearings:
        x, y, z = bp.location            # girder bottom flange
        bid = f"BRG-G{bp.line_no}-S{bp.station_index}"
        plate_loop = tuple((x + dx, y + dy, z - plate_t_ft) for dx, dy in
                           ((-plate_half, -plate_half),
                            (plate_half, -plate_half),
                            (plate_half, plate_half),
                            (-plate_half, plate_half)))
        objects.append(EmitObject(
            kind="prism", layer=LAYER_LOAD_PLATES, points=plate_loop,
            vector=(0.0, 0.0, plate_t_ft),
            tags=bim.load_plate_tags(bid + "-LP",
                                     thickness_in=PLATE_THICKNESS_IN,
                                     grade="50", weight_lb=plate_wt)))
        pad_loop = tuple((x + dx, y + dy, z - plate_t_ft - pad_t_ft)
                         for dx, dy in ((-pad_half, -pad_half),
                                        (pad_half, -pad_half),
                                        (pad_half, pad_half),
                                        (-pad_half, pad_half)))
        objects.append(EmitObject(
            kind="prism", layer=LAYER_BEARINGS, points=pad_loop,
            vector=(0.0, 0.0, pad_t_ft),
            tags=bim.bearing_tags(bid, fixity=bp.fixity,
                                  plies=BEARING_PLIES,
                                  ply_thickness_in=BEARING_PLY_IN,
                                  total_thickness_in=BEARING_PLIES
                                  * BEARING_PLY_IN)))
        # analysis contract: the tagged bearing point the gdr reader consumes
        objects.append(EmitObject(
            kind="point", layer=LAYER_BEARINGS, points=(bp.location,),
            tags={**bp.tags, "bim.id": bid}))

    return BridgeEmit(inputs=inp, layout=layout, objects=tuple(objects),
                      doc_tags=doc_tags)


def _sbr1_cage(br, s: float, B: float, T: float, H: float, L: float,
               tan_skew: float, *, t_deck_in: float,
               scd_year: int | str) -> list[EmitObject]:
    """SBR-1-20 reinforcing cage for one standard-railing run (the bar
    schedule constants above; the 14 ft guardrail transitions at the ends
    are not modeled).  ``s`` is +1/-1 toward traffic; ``B``/``T``/``H``
    the base/top/height (ft) of the single-slope section whose back face
    sits on the barrier line.

    Y601/Y602 verticals embed ``t_deck_in - 1.5 in`` into the deck (the
    SCD's ``EMBEDMENT = X - 1 1/2"``, 9 in minimum) and their horizontal
    legs point toward traffic to lap the bottom transverse deck steel.
    Longitudinal bars are modeled as full-length runs (the real 10 ft
    stock lengths lap-splice; the take-off length is the same).
    """
    (x0, y0, z0), _ = br.line
    c = SBR1_COVER_IN / 12.0
    leg = SBR1_LEG_IN / 12.0
    # EMBEDMENT = X - 1 1/2" with X the deck thickness under the railing —
    # the *overhang* thickness (t + 2 in), so the standard deck meets the
    # SCD's 9 in minimum exactly. The minimum itself is a design check
    # (short decks go to LRFD Section 13 per sheet 5), not a clamp: a bar
    # cannot embed deeper than the slab it sits on.
    embed = (t_deck_in - SBR1_EMBED_REDUCTION_IN) / 12.0
    z_emb = z0 - embed
    batter = (B - T) / H                     # traffic-face slope, ft/ft

    def face_y(z_rel: float) -> float:
        """Traffic-face offset from the barrier line at height above base."""
        return s * (B - batter * z_rel)

    out: list[EmitObject] = []
    step = SBR1_VERT_SPACING_IN / 12.0
    n = 0
    x = step / 2.0
    while x <= L - step / 2.0 + 1e-9:
        n += 1
        # verticals live at station x along the run; dy offsets map the
        # section into plan through the skew
        zt = z0 + H - c
        y_back = s * c
        y601_base = face_y(0.0) - s * c
        y601_top = face_y(H - c) - s * c
        out.append(EmitObject(
            kind="polyline", layer=LAYER_REBAR,
            points=tuple((x + x0 + dy * tan_skew, y0 + dy, z) for dy, z in (
                (y601_base + s * leg, z_emb),
                (y601_base, z_emb),
                (y601_base, z0),
                (y601_top, zt),
                (y601_top - s * SBR1_Y601_TOP_BEND_IN / 12.0, zt))),
            tags=bim.rebar_tags(
                f"PARBAR-{br.edge}-Y601-{n}", size=SBR1_VERT_SIZE,
                coating="epoxy", mat="parapet", bend="Y601",
                length_ft=leg + embed + H - c + SBR1_Y601_TOP_BEND_IN / 12.0,
                scd="SBR-1-20")))
        out.append(EmitObject(
            kind="polyline", layer=LAYER_REBAR,
            points=tuple((x + x0 + dy * tan_skew, y0 + dy, z) for dy, z in (
                (y_back + s * leg, z_emb),
                (y_back, z_emb),
                (y_back, zt),
                (y_back + s * SBR1_Y602_HOOK_OVER_IN / 12.0, zt),
                (y_back + s * SBR1_Y602_HOOK_OVER_IN / 12.0,
                 zt - SBR1_Y602_HOOK_DOWN_IN / 12.0))),
            tags=bim.rebar_tags(
                f"PARBAR-{br.edge}-Y602-{n}", size=SBR1_VERT_SIZE,
                coating="epoxy", mat="parapet", bend="Y602",
                length_ft=leg + embed + H - c
                + (SBR1_Y602_HOOK_OVER_IN + SBR1_Y602_HOOK_DOWN_IN) / 12.0,
                scd="SBR-1-20")))
        x += step

    # longitudinal #4 GFRP: 5 per face + the 2-X401 pair at the top
    runs: list[tuple[float, float, str]] = []
    for k in range(SBR1_FACE_BARS_PER_FACE):
        z_rel = (SBR1_FACE_BAR_START_IN + k * SBR1_FACE_BAR_SPACING_IN) / 12.0
        runs.append((s * c, z_rel, f"X4-BACK-{k + 1}"))
        runs.append((face_y(z_rel) - s * c, z_rel, f"X4-FACE-{k + 1}"))
    z_top_rel = H - SBR1_TOP_BAR_DROP_IN / 12.0
    runs.append((s * c + s * 2.0 / 12.0, z_top_rel, "X401-1"))
    runs.append((face_y(z_top_rel) - s * c, z_top_rel, "X401-2"))
    for dy, z_rel, mark in runs:
        pts = ((x0 + dy * tan_skew, y0 + dy, z0 + z_rel),
               (x0 + L + dy * tan_skew, y0 + dy, z0 + z_rel))
        out.append(EmitObject(
            kind="polyline", layer=LAYER_REBAR, points=pts,
            tags=bim.rebar_tags(
                f"PARBAR-{br.edge}-{mark}", size=SBR1_FACE_BAR_SIZE,
                coating="GFRP", mat="parapet", bend="straight",
                length_ft=L, scd="SBR-1-20")))
    return out


# ── substructure emit (work-plan phase 4) ─────────────────────────────────

SUB_FC_PSI = 4000.0          #: Class QC1 substructure concrete


@dataclass(frozen=True)
class SubRebarSpec:
    """Substructure reinforcing parameters that the executed designs do
    not size themselves.  The cap's *main* (tie) steel comes from the STM
    bar schedule on the placed :class:`CapBeam` and the column verticals
    from the bent's ``RebarLayer`` area — everything here is the detailing
    around them: the stirrups the cap shear check was run with, the bar
    size the column steel area is broken into, its ties, and the nominal
    two-face wall mats (temperature/shrinkage-level; final wall design
    replaces them)."""

    stirrup_size: int = 5
    stirrup_spacing_in: float = 12.0
    column_bar_size: int = 9
    column_tie_size: int = 4
    column_tie_spacing_in: float = 12.0
    wall_bar_size: int = 5
    wall_bar_spacing_in: float = 12.0
    cover_in: float = 3.0            #: caps / columns / footings
    wall_cover_in: float = 2.0
    coating: str = "epoxy"


def _unit_prefix(unit) -> str:
    """``"Pier 2"`` -> ``"PIER2"``, ``"Abutment 1"`` -> ``"ABUT1"``."""
    return unit.name.replace("Abutment ", "ABUT").replace("Pier ", "PIER")


def _oriented_rect(cx: float, cy: float, z: float, half_u: float,
                   half_n: float, u: Point, n: Point) -> tuple[Point, ...]:
    """Plan rectangle centered on ``(cx, cy)`` at ``z``, half-sides along
    the ``u`` / ``n`` unit vectors."""
    return tuple(
        (cx + su * half_u * u[0] + sn * half_n * n[0],
         cy + su * half_u * u[1] + sn * half_n * n[1], z)
        for su, sn in ((-1, -1), (1, -1), (1, 1), (-1, 1)))


def _cap_prism(cap, layer: str, tags: dict) -> EmitObject:
    """Cap-beam prism: cross-section in the (normal, z) plane at the cap
    origin, extruded along the (skewed) support line."""
    x0, y0, z_top = cap.origin
    u = cap.axis
    n = (u[1], -u[0], 0.0)
    w2 = cap.width_ft / 2.0
    loop = tuple((x0 + s * w2 * n[0], y0 + s * w2 * n[1], z)
                 for s, z in ((-1, z_top), (1, z_top),
                              (1, z_top - cap.depth_ft),
                              (-1, z_top - cap.depth_ft)))
    return EmitObject(kind="prism", layer=layer, points=loop,
                      vector=(u[0] * cap.length_ft, u[1] * cap.length_ft,
                              0.0), tags=tags)


def _wall_prism(wall, layer: str, tags: dict) -> EmitObject:
    """WallPanel prism: thickness centered on the bottom line, extruded
    along the wall axis."""
    x0, y0, z0 = wall.origin
    a = wall.axis
    m = (a[1], -a[0], 0.0)
    t2 = wall.thickness_ft / 2.0
    loop = tuple((x0 + s * t2 * m[0], y0 + s * t2 * m[1], z)
                 for s, z in ((-1, z0), (1, z0), (1, z0 + wall.height_ft),
                              (-1, z0 + wall.height_ft)))
    return EmitObject(kind="prism", layer=layer, points=loop,
                      vector=(a[0] * wall.length_ft, a[1] * wall.length_ft,
                              0.0), tags=tags)


def _pile_prism(pile, u: Point, n: Point) -> EmitObject:
    """Driven HP pile as a true I-prism (flanges parallel to the cap axis,
    web along the roadway for strong-axis bending about the cap)."""
    from civilpy.structural.bridge_layout import girder_section

    hx, hy, hz = pile.head
    sec = girder_section(pile.shape)
    loop = tuple(
        (hx + (w / 12.0) * u[0] + ((h - sec.depth / 2.0) / 12.0) * n[0],
         hy + (w / 12.0) * u[1] + ((h - sec.depth / 2.0) / 12.0) * n[1], hz)
        for w, h in i_profile_wh(sec))
    return EmitObject(
        kind="prism", layer=LAYER_SUB_PILES, points=loop,
        vector=(0.0, 0.0, -pile.length_ft),
        tags=bim.pile_tags(pile.tags_id, shape=pile.shape,
                           length_ft=pile.length_ft))


def _bar_area_in2(size: int) -> float:
    from civilpy.structural.steel import Rebar

    return float(Rebar(size).area.magnitude)


def _cap_rebar(geom, cap_type: str, spec: SubRebarSpec) -> list[EmitObject]:
    """Cap main steel straight from the STM tie schedule plus the
    stirrups the shear check was run with."""
    pid = _unit_prefix(geom.unit)
    cap = geom.cap
    x0, y0, z_top = cap.origin
    u = cap.axis
    n = (u[1], -u[0], 0.0)
    z_bot = z_top - cap.depth_ft
    c = spec.cover_in / 12.0
    out: list[EmitObject] = []

    if cap.tie_bar_count:
        dia_ft = cap.tie_bar_size / 8.0 / 12.0
        z_bar = z_bot + c + dia_ft / 2.0
        half = cap.width_ft / 2.0 - c - dia_ft / 2.0
        length = cap.length_ft - 2.0 * c
        for k in range(cap.tie_bar_count):
            f = (k / (cap.tie_bar_count - 1) if cap.tie_bar_count > 1
                 else 0.5)
            dn = -half + 2.0 * half * f
            p0 = (x0 + c * u[0] + dn * n[0], y0 + c * u[1] + dn * n[1],
                  z_bar)
            out.append(EmitObject(
                kind="polyline", layer=LAYER_SUB_REBAR,
                points=(p0, (p0[0] + length * u[0], p0[1] + length * u[1],
                             z_bar)),
                tags=bim.rebar_tags(
                    f"{pid}-CAPBAR-{k + 1}", size=cap.tie_bar_size,
                    coating=spec.coating, mat=cap_type, bend="straight",
                    length_ft=length)))

    half_w = cap.width_ft / 2.0 - c
    z_lo, z_hi = z_bot + c, z_top - c
    hoop_len = 2.0 * (2.0 * half_w + (z_hi - z_lo))
    step = spec.stirrup_spacing_in / 12.0
    k, s = 0, step / 2.0
    while s <= cap.length_ft - step / 2.0 + 1e-9:
        k += 1
        cx, cy = x0 + s * u[0], y0 + s * u[1]
        corners = [(-half_w, z_lo), (half_w, z_lo), (half_w, z_hi),
                   (-half_w, z_hi), (-half_w, z_lo)]
        out.append(EmitObject(
            kind="polyline", layer=LAYER_SUB_REBAR,
            points=tuple((cx + dn * n[0], cy + dn * n[1], z)
                         for dn, z in corners),
            tags=bim.rebar_tags(
                f"{pid}-STIR-{k}", size=spec.stirrup_size,
                coating=spec.coating, mat=cap_type, bend="stirrup",
                length_ft=hoop_len)))
        s += step
    return out


def _column_rebar(col, pid: str, index: int,
                  spec: SubRebarSpec) -> list[EmitObject]:
    """Column verticals carrying the design's total steel area (broken
    into ``column_bar_size`` bars on a ring at cover) plus circular ties
    over the clear height.  Rectangular columns distribute the same bars
    around the cover rectangle."""
    if col.bars_area_in2 <= 0.0:
        return []
    count = max(4, math.ceil(col.bars_area_in2
                             / _bar_area_in2(spec.column_bar_size)))
    cx, cy = col.center
    c_ft = spec.cover_in / 12.0
    out: list[EmitObject] = []

    if col.diameter_in is not None:
        r = col.diameter_in / 24.0 - c_ft - 0.5 / 12.0
        ring = [(cx + r * math.cos(2.0 * math.pi * k / count),
                 cy + r * math.sin(2.0 * math.pi * k / count))
                for k in range(count)]
        r_tie = col.diameter_in / 24.0 - c_ft
        tie_pts = [(cx + r_tie * math.cos(2.0 * math.pi * k / 24.0),
                    cy + r_tie * math.sin(2.0 * math.pi * k / 24.0))
                   for k in range(25)]
        tie_len = 2.0 * math.pi * r_tie
    else:
        hb = col.b_in / 24.0 - c_ft
        hh = col.h_in / 24.0 - c_ft
        perim = [(hb, hh), (-hb, hh), (-hb, -hh), (hb, -hh)]
        ring, per_side = [], math.ceil(count / 4)
        for (ax, ay), (bx, by) in zip(perim, perim[1:] + perim[:1]):
            for k in range(per_side):
                f = k / per_side
                ring.append((cx + ax + (bx - ax) * f,
                             cy + ay + (by - ay) * f))
        ring = ring[:count]
        tie_pts = [(cx + px, cy + py) for px, py in perim + perim[:1]]
        tie_len = 4.0 * (hb + hh)

    for k, (bx, by) in enumerate(ring, start=1):
        out.append(EmitObject(
            kind="polyline", layer=LAYER_SUB_REBAR,
            points=((bx, by, col.z_bot), (bx, by, col.z_top)),
            tags=bim.rebar_tags(
                f"{pid}-COL{index}-V{k}", size=spec.column_bar_size,
                coating=spec.coating, mat="column", bend="straight",
                length_ft=col.height_ft)))
    step = spec.column_tie_spacing_in / 12.0
    k, z = 0, col.z_bot + step / 2.0
    while z <= col.z_top - step / 2.0 + 1e-9:
        k += 1
        out.append(EmitObject(
            kind="polyline", layer=LAYER_SUB_REBAR,
            points=tuple((px, py, z) for px, py in tie_pts),
            tags=bim.rebar_tags(
                f"{pid}-COL{index}-T{k}", size=spec.column_tie_size,
                coating=spec.coating, mat="column", bend="hoop",
                length_ft=tie_len)))
        z += step
    return out


def _wall_rebar(wall, pid: str, name: str, mat: str,
                spec: SubRebarSpec) -> list[EmitObject]:
    """Nominal two-face vertical + horizontal mats on a wall panel."""
    x0, y0, z0 = wall.origin
    a = wall.axis
    m = (a[1], -a[0], 0.0)
    c = spec.wall_cover_in / 12.0
    z_lo, z_hi = z0 + c, z0 + wall.height_ft - c
    faces = (wall.thickness_ft / 2.0 - c, -(wall.thickness_ft / 2.0 - c))
    out: list[EmitObject] = []
    step = spec.wall_bar_spacing_in / 12.0
    for fi, dm in enumerate(faces):
        fx, fy = x0 + dm * m[0], y0 + dm * m[1]
        k, s = 0, step / 2.0
        while s <= wall.length_ft - step / 2.0 + 1e-9:
            k += 1
            bx, by = fx + s * a[0], fy + s * a[1]
            out.append(EmitObject(
                kind="polyline", layer=LAYER_SUB_REBAR,
                points=((bx, by, z_lo), (bx, by, z_hi)),
                tags=bim.rebar_tags(
                    f"{pid}-{name}-F{fi + 1}-V{k}", size=spec.wall_bar_size,
                    coating=spec.coating, mat=mat, bend="straight",
                    length_ft=z_hi - z_lo)))
            s += step
        k, z = 0, z_lo + step / 2.0
        length = wall.length_ft - 2.0 * c
        while z <= z_hi - step / 2.0 + 1e-9:
            k += 1
            p0 = (fx + c * a[0], fy + c * a[1], z)
            out.append(EmitObject(
                kind="polyline", layer=LAYER_SUB_REBAR,
                points=(p0, (p0[0] + length * a[0], p0[1] + length * a[1],
                             z)),
                tags=bim.rebar_tags(
                    f"{pid}-{name}-F{fi + 1}-H{k}", size=spec.wall_bar_size,
                    coating=spec.coating, mat=mat, bend="straight",
                    length_ft=length)))
            z += step
    return out


def _unit_objects(geom, cap_type: str, *, fc_psi: float) -> list[EmitObject]:
    """Emit one substructure unit (the parts piers and abutments share)."""
    pid = _unit_prefix(geom.unit)
    cap = geom.cap
    u = cap.axis
    n = (u[1], -u[0], 0.0)
    out = [_cap_prism(cap, LAYER_SUB_CAPS, bim.substructure_concrete_tags(
        cap_type, f"{pid}-CAP", fc_psi=fc_psi, volume_cy=cap.volume_cy,
        length_ft=cap.length_ft, width_ft=cap.width_ft,
        depth_ft=cap.depth_ft))]
    for seat in geom.seats:
        cx, cy, z_top = seat.center
        h_ft = seat.height_in / 12.0
        half = seat.side_in / 24.0
        out.append(EmitObject(
            kind="prism", layer=LAYER_SUB_SEATS,
            points=_oriented_rect(cx, cy, z_top - h_ft, half, half, u, n),
            vector=(0.0, 0.0, h_ft),
            tags=bim.substructure_concrete_tags(
                "beam_seat", f"{pid}-SEAT-G{seat.girder_line}",
                fc_psi=fc_psi,
                volume_cy=(seat.side_in / 12.0) ** 2 * h_ft / 27.0,
                side_in=seat.side_in, height_in=seat.height_in)))
    return out


def substructure_emit(sub, *, fc_psi: float = SUB_FC_PSI,
                      rebar: SubRebarSpec | None = SubRebarSpec()
                      ) -> tuple[EmitObject, ...]:
    """Tagged BrIM geometry for a placed
    :class:`~civilpy.structural.substructure_layout.SubstructureLayout`:
    pier caps / columns / footings and abutment caps / piles / backwalls /
    wingwalls on the ``Substructure::*`` layers, with the stepped beam
    seats under every bearing stack.  All cast-in-place concrete measures
    into the Class QC1 substructure item; piles into the steel-pile item
    (ft).

    ``rebar`` adds the reinforcing cage: cap main steel from the placed
    STM tie schedule, column verticals from the bent's steel area, and
    the detailing in :class:`SubRebarSpec` (pass ``None`` to skip)."""
    objects: list[EmitObject] = []

    for pier in sub.piers:
        pid = _unit_prefix(pier.unit)
        u = pier.cap.axis
        n = (u[1], -u[0], 0.0)
        objects += _unit_objects(pier, "pier_cap", fc_psi=fc_psi)
        if rebar is not None:
            objects += _cap_rebar(pier, "pier_cap", rebar)
        for i, col in enumerate(pier.columns, start=1):
            if rebar is not None:
                objects += _column_rebar(col, pid, i, rebar)
            cx, cy = col.center
            if col.diameter_in is not None:
                obj = EmitObject(
                    kind="cylinder", layer=LAYER_SUB_COLUMNS,
                    points=((cx, cy, col.z_bot), (cx, cy, col.z_top)),
                    radius_ft=col.diameter_in / 24.0,
                    tags=bim.substructure_concrete_tags(
                        "column", f"{pid}-COL-{i}", fc_psi=fc_psi,
                        volume_cy=col.volume_cy,
                        diameter_in=col.diameter_in,
                        height_ft=col.height_ft))
            else:
                obj = EmitObject(
                    kind="prism", layer=LAYER_SUB_COLUMNS,
                    points=_oriented_rect(cx, cy, col.z_bot,
                                          col.b_in / 24.0, col.h_in / 24.0,
                                          u, n),
                    vector=(0.0, 0.0, col.height_ft),
                    tags=bim.substructure_concrete_tags(
                        "column", f"{pid}-COL-{i}", fc_psi=fc_psi,
                        volume_cy=col.volume_cy, b_in=col.b_in,
                        h_in=col.h_in, height_ft=col.height_ft))
            objects.append(obj)
        for i, ftg in enumerate(pier.footings, start=1):
            fx, fy = ftg.center
            objects.append(EmitObject(
                kind="prism", layer=LAYER_SUB_FOOTINGS,
                points=_oriented_rect(fx, fy, ftg.z_top - ftg.thickness_ft,
                                      ftg.length_ft / 2.0,
                                      ftg.width_ft / 2.0, u, n),
                vector=(0.0, 0.0, ftg.thickness_ft),
                tags=bim.substructure_concrete_tags(
                    "footing", f"{pid}-FTG-{i}", fc_psi=fc_psi,
                    volume_cy=ftg.volume_cy, length_ft=ftg.length_ft,
                    width_ft=ftg.width_ft,
                    thickness_ft=ftg.thickness_ft)))

    for ab in sub.abutments:
        pid = _unit_prefix(ab.unit)
        u = ab.cap.axis
        n = (u[1], -u[0], 0.0)
        objects += _unit_objects(ab, "abutment_cap", fc_psi=fc_psi)
        if rebar is not None:
            objects += _cap_rebar(ab, "abutment_cap", rebar)
        for i, pile in enumerate(ab.piles, start=1):
            pile = _WithId(pile, f"{pid}-PILE-{i}")
            objects.append(_pile_prism(pile, u, n))
        if ab.backwall is not None:
            objects.append(_wall_prism(
                ab.backwall, LAYER_SUB_BACKWALLS,
                bim.substructure_concrete_tags(
                    "backwall", f"{pid}-BW", fc_psi=fc_psi,
                    volume_cy=ab.backwall.volume_cy,
                    thickness_ft=ab.backwall.thickness_ft,
                    height_ft=ab.backwall.height_ft)))
            if rebar is not None:
                objects += _wall_rebar(ab.backwall, pid, "BW", "backwall",
                                       rebar)
        for i, wing in enumerate(ab.wingwalls, start=1):
            objects.append(_wall_prism(
                wing, LAYER_SUB_WINGWALLS,
                bim.substructure_concrete_tags(
                    "wingwall", f"{pid}-WW-{i}", fc_psi=fc_psi,
                    volume_cy=wing.volume_cy,
                    thickness_ft=wing.thickness_ft,
                    height_ft=wing.height_ft)))
            if rebar is not None:
                objects += _wall_rebar(wing, pid, f"WW{i}", "wingwall",
                                       rebar)

    return tuple(objects)


class _WithId:
    """Attach the emit's ``bim.id`` to a pile record without widening the
    geometry dataclass."""

    def __init__(self, pile, tags_id: str):
        self._pile = pile
        self.tags_id = tags_id

    def __getattr__(self, name):
        return getattr(self._pile, name)


def add_substructure(emit: BridgeEmit, sub, *,
                     fc_psi: float = SUB_FC_PSI,
                     rebar: SubRebarSpec | None = SubRebarSpec()
                     ) -> BridgeEmit:
    """A new :class:`BridgeEmit` with the substructure appended to the
    superstructure emit — same doc tags, so the merged record still
    round-trips through :func:`emit_to_json`, :func:`read_bim_tags`, and
    the quantity rollup."""
    return BridgeEmit(inputs=emit.inputs, layout=emit.layout,
                      objects=emit.objects + substructure_emit(
                          sub, fc_psi=fc_psi, rebar=rebar),
                      doc_tags=emit.doc_tags)


# ── estimating rollup + read-back (work-plan 3.2 / 3.3) ───────────────────

def _tag_quantities(tag_dicts) -> dict[str, dict]:
    """Group tag dicts by ``pay.item`` and total their ``pay.qty`` —
    the on-the-fly quantity estimate the per-object pay-item tags exist
    to support.  Returns ``{item: {"desc", "unit", "qty", "objects"}}``
    sorted by item number."""
    out: dict[str, dict] = {}
    for tags in tag_dicts:
        item = tags.get("pay.item")
        if item is None:
            continue
        rec = out.setdefault(item, {
            "desc": tags.get("pay.desc", ""),
            "unit": tags.get("pay.unit", ""),
            "qty": 0.0, "objects": 0})
        rec["objects"] += 1
        qty = tags.get("pay.qty")
        if qty is not None:
            rec["qty"] += float(qty)
    for rec in out.values():
        rec["qty"] = round(rec["qty"], 2)
    return dict(sorted(out.items()))


def pay_item_quantities(emit: BridgeEmit) -> dict[str, dict]:
    """Quantity rollup straight from an emit (see :func:`_tag_quantities`)."""
    return _tag_quantities(o.tags for o in emit.objects)


def read_bim_tags(path) -> dict:
    """Read a BrIM-tagged ``.3dm`` back: every object carrying ``bim.type``
    returns its full user-text dict, and the ``bim.type = bridge`` marker's
    tags come back as the bridge-wide record.

    This is the round-trip half of the source-of-truth contract: the saved
    Rhino document alone carries enough attributes to regenerate the
    estimate (and, through the preserved ``gdr.*`` tags, the analysis
    model) without the session that drew it.  Returns ``{"bridge": {...},
    "components": [tags, ...]}``.
    """
    from civilpy.structural.rhino_stm import _require_rhino3dm

    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError(f"could not read 3dm file: {path}")
    bridge: dict = {}
    components: list[dict] = []
    for obj in f.Objects:
        us = dict(obj.Attributes.GetUserStrings() or {})
        btype = us.get("bim.type")
        if btype == "bridge":
            bridge = us
        elif btype is not None:
            components.append(us)
    return {"bridge": bridge, "components": components}


def read_bim_quantities(path) -> dict[str, dict]:
    """Pay-item rollup for a saved BrIM ``.3dm`` (read-back + estimate)."""
    return _tag_quantities(read_bim_tags(path)["components"])


# ── JSON transport for the live-document driver ───────────────────────────

def emit_to_json(emit: BridgeEmit) -> str:
    """Serialize the emit for ``draw_bim_emit.py`` (a pure-Rhino script —
    no civilpy import needed inside Rhino, so a stale civilpy in Rhino's
    site environment cannot skew the geometry).  Layer colors ride along
    so every backend paints the shared taxonomy identically."""
    import json

    from civilpy.structural.rhino_layers import DEFAULT_COLORS

    layers = sorted({o.layer for o in emit.objects})
    return json.dumps({
        "doc_tags": emit.doc_tags,
        "layers": {name: DEFAULT_COLORS.get(name, (128, 128, 128, 255))[:3]
                   for name in layers},
        "objects": [{
            "kind": o.kind, "layer": o.layer, "points": o.points,
            "tags": o.tags, "vector": o.vector, "radius_ft": o.radius_ft,
        } for o in emit.objects],
    })
