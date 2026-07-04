"""Rhino 3D -> girder-line model (the ``gdr.*`` reader, stage **G4**).

Parses a tagged ``.3dm`` authored by the C# ``GirderLines`` / ``GirderShape`` /
``GirderBearing`` commands into the canonical
:class:`~civilpy.structural.structural_model.StructuralModel` hub, following the
girder / field-splice contract in ``docs/Rhino Design Philosophy.md``:

    Geometry carries what is spatial; tags carry what is scalar.

* **Girder lines** are curves tagged ``gdr.kind=girder`` with ``gdr.shape``
  (AISC label, e.g. ``W24X104``), ``gdr.grade`` (default ``Grade 50``), and
  ``gdr.line`` (girder number).  A polyline yields one :class:`Element` per
  segment (a continuous-span chain); each element carries the resolved AISC
  section label and the grade.
* **Bearings** are points tagged ``gdr.kind=support`` with
  ``gdr.fixity=fixed|expansion`` and ``gdr.line``; they become 6-DOF
  :class:`Restraint`\\ s on the nearest node of their girder line.
* **Bridge parameters** live in document user text (``gdr.deck_t``,
  ``gdr.deck_weff``, ``gdr.deck_fc``, ``gdr.ship_max``, ``gdr.bolt_*``) and are
  returned as a :class:`GirderBridge` alongside the hub.

Plane convention: **PLAN** -- X = stations along the bridge, Y = transverse,
Z = up; lengths in feet (``ModelUnitSystem`` honored on read, mirroring
``rhino_stm``).  ``rhino3dm`` is an optional dependency imported lazily.
"""

#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

from civilpy.structural.rhino_stm import _require_rhino3dm, _unit_to_feet
from civilpy.structural.structural_model import StructuralModel, Units

GTAG = "gdr."  # user-text namespace for the girder pipeline

# gdr.grade -> (Fy, Fu) ksi.  The C# picker offers these names (Gdr.cs
# GradeChoices); they are UI-friendly and do not resolve to civilpy's
# ASTM-named SteelMaterial instances, so the mapping lives here (G1 sign-off
# follow-up #1).  Weathering / HPS grades have no prebuilt SteelMaterial yet.
GRADE_FY_FU: dict[str, tuple[float, float]] = {
    "Grade 36": (36.0, 58.0),
    "Grade 50": (50.0, 65.0),
    "Grade 50W": (50.0, 70.0),
    "HPS 50W": (50.0, 70.0),
    "HPS 70W": (70.0, 85.0),
}
DEFAULT_GRADE = "Grade 50"

# gdr.fixity -> 6-DOF restraint flags, in the PLAN frame (X longitudinal,
# Y transverse, Z vertical).  Bearings restrain translation only (rotations
# free); a fixed bearing holds longitudinal too, an expansion bearing frees it.
FIXITY_DOF: dict[str, dict[str, bool]] = {
    "fixed": {"fix_x": True, "fix_y": True, "fix_z": True},
    "expansion": {"fix_x": False, "fix_y": True, "fix_z": True},
}

# document-level bridge parameters and their units (for the loud-default note)
_DECK_KEYS = {
    "deck_t": "in", "deck_weff": "in", "deck_fc": "ksi",
    "ship_max": "ft", "bolt_dia": "in", "bolt_spec": "-",
    "bolt_hole": "-", "bolt_class": "-",
}
_DECK_DEFAULTS = {
    "deck_fc": 4.0, "ship_max": 100.0, "bolt_dia": 0.875,
    "bolt_spec": "A325", "bolt_hole": "oversize", "bolt_class": "C",
}


@dataclass
class GirderBridge:
    """The canonical hub plus the document-level bridge parameters the girder /
    splice pipeline needs (deck composite section + bolt standard).  Missing
    ``deck_t`` / ``deck_weff`` are ``None`` (a loud warning is issued on read);
    the rest fall back to the ODOT BDM 308.2.2.1.j defaults."""

    model: StructuralModel
    deck_t: float | None = None          # structural slab thickness, in
    deck_weff: float | None = None       # effective flange width, in
    deck_fc: float = 4.0                 # deck concrete strength, ksi
    ship_max: float = 100.0              # max shipping length, ft
    bolt_dia: float = 0.875              # bolt diameter, in
    bolt_spec: str = "A325"
    bolt_hole: str = "oversize"
    bolt_class: str = "C"
    girder_lines: dict[str, list[str]] = field(default_factory=dict)  # line -> element ids


def resolve_shape(label: str):
    """Look up an AISC W-shape by (already-normalized) label via
    ``steel.W``; returns the section or ``None`` (with a warning) if it does not
    resolve.  Import is local so the reader works without the steel db warmed."""
    from civilpy.structural import steel
    try:
        return steel.W(label)
    except Exception as exc:  # pragma: no cover - db-shape specific
        warnings.warn(f"gdr.shape {label!r} did not resolve to an AISC "
                      f"W-shape ({exc}); the element keeps the raw label.")
        return None


def grade_fy_fu(grade: str) -> tuple[float, float]:
    """(Fy, Fu) ksi for a ``gdr.grade`` name; warns + defaults to Grade 50."""
    if grade not in GRADE_FY_FU:
        warnings.warn(f"unknown gdr.grade {grade!r}; assuming {DEFAULT_GRADE}.")
        return GRADE_FY_FU[DEFAULT_GRADE]
    return GRADE_FY_FU[grade]


def _curve_vertices(g, scale):
    """Ordered 3D vertices (scaled to feet) of a line or polyline curve, or
    ``None`` if the geometry is not a readable curve."""
    gtype = type(g).__name__
    pts = []
    if gtype == "PolylineCurve" and hasattr(g, "PointCount"):
        for i in range(g.PointCount):
            p = g.Point(i)
            pts.append((p.X * scale, p.Y * scale, p.Z * scale))
    elif hasattr(g, "PointAtStart") and hasattr(g, "PointAtEnd"):
        a, b = g.PointAtStart, g.PointAtEnd
        pts = [(a.X * scale, a.Y * scale, a.Z * scale),
               (b.X * scale, b.Y * scale, b.Z * scale)]
    else:
        return None
    return pts


def _read_gdr_raw(path):
    """Parse a tagged ``.3dm`` into ``(girders_raw, supports_raw, doc)``.

    * ``girders_raw`` = ``[(vertices, shape, grade, line), ...]`` (feet),
    * ``supports_raw`` = ``[(point, fixity, line), ...]`` (feet),
    * ``doc`` = the document user-text dict (bridge params, raw strings).
    """
    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError(f"could not read 3dm file: {path}")
    scale = _unit_to_feet(f)

    girders_raw, supports_raw, doc = [], [], {}
    for obj in f.Objects:
        attrs = obj.Attributes
        if attrs.IsInstanceDefinitionObject:
            continue
        us = dict(attrs.GetUserStrings() or {})
        kind = us.get(GTAG + "kind")
        g = obj.Geometry
        if kind == "bridge":
            # bridge-wide parameters ride on a dedicated marker object's user
            # text -- NOT RhinoDoc.Strings, which rhino3dm cannot read (see the
            # G4 contract note in docs/Rhino Design Philosophy.md).
            doc.update(us)
            continue
        if kind == "girder":
            verts = _curve_vertices(g, scale)
            if verts is None or len(verts) < 2:
                warnings.warn("gdr.kind=girder object is not a readable "
                              "line/polyline; skipping.")
                continue
            shape = _normalize_shape(us.get(GTAG + "shape", ""))
            grade = us.get(GTAG + "grade", DEFAULT_GRADE)
            line = us.get(GTAG + "line", "")
            girders_raw.append((verts, shape, grade, line))
        elif kind == "support":
            loc = getattr(g, "Location", None)
            if loc is None:
                warnings.warn("gdr.kind=support object is not a point; "
                              "skipping.")
                continue
            pt = (loc.X * scale, loc.Y * scale, loc.Z * scale)
            fixity = us.get(GTAG + "fixity", "fixed")
            supports_raw.append((pt, fixity, us.get(GTAG + "line", "")))

    return girders_raw, supports_raw, doc


def _normalize_shape(label: str) -> str:
    """Match civilpy's ``SteelSection.clean_user_input`` / the C#
    ``Gdr.NormalizeShapeLabel``: strip spaces, uppercase."""
    return label.replace(" ", "").upper()


def _doc_float(doc, key, default=None):
    raw = doc.get(GTAG + key)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        warnings.warn(f"{GTAG}{key}={raw!r} is not a number; using {default!r}.")
        return default


def read_girder_model(path, *, tol=0.5) -> GirderBridge:
    """Read a tagged Rhino ``.3dm`` into a :class:`GirderBridge` (the canonical
    hub + bridge parameters).  One :class:`Element` chain per ``gdr.line``;
    ``Element.section`` is the resolved AISC label, ``Element.material`` the
    grade name.  Bearings become 6-DOF restraints on the nearest node of their
    girder line.

    Parameters
    ----------
    path : str
        Path to the ``.3dm`` file.
    tol : float
        Snap tolerance (feet) for attaching a bearing point to a girder node.
    """
    girders_raw, supports_raw, doc = _read_gdr_raw(path)

    model = StructuralModel(units=Units(force="kips", length="ft"))
    girder_lines: dict[str, list[str]] = {}
    # node id by (rounded) coordinate, so shared bearing/girder points coincide
    node_by_xyz: dict[tuple, str] = {}

    def node_at(pt, label=None):
        key = (round(pt[0], 3), round(pt[1], 3), round(pt[2], 3))
        if key not in node_by_xyz:
            node_by_xyz[key] = model.add_node(pt[0], pt[1], pt[2],
                                              label=label).id
        return node_by_xyz[key]

    for verts, shape, grade, line in girders_raw:
        if shape and resolve_shape(shape) is None:
            pass  # warning already issued; keep the raw label on the element
        grade_fy_fu(grade)  # validate / warn early
        ids = []
        prev = node_at(verts[0])
        for v in verts[1:]:
            cur = node_at(v)
            elem = model.add_element(prev, cur, role="girder",
                                     midas_type="BEAM",
                                     section=shape or None, material=grade)
            elem.metadata["gdr.line"] = line
            ids.append(elem.id)
            prev = cur
        girder_lines.setdefault(line or f"_{len(girder_lines)}", []).extend(ids)

    # attach bearings to the nearest existing node (their girder-line end/support)
    for pt, fixity, line in supports_raw:
        nid = _nearest_node(model, pt, tol)
        if nid is None:
            warnings.warn(f"gdr.kind=support on line {line!r} at {pt} has no "
                          f"girder node within {tol} ft; skipping.")
            continue
        dof = FIXITY_DOF.get(fixity)
        if dof is None:
            warnings.warn(f"unknown gdr.fixity {fixity!r}; treating as fixed.")
            dof = FIXITY_DOF["fixed"]
        model.add_restraint(nid, **dof).preset = fixity

    bridge = _build_bridge(model, doc, girder_lines)
    return bridge


def _nearest_node(model, pt, tol):
    best, bd = None, None
    for node in model.nodes.values():
        d = math.dist((node.x, node.y, node.z), pt)
        if bd is None or d < bd:
            best, bd = node.id, d
    return best if (bd is not None and bd <= tol) else None


def splice_writeback_tags(design) -> dict:
    """Build the ``gdr.status`` / ``gdr.summary`` / ``gdr.checks`` write-back
    tags (stage **G8**) from a
    :class:`~civilpy.structural.aashto.lrfd.bolted_field_splice.SpliceDesign`.

    ``gdr.checks`` is newline-separated ``article|check|actual|allowable|verdict``
    records -- one row per limit state -- the format the C# ``GirderSplice``
    command renders (NG rows red)."""
    def num(v):
        return "-" if v is None else f"{v:.2f}"

    rows = []
    for c in design.checks:
        verdict = "OK" if c.ok else "NG"
        rows.append(f"{c.article}|{c.name}|{num(c.demand)}|"
                    f"{num(c.factored_capacity)}|{verdict}")
    ng = sum(1 for c in design.checks if not c.ok)
    status = "OK" if design.ok else "NG"
    summary = (f"{design.top_flange.total_bolts} bolts/flange, "
               f"web {design.web.total_bolts}; {len(design.checks)} checks"
               + (f", {ng} NG" if ng else ", all OK"))
    return {GTAG + "status": status, GTAG + "summary": summary,
            GTAG + "checks": "\n".join(rows)}


@dataclass
class SpliceMarker:
    """A designed splice to write back: its station point (feet, PLAN), the
    :class:`SpliceDesign`, and the ``gdr.line`` it belongs to."""
    point: tuple            # (x, y, z) in feet
    design: object          # SpliceDesign
    line: str = ""


def write_splice_results(out_path, markers, *, unit_system=None):
    """Author ``gdr.kind=splice`` marker points carrying the G8 write-back tags
    into a new ``.3dm`` for the C# ``GirderSplice`` review command.

    ``markers`` is a list of :class:`SpliceMarker`.  Geometry is written in the
    model's units (``unit_system`` defaults to feet); the plate/bolt *detail*
    geometry is a later enhancement -- the check table travels in the tags.
    Returns the number of markers written.
    """
    r3 = _require_rhino3dm()
    f = r3.File3dm()
    # default to feet so points round-trip 1:1 through _unit_to_feet on read
    f.Settings.ModelUnitSystem = unit_system or r3.UnitSystem.Feet
    for m in markers:
        attr = r3.ObjectAttributes()
        attr.SetUserString(GTAG + "kind", "splice")
        if m.line:
            attr.SetUserString(GTAG + "line", str(m.line))
        for k, v in splice_writeback_tags(m.design).items():
            attr.SetUserString(k, v)
        x, y, z = m.point
        f.Objects.AddPoint(r3.Point3d(x, y, z), attr)
    if not f.Write(str(out_path), 7):
        raise IOError(f"could not write splice results to {out_path}")
    return len(markers)


def read_splice_results(path):
    """Read ``gdr.kind=splice`` markers back from a ``.3dm``: a list of dicts
    with ``point`` (feet), ``line``, ``status``, ``summary``, and ``checks``
    (parsed into ``[article, check, actual, allowable, verdict]`` records).
    Round-trips :func:`write_splice_results` and mirrors what C# reads."""
    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError(f"could not read 3dm file: {path}")
    scale = _unit_to_feet(f)
    out = []
    for obj in f.Objects:
        us = dict(obj.Attributes.GetUserStrings() or {})
        if us.get(GTAG + "kind") != "splice":
            continue
        loc = getattr(obj.Geometry, "Location", None)
        pt = ((loc.X * scale, loc.Y * scale, loc.Z * scale)
              if loc is not None else None)
        raw = us.get(GTAG + "checks", "")
        checks = [r.split("|") for r in raw.splitlines() if r]
        out.append({
            "point": pt, "line": us.get(GTAG + "line", ""),
            "status": us.get(GTAG + "status"),
            "summary": us.get(GTAG + "summary"), "checks": checks})
    return out


def _build_bridge(model, doc, girder_lines) -> GirderBridge:
    deck_t = _doc_float(doc, "deck_t")
    deck_weff = _doc_float(doc, "deck_weff")
    if deck_t is None or deck_weff is None:
        warnings.warn(
            "girder model is missing gdr.deck_t and/or gdr.deck_weff -- the "
            "composite deck section cannot be built without them; supply the "
            "structural slab thickness (in) and effective width (in), or fall "
            "back to ODOT BDM defaults downstream (G5).")
    return GirderBridge(
        model=model,
        deck_t=deck_t,
        deck_weff=deck_weff,
        deck_fc=_doc_float(doc, "deck_fc", _DECK_DEFAULTS["deck_fc"]),
        ship_max=_doc_float(doc, "ship_max", _DECK_DEFAULTS["ship_max"]),
        bolt_dia=_doc_float(doc, "bolt_dia", _DECK_DEFAULTS["bolt_dia"]),
        bolt_spec=doc.get(GTAG + "bolt_spec") or _DECK_DEFAULTS["bolt_spec"],
        bolt_hole=doc.get(GTAG + "bolt_hole") or _DECK_DEFAULTS["bolt_hole"],
        bolt_class=doc.get(GTAG + "bolt_class") or _DECK_DEFAULTS["bolt_class"],
        girder_lines=girder_lines,
    )
