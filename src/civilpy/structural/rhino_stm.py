"""Rhino 3D <-> strut-and-tie interchange.

Bridges a Rhino ``.3dm`` model and :class:`~civilpy.structural.strut_and_tie.
StrutAndTieModel` using the convention documented in
``docs/Rhino Design Philosophy.md``:

    Geometry carries what is spatial; tags carry what is scalar.

* **Members** are curves tagged ``stm.kind=member`` (an untagged curve falls
  back to a member, so quick sketches still import).
* **Supports** are block instances (``STM_Pin`` / ``STM_Roller_V`` /
  ``STM_Roller_H`` / ``STM_Fixed``) at a node; the block name sets the common
  fixity and ``stm.fix_*`` user text overrides it.  Full 6-DOF is recorded for
  future frame/Midas use; the 2D STM solver consumes only the in-plane
  translations.
* **Loads** are ``STM_Load`` arrow blocks (or plain tagged lines).  The arrow's
  orientation *is* the force direction; ``stm.kips`` carries the magnitude.

Nodes are not authored explicitly -- they are derived by snapping member
endpoints together within a tolerance and auto-labeling A, B, C... ordered
bottom-to-top then left-to-right (so labels read like an elevation).

The model is drawn flat in a world plane (the FHWA examples use **XZ**, a front
elevation).  ``plane="auto"`` detects it; ``X``/``Z`` map to the analysis
``x``/``y`` with gravity along ``-Z``.

``rhino3dm`` is an optional dependency (``pip install civilpy[rhino]``); it is
imported lazily so the rest of :mod:`civilpy.structural` works without it.
"""

#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

import contextlib
import gc
import math
from collections import namedtuple

from civilpy.structural.strut_and_tie import StrutAndTieModel
from civilpy.structural.structural_model import MEMBER_TYPES, StructuralModel


@contextlib.contextmanager
def _gc_paused():
    """Pause Python's cyclic garbage collector.

    rhino3dm (8.x) does not take ownership of geometry/attributes handed to
    ``InstanceDefinitions.Add`` and friends; a cyclic-GC pass during model
    construction can free objects out from under it and crash the interpreter.
    Pausing GC across the build + ``Write`` avoids this.
    """
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()

# ── Convention constants ──────────────────────────────────────────────────────

TAG = "stm."  # user-text namespace

BLOCK_PIN = "STM_Pin"
BLOCK_ROLLER_V = "STM_Roller_V"
BLOCK_ROLLER_H = "STM_Roller_H"
BLOCK_FIXED = "STM_Fixed"
BLOCK_LOAD = "STM_Load"

LAYER_MEMBERS = "STM::Members"
LAYER_SUPPORTS = "STM::Supports"
LAYER_LOADS = "STM::Loads"
LAYER_RESULTS = "STM::Results"

# the six rigid-body DOF, in order; STM uses the first two (in-plane translation)
DOF_KEYS = ("fix_x", "fix_y", "fix_z", "fix_rx", "fix_ry", "fix_rz")

# support type -> set DOF that are fixed (true)
SUPPORT_DOF: dict[str, dict[str, bool]] = {
    "pin": {"fix_x": True, "fix_y": True},
    "roller-v": {"fix_y": True},
    "roller-h": {"fix_x": True},
    "fixed": {"fix_x": True, "fix_y": True, "fix_rz": True},
}
BLOCK_SUPPORT = {
    BLOCK_PIN: "pin",
    BLOCK_ROLLER_V: "roller-v",
    BLOCK_ROLLER_H: "roller-h",
    BLOCK_FIXED: "fixed",
}
# layer colors (R, G, B, A)
_LAYER_COLORS = {
    LAYER_MEMBERS: (40, 40, 40, 255),
    LAYER_SUPPORTS: (0, 110, 200, 255),
    LAYER_LOADS: (0, 150, 0, 255),
    LAYER_RESULTS: (160, 160, 160, 255),
}


def _require_rhino3dm():
    try:
        import rhino3dm
    except ImportError as exc:  # pragma: no cover - exercised only without dep
        raise ImportError(
            "rhino3dm is required for Rhino interchange; install it with "
            "`pip install civilpy[rhino]` or `pip install rhino3dm`."
        ) from exc
    return rhino3dm


# ── Plane projection (3D world <-> 2D analysis) ───────────────────────────────

# each plane: (index of the in-plane axes for x and y, index of the normal axis)
_PLANES = {"XY": (0, 1, 2), "XZ": (0, 2, 1), "YZ": (1, 2, 0)}


def _project(triple, plane):
    ix, iy, _ = _PLANES[plane]
    return triple[ix], triple[iy]


def _unproject(xy, plane):
    """2D analysis (x, y) -> world (X, Y, Z) with the out-of-plane coord 0."""
    ix, iy, _ = _PLANES[plane]
    out = [0.0, 0.0, 0.0]
    out[ix], out[iy] = xy
    return tuple(out)


def _detect_plane(points):
    """Pick the world plane the geometry lies in: the axis with the smallest
    spread is the normal."""
    if not points:
        return "XZ"
    spread = [
        max(p[k] for p in points) - min(p[k] for p in points) for k in range(3)
    ]
    normal = spread.index(min(spread))
    return {2: "XY", 1: "XZ", 0: "YZ"}[normal]


# ── Node labeling ─────────────────────────────────────────────────────────────

def _label(i):
    """0->A, 25->Z, 26->AA ..."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


class _NodeSet:
    """Clusters 2D points within a tolerance and hands out stable labels."""

    def __init__(self, tol):
        self.tol = tol
        self.points: list[tuple[float, float]] = []

    def add(self, xy):
        for q in self.points:
            if math.hypot(xy[0] - q[0], xy[1] - q[1]) <= self.tol:
                return
        self.points.append((float(xy[0]), float(xy[1])))

    def finalize(self):
        # bottom-to-top, then left-to-right, so labels read like an elevation
        self.ordered = sorted(self.points, key=lambda p: (round(p[1], 6), p[0]))
        self.labels = {p: _label(i) for i, p in enumerate(self.ordered)}

    def nearest(self, xy):
        best, bd = None, None
        for p in self.ordered:
            d = math.hypot(xy[0] - p[0], xy[1] - p[1])
            if bd is None or d < bd:
                best, bd = p, d
        return self.labels[best]


# ── Reading: 3dm -> model ─────────────────────────────────────────────────────

def model_from_3dm(path, *, plane="auto", tol=0.05):
    """Read a tagged Rhino ``.3dm`` file into a :class:`StrutAndTieModel`.

    Parameters
    ----------
    path : str
        Path to the ``.3dm`` file.
    plane : {"auto", "XY", "XZ", "YZ"}
        World plane the model is drawn in.  ``"auto"`` infers it from the
        geometry (the near-constant axis is the normal).
    tol : float
        Snapping tolerance (model units) for collapsing coincident endpoints
        into nodes and matching supports/loads to them.
    """
    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError(f"could not read 3dm file: {path}")

    members_raw = []   # (worldA, worldB)
    supports_raw = []  # (world_pt, dof_dict)
    loads_raw = []     # (world_pt, world_dir_vec, kips)
    world_pts = []     # for plane detection

    for obj in f.Objects:
        attrs = obj.Attributes
        # the curves that make up the block definitions live in the object
        # table too, flagged -- they are not part of the model
        if attrs.IsInstanceDefinitionObject:
            continue
        g = obj.Geometry
        us = dict(attrs.GetUserStrings() or {})
        kind = us.get(TAG + "kind")
        gtype = type(g).__name__

        if gtype == "InstanceReference":
            defn = f.InstanceDefinitions.FindId(g.ParentIdefId)
            name = defn.Name if defn else ""
            origin = (g.Xform.M03, g.Xform.M13, g.Xform.M23)
            world_pts.append(origin)
            if name in BLOCK_SUPPORT or kind == "support":
                dof = dict(SUPPORT_DOF.get(BLOCK_SUPPORT.get(name, ""), {}))
                _apply_dof_overrides(dof, us)
                supports_raw.append((origin, dof))
            elif name == BLOCK_LOAD or kind == "load":
                # the block's local +X axis, transformed, is the force direction
                xaxis = (g.Xform.M00, g.Xform.M10, g.Xform.M20)
                kips = float(us.get(TAG + "kips", 0.0))
                loads_raw.append((origin, xaxis, kips))
            continue

        # curves: members (tagged or untagged), or a load drawn as a line
        if hasattr(g, "PointAtStart") and hasattr(g, "PointAtEnd"):
            a, b = g.PointAtStart, g.PointAtEnd
            pa, pb = (a.X, a.Y, a.Z), (b.X, b.Y, b.Z)
            world_pts.extend((pa, pb))
            if kind == "load":
                direction = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
                loads_raw.append((pa, direction, float(us.get(TAG + "kips", 0.0))))
            elif kind == "support":
                dof = {}
                _apply_dof_overrides(dof, us)
                supports_raw.append((pa, dof))
            else:  # member (explicit stm.kind=member or untagged fallback)
                members_raw.append((pa, pb))
        elif gtype == "Point" and kind == "support":
            p = g.Location
            world_pts.append((p.X, p.Y, p.Z))
            dof = {}
            _apply_dof_overrides(dof, us)
            supports_raw.append(((p.X, p.Y, p.Z), dof))

    if plane == "auto":
        plane = _detect_plane(world_pts)

    # build nodes from member endpoints
    nodes = _NodeSet(tol)
    for pa, pb in members_raw:
        nodes.add(_project(pa, plane))
        nodes.add(_project(pb, plane))
    nodes.finalize()

    model = StrutAndTieModel()
    for p in nodes.ordered:
        model.add_node(nodes.labels[p], p[0], p[1])
    for pa, pb in members_raw:
        model.add_member(nodes.nearest(_project(pa, plane)),
                         nodes.nearest(_project(pb, plane)))
    for pt, dof in supports_raw:
        model.add_support(nodes.nearest(_project(pt, plane)),
                          fix_x=bool(dof.get("fix_x")),
                          fix_y=bool(dof.get("fix_y")))
    for pt, direction, kips in loads_raw:
        dx, dy = _project(direction, plane)
        mag = math.hypot(dx, dy)
        if mag == 0.0 or kips == 0.0:
            continue
        model.add_load(nodes.nearest(_project(pt, plane)),
                       fx=kips * dx / mag, fy=kips * dy / mag)
    return model


def problem_from_3dm(path, *, plane="auto", nu=0.2):
    """Read a tagged Rhino ``.3dm`` authored with the *region* workflow into a
    :class:`~civilpy.structural.stm_topology.problem.DRegionProblem`.

    The file holds one closed ``stm.kind=region`` curve (the concrete D-region)
    carrying ``stm.thickness`` (ft) and ``stm.fc`` (ksi), optionally
    ``stm.E``/``stm.nu``/``stm.vol_frac``; optional ``stm.kind=void`` /
    ``stm.kind=solid`` inner curves; and the same supports and loads as the
    drawn-truss workflow, optionally with an ``stm.bearing`` (ft) width.  See
    ``docs/Rhino Design Philosophy.md`` (§"Two front ends").
    """
    from civilpy.structural.stm_topology.problem import (
        DRegionProblem, Material, Support, Load,
    )

    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError(f"could not read 3dm file: {path}")

    region = None          # (polygon_pts_world, tags_dict)
    voids, solids = [], []
    supports_raw = []      # (world_pt, dof_dict, bearing)
    loads_raw = []         # (world_pt, world_dir, kips, bearing)
    world_pts = []

    for obj in f.Objects:
        attrs = obj.Attributes
        if attrs.IsInstanceDefinitionObject:
            continue
        g = obj.Geometry
        us = dict(attrs.GetUserStrings() or {})
        kind = us.get(TAG + "kind")
        bearing = us.get(TAG + "bearing")
        bearing = float(bearing) if bearing not in (None, "") else None
        gtype = type(g).__name__

        if gtype == "InstanceReference":
            defn = f.InstanceDefinitions.FindId(g.ParentIdefId)
            name = defn.Name if defn else ""
            origin = (g.Xform.M03, g.Xform.M13, g.Xform.M23)
            world_pts.append(origin)
            if name in BLOCK_SUPPORT or kind == "support":
                dof = dict(SUPPORT_DOF.get(BLOCK_SUPPORT.get(name, ""), {}))
                _apply_dof_overrides(dof, us)
                supports_raw.append((origin, dof, bearing))
            elif name == BLOCK_LOAD or kind == "load":
                xaxis = (g.Xform.M00, g.Xform.M10, g.Xform.M20)
                kips = float(us.get(TAG + "kips", 0.0))
                loads_raw.append((origin, xaxis, kips, bearing))
            continue

        if kind == "region" or kind == "void" or kind == "solid":
            poly = _curve_points(g)
            world_pts.extend(poly)
            if kind == "region":
                region = (poly, us)
            elif kind == "void":
                voids.append(poly)
            else:
                solids.append(poly)
        elif hasattr(g, "PointAtStart") and hasattr(g, "PointAtEnd"):
            a, b = g.PointAtStart, g.PointAtEnd
            pa, pb = (a.X, a.Y, a.Z), (b.X, b.Y, b.Z)
            world_pts.extend((pa, pb))
            if kind == "load":
                direction = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
                loads_raw.append((pa, direction, float(us.get(TAG + "kips", 0.0)), bearing))
            elif kind == "support":
                dof = {}
                _apply_dof_overrides(dof, us)
                supports_raw.append((pa, dof, bearing))
        elif gtype == "Point" and kind == "support":
            p = g.Location
            world_pts.append((p.X, p.Y, p.Z))
            dof = {}
            _apply_dof_overrides(dof, us)
            supports_raw.append(((p.X, p.Y, p.Z), dof, bearing))

    if region is None:
        raise ValueError(
            "no stm.kind=region curve found — this file is not a topology-"
            "optimization problem (use model_from_3dm for a drawn truss)")
    if plane == "auto":
        plane = _detect_plane(world_pts)

    poly, tags = region
    boundary = [_project(p, plane) for p in poly]
    material = Material(
        f_c=float(tags.get(TAG + "fc", 5.0)),
        E=float(tags[TAG + "E"]) if tags.get(TAG + "E") else None,
        nu=float(tags.get(TAG + "nu", nu)),
    )
    problem = DRegionProblem(
        boundary=boundary,
        thickness=float(tags.get(TAG + "thickness", 1.0)),
        material=material,
        voids=[[_project(p, plane) for p in v] for v in voids],
        solids=[[_project(p, plane) for p in s] for s in solids],
        vol_frac=float(tags.get(TAG + "vol_frac", 0.3)),
    )
    for pt, dof, bearing in supports_raw:
        x, y = _project(pt, plane)
        problem.add_support(x, y, fix_x=bool(dof.get("fix_x")),
                            fix_y=bool(dof.get("fix_y")), bearing=bearing)
    for pt, direction, kips, bearing in loads_raw:
        dx, dy = _project(direction, plane)
        mag = math.hypot(dx, dy)
        if mag == 0.0 or kips == 0.0:
            continue
        x, y = _project(pt, plane)
        problem.add_load(x, y, fx=kips * dx / mag, fy=kips * dy / mag, bearing=bearing)
    return problem


def _curve_points(g, n=96):
    """Return a polygon ``[(X,Y,Z), ...]`` for a closed Rhino curve, preferring
    its polyline form and falling back to uniform sampling."""
    pl = None
    if hasattr(g, "TryGetPolyline"):
        try:
            ok = g.TryGetPolyline()
            pl = ok[1] if isinstance(ok, (tuple, list)) else ok
        except Exception:
            pl = None
    pts = []
    if pl is not None and hasattr(pl, "__len__") and len(pl):
        for i in range(len(pl)):
            p = pl[i]
            pts.append((p.X, p.Y, p.Z))
    elif hasattr(g, "PointAt") and hasattr(g, "Domain"):
        d = g.Domain
        for i in range(n):
            t = d.T0 + (d.T1 - d.T0) * i / n
            p = g.PointAt(t)
            pts.append((p.X, p.Y, p.Z))
    # drop a duplicated closing point
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _apply_dof_overrides(dof, us):
    """Overlay explicit ``stm.fix_*`` and ``stm.support`` user text onto a DOF
    dict (mutates in place)."""
    support = us.get(TAG + "support")
    if support in SUPPORT_DOF:
        dof.update(SUPPORT_DOF[support])
    for key in DOF_KEYS:
        val = us.get(TAG + key)
        if val is not None:
            dof[key] = str(val).strip().lower() in ("1", "true", "yes")


# ── Writing: model -> 3dm ─────────────────────────────────────────────────────

def model_to_3dm(model, path, *, plane="XZ", arrow_len=1.0, version=7):
    """Author a :class:`StrutAndTieModel` as a tagged ``.3dm`` file.

    Members are tagged lines, supports are tagged points (``stm.support`` plus
    the ``stm.fix_*`` flags), and loads are tagged arrow lines drawn from the
    node in the force direction with the magnitude in ``stm.kips``.  This keeps
    the writer to the rock-solid ``AddLine``/``AddPoint`` paths; the richer
    symbol *blocks* live in the template (:func:`build_template`) and are
    inserted by the in-Rhino authoring tools, and the reader understands both
    representations.

    ``arrow_len`` is the drawn length of load arrows in model units (purely
    visual; magnitude comes from the tag).
    """
    r3 = _require_rhino3dm()
    f = r3.File3dm()
    f.Settings.ModelUnitSystem = r3.UnitSystem.Feet
    layers = _ensure_layers(f, r3)
    keep = []  # hold attributes alive until after Write (see _gc_paused)

    def world(label):
        return _unproject(model.nodes[label], plane)

    def attrs(layer, **strings):
        a = r3.ObjectAttributes()
        a.LayerIndex = layer
        for k, v in strings.items():
            a.SetUserString(TAG + k, v)
        keep.append(a)
        return a

    with _gc_paused():
        for na, nb in model.members:
            f.Objects.AddLine(r3.Point3d(*world(na)), r3.Point3d(*world(nb)),
                              attrs(layers[LAYER_MEMBERS], kind="member"))

        for node, (fix_x, fix_y) in model.supports.items():
            stype = ("pin" if fix_x and fix_y
                     else "roller-h" if fix_x else "roller-v")
            f.Objects.AddPoint(
                r3.Point3d(*world(node)),
                attrs(layers[LAYER_SUPPORTS], kind="support", support=stype,
                      fix_x=str(bool(fix_x)).lower(),
                      fix_y=str(bool(fix_y)).lower()),
            )

        for node, (fx, fy) in model.loads.items():
            kips = math.hypot(fx, fy)
            if kips == 0.0:
                continue
            x, y = model.nodes[node]
            tip = (x + fx / kips * arrow_len, y + fy / kips * arrow_len)
            f.Objects.AddLine(
                r3.Point3d(*world(node)), r3.Point3d(*_unproject(tip, plane)),
                attrs(layers[LAYER_LOADS], kind="load", kips=f"{kips:g}"),
            )

        if not f.Write(str(path), version):
            raise IOError(f"failed to write 3dm file: {path}")
    return path


def results_to_3dm(model, path, *, plane="XZ", version=7):
    """Write a solved model for review in Rhino: ties red, struts blue, with a
    text dot of the member force at each midpoint and reactions at supports."""
    r3 = _require_rhino3dm()
    if model.forces is None:
        model.solve()
    f = r3.File3dm()
    f.Settings.ModelUnitSystem = r3.UnitSystem.Feet
    layers = _ensure_layers(f, r3)
    keep = []

    def world(label):
        return _unproject(model.nodes[label], plane)

    with _gc_paused():
        for (na, nb), force in model.forces.items():
            a, b = world(na), world(nb)
            attr = r3.ObjectAttributes()
            attr.LayerIndex = layers[LAYER_RESULTS]
            attr.ObjectColor = ((200, 0, 0, 255) if force > 1e-9
                                else (0, 0, 255, 255))
            attr.ColorSource = r3.ObjectColorSource.ColorFromObject
            keep.append(attr)
            f.Objects.AddLine(r3.Point3d(*a), r3.Point3d(*b), attr)
            mid = r3.Point3d((a[0] + b[0]) / 2, (a[1] + b[1]) / 2,
                             (a[2] + b[2]) / 2)
            f.Objects.AddTextDot(f"{force:+.1f}", mid)

        if model.reactions:
            for node, (rx, ry) in model.reactions.items():
                f.Objects.AddTextDot(f"R=({rx:+.1f},{ry:+.1f})",
                                     r3.Point3d(*world(node)))

        if not f.Write(str(path), version):
            raise IOError(f"failed to write 3dm file: {path}")
    return path


# ── Template + layer construction ─────────────────────────────────────────────

def build_template(path, *, version=7):
    """Write a starter ``.3dm`` (units feet) holding the STM layers, ready to
    draw into.

    The symbol *block definitions* (pin / rollers / fixed / load arrow) are
    intentionally **not** baked in here: rhino3dm 8.x's
    ``InstanceDefinitions.Add`` corrupts memory probabilistically, so block
    creation is left to the in-Rhino authoring tools (``tools/rhino/
    stm_authoring.py``), where RhinoCommon creates them reliably on first use.
    The reader (:func:`model_from_3dm`) understands those Rhino-authored block
    symbols as well as the tagged points/lines this package writes.
    """
    r3 = _require_rhino3dm()
    f = r3.File3dm()
    f.Settings.ModelUnitSystem = r3.UnitSystem.Feet
    _ensure_layers(f, r3)
    if not f.Write(str(path), version):
        raise IOError(f"failed to write 3dm file: {path}")
    return path


def _ensure_layers(f, r3):
    existing = {layer.FullPath: layer.Index for layer in f.Layers}
    out = {}
    for name, color in _LAYER_COLORS.items():
        if name in existing:
            out[name] = existing[name]
            continue
        layer = r3.Layer()
        layer.Name = name
        layer.Color = color
        out[name] = f.Layers.Add(layer)
    return out
