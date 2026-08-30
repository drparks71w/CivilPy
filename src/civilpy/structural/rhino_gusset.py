#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.
"""Rhino interchange for truss gusset-plate ratings.

:mod:`civilpy.structural.gusset_geometry` computes every quantity a gusset
rating needs -- Whitmore sections, unbraced lengths, block-shear paths, cut
sections, remaining thickness -- from coordinates.  Those quantities are
only believable if somebody can *see* where they were taken, which is what
this module is for: it bakes a
:class:`~civilpy.structural.gusset_geometry.GussetJoint` into Rhino, one
layer per failure mechanism, and reads a reviewer's edits back out.

The round trip is the point.  A reviewer opens the joint, toggles
``Gusset::Whitmore`` against ``Gusset::BlockShear``, moves a rivet the
drawing parser put in the wrong place, adds the field-drilled LC-1 holes
(CUY-10-1613 Stage 2 sheets 97-99), or sketches a corrosion patch over the
pack rust at the bottom of the plate -- and :func:`gusset_from_3dm` returns
a ``GussetJoint`` whose ``summary()`` reflects exactly that, ready to
re-rate.  Nothing on the derived layers (Whitmore / Unbraced / BlockShear /
Sections / Text) is read back: those are recomputed from the outline,
fasteners, work lines and loss patches, which are the only inputs.

Units and coordinates
---------------------
Everything is **inches**, in the plate's own 2-D system (x right, y up, the
same coordinates ``gusset_geometry`` uses), baked at ``z = 0`` for one plate
at a time -- these are failure-plane sheets, not bridge geometry.  A written
``.3dm`` stamps ``ModelUnitSystem = Inches``; a file in other units is
scaled to inches on read.  Joint-wide facts ride on a ``gus.kind=joint``
marker point's user text rather than the document string table, because
``rhino3dm`` cannot read ``RhinoDoc.Strings`` (the same contract as
``rhino_gdr``'s ``gdr.kind=bridge`` marker).

Layers (see :mod:`civilpy.structural.rhino_layers`)
---------------------------------------------------
==========================  ================================================
``Gusset::Outline``         plate outline polyline (input)
``Gusset::Fasteners``       one circle per rivet/bolt at hole diameter (input)
``Gusset::WorkLines``       member axes from the work point (input)
``Gusset::Loss``            ``ThicknessPatch`` polygons + shaded mesh (input)
``Gusset::Whitmore``        section line, its effective (clipped) part, and
                            the two 30-degree spread lines (derived)
``Gusset::Unbraced``        the L1 / Lmid / L2 rays (derived)
``Gusset::BlockShear``      tear-out polygon per member (derived)
``Gusset::Sections``        arbitrary cut lines with gross/net areas (derived)
``Gusset::ScanDepth``       scan depth heat-map mesh (derived)
``Gusset::Text``            joint id, governing check, rating factors
==========================  ================================================

Two back ends, one geometry
---------------------------
:func:`gusset_entities` builds a back-end-independent list of
:class:`Entity` records.  :func:`gusset_to_3dm` bakes them into a ``.3dm``
with ``rhino3dm`` (offline, no Rhino needed); :func:`bake_to_document` bakes
the *same* entities into a live ``RhinoDoc`` with RhinoCommon, so driving
Rhino over its MCP server and writing the file for the record produce
identical layers and user text.  Keep new artifacts flowing through
``gusset_entities`` so both paths stay in step.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field as _dc_field

from civilpy.structural.gusset_geometry import (
    Fastener,
    GussetJoint,
    GussetPlate,
    MemberEnd,
    ThicknessField,
    ThicknessPatch,
    clip_segment,
    mesh_vertices_from_3dm,
    thickness_field_from_points,
)
from civilpy.structural.rhino_layers import (
    DEFAULT_COLORS,
    LAYER_GUSSET,
    LAYER_GUSSET_BLOCKSHEAR,
    LAYER_GUSSET_FASTENERS,
    LAYER_GUSSET_LOSS,
    LAYER_GUSSET_OUTLINE,
    LAYER_GUSSET_SCANDEPTH,
    LAYER_GUSSET_SECTIONS,
    LAYER_GUSSET_TEXT,
    LAYER_GUSSET_UNBRACED,
    LAYER_GUSSET_WHITMORE,
    LAYER_GUSSET_WORKLINES,
    ensure_layer,
)

#: User-text namespace for the gusset pipeline (mirrors ``gdr.`` / ``stm.``).
GTAG = "gus."

#: Conversion factor from a ``.3dm`` model unit system to inches.  A plain
#: table rather than :mod:`civilpy.general.units` so the module stays
#: importable inside Rhino's own Python, which has no pint.
_UNIT_TO_INCHES = {
    "Inches": 1.0, "Feet": 12.0, "Yards": 36.0, "Miles": 63360.0,
    "Millimeters": 1.0 / 25.4, "Centimeters": 1.0 / 2.54,
    "Decimeters": 10.0 / 25.4, "Meters": 1000.0 / 25.4,
    "Kilometers": 1.0e6 / 25.4,
}

#: How far past the outermost fastener a member's work line is drawn (in).
WORKLINE_STICKOUT = 8.0


# --------------------------------------------------------------------------- #
# back-end-independent geometry
# --------------------------------------------------------------------------- #
@dataclass
class Entity:
    """One thing to bake, in plate coordinates (inches).

    ``kind`` is one of ``polyline`` / ``line`` / ``circle`` / ``point`` /
    ``mesh`` / ``dot``.  ``tags`` keys are written as user text with the
    :data:`GTAG` prefix added; ``colors`` (per-vertex RGB) is used only by
    ``mesh``."""
    layer: str
    kind: str
    points: list = _dc_field(default_factory=list)
    name: str = ""
    tags: dict = _dc_field(default_factory=dict)
    radius: float = 0.0
    text: str = ""
    faces: list = _dc_field(default_factory=list)
    colors: list = _dc_field(default_factory=list)


def _f(v) -> str:
    """Full-precision repr so a written value reads back bit-identical."""
    return repr(float(v))


def _3d(pt, z=0.0):
    return (float(pt[0]), float(pt[1]), float(z))


def _checks_blob(checks) -> str:
    """``[(article, check, actual, allowable, verdict), ...]`` -> the
    pipe/newline blob :func:`read_gusset_results` and ``rhino_gdr`` share."""
    rows = []
    for c in checks or ():
        rows.append("|".join("" if x is None else str(x) for x in c))
    return "\n".join(rows)


def _result_tags(res) -> dict:
    """Flatten a per-joint or per-member result dict into user text."""
    out = {}
    if not res:
        return out
    for key in ("edition", "governing", "status", "summary"):
        if res.get(key) not in (None, ""):
            out[key] = str(res[key])
    for key in ("rf", "rf_inventory", "rf_operating"):
        if res.get(key) is not None:
            out[key] = _f(res[key])
    if res.get("checks"):
        out["checks"] = _checks_blob(res["checks"])
    return out


def _members_for(joint: GussetJoint, plate: GussetPlate):
    """The member ends that belong to ``plate`` (the outside plate may carry
    its own fastener pattern via ``members_outside``)."""
    if plate is joint.outside and joint.members_outside:
        return joint.members_outside
    return joint.members


def _polygon_mesh(poly, z=0.0):
    """(vertices, faces) for a simple polygon: a quad when it has four
    corners, otherwise a fan from the first vertex -- fine for the convex
    cells a scan produces; a concave sketch is displayed approximately."""
    verts = [_3d(p, z) for p in poly]
    if len(verts) == 4:
        return verts, [(0, 1, 2, 3)]
    return verts, [(0, i, i + 1) for i in range(1, len(verts) - 1)]


def _loss_color(loss: float, t_nominal: float):
    """Rust-orange ramp: untouched plate pale, half the plate gone deep red."""
    frac = 0.0 if t_nominal <= 0 else max(0.0, min(1.0, loss / (0.5 * t_nominal)))
    return (int(235 - 55 * frac), int(200 - 155 * frac), int(150 - 130 * frac))


def gusset_entities(joint: GussetJoint, plate: GussetPlate = None, *,
                    results=None, field: ThicknessField = None,
                    sections=None, z: float = 0.0, tol: float = 0.35,
                    derived: bool = True) -> list:
    """Every artifact of ``joint`` on one ``plate`` as :class:`Entity` records.

    ``plate`` defaults to the inside plate.  ``field`` overrides the plate's
    own :class:`ThicknessField` for the ``Gusset::Loss`` layer (a field just
    built from a scan, say).  ``results`` is an optional rating write-back::

        {"edition": "LFR2012", "governing": "check 3 rivet shear",
         "rf": 5.149, "checks": [(article, check, actual, allow, verdict)],
         "members": {"U0L1": {"governing": ..., "rf": ..., "checks": [...]}}}

    ``sections`` is an optional list of ``(p0, p1)`` or ``(p0, p1, label)``
    cut lines.  ``derived=False`` emits only the layers that are *read back*
    (outline, fasteners, work lines, loss) -- the round-trip inputs.
    """
    plate = plate or joint.inside
    members = _members_for(joint, plate)
    ents = []
    tfield = field if field is not None else plate.thickness
    results = results or {}
    member_results = results.get("members") or {}

    # -- joint marker: the work point, and everything document-wide --------
    x0, y0, x1, y1 = plate.bbox
    jtags = {
        "kind": "joint", "joint": joint.name, "plate": plate.label,
        "units": "inches", "t_nominal": _f(plate.t), "fy": _f(plate.fy),
        "fu": _f(plate.fu), "fastener_diameter": _f(joint.fastener_diameter),
        "n_samples": str(int(getattr(tfield, "n_samples", 200))),
        "n_members": str(len(members)),
        "generator": "civilpy.structural.rhino_gusset",
    }
    jtags.update(_result_tags(results))
    ents.append(Entity(LAYER_GUSSET, "point", [_3d(joint.work_point, z)],
                       name="%s work point" % joint.name, tags=jtags))

    # -- outline -----------------------------------------------------------
    ring = list(plate.outline)
    ents.append(Entity(
        LAYER_GUSSET_OUTLINE, "polyline",
        [_3d(p, z) for p in ring] + [_3d(ring[0], z)],
        name="%s outline" % joint.name,
        tags={"kind": "outline", "joint": joint.name, "plate": plate.label,
              "t_nominal": _f(plate.t), "fy": _f(plate.fy), "fu": _f(plate.fu),
              "area": _f(plate.area), "gross_width": _f(plate.gross_width),
              "gross_height": _f(plate.gross_height),
              "max_edge": _f(joint.max_unsupported_edge(plate))}))

    # -- per member --------------------------------------------------------
    for mi, m in enumerate(members):
        rows = m.rows(tol)                  # joint outward: rows[0] nearest
        n_rows = len(rows)
        cols = m.column_lines(tol)

        # work line: from the work point out along the member axis
        end = m.point_at(m.s_first + WORKLINE_STICKOUT, 0.0)
        ents.append(Entity(
            LAYER_GUSSET_WORKLINES, "line",
            [_3d(joint.work_point, z), _3d(end, z)], name=m.name,
            tags={"kind": "workline", "joint": joint.name, "member": m.name,
                  "index": str(mi), "axis_x": _f(m.axis[0]), "axis_y": _f(m.axis[1]),
                  "member_type": m.member_type, "is_chord": str(bool(m.is_chord)),
                  "spliced_at_joint": str(bool(m.spliced_at_joint)),
                  "milled_butt": str(bool(m.milled_butt)),
                  "n": str(m.n_fasteners), "n_rows": str(n_rows),
                  "n_cols": str(len(cols)), "L_conn": _f(m.connection_length),
                  "s_first": _f(m.s_first), "s_last": _f(m.s_last)}))

        # fasteners: row 1 = the first row, farthest from the joint (where the
        # member's force enters the plate); row n_rows = the Whitmore row
        for fi, fa in enumerate(m.fasteners):
            s, c = m.s_of(fa), m.c_of(fa)
            row = min(range(n_rows), key=lambda k: abs(m.s_of(rows[k][0]) - s))
            col = min(range(len(cols)), key=lambda k: abs(cols[k] - c))
            ents.append(Entity(
                LAYER_GUSSET_FASTENERS, "circle", [_3d(fa.pt, z)], name=m.name,
                radius=fa.hole_dia / 2.0,
                tags={"kind": "fastener", "joint": joint.name, "member": m.name,
                      "idx": str(fi), "row": str(n_rows - row), "col": str(col + 1),
                      "x": _f(fa.x), "y": _f(fa.y), "s": _f(s), "c": _f(c),
                      "diameter": _f(fa.diameter), "hole": _f(fa.hole_dia),
                      "fastener_kind": fa.kind}))

        if not derived:
            continue

        # Whitmore: the section, the part of it inside the plate, and the fan
        w = joint.whitmore(m, plate)
        p0, p1 = w["p0"], w["p1"]
        wtags = {"kind": "whitmore", "joint": joint.name, "member": m.name,
                 "b": _f(w["b"]), "b_effective": _f(w["b_effective"]),
                 "length_in_plate": _f(w["length_in_plate"]),
                 "A_gross": _f(w["A_gross"]), "A_net": _f(w["A_net"])}
        ents.append(Entity(LAYER_GUSSET_WHITMORE, "line",
                           [_3d(p0, z), _3d(p1, z)],
                           name="%s Whitmore b=%.2f" % (m.name, w["b"]), tags=wtags))
        if w["b_effective"] < w["b"] - 1e-9:
            for si, (a, b) in enumerate(w["segments"]):
                et = dict(wtags)
                et["kind"] = "whitmore_effective"
                et["segment"] = str(si)
                ents.append(Entity(
                    LAYER_GUSSET_WHITMORE, "line", [_3d(a, z), _3d(b, z)],
                    name="%s Whitmore effective b=%.2f" % (m.name, w["b_effective"]),
                    tags=et))
        c0 = m.first_row_center(tol)
        half = m.first_row_width(tol) / 2.0
        for sgn, side in ((-1.0, "lo"), (1.0, "hi")):
            a = m.point_at(m.s_first, c0 + sgn * half)
            b = m.point_at(m.s_last, c0 + sgn * w["b"] / 2.0)
            ents.append(Entity(
                LAYER_GUSSET_WHITMORE, "line", [_3d(a, z), _3d(b, z)],
                name="%s 30deg spread" % m.name,
                tags={"kind": "whitmore_spread", "joint": joint.name,
                      "member": m.name, "side": side, "angle_deg": "30.0",
                      "L_conn": _f(m.connection_length)}))

        # unbraced lengths: rays from the clipped Whitmore section toward the
        # joint -- rebuilt exactly the way unbraced_lengths() measures them
        lc = joint.unbraced_lengths(m, plate)
        q0, q1 = m.whitmore_segment(tol)
        segs = clip_segment(q0, q1, plate.outline)
        if segs:
            q0, q1 = segs[0][0], segs[-1][1]
        for key, frac in (("L1", 0.02), ("Lmid", 0.5), ("L2", 0.98)):
            start = (q0[0] + frac * (q1[0] - q0[0]), q0[1] + frac * (q1[1] - q0[1]))
            L = lc[key]
            stop = (start[0] - L * m.axis[0], start[1] - L * m.axis[1])
            ents.append(Entity(
                LAYER_GUSSET_UNBRACED, "line", [_3d(start, z), _3d(stop, z)],
                name="%s %s=%.2f" % (m.name, key, L),
                tags={"kind": "unbraced", "joint": joint.name, "member": m.name,
                      "which": key, "length": _f(L), "Lc_avg": _f(lc["Lc_avg"]),
                      "Lc_min": _f(lc["Lc_min"])}))

        # block shear / tear-out
        bs = joint.block_shear(m, plate, tol)
        poly = list(bs["polygon"])
        ents.append(Entity(
            LAYER_GUSSET_BLOCKSHEAR, "polyline",
            [_3d(p, z) for p in poly] + [_3d(poly[0], z)],
            name="%s block shear" % m.name,
            tags={"kind": "blockshear", "joint": joint.name, "member": m.name,
                  "A_vg": _f(bs["A_vg"]), "A_vn": _f(bs["A_vn"]),
                  "A_tg": _f(bs["A_tg"]), "A_tn": _f(bs["A_tn"]),
                  "shear_length": _f(bs["shear_length"]),
                  "tension_width": _f(bs["tension_width"])}))

        # member label
        lab = m.point_at(m.s_first + WORKLINE_STICKOUT, 0.0)
        mr = member_results.get(m.name) or {}
        txt = "%s  n=%d  L=%.1f" % (m.name, m.n_fasteners, m.connection_length)
        if mr.get("rf") is not None:
            txt += "  RF=%.3f" % float(mr["rf"])
        if mr.get("governing"):
            txt += "  (%s)" % mr["governing"]
        mtags = {"kind": "member_label", "joint": joint.name, "member": m.name}
        mtags.update(_result_tags(mr))
        ents.append(Entity(LAYER_GUSSET_TEXT, "dot", [_3d(lab, z)],
                           name=m.name, text=txt, tags=mtags))

    # -- section cuts ------------------------------------------------------
    for si, cut in enumerate(sections or ()):
        a, b = cut[0], cut[1]
        label = cut[2] if len(cut) > 2 else "section %d" % (si + 1)
        sec = joint.section_along(a, b, plate)
        ents.append(Entity(
            LAYER_GUSSET_SECTIONS, "line", [_3d(a, z), _3d(b, z)], name=label,
            tags={"kind": "section", "joint": joint.name, "label": label,
                  "length": _f(sec["length"]), "A_gross": _f(sec["A_gross"]),
                  "A_net": _f(sec["A_net"])}))

    # -- section loss ------------------------------------------------------
    for pi, patch in enumerate(getattr(tfield, "patches", []) or ()):
        loss = tfield.t_nominal - patch.t_remaining
        ptags = {"kind": "loss", "joint": joint.name, "plate": plate.label,
                 "idx": str(pi), "t_remaining": _f(patch.t_remaining),
                 "t_nominal": _f(tfield.t_nominal), "loss": _f(loss),
                 "note": patch.note}
        pring = list(patch.polygon)
        ents.append(Entity(
            LAYER_GUSSET_LOSS, "polyline",
            [_3d(p, z) for p in pring] + [_3d(pring[0], z)],
            name="loss t=%.3f" % patch.t_remaining, tags=ptags))
        verts, faces = _polygon_mesh(pring, z)
        shade = dict(ptags)
        shade["kind"] = "loss_mesh"
        ents.append(Entity(LAYER_GUSSET_LOSS, "mesh", verts, faces=faces,
                           name="loss t=%.3f" % patch.t_remaining, tags=shade,
                           colors=[_loss_color(loss, tfield.t_nominal)] * len(verts)))

    # -- joint label -------------------------------------------------------
    if derived:
        txt = joint.name
        if plate.label and plate.label != joint.name:
            txt += "  [%s]" % plate.label
        txt += "  t=%.3f" % plate.t
        if results.get("edition"):
            txt += "  %s" % results["edition"]
        if results.get("governing"):
            txt += "  gov: %s" % results["governing"]
        if results.get("rf") is not None:
            txt += "  RF=%.3f" % float(results["rf"])
        ttags = {"kind": "joint_label", "joint": joint.name, "plate": plate.label}
        ttags.update(_result_tags(results))
        ents.append(Entity(LAYER_GUSSET_TEXT, "dot",
                           [((x0 + x1) / 2.0, y1 + 4.0, z)],
                           name=joint.name, text=txt, tags=ttags))
    return ents


# --------------------------------------------------------------------------- #
# offline back end: rhino3dm  ->  .3dm
# --------------------------------------------------------------------------- #
def _require_rhino3dm():
    try:
        import rhino3dm
    except ImportError as exc:  # pragma: no cover - exercised only without dep
        raise ImportError(
            "rhino3dm is required for Rhino interchange; install it with "
            "`pip install civilpy[rhino]` or `pip install rhino3dm`."
        ) from exc
    return rhino3dm


def _unit_to_inches(f) -> float:
    """Scale factor from a ``.3dm``'s model units to inches (1.0 if unset)."""
    try:
        name = f.Settings.ModelUnitSystem.name
    except Exception:                       # pragma: no cover - defensive
        return 1.0
    if name in (None, "Inches", "None", "Unset"):
        return 1.0
    scale = _UNIT_TO_INCHES.get(name)
    if scale is None:
        warnings.warn(
            "unrecognized .3dm model unit %r; assuming inches (no scaling)" % name,
            stacklevel=2)
        return 1.0
    return scale


def _bake_3dm(f, r3, ents):
    """Bake :class:`Entity` records into an open ``rhino3dm.File3dm``."""
    layers = {}
    n = 0
    for e in ents:
        if e.layer not in layers:
            layers[e.layer] = ensure_layer(f, e.layer, DEFAULT_COLORS.get(e.layer))
        attr = r3.ObjectAttributes()
        attr.LayerIndex = layers[e.layer]
        if e.name:
            attr.Name = e.name
        for k, v in e.tags.items():
            attr.SetUserString(GTAG + k, v)
        pts = [r3.Point3d(*p) for p in e.points]
        if e.kind == "point":
            f.Objects.AddPoint(pts[0], attr)
        elif e.kind == "line":
            f.Objects.AddLine(pts[0], pts[1], attr)
        elif e.kind == "polyline":
            f.Objects.AddPolyline(pts, attr)
        elif e.kind == "circle":
            f.Objects.AddCircle(r3.Circle(pts[0], e.radius), attr)
        elif e.kind == "dot":
            f.Objects.AddTextDot(e.text, pts[0], attr)
        elif e.kind == "mesh":
            mesh = r3.Mesh()
            for p in e.points:
                mesh.Vertices.Add(p[0], p[1], p[2])
            for face in e.faces:
                if len(face) == 4:
                    mesh.Faces.AddFace(face[0], face[1], face[2], face[3])
                else:
                    mesh.Faces.AddFace(face[0], face[1], face[2])
            for c in e.colors:
                try:
                    mesh.VertexColors.Add(c[0], c[1], c[2])
                except Exception:            # pragma: no cover - old rhino3dm
                    break
            f.Objects.AddMesh(mesh, attr)
        else:                                # pragma: no cover - guarded above
            raise ValueError("unknown entity kind %r" % e.kind)
        n += 1
    return n


def gusset_to_3dm(joint: GussetJoint, path, *, results=None,
                  field: ThicknessField = None, plate: GussetPlate = None,
                  sections=None, z: float = 0.0, derived: bool = True,
                  unit_system=None) -> int:
    """Write one plate of ``joint`` to ``path`` as a layered ``.3dm``.

    One layer per artifact so a reviewer can toggle them (see the module
    docstring for the list).  ``results`` is the optional rating write-back,
    ``field`` an optional :class:`ThicknessField` overriding the plate's own,
    ``plate`` the plate to draw (default: inside), ``sections`` extra cut
    lines, ``z`` the elevation to bake at (offset the second plate if you
    draw both).  Returns the object count.

    The file is stamped ``Inches``; :func:`gusset_from_3dm` reads it back
    into an equal :class:`~civilpy.structural.gusset_geometry.GussetJoint`.
    """
    r3 = _require_rhino3dm()
    f = r3.File3dm()
    f.Settings.ModelUnitSystem = unit_system or r3.UnitSystem.Inches
    ents = gusset_entities(joint, plate, results=results, field=field,
                           sections=sections, z=z, derived=derived)
    n = _bake_3dm(f, r3, ents)
    if not f.Write(str(path), 7):
        raise IOError("could not write gusset joint to %s" % path)
    return n


# --------------------------------------------------------------------------- #
# live back end: RhinoCommon  ->  the open document
# --------------------------------------------------------------------------- #
def _ensure_layer_doc(doc, full_path, color=None):
    """``ensure_layer`` for a live ``RhinoDoc`` (RhinoCommon, inside Rhino)."""
    import Rhino

    idx = doc.Layers.FindByFullPath(full_path, -1)
    if idx >= 0:
        return idx
    parent_id = None
    accum = ""
    for part in full_path.split("::"):
        accum = part if not accum else accum + "::" + part
        i = doc.Layers.FindByFullPath(accum, -1)
        if i < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = part
            rgba = (color if (accum == full_path and color)
                    else DEFAULT_COLORS.get(accum, (128, 128, 128, 255)))
            try:
                from System.Drawing import Color
                lyr.Color = Color.FromArgb(
                    rgba[3] if len(rgba) > 3 else 255, rgba[0], rgba[1], rgba[2])
            except Exception:                # pragma: no cover - no .NET interop
                pass
            if parent_id is not None:
                lyr.ParentLayerId = parent_id
            i = doc.Layers.Add(lyr)
        parent_id = doc.Layers[i].Id
        idx = i
    return idx


def clear_gusset_layers(doc) -> int:
    """Delete every object on the ``Gusset`` layer tree of a live document, so
    a re-bake replaces the joint instead of stacking a second copy on it.
    Returns the number of objects deleted."""
    n = 0
    for obj in list(doc.Objects):
        try:
            path = doc.Layers[obj.Attributes.LayerIndex].FullPath
        except Exception:                    # pragma: no cover - defensive
            continue
        if path == LAYER_GUSSET or path.startswith(LAYER_GUSSET + "::"):
            if doc.Objects.Delete(obj, True):
                n += 1
    return n


def bake_to_document(joint: GussetJoint, doc=None, *, results=None,
                     field: ThicknessField = None, plate: GussetPlate = None,
                     sections=None, z: float = 0.0, derived: bool = True,
                     clear: bool = True, set_units: bool = True) -> int:
    """Bake one plate of ``joint`` into a **live** Rhino document.

    The RhinoCommon twin of :func:`gusset_to_3dm` -- same entities, same
    layers, same user text -- for driving the open Rhino over its MCP server,
    where ``doc`` is the injected ``__rhino_doc__``.  ``clear`` wipes the
    ``Gusset`` tree first so re-baking is idempotent; ``set_units`` puts the
    document in inches (scaling nothing, since the plate model *is* inches).
    Returns the object count.
    """
    import Rhino
    from Rhino.Geometry import Circle, Mesh, Point3d, Polyline, TextDot

    if doc is None:                          # pragma: no cover - inside Rhino
        doc = Rhino.RhinoDoc.ActiveDoc
    if set_units and doc.ModelUnitSystem != Rhino.UnitSystem.Inches:
        doc.AdjustModelUnitSystem(Rhino.UnitSystem.Inches, False)
    if clear:
        clear_gusset_layers(doc)

    ents = gusset_entities(joint, plate, results=results, field=field,
                           sections=sections, z=z, derived=derived)
    layers = {}
    n = 0
    for e in ents:
        if e.layer not in layers:
            layers[e.layer] = _ensure_layer_doc(doc, e.layer,
                                                DEFAULT_COLORS.get(e.layer))
        attr = Rhino.DocObjects.ObjectAttributes()
        attr.LayerIndex = layers[e.layer]
        if e.name:
            attr.Name = e.name
        for k, v in e.tags.items():
            attr.SetUserString(GTAG + k, v)
        pts = [Point3d(p[0], p[1], p[2]) for p in e.points]
        if e.kind == "point":
            doc.Objects.AddPoint(pts[0], attr)
        elif e.kind == "line":
            doc.Objects.AddLine(pts[0], pts[1], attr)
        elif e.kind == "polyline":
            pl = Polyline()
            for p in pts:
                pl.Add(p)
            doc.Objects.AddPolyline(pl, attr)
        elif e.kind == "circle":
            doc.Objects.AddCircle(Circle(pts[0], e.radius), attr)
        elif e.kind == "dot":
            doc.Objects.AddTextDot(TextDot(e.text, pts[0]), attr)
        elif e.kind == "mesh":
            mesh = Mesh()
            for p in e.points:
                mesh.Vertices.Add(p[0], p[1], p[2])
            for face in e.faces:
                if len(face) == 4:
                    mesh.Faces.AddFace(face[0], face[1], face[2], face[3])
                else:
                    mesh.Faces.AddFace(face[0], face[1], face[2])
            for c in e.colors:
                try:
                    mesh.VertexColors.Add(c[0], c[1], c[2])
                except Exception:            # pragma: no cover - old RhinoCommon
                    break
            doc.Objects.AddMesh(mesh, attr)
        else:                                # pragma: no cover - guarded above
            raise ValueError("unknown entity kind %r" % e.kind)
        n += 1
    doc.Views.Redraw()
    return n


# --------------------------------------------------------------------------- #
# reading a reviewer's document back
# --------------------------------------------------------------------------- #
def _curve_points(g, scale):
    """Vertices of a rhino3dm curve as 2-D plate coordinates."""
    if hasattr(g, "PointCount") and hasattr(g, "Point"):
        return [(g.Point(i).X * scale, g.Point(i).Y * scale)
                for i in range(g.PointCount)]
    a, b = g.PointAtStart, g.PointAtEnd
    return [(a.X * scale, a.Y * scale), (b.X * scale, b.Y * scale)]


def _center_radius(g, scale):
    """Centre and radius of a circle object (baked circles read back as a
    NurbsCurve, so take them from the bounding box)."""
    bb = g.GetBoundingBox()
    cx = (bb.Min.X + bb.Max.X) / 2.0 * scale
    cy = (bb.Min.Y + bb.Max.Y) / 2.0 * scale
    r = max(bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y) / 2.0 * scale
    return (cx, cy), r


def _close_ring(pts):
    """Drop the closing duplicate vertex a baked ring carries."""
    if len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) < 1e-9 \
            and abs(pts[0][1] - pts[-1][1]) < 1e-9:
        return pts[:-1]
    return pts


def _tag_float(tags, key, default=None):
    raw = tags.get(key)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        warnings.warn("%s%s=%r is not a number; using %r" % (GTAG, key, raw, default))
        return default


def _read_objects(path):
    """``(records, scale)`` -- one ``(tags, geometry, name)`` per tagged object."""
    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError("could not read 3dm file: %s" % path)
    scale = _unit_to_inches(f)
    out = []
    for obj in f.Objects:
        us = dict(obj.Attributes.GetUserStrings() or {})
        tags = {k[len(GTAG):]: v for k, v in us.items() if k.startswith(GTAG)}
        if not tags:
            continue
        out.append((tags, obj.Geometry, obj.Attributes.Name or ""))
    return out, scale


def _nearest_member(ends, pt):
    """The member whose work-line ray the point sits closest to (used for
    fasteners a reviewer added without a member tag)."""
    best = None
    best_d = None
    for m in ends:
        s = m.s_of(pt)
        d = abs(m.c_of(pt)) if s >= 0 else math.hypot(pt[0] - m.work_point[0],
                                                      pt[1] - m.work_point[1])
        if best_d is None or d < best_d:
            best, best_d = m, d
    return best


def gusset_from_3dm(path, *, tol: float = 0.35) -> GussetJoint:
    """Read a ``.3dm`` written by :func:`gusset_to_3dm` -- or edited by a
    reviewer -- back into a
    :class:`~civilpy.structural.gusset_geometry.GussetJoint`.

    Only the *input* layers are read: the outline, the fasteners, the member
    work lines and the ``Gusset::Loss`` patches.  Everything else (Whitmore,
    unbraced, block shear, sections, labels) is derived and is recomputed by
    the geometry model, so a moved rivet or a new corrosion patch shows up in
    ``summary()`` immediately.

    A fastener with no ``gus.member`` tag -- one the reviewer drew from
    scratch -- is assigned to the member whose work line it sits closest to.
    """
    recs, scale = _read_objects(path)

    joint_tags = {}
    outline = None
    plate_tags = {}
    members = []
    fasteners = []
    patches = []
    for tags, g, _name in recs:
        kind = tags.get("kind")
        if kind == "joint":
            joint_tags = dict(tags)
            loc = getattr(g, "Location", None)
            if loc is not None:
                joint_tags["_wp"] = (loc.X * scale, loc.Y * scale)
        elif kind == "outline":
            outline = _close_ring(_curve_points(g, scale))
            plate_tags = tags
        elif kind == "workline":
            pts = _curve_points(g, scale)
            ax = (_tag_float(tags, "axis_x"), _tag_float(tags, "axis_y"))
            if ax[0] is None or ax[1] is None:
                ax = (pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
            members.append((tags, pts[0], ax))
        elif kind == "fastener":
            x, y = _tag_float(tags, "x"), _tag_float(tags, "y")
            hole = _tag_float(tags, "hole")
            if x is None or y is None or hole is None:
                (cx, cy), rr = _center_radius(g, scale)
                x = cx if x is None else x
                y = cy if y is None else y
                hole = 2.0 * rr if hole is None else hole
            fasteners.append((tags, x, y, hole))
        elif kind == "loss":
            patches.append((tags, _close_ring(_curve_points(g, scale))))
        # loss_mesh / whitmore / unbraced / blockshear / section / labels and
        # scan_depth are derived display -- ignored by contract.

    if outline is None:
        raise ValueError("no gus.kind=outline object in %s; not a gusset file" % path)

    # -- plate -------------------------------------------------------------
    t_nom = _tag_float(plate_tags, "t_nominal",
                       _tag_float(joint_tags, "t_nominal", 0.5))
    tfield = ThicknessField(t_nom, n_samples=int(_tag_float(joint_tags, "n_samples", 200)))
    for tags, ring in sorted(patches,
                             key=lambda pr: int(_tag_float(pr[0], "idx", 0))):
        tfield.patches.append(ThicknessPatch(
            ring, _tag_float(tags, "t_remaining", t_nom), tags.get("note", "")))
    plate = GussetPlate(outline, tfield,
                        fy=_tag_float(plate_tags, "fy", 45.0),
                        fu=_tag_float(plate_tags, "fu", 70.0),
                        label=plate_tags.get("plate", joint_tags.get("plate", "")))

    # -- work point --------------------------------------------------------
    wp = joint_tags.get("_wp")
    if wp is None:
        wp = members[0][1] if members else (0.0, 0.0)

    # -- members -----------------------------------------------------------
    members.sort(key=lambda mr: int(_tag_float(mr[0], "index", 0)))
    ends = []
    for tags, _start, ax in members:
        ends.append(MemberEnd(
            tags.get("member", ""), wp, ax, [],
            member_type=tags.get("member_type", "diagonal"),
            is_chord=tags.get("is_chord", "False") == "True",
            spliced_at_joint=tags.get("spliced_at_joint", "False") == "True",
            milled_butt=tags.get("milled_butt", "False") == "True"))
    by_name = {m.name: m for m in ends}

    orphans = 0
    for tags, x, y, hole in sorted(
            fasteners,
            key=lambda fr: (fr[0].get("member", ""), int(_tag_float(fr[0], "idx", 0)))):
        fa = Fastener(x, y, _tag_float(tags, "diameter", hole), hole,
                      tags.get("fastener_kind", "rivet"))
        m = by_name.get(tags.get("member", ""))
        if m is None:
            m = _nearest_member(ends, (x, y))
            orphans += 1
        if m is None:
            continue
        m.fasteners.append(fa)
    if orphans:
        warnings.warn("%d fastener(s) had no %smember tag; assigned to the "
                      "nearest work line" % (orphans, GTAG))

    return GussetJoint(
        joint_tags.get("joint", plate_tags.get("joint", "")), wp, plate,
        members=[m for m in ends if m.fasteners],
        fastener_diameter=_tag_float(joint_tags, "fastener_diameter", 1.0))


def read_gusset_results(path) -> dict:
    """The rating write-back stamped on a gusset ``.3dm``: ``edition``,
    ``governing``, ``rf``, the parsed ``checks`` rows, and the same per member
    under ``members``.  The counterpart of ``gusset_to_3dm(results=...)``."""
    recs, _scale = _read_objects(path)

    def unpack(tags):
        out = {k: tags[k] for k in ("edition", "governing", "status", "summary")
               if tags.get(k)}
        for k in ("rf", "rf_inventory", "rf_operating"):
            if tags.get(k) is not None:
                out[k] = _tag_float(tags, k)
        raw = tags.get("checks", "")
        if raw:
            out["checks"] = [r.split("|") for r in raw.splitlines() if r]
        return out

    res = {"members": {}}
    for tags, _g, _n in recs:
        if tags.get("kind") == "joint":
            res.update(unpack(tags))
        elif tags.get("kind") == "member_label":
            res["members"][tags.get("member", "")] = unpack(tags)
    return res


# --------------------------------------------------------------------------- #
# scan -> thickness field -> Rhino
# --------------------------------------------------------------------------- #
def registration_axes(p_origin, p_x, p_plane):
    """Plate axes from three reference points picked in Rhino.

    ``p_origin`` is the plate-coordinate origin (a plate corner), ``p_x`` a
    second point on the plate x axis (the chord direction, or two rivets of
    the same row), and ``p_plane`` any third non-collinear point on the face.
    Returns ``(origin, u, v, normal)`` as 3-vectors, ready to hand to
    :func:`field_from_scan_layer` as ``plate_axes=(u, v)`` and
    ``plane=(origin, normal)``."""
    import numpy as np

    o = np.asarray(p_origin, float)
    u = np.asarray(p_x, float) - o
    u = u / np.linalg.norm(u)
    w = np.asarray(p_plane, float) - o
    n = np.cross(u, w)
    n = n / np.linalg.norm(n)
    v = np.cross(n, u)
    return o, u, v, n


def _depth_color(d: float, dmax: float):
    """Blue (sound) through yellow to red (deepest pit)."""
    t = 0.0 if dmax <= 0 else max(0.0, min(1.0, d / dmax))
    if t < 0.5:
        k = t / 0.5
        return (int(40 + 215 * k), int(110 + 110 * k), int(200 - 160 * k))
    k = (t - 0.5) / 0.5
    return (255, int(220 - 190 * k), int(40 - 10 * k))


def scan_depth_entities(info, z: float = 0.0, min_depth: float = 0.0) -> list:
    """A per-cell depth heat-map mesh on ``Gusset::ScanDepth`` from the
    ``info`` dict :func:`field_from_scan_layer` returns."""
    grid = info["depth_grid"]
    count = info["count_grid"]
    x0, y0, cell = info["x0"], info["y0"], info["cell"]
    ny, nx = grid.shape
    dmax = float(grid.max()) or 1.0
    verts, faces, colors = [], [], []
    for j in range(ny):
        for i in range(nx):
            if not count[j, i] or grid[j, i] < min_depth:
                continue
            d = float(grid[j, i])
            ax, ay = x0 + i * cell, y0 + j * cell
            k = len(verts)
            verts.extend([(ax, ay, z), (ax + cell, ay, z),
                          (ax + cell, ay + cell, z), (ax, ay + cell, z)])
            faces.append((k, k + 1, k + 2, k + 3))
            colors.extend([_depth_color(d, dmax)] * 4)
    if not verts:
        return []
    return [Entity(LAYER_GUSSET_SCANDEPTH, "mesh", verts, faces=faces,
                   name="scan depth", colors=colors,
                   tags={"kind": "scan_depth", "cell": _f(cell), "x0": _f(x0),
                         "y0": _f(y0), "depth_max": _f(dmax),
                         "nx": str(nx), "ny": str(ny)})]


def _field_bbox(info):
    grid = info["depth_grid"]
    ny, nx = grid.shape
    x0, y0, cell = info["x0"], info["y0"], info["cell"]
    return [(x0, y0), (x0 + nx * cell, y0), (x0 + nx * cell, y0 + ny * cell),
            (x0, y0 + ny * cell)]


def _write_scan_3dm(out_path, field, info, joint=None, plate=None, z=0.0):
    r3 = _require_rhino3dm()
    f = r3.File3dm()
    f.Settings.ModelUnitSystem = r3.UnitSystem.Inches
    if joint is not None:
        ents = gusset_entities(joint, plate, field=field, z=z)
    else:
        stub = GussetPlate(_field_bbox(info), field, label="scan")
        ents = gusset_entities(GussetJoint("scan", (0.0, 0.0), stub),
                               field=field, z=z, derived=False)
    ents.extend(scan_depth_entities(info, z=z))
    n = _bake_3dm(f, r3, ents)
    if not f.Write(str(out_path), 7):
        raise IOError("could not write scan results to %s" % out_path)
    return n


def field_from_scan_layer(path, layer, t_nominal, *, plate_axes=None,
                          plane=None, cell: float = 0.5, min_depth: float = 0.03,
                          both_sides: bool = False, out_path=None,
                          joint: GussetJoint = None, plate: GussetPlate = None,
                          z: float = 0.0):
    """Turn a scanned plate face in a ``.3dm`` into a :class:`ThicknessField`.

    Reads the mesh vertices on ``layer`` (an Artec/FARO export imported into
    Rhino), fits the undamaged face plane, bins the depth below it, and
    returns ``(field, info)`` exactly as
    :func:`~civilpy.structural.gusset_geometry.thickness_field_from_points`
    does.

    ``plate_axes`` is the in-plane ``(u, v)`` from :func:`registration_axes`,
    ``plane`` the ``(origin, normal)`` from the same three picked points.
    Without them the scan's own principal directions are used, which is only
    safe if the scan already sits in plate coordinates.

    With ``out_path`` the result is written back as a ``.3dm``: the patches on
    ``Gusset::Loss`` and a depth heat map on ``Gusset::ScanDepth`` -- plus the
    whole joint when ``joint`` is given, so the loss lands under the failure
    planes it affects.  Scanning both faces gives two fields; sum the losses
    per cell with :func:`combine_fields` before rating.
    """
    pts = mesh_vertices_from_3dm(str(path), layer)
    if len(pts) == 0:
        raise ValueError("no mesh vertices on layer %r in %s" % (layer, path))
    if plate_axes is None and plane is None:
        warnings.warn(
            "field_from_scan_layer() got no registration: the scan's own "
            "principal directions become plate x/y, so the loss will be "
            "placed in ROTATED coordinates unless the scan is already in "
            "plate coordinates. Pick three reference points in Rhino and "
            "pass plate_axes=/plane= from registration_axes().", stacklevel=2)
    field, info = thickness_field_from_points(
        pts, t_nominal, cell=cell, min_depth=min_depth, plane=plane,
        axes=plate_axes, both_sides=both_sides)
    if out_path is not None:
        _write_scan_3dm(out_path, field, info, joint=joint, plate=plate, z=z)
    return field, info


def _centroid(poly):
    n = float(len(poly))
    return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)


def combine_fields(*fields) -> ThicknessField:
    """One :class:`ThicknessField` from several -- the two faces of a plate, or
    a scan plus UT readings.

    Loss **adds** where the inputs overlap: a 0.05 in pit on the outside face
    and a 0.04 in pit on the inside face at the same spot leave 0.09 in less
    plate, not 0.05.  ``ThicknessField.t_at`` takes the *minimum* over
    patches, so simply pooling the patches would under-count; each patch is
    therefore re-issued with the other fields' loss at its centroid already
    added in.  Overlaps are resolved at patch-centroid resolution, which is
    exact for the grid-aligned cells a scan produces and approximate for
    hand-sketched polygons that only partly overlap.
    """
    fields = [f for f in fields if f is not None]
    if not fields:
        raise ValueError("combine_fields() needs at least one field")
    t_nom = min(f.t_nominal for f in fields)
    out = ThicknessField(t_nom, n_samples=max(f.n_samples for f in fields))
    for f in fields:
        for p in f.patches:
            loss = f.t_nominal - p.t_remaining
            cen = _centroid(p.polygon)
            extra = sum(max(g.t_nominal - g.t_at(cen), 0.0)
                        for g in fields if g is not f)
            out.patches.append(ThicknessPatch(
                list(p.polygon), max(t_nom - loss - extra, 0.0), p.note))
    return out
