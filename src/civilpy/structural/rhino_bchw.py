#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""BrIM emit for the ODOT BCHW box culvert headwall / wingwall insert.

Turns a :class:`~civilpy.structural.odot.box_culvert_headwall.WingwallInput`
into the same *tagged, transport-neutral* geometry records the bridge
emits produce (:mod:`~civilpy.structural.rhino_bim`): true solids for the
tapered wingwall stem, the foreslope wall, the cutoff wall, and the
L-shaped footing, plus the nominal two-face reinforcing mats the sheet's
WW5xx / FS5xx / F6xx bar series describe — every object on a
``Culvert::*`` layer and stamped with its ``bim.*`` / ``pay.*`` /
``mat.*`` user text, so quantities roll into the Class QC1 concrete and
epoxy-rebar items exactly like the bridge components.

The record draws through every existing backend: the BCHW Grasshopper
component (live preview + bake),
``Notebooks/Rhino Components/draw_bim_emit.py`` (live document), and
:func:`~civilpy.structural.rhino_bim.emit_to_3dm` (headless ``.3dm``).

Frame (matches :func:`~civilpy.structural.odot.box_culvert_headwall
.layout_wingwall`): the box culvert wall face contains y = 0, the
wingwall flares out to ``y = L`` (sheared ``+x`` by the skew), x = 0 at
the wingwall root, z = 0 at the top of footing.  The foreslope wall runs
``-x`` from the root along the culvert face.

BCHW is a detailing template with no dimension table, so everything the
elevation/section sheets leave to the project engineer stays an input:
the two solids-only dimensions (``foreslope_run_ft``,
``footing_thickness_ft``) and the bar spacings/sizes arrive as arguments
with sheet-plausible defaults rather than catalog values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural import bim
from civilpy.structural.odot.box_culvert_headwall import (
    CLEAR_COVER_IN,
    WingwallInput,
    layout_wingwall,
)
from civilpy.structural.rhino_bim import EmitObject, Point
from civilpy.structural.rhino_layers import (
    LAYER_CULVERT_FOOTINGS,
    LAYER_CULVERT_REBAR,
    LAYER_CULVERT_WALLS,
    LAYER_CULVERT_WINGWALLS,
)

CY = 27.0  # ft^3 per cubic yard


def _conc_tags(btype: str, bid: str, volume_cy: float) -> dict:
    return {**bim.substructure_concrete_tags(btype, bid,
                                             volume_cy=volume_cy),
            "bim.scd": "BCHW"}


@dataclass(frozen=True)
class BchwEmit:
    """Everything a backend needs to draw one BCHW wingwall corner —
    duck-compatible with :func:`~civilpy.structural.rhino_bim.emit_to_json`
    and :func:`~civilpy.structural.rhino_bim.emit_to_3dm`."""

    inputs: WingwallInput
    objects: tuple[EmitObject, ...]
    doc_tags: dict[str, str] = field(default_factory=dict)


def _wall_face_frame(skew_deg: float) -> tuple[Point, Point]:
    """Unit axis ``a`` along the wingwall flare (skew-sheared) and unit
    normal ``m`` (+x side) of the wall face plane."""
    t = math.tan(math.radians(skew_deg))
    n = math.hypot(t, 1.0)
    a = (t / n, 1.0 / n, 0.0)
    return a, (a[1], -a[0], 0.0)


def _height_at(inp: WingwallInput, s: float) -> float:
    """Wingwall height at ``s`` ft along the flare (H at the root
    tapering to hf at the far end)."""
    H, hf = inp.wall_height_ft, inp.foreslope_height_ft
    return H + (hf - H) * s / inp.length_ft


def _wingwall_solid(inp: WingwallInput, t_wall: float) -> EmitObject:
    a, m = _wall_face_frame(inp.skew_deg)
    L_fl = inp.length_ft / a[1]          # flare length along the axis
    prof = [(0.0, 0.0), (0.0, inp.wall_height_ft),
            (L_fl, inp.foreslope_height_ft), (L_fl, 0.0)]
    loop = tuple((s * a[0], s * a[1], z) for s, z in prof)
    vol_cy = (inp.length_ft * (inp.wall_height_ft + inp.foreslope_height_ft)
              / 2.0 * t_wall / CY)
    return EmitObject(
        kind="prism", layer=LAYER_CULVERT_WINGWALLS, points=loop,
        vector=(-t_wall * m[0], -t_wall * m[1], 0.0),
        tags=_conc_tags("wingwall", "BCHW-WW", vol_cy))


def _foreslope_solids(inp: WingwallInput, t_wall: float, run: float,
                      ) -> list[EmitObject]:
    """Foreslope-wall stem (z 0..hf) and cutoff wall (z 0..-hcw at the
    stream edge of the footing), both running ``-x`` along the culvert
    face from the wingwall root."""
    hf, hcw, Wf = (inp.foreslope_height_ft, inp.cutoff_wall_height_ft,
                   inp.footing_width_ft)
    stem = tuple((0.0, y, z) for y, z in
                 ((0.0, 0.0), (t_wall, 0.0), (t_wall, hf), (0.0, hf)))
    cutoff = tuple((0.0, y, z) for y, z in
                   ((-Wf / 2.0, 0.0), (-Wf / 2.0 + t_wall, 0.0),
                    (-Wf / 2.0 + t_wall, -hcw), (-Wf / 2.0, -hcw)))
    return [
        EmitObject(kind="prism", layer=LAYER_CULVERT_WALLS, points=stem,
                   vector=(-run, 0.0, 0.0),
                   tags=_conc_tags("foreslope_wall", "BCHW-FS", run * hf * t_wall / CY)),
        EmitObject(kind="prism", layer=LAYER_CULVERT_WALLS, points=cutoff,
                   vector=(-run, 0.0, 0.0),
                   tags=_conc_tags("cutoff_wall", "BCHW-CW", run * hcw * t_wall / CY)),
    ]


def _footing_solids(inp: WingwallInput, run: float,
                    tf: float) -> list[EmitObject]:
    """L-shaped footing as two prisms: under the wingwall flare and under
    the foreslope-wall run, both ``Wf`` wide, ``tf`` thick below z = 0."""
    a, m = _wall_face_frame(inp.skew_deg)
    L_fl = inp.length_ft / a[1]
    w2 = inp.footing_width_ft / 2.0

    def at(s: float, d: float) -> Point:
        return (s * a[0] + d * m[0], s * a[1] + d * m[1], 0.0)

    ww = (at(0.0, -w2), at(L_fl, -w2), at(L_fl, w2), at(0.0, w2))
    fs = ((0.0, -w2, 0.0), (-run, -w2, 0.0), (-run, w2, 0.0), (0.0, w2, 0.0))
    return [
        EmitObject(kind="prism", layer=LAYER_CULVERT_FOOTINGS, points=ww,
                   vector=(0.0, 0.0, -tf),
                   tags=_conc_tags("footing", "BCHW-FTG-WW", inp.length_ft * inp.footing_width_ft
                       * tf / CY)),
        EmitObject(kind="prism", layer=LAYER_CULVERT_FOOTINGS, points=fs,
                   vector=(0.0, 0.0, -tf),
                   tags=_conc_tags("footing", "BCHW-FTG-FS",
                                   run * inp.footing_width_ft * tf / CY)),
    ]


def _wingwall_rebar(inp: WingwallInput, t_wall: float, *, size: int,
                    spacing_in: float, cover_in: float) -> list[EmitObject]:
    """WW5xx-series nominal cage: verticals both faces following the
    taper, horizontals both faces stopping where the taper cuts them."""
    a, m = _wall_face_frame(inp.skew_deg)
    L_fl = inp.length_ft / a[1]
    c = cover_in / 12.0
    step = spacing_in / 12.0
    faces = (-c, -(t_wall - c))
    out: list[EmitObject] = []

    def pt(s: float, d: float, z: float) -> Point:
        return (s * a[0] + d * m[0], s * a[1] + d * m[1], z)

    for fi, d in enumerate(faces):
        k, s = 0, step / 2.0
        while s <= L_fl - step / 2.0 + 1e-9:                # verticals
            k += 1
            z_hi = _height_at(inp, s * a[1]) - c
            out.append(EmitObject(
                kind="polyline", layer=LAYER_CULVERT_REBAR,
                points=(pt(s, d, c), pt(s, d, z_hi)),
                tags=bim.rebar_tags(f"BCHW-WW-F{fi + 1}-V{k}", size=size,
                                    mat="wingwall", length_ft=z_hi - c,
                                    scd="BCHW")))
            s += step
        k, z = 0, c + step / 2.0                            # horizontals
        z_top = max(inp.wall_height_ft, inp.foreslope_height_ft) - c
        H, hf, L = (inp.wall_height_ft, inp.foreslope_height_ft,
                    inp.length_ft)
        while z <= z_top + 1e-9:
            # bar exists where the wall is at least z + cover tall
            s0, s1 = c, L_fl - c
            if H != hf:
                s_cut = L * (z + c - H) / (hf - H) / a[1]
                if hf > H:
                    s0 = max(s0, s_cut)
                else:
                    s1 = min(s1, s_cut)
            if s1 - s0 > step:
                k += 1
                out.append(EmitObject(
                    kind="polyline", layer=LAYER_CULVERT_REBAR,
                    points=(pt(s0, d, z), pt(s1, d, z)),
                    tags=bim.rebar_tags(f"BCHW-WW-F{fi + 1}-H{k}",
                                        size=size, mat="wingwall",
                                        length_ft=s1 - s0, scd="BCHW")))
            z += step
    return out


def _foreslope_rebar(inp: WingwallInput, t_wall: float, run: float, *,
                     size: int, spacing_in: float,
                     cover_in: float) -> list[EmitObject]:
    """FS5xx-series nominal cage on the foreslope-wall stem."""
    c = cover_in / 12.0
    step = spacing_in / 12.0
    hf = inp.foreslope_height_ft
    faces = (c, t_wall - c)
    out: list[EmitObject] = []
    for fi, y in enumerate(faces):
        k, x = 0, -step / 2.0
        while x >= -(run - step / 2.0) - 1e-9:              # verticals
            k += 1
            out.append(EmitObject(
                kind="polyline", layer=LAYER_CULVERT_REBAR,
                points=((x, y, c), (x, y, hf - c)),
                tags=bim.rebar_tags(f"BCHW-FS-F{fi + 1}-V{k}", size=size,
                                    mat="foreslope_wall",
                                    length_ft=hf - 2.0 * c, scd="BCHW")))
            x -= step
        k, z = 0, c + step / 2.0                            # horizontals
        while z <= hf - c + 1e-9:
            k += 1
            out.append(EmitObject(
                kind="polyline", layer=LAYER_CULVERT_REBAR,
                points=((-c, y, z), (-(run - c), y, z)),
                tags=bim.rebar_tags(f"BCHW-FS-F{fi + 1}-H{k}", size=size,
                                    mat="foreslope_wall",
                                    length_ft=run - 2.0 * c, scd="BCHW")))
            z += step
    return out


def _footing_rebar(inp: WingwallInput, run: float, tf: float, *, size: int,
                   spacing_in: float, cover_in: float) -> list[EmitObject]:
    """F6xx-series nominal top mat: transverse bars across ``Wf`` plus
    four longitudinal runners, over both legs of the L."""
    a, m = _wall_face_frame(inp.skew_deg)
    L_fl = inp.length_ft / a[1]
    c = cover_in / 12.0
    step = spacing_in / 12.0
    w2 = inp.footing_width_ft / 2.0 - c
    z = -c
    out: list[EmitObject] = []

    def at(s: float, d: float) -> Point:
        return (s * a[0] + d * m[0], s * a[1] + d * m[1], z)

    k, s = 0, step / 2.0
    while s <= L_fl - step / 2.0 + 1e-9:                    # wingwall leg
        k += 1
        out.append(EmitObject(
            kind="polyline", layer=LAYER_CULVERT_REBAR,
            points=(at(s, -w2), at(s, w2)),
            tags=bim.rebar_tags(f"BCHW-FTG-WW-T{k}", size=size,
                                mat="footing", length_ft=2.0 * w2,
                                scd="BCHW")))
        s += step
    k, x = 0, -step / 2.0
    while x >= -(run - step / 2.0) - 1e-9:                  # foreslope leg
        k += 1
        out.append(EmitObject(
            kind="polyline", layer=LAYER_CULVERT_REBAR,
            points=((x, -w2, z), (x, w2, z)),
            tags=bim.rebar_tags(f"BCHW-FTG-FS-T{k}", size=size,
                                mat="footing", length_ft=2.0 * w2,
                                scd="BCHW")))
        x -= step
    for j in range(4):                                      # runners
        d = -w2 + (2.0 * w2) * j / 3.0
        out.append(EmitObject(
            kind="polyline", layer=LAYER_CULVERT_REBAR,
            points=((-(run - c), d, z), at(L_fl - c, d)),
            tags=bim.rebar_tags(f"BCHW-FTG-L{j + 1}", size=size,
                                mat="footing",
                                length_ft=run + L_fl - 2.0 * c,
                                scd="BCHW")))
    return out


def bchw_emit(inp: WingwallInput, *, foreslope_run_ft: float,
              footing_thickness_ft: float = 1.5, rebar: bool = True,
              wall_bar_size: int = 5, footing_bar_size: int = 6,
              bar_spacing_in: float = 12.0,
              cover_in: float = CLEAR_COVER_IN) -> BchwEmit:
    """Tagged BrIM geometry for one BCHW wingwall corner: wingwall,
    foreslope wall, cutoff wall, and L-shaped footing solids plus the
    nominal WW5xx / FS5xx / F6xx reinforcing mats.

    ``foreslope_run_ft`` is how far the foreslope/cutoff walls (and their
    footing leg) run from the wingwall root along the culvert face —
    typically half the box span plus a wall thickness (the sheet leaves
    it, like everything else, to the project).  Bar sizes/spacing default
    to the sheet's #5 walls / #6 footing at 12 in; pass ``rebar=False``
    for concrete-only.  All quantities roll into the 511E40000 /
    509E00200 items via :func:`~civilpy.structural.rhino_bim
    .pay_item_quantities`."""
    if foreslope_run_ft <= 0.0:
        raise ValueError("foreslope_run_ft must be positive")
    if footing_thickness_ft <= 0.0:
        raise ValueError("footing_thickness_ft must be positive")
    layout = layout_wingwall(inp)        # validates the shared dimensions

    t_wall = inp.box_wall_thickness_in / 12.0
    run = foreslope_run_ft
    tf = footing_thickness_ft

    objects: list[EmitObject] = [
        EmitObject(kind="point", layer=LAYER_CULVERT_WINGWALLS,
                   points=((0.0, 0.0, 0.0),),
                   tags={**bim._base("bridge", "BCHW", scd="BCHW"),
                         "bim.units": "ft",
                         "bchw.length_ft": f"{inp.length_ft:g}",
                         "bchw.skew_deg": f"{inp.skew_deg:g}",
                         "bchw.foreslope_run_ft": f"{run:g}"}),
        _wingwall_solid(inp, t_wall),
    ]
    objects += _foreslope_solids(inp, t_wall, run)
    objects += _footing_solids(inp, run, tf)
    if rebar:
        objects += _wingwall_rebar(inp, t_wall, size=wall_bar_size,
                                   spacing_in=bar_spacing_in,
                                   cover_in=cover_in)
        objects += _foreslope_rebar(inp, t_wall, run, size=wall_bar_size,
                                    spacing_in=bar_spacing_in,
                                    cover_in=cover_in)
        objects += _footing_rebar(inp, run, tf, size=footing_bar_size,
                                  spacing_in=bar_spacing_in,
                                  cover_in=cover_in)

    doc_tags = {"bim.units": "ft", "bim.scd": "BCHW",
                "bim.notes": " | ".join(layout.notes)}
    return BchwEmit(inputs=inp, objects=tuple(objects), doc_tags=doc_tags)
