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
