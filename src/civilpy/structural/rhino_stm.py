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
import warnings
from collections import namedtuple

from civilpy.structural.strut_and_tie import StrutAndTieModel
from civilpy.structural.structural_model import MEMBER_TYPES, StructuralModel, Units


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


# rhino3dm ModelUnitSystem name -> pint unit name (for the read-time conversion
# to feet, the STM/Midas length unit).  Names not listed assume feet.
_RHINO_UNIT_TO_PINT = {
    "Inches": "inch", "Feet": "feet", "Yards": "yard", "Miles": "mile",
    "Millimeters": "mm", "Centimeters": "cm", "Decimeters": "dm",
    "Meters": "m", "Kilometers": "km",
}


def _unit_to_feet(f):
    """Conversion factor from a ``.3dm``'s model unit system to **feet** (the
    STM / MIDAS length unit), via the ``civilpy.general.units`` pint registry --
    mirroring ``midas.convert_node_units``.  Falls back to ``1.0`` (assume feet)
    for an unset or unrecognized unit system, so feet-authored files are
    untouched and never import the registry needlessly."""
    try:
        name = f.Settings.ModelUnitSystem.name
    except Exception:                       # pragma: no cover - defensive
        return 1.0
    if name in (None, "Feet", "None", "Unset"):
        return 1.0
    pint_name = _RHINO_UNIT_TO_PINT.get(name)
    if pint_name is None:
        warnings.warn(
            f"unrecognized .3dm model unit {name!r}; assuming feet (no scaling)",
            stacklevel=2,
        )
        return 1.0
    from civilpy.general import units
    return (1 * units(pint_name)).to(units("feet")).magnitude


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
    """Clusters points within a tolerance and hands out stable labels.

    Points are clustered in the 2D analysis plane (so coincident endpoints
    merge), but the first 3D coordinate seen for each cluster is retained in
    ``coords3d`` / ``ordered3d`` so a full-3D
    :class:`~civilpy.structural.structural_model.StructuralModel` can be built
    without re-projecting.
    """

    def __init__(self, tol):
        self.tol = tol
        self.points: list[tuple[float, float]] = []
        self.coords3d: list[tuple[float, float, float]] = []

    def add(self, xy, xyz=None):
        for q in self.points:
            if math.hypot(xy[0] - q[0], xy[1] - q[1]) <= self.tol:
                return
        self.points.append((float(xy[0]), float(xy[1])))
        self.coords3d.append(
            tuple(float(c) for c in xyz) if xyz is not None
            else (float(xy[0]), float(xy[1]), 0.0)
        )

    def finalize(self):
        # bottom-to-top, then left-to-right, so labels read like an elevation
        order = sorted(range(len(self.points)),
                       key=lambda i: (round(self.points[i][1], 6),
                                      self.points[i][0]))
        self.ordered = [self.points[i] for i in order]
        self.ordered3d = [self.coords3d[i] for i in order]
        self.labels = {p: _label(k) for k, p in enumerate(self.ordered)}

    def nearest(self, xy):
        best, bd = None, None
        for p in self.ordered:
            d = math.hypot(xy[0] - p[0], xy[1] - p[1])
            if bd is None or d < bd:
                best, bd = p, d
        return self.labels[best]


# ── Reading: 3dm -> model ─────────────────────────────────────────────────────

def _read_raw(path):
    """Parse a tagged ``.3dm`` into plain Python tuples (no model class yet).

    Returns ``(members_raw, supports_raw, loads_raw, world_pts)`` where

    * ``members_raw`` is ``[(worldA, worldB, member_type), ...]`` (3D endpoints
      plus the ``stm.member`` hint -- ``auto`` (default) / ``tie`` / ``strut``),
    * ``supports_raw`` is ``[(world_pt, dof_dict, preset_or_None), ...]`` with
      the **full 6-DOF** resolved into ``dof_dict``,
    * ``loads_raw`` is ``[(world_pt, world_dir_vec, kips), ...]``, and
    * ``world_pts`` collects every point seen, for plane detection.

    This is the single Rhino parser :func:`read_structural_model` (and, through
    it, :func:`model_from_3dm`) build on -- one reader feeding both consumers,
    so the two never drift.
    """
    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError(f"could not read 3dm file: {path}")

    members_raw = []
    supports_raw = []
    loads_raw = []
    world_pts = []

    # scale every coordinate to feet so coords, the snap tolerance, and arrow
    # lengths are all in the one length unit downstream (forces stay in kips)
    to_ft = _unit_to_feet(f)

    def s(p):
        return (p[0] * to_ft, p[1] * to_ft, p[2] * to_ft)

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
            origin = s((g.Xform.M03, g.Xform.M13, g.Xform.M23))
            world_pts.append(origin)
            if name in BLOCK_SUPPORT or kind == "support":
                preset = BLOCK_SUPPORT.get(name)
                dof = dict(SUPPORT_DOF.get(preset, {})) if preset else {}
                _apply_dof_overrides(dof, us)
                supports_raw.append((origin, dof, us.get(TAG + "support", preset)))
            elif name == BLOCK_LOAD or kind == "load":
                # the block's local +X axis, transformed, is the force direction
                xaxis = (g.Xform.M00, g.Xform.M10, g.Xform.M20)
                kips = float(us.get(TAG + "kips", 0.0))
                loads_raw.append((origin, xaxis, kips))
            continue

        # curves: members (tagged or untagged), or a load drawn as a line
        if hasattr(g, "PointAtStart") and hasattr(g, "PointAtEnd"):
            a, b = g.PointAtStart, g.PointAtEnd
            pa, pb = s((a.X, a.Y, a.Z)), s((b.X, b.Y, b.Z))
            world_pts.extend((pa, pb))
            if kind == "load":
                direction = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
                loads_raw.append((pa, direction, float(us.get(TAG + "kips", 0.0))))
            elif kind == "support":
                dof = {}
                _apply_dof_overrides(dof, us)
                supports_raw.append((pa, dof, us.get(TAG + "support")))
            else:  # member (explicit stm.kind=member or untagged fallback)
                members_raw.append((pa, pb, _member_type(us)))
        elif gtype == "Point" and kind == "support":
            p = s((g.Location.X, g.Location.Y, g.Location.Z))
            world_pts.append(p)
            dof = {}
            _apply_dof_overrides(dof, us)
            supports_raw.append((p, dof, us.get(TAG + "support")))

    return members_raw, supports_raw, loads_raw, world_pts


def read_structural_model(path, *, plane="auto", tol=0.05):
    """Read a tagged Rhino ``.3dm`` into the canonical
    :class:`~civilpy.structural.structural_model.StructuralModel` hub.

    Where :func:`model_from_3dm` returns the lossy 2D :class:`StrutAndTieModel`,
    this preserves everything the MIDAS and IFC adapters need: **full 3D node
    coordinates, the complete 6-DOF restraint** (``stm.fix_*`` -- so
    ``fix_z``/``fix_rx``/``fix_ry``/``fix_rz`` survive, not just the in-plane
    pair the truss solver uses), the support preset, stable object ids, and the
    full 3D load vectors.  This is stage **S2** of the package-coherence track
    in ``docs/Rhino Design Philosophy.md``.

    Parameters
    ----------
    path : str
        Path to the ``.3dm`` file.
    plane : {"auto", "XY", "XZ", "YZ"}
        World plane the model is drawn in, used only to cluster coincident
        endpoints into nodes; ``"auto"`` infers it from the geometry.  The hub
        keeps the genuine 3D coordinates regardless.
    tol : float
        Snapping tolerance (model units) for collapsing coincident endpoints
        into nodes and matching supports/loads to them.
    """
    members_raw, supports_raw, loads_raw, world_pts = _read_raw(path)
    if plane == "auto":
        plane = _detect_plane(world_pts)

    # cluster nodes in the analysis plane, but keep the genuine 3D coordinate
    nodes = _NodeSet(tol)
    for pa, pb, _mtype in members_raw:
        nodes.add(_project(pa, plane), pa)
        nodes.add(_project(pb, plane), pb)
    nodes.finalize()

    model = StructuralModel(units=Units(force="kips", length="ft"))
    id_by_label = {}
    for p2, p3 in zip(nodes.ordered, nodes.ordered3d):
        label = nodes.labels[p2]
        id_by_label[label] = model.add_node(p3[0], p3[1], p3[2], label=label).id

    def nid(pt3):
        return id_by_label[nodes.nearest(_project(pt3, plane))]

    for pa, pb, mtype in members_raw:
        model.add_element(nid(pa), nid(pb), member_type=mtype)
    for pt, dof, preset in supports_raw:
        restraint = model.add_restraint(nid(pt), **dof)
        if preset:
            restraint.preset = preset
    for pt, direction, kips in loads_raw:
        mag = math.sqrt(sum(c * c for c in direction))
        if mag == 0.0 or kips == 0.0:
            continue
        model.add_load(nid(pt), fx=kips * direction[0] / mag,
                       fy=kips * direction[1] / mag,
                       fz=kips * direction[2] / mag)
    return model


def model_from_3dm(path, *, plane="auto", tol=0.05, as_model=False):
    """Read a tagged Rhino ``.3dm`` file into a structural model.

    By default returns a 2D :class:`StrutAndTieModel` (backward compatible) --
    now produced as a thin projection of the canonical hub rather than via a
    second parser.  Pass ``as_model=True`` to get the richer 3D / 6-DOF
    :class:`~civilpy.structural.structural_model.StructuralModel` hub instead
    (equivalent to :func:`read_structural_model`).

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
    as_model : bool
        When ``True`` return the full :class:`StructuralModel` hub instead of
        the projected 2D :class:`StrutAndTieModel`.
    """
    hub = read_structural_model(path, plane=plane, tol=tol)
    if as_model:
        return hub
    _warn_if_not_planar(hub, plane, tol)
    return StrutAndTieModel.from_structural_model(hub, plane=plane)


def _warn_if_not_planar(hub, plane, tol):
    """Warn when the hub's nodes are not planar within ``tol`` -- the 2D STM
    solver silently projects onto the plane, so genuine out-of-plane geometry
    would be flattened without notice.  Use ``read_structural_model`` /
    ``as_model=True`` (which keeps full 3D) for a non-planar model."""
    coords = [n.coords for n in hub.nodes.values()]
    if not coords:
        return
    use_plane = _detect_plane(coords) if plane == "auto" else plane
    normal = _PLANES[use_plane][2]
    spread = max(c[normal] for c in coords) - min(c[normal] for c in coords)
    if spread > tol:
        warnings.warn(
            f"model is not planar: nodes span {spread:g} (> tol {tol:g}) along "
            f"the {use_plane!r} normal axis; the 2D strut-and-tie solver projects "
            f"onto the plane and loses that depth. Use read_structural_model "
            f"(as_model=True) to keep the full 3D model.",
            stacklevel=2,
        )


def _member_type(us):
    """The ``stm.member`` hint (``auto`` default; ``tie``/``strut`` override).

    Per the frozen contract ``auto`` is the never-written default, so an absent
    tag reads as ``auto``.  An unrecognized value warns and falls back to
    ``auto`` rather than failing the whole import.
    """
    val = (us.get(TAG + "member") or "auto").strip().lower()
    if val not in MEMBER_TYPES:
        warnings.warn(
            f"ignoring unknown stm.member={val!r} (expected one of "
            f"{MEMBER_TYPES}); treating member as 'auto'",
            stacklevel=2,
        )
        return "auto"
    return val


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

    member_types = getattr(model, "member_types", {})
    with _gc_paused():
        for na, nb in model.members:
            # auto is the never-written default; only emit a forced override
            extra = ({"member": member_types[(na, nb)]}
                     if member_types.get((na, nb)) in ("tie", "strut") else {})
            f.Objects.AddLine(r3.Point3d(*world(na)), r3.Point3d(*world(nb)),
                              attrs(layers[LAYER_MEMBERS], kind="member", **extra))

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
    creation is left to the in-Rhino authoring tools (``src/civilpy/structural/rhino_scripts/
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
