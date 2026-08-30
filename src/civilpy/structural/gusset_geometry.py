#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.
"""Geometry model for riveted / bolted truss gusset plates.

Everything a gusset-plate rating needs before any code check is applied is
a *geometric* quantity: where the fasteners of each member end are, the
Whitmore effective width they define, the unbraced lengths from the
Whitmore section to the neighbouring members, the block-shear and
combined-plane failure paths, the gross and net section along any cut, and
-- for as-inspected ratings -- how much plate is left where.  This module
computes those from coordinates so the rating functions in
:mod:`civilpy.structural.aashto.lrfd.gusset` only see areas and lengths.

Units: inches throughout; angles in degrees; areas in in^2.

Conventions
-----------
* A :class:`GussetPlate` is one plate (one side of the joint) with an
  outline polygon in plate coordinates (x to the right, y up, origin
  anywhere), a nominal thickness and material.
* A :class:`MemberEnd` is one member framing into the plate: its work
  point, its axis direction (unit vector pointing from the joint *out
  along the member*), and the coordinates of the fasteners that connect it
  to this plate.
* "Along the member" is measured by ``s`` (projection on the axis, larger
  ``s`` = farther from the joint); "across" by ``c``.  The **first** row of
  fasteners is the one farthest from the joint (largest ``s``, where the
  member's force first enters the plate); the **last** row is the one
  nearest the joint (smallest ``s``), which is where the Whitmore section
  is taken.
* Whitmore effective width (FHWA-IF-09-014 §3.4, AASHTO LRFD 6.14.2.8.4):
  width across the first row of fasteners plus the 30-degree spread over
  the connection length to the last row.
* Unbraced lengths L1, Lmid, L2 (same references): from the ends and the
  midpoint of the Whitmore section, parallel to the member axis toward the
  joint, to the nearest fastener line of an adjacent member or the plate
  edge.

Section loss is modelled by a :class:`ThicknessField`: a nominal thickness
with any number of patches (polygons) of reduced remaining thickness.  All
area functions integrate thickness along the cut, so a plate with a
corrosion patch through the Whitmore section simply yields a smaller area.
:func:`thickness_field_from_points` turns a surface scan (any point cloud
of the plate face, e.g. from an Artec Leo mesh brought in through Rhino)
into such a field by fitting the undamaged plane and reading pit depth.

No third-party dependencies; :mod:`numpy` is used only in the scan
helpers and imported lazily.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

Point = tuple[float, float]
Polygon = list[Point]

TAN30 = math.tan(math.radians(30.0))


# --------------------------------------------------------------------------- #
# basic 2-D helpers
# --------------------------------------------------------------------------- #
def polygon_area(poly: Sequence[Point]) -> float:
    """Signed shoelace area (positive for counter-clockwise)."""
    a = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def point_in_polygon(pt: Point, poly: Sequence[Point]) -> bool:
    """Even-odd rule; points on an edge count as inside."""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        # on-edge test
        cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
        if abs(cross) < 1e-9 and min(x0, x1) - 1e-9 <= x <= max(x0, x1) + 1e-9 \
                and min(y0, y1) - 1e-9 <= y <= max(y0, y1) + 1e-9:
            return True
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xi:
                inside = not inside
    return inside


def _seg_intersections(p0: Point, p1: Point, poly: Sequence[Point]) -> list[float]:
    """Parameters t in [0,1] where segment p0->p1 crosses the polygon edges."""
    ts = []
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        den = dx * ey - dy * ex
        if abs(den) < 1e-12:
            continue
        t = ((ax - x0) * ey - (ay - y0) * ex) / den
        u = ((ax - x0) * dy - (ay - y0) * dx) / den
        if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
            ts.append(min(max(t, 0.0), 1.0))
    return sorted(ts)


def clip_segment(p0: Point, p1: Point, poly: Sequence[Point]) -> list[tuple[Point, Point]]:
    """Portions of segment p0->p1 that lie inside ``poly``."""
    ts = [0.0] + _seg_intersections(p0, p1, poly) + [1.0]
    out = []
    for a, b in zip(ts, ts[1:]):
        if b - a < 1e-9:
            continue
        m = (a + b) / 2
        mid = (p0[0] + m * (p1[0] - p0[0]), p0[1] + m * (p1[1] - p0[1]))
        if point_in_polygon(mid, poly):
            out.append(((p0[0] + a * (p1[0] - p0[0]), p0[1] + a * (p1[1] - p0[1])),
                        (p0[0] + b * (p1[0] - p0[0]), p0[1] + b * (p1[1] - p0[1]))))
    return out


def _length(p0: Point, p1: Point) -> float:
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1])


def _unit(v: Point) -> Point:
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def _perp(u: Point) -> Point:
    return (-u[1], u[0])


def _ray_hits_segment(p0: Point, p1: Point, a: Point, b: Point, widen: float = 0.0):
    """Distance from p0 along p0->p1 to the crossing with segment a-b (the
    segment extended by ``widen`` at both ends); None when they do not cross."""
    if widen:
        u = _unit((b[0] - a[0], b[1] - a[1])) if _length(a, b) > 1e-9 else (0.0, 0.0)
        a = (a[0] - widen * u[0], a[1] - widen * u[1])
        b = (b[0] + widen * u[0], b[1] + widen * u[1])
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ex, ey = b[0] - a[0], b[1] - a[1]
    den = dx * ey - dy * ex
    if abs(den) < 1e-12:
        return None
    t = ((a[0] - p0[0]) * ey - (a[1] - p0[1]) * ex) / den
    u = ((a[0] - p0[0]) * dy - (a[1] - p0[1]) * dx) / den
    if 0 <= t <= 1 and -1e-9 <= u <= 1 + 1e-9:
        return t * math.hypot(dx, dy)
    return None


def dist_point_segment(pt: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    px, py = pt
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


# --------------------------------------------------------------------------- #
# section loss
# --------------------------------------------------------------------------- #
@dataclass
class ThicknessPatch:
    """A region of the plate with a reduced remaining thickness."""
    polygon: Polygon
    t_remaining: float
    note: str = ""


@dataclass
class ThicknessField:
    """Nominal plate thickness with corrosion patches.

    ``t_at(pt)`` returns the remaining thickness at a point (the thinnest
    patch containing it, else the nominal).  Line and area integrals sample
    the field; ``n_samples`` controls the resolution of a line integral."""
    t_nominal: float
    patches: list[ThicknessPatch] = field(default_factory=list)
    n_samples: int = 200

    def t_at(self, pt: Point) -> float:
        t = self.t_nominal
        for p in self.patches:
            if point_in_polygon(pt, p.polygon):
                t = min(t, p.t_remaining)
        return max(t, 0.0)

    def line_area(self, p0: Point, p1: Point) -> float:
        """Integral of thickness along the segment (in^2)."""
        L = _length(p0, p1)
        if L < 1e-12:
            return 0.0
        n = max(2, self.n_samples)
        total = 0.0
        for i in range(n):
            m = (i + 0.5) / n
            total += self.t_at((p0[0] + m * (p1[0] - p0[0]), p0[1] + m * (p1[1] - p0[1])))
        return total / n * L

    def min_t_along(self, p0: Point, p1: Point) -> float:
        n = max(2, self.n_samples)
        return min(self.t_at((p0[0] + (i + 0.5) / n * (p1[0] - p0[0]),
                              p0[1] + (i + 0.5) / n * (p1[1] - p0[1]))) for i in range(n))

    @property
    def is_uniform(self) -> bool:
        return not self.patches


# --------------------------------------------------------------------------- #
# model
# --------------------------------------------------------------------------- #
@dataclass
class Fastener:
    x: float
    y: float
    diameter: float = 1.0           # rivet/bolt nominal diameter
    hole: float | None = None       # hole diameter for net-area deductions
    kind: str = "rivet"             # "rivet" | "bolt"

    @property
    def pt(self) -> Point:
        return (self.x, self.y)

    @property
    def hole_dia(self) -> float:
        # AASHTO 6.8.3 / 10.16.14.6: nominal hole + 1/16 (1/8 over the fastener)
        return self.hole if self.hole is not None else self.diameter + 0.125


@dataclass
class MemberEnd:
    """One member framing into the plate."""
    name: str                                   # e.g. "U0L1"
    work_point: Point                           # joint work point (member axes meet here)
    axis: Point                                 # unit vector, joint -> along member
    fasteners: list[Fastener]
    member_type: str = "diagonal"               # chord | diagonal | vertical
    is_chord: bool = False
    spliced_at_joint: bool = False              # chord ends spliced at joint centre
    milled_butt: bool = False

    def __post_init__(self):
        self.axis = _unit(self.axis)

    # -- projections -------------------------------------------------------
    def s_of(self, pt) -> float:
        """Distance along the member axis from the work point (accepts a
        point or a :class:`Fastener`)."""
        pt = getattr(pt, "pt", pt)
        return (pt[0] - self.work_point[0]) * self.axis[0] + (pt[1] - self.work_point[1]) * self.axis[1]

    def c_of(self, pt) -> float:
        """Offset across the member axis (accepts a point or a Fastener)."""
        pt = getattr(pt, "pt", pt)
        n = _perp(self.axis)
        return (pt[0] - self.work_point[0]) * n[0] + (pt[1] - self.work_point[1]) * n[1]

    def point_at(self, s: float, c: float) -> Point:
        n = _perp(self.axis)
        return (self.work_point[0] + s * self.axis[0] + c * n[0],
                self.work_point[1] + s * self.axis[1] + c * n[1])

    def rows(self, tol: float = 0.35) -> list[list[Fastener]]:
        """Fasteners grouped into rows across the member (same ``s``), ordered
        from the joint outward (increasing ``s``)."""
        fs = sorted(self.fasteners, key=self.s_of)
        rows: list[list[Fastener]] = []
        for f in fs:
            if rows and abs(self.s_of(f) - self.s_of(rows[-1][0])) <= tol:
                rows[-1].append(f)
            else:
                rows.append([f])
        return rows

    @property
    def n_fasteners(self) -> int:
        return len(self.fasteners)

    @property
    def s_first(self) -> float:
        """Row farthest from the joint (load enters here)."""
        return max(self.s_of(f) for f in self.fasteners)

    @property
    def s_last(self) -> float:
        """Row nearest the joint (Whitmore section)."""
        return min(self.s_of(f) for f in self.fasteners)

    @property
    def connection_length(self) -> float:
        return self.s_first - self.s_last

    def first_row(self, tol: float = 0.35) -> list[Fastener]:
        return [f for f in self.fasteners if self.s_of(f) >= self.s_first - tol]

    def last_row(self, tol: float = 0.35) -> list[Fastener]:
        return [f for f in self.fasteners if self.s_of(f) <= self.s_last + tol]

    def first_row_width(self, tol: float = 0.35) -> float:
        cs = [self.c_of(f) for f in self.first_row(tol)]
        return max(cs) - min(cs)

    def first_row_center(self, tol: float = 0.35) -> float:
        cs = [self.c_of(f) for f in self.first_row(tol)]
        return (max(cs) + min(cs)) / 2

    # -- Whitmore ----------------------------------------------------------
    def whitmore_width(self, tol: float = 0.35) -> float:
        """b = (first-row width) + 2 * L * tan 30."""
        return self.first_row_width(tol) + 2.0 * self.connection_length * TAN30

    def whitmore_segment(self, tol: float = 0.35) -> tuple[Point, Point]:
        """End points of the Whitmore section line (unclipped)."""
        b = self.whitmore_width(tol)
        c0 = self.first_row_center(tol)
        return self.point_at(self.s_last, c0 - b / 2), self.point_at(self.s_last, c0 + b / 2)

    def fastener_lines(self, tol: float = 0.35) -> list[tuple[Point, Point]]:
        """Every straight line of two or more fasteners (rows across the member
        and columns along it) as a segment between its extreme fasteners --
        the 'fastener lines' that bound Whitmore unbraced lengths."""
        segs = []
        for key in (self.s_of, self.c_of):
            groups: list[list[Fastener]] = []
            for f in sorted(self.fasteners, key=key):
                if groups and abs(key(f) - key(groups[-1][0])) <= tol:
                    groups[-1].append(f)
                else:
                    groups.append([f])
            other = self.c_of if key is self.s_of else self.s_of
            for g in groups:
                if len(g) >= 2:
                    g = sorted(g, key=other)
                    segs.append((g[0].pt, g[-1].pt))
        return segs

    def column_lines(self, tol: float = 0.35) -> list[float]:
        """Distinct fastener columns (values of ``c``), outermost first/last."""
        cs = sorted(self.c_of(f) for f in self.fasteners)
        cols: list[float] = []
        for c in cs:
            if not cols or abs(c - cols[-1]) > tol:
                cols.append(c)
        return cols


@dataclass
class GussetPlate:
    """One gusset plate (one side of the joint)."""
    outline: Polygon
    thickness: ThicknessField | float
    fy: float = 45.0
    fu: float = 70.0
    label: str = ""

    def __post_init__(self):
        if not isinstance(self.thickness, ThicknessField):
            self.thickness = ThicknessField(float(self.thickness))

    @property
    def t(self) -> float:
        return self.thickness.t_nominal

    @property
    def area(self) -> float:
        return abs(polygon_area(self.outline))

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.outline]
        ys = [p[1] for p in self.outline]
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def gross_width(self) -> float:
        x0, _, x1, _ = self.bbox
        return x1 - x0

    @property
    def gross_height(self) -> float:
        _, y0, _, y1 = self.bbox
        return y1 - y0

    def edge_lengths(self) -> list[float]:
        n = len(self.outline)
        return [_length(self.outline[i], self.outline[(i + 1) % n]) for i in range(n)]

    # -- cut-line areas ----------------------------------------------------
    def gross_area_along(self, p0: Point, p1: Point) -> float:
        """Integral of thickness over the parts of segment p0-p1 inside the plate."""
        return sum(self.thickness.line_area(a, b) for a, b in clip_segment(p0, p1, self.outline))

    def gross_length_along(self, p0: Point, p1: Point) -> float:
        return sum(_length(a, b) for a, b in clip_segment(p0, p1, self.outline))

    def net_area_along(self, p0: Point, p1: Point, fasteners: Iterable[Fastener],
                       tol: float = 0.35) -> float:
        """Gross area along the cut minus the holes whose centres lie on it."""
        gross = self.gross_area_along(p0, p1)
        deduct = 0.0
        for f in fasteners:
            if dist_point_segment(f.pt, p0, p1) <= tol:
                deduct += f.hole_dia * self.thickness.t_at(f.pt)
        return max(gross - deduct, 0.0)


@dataclass
class GussetJoint:
    """A joint: one or two plates and the member ends framing in.

    ``members`` are shared by both plates (same fastener pattern assumed on
    inside and outside plates unless ``members_outside`` is given)."""
    name: str
    work_point: Point
    inside: GussetPlate
    outside: GussetPlate | None = None
    members: list[MemberEnd] = field(default_factory=list)
    members_outside: list[MemberEnd] | None = None
    fastener_diameter: float = 1.0

    @property
    def plates(self) -> list[GussetPlate]:
        return [p for p in (self.inside, self.outside) if p is not None]

    def member(self, name: str) -> MemberEnd:
        for m in self.members:
            if m.name == name:
                return m
        raise KeyError(name)

    def all_fasteners(self, exclude: MemberEnd | None = None) -> list[Fastener]:
        return [f for m in self.members if m is not exclude for f in m.fasteners]

    # -- derived quantities ------------------------------------------------
    def whitmore(self, member: MemberEnd | str, plate: GussetPlate | None = None) -> dict:
        """Whitmore section of ``member`` on ``plate`` (default: inside plate).

        Returns width b, the clipped section length (b limited by the plate
        outline), gross and net areas (thickness-integrated), and the
        section end points."""
        m = self.member(member) if isinstance(member, str) else member
        plate = plate or self.inside
        p0, p1 = m.whitmore_segment()
        segs = clip_segment(p0, p1, plate.outline)
        length = sum(_length(a, b) for a, b in segs)
        gross = plate.gross_area_along(p0, p1)
        net = plate.net_area_along(p0, p1, m.fasteners)
        return {"b": m.whitmore_width(), "length_in_plate": length,
                "b_effective": min(m.whitmore_width(), length), "A_gross": gross,
                "A_net": net, "p0": p0, "p1": p1, "segments": segs}

    def unbraced_lengths(self, member: MemberEnd | str, plate: GussetPlate | None = None,
                         c_tol: float = 1.0) -> dict:
        """Unbraced lengths from the Whitmore section toward the joint.

        From the two ends and the midpoint of the Whitmore section, rays run
        parallel to the member axis toward the joint until they meet the
        nearest fastener *row* of another member (the segment between that
        row's extreme fasteners, widened by ``c_tol``) or leave the plate.
        Returns L1, Lmid, L2, their average ``Lc_avg`` (FHWA-IF-09-014) and
        the minimum ``Lc_min`` (what a single 'unbraced length below the
        member' entry, e.g. the ODOT 2012 sheet, records)."""
        m = self.member(member) if isinstance(member, str) else member
        plate = plate or self.inside
        p0, p1 = m.whitmore_segment()
        # clip the Whitmore section to the plate so the end rays start inside it
        segs = clip_segment(p0, p1, plate.outline)
        if segs:
            p0, p1 = segs[0][0], segs[-1][1]
        lines = [seg for o in self.members if o is not m for seg in o.fastener_lines()]
        out = {}
        for key, frac in (("L1", 0.02), ("Lmid", 0.5), ("L2", 0.98)):
            start = (p0[0] + frac * (p1[0] - p0[0]), p0[1] + frac * (p1[1] - p0[1]))
            s0, c0 = m.s_of(start), m.c_of(start)
            far = m.point_at(s0 - 1e4, c0)
            best = None
            for a, b in lines:
                t = _ray_hits_segment(start, far, a, b, widen=c_tol)
                if t is not None and t > 1e-6:
                    best = t if best is None else min(best, t)
            edge = sum(_length(a, b) for a, b in clip_segment(start, far, plate.outline))
            out[key] = max(min(best, edge) if best is not None else edge, 0.0)
        out["Lc_avg"] = (out["L1"] + out["Lmid"] + out["L2"]) / 3.0
        out["Lc_min"] = min(out["L1"], out["Lmid"], out["L2"])
        out["Lc"] = out["Lc_avg"]
        return out

    def block_shear(self, member: MemberEnd | str, plate: GussetPlate | None = None,
                    tol: float = 0.35) -> dict:
        """Block-shear (member tear-out) geometry for one plate: two shear
        planes along the outer fastener columns from the first row to the
        last row, and the tension plane across the last row.

        Returns Avg, Avn, Atg, Atn (thickness-integrated) and the polygon."""
        m = self.member(member) if isinstance(member, str) else member
        plate = plate or self.inside
        cols = m.column_lines(tol)
        c_lo, c_hi = cols[0], cols[-1]
        s_first, s_last = m.s_first, m.s_last
        # shear planes: from the first row to the last row along each outer column
        a_vg = 0.0
        a_vn = 0.0
        for c in (c_lo, c_hi):
            p_out = m.point_at(s_first, c)
            p_in = m.point_at(s_last, c)
            a_vg += plate.gross_area_along(p_out, p_in)
            a_vn += plate.net_area_along(p_out, p_in, m.fasteners, tol)
            # net-area convention: the hole on the tension-plane row counts half on the shear plane
            for f in m.fasteners:
                if abs(m.c_of(f) - c) <= tol and abs(m.s_of(f) - s_last) <= tol:
                    a_vn += 0.5 * f.hole_dia * plate.thickness.t_at(f.pt)
        q0 = m.point_at(s_last, c_lo)
        q1 = m.point_at(s_last, c_hi)
        a_tg = plate.gross_area_along(q0, q1)
        # tension plane: the two corner holes count half each
        a_tn = a_tg
        for f in m.fasteners:
            if abs(m.s_of(f) - s_last) <= tol:
                frac = 0.5 if (abs(m.c_of(f) - c_lo) <= tol or abs(m.c_of(f) - c_hi) <= tol) else 1.0
                a_tn -= frac * f.hole_dia * plate.thickness.t_at(f.pt)
        poly = [m.point_at(s_first, c_lo), m.point_at(s_first, c_hi), q1, q0]
        return {"A_vg": a_vg, "A_vn": max(a_vn, 0.0), "A_tg": a_tg, "A_tn": max(a_tn, 0.0),
                "polygon": poly, "shear_length": s_first - s_last, "tension_width": c_hi - c_lo}

    def section_along(self, p0: Point, p1: Point, plate: GussetPlate | None = None) -> dict:
        """Gross/net area and length of an arbitrary cut through a plate."""
        plate = plate or self.inside
        fs = self.all_fasteners()
        return {"length": plate.gross_length_along(p0, p1),
                "A_gross": plate.gross_area_along(p0, p1),
                "A_net": plate.net_area_along(p0, p1, fs)}

    def horizontal_section(self, y: float, plate: GussetPlate | None = None) -> dict:
        plate = plate or self.inside
        x0, _, x1, _ = plate.bbox
        return self.section_along((x0 - 1, y), (x1 + 1, y), plate)

    def vertical_section(self, x: float, plate: GussetPlate | None = None) -> dict:
        plate = plate or self.inside
        _, y0, _, y1 = plate.bbox
        return self.section_along((x, y0 - 1), (x, y1 + 1), plate)

    def max_unsupported_edge(self, plate: GussetPlate | None = None) -> float:
        """Longest free edge of the outline (edge-slenderness check input)."""
        plate = plate or self.inside
        return max(plate.edge_lengths())

    def summary(self, plate: GussetPlate | None = None) -> dict:
        plate = plate or self.inside
        out = {"joint": self.name, "plate": plate.label, "t": plate.t,
               "gross_width": plate.gross_width, "gross_height": plate.gross_height,
               "max_edge": self.max_unsupported_edge(plate), "members": {}}
        for m in self.members:
            w = self.whitmore(m, plate)
            lc = self.unbraced_lengths(m, plate)
            bs = self.block_shear(m, plate)
            out["members"][m.name] = {"n": m.n_fasteners, "L_conn": m.connection_length,
                                      "b_whitmore": w["b"], "A_whitmore_gross": w["A_gross"],
                                      "A_whitmore_net": w["A_net"], **lc,
                                      "A_vg": bs["A_vg"], "A_vn": bs["A_vn"], "A_tn": bs["A_tn"]}
        return out


# --------------------------------------------------------------------------- #
# builders
# --------------------------------------------------------------------------- #
def rectangular_grid(origin: Point, axis: Point, n_rows: int, n_cols: int,
                     pitch_s: float, pitch_c: float, diameter: float = 1.0,
                     offset_c: float = 0.0, kind: str = "rivet") -> list[Fastener]:
    """A rows x cols fastener grid starting at ``origin`` and running along
    ``axis`` (rows spaced ``pitch_s`` along, columns ``pitch_c`` across,
    centred on the axis line plus ``offset_c``)."""
    u = _unit(axis)
    n = _perp(u)
    out = []
    c_start = offset_c - (n_cols - 1) * pitch_c / 2
    for i in range(n_rows):
        for j in range(n_cols):
            s = i * pitch_s
            c = c_start + j * pitch_c
            out.append(Fastener(origin[0] + s * u[0] + c * n[0], origin[1] + s * u[1] + c * n[1],
                                diameter, kind=kind))
    return out


def polygon_from_bbox(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# --------------------------------------------------------------------------- #
# scan / point-cloud support (Artec Leo -> Rhino mesh -> thickness field)
# --------------------------------------------------------------------------- #
def fit_plane(points, robust_iters: int = 3, clip_sigma: float = 2.0):
    """Least-squares plane through a point cloud, re-fit after dropping
    outliers (pits) so the fitted plane is the *undamaged* surface.

    ``points`` is an (N, 3) array-like.  Returns (centroid, unit normal)."""
    import numpy as np
    P = np.asarray(points, dtype=float)
    keep = np.ones(len(P), dtype=bool)
    for _ in range(max(1, robust_iters)):
        Q = P[keep]
        c = Q.mean(axis=0)
        _, _, vt = np.linalg.svd(Q - c, full_matrices=False)
        n = vt[-1]
        d = (P - c) @ n
        sigma = d[keep].std() or 1e-9
        keep = np.abs(d - d[keep].mean()) < clip_sigma * sigma
    Q = P[keep]
    c = Q.mean(axis=0)
    _, _, vt = np.linalg.svd(Q - c, full_matrices=False)
    n = vt[-1]
    # orient the normal toward the side the points are scanned from (+ side)
    return c, n


def thickness_field_from_points(points, t_nominal: float, cell: float = 0.5,
                                min_depth: float = 0.03, plane=None,
                                axes=None, both_sides: bool = False) -> tuple[ThicknessField, dict]:
    """Build a :class:`ThicknessField` from a surface scan of one plate face.

    * ``points``: (N, 3) scan points of the face in any consistent units
      (inches expected).
    * The undamaged face plane is fitted robustly (pits are outliers), each
      point's depth below that plane is taken as local section loss, the
      depths are binned on a ``cell`` x ``cell`` grid in plate coordinates
      and every cell deeper than ``min_depth`` becomes a patch with
      ``t_remaining = t_nominal - depth`` (``- 2*depth`` when
      ``both_sides`` is set and only one face was scanned but symmetric
      loss is assumed).
    * ``axes``: optional (u, v) in-plane unit vectors to define plate x/y;
      default: the plane's principal directions.

    Returns the field and a dict with the fitted plane, the grid extents
    and a depth grid for plotting / Rhino export.  One-sided scans measure
    surface pitting only; through-thickness loss needs both faces or UT
    readings -- combine by passing the deeper of the two fields' patches."""
    import numpy as np
    P = np.asarray(points, dtype=float)
    if plane is None:
        c, n = fit_plane(P)
    else:
        c, n = plane
        c, n = np.asarray(c, float), np.asarray(n, float) / np.linalg.norm(plane[1])
    d = (P - c) @ n
    # depth = distance *below* the surface: scanned side is +n by construction
    if d.mean() > 0:
        n = -n
        d = -d
    depth = np.clip(-d, 0.0, None)
    if axes is None:
        _, _, vt = np.linalg.svd(P - c, full_matrices=False)
        u = vt[0] - (vt[0] @ n) * n
        u /= np.linalg.norm(u)
    else:
        u = np.asarray(axes[0], float)
        u = u - (u @ n) * n
        u /= np.linalg.norm(u)
    if u[int(np.argmax(np.abs(u)))] < 0:          # fix the SVD sign so plate x follows +X
        u = -u
    v = np.cross(n, u)
    if v[int(np.argmax(np.abs(v)))] < 0:
        v, n = -v, -n
        d = -d
        depth = np.clip(-d, 0.0, None)
    # plate coordinates are absolute projections (a scan already in plate
    # coordinates keeps its x/y), not centroid-relative
    X = P @ u
    Y = P @ v
    x0, y0 = X.min(), Y.min()
    nx = int(math.ceil((X.max() - x0) / cell)) + 1
    ny = int(math.ceil((Y.max() - y0) / cell)) + 1
    grid = np.zeros((ny, nx))
    count = np.zeros((ny, nx))
    ix = ((X - x0) / cell).astype(int)
    iy = ((Y - y0) / cell).astype(int)
    # max depth per cell (worst pit governs)
    np.maximum.at(grid, (iy, ix), depth)
    np.add.at(count, (iy, ix), 1)
    patches = []
    for j in range(ny):
        for i in range(nx):
            if count[j, i] and grid[j, i] >= min_depth:
                loss = grid[j, i] * (2.0 if both_sides else 1.0)
                poly = polygon_from_bbox(x0 + i * cell, y0 + j * cell, x0 + (i + 1) * cell, y0 + (j + 1) * cell)
                patches.append(ThicknessPatch(poly, max(t_nominal - loss, 0.0), f"scan depth {grid[j, i]:.3f}"))
    field_ = ThicknessField(t_nominal, patches)
    return field_, {"centroid": c, "normal": n, "u": u, "v": v, "x0": x0, "y0": y0,
                    "cell": cell, "depth_grid": grid, "count_grid": count}


def mesh_vertices_from_3dm(path: str, layer: str | None = None):
    """Vertices (N, 3) of all meshes in a Rhino .3dm (optionally one layer).
    Requires ``rhino3dm``; a scanner export brought into Rhino lands here.

    A ``layer`` that does not exist is an error rather than a silent
    fall-back to every mesh in the file: a mistyped layer would otherwise
    hand a section-loss rating the wrong plate's scan."""
    import numpy as np
    import rhino3dm  # noqa: F401  (optional dependency)
    f = rhino3dm.File3dm.Read(path)
    layer_idx = None
    if layer is not None:
        for i, ly in enumerate(f.Layers):
            if ly.FullPath == layer or ly.Name == layer:
                layer_idx = i
        if layer_idx is None:
            raise ValueError(
                f"no layer named {layer!r} in {path}; found "
                f"{sorted(ly.FullPath for ly in f.Layers)}")
    pts = []
    for obj in f.Objects:
        if layer_idx is not None and obj.Attributes.LayerIndex != layer_idx:
            continue
        g = obj.Geometry
        if isinstance(g, rhino3dm.Mesh):
            for k in range(len(g.Vertices)):
                p = g.Vertices[k]
                pts.append((p.X, p.Y, p.Z))
    return np.asarray(pts, dtype=float)


# --------------------------------------------------------------------------- #
# serialization (one JSON per joint: the drawing-parser -> Rhino hand-off)
# --------------------------------------------------------------------------- #
def joint_to_dict(joint: GussetJoint) -> dict:
    """A JSON-safe dict holding everything needed to rebuild ``joint``.

    The seeding format: the failure-plane drawing parser writes one of these
    per joint, and anything that cannot import this module's dependencies --
    Rhino's own Python, say -- rebuilds the joint from it with
    :func:`joint_from_dict`.  Only *inputs* are stored; every derived
    quantity is recomputed."""
    def plate_d(p: GussetPlate) -> dict:
        return {"outline": [list(pt) for pt in p.outline], "fy": p.fy,
                "fu": p.fu, "label": p.label,
                "thickness": {"t_nominal": p.thickness.t_nominal,
                              "n_samples": p.thickness.n_samples,
                              "patches": [{"polygon": [list(pt) for pt in q.polygon],
                                           "t_remaining": q.t_remaining,
                                           "note": q.note}
                                          for q in p.thickness.patches]}}

    def member_d(m: MemberEnd) -> dict:
        return {"name": m.name, "axis": list(m.axis), "member_type": m.member_type,
                "is_chord": m.is_chord, "spliced_at_joint": m.spliced_at_joint,
                "milled_butt": m.milled_butt,
                "fasteners": [{"x": f.x, "y": f.y, "diameter": f.diameter,
                               "hole": f.hole, "kind": f.kind} for f in m.fasteners]}

    out = {"name": joint.name, "work_point": list(joint.work_point),
           "fastener_diameter": joint.fastener_diameter,
           "inside": plate_d(joint.inside),
           "members": [member_d(m) for m in joint.members]}
    if joint.outside is not None:
        out["outside"] = plate_d(joint.outside)
    if joint.members_outside:
        out["members_outside"] = [member_d(m) for m in joint.members_outside]
    return out


def joint_from_dict(d: dict) -> GussetJoint:
    """Rebuild a :class:`GussetJoint` from :func:`joint_to_dict` output."""
    wp = tuple(d["work_point"])

    def plate(pd):
        t = pd["thickness"]
        return GussetPlate([tuple(pt) for pt in pd["outline"]],
                           ThicknessField(t["t_nominal"],
                                          [ThicknessPatch([tuple(pt) for pt in q["polygon"]],
                                                          q["t_remaining"], q.get("note", ""))
                                           for q in t.get("patches", [])],
                                          t.get("n_samples", 200)),
                           fy=pd.get("fy", 45.0), fu=pd.get("fu", 70.0),
                           label=pd.get("label", ""))

    def member(md):
        return MemberEnd(md["name"], wp, tuple(md["axis"]),
                         [Fastener(f["x"], f["y"], f.get("diameter", 1.0),
                                   f.get("hole"), f.get("kind", "rivet"))
                          for f in md["fasteners"]],
                         member_type=md.get("member_type", "diagonal"),
                         is_chord=md.get("is_chord", False),
                         spliced_at_joint=md.get("spliced_at_joint", False),
                         milled_butt=md.get("milled_butt", False))

    return GussetJoint(d["name"], wp, plate(d["inside"]),
                       outside=plate(d["outside"]) if d.get("outside") else None,
                       members=[member(m) for m in d["members"]],
                       members_outside=([member(m) for m in d["members_outside"]]
                                        if d.get("members_outside") else None),
                       fastener_diameter=d.get("fastener_diameter", 1.0))
