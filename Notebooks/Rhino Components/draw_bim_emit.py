"""Live-document driver for the civilpy BrIM emit (Rhino 8, CPython 3).

Draws a steel-girder BrIM model from the JSON produced by
``civilpy.structural.rhino_bim.emit_to_json`` — girder solids with true
k-fillets, the crowned deck solid, haunches, shear studs, both rebar
mats, parapets, bearings, and load plates, each stamped with its
``bim.*``/``pay.*``/``mat.*`` user text.  Girder centerlines and bearing
points keep their ``gdr.*`` tags and the bridge-wide keys are mirrored
into the document string table, so the drawn document stays readable by
``civilpy.structural.rhino_gdr`` (the MIDAS pipeline).

Deliberately **pure Rhino** — it never imports civilpy — so it runs
unchanged whether Rhino's own Python environment carries a current
civilpy or none at all.  Generate the payload wherever civilpy lives
(a notebook, an MCP agent's environment):

    from civilpy.structural.bridge_layout import BridgeInput
    from civilpy.structural.rhino_bim import girder_bridge_emit, emit_to_json
    emit = girder_bridge_emit(BridgeInput(...))
    open(path, "w").write(emit_to_json(emit))

then run ``draw_bim_emit(path)`` inside Rhino (set ``EMIT_JSON_PATH``
below when running as a script).  Coordinates in the payload are feet;
the driver scales into the document's unit system — the model template
should still be **Large Objects – Feet + Inches** per the work plan.
"""

import json
import math

import Rhino
import Rhino.Geometry as rg
import System.Drawing as sd

EMIT_JSON_PATH = ""     # set when running as a plain script

#: Layers the driver owns: cleared before redrawing so regeneration
#: replaces the previous model instead of stacking a second one.
_CLEAR_DEFAULT = True


def _doc():
    return globals().get("__rhino_doc__") or Rhino.RhinoDoc.ActiveDoc


def _scale(doc):
    return Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Feet,
                                     doc.ModelUnitSystem)


def _ensure_layer(doc, path, rgb):
    idx = doc.Layers.FindByFullPath(path, -1)
    if idx >= 0:
        return idx
    parent = None
    accum = ""
    for name in path.split("::"):
        accum = name if not accum else accum + "::" + name
        idx = doc.Layers.FindByFullPath(accum, -1)
        if idx < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = name
            lyr.Color = sd.Color.FromArgb(*rgb)
            if parent is not None:
                lyr.ParentLayerId = doc.Layers[parent].Id
            idx = doc.Layers.Add(lyr)
        parent = idx
    return idx


def _attrs(doc, layer_index, tags):
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = layer_index
    for k, v in (tags or {}).items():
        a.SetUserString(k, str(v))
    return a


def _prism(doc, pts, vector, attrs, tol):
    """Closed planar loop extruded along ``vector``: loft the loop and its
    translate, then cap."""
    loop = [rg.Point3d(*p) for p in pts]
    move = rg.Vector3d(*vector)
    a = rg.Polyline(loop + [loop[0]]).ToNurbsCurve()
    b = a.DuplicateCurve()
    b.Translate(move)
    lofted = rg.Brep.CreateFromLoft([a, b], rg.Point3d.Unset,
                                    rg.Point3d.Unset, rg.LoftType.Straight,
                                    False)
    if not lofted:
        return None
    solid = lofted[0].CapPlanarHoles(tol) or lofted[0]
    return doc.Objects.AddBrep(solid, attrs)


def _is_axial(vp):
    d = vp.CameraDirection
    d.Unitize()
    return max(abs(d.X), abs(d.Y), abs(d.Z)) > 0.999


def set_bridge_views(doc, bbox=None):
    """Aim the standard viewports at the bridge convention (X = stations,
    Y transverse):

    * **Front** — the cross-section, camera looking up-station (+X), the
      direction typical sections are drawn looking;
    * **Right** — the profile/elevation, camera looking +Y so stations
      increase to screen right;
    * a Perspective panel that an earlier session's ``SetProjection``
      renamed to a duplicate "Front"/"Right" is restored.

    Rhino's out-of-the-box Front/Right are backwards for this frame
    (Front would show the profile), so the driver re-aims them on every
    redraw.  Idempotent; safe on an empty document."""
    if bbox is None:
        bbox = rg.BoundingBox.Empty
        for o in doc.Objects:
            bbox.Union(o.Geometry.GetBoundingBox(True))
    if not bbox.IsValid:
        bbox = rg.BoundingBox(rg.Point3d(0, 0, -10), rg.Point3d(100, 40, 5))
    center = bbox.Center
    span = max(bbox.Diagonal.Length, 1.0)

    named = {}
    for view in doc.Views:
        named.setdefault(view.ActiveViewport.Name, []).append(view)

    if "Perspective" not in named:
        for views in named.values():
            if len(views) > 1:
                stray = next((v for v in views
                              if not _is_axial(v.ActiveViewport)), None)
                if stray is not None:
                    vp = stray.ActiveViewport
                    vp.Name = "Perspective"
                    vp.ChangeToPerspectiveProjection(True, 50.0)
                    vp.SetCameraLocations(
                        center, center + rg.Vector3d(-0.45 * span,
                                                     -0.65 * span,
                                                     0.35 * span))
                    stray.ActiveViewport.ZoomExtents()
                    views.remove(stray)
                    break

    aims = {"Front": rg.Vector3d(1.0, 0.0, 0.0),      # up-station: section
            "Right": rg.Vector3d(0.0, 1.0, 0.0)}      # cross-bridge: profile
    for name, aim in aims.items():
        views = named.get(name, [])
        if not views:
            continue
        view = next((v for v in views if _is_axial(v.ActiveViewport)),
                    views[0])
        vp = view.ActiveViewport
        vp.ChangeToParallelProjection(True)
        vp.SetCameraLocations(center, center - aim * span)
        vp.CameraUp = rg.Vector3d.ZAxis
        vp.ZoomExtents()
    doc.Views.Redraw()


def draw_bim_emit(json_path=None, clear=_CLEAR_DEFAULT):
    """Draw (or redraw) the BrIM model from an emit JSON file.  Returns a
    per-layer object-count report string."""
    doc = _doc()
    tol = doc.ModelAbsoluteTolerance
    s = _scale(doc)
    data = json.load(open(json_path or EMIT_JSON_PATH))

    layer_idx = {}
    for name, rgb in data["layers"].items():
        layer_idx[name] = _ensure_layer(doc, name, rgb)

    if clear:
        for name, idx in layer_idx.items():
            for o in list(doc.Objects.FindByLayer(doc.Layers[idx])):
                doc.Objects.Delete(o, True)

    counts = {}
    for obj in data["objects"]:
        idx = layer_idx[obj["layer"]]
        attrs = _attrs(doc, idx, obj["tags"])
        pts = [tuple(c * s for c in p) for p in obj["points"]]
        kind = obj["kind"]
        added = None
        if kind == "prism":
            vec = tuple(c * s for c in obj["vector"])
            added = _prism(doc, pts, vec, attrs, tol)
        elif kind == "polyline":
            added = doc.Objects.AddPolyline(
                rg.Polyline([rg.Point3d(*p) for p in pts]), attrs)
        elif kind == "cylinder":
            base, tip = rg.Point3d(*pts[0]), rg.Point3d(*pts[1])
            axis = tip - base
            plane = rg.Plane(base, axis)
            cyl = rg.Cylinder(rg.Circle(plane, obj["radius_ft"] * s),
                              axis.Length)
            added = doc.Objects.AddBrep(cyl.ToBrep(True, True), attrs)
        elif kind == "point":
            added = doc.Objects.AddPoint(rg.Point3d(*pts[0]), attrs)
        if added is not None:
            counts[obj["layer"]] = counts.get(obj["layer"], 0) + 1

    # mirror the bridge-wide keys for the rhino_gdr document-tag reader
    for k, v in data["doc_tags"].items():
        doc.Strings.SetString(k, str(v))

    set_bridge_views(doc)
    return "\n".join(f"{k}: {v}" for k, v in sorted(counts.items()))


if __name__ == "__main__":
    print(draw_bim_emit())
