#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.
"""BrIM emit for a riveted steel truss -- the source-of-truth 3-D model.

:mod:`civilpy.structural.rhino_bim` does this for the parametric plate-girder
bridge; this is its twin for the trusses that make up most of the old long
spans, where there is no parametric layout to generate from -- the geometry
comes off the erection and member sheets, panel point by panel point.

The model is *as-built*, not schematic.  A truss member of the riveted era
is a bundle of flat plates and angles, and at LOD 400 that is exactly what
is drawn: :mod:`civilpy.structural.builtup` decomposes the plan-sheet
shorthand (``"2P24x9/16 4L6x4x3/8"``) into its web plates, its four corner
angles and its cover plates, and each becomes its own solid on the member's
axis.  At LOD 300 the member collapses to the single box that envelopes it,
which is what a whole-bridge file wants.  Gusset plates are real plates:
the outline traced off the failure-plane sheets, extruded at the measured
thickness, sitting on the faces of the member webs at the joint -- with
their rating write-back on board, so a viewer can pick any plate in the
bridge and read what governs it.

Everything is stamped with :mod:`civilpy.structural.bim` tags
(``bim.type``/``bim.id``, a ``pay.*`` block, a ``mat.*`` block carrying the
MBE historic-steel yield and tensile), so the same file drives the model
tree, the quantity takeoff and the estimator hand-off that the girder
pipeline already feeds.

Coordinates are **feet** (the hub convention): X along the bridge, Y
transverse, Z elevation.  Section dimensions in the tags stay in inches.

Member orientation
------------------
A truss member's webs are parallel to the plane of its truss, so the
section's local axes follow from the member axis and the truss plane
normal:

* local **u** -- along the member, node i to node j
* local **y** -- across the width (web to web), the truss plane normal,
  i.e. bridge-transverse for a truss in a vertical plane
* local **z** -- through the depth, in the truss plane, perpendicular to
  the member

which is the same y/z that :mod:`civilpy.structural.builtup` uses, so a
section rectangle maps straight onto the member with no extra convention.

Backends
--------
:func:`truss_emit` returns the same neutral ``EmitObject`` records
``rhino_bim`` uses, so both of its backends work unchanged:
:func:`~civilpy.structural.rhino_bim.objects_to_3dm` bakes a ``.3dm`` with
standalone ``rhino3dm`` (use ``mesh=True`` for a file the web viewer can
shade), and the live-document driver consumes the same JSON.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural import bim, builtup
from civilpy.structural.rhino_bim import EmitObject
from civilpy.structural.rhino_layers import (
    LAYER_FLOOR_BEAMS,
    LAYER_GUSSET_PLATES,
    LAYER_LATERAL_BRACING,
    LAYER_PANEL_POINTS,
    LAYER_STRINGERS,
    LAYER_SWAY_BRACING,
    LAYER_TRUSS_CHORDS,
    LAYER_TRUSS_DIAGONALS,
    LAYER_TRUSS_END_POSTS,
    LAYER_TRUSS_STRUTS,
    LAYER_TRUSS_VERTICALS,
)

Point3 = tuple

#: ``bim.type`` -> layer for every object this module emits.
TYPE_LAYER = {
    "truss_chord_top": LAYER_TRUSS_CHORDS,
    "truss_chord_bottom": LAYER_TRUSS_CHORDS,
    "truss_vertical": LAYER_TRUSS_VERTICALS,
    "truss_diagonal": LAYER_TRUSS_DIAGONALS,
    "truss_end_post": LAYER_TRUSS_END_POSTS,
    "truss_strut": LAYER_TRUSS_STRUTS,
    "gusset_plate": LAYER_GUSSET_PLATES,
    "floor_beam": LAYER_FLOOR_BEAMS,
    "stringer": LAYER_STRINGERS,
    "lateral_brace": LAYER_LATERAL_BRACING,
    "sway_brace": LAYER_SWAY_BRACING,
    "portal_brace": LAYER_SWAY_BRACING,
    "panel_point": LAYER_PANEL_POINTS,
}


# --------------------------------------------------------------------------- #
# vector helpers (feet)
# --------------------------------------------------------------------------- #
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _norm(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _unit(a):
    n = _norm(a)
    if n < 1e-12:
        raise ValueError("zero-length vector")
    return (a[0] / n, a[1] / n, a[2] / n)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


# --------------------------------------------------------------------------- #
# model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TrussNode:
    """A panel point (or any other work point) in bridge coordinates, feet."""
    id: str
    point: Point3
    line: str = ""            # truss line, e.g. "OS" / "IS" / "IN" / "ON"
    span: str = ""
    chord: str = ""           # "U" upper, "L" lower, "M" intermediate, "P" pier
    pp: int = 0               # panel-point index along the span
    joint: str = ""           # the rating joint id this work point carries


@dataclass(frozen=True)
class TrussMember:
    """One truss member between two nodes, described by its plan-sheet spec.

    ``normal`` is the truss plane normal (the direction the section's width
    runs); it defaults to bridge-transverse, which is right for a truss in a
    vertical plane."""
    id: str
    i: str
    j: str
    spec: str
    role: str = "truss_chord_top"
    line: str = ""
    span: str = ""
    normal: Point3 = (0.0, 1.0, 0.0)
    steel: str = "silicon 1917-1936"


@dataclass(frozen=True)
class FramingMember:
    """A floor beam, stringer or bracing member: drawn as a box, since the
    floor-system sections are estimates rather than sheet values."""
    id: str
    i: str
    j: str
    section: str
    role: str = "floor_beam"
    depth_in: float = 18.0
    width_in: float = 8.0
    level: str = ""
    span: str = ""
    normal: Point3 = (0.0, 0.0, 1.0)


@dataclass(frozen=True)
class GussetPlacement:
    """One gusset plate positioned at a joint.

    ``outline`` is the plate polygon in the drawing's own 2-D plate
    coordinates (inches, x right / y up, the convention
    :mod:`civilpy.structural.gusset_geometry` uses) and ``work_point`` the
    point in those coordinates that sits on ``node``.  ``plane_x`` is the
    direction the plate's local +x runs in bridge coordinates (default: along
    +X) and ``normal`` the plate normal; ``offset_in`` slides the plate along
    its normal to the face of the member webs it is riveted to."""
    id: str
    node: str
    outline: tuple
    work_point: tuple
    thickness_in: float = 0.625
    joint: str = ""
    face: str = "outside"
    offset_in: float = 9.0
    plane_x: Point3 = (1.0, 0.0, 0.0)
    normal: Point3 = (0.0, 1.0, 0.0)
    members: str = ""
    t_remaining_in: float = None
    rating_rf: float = None
    governing: str = ""
    steel: str = "silicon 1917-1936"


@dataclass
class TrussModel:
    """A whole truss bridge: work points, members, framing and gusset plates."""
    name: str
    nodes: dict = field(default_factory=dict)
    members: list = field(default_factory=list)
    framing: list = field(default_factory=list)
    gussets: list = field(default_factory=list)
    doc_tags: dict = field(default_factory=dict)

    def node(self, nid: str) -> TrussNode:
        return self.nodes[nid]

    def add_node(self, node: TrussNode) -> TrussNode:
        self.nodes[node.id] = node
        return node

    def length_ft(self, m) -> float:
        return _norm(_sub(self.nodes[m.j].point, self.nodes[m.i].point))

    def bbox(self):
        pts = [n.point for n in self.nodes.values()]
        return (tuple(min(p[k] for p in pts) for k in range(3)),
                tuple(max(p[k] for p in pts) for k in range(3)))


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #
def member_frame(p_i: Point3, p_j: Point3, normal: Point3):
    """``(u, v, w, length)`` for a member: ``u`` along it, ``v`` across the
    width (the truss plane normal, squared up against ``u``), ``w`` through
    the depth in the truss plane."""
    d = _sub(p_j, p_i)
    length = _norm(d)
    if length < 1e-9:
        raise ValueError("member has zero length")
    u = _scale(d, 1.0 / length)
    v = _sub(normal, _scale(u, _dot(normal, u)))     # normal, orthogonalised
    if _norm(v) < 1e-9:                              # member runs along the normal
        alt = (0.0, 0.0, 1.0) if abs(u[2]) < 0.9 else (1.0, 0.0, 0.0)
        v = _sub(alt, _scale(u, _dot(alt, u)))
    v = _unit(v)
    w = _cross(u, v)
    return u, v, w, length


def _rect_loop(origin, v, w, y_c, z_c, b, h):
    """The four corners of a section rectangle, in bridge coordinates (feet).

    ``y_c``/``z_c``/``b``/``h`` are inches in the section's own axes."""
    ft = 1.0 / 12.0
    pts = []
    for sy, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        y = (y_c + sy * b / 2.0) * ft
        z = (z_c + sz * h / 2.0) * ft
        pts.append(_add(origin, _add(_scale(v, y), _scale(w, z))))
    return tuple(pts)


def member_objects(model: TrussModel, m: TrussMember, *, lod: int = 400,
                   shorten_ft: float = 0.0) -> list:
    """The solids for one truss member.

    At ``lod >= 400`` one prism per plate and per angle leg -- the member as
    it was riveted; at LOD 300 a single enveloping box.  ``shorten_ft``
    trims both ends, so members can stop clear of the gusset plates instead
    of running through them."""
    p_i = model.nodes[m.i].point
    p_j = model.nodes[m.j].point
    u, v, w, length = member_frame(p_i, p_j, m.normal)
    if shorten_ft > 0.0 and length > 2.2 * shorten_ft:
        p_i = _add(p_i, _scale(u, shorten_ft))
        length -= 2.0 * shorten_ft
    vector = _scale(u, length)
    props = builtup.properties(m.spec)
    weight_lb = props["A"] / 144.0 * builtup.STEEL_PCF * length
    if m.role not in TYPE_LAYER:
        raise ValueError("unknown truss member role %r; expected one of %s"
                         % (m.role, ", ".join(bim.TRUSS_MEMBER_TYPES)))
    layer = TYPE_LAYER[m.role]

    if lod < 400:
        b, h = builtup.envelope(m.spec)
        tags = bim.truss_member_tags(
            m.id, role=m.role, spec=m.spec, length_ft=length,
            weight_lb=weight_lb, line=m.line, span=m.span, steel=m.steel)
        return [EmitObject("prism", layer, _rect_loop(p_i, v, w, 0.0, 0.0, b, h),
                           tags, vector)]

    rects, _meta = builtup.rects(m.spec)
    labels = builtup.piece_labels(m.spec)
    out = []
    for k, (b, h, y_c, z_c) in enumerate(rects):
        # the pay quantity rides on the first piece only: every piece shares
        # the member's bim.id, and the takeoff sums pay.qty
        tags = bim.truss_member_tags(
            m.id, role=m.role, spec=m.spec, length_ft=length,
            weight_lb=weight_lb if k == 0 else None,
            line=m.line, span=m.span, steel=m.steel,
            piece=labels[k] if k < len(labels) else "piece %d" % k)
        out.append(EmitObject("prism", layer,
                              _rect_loop(p_i, v, w, y_c, z_c, b, h),
                              tags, vector))
    return out


def framing_objects(model: TrussModel, f: FramingMember) -> list:
    """One box solid for a floor beam, stringer or brace."""
    p_i = model.nodes[f.i].point
    p_j = model.nodes[f.j].point
    u, v, w, length = member_frame(p_i, p_j, f.normal)
    area_in2 = f.depth_in * f.width_in * 0.35          # ~35% of the box is steel
    weight_lb = area_in2 / 144.0 * builtup.STEEL_PCF * length
    tags = bim.truss_framing_tags(
        f.id, role=f.role, section=f.section, length_ft=length,
        weight_lb=weight_lb, level=f.level or None, span=f.span or None)
    return [EmitObject("prism", TYPE_LAYER[f.role],
                       _rect_loop(p_i, v, w, 0.0, 0.0, f.width_in, f.depth_in),
                       tags, _scale(u, length))]


def gusset_objects(model: TrussModel, g: GussetPlacement) -> list:
    """One plate solid for a gusset, positioned on its joint.

    The plate's 2-D outline is carried into bridge coordinates by putting its
    work point on the node, its local +x along ``plane_x`` and its local +y
    on the in-plane perpendicular, then extruding along the normal by the
    plate thickness."""
    node = model.nodes[g.node]
    n = _unit(g.normal)
    ex = _sub(g.plane_x, _scale(n, _dot(g.plane_x, n)))
    ex = _unit(ex)
    # plate +y must come out UP: with the plate normal transverse (+Y) and
    # its +x along the bridge (+X), that is cross(ex, n), not cross(n, ex) --
    # the other order lands the drawing upside down on the joint.
    ey = _cross(ex, n)
    ft = 1.0 / 12.0
    base = _add(node.point, _scale(n, g.offset_in * ft))
    wx, wy = g.work_point
    pts = tuple(
        _add(base, _add(_scale(ex, (px - wx) * ft), _scale(ey, (py - wy) * ft)))
        for px, py in g.outline)

    area = abs(_polygon_area(g.outline))
    t = g.t_remaining_in if g.t_remaining_in is not None else g.thickness_in
    weight_lb = area * t / 1728.0 * builtup.STEEL_PCF
    tags = bim.gusset_plate_tags(
        g.id, joint=g.joint or g.node, thickness_in=g.thickness_in,
        face=g.face, area_in2=area, weight_lb=weight_lb,
        members=g.members or None, t_remaining_in=g.t_remaining_in,
        rating_rf=g.rating_rf, governing=g.governing or None, steel=g.steel)
    return [EmitObject("prism", LAYER_GUSSET_PLATES, pts, tags,
                       _scale(n, g.thickness_in * ft))]


def _polygon_area(poly) -> float:
    a = 0.0
    n = len(poly)
    for k in range(n):
        x0, y0 = poly[k]
        x1, y1 = poly[(k + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def panel_point_objects(model: TrussModel, node: TrussNode) -> list:
    """The work-point marker for a panel point."""
    tags = bim.panel_point_tags(node.id, joint=node.joint or node.id,
                                line=node.line, span=node.span,
                                chord=node.chord, pp=node.pp)
    return [EmitObject("point", LAYER_PANEL_POINTS, (node.point,), tags)]


# --------------------------------------------------------------------------- #
# emit
# --------------------------------------------------------------------------- #
def truss_emit(model: TrussModel, *, lod: int = 400, shorten_ft: float = 0.0,
               panel_points: bool = True, framing: bool = True,
               gussets: bool = True, members: bool = True) -> tuple:
    """Every drawable object of ``model`` as neutral ``EmitObject`` records.

    ``lod`` 400 or more draws the built-up members piece by piece; 300 draws
    each as one enveloping box, which is what a whole-bridge file wants.
    The four content switches let a caller emit, say, only the gusset plates
    and the panel points for a joint-by-joint review file."""
    out = []
    if members:
        for m in model.members:
            out.extend(member_objects(model, m, lod=lod, shorten_ft=shorten_ft))
    if framing:
        for f in model.framing:
            out.extend(framing_objects(model, f))
    if gussets:
        for g in model.gussets:
            out.extend(gusset_objects(model, g))
    if panel_points:
        for node in model.nodes.values():
            if node.chord in ("U", "L"):
                out.extend(panel_point_objects(model, node))
    return tuple(out)


def model_doc_tags(model: TrussModel, *, lod: int) -> dict:
    """The document-wide record, carried on a ``bim.type = bridge`` marker
    the way ``rhino_bim`` does (standalone ``rhino3dm`` cannot write the
    document string table)."""
    (x0, y0, z0), (x1, y1, z1) = model.bbox()
    tags = {"bim.type": "bridge", "bim.id": model.name,
            "bridge.structure_type": "riveted steel truss",
            "bridge.lod": str(lod),
            "bridge.units": "feet",
            "bridge.length_ft": "%.3f" % (x1 - x0),
            "bridge.width_ft": "%.3f" % (y1 - y0),
            "bridge.height_ft": "%.3f" % (z1 - z0),
            "bridge.panel_points": str(sum(1 for n in model.nodes.values()
                                           if n.chord in ("U", "L"))),
            "bridge.truss_members": str(len(model.members)),
            "bridge.framing_members": str(len(model.framing)),
            "bridge.gusset_plates": str(len(model.gussets)),
            "bridge.generator": "civilpy.structural.rhino_truss"}
    tags.update(model.doc_tags)
    return tags


def truss_to_3dm(model: TrussModel, path, *, lod: int = 400,
                 mesh: bool = True, version: int = 7, shorten_ft: float = 0.0,
                 **content) -> dict:
    """Bake the truss to a ``.3dm``.

    ``mesh=True`` (the default here, unlike ``rhino_bim``) builds closed
    meshes rather than breps: headless ``rhino3dm`` cannot tessellate a brep,
    so a brep file arrives *empty* in three.js -- and the point of this model
    is that it opens in the asset-management viewer.  Returns per-layer
    object counts."""
    from civilpy.structural.rhino_bim import objects_to_3dm

    objects = truss_emit(model, lod=lod, shorten_ft=shorten_ft, **content)
    doc = EmitObject("point", LAYER_PANEL_POINTS,
                     (model.bbox()[0],), model_doc_tags(model, lod=lod))
    return objects_to_3dm(objects + (doc,), path, version=version, mesh=mesh)


def gusset_joint_placements(joint, node_id: str, *, thickness_in: float = None,
                            half_width_in: float = 9.0, plane_x=(1.0, 0.0, 0.0),
                            normal=(0.0, 1.0, 0.0), rating_rf: float = None,
                            governing: str = "", id_prefix: str = "") -> list:
    """The two :class:`GussetPlacement` records for a
    :class:`~civilpy.structural.gusset_geometry.GussetJoint` -- one plate on
    each face of the member webs, ``half_width_in`` either side of the truss
    line.

    This is the bridge between the failure-plane drawings and the 3-D model:
    a joint parsed off a sheet drops straight onto its panel point."""
    prefix = id_prefix or joint.name
    out = []
    for face, sign, plate in (("inside", -1.0, joint.inside),
                              ("outside", +1.0, joint.outside or joint.inside)):
        if plate is None:
            continue
        members = ",".join(m.name for m in joint.members)
        loss = None
        if getattr(plate.thickness, "patches", None):
            loss = min(p.t_remaining for p in plate.thickness.patches)
        out.append(GussetPlacement(
            id="%s-%s" % (prefix, face), node=node_id,
            outline=tuple(plate.outline), work_point=tuple(joint.work_point),
            thickness_in=thickness_in or plate.t, joint=joint.name, face=face,
            offset_in=sign * half_width_in,
            plane_x=plane_x, normal=normal, members=members,
            t_remaining_in=loss, rating_rf=rating_rf, governing=governing))
    return out
