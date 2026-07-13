"""Traffic barriers, bridge railings, portable concrete barriers, lane
markings, and their reinforcement for the girder-line model (stage **G7**,
the *barrier & markings* companion to :mod:`civilpy.structural.rhino_deck`).

Where :mod:`~civilpy.structural.rhino_deck` puts a single generic parapet on
each deck edge, this module renders the **actual ODOT standard section** for a
chosen catalog entry (:mod:`civilpy.structural.odot.bridge_railing`):

* **concrete parapets** in their true shape family -- the New Jersey safety
  shape (vertical toe, lower/upper batter), the single-slope face, or the
  symmetric F-shape of a freestanding **portable concrete barrier** (PCB);
* **steel post-and-beam railings** (TST-1 / TST-2) as a low concrete curb
  carrying vertical posts and horizontal rail tubes;
* placeable on the two deck **edges**, in the **median**, or along any picked
  transverse line, so a construction-phase PCB run or a median SBR-2 is authored
  the same way as an edge parapet.

Each concrete barrier is drawn with a **rebar cage** -- the vertical face bars at
the catalog ``vertical_bar_spacing`` plus longitudinal bars -- as bar-centerline
curves on the ``Deck::Rebar`` layer, tagged ``gdr.kind=rebar``.  A companion
:func:`build_lane_lines` paints the **traffic lane markings** (a solid edge line
each side, dashed lane dividers between the 12 ft lanes) as flat strips on the
deck top.

Everything is display geometry tagged ``gdr.kind=barrier | rebar | lane_line`` so
the girder reader ignores it; the barrier's real contribution to the analysis
model is its ``dc2`` line load, carried in the tags exactly as the deck's parapet
is.  ``rhino3dm`` is an optional dependency imported lazily.
"""

#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

from __future__ import annotations

import re
import uuid
import warnings
from dataclasses import dataclass, field

from civilpy.structural.odot.bridge_railing import BRIDGE_RAILINGS
from civilpy.structural.rhino_gdr import (
    GTAG, GirderBridge, read_girder_model, _require_rhino3dm, _box_mesh, _fmt_num,
)
from civilpy.structural.rhino_layers import (
    LAYER_BARRIERS, LAYER_LANE_MARKINGS, LAYER_REBAR, ensure_layer,
)

#: Reinforced-concrete unit weight (pcf) for barrier dead load.
CONCRETE_PCF = 150.0
#: Default barrier designation (36 in New Jersey, TL-4).
DEFAULT_BARRIER = "BR-1 (36 in)"
#: Default deck overhang beyond each exterior girder line (ft) -- where the
#: edge barriers land when placements are not given explicitly.
DEFAULT_OVERHANG_FT = 3.5
#: Default clear cover to the reinforcing, inches.
DEFAULT_COVER_IN = 2.0
#: Standard reinforcing-bar nominal diameters (in), keyed by bar number.
BAR_DIAMETERS_IN: dict[int, float] = {
    3: 0.375, 4: 0.500, 5: 0.625, 6: 0.750, 7: 0.875,
    8: 1.000, 9: 1.128, 10: 1.270, 11: 1.410, 14: 1.693, 18: 2.257,
}


def bar_diameter_in(bar_no: int) -> float:
    """Nominal diameter (in) of a standard ``#bar_no`` reinforcing bar."""
    return BAR_DIAMETERS_IN.get(int(bar_no), int(bar_no) / 8.0)


@dataclass
class BarrierModel:
    """Summary of a generated barrier run: what was placed and the dead load
    it hands the analysis model. Lengths in the units named; loads in klf."""

    designation: str
    shape_family: str
    height_in: float
    length_ft: float
    n_placements: int
    dc2_klf_each: float
    n_barrier: int
    n_steel: int
    n_rebar: int
    material: str = ""

    @property
    def total_dc2_klf(self) -> float:
        """Combined dead load of every barrier run placed (klf)."""
        return self.n_placements * self.dc2_klf_each


# ── catalog + shape helpers ───────────────────────────────────────────────
def _railing(designation: str):
    try:
        return BRIDGE_RAILINGS[designation]
    except KeyError:
        raise KeyError(
            f"unknown bridge-railing designation {designation!r}; choose one of "
            f"{sorted(BRIDGE_RAILINGS)}")


def _extents(bridge: GirderBridge):
    """(x_min, x_max, girder Ys sorted) in feet from the girder-line nodes."""
    xs = [n.x for n in bridge.model.nodes.values()]
    ys = sorted({round(n.y, 4) for n in bridge.model.nodes.values()})
    return min(xs), max(xs), ys


def shape_family(r) -> str:
    """Classify a catalog railing into a geometry family: ``"new jersey"``,
    ``"single slope"``, ``"portable"`` (PCB F-shape), ``"combination"``
    (full-height concrete barrier + steel tube pedestrian rail on top,
    e.g. BR-2-15), ``"steel tube"`` (post-and-beam on a low curb, e.g.
    TST-1/TST-2), or ``"trapezoid"`` (generic concrete)."""
    shape = (r.shape or "").lower()
    scd = (r.scd or "").upper()
    if "combination" in shape:
        return "combination"
    if r.post_shape or "post-and-beam" in shape or "tube" in shape or (
            r.material or "").lower() == "steel":
        return "steel tube"
    if scd.startswith("PCB") or "portable" in (r.name or "").lower():
        return "portable"
    if "single slope" in shape or "single-slope" in shape:
        return "single slope"
    if "new jersey" in shape or "nj" == shape:
        return "new jersey"
    return "trapezoid"


def barrier_dc2_klf(designation: str, *, concrete_pcf: float = CONCRETE_PCF) -> float:
    """Dead load of one barrier run (klf): the gross concrete ``section_area``
    x unit weight for a concrete section, else the steel ``weight_per_ft``."""
    r = _railing(designation)
    if r.section_area is not None:
        return r.section_area / 144.0 * concrete_pcf / 1000.0
    if r.weight_per_ft is not None:
        return r.weight_per_ft / 1000.0
    return 0.0


def barrier_profile(r, height_ft: float, side: int) -> list[tuple[float, float]]:
    """Cross-section of a concrete barrier as ``(offset, z)`` vertices (ft),
    ``offset`` measured transversely from the placement line and ``z`` from the
    deck top. ``side`` is ``+1`` / ``-1`` for an edge barrier whose back face is
    on the line and body toward +Y / -Y, or ``0`` for a freestanding barrier
    built symmetric about the line (a PCB or median section).

    The vertex order winds around the section; the extruder fans its end caps
    from the centroid, so mild non-convexity (the NJ / F-shape break) is fine.
    """
    fam = shape_family(r)
    B = (r.base_width or 18.0) / 12.0
    T = (r.top_width or r.base_width or 8.0) / 12.0
    H = height_ft
    toe = 3.0 / 12.0                       # vertical reveal at the gutter line
    brk_h = min(13.0 / 12.0, 0.4 * H)      # lower/upper batter break height
    brk = T + 0.25 * (B - T)               # break-point horizontal offset

    if fam == "steel tube":
        # low concrete curb only; posts + rails are added by the caller
        curb = min(H, 10.0 / 12.0)
        Bc, Tc = B or (9.0 / 12.0), (T or 8.0 / 12.0)
        if side == 0:
            return [(-Bc / 2, 0.0), (Bc / 2, 0.0),
                    (Tc / 2, curb), (-Tc / 2, curb)]
        s = side
        return [(0.0, 0.0), (s * Bc, 0.0), (s * Tc, curb), (0.0, curb)]

    if fam == "portable":
        # symmetric F-shape, freestanding: mirror the battered face both sides
        hb, ht = B / 2, T / 2
        return [(-hb, 0.0), (hb, 0.0), (hb, toe), (brk, brk_h),
                (ht, H), (-ht, H), (-brk, brk_h), (-hb, toe)]

    if fam == "new jersey":
        s = side or 1
        # back face vertical on the line; battered traffic face inward
        return [(0.0, 0.0), (s * B, 0.0), (s * B, toe),
                (s * brk, brk_h), (s * T, H), (0.0, H)]

    if fam == "single slope" and side == 0:
        # freestanding (e.g. a roadway median/at-grade barrier): symmetric
        # about the placement line, both faces battered.
        return [(-B / 2, 0.0), (B / 2, 0.0), (T / 2, H), (-T / 2, H)]

    # single slope / generic trapezoid: one straight battered face
    s = side or 1
    return [(0.0, 0.0), (s * B, 0.0), (s * T, H), (0.0, H)]


# ── mesh / rebar primitives ───────────────────────────────────────────────
def _extrude_profile(r3, prof, y_ref, x0, x1, z0):
    """Extrude an ``(offset, z)`` profile placed at transverse ``y_ref`` and
    resting on ``z0`` along X from ``x0`` to ``x1`` into a closed mesh, capping
    each end with a triangle fan from the section centroid."""
    pts = [(y_ref + off, z0 + z) for (off, z) in prof]
    n = len(pts)
    m = r3.Mesh()
    for x in (x0, x1):
        for (y, z) in pts:
            m.Vertices.Add(x, y, z)
    cy = sum(y for y, _ in pts) / n
    cz = sum(z for _, z in pts) / n
    c0 = m.Vertices.Add(x0, cy, cz)
    c1 = m.Vertices.Add(x1, cy, cz)
    for i in range(n):
        j = (i + 1) % n
        m.Faces.AddFace(i, j, n + j, n + i)   # side quad
        m.Faces.AddFace(c0, j, i)             # x0 cap
        m.Faces.AddFace(c1, n + i, n + j)     # x1 cap
    m.Normals.ComputeNormals()
    m.Compact()
    return m


def _polyline_curve(r3, pts):
    pl = r3.Polyline()
    for (x, y, z) in pts:
        pl.Add(x, y, z)
    return pl.ToPolylineCurve()


def _rebar_attrs(r3, layer_index, *, size, form, host):
    a = r3.ObjectAttributes()
    a.LayerIndex = layer_index
    a.SetUserString(GTAG + "kind", "rebar")
    a.SetUserString(GTAG + "id", str(uuid.uuid4()))
    a.SetUserString(GTAG + "rebar.size", str(size))
    a.SetUserString(GTAG + "rebar.dia", _fmt_num(bar_diameter_in(size)))
    a.SetUserString(GTAG + "rebar.form", form)     # "vertical" | "longitudinal"
    a.SetUserString(GTAG + "rebar.host", host)     # "barrier" | "deck"
    return a


def barrier_rebar_curves(prof, y_ref, x0, x1, z0, *, cover_ft, spacing_ft,
                         bar_size, long_spacing_ft):
    """Bar centerlines for a concrete barrier's cage: a vertical face bar every
    ``spacing_ft`` along X tracing the section inset by ``cover_ft``, plus
    longitudinal bars every ``long_spacing_ft`` up the inset face. Returns
    ``(vertical_pts, longitudinal_pts)`` -- each a list of 3D point lists."""
    inset = _inset_profile(prof, cover_ft)
    # vertical bars: the inset section swept as discrete stirrups along X
    verticals = []
    x = x0 + spacing_ft / 2.0
    while x <= x1 - 1e-6:
        verticals.append([(x, y_ref + off, z0 + z) for (off, z) in inset])
        x += spacing_ft
    # longitudinal bars: follow the inset traffic-face polyline vertically,
    # sampling a bar every long_spacing_ft of height, run full length in X
    face = _face_polyline(inset)
    z_max = max(z for _, z in inset)
    longitudinals = []
    zc = cover_ft
    while zc <= z_max - cover_ft + 1e-9:
        off = _interp_offset(face, zc)
        longitudinals.append([(x0, y_ref + off, z0 + zc), (x1, y_ref + off, z0 + zc)])
        zc += long_spacing_ft
    return verticals, longitudinals


def _inset_profile(prof, cover_ft):
    """Shrink a profile toward its centroid by ``cover_ft`` -- a cheap uniform
    inset good enough for a display rebar cage (not a true offset)."""
    cy = sum(off for off, _ in prof) / len(prof)
    cz = sum(z for _, z in prof) / len(prof)
    out = []
    for off, z in prof:
        dy, dz = off - cy, z - cz
        d = (dy * dy + dz * dz) ** 0.5 or 1.0
        out.append((off - cover_ft * dy / d, z - cover_ft * dz / d))
    return out


def _face_polyline(prof):
    """The vertices of a profile sorted by height -- a monotone-ish trace of
    the traffic face used to sample longitudinal bar offsets."""
    return sorted(prof, key=lambda p: p[1])


def _interp_offset(face, z):
    """Linear-interpolate the transverse offset at height ``z`` along ``face``."""
    if z <= face[0][1]:
        return face[0][0]
    if z >= face[-1][1]:
        return face[-1][0]
    for (o0, z0), (o1, z1) in zip(face, face[1:]):
        if z0 <= z <= z1 and z1 != z0:
            t = (z - z0) / (z1 - z0)
            return o0 + t * (o1 - o0)
    return face[-1][0]


# ── layer helpers ─────────────────────────────────────────────────────────
def _add_layers(f, r3):
    """Create the nested ``Deck::`` layers a directly-opened barrier .3dm
    should carry (the DeckBarrier importer re-parents by gdr.kind
    regardless of source layer, but a direct open should already match).
    Returns their indices as a dict."""
    return {
        "barrier": ensure_layer(f, LAYER_BARRIERS),
        "steel": ensure_layer(f, LAYER_BARRIERS),
        "rebar": ensure_layer(f, LAYER_REBAR),
        "lane": ensure_layer(f, LAYER_LANE_MARKINGS),
    }


# ── steel post-and-beam detailing ─────────────────────────────────────────
def _rail_count(r) -> int:
    """Number of horizontal rail tubes from the catalog ``rail_element`` string
    (leading integer of e.g. ``"3 - HSS tube"``), defaulting to 2."""
    m = re.match(r"\s*(\d+)", r.rail_element or "")
    return int(m.group(1)) if m else 2


def _add_steel_railing(f, r3, r, y_ref, side, x0, x1, z_curb, height_ft, attr_base):
    """Vertical posts at ``post_spacing`` and horizontal rail tubes for a
    steel post-and-beam railing sitting on a curb of top ``z_curb``. Returns the
    count of steel objects added."""
    n = 0
    s = side or 1
    y_post = y_ref + s * (0.15)                    # post centered just inside curb
    post_w = 4.0 / 12.0
    spacing = (r.post_spacing or 75.0) / 12.0
    x = x0 + spacing / 2.0
    while x <= x1 - 1e-6:
        a = _steel_attr(r3, attr_base, r, "post")
        f.Objects.AddMesh(_box_mesh(
            r3, x - post_w / 2, x + post_w / 2,
            y_post - post_w / 2, y_post + post_w / 2, z_curb, height_ft), a)
        n += 1
        x += spacing
    # rail tubes spread between just above the curb and the top
    n_rails = _rail_count(r)
    tube = 6.0 / 12.0
    z_lo, z_hi = z_curb + tube, height_ft - tube / 2
    for k in range(n_rails):
        zc = z_lo if n_rails == 1 else z_lo + (z_hi - z_lo) * k / (n_rails - 1)
        a = _steel_attr(r3, attr_base, r, "rail")
        f.Objects.AddMesh(_box_mesh(
            r3, x0, x1, y_post - tube / 2, y_post + tube / 2,
            zc - tube / 2, zc + tube / 2), a)
        n += 1
    return n


def _steel_attr(r3, layer_index, r, part):
    a = r3.ObjectAttributes()
    a.LayerIndex = layer_index
    a.SetUserString(GTAG + "kind", "barrier")
    a.SetUserString(GTAG + "id", str(uuid.uuid4()))
    a.SetUserString(GTAG + "barrier.designation", r.designation)
    a.SetUserString(GTAG + "barrier.part", part)     # "post" | "rail"
    a.SetUserString(GTAG + "barrier.material", "steel")
    return a


# ── public builders ───────────────────────────────────────────────────────
def build_barriers(source, *, out_path, designation: str = DEFAULT_BARRIER,
                   placements=None, overhang_ft: float = DEFAULT_OVERHANG_FT,
                   deck_top_z_ft: float = 0.0, height_in: float | None = None,
                   rebar: bool = True, cover_in: float = DEFAULT_COVER_IN,
                   long_spacing_in: float = 12.0, concrete_pcf: float = CONCRETE_PCF,
                   unit_system=None) -> BarrierModel:
    """Render the ODOT standard section for ``designation`` and write it to
    ``out_path`` (a ``.3dm`` the ``DeckBarrier`` command imports). ``source``
    is a :class:`~civilpy.structural.rhino_gdr.GirderBridge` or a path to a
    girder ``.3dm``.

    ``placements`` selects where the barrier goes:

    * ``None`` -- one on each deck **edge** (``y_extent`` +/- ``overhang_ft``),
      back face outward;
    * ``"median"`` -- one freestanding barrier on the bridge centerline;
    * a list of ``(y_ft, side)`` -- explicit transverse offsets, ``side`` being
      ``+1`` / ``-1`` for an edge barrier facing inward / outward or ``0`` for a
      freestanding (symmetric) section such as a PCB.

    ``height_in`` overrides the catalog height. When ``rebar`` is true a bar cage
    is drawn on the ``Rebar`` layer for each concrete barrier (skipped for a
    steel railing, whose reinforcement lives in its curb detail). Returns a
    :class:`BarrierModel`.
    """
    bridge = source if isinstance(source, GirderBridge) else read_girder_model(source)
    r3 = _require_rhino3dm()
    r = _railing(designation)
    fam = shape_family(r)
    x0, x1, ys = _extents(bridge)
    y_lo, y_hi = ys[0], ys[-1]

    if placements is None:
        placements = [(y_lo - overhang_ft, +1), (y_hi + overhang_ft, -1)]
    elif placements == "median":
        placements = [((y_lo + y_hi) / 2.0, 0)]

    height_ft = (height_in if height_in is not None
                 else (r.height if r.height is not None else 36.0)) / 12.0
    dc2 = barrier_dc2_klf(designation, concrete_pcf=concrete_pcf)
    cover_ft = cover_in / 12.0
    bar_size = max(r.bar_sizes) if r.bar_sizes else 5
    v_spacing = (r.vertical_bar_spacing or 12.0) / 12.0

    f = r3.File3dm()
    f.Settings.ModelUnitSystem = unit_system or r3.UnitSystem.Feet
    lay = _add_layers(f, r3)

    n_barrier = n_steel = n_rebar = 0
    for (y_ref, side) in placements:
        prof = barrier_profile(r, height_ft, side)
        # concrete body (curb only for a steel railing)
        ba = r3.ObjectAttributes()
        ba.LayerIndex = lay["barrier"]
        ba.SetUserString(GTAG + "kind", "barrier")
        ba.SetUserString(GTAG + "id", str(uuid.uuid4()))
        ba.SetUserString(GTAG + "barrier.designation", designation)
        ba.SetUserString(GTAG + "barrier.shape", fam)
        ba.SetUserString(GTAG + "barrier.part", "body")
        ba.SetUserString(GTAG + "barrier.material", r.material or "")
        ba.SetUserString(GTAG + "barrier.h", _fmt_num(height_ft * 12.0))
        ba.SetUserString(GTAG + "barrier.test_level", r.test_level or "")
        ba.SetUserString(GTAG + "barrier.dc2", _fmt_num(dc2))
        f.Objects.AddMesh(_extrude_profile(r3, prof, y_ref, x0, x1, deck_top_z_ft), ba)
        n_barrier += 1

        if fam == "steel tube":
            # low curb; posts/rails carry the full railing height above it
            z_curb = deck_top_z_ft + min(height_ft, 10.0 / 12.0)
            n_steel += _add_steel_railing(
                f, r3, r, y_ref, side, x0, x1, z_curb,
                deck_top_z_ft + height_ft, lay["steel"])
        elif fam == "combination":
            # full-height reinforced concrete barrier; the steel tube
            # pedestrian rail mounts on TOP of it (e.g. BR-2-15's HSS posts
            # bolted to the barrier top, rail_height_above_in above that)
            z_top = deck_top_z_ft + height_ft
            n_steel += _add_steel_railing(
                f, r3, r, y_ref, side, x0, x1, z_top,
                z_top + (r.rail_height_above_in or 24.0) / 12.0, lay["steel"])

        if fam != "steel tube" and rebar:
            verts, longs = barrier_rebar_curves(
                prof, y_ref, x0, x1, deck_top_z_ft, cover_ft=cover_ft,
                spacing_ft=v_spacing, bar_size=bar_size,
                long_spacing_ft=long_spacing_in / 12.0)
            for pts in verts:
                f.Objects.AddCurve(_polyline_curve(r3, pts),
                                   _rebar_attrs(r3, lay["rebar"], size=bar_size,
                                                form="vertical", host="barrier"))
                n_rebar += 1
            for pts in longs:
                f.Objects.AddCurve(_polyline_curve(r3, pts),
                                   _rebar_attrs(r3, lay["rebar"], size=bar_size,
                                                form="longitudinal", host="barrier"))
                n_rebar += 1

    if not f.Write(str(out_path), 7):
        raise IOError(f"could not write barrier model to {out_path}")

    return BarrierModel(
        designation=designation, shape_family=fam, height_in=height_ft * 12.0,
        length_ft=x1 - x0, n_placements=len(placements), dc2_klf_each=dc2,
        n_barrier=n_barrier, n_steel=n_steel, n_rebar=n_rebar,
        material=r.material or "")


@dataclass
class LaneLineModel:
    """Summary of generated lane markings."""
    n_lanes: int
    lane_width_ft: float
    usable_width_ft: float
    n_edge_lines: int
    n_divider_lines: int
    n_objects: int


def build_lane_lines(source, *, out_path, n_lanes: int | None = None,
                     lane_width_ft: float = 12.0, line_width_in: float = 4.0,
                     edge_offset_ft: float = 1.0, overhang_ft: float = DEFAULT_OVERHANG_FT,
                     barrier_base_in: float = 18.0, deck_top_z_ft: float = 0.0,
                     dash_len_ft: float = 10.0, gap_len_ft: float = 30.0,
                     unit_system=None) -> LaneLineModel:
    """Paint traffic lane markings on the deck top and write them to
    ``out_path`` (a ``.3dm`` the ``DeckLaneLines`` command imports): a **solid
    edge line** ``edge_offset_ft`` inside each barrier face and **dashed lane
    dividers** every ``lane_width_ft`` between them. ``n_lanes`` defaults to the
    usable width divided by ``lane_width_ft`` (rounded). Returns a
    :class:`LaneLineModel`."""
    bridge = source if isinstance(source, GirderBridge) else read_girder_model(source)
    r3 = _require_rhino3dm()
    x0, x1, ys = _extents(bridge)
    y_lo, y_hi = ys[0], ys[-1]
    base_ft = barrier_base_in / 12.0
    # travelway between the two barrier traffic faces
    usable_lo = (y_lo - overhang_ft) + base_ft
    usable_hi = (y_hi + overhang_ft) - base_ft
    usable = usable_hi - usable_lo
    if usable <= 0:
        raise ValueError("no usable deck width between the barriers for lane lines")
    if n_lanes is None:
        n_lanes = max(1, round(usable / lane_width_ft))

    f = r3.File3dm()
    f.Settings.ModelUnitSystem = unit_system or r3.UnitSystem.Feet
    lay = ensure_layer(f, LAYER_LANE_MARKINGS)
    z = deck_top_z_ft + 0.02
    w = line_width_in / 12.0 / 2.0
    count = {"n": 0}

    def _line(y, style):
        a = r3.ObjectAttributes()
        a.LayerIndex = lay
        a.SetUserString(GTAG + "kind", "lane_line")
        a.SetUserString(GTAG + "id", str(uuid.uuid4()))
        a.SetUserString(GTAG + "lane_line.type", "edge" if style == "solid" else "divider")
        a.SetUserString(GTAG + "lane_line.style", style)
        a.SetUserString(GTAG + "lane_line.width", _fmt_num(line_width_in))
        return a

    def _paint(y, style):
        if style == "solid":
            f.Objects.AddMesh(_box_mesh(r3, x0, x1, y - w, y + w, z, z + 0.02),
                              _line(y, style))
            count["n"] += 1
            return 1
        # dashed: repeat dash/gap cycles down the length
        added, x = 0, x0
        while x < x1 - 1e-6:
            xe = min(x + dash_len_ft, x1)
            f.Objects.AddMesh(_box_mesh(r3, x, xe, y - w, y + w, z, z + 0.02),
                              _line(y, style))
            count["n"] += 1
            added += 1
            x += dash_len_ft + gap_len_ft
        return added

    # solid edge lines just inside each barrier
    _paint(usable_lo + edge_offset_ft, "solid")
    _paint(usable_hi - edge_offset_ft, "solid")
    n_edge = 2
    # dashed dividers spaced across the usable width
    lane_w = usable / n_lanes
    n_div = 0
    for k in range(1, n_lanes):
        _paint(usable_lo + k * lane_w, "dashed")
        n_div += 1

    if not f.Write(str(out_path), 7):
        raise IOError(f"could not write lane markings to {out_path}")

    return LaneLineModel(
        n_lanes=n_lanes, lane_width_ft=lane_w, usable_width_ft=usable,
        n_edge_lines=n_edge, n_divider_lines=n_div, n_objects=count["n"])


def deck_rebar_curves(x0, x1, y0, y1, z_bot, z_top, *, cover_ft,
                      transverse_spacing_ft, longitudinal_spacing_ft):
    """Top and bottom reinforcing mats for a deck slab spanning ``[y0, y1]`` over
    ``[x0, x1]`` between ``z_bot`` and ``z_top``. Returns a list of
    ``(form, points)`` bar centerlines: transverse bars (run in Y at each X
    station) and longitudinal bars (run in X at each Y station), in both the top
    and bottom mat, inset by ``cover_ft``."""
    bars = []
    zt = z_top - cover_ft
    zb = z_bot + cover_ft
    xa, xb = x0 + cover_ft, x1 - cover_ft
    ya, yb = y0 + cover_ft, y1 - cover_ft
    # transverse bars (span direction across the deck), stepping along X
    x = xa
    while x <= xb + 1e-9:
        for z in (zt, zb):
            bars.append(("transverse", [(x, ya, z), (x, yb, z)]))
        x += transverse_spacing_ft
    # longitudinal bars, stepping across Y
    y = ya
    while y <= yb + 1e-9:
        for z in (zt, zb):
            bars.append(("longitudinal", [(xa, y, z), (xb, y, z)]))
        y += longitudinal_spacing_ft
    return bars


def read_barrier_model(path):
    """Read the ``gdr.kind=barrier | rebar | lane_line`` objects back from a
    barrier/markings ``.3dm``: a list of dicts with ``kind``, ``id``, and an
    ``attrs`` map of the kind's ``gdr.<kind>.*`` tags (numeric values as
    ``float``). Round-trips :func:`build_barriers` / :func:`build_lane_lines`."""
    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError(f"could not read 3dm file: {path}")
    kinds = {"barrier", "rebar", "lane_line"}
    out = []
    for obj in f.Objects:
        us = dict(obj.Attributes.GetUserStrings() or {})
        kind = us.get(GTAG + "kind")
        if kind not in kinds:
            continue
        prefix = GTAG + kind + "."
        attrs = {}
        for k, v in us.items():
            if not k.startswith(prefix):
                continue
            key = k[len(prefix):]
            try:
                attrs[key] = float(v)
            except ValueError:
                attrs[key] = v
        out.append({"kind": kind, "id": us.get(GTAG + "id", ""), "attrs": attrs})
    return out
