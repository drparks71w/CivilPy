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

    doc.Views.Redraw()
    return "\n".join(f"{k}: {v}" for k, v in sorted(counts.items()))


if __name__ == "__main__":
    print(draw_bim_emit())
