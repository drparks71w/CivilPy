#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""BrIM emit for ODOT concrete headwalls on precast box culverts (BCHW).

Builds the **complete culvert-end assembly** the Design Data sheets
(1/6-6/6) tabulate — resolved through
:func:`~civilpy.structural.odot.box_culvert_headwall.design_headwall`:

* **both wingwalls**, placed per headwall type (Type A: both at 45 deg
  from the culvert centerline; Type B: wall #1 at 45 deg + wall #2
  straight along the roadway line, per tabulated skew; Type C: both
  parallel to the roadway), tops on the sheet's 2:1 backslope (level for
  Type C) down to the 2 ft minimum tip;
* the **foreslope wall** — the 6 in / 1'-6" panel that sits *on top of
  the box*, leaving the barrel opening clear;
* an optional **precast box stub** (display only — the box itself is a
  separate ASTM C1433 design) so the opening reads as a culvert;
* **footings** under each wingwall (with the 4'-0" extension past the
  tip) and the culvert footing strip across the opening, each with its
  **cutoff wall** at the stream edge;
* the sheet's reinforcing series as bar centerlines: "X" verticals and
  "Y" footing dowels at the tabulated size/spacing on the stream face,
  the #5 @ 18 near-face/horizontal mats, "V"/"W" footing mats and "Z"
  cutoff bars per the footing design number, and the foreslope-wall
  bars.

Every object lands on a ``Culvert::*`` layer with ``bim.*`` /
``pay.*`` / ``mat.*`` user text.  **Quantities come from the sheet
tables, not from the drawn geometry**: concrete solids carry their
tabulated cy (whole-assembly values split across the parts) and the
tabulated reinforcing lbs ride on per-part schedule markers, so
:func:`~civilpy.structural.rhino_bim.pay_item_quantities` reproduces the
sheet's estimated quantities exactly.  Individual bars are visual and
carry ``rebar.*`` metadata but no pay block (they would double-count the
schedule markers).

Frame: culvert axis = +x (the barrel runs into +x), headwall face
through the origin, z = 0 at the top of footing, y = 0 on the culvert
centerline.  A Type B/C roadway skew rotates the face line by theta
about z.

The record draws through the BCHW Grasshopper component,
``Notebooks/Rhino Components/draw_bim_emit.py``, and
:func:`~civilpy.structural.rhino_bim.emit_to_3dm`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural import bim
from civilpy.structural.odot.box_culvert_headwall import (
    CLEAR_COVER_IN,
    CUTOFF_WALL_WIDTH_FT,
    FOOTING_EXTENSION_FT,
    HeadwallDesign,
    HeadwallInput,
    WINGWALL_BACKSLOPE,
    WINGWALL_TIP_MIN_FT,
    design_headwall,
)
from civilpy.structural.rhino_bim import EmitObject, Point
from civilpy.structural.rhino_layers import (
    LAYER_CULVERT_BOX,
    LAYER_CULVERT_FOOTINGS,
    LAYER_CULVERT_REBAR,
    LAYER_CULVERT_WALLS,
    LAYER_CULVERT_WINGWALLS,
)

CY = 27.0


@dataclass(frozen=True)
class BchwEmit:
    """One culvert-end headwall assembly — duck-compatible with
    :func:`~civilpy.structural.rhino_bim.emit_to_json` and
    :func:`~civilpy.structural.rhino_bim.emit_to_3dm`."""

    design: HeadwallDesign
    objects: tuple[EmitObject, ...]
    doc_tags: dict[str, str] = field(default_factory=dict)


def _conc_tags(btype: str, bid: str, volume_cy: float) -> dict:
    return {**bim.substructure_concrete_tags(btype, bid,
                                             volume_cy=volume_cy),
            "bim.scd": "BCHW"}


def _bar_tags(bid: str, *, size: int, mat: str, length_ft: float,
              bend: str = "straight") -> dict:
    """Rebar metadata without the pay block (the tabulated schedule
    markers carry the lbs; per-bar weights would double-count)."""
    tags = bim.rebar_tags(bid, size=size, mat=mat, bend=bend,
                          length_ft=length_ft, scd="BCHW")
    return {k: v for k, v in tags.items() if not k.startswith("pay.")}


def _schedule_marker(bid: str, mat: str, lbs: float,
                     at: Point) -> EmitObject:
    """The tabulated reinforcing quantity for one assembly part, carried
    on a marker point (the sheet's number, not a bar-by-bar takeoff)."""
    tags = bim.rebar_tags(f"{bid}-SCHEDULE", size=5, mat=mat,
                          bend="schedule", scd="BCHW")
    tags.update({"pay.item": "509E00200", "pay.qty": f"{lbs:g}",
                 "pay.unit": "lb", "rebar.schedule_lbs": f"{lbs:g}"})
    return EmitObject(kind="point", layer=LAYER_CULVERT_REBAR,
                      points=(at,), tags=tags)


# ── wall frames ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Wall:
    """One wingwall placement: root point on the face line, unit axis
    along the wall, unit normal toward the backfill.  The root rises the
    full design height H (retaining the fill beside the box); the
    tabulated wingwall height ``h`` is the **tip** height, the top
    dropping linearly with the graded embankment (level walls -- Type C,
    and Type B wall #2 at zero skew -- tabulate h = H)."""

    name: str
    root: Point
    axis: Point
    n_fill: Point
    length: float
    h_root: float
    h_tip: float

    def tip_height(self) -> float:
        return self.h_tip

    def top_at(self, s: float) -> float:
        s = min(max(s, 0.0), self.length)
        return self.h_root + (self.h_tip - self.h_root) * s / self.length


def _unit(x: float, y: float) -> Point:
    n = math.hypot(x, y)
    return (x / n, y / n, 0.0)


def _fill_normal(axis: Point) -> Point:
    """Wall-thickness direction: perpendicular to the axis, on the
    backfill (+x, roadway) side."""
    n = (axis[1], -axis[0], 0.0)
    return n if n[0] > 1e-9 else (-n[0], -n[1], 0.0)


def _walls(design: HeadwallDesign) -> tuple[_Wall, _Wall, Point, float]:
    """Both wingwall frames + the face direction and opening half-width
    (along the face) for the assembly."""
    inp = design.inputs
    row = design.row
    t = design.t_wall_in / 12.0
    th = math.radians(inp.roadway_skew_deg)
    f = _unit(math.sin(th), math.cos(th))         # face line direction
    half = (inp.box_span_ft / 2.0 + t) / math.cos(th)
    root_pos = (f[0] * half, f[1] * half, 0.0)
    root_neg = (-f[0] * half, -f[1] * half, 0.0)

    flare = _unit(-math.cos(math.radians(45.0)), math.sin(math.radians(45.0)))
    if inp.headwall_type == "A":
        axes = (flare, (flare[0], -flare[1], 0.0))
    elif inp.headwall_type == "B":
        # wall #1 flares at 45 deg; wall #2 runs straight along the face
        axes = (flare, (-f[0], -f[1], 0.0))
    else:                                          # Type C: both straight
        axes = (f, (-f[0], -f[1], 0.0))
    w1 = _Wall("WW1", root_pos, axes[0], _fill_normal(axes[0]),
               row.L1, design.H, row.h1)
    w2 = _Wall("WW2", root_neg, axes[1], _fill_normal(axes[1]),
               row.L2, design.H, row.h2)
    return w1, w2, f, half


# ── solids ────────────────────────────────────────────────────────────────

def _wall_area(w: _Wall) -> float:
    return w.length * (w.h_root + w.tip_height()) / 2.0


def _wingwall_solid(w: _Wall, t: float, conc_cy: float) -> EmitObject:
    ax, nf = w.axis, w.n_fill
    x0, y0, _ = w.root

    def p(s: float, z: float) -> Point:
        return (x0 + s * ax[0], y0 + s * ax[1], z)

    loop = (p(0.0, 0.0), p(0.0, w.h_root),
            p(w.length, w.tip_height()), p(w.length, 0.0))
    return EmitObject(
        kind="prism", layer=LAYER_CULVERT_WINGWALLS, points=loop,
        vector=(t * nf[0], t * nf[1], 0.0),
        tags=_conc_tags("wingwall", f"BCHW-{w.name}", conc_cy))


def _line_x(p1, d1, p2, d2):
    """2D intersection of lines p1 + s d1 and p2 + u d2 (None when
    parallel -- a straight wall whose toe line continues the strip's)."""
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(cross) < 1e-9:
        return None
    s = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / cross
    return (p1[0] + s * d1[0], p1[1] + s * d1[1])


def _footing_frames(design, w1, w2, f):
    """Toe/heel corner points of the continuous footing: for each wall,
    the tip corners and the mitered intersections of its toe/heel lines
    with the culvert strip's front/back lines."""
    row = design.row
    d_toe = row.a + CUTOFF_WALL_WIDTH_FT
    d_heel = row.footing_w - d_toe
    ns_f = (-f[1], f[0])                     # stream (-x) side of the face
    front_p, front_d = (d_toe * ns_f[0], d_toe * ns_f[1]), (f[0], f[1])
    back_p = (-d_heel * ns_f[0], -d_heel * ns_f[1])

    out = []
    for w in (w1, w2):
        ax = (w.axis[0], w.axis[1])
        ns = (-w.n_fill[0], -w.n_fill[1])
        length = w.length + FOOTING_EXTENSION_FT
        root = (w.root[0], w.root[1])
        toe_p = (root[0] + d_toe * ns[0], root[1] + d_toe * ns[1])
        heel_p = (root[0] - d_heel * ns[0], root[1] - d_heel * ns[1])
        c_toe = _line_x(front_p, front_d, toe_p, ax) or toe_p
        c_heel = _line_x(back_p, front_d, heel_p, ax) or heel_p
        out.append({
            "tip_toe": (toe_p[0] + length * ax[0], toe_p[1] + length * ax[1]),
            "tip_heel": (heel_p[0] + length * ax[0],
                         heel_p[1] + length * ax[1]),
            "c_toe": c_toe, "c_heel": c_heel,
            "toe_dir": ax, "ns": ns,
        })
    return out


def _footing_union(design: HeadwallDesign, w1: _Wall, w2: _Wall, f: Point,
                   span: float) -> list[EmitObject]:
    """The footing as it is cast: ONE continuous polygon -- both wingwall
    legs and the culvert strip with mitered front/back corners (no joint
    gaps for rebar to escape through) -- and the matching continuous
    cutoff-wall ribbon following the toe edge."""
    row = design.row
    fr = _footing_frames(design, w1, w2, f)

    def z0(p):
        return (p[0], p[1], 0.0)

    outline = (fr[0]["tip_toe"], fr[0]["c_toe"], fr[1]["c_toe"],
               fr[1]["tip_toe"], fr[1]["tip_heel"], fr[1]["c_heel"],
               fr[0]["c_heel"], fr[0]["tip_heel"])
    footing = EmitObject(
        kind="prism", layer=LAYER_CULVERT_FOOTINGS,
        points=tuple(z0(p) for p in outline),
        vector=(0.0, 0.0, -row.footing_t),
        tags=_conc_tags(
            "footing", "BCHW-FTG",
            row.footing_conc_cy
            + row.culvert_footing_cy_per_ft * span))

    # cutoff ribbon: the toe polyline offset CUTOFF_WALL_WIDTH_FT toward
    # the heel, mitered at the same corners
    cw = CUTOFF_WALL_WIDTH_FT
    ns_f = (-f[1], f[0])
    outer = [fr[0]["tip_toe"], fr[0]["c_toe"], fr[1]["c_toe"],
             fr[1]["tip_toe"]]
    off = [(-cw * fr[0]["ns"][0], -cw * fr[0]["ns"][1]),
           (-cw * ns_f[0], -cw * ns_f[1]),
           (-cw * fr[1]["ns"][0], -cw * fr[1]["ns"][1])]
    i0 = (outer[0][0] + off[0][0], outer[0][1] + off[0][1])
    i3 = (outer[3][0] + off[2][0], outer[3][1] + off[2][1])
    i1 = _line_x(i0, fr[0]["toe_dir"],
                 (outer[1][0] + off[1][0], outer[1][1] + off[1][1]),
                 (f[0], f[1])) or (outer[1][0] + off[1][0],
                                   outer[1][1] + off[1][1])
    i2 = _line_x(i3, fr[1]["toe_dir"],
                 (outer[2][0] + off[1][0], outer[2][1] + off[1][1]),
                 (f[0], f[1])) or (outer[2][0] + off[1][0],
                                   outer[2][1] + off[1][1])
    ribbon = tuple(outer + [i3, i2, i1, i0])
    area = abs(sum(p[0] * q[1] - q[0] * p[1]
                   for p, q in zip(ribbon, ribbon[1:] + ribbon[:1]))) / 2.0
    zc = -row.footing_t
    cutoff = EmitObject(
        kind="prism", layer=LAYER_CULVERT_WALLS,
        points=tuple((p[0], p[1], zc) for p in ribbon),
        vector=(0.0, 0.0, -row.hcw),
        tags=_conc_tags("cutoff_wall", "BCHW-CW",
                        area * row.hcw / CY))
    return [footing, cutoff]


def _foreslope_wall(design: HeadwallDesign, f: Point,
                    half: float) -> EmitObject:
    """The 6 in / 1'-6" panel spanning the opening **on top of the box**
    (anchor dowels + closure pour per Section A-A)."""
    inp = design.inputs
    row = design.row
    fs = inp.foreslope_wall_height_in / 12.0
    # the panel bears on the box top (anchor dowels + closure pour);
    # the table H is the rounded-up wingwall design height
    z0 = inp.box_rise_ft + 2.0 * inp.box_slab_thickness_in / 12.0
    ns = (f[1], -f[0], 0.0)                       # over the barrel
    span = inp.box_span_ft + 2.0 * design.t_wall_in / 12.0
    p0 = (-f[0] * half, -f[1] * half)

    def p(d: float, z: float) -> Point:
        return (p0[0] + d * ns[0], p0[1] + d * ns[1], z)

    loop = (p(0.0, z0), p(row.b, z0), p(row.b, z0 + fs), p(0.0, z0 + fs))
    return EmitObject(
        kind="prism", layer=LAYER_CULVERT_WALLS, points=loop,
        vector=(f[0] * 2.0 * half, f[1] * 2.0 * half, 0.0),
        tags=_conc_tags("foreslope_wall", "BCHW-FS",
                        design.foreslope_cy_per_ft * span))


def _box_stub(design: HeadwallDesign, stub_ft: float) -> list[EmitObject]:
    """Display-only precast box segment behind the headwall so the barrel
    opening reads (the box itself is a separate ASTM C1433 / OSE
    design — no pay items here)."""
    inp = design.inputs
    t = design.t_wall_in / 12.0
    ts = inp.box_slab_thickness_in / 12.0
    S, R = inp.box_span_ft, inp.box_rise_ft
    tan_th = math.tan(math.radians(inp.roadway_skew_deg))

    def tags(part: str) -> dict:
        return {**bim._base("box_culvert", f"BCHW-BOX-{part}", scd="BCHW"),
                "box.span_ft": f"{S:g}", "box.rise_ft": f"{R:g}",
                "box.display_only": "true"}

    def prism(loop_yz, part):
        # the end face lies ON the skewed headwall plane (x = y tan
        # theta), so a skewed culvert meets the rotated foreslope wall
        # instead of leaving it hanging in the air
        loop = tuple((y * tan_th, y, z) for y, z in loop_yz)
        return EmitObject(kind="prism", layer=LAYER_CULVERT_BOX,
                          points=loop, vector=(stub_ft, 0.0, 0.0),
                          tags=tags(part))

    walls_z = (0.0, R + 2.0 * ts)
    out = [
        prism(((-S / 2.0 - t, walls_z[0]), (-S / 2.0, walls_z[0]),
               (-S / 2.0, walls_z[1]), (-S / 2.0 - t, walls_z[1])), "W1"),
        prism(((S / 2.0, walls_z[0]), (S / 2.0 + t, walls_z[0]),
               (S / 2.0 + t, walls_z[1]), (S / 2.0, walls_z[1])), "W2"),
        prism(((-S / 2.0, 0.0), (S / 2.0, 0.0),
               (S / 2.0, ts), (-S / 2.0, ts)), "SLAB-BOT"),
        prism(((-S / 2.0, R + ts), (S / 2.0, R + ts),
               (S / 2.0, R + 2.0 * ts), (-S / 2.0, R + 2.0 * ts)),
              "SLAB-TOP"),
    ]
    # haunched (chamfered) inside corners, leg = wall thickness
    ch = t
    corners = ((-S / 2.0, ts, 1.0, 1.0), (S / 2.0, ts, -1.0, 1.0),
               (-S / 2.0, R + ts, 1.0, -1.0),
               (S / 2.0, R + ts, -1.0, -1.0))
    for k, (cy, cz, sy, sz) in enumerate(corners):
        out.append(prism(((cy, cz), (cy + sy * ch, cz),
                          (cy, cz + sz * ch)), f"HAUNCH-{k + 1}"))
    return out


# ── reinforcing (visual; the schedule markers carry the tabulated lbs) ────

def _wall_bars(w: _Wall, design: HeadwallDesign) -> list[EmitObject]:
    row = design.row
    t = design.t_wall_in / 12.0
    c = CLEAR_COVER_IN / 12.0
    ax, nf = w.axis, w.n_fill
    x0, y0, _ = w.root
    out: list[EmitObject] = []

    def p(s: float, d: float, z: float) -> Point:
        return (x0 + s * ax[0] + d * nf[0],
                y0 + s * ax[1] + d * nf[1], z)

    top_at = w.top_at

    # "X" verticals on the stream (far) face at the tabulated spacing,
    # "Y" footing dowels beside them rising the extension length c
    k, s = 0, row.x_spa_in / 24.0
    while s <= w.length - c:
        k += 1
        z_hi = top_at(s) - c
        out.append(EmitObject(
            kind="polyline", layer=LAYER_CULVERT_REBAR,
            points=(p(s, c, c), p(s, c, z_hi)),
            tags=_bar_tags(f"BCHW-{w.name}-X{k}", size=row.x_bar,
                           mat="wingwall", length_ft=z_hi - c)))
        s += row.x_spa_in / 12.0
    k, s = 0, row.y_spa_in / 24.0
    while s <= w.length - c:
        k += 1
        z_top = min(row.c, top_at(s) - c)
        out.append(EmitObject(
            kind="polyline", layer=LAYER_CULVERT_REBAR,
            points=(p(s, t - c, -row.footing_t + c),
                    p(s, t - c, z_top),),
            tags=_bar_tags(f"BCHW-{w.name}-Y{k}", size=row.y_bar,
                           mat="wingwall", length_ft=row.footing_t + z_top,
                           bend="dowel")))
        s += row.y_spa_in / 12.0
    # near-face verticals and both-face horizontals, #5 @ 18 max
    k, s = 0, 0.75
    while s <= w.length - c:
        k += 1
        z_hi = top_at(s) - c
        out.append(EmitObject(
            kind="polyline", layer=LAYER_CULVERT_REBAR,
            points=(p(s, t - c, c), p(s, t - c, z_hi)),
            tags=_bar_tags(f"BCHW-{w.name}-NF{k}", size=5,
                           mat="wingwall", length_ft=z_hi - c)))
        s += 1.5
    for d, face in ((c, "FF"), (t - c, "NF")):
        k, z = 0, 0.75
        while z <= max(w.h_root, w.h_tip) - c:
            k += 1
            s_end = w.length - c
            if w.h_tip < w.h_root and z + c > w.h_tip:
                s_end = min(s_end, (z + c - w.h_root) * w.length
                            / (w.h_tip - w.h_root))
            if s_end > 1.0:
                out.append(EmitObject(
                    kind="polyline", layer=LAYER_CULVERT_REBAR,
                    points=(p(c, d, z), p(s_end, d, z)),
                    tags=_bar_tags(f"BCHW-{w.name}-{face}-H{k}", size=5,
                                   mat="wingwall", length_ft=s_end - c)))
            z += 1.5
    return out


def _footing_bars(w: _Wall, design: HeadwallDesign) -> list[EmitObject]:
    """"V" transverse + "W" longitudinal mats (T&B) and "Z" cutoff bars
    per the footing design number."""
    row = design.row
    (v_size, v_spa), (wz_size, wz_spa) = design.v_bar, design.wz_bar
    c = CLEAR_COVER_IN / 12.0
    ax, nf = w.axis, w.n_fill
    ns = (-nf[0], -nf[1], 0.0)
    length = w.length + FOOTING_EXTENSION_FT
    d_toe = row.a + CUTOFF_WALL_WIDTH_FT - c
    d_heel = row.footing_w - row.a - CUTOFF_WALL_WIDTH_FT - c
    x0, y0, _ = w.root

    def at(s: float, d: float, z: float) -> Point:
        return (x0 + s * ax[0] + d * ns[0], y0 + s * ax[1] + d * ns[1], z)

    out: list[EmitObject] = []
    for z, face in ((-c, "T"), (-row.footing_t + c, "B")):
        k, s = 0, v_spa / 24.0
        while s <= length - c:
            k += 1
            out.append(EmitObject(
                kind="polyline", layer=LAYER_CULVERT_REBAR,
                points=(at(s, d_toe, z), at(s, -d_heel, z)),
                tags=_bar_tags(f"BCHW-{w.name}-V{face}{k}", size=v_size,
                               mat="footing", length_ft=d_toe + d_heel)))
            s += v_spa / 12.0
        k, d = 0, -d_heel + wz_spa / 24.0
        while d <= d_toe:
            k += 1
            out.append(EmitObject(
                kind="polyline", layer=LAYER_CULVERT_REBAR,
                points=(at(c, d, z), at(length - c, d, z)),
                tags=_bar_tags(f"BCHW-{w.name}-W{face}{k}", size=wz_size,
                               mat="footing", length_ft=length - 2.0 * c)))
            d += wz_spa / 12.0
    # "Z" bars down the cutoff wall
    k, s = 0, wz_spa / 24.0
    d_cw = row.a + CUTOFF_WALL_WIDTH_FT / 2.0
    while s <= length - c:
        k += 1
        out.append(EmitObject(
            kind="polyline", layer=LAYER_CULVERT_REBAR,
            points=(at(s, d_cw, -row.footing_t),
                    at(s, d_cw, -row.footing_t - row.hcw + c)),
            tags=_bar_tags(f"BCHW-{w.name}-Z{k}", size=wz_size,
                           mat="cutoff_wall",
                           length_ft=row.hcw - c)))
        s += wz_spa / 12.0
    return out


def _culvert_footing_bars(design: HeadwallDesign, f: Point,
                          half: float) -> list[EmitObject]:
    """The culvert footing strip's mats: \"V\" transverse + \"W\"
    longitudinal (T&B) and the \"Z\" cutoff bars, all running the full
    width across the culvert (continuous through the opening -- not
    shown on the plan insert, but they don't stop at the box)."""
    row = design.row
    (v_size, v_spa), (wz_size, wz_spa) = design.v_bar, design.wz_bar
    c = CLEAR_COVER_IN / 12.0
    ns = (-f[1], f[0], 0.0)
    d_toe = row.a + CUTOFF_WALL_WIDTH_FT - c
    d_heel = row.footing_w - row.a - CUTOFF_WALL_WIDTH_FT - c

    def at(s: float, d: float, z: float) -> Point:
        return (s * f[0] + d * ns[0], s * f[1] + d * ns[1], z)

    out: list[EmitObject] = []
    for z, face in ((-c, "T"), (-row.footing_t + c, "B")):
        k, s = 0, -half + v_spa / 24.0
        while s <= half - v_spa / 24.0 + 1e-9:      # "V" transverse
            k += 1
            out.append(EmitObject(
                kind="polyline", layer=LAYER_CULVERT_REBAR,
                points=(at(s, d_toe, z), at(s, -d_heel, z)),
                tags=_bar_tags(f"BCHW-CULV-V{face}{k}", size=v_size,
                               mat="footing", length_ft=d_toe + d_heel)))
            s += v_spa / 12.0
        k, d = 0, -d_heel + wz_spa / 24.0
        while d <= d_toe:                           # "W" longitudinal
            k += 1
            out.append(EmitObject(
                kind="polyline", layer=LAYER_CULVERT_REBAR,
                points=(at(-half, d, z), at(half, d, z)),
                tags=_bar_tags(f"BCHW-CULV-W{face}{k}", size=wz_size,
                               mat="footing", length_ft=2.0 * half)))
            d += wz_spa / 12.0
    # "Z" bars: continuous across the culvert cutoff wall
    k, s = 0, -half + wz_spa / 24.0
    d_cw = row.a + CUTOFF_WALL_WIDTH_FT / 2.0
    while s <= half - wz_spa / 24.0 + 1e-9:
        k += 1
        out.append(EmitObject(
            kind="polyline", layer=LAYER_CULVERT_REBAR,
            points=(at(s, d_cw, -row.footing_t),
                    at(s, d_cw, -row.footing_t - row.hcw + c)),
            tags=_bar_tags(f"BCHW-CULV-Z{k}", size=wz_size,
                           mat="cutoff_wall", length_ft=row.hcw - c)))
        s += wz_spa / 12.0
    # longitudinal runners tying the Z bars across the full cutoff
    for z in (-row.footing_t - c, -row.footing_t - row.hcw + c):
        out.append(EmitObject(
            kind="polyline", layer=LAYER_CULVERT_REBAR,
            points=(at(-half, d_cw, z), at(half, d_cw, z)),
            tags=_bar_tags(f"BCHW-CULV-ZL{'T' if z > -row.footing_t - 1 else 'B'}",
                           size=wz_size, mat="cutoff_wall",
                           length_ft=2.0 * half)))
    return out


def _foreslope_bars(design: HeadwallDesign, f: Point,
                    half: float) -> list[EmitObject]:
    """#5 @ 12 max horizontals + anchor dowels (Section A-A)."""
    inp = design.inputs
    row = design.row
    c = CLEAR_COVER_IN / 12.0
    fs = inp.foreslope_wall_height_in / 12.0
    z0 = inp.box_rise_ft + 2.0 * inp.box_slab_thickness_in / 12.0
    ns = (f[1], -f[0], 0.0)

    def p(s: float, d: float, z: float) -> Point:
        return (s * f[0] + d * ns[0], s * f[1] + d * ns[1], z)

    out: list[EmitObject] = []
    n_rows = max(1, int(fs / 0.5))
    for j in range(n_rows):
        z = z0 + c + (fs - 2.0 * c) * (j + 0.5) / n_rows
        for d, face in ((c, "F"), (row.b - c, "N")):
            out.append(EmitObject(
                kind="polyline", layer=LAYER_CULVERT_REBAR,
                points=(p(-half + c, d, z), p(half - c, d, z)),
                tags=_bar_tags(f"BCHW-FS-{face}-H{j + 1}", size=5,
                               mat="foreslope_wall",
                               length_ft=2.0 * half - 2.0 * c)))
    ts = inp.box_slab_thickness_in / 12.0
    embed = max(ts - c, 0.25)          # into the top slab, with cover
    k, s = 0, -half + 0.5
    while s <= half - 0.5:
        k += 1
        out.append(EmitObject(
            kind="polyline", layer=LAYER_CULVERT_REBAR,
            points=(p(s, row.b / 2.0, z0 - embed),
                    p(s, row.b / 2.0, z0 + fs - c)),
            tags=_bar_tags(f"BCHW-FS-D{k}", size=5, mat="foreslope_wall",
                           length_ft=fs + embed - c, bend="dowel")))
        s += 1.0
    return out


# ── assembly ──────────────────────────────────────────────────────────────

def bchw_emit(inp: HeadwallInput, *, box_stub_ft: float = 4.0,
              rebar: bool = True) -> BchwEmit:
    """Tagged BrIM geometry for one culvert-end headwall assembly,
    resolved from the Design Data tables (see the module docstring).
    ``box_stub_ft`` draws that much display-only precast box behind the
    headwall (0 skips it); ``rebar=False`` skips the bar centerlines
    (the tabulated schedule markers, and therefore the quantities, stay
    either way)."""
    design = design_headwall(inp)
    row = design.row
    t = design.t_wall_in / 12.0
    w1, w2, f, half = _walls(design)
    span = inp.box_span_ft + 2.0 * t

    a1, a2 = _wall_area(w1), _wall_area(w2)
    share1 = a1 / (a1 + a2)

    objects: list[EmitObject] = [EmitObject(
        kind="point", layer=LAYER_CULVERT_WINGWALLS,
        points=((0.0, 0.0, design.H),),
        tags={**bim._base("bridge", "BCHW", scd="BCHW"),
              "bim.units": "ft",
              "bchw.type": inp.headwall_type,
              "bchw.box_span_ft": f"{inp.box_span_ft:g}",
              "bchw.box_rise_ft": f"{inp.box_rise_ft:g}",
              "bchw.design_height_ft": f"{design.H:g}",
              "bchw.roadway_skew_deg": f"{inp.roadway_skew_deg:g}",
              "bchw.footing_design": str(row.footing_design)})]

    objects.append(_wingwall_solid(w1, t, row.wingwall_conc_cy * share1))
    objects.append(_wingwall_solid(w2, t, row.wingwall_conc_cy
                                   * (1.0 - share1)))
    objects += _footing_union(design, w1, w2, f, span)
    objects.append(_foreslope_wall(design, f, half))
    if rebar:
        objects += _culvert_footing_bars(design, f, half)
    if box_stub_ft > 0.0:
        objects += _box_stub(design, box_stub_ft)

    # the sheet's estimated reinforcing quantities, one marker per group
    objects += [
        _schedule_marker("BCHW-WW", "wingwall", row.wingwall_reinf_lbs,
                         (0.0, 0.0, design.H)),
        _schedule_marker("BCHW-FTG", "footing", row.footing_reinf_lbs,
                         (0.0, 0.0, -row.footing_t)),
        _schedule_marker("BCHW-CULV-FTG", "footing",
                         row.culvert_footing_lbs_per_ft * span,
                         (0.0, 0.0, -row.footing_t - row.hcw)),
        _schedule_marker("BCHW-FS", "foreslope_wall",
                         design.foreslope_lbs_per_ft * span,
                         (0.0, 0.0, design.H - 0.25)),
    ]

    if rebar:
        objects += _wall_bars(w1, design)
        objects += _wall_bars(w2, design)
        objects += _footing_bars(w1, design)
        objects += _footing_bars(w2, design)
        objects += _foreslope_bars(design, f, half)

    doc_tags = {"bim.units": "ft", "bim.scd": "BCHW",
                "bchw.type": inp.headwall_type,
                "bchw.design_height_ft": f"{design.H:g}"}
    return BchwEmit(design=design, objects=tuple(objects),
                    doc_tags=doc_tags)
