#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Parametric prestressed-concrete cross-section input and preview.

Midas Civil's PSC wizards take mild reinforcement and strand positions as
raw coordinate tables typed in by hand.  This module replaces that entry
mode with *rules*: pick a standard shape (ODOT PSID I-beams, ODOT PSBD
48 in box beams), describe the strands and rebar parametrically, preview
the section in a notebook with :func:`plot_psc_section`, and only then
emit the coordinate tables the Midas API wants.

Strand input, three ways
------------------------

* :func:`strands_by_count` -- "give me N strands": fills the section's
  permissible grid in the standard order (PSID sheets encode the grid;
  box beams use the 2/4/6 in rows on a 2 in lattice, outermost first).
* :func:`strands_by_rows` -- explicit ``{height: count}`` rows for
  non-standard patterns; placement stays on the lattice and is checked
  against the actual solid geometry (a strand can't land in a void).
* :func:`strands_from_odot_design` -- the tabulated PSBDD-1-25 standard
  design for a box designation and span.

Rebar input, two ways
---------------------

* :func:`rebar_row` -- N bars evenly spaced across the solid width at a
  height (deck-interface bars, flange bars).
* :func:`perimeter_bars` -- bars following the outline at a clear cover
  (the typical stirrup-cage longitudinal steel).

All coordinates are ``(y, z)`` in inches, ``y`` transverse from the beam
centerline, ``z`` up from the soffit -- the same convention as
:mod:`civilpy.structural.odot.ps_i_beam`.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import importlib

from civilpy.structural.odot import ps_i_beam as _psid
from civilpy.structural.odot import box_beam as _psbd

# the odot package re-exports a *function* named box_beam_design, shadowing
# the module attribute -- import the module explicitly
_psbdd = importlib.import_module("civilpy.structural.odot.box_beam_design")

Point = tuple[float, float]  # (y, z) inches

#: I-beam strand: 0.6 in Grade 270 low-relaxation (PSID-1-13 sheet 10),
#: nominal area 0.217 in^2.
STRAND_AREA_IN2 = _psid.STRAND_AREA_IN2
STRAND_DIAMETER_IN = _psid.STRAND_DIAMETER_IN
STRAND_FPU_KSI = _psid.STRAND_FPU_KSI

#: Box-beam strand: 0.5 in Grade 270 low-relaxation, nominal area
#: 0.167 in^2 (PSBD-1-25 general notes, "PRESTRESSING STRAND").
BOX_STRAND_AREA_IN2 = 0.167
BOX_STRAND_DIAMETER_IN = 0.5

#: Standard lattice pitch and edge distance for generated strand rows, in.
STRAND_LATTICE_IN = 2.0
STRAND_EDGE_COVER_IN = 2.0

#: PSBD-1-25 sheet 2 "STRAND LAYOUT AND BAR SPACING": rows start 4 in
#: from each beam face with a 4 in gap astride the centerline (no
#: centerline strand).
BOX_STRAND_EDGE_IN = 4.0
#: PSBD-1-25 sheet 2 sections: top/bottom flanges are 5 1/2 in (the
#: 5 1/2"/void/5 1/2" left dimension chain, every depth).
BOX_FLANGE_IN = _psbd.BOX_FLANGE_THICKNESS_IN          # 5.5
#: PSBD-1-25 sheet 2 sections: side walls are 6 in (void is 3'-0" wide).
BOX_SIDE_WALL_IN = _psbd.BOX_WEB_THICKNESS_IN          # 6.0
#: PSBD-1-25 sheet 2 "STRAND LAYOUT AND BAR SPACING": the two bottom
#: longitudinal #5 bars sit in the 2 in strand row, 8 in from each
#: outside face -- those lattice points are bars, not strands.
BOX_BOTTOM_BAR_EDGE_IN = 8.0


# ── shapes ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class PSCShape:
    """A prestressed cross-section outline with optional interior voids.

    ``outline`` and each void are closed CCW polygons of ``(y, z)``
    vertices in inches.  ``strand_grid`` is the published permissible
    strand grid in standard fill order (empty when the standard doesn't
    publish one -- box beams -- and rows are generated on the lattice
    instead).  ``yb_in``/``area_in2`` are the *published* section values
    where available; the drawn polygon ignores chamfers/keyways so its
    area runs slightly high.
    """

    name: str
    family: str                      # "i-beam" | "box"
    outline: tuple[Point, ...]
    voids: tuple[tuple[Point, ...], ...] = ()
    depth_in: float = 0.0
    yb_in: float | None = None
    area_in2: float | None = None
    strand_grid: tuple[Point, ...] = ()
    draped_required: tuple[Point, ...] = ()
    strand_row_heights: tuple[float, ...] = ()   # rows for generated fills
    #: published top-flange shipping strand locations (Modified Type 4 /
    #: WF I-beams; empty elsewhere)
    shipping_strands: tuple[Point, ...] = ()


def i_beam_shape(name: str) -> PSCShape:
    """A PSID-1-13 I-beam section (``"AASHTO Type 2"`` .. ``"WF72-49"``)
    as a :class:`PSCShape`, carrying the sheet's permissible strand grid
    and must-drape locations."""
    s = _psid.ps_i_beam_section(name)
    return PSCShape(
        name=name, family="i-beam",
        outline=tuple(_psid.ps_i_beam_profile(name)),
        depth_in=s.depth_in, yb_in=s.yb_in, area_in2=s.area_in2,
        strand_grid=tuple(_psid.strand_grid(name)),
        draped_required=tuple(s.draped_required),
        strand_row_heights=tuple(z for z, _ in s.strand_rows),
        shipping_strands=tuple(s.shipping_strand_locations),
    )


_BOX_RE = re.compile(r"^(C?B)(\d+)-(\d+)$")


def _box_strand_grid(width: float) -> tuple[Point, ...]:
    """The PSBD-1-25 sheet 2 permissible strand grid, in standard fill
    order (bottom row up, outermost first).  Sheet-verified for the 48 in
    beams: the 2 and 4 in rows run "9 SPA. @ 2" from 4 in off each face
    with a 4 in gap astride the centerline (y = +-2..+-20, **no**
    centerline strand); the 6 in row is the single wall location above
    each row end (y = +-20).  In the 2 in row the lattice point 8 in
    from each face (y = +-16 on 48 in beams) is drawn as one of the two
    minimum bottom longitudinal #5 bars (sheet 2 note 2), so it is *not*
    a permissible strand location.  Other widths reuse the same
    edge/gap/bar rules (unverified against a sheet -- PSBDD-3-26
    territory)."""
    y_max = width / 2.0 - BOX_STRAND_EDGE_IN
    y_bar = width / 2.0 - BOX_BOTTOM_BAR_EDGE_IN
    ys = []
    y = y_max
    while y >= STRAND_LATTICE_IN * 0.999:            # stop before y=0
        ys.extend((-y, y) if y else (y,))
        y -= STRAND_LATTICE_IN
    h2, h4, h6 = _psbdd.STRAND_ROW_HEIGHTS_IN
    grid = [(y, h2) for y in ys if abs(y) != y_bar]
    grid += [(y, h4) for y in ys]
    grid += [(-y_max, h6), (y_max, h6)]
    return tuple(grid)


def box_beam_shape(designation: str, *, solid: bool = False) -> PSCShape:
    """A PSBD-1-25 box beam (``"B21-48"``, ``"CB27-48"``, ...) as a
    :class:`PSCShape`, per the sheet 2/6 dimension chains: 5 in top/bottom
    flanges, 6 in side walls (the void is 3'-0" wide on 48 in beams), the
    void's corner fillets (1.5 in on 17 in beams, 3 in otherwise) modeled
    as chamfers, and the exterior shear-key profile (5 in full-width
    bearing band at the soffit, 1 1/4 in deep keyway recess, 5 in top band
    set back 3/4 in), and the 1 in x 1 in soffit corner chamfers (the
    top corners are square).  Geometry taken from dane's dimensioned
    Rhino model of B17-48; reproduces the published sheet 4/6 Ab / Yb /
    Ib to within 0.15 percent at every depth.  Carries the sheet 2
    permissible strand grid.

    ``solid=True`` returns the same outline with **no void** -- the beam as
    it is actually cast at the ends and at each intermediate diaphragm
    (PSBD-1-25 sheets 3 and 4).  Those blocks are what carry the bearing
    reaction, the anchor dowels, the lifting inserts and the tie rods, and
    a model that runs the voided section end to end understates the end
    reaction badly; use both sections and switch at the block boundaries.
    """
    m = _BOX_RE.match(designation)
    if not m:
        raise ValueError(
            f"box designation {designation!r} not of the form B<depth>-<width>"
            f" / CB<depth>-<width>")
    depth, width = float(m.group(2)), float(m.group(3))
    w2 = width / 2.0
    f = (_psbd.BOX_VOID_FILLET_SHALLOW_IN if depth <= 17
         else _psbd.BOX_VOID_FILLET_IN)
    vw2, z0, z1 = w2 - BOX_SIDE_WALL_IN, BOX_FLANGE_IN, depth - BOX_FLANGE_IN
    # exterior side-face profile: bearing band, keyway recess, top band
    rw = w2 - _psbd.KEYWAY_RECESS_DEPTH_IN          # recessed face
    tw = w2 - _psbd.KEYWAY_TOP_SETBACK_IN           # top band face
    zb = _psbd.KEYWAY_BOTTOM_BAND_IN
    zr0 = zb + _psbd.KEYWAY_LOWER_CHAMFER_IN
    zt1 = depth - _psbd.KEYWAY_TOP_BAND_IN
    zr1 = zt1 - _psbd.KEYWAY_UPPER_CHAMFER_IN
    ch = _psbd.BOX_BOTTOM_CHAMFER_IN
    outline = ((-w2 + ch, 0.0), (w2 - ch, 0.0), (w2, ch), (w2, zb),
               (rw, zr0), (rw, zr1), (tw, zt1), (tw, depth),
               (-tw, depth), (-tw, zt1), (-rw, zr1), (-rw, zr0),
               (-w2, zb), (-w2, ch))
    void = ((-(vw2 - f), z0), (vw2 - f, z0), (vw2, z0 + f), (vw2, z1 - f),
            (vw2 - f, z1), (-(vw2 - f), z1), (-vw2, z1 - f), (-vw2, z0 + f))
    yb = area = None
    if width == _psbd.BOX_WIDTH_IN and not solid:
        props = _psbd.box_section_properties(int(depth))
        yb, area = props.yb, props.area
    return PSCShape(
        name=f"{designation}-SOLID" if solid else designation,
        family="box", outline=outline, voids=() if solid else (void,),
        depth_in=depth, yb_in=yb, area_in2=area,
        strand_grid=_box_strand_grid(width),
        strand_row_heights=tuple(_psbdd.STRAND_ROW_HEIGHTS_IN),
    )


def shear_key_shape(designation: str) -> PSCShape:
    """The **grouted shear key** between two adjacent PSBD-1-25 boxes.

    Two beams set side by side touch over the 5 in bearing band at the
    soffit and over nothing else: above that band each mating face is
    relieved by the keyway, so the pair encloses a continuous void that
    the C&MS 515 non-shrink grout fills.  This returns that void as its
    own section -- the mirror image of :func:`box_beam_shape`'s exterior
    profile about the joint, so the two can never drift apart:

    * a 1 1/4 in chamfer each side opening the key up off the bearing
      band (a ``2 * KEYWAY_LOWER_CHAMFER_IN`` tall vee),
    * the full 2 1/2 in wide recess over most of the depth,
    * a 1/2 in transition into the 1 1/2 in wide top slot formed by the
      3/4 in setbacks, running the top 5 in to the beam surface.

    Coordinates use the **beam's own datum** -- ``y`` from the joint
    centerline, ``z`` up from the beam soffit -- so the key polygon drops
    straight onto a box-beam cross-section drawing without a transform,
    and :func:`shape_centroid_in` gives the elevation to put the element
    axis at.

    The key is a real, if slender, section: about 48 in^2 on a 27 in box.
    Model it for what it is -- a vertical shear transfer -- not as a
    longitudinal flexural member; see
    :func:`~civilpy.structural.box_beam_pipeline.structural_model_from_box`
    for how the grillage connects it.
    """
    m = _BOX_RE.match(designation)
    if not m:
        raise ValueError(
            f"box designation {designation!r} not of the form B<depth>-<width>"
            f" / CB<depth>-<width>")
    depth = float(m.group(2))
    r = _psbd.KEYWAY_RECESS_DEPTH_IN            # 1 1/4 in each face
    t = _psbd.KEYWAY_TOP_SETBACK_IN             # 3/4 in each face
    zb = _psbd.KEYWAY_BOTTOM_BAND_IN            # top of the bearing band
    zr0 = zb + _psbd.KEYWAY_LOWER_CHAMFER_IN
    zt1 = depth - _psbd.KEYWAY_TOP_BAND_IN
    zr1 = zt1 - _psbd.KEYWAY_UPPER_CHAMFER_IN
    outline = ((0.0, zb), (r, zr0), (r, zr1), (t, zt1), (t, depth),
               (-t, depth), (-t, zt1), (-r, zr1), (-r, zr0))
    return PSCShape(name=f"KEY-{designation}", family="shear-key",
                    outline=outline, depth_in=depth)


def shape_centroid_in(shape: PSCShape) -> tuple[float, float]:
    """Area centroid ``(y, z)`` of ``shape``'s outline less its voids, in
    the shape's own coordinates.

    This is the point a MIDAS section with the default center-center
    offset puts on the element axis, so it is also the elevation to place
    the nodes at when several sections have to line up in one model.
    """
    def _moments(poly: tuple[Point, ...]) -> tuple[float, float, float]:
        """``(A, A*y_c, A*z_c)`` by the shoelace formula, sign-normalized
        so winding direction does not matter."""
        a = my = mz = 0.0
        for i in range(len(poly)):
            (y0, z0), (y1, z1) = poly[i], poly[(i + 1) % len(poly)]
            cross = y0 * z1 - y1 * z0
            a += cross
            my += (y0 + y1) * cross
            mz += (z0 + z1) * cross
        sign = 1.0 if a >= 0 else -1.0
        return sign * a / 2.0, sign * my / 6.0, sign * mz / 6.0

    area, my, mz = _moments(shape.outline)
    for void in shape.voids:
        v_a, v_my, v_mz = _moments(void)
        area -= v_a
        my -= v_my
        mz -= v_mz
    if area <= 0.0:
        raise ValueError(f"{shape.name} has no net area -- voids exceed the "
                         f"outline")
    return my / area, mz / area


# ── scanline geometry ────────────────────────────────────────────────────
def _intervals_at(poly: tuple[Point, ...], z: float) -> list[tuple[float, float]]:
    """Sorted ``(y0, y1)`` spans of ``poly``'s interior on the horizontal
    line at height ``z`` (even-odd rule, half-open edges so shared
    vertices count once)."""
    ys = []
    n = len(poly)
    for i in range(n):
        (ya, za), (yb, zb) = poly[i], poly[(i + 1) % n]
        if za == zb:
            continue
        lo, hi = (za, zb) if za < zb else (zb, za)
        if lo <= z < hi:
            ys.append(ya + (yb - ya) * (z - za) / (zb - za))
    ys.sort()
    return [(ys[i], ys[i + 1]) for i in range(0, len(ys) - 1, 2)]


def _subtract(spans, holes):
    """Interval subtraction: ``spans`` minus ``holes`` (both sorted)."""
    out = list(spans)
    for h0, h1 in holes:
        nxt = []
        for a, b in out:
            if h1 <= a or h0 >= b:
                nxt.append((a, b))
                continue
            if a < h0:
                nxt.append((a, h0))
            if h1 < b:
                nxt.append((h1, b))
        out = nxt
    return out


def solid_intervals(shape: PSCShape, z: float) -> list[tuple[float, float]]:
    """The solid ``(y0, y1)`` spans of the section at height ``z``
    (outline minus voids)."""
    spans = _intervals_at(shape.outline, z)
    for v in shape.voids:
        spans = _subtract(spans, _intervals_at(v, z))
    return spans


def point_in_solid(shape: PSCShape, y: float, z: float,
                   margin: float = 0.0) -> bool:
    """Whether ``(y, z)`` lies in solid concrete, at least ``margin``
    inches clear of every face (horizontally)."""
    return any(a + margin <= y <= b - margin
               for a, b in solid_intervals(shape, z))


def _row_candidates(shape: PSCShape, z: float, *,
                    spacing: float = STRAND_LATTICE_IN,
                    edge_cover: float = STRAND_EDGE_COVER_IN) -> list[float]:
    """Permissible strand ``y`` positions at height ``z`` on the global
    symmetric lattice (``0, +-spacing, ...``), ``edge_cover`` clear of
    every solid/void face -- outermost first, the standard fill order."""
    out: list[float] = []
    for a, b in solid_intervals(shape, z):
        k0 = math.ceil((a + edge_cover) / spacing)
        k1 = math.floor((b - edge_cover) / spacing)
        out.extend(k * spacing for k in range(k0, k1 + 1))
    return sorted(out, key=lambda y: (-abs(y), y))


# ── strand layouts ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class StrandLayout:
    """A concrete strand pattern on a :class:`PSCShape`."""

    shape: PSCShape
    points: tuple[Point, ...]
    strand_area: float = STRAND_AREA_IN2
    f_pu: float = STRAND_FPU_KSI
    source: str = ""
    strand_diameter: float = STRAND_DIAMETER_IN

    @property
    def n(self) -> int:
        return len(self.points)

    @property
    def a_ps(self) -> float:
        """Total strand area, in^2."""
        return self.n * self.strand_area

    @property
    def centroid_in(self) -> float:
        """Strand-group centroid above the soffit, in."""
        if not self.points:
            raise ValueError("empty strand layout")
        return sum(z for _, z in self.points) / self.n

    @property
    def eccentricity_in(self) -> float:
        """Eccentricity below the section centroid (Yb - ybar), in."""
        if self.shape.yb_in is None:
            raise ValueError(
                f"{self.shape.name} has no published Yb; compute the "
                "section centroid before asking for eccentricity")
        return self.shape.yb_in - self.centroid_in

    def __add__(self, other: "StrandLayout") -> "StrandLayout":
        """Merge two patterns on the same shape (e.g. a bottom-flange
        design pattern + the standard shipping strands).  Strand area
        and f_pu must match -- a mixed-size group would make ``a_ps``
        and the flexural helpers silently wrong."""
        if other.shape.name != self.shape.name:
            raise ValueError("cannot combine strand layouts on different "
                             f"shapes ({self.shape.name} + {other.shape.name})")
        if (other.strand_area != self.strand_area
                or other.f_pu != self.f_pu):
            raise ValueError("cannot combine strand layouts with different "
                             "strand area / f_pu")
        dup = set(self.points) & set(other.points)
        if dup:
            raise ValueError(f"strand locations occupied twice: {sorted(dup)}")
        return StrandLayout(self.shape, self.points + other.points,
                            self.strand_area, self.f_pu,
                            f"{self.source} + {other.source}",
                            self.strand_diameter)


def _strand_props(shape: PSCShape,
                  strand_area: float | None) -> tuple[float, float]:
    """(area, diameter) for the shape's standard strand: 0.6 in / 0.217
    in^2 for I-beams (PSID-1-13), 0.5 in / 0.167 in^2 for box beams
    (PSBD-1-25 general notes).  An explicit ``strand_area`` overrides the
    area but keeps the family diameter."""
    dia = (BOX_STRAND_DIAMETER_IN if shape.family == "box"
           else STRAND_DIAMETER_IN)
    if strand_area is not None:
        return strand_area, dia
    return (BOX_STRAND_AREA_IN2 if shape.family == "box"
            else STRAND_AREA_IN2), dia


def strands_by_count(shape: PSCShape, n: int, *,
                     strand_area: float | None = None) -> StrandLayout:
    """The first ``n`` locations of the section's standard fill order:
    the published permissible grid (PSID sheets 1-3 for I-beams, PSBD
    sheet 2 for box beams), or the generated 2 in lattice on the standard
    row heights (bottom row up, outermost first) for shapes without a
    grid."""
    if shape.strand_grid:
        grid = list(shape.strand_grid)
    else:
        grid = [(y, z) for z in shape.strand_row_heights
                for y in _row_candidates(shape, z)]
    if not 0 < n <= len(grid):
        raise ValueError(f"{shape.name} has {len(grid)} permissible strand "
                         f"locations, cannot place {n}")
    area, dia = _strand_props(shape, strand_area)
    return StrandLayout(shape, tuple(grid[:n]), area,
                        source=f"count n={n}", strand_diameter=dia)


def strands_by_rows(shape: PSCShape, rows: dict[float, int], *,
                    fill: str = "outer",
                    spacing: float = STRAND_LATTICE_IN,
                    edge_cover: float = STRAND_EDGE_COVER_IN,
                    strand_area: float | None = None) -> StrandLayout:
    """A pattern from explicit ``{height_above_soffit: count}`` rows.

    When the shape's published grid has locations at a row height, those
    are the candidates (so box rows honor PSBD sheet 2 exactly);
    otherwise positions come from the symmetric lattice inside solid
    concrete.  ``fill="outer"`` takes the outermost locations first
    (standard practice, keeps the pattern spread), ``fill="center"``
    packs from the centerline out."""
    if fill not in ("outer", "center"):
        raise ValueError(f"fill must be 'outer' or 'center', not {fill!r}")
    pts: list[Point] = []
    for z in sorted(rows):
        count = rows[z]
        cand = [y for y, gz in shape.strand_grid if gz == z]
        if not cand:
            cand = _row_candidates(shape, z, spacing=spacing,
                                   edge_cover=edge_cover)
        if fill == "center":
            cand = sorted(cand, key=lambda y: (abs(y), y))
        if count > len(cand):
            raise ValueError(
                f"{shape.name}: row z={z:g} in has {len(cand)} permissible "
                f"strand locations, cannot place {count}")
        pts.extend((y, z) for y in sorted(cand[:count]))
    area, dia = _strand_props(shape, strand_area)
    return StrandLayout(shape, tuple(pts), area,
                        source=f"rows {dict(sorted(rows.items()))}",
                        strand_diameter=dia)


def strands_from_odot_design(box: str, span_ft: int,
                             beam_type: str | None = None) -> StrandLayout:
    """The tabulated PSBDD-1-25 standard strand pattern for a box
    designation and span: the sheet's 2/4/6 in row counts placed
    outermost-first on the PSBD-1-25 sheet 2 permissible grid
    (verified against the drawing's "STRAND LAYOUT AND BAR SPACING"
    detail; PSBD note 1 requires the pattern be symmetric about the
    beam's vertical centerline, which outermost-first placement of the
    even tabulated counts preserves)."""
    designs = [d for d in _psbdd.designs_for_box(box) if d.span == span_ft
               and (beam_type is None or d.beam_type == beam_type)]
    if not designs:
        raise KeyError(f"no PSBDD-1-25 design for {box} at span {span_ft} ft"
                       + (f" ({beam_type})" if beam_type else ""))
    if len(designs) > 1:
        raise ValueError(
            f"{box} span {span_ft} ft has both composite and non-composite "
            "designs; pass beam_type='composite' or 'non_composite'")
    d = designs[0]
    h2, h4, h6 = _psbdd.STRAND_ROW_HEIGHTS_IN
    rows = {h: c for h, c in ((h2, d.strands_2in), (h4, d.strands_4in),
                              (h6, d.strands_6in)) if c}
    layout = strands_by_rows(box_beam_shape(box), rows)
    return StrandLayout(layout.shape, layout.points, layout.strand_area,
                        source=f"PSBDD-1-25 {d.beam_type} {box} "
                               f"span {span_ft} ft",
                        strand_diameter=layout.strand_diameter)


def shipping_strands(shape: PSCShape, *,
                     strand_area: float | None = None) -> StrandLayout:
    """The section's published top-flange shipping strand locations
    (Modified AASHTO Type 4 / WF I-beams: six at +-6, +-8, +-10 in,
    2-3/4 in below the top surface) as a :class:`StrandLayout`, so
    ``design_pattern + shipping_strands(shape)`` previews the full
    fabrication pattern.  Shipping strands stabilize the top flange for
    handling and are tensioned per the PSID general notes, not as design
    prestress -- exclude them from flexural checks unless the design
    counts them."""
    if not shape.shipping_strands:
        raise ValueError(f"{shape.name} has no published shipping strand "
                         "locations (AASHTO Type 2-4 top flanges carry "
                         "none)")
    area, dia = _strand_props(shape, strand_area)
    return StrandLayout(shape, tuple(shape.shipping_strands), area,
                        source="shipping strands", strand_diameter=dia)


# ── rebar layouts ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RebarPoint:
    y: float
    z: float
    size: int      # standard US bar designator, e.g. 5 for a #5


@dataclass(frozen=True)
class RebarLayout:
    """Mild-steel bar positions on a :class:`PSCShape`."""

    shape: PSCShape
    bars: tuple[RebarPoint, ...]
    source: str = ""

    @property
    def n(self) -> int:
        return len(self.bars)

    @property
    def a_s(self) -> float:
        """Total bar area, in^2."""
        from civilpy.structural.steel import Rebar
        return sum(float(Rebar(b.size).area.magnitude) for b in self.bars)

    def __add__(self, other: "RebarLayout") -> "RebarLayout":
        if other.shape.name != self.shape.name:
            raise ValueError("cannot combine rebar layouts on different "
                             f"shapes ({self.shape.name} + {other.shape.name})")
        return RebarLayout(self.shape, self.bars + other.bars,
                           f"{self.source} + {other.source}")


def _bar_diameter(size: int) -> float:
    from civilpy.structural.steel import Rebar
    return float(Rebar(size).diameter.magnitude)


def rebar_row(shape: PSCShape, size: int, n: int, z: float, *,
              side_cover: float = 2.0) -> RebarLayout:
    """``n`` bars of one size evenly spaced across the widest solid span
    at height ``z``, ``side_cover`` clear of the faces."""
    spans = solid_intervals(shape, z)
    if not spans:
        raise ValueError(f"{shape.name} has no solid material at z={z:g} in")
    a, b = max(spans, key=lambda s: s[1] - s[0])
    inset = side_cover + _bar_diameter(size) / 2.0
    a, b = a + inset, b - inset
    if a > b:
        raise ValueError(f"row at z={z:g} in too narrow for cover {side_cover:g} in")
    if n == 1:
        ys = [(a + b) / 2.0]
    else:
        step = (b - a) / (n - 1)
        ys = [a + i * step for i in range(n)]
    return RebarLayout(shape, tuple(RebarPoint(y, z, size) for y in ys),
                       source=f"row {n}-#{size} @ z={z:g}")


def perimeter_bars(shape: PSCShape, size: int, spacing: float, *,
                   cover: float = 2.0,
                   z_min: float | None = None,
                   z_max: float | None = None) -> RebarLayout:
    """Bars following the outline at a clear ``cover`` -- the stirrup-cage
    longitudinal steel.  Each edge is inset along its inward normal and
    bars are placed at roughly ``spacing`` with half-spacing end margins;
    corners are not mitered, so tight corners can put adjacent-edge bars
    close together -- preview before trusting.  ``z_min``/``z_max``
    restrict the band (e.g. only the bottom flange)."""
    inset = cover + _bar_diameter(size) / 2.0
    pts: list[RebarPoint] = []
    n = len(shape.outline)
    for i in range(n):
        (ya, za), (yb, zb) = shape.outline[i], shape.outline[(i + 1) % n]
        dy, dz = yb - ya, zb - za
        length = math.hypot(dy, dz)
        if length < spacing / 2.0:
            continue
        ny, nz = -dz / length, dy / length          # inward for CCW outline
        count = max(1, round(length / spacing))
        for k in range(count):
            t = (k + 0.5) / count
            y, z = ya + t * dy + ny * inset, za + t * dz + nz * inset
            if z_min is not None and z < z_min:
                continue
            if z_max is not None and z > z_max:
                continue
            if point_in_solid(shape, y, z):
                pts.append(RebarPoint(y, z, size))
    return RebarLayout(shape, tuple(pts),
                       source=f"perimeter #{size} @ {spacing:g} in, "
                              f"cover {cover:g} in")


def box_standard_bars(shape: PSCShape) -> RebarLayout:
    """The PSBD-1-25 minimum longitudinal reinforcing for a box beam
    (sheet 2 note 2): four #5 across the top flange and two #5 in the
    bottom.  Positions follow the "STRAND LAYOUT AND BAR SPACING"
    detail: the bottom pair sits *in* the 2 in strand row 8 in from
    each outside face (displacing those two strand locations -- see
    :func:`_box_strand_grid`); the top four sit just under the top
    surface, two near the walls and two inboard.  Everything else in
    the section's bar cage (#4 A..T transverse bars, tie/stirrup legs)
    is transverse steel and does not appear in a cross-section layout.
    """
    if shape.family != "box":
        raise ValueError(f"{shape.name} is not a PSBD box beam")
    w2 = max(y for y, _ in shape.outline)
    y_bot = w2 - BOX_BOTTOM_BAR_EDGE_IN
    z_top = shape.depth_in - 2.5
    h2 = _psbdd.STRAND_ROW_HEIGHTS_IN[0]
    bars = [RebarPoint(-y_bot, h2, 5), RebarPoint(y_bot, h2, 5)]
    for y in (-(w2 - 4.0), -8.0, 8.0, w2 - 4.0):
        bars.append(RebarPoint(y, z_top, 5))
    return RebarLayout(shape, tuple(bars),
                       source="PSBD-1-25 note 2 minimum longitudinal "
                              "(4+2) #5")


# ── preview ──────────────────────────────────────────────────────────────
def plot_psc_section(shape: PSCShape,
                     strands: StrandLayout | None = None,
                     rebar: RebarLayout | None = None, *,
                     show_grid: bool = True,
                     annotate: bool = True,
                     ax=None,
                     title: str | None = None):
    """Render the section with its strand grid, strands, and rebar to
    scale -- the pre-Midas sanity check.  Returns the figure."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    if ax is None:
        fig, ax = plt.subplots(figsize=(6.5, 6.5))
    else:
        fig = ax.figure
    ys = [y for y, _ in shape.outline]
    ax.fill(*zip(*shape.outline), facecolor="0.88", edgecolor="black",
            lw=1.2, zorder=1)
    for v in shape.voids:
        ax.fill(*zip(*v), facecolor="white", edgecolor="black", lw=0.9,
                zorder=2)
    occupied = set(strands.points) if strands else set()
    if show_grid:
        grid = shape.strand_grid or [
            (y, z) for z in shape.strand_row_heights
            for y in _row_candidates(shape, z)]
        free = [p for p in grid if p not in occupied]
        if free:
            ax.plot([y for y, _ in free], [z for _, z in free], "+",
                    color="0.55", ms=5, mew=0.9, zorder=3)
        draped_free = [p for p in shape.draped_required if p not in occupied]
        if draped_free:
            ax.plot([y for y, _ in draped_free],
                    [z for _, z in draped_free], "x", color="0.55",
                    ms=5, mew=0.9, zorder=3)
        ship_free = [p for p in shape.shipping_strands if p not in occupied]
        if ship_free:
            ax.plot([y for y, _ in ship_free],
                    [z for _, z in ship_free], "^", mfc="none",
                    color="0.55", ms=5, mew=0.9, zorder=3)
    if rebar:
        for b in rebar.bars:
            ax.add_patch(Circle((b.y, b.z), _bar_diameter(b.size) / 2.0,
                                facecolor="white", edgecolor="firebrick",
                                lw=1.1, zorder=4))
    if strands:
        r = strands.strand_diameter / 2.0
        for y, z in strands.points:
            ax.add_patch(Circle((y, z), r, facecolor="steelblue",
                                edgecolor="midnightblue", lw=0.6, zorder=5))
        ax.axhline(strands.centroid_in, color="steelblue", ls=":", lw=1.0,
                   zorder=0)
    if shape.yb_in is not None:
        ax.axhline(shape.yb_in, color="black", ls="--", lw=0.8, zorder=0)
    if annotate:
        lines = [shape.name]
        if strands:
            lines.append(f"{strands.n} strands, "
                         f"$A_{{ps}}$ = {strands.a_ps:.2f} in$^2$")
            lines.append(f"$\\bar{{y}}$ = {strands.centroid_in:.2f} in"
                         + (f", e = {strands.eccentricity_in:.2f} in"
                            if shape.yb_in is not None else ""))
        if rebar:
            lines.append(f"{rebar.n} bars, $A_s$ = {rebar.a_s:.2f} in$^2$")
        ax.text(0.02, 0.98, "\n".join(lines), transform=ax.transAxes,
                va="top", ha="left", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.4", fc="white",
                          ec="0.6", alpha=0.9))
    pad = (max(ys) - min(ys)) * 0.08
    ax.set_xlim(min(ys) - pad, max(ys) + pad)
    ax.set_ylim(-pad, shape.depth_in + pad)
    ax.set_aspect("equal")
    ax.set_xlabel("y (in)")
    ax.set_ylabel("z above soffit (in)")
    if title:
        ax.set_title(title)
    return fig


# ── torsion section properties ───────────────────────────────────────────
def _poly_area_perimeter(poly: tuple[Point, ...]) -> tuple[float, float]:
    n = len(poly)
    area = per = 0.0
    for i in range(n):
        (ya, za), (yb, zb) = poly[i], poly[(i + 1) % n]
        area += ya * zb - yb * za
        per += math.hypot(yb - ya, zb - za)
    return abs(area) / 2.0, per


@dataclass(frozen=True)
class TorsionProperties:
    """Torsion section dimensions (5.7.2.1): outside-perimeter area/length
    and, for cellular sections, the shear-flow-path quantities."""

    a_cp: float             # area enclosed by the outside perimeter, in^2
    p_c: float              # outside perimeter, in
    a_o: float | None       # area enclosed by the shear flow path, in^2
    p_h: float | None       # perimeter of the shear-flow centerline, in
    b_e: float | None       # effective width of the shear flow path, in


def torsion_properties(shape: PSCShape) -> TorsionProperties:
    """Torsion dimensions from the coordinate data.  ``a_cp``/``p_c`` come
    straight off the outline polygon.  For single-cell box shapes the
    shear flow path is taken at the wall midlines (bounding boxes of the
    outline and void), giving ``a_o``, ``p_h``, and ``b_e`` = the minimum
    wall thickness capped at Acp/pc (5.7.2.1); solid shapes report those
    as None -- solid-section torsion uses Acp/pc directly."""
    a_cp, p_c = _poly_area_perimeter(shape.outline)
    if not shape.voids:
        return TorsionProperties(a_cp, p_c, None, None, None)
    ys = [y for y, _ in shape.outline]
    zs = [z for _, z in shape.outline]
    vy = [y for y, _ in shape.voids[0]]
    vz = [z for _, z in shape.voids[0]]
    w_med = (max(ys) - min(ys) + max(vy) - min(vy)) / 2.0
    h_med = (max(zs) - min(zs) + max(vz) - min(vz)) / 2.0
    a_o = w_med * h_med
    p_h = 2.0 * (w_med + h_med)
    walls = ((max(ys) - min(ys)) - (max(vy) - min(vy))) / 2.0
    flanges = ((max(zs) - min(zs)) - (max(vz) - min(vz))) / 2.0
    b_e = min(walls, flanges, a_cp / p_c)
    return TorsionProperties(a_cp, p_c, a_o, p_h, b_e)


# ── strain-compatibility flexure ─────────────────────────────────────────
#: Concrete crushing strain at the extreme compression fiber (5.6.2.1).
EPS_CU = 0.003
#: Grade 270 low-relaxation strand "power formula" constants (PCI Design
#: Handbook): f_ps = eps * (A + B / (1 + (C*eps)^D)^(1/D)) <= f_pu.  At
#: small strain this reduces to E_p = A + B = 28,500 ksi.
_PF_A, _PF_B, _PF_C, _PF_D = 887.0, 27613.0, 112.4, 7.36


def strand_stress_270(eps: float) -> float:
    """Grade 270 low-relaxation strand stress (ksi) from total strain via
    the PCI power formula -- elastic at small strain, capped at 270."""
    f = eps * (_PF_A + _PF_B / (1.0 + (_PF_C * max(eps, 0.0)) ** _PF_D)
               ** (1.0 / _PF_D))
    return min(f, 270.0) if eps >= 0.0 else eps * (_PF_A + _PF_B)


def extreme_fibers(shape: PSCShape) -> tuple[float, float]:
    """``(z_bottom, z_top)`` of the outline -- the extreme fibers, straight
    from the coordinate data."""
    zs = [z for _, z in shape.outline]
    return min(zs), max(zs)


def composite_topping(shape: PSCShape, *,
                      thickness: float =
                      _psbd.COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN,
                      width: float | None = None) -> PSCShape:
    """The CIP composite topping over a girder as its own
    :class:`PSCShape`: a slab of ``thickness`` (default the PSBD-1-25
    5 in structural topping) sitting on the girder's top fiber, ``width``
    defaulting to the girder's overall width (pass the LRFD 4.6.2.6
    effective flange width for deck-on-I-beam sections)."""
    z0, z1 = extreme_fibers(shape)
    if width is None:
        ys = [y for y, _ in shape.outline]
        width = max(ys) - min(ys)
    w2 = width / 2.0
    return PSCShape(
        name=f"{shape.name} + {thickness:g} in topping", family="topping",
        outline=((-w2, z1), (w2, z1), (w2, z1 + thickness),
                 (-w2, z1 + thickness)),
        depth_in=z1 + thickness - z0)


def _band_area_moment(shape: PSCShape, a: float, bending: str,
                      z_bot: float, z_top: float) -> tuple[float, float]:
    """Solid area (in^2) and its centroid depth (in, from the extreme
    compression fiber at ``z_top``/``z_bot`` of the *combined* section)
    of the compression band ``0..a``.  Exact for the polygon shapes:
    solid width is piecewise linear between vertex heights, integrated
    segment-by-segment with 2-point Gauss."""

    def z_of(u):        # depth u below the compression fiber -> section z
        return z_top - u if bending == "sagging" else z_bot + u

    def w(u):
        return sum(b_ - a_ for a_, b_ in solid_intervals(shape, z_of(u)))

    verts = {z for poly in (shape.outline, *shape.voids) for _, z in poly}
    us = sorted({0.0, a} | {
        (z_top - z if bending == "sagging" else z - z_bot) for z in verts
        if 0.0 < (z_top - z if bending == "sagging" else z - z_bot) < a})
    area = moment = 0.0
    g = 1.0 / math.sqrt(3.0)
    for u0, u1 in zip(us, us[1:]):
        mid, half = (u0 + u1) / 2.0, (u1 - u0) / 2.0
        for ug in (mid - half * g, mid + half * g):
            area += half * w(ug)
            moment += half * w(ug) * ug
    return area, (moment / area if area else 0.0)


@dataclass(frozen=True)
class FiberForce:
    """One bar or tendon in the converged strain field: its depth from
    the compression fiber, compatibility strain (tension positive),
    stress, and force -- the per-component intermediates the hand calc
    tabulates."""

    kind: str               # "bar" | "tendon"
    d_in: float             # depth from the extreme compression fiber
    eps: float              # strain from compatibility (tension positive)
    f_ksi: float            # stress (tension positive)
    force_kips: float       # force incl. any displaced-concrete credit


@dataclass(frozen=True)
class FlexuralResult:
    """Strain-compatibility state at nominal flexural resistance."""

    bending: str            # "sagging" | "hogging"
    c_in: float             # neutral-axis depth from the compression fiber
    a_in: float             # equivalent stress-block depth (beta1 * c)
    d_t_in: float           # depth of the extreme tension steel
    eps_t: float            # net tensile strain there (5.5.4.2 input)
    phi: float              # resistance factor per 5.5.4.2
    m_n_kipft: float        # nominal flexural resistance
    c_c_kips: float         # concrete compression resultant
    t_ps_kips: float        # net tendon force, Sigma A_p*f_ps
    t_s_kips: float         # net mild-steel force (tension positive)
    f_ps_extreme_ksi: float  # stress in the tendon nearest the tension fiber
    residual_kips: float    # equilibrium residual at convergence
    iterations: int
    bar_forces: tuple[FiberForce, ...] = ()
    tendon_forces: tuple[FiberForce, ...] = ()

    @property
    def phi_mn_kipft(self) -> float:
        return self.phi * self.m_n_kipft

    @property
    def t_s_tension_kips(self) -> float:
        """T_s: the tension-side mild-steel resultant, Sigma A_s*f_s."""
        return sum(b.force_kips for b in self.bar_forces if b.force_kips > 0)

    @property
    def c_s_kips(self) -> float:
        """C_s: the compression-side mild-steel resultant (positive),
        Sigma A_s'*f_s'."""
        return -sum(b.force_kips for b in self.bar_forces
                    if b.force_kips < 0)

    def table(self) -> list[dict]:
        """Per-component rows (bars then tendons) ready for a DataFrame:
        the strain / stress / force triplet at each depth."""
        return [{"kind": f.kind, "d (in)": f.d_in, "eps": f.eps,
                 "f (ksi)": f.f_ksi, "force (kips)": f.force_kips}
                for f in self.bar_forces + self.tendon_forces]


def flexural_strain_compatibility(
        shape: PSCShape,
        strands: StrandLayout | None = None,
        rebar: RebarLayout | None = None, *,
        f_c: float,
        f_pe: float = 0.0,
        bending: str = "sagging",
        f_y: float = 60.0,
        e_s: float = 29000.0,
        e_p: float = 28500.0,
        eps_cu: float = EPS_CU,
        topping: PSCShape | None = None,
        topping_f_c: float | None = None,
        displaced_concrete_credit: bool = True,
        max_iter: int = 200) -> FlexuralResult:
    """Nominal flexural resistance by the strain-compatibility approach
    (5.6.3.2.5) on the actual coordinate data -- the calculation the Midas
    guide walks through by hand.

    The extreme fibers come straight from the outline coordinates (top
    fiber in compression for sagging, bottom for hogging).  A linear
    strain field pinned at ``eps_cu`` crushes the compression fiber; the
    neutral-axis depth ``c`` is iterated (bisection -- brackets the same
    root the guide's H/2 start walks to) until

        C_c + C_s = T_s + T_ps

    Concrete uses the rectangular stress block (alpha1 = 0.85, 5.6.2.2
    for f'c <= 10 ksi; beta1 per 5.6.2.2) integrated over the *actual*
    solid band, so flanges, tapers, and voids are handled exactly.  Mild
    steel is elastic-perfectly-plastic; bars and tendons inside the
    stress block are credited back the displaced concrete.  Tendon strain
    is the effective-prestress strain ``f_pe / e_p`` plus the bending
    change ``eps_cu * (d_p - c) / c`` (concrete decompression strain
    neglected), with stress from the Grade 270 power formula.

    ``eps_t`` is reported at the extreme tension steel -- the tendon/bar
    the guide identifies as closest to the extreme tension fiber -- and
    feeds :func:`~civilpy.structural.aashto.lrfd.prestressed.phi_flexure_ps`.

    **Composite sections**: pass the CIP deck/topping as ``topping`` (see
    :func:`composite_topping`) with its own ``topping_f_c`` (PSBD-1-25
    general notes: 4.5 ksi).  The extreme fibers span the combined
    section, the compression block is integrated per material, and
    ``beta1`` is taken from the concrete at the extreme compression
    fiber (the topping for sagging, the girder for hogging).

    ``displaced_concrete_credit`` deducts 0.85 f'c from steel inside the
    stress block; turn it off to reproduce hand calcs that take C_s as a
    bare A_s' * f_s'.  TODO(midas-api): confirm which convention Midas
    uses before check()-ing its reinforcement forces.

    Units: kips, inches, ksi; ``m_n`` reported in kip-ft.
    """
    if bending not in ("sagging", "hogging"):
        raise ValueError(f"bending must be 'sagging' or 'hogging', "
                         f"not {bending!r}")
    if (topping is None) != (topping_f_c is None):
        raise ValueError("pass topping and topping_f_c together")
    from civilpy.structural.aashto.lrfd.concrete import beta1
    from civilpy.structural.aashto.lrfd.prestressed import phi_flexure_ps
    from civilpy.structural.steel import Rebar

    parts = [(shape, f_c)]
    if topping is not None:
        parts.append((topping, topping_f_c))
    z_bot = min(extreme_fibers(s)[0] for s, _ in parts)
    z_top = max(extreme_fibers(s)[1] for s, _ in parts)
    height = z_top - z_bot

    def u_of(z):        # depth below the extreme compression fiber
        return z_top - z if bending == "sagging" else z - z_bot

    def fc_at(z):       # concrete strength of the part holding depth z
        for s, fc_i in parts:
            lo_, hi_ = extreme_fibers(s)
            if lo_ <= z <= hi_:
                return fc_i
        return f_c

    tendons = [(u_of(z), strands.strand_area, z)
               for _, z in strands.points] if strands else []
    bars = [(u_of(b.z), float(Rebar(b.size).area.magnitude), b.z)
            for b in rebar.bars] if rebar else []
    if not tendons and not bars:
        raise ValueError("no strands or rebar -- nothing to resist tension")
    # beta1 of the concrete at the extreme compression fiber
    fiber_z = z_top if bending == "sagging" else z_bot
    b1 = beta1(fc_at(fiber_z - 1e-9) if bending == "sagging"
               else fc_at(fiber_z + 1e-9))
    eps_pe = f_pe / e_p

    def forces(c, detail=False):
        a = b1 * c
        c_c = m_cc = 0.0
        for s, fc_i in parts:
            area, u_c = _band_area_moment(s, a, bending, z_bot, z_top)
            c_c += 0.85 * fc_i * area
            m_cc += 0.85 * fc_i * area * u_c
        fibers = []
        t_s = m_s = 0.0
        for u, a_s, z in bars:
            eps = eps_cu * (u - c) / c
            f = min(max(e_s * eps, -f_y), f_y)
            force = a_s * f
            if displaced_concrete_credit and u < a:
                force += a_s * 0.85 * fc_at(z)
            t_s += force
            m_s += force * u
            if detail:
                fibers.append(FiberForce("bar", u, eps, f, force))
        t_ps = m_ps = 0.0
        for u, a_p, z in tendons:
            eps = eps_pe + eps_cu * (u - c) / c
            f = strand_stress_270(eps)
            force = a_p * f
            if displaced_concrete_credit and u < a:
                force += a_p * 0.85 * fc_at(z)
            t_ps += force
            m_ps += force * u
            if detail:
                fibers.append(FiberForce("tendon", u, eps, f, force))
        residual = t_s + t_ps - c_c         # >0 -> too much tension
        m_n = (m_s + m_ps - m_cc) / 12.0
        return residual, c_c, t_s, t_ps, m_n, fibers

    lo, hi = 1e-6 * height, height
    if forces(hi)[0] > 0.0:
        raise ValueError(
            "tension exceeds concrete capacity with the neutral axis at "
            "the full section depth -- section is over-reinforced beyond "
            "the stress-block model's range")
    it = 0
    for it in range(1, max_iter + 1):
        c = (lo + hi) / 2.0
        residual = forces(c)[0]
        if abs(residual) < 1e-6 or (hi - lo) < 1e-12 * height:
            break
        if residual > 0.0:
            lo = c
        else:
            hi = c
    c = (lo + hi) / 2.0
    residual, c_c, t_s, t_ps, m_n, fibers = forces(c, detail=True)

    d_t = max(u for u, _, _ in tendons + bars)
    eps_t = eps_cu * (d_t - c) / c
    if tendons:
        u_ext = max(u for u, _, _ in tendons)
        f_ps_ext = strand_stress_270(eps_pe + eps_cu * (u_ext - c) / c)
    else:
        f_ps_ext = 0.0
    return FlexuralResult(
        bending=bending, c_in=c, a_in=b1 * c, d_t_in=d_t, eps_t=eps_t,
        phi=phi_flexure_ps(eps_t), m_n_kipft=m_n, c_c_kips=c_c,
        t_ps_kips=t_ps, t_s_kips=t_s, f_ps_extreme_ksi=f_ps_ext,
        residual_kips=residual, iterations=it,
        bar_forces=tuple(f for f in fibers if f.kind == "bar"),
        tendon_forces=tuple(f for f in fibers if f.kind == "tendon"))


# ── Midas export ─────────────────────────────────────────────────────────
#: Inches per unit of a model's ``UNIT`` DIST setting -- the factor that
#: takes these inch polygons into the model's own length unit.
_LENGTH_SCALE = {"in": 1.0, "inch": 1.0, "inches": 1.0,
                 "ft": 1.0 / 12.0, "feet": 1.0 / 12.0, "foot": 1.0 / 12.0,
                 "m": 0.0254, "meter": 0.0254, "metre": 0.0254,
                 "mm": 25.4, "cm": 2.54}


def _length_scale(length_unit: str) -> float:
    try:
        return _LENGTH_SCALE[str(length_unit).strip().lower()]
    except KeyError:
        raise ValueError(
            f"unsupported model length unit {length_unit!r}; expected one of "
            f"{sorted(set(_LENGTH_SCALE))}") from None


def _ccw(poly: tuple[Point, ...]) -> tuple[Point, ...]:
    """``poly`` wound counter-clockwise (positive shoelace area)."""
    a = sum(y0 * z1 - y1 * z0 for (y0, z0), (y1, z1)
            in zip(poly, poly[1:] + poly[:1]))
    return poly if a >= 0 else tuple(reversed(poly))


def midas_section_payload(shape: PSCShape, *, name: str | None = None,
                          web_thickness: float | None = None,
                          length_unit: str = "in") -> dict:
    """A ``PUT /db/SECT`` PSC-VALUE section payload carrying the shape's
    exact outline and void polygons (verified against live Civil NX
    2026-07-27: the value section reproduced the parametric CB27-48's
    area and inertia to 0.01%).

    The outer polygon goes CCW as stored, voids reversed to CW.  With the
    default center-center offset the element axis lands on the section
    centroid -- the reference the tendon builders below assume.
    ``web_thickness`` is the summed web width for the shear checks
    (defaults to the solid width at mid-depth).

    ``length_unit`` is the **model's** ``UNIT`` table DIST, not the
    shape's: these polygons are always in inches, and MIDAS applies one
    length unit to every geometric quantity in a model, section
    coordinates included.  Sending inches into a model whose DIST is FT
    gives a 12x oversized, self-intersecting section that still stores
    without complaint -- so pass the hub's own ``units.length``.

    Two constraints MIDAS enforces on the polygon, both established by
    bisecting a rejected section against a live Civil NX (2026-07-29).
    Neither is documented, and both surface as the same unhelpful
    ``"[Error] Section input data contain errors."``:

    * **the outline must rest on z = 0.**  A polygon whose bottom fiber
      sits above the origin is refused -- a shear key drawn at its true
      elevation in the beam (z = 5 in to 27 in) fails, and the identical
      polygon shifted down 5 in is accepted.  This function translates
      the shape for you, which costs nothing: the default center-center
      offset puts the element axis on the centroid either way, so a shape
      may be drawn at whatever elevation makes sense to a human.
    * **the winding must be counter-clockwise.**  The same outline
      reversed is refused rather than silently normalized.
    """
    scale = _length_scale(length_unit)
    z_base = min(z for _, z in shape.outline)
    outline = _ccw(shape.outline)
    z0, z1 = ((v - z_base) * scale for v in extreme_fibers(shape))
    ys = [y * scale for y, _ in outline]
    if web_thickness is None:
        web_thickness = sum(b - a for a, b in
                            solid_intervals(shape, (z0 + z1) / 2.0 / scale
                                            + z_base))
    web_thickness *= scale
    outer = [{"X": y * scale, "Y": (z - z_base) * scale} for y, z in outline]
    inner = [[{"X": y * scale, "Y": (z - z_base) * scale}
              for y, z in reversed(_ccw(v))] for v in shape.voids]
    sect_i = {"SECT_NAME": "",
              "vSIZE": [z1 - z0, max(ys) - min(ys),
                        web_thickness / 2.0, web_thickness / 2.0],
              "OUTER_POLYGON": [{"VERTEX": outer}]}
    if inner:
        sect_i["INNER_POLYGON"] = [{"VERTEX": v} for v in inner]
    return {
        "SECTTYPE": "PSC", "SECT_NAME": name or shape.name,
        "CALC_OPT": True,
        "SECT_BEFORE": {
            "SHAPE": "VALU", "SECT_I": sect_i,
            "SHEAR_CHK": True,
            "SHEAR_CHK_POS": [[z0, (z0 + z1) / 2.0, z1], [0, 0, 0]],
            "USE_AUTO_QY": [[True, True, True], [False, False, False]],
            "WEB_THICK": [web_thickness, 0],
            "USE_WEB_THICK_SHEAR": [[True, True, True],
                                    [False, False, False]],
            "OFFSET_PT": "CC", "OFFSET_CENTER": 0, "USER_OFFSET_REF": 0,
            "HORZ_OFFSET_OPT": 0, "USERDEF_OFFSET_YI": 0.0,
            "VERT_OFFSET_OPT": 0, "USERDEF_OFFSET_ZI": 0.0,
            "USE_SHEAR_DEFORM": True, "USE_WARPING_EFFECT": False,
        },
    }


def midas_tendon_payloads(layout: StrandLayout, *, elems: list[int],
                          length_in: float, matl_id: int,
                          jack_stress_ksi: float,
                          load_case: str = "PS",
                          z_centroid: float | None = None,
                          name_prefix: str = "S") -> dict:
    """The three tendon table payloads for a straight pretensioned
    pattern: ``TDNT`` (property), ``TDNA`` (profiles), ``TDPL``
    (prestress), ready for ``PUT /db/<table>``.

    Conventions verified against live Civil NX (2026-07-27):

    * STRAIGHT profiles take model coordinates -- with the value section
      at its default center-center offset the element axis is the section
      centroid, so profile z = strand z minus ``z_centroid`` (defaults to
      the mid-height of the outline, exact for symmetric-void boxes;
      pass the computed centroid for unsymmetric shapes).
    * strand AREA lives on the property, one property for the pattern.
    * ``D_AREA`` must be > 0 even for pretension (the strand diameter
      serves).
    * relaxation: Magura-45 (``RM`` 0, ``RV`` 45) with US/YS in ksi.
    """
    z0, z1 = extreme_fibers(layout.shape)
    if z_centroid is None:
        z_centroid = (z0 + z1) / 2.0
    tdnt = {"1": {
        "NAME": f"{layout.strand_diameter:g}-270LR", "TYPE": "INTERNAL",
        "LT": "PRE", "MATL": matl_id, "AREA": layout.strand_area,
        "D_AREA": layout.strand_diameter, "ASB": 0.0, "ASE": 0.0,
        "bBONDED": True, "ALPHA": 0.0,
        "RM": 0, "RV": 45, "US": layout.f_pu,
        "YS": 0.9 * layout.f_pu, "FF": 0.0, "WF": 0.0,
    }}
    tdna, tdpl = {}, {}
    for i, (y, z) in enumerate(layout.points, start=1):
        name = f"{name_prefix}{i:02d}"
        zc = z - z_centroid
        tdna[str(i)] = {
            "NAME": name, "TDN_PROP": 1, "ELEM": list(elems),
            "BELENG": 0.0, "ELENG": 0.0, "CURVE": "SPLINE",
            "INPUT": "3D", "TDN_GRUP": 0, "LENG_OPT": "AUTO2",
            "BLEN": 0.0, "ELEN": 0.0, "bTP": False, "CNT": 0,
            "DeBondBLEN": 0.0, "DeBondELEN": 0.0, "SHAPE": "STRAIGHT",
            "IP": [0.0, 0.0, 0.0], "AXIS": "X", "VEC": [0.0, 0.0],
            "XAR_ANGLE": 0.0, "bPJ": True, "GR_AXIS": "X",
            "GR_ANGLE": 0.0,
            "PROF": [{"PT": [0.0, y, zc], "bFIX": False, "R": [0, 0]},
                     {"PT": [length_in, y, zc], "bFIX": False,
                      "R": [0, 0]}],
        }
        tdpl[str(i)] = {"ITEMS": [{
            "ID": 1, "LCNAME": load_case, "GROUP_NAME": "",
            "TENDON_NAME": name, "TYPE": "STRESS", "ORDER": "BEGIN",
            "BEGIN": jack_stress_ksi, "END": 0.0, "GROUTING": 0,
        }]}
    return {"TDNT": tdnt, "TDNA": tdna, "TDPL": tdpl}


def midas_strand_coordinates(layout: StrandLayout, *,
                             origin: str = "centroid") -> list[dict]:
    """Strand positions as coordinate rows.

    ``origin="centroid"`` measures z from the section centroid (requires
    a published Yb), ``"soffit"`` from the beam bottom.  Verified against
    live Civil NX (2026-07-27): centroid-origin rows are exactly what the
    TDNA STRAIGHT tendon profiles take -- see
    :func:`midas_tendon_payloads` for the full table payloads.
    """
    if origin not in ("centroid", "soffit"):
        raise ValueError(f"origin must be 'centroid' or 'soffit', not {origin!r}")
    dz = layout.shape.yb_in if origin == "centroid" else 0.0
    if dz is None:
        raise ValueError(f"{layout.shape.name} has no published Yb; "
                         "use origin='soffit'")
    return [{"ID": i + 1, "Y": y, "Z": z - dz, "AREA": layout.strand_area}
            for i, (y, z) in enumerate(layout.points)]


def midas_rebar_coordinates(layout: RebarLayout, *,
                            origin: str = "centroid") -> list[dict]:
    """Rebar positions for the Midas PSC-section reinforcement wizard.

    The z-origin conventions match :func:`midas_strand_coordinates`
    (verified live 2026-07-27).  The PSC *design* rebar tables themselves
    (Section Manager longitudinal/stirrup input) are not exposed through
    the known API surface -- entry stays UI-side; these rows are the
    hand-off data.  TODO(midas-api): revisit if a design-module endpoint
    surfaces (official JSON manual's design section).
    """
    if origin not in ("centroid", "soffit"):
        raise ValueError(f"origin must be 'centroid' or 'soffit', not {origin!r}")
    dz = layout.shape.yb_in if origin == "centroid" else 0.0
    if dz is None:
        raise ValueError(f"{layout.shape.name} has no published Yb; "
                         "use origin='soffit'")
    from civilpy.structural.steel import Rebar
    return [{"ID": i + 1, "Y": b.y, "Z": b.z - dz, "SIZE": f"#{b.size}",
             "AREA": float(Rebar(b.size).area.magnitude)}
            for i, b in enumerate(layout.bars)]
