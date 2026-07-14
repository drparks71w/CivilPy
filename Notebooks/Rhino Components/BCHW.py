# r: civilpy
"""ODOT BCHW Box Culvert Headwall/Wingwall — GHPython (Rhino 8, CPython 3)
source.

Drop-in Grasshopper component for the BCHW plan insert (rev. 01-21-2022):
one cast-in-place wingwall corner — tapered wingwall stem, foreslope wall,
cutoff wall, L-shaped footing, and the nominal WW5xx/FS5xx/F6xx reinforcing
mats — as true solids + rebar curves from the
``civilpy.structural.rhino_bchw`` BrIM emit (the same tagged-record
architecture as the steel-girder and box-beam components). All engineering
content comes from that module; this script only draws.

Frame: box culvert wall face contains y = 0 (the wingwall flares out to
y = length, sheared by the skew), x = 0 at the wingwall root (foreslope
wall runs -x along the culvert face), z = 0 at the top of footing.

Component inputs (Type Hint / Access in parentheses):
    length       (float, Item)  wingwall length L, ft
    skew         (float, Item)  box culvert skew, degrees (optional, 0)
    wall_height  (float, Item)  wingwall height H at the box face, ft
    foreslope_height (float, Item)  hf, foreslope wall height, ft
    cutoff_height    (float, Item)  hcw, cutoff wall depth below top of
                                    footing (extends to z = -hcw), ft
    footing_width    (float, Item)  Wf, perpendicular to the wall, ft
    box_wall_thickness (float, Item)  t box, in -- also the wall stem
                                    thickness of every drawn wall
    foreslope_run    (float, Item)  foreslope/cutoff wall run from the
                                    wingwall root along the culvert face
                                    (typically half the box span + t), ft
    footing_thickness (float, Item) tf, ft (optional, 1.5)
    rebar        (bool, Item)   draw the reinforcing mats (optional, True)
    bake         (bool, Item)   write tagged geometry to the Culvert layers
Outputs:
    solids  (Brep, List)   wingwall / foreslope / cutoff / footing solids
    rebar_crvs (Curve, List)  reinforcing bar centerlines
    report  (str)          pay-item quantity rollup + notes

Baked objects carry their full ``bim.*`` / ``pay.*`` / ``mat.*`` user text
on the ``Culvert::*`` layers, so ``read_bim_quantities`` regenerates the
estimate from the saved document.
"""

"""
# //TODO -- still open after the 2026-07 review pass
- foreslope_height should eventually come from a terrain model
  (civilpy.transportation.terrain now exists) instead of a user input.
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.box_culvert_headwall import WingwallInput
from civilpy.structural.rhino_bchw import bchw_emit
from civilpy.structural.rhino_bim import pay_item_quantities
from civilpy.structural.rhino_layers import DEFAULT_COLORS

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _prism_brep(obj, s):
    """Closed planar loop extruded along the emit vector: loft + cap
    (the same construction as draw_bim_emit)."""
    loop = [_pt(p, s) for p in obj.points]
    a = rg.Polyline(loop + [loop[0]]).ToNurbsCurve()
    b = a.DuplicateCurve()
    b.Translate(rg.Vector3d(*[c * s for c in obj.vector]))
    lofted = rg.Brep.CreateFromLoft([a, b], rg.Point3d.Unset,
                                    rg.Point3d.Unset, rg.LoftType.Straight,
                                    False)
    if not lofted:
        return None
    return lofted[0].CapPlanarHoles(TOL) or lofted[0]


def _polyline_crv(obj, s):
    return rg.Polyline([_pt(p, s) for p in obj.points]).ToNurbsCurve()


def _ensure_layer(doc, path, rgb):
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath(path, -1)
    if idx >= 0:
        return idx
    parent, accum = None, ""
    for name in path.split("::"):
        accum = name if not accum else accum + "::" + name
        idx = doc.Layers.FindByFullPath(accum, -1)
        if idx < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = name
            if parent is not None:
                lyr.ParentLayerId = doc.Layers[parent].Id
            lyr.Color = sd.Color.FromArgb(*rgb[:3])
            idx = doc.Layers.Add(lyr)
        parent = idx
    return idx


def _bake(emit, geometry):
    doc = Rhino.RhinoDoc.ActiveDoc
    n = 0
    for obj, geom in zip(emit.objects, geometry):
        if geom is None:
            continue
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex = _ensure_layer(
            doc, obj.layer, DEFAULT_COLORS.get(obj.layer, (128, 128, 128)))
        for k, v in obj.tags.items():
            a.SetUserString(k, str(v))
        if isinstance(geom, rg.Brep):
            doc.Objects.AddBrep(geom, a)
        elif isinstance(geom, rg.Curve):
            doc.Objects.AddCurve(geom, a)
        else:
            doc.Objects.AddPoint(geom, a)
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

solids, rebar_crvs = [], []

_required = ("length", "wall_height", "foreslope_height", "cutoff_height",
             "footing_width", "box_wall_thickness", "foreslope_run")
if not all(globals().get(k) for k in _required):
    report = "Connect all of: length, wall_height, foreslope_height, " \
             "cutoff_height, footing_width, box_wall_thickness, " \
             "foreslope_run (ft/in). Optional: skew (deg), " \
             "footing_thickness (ft, 1.5), rebar (bool), bake. BCHW has " \
             "no dimension table -- every value is project-specific " \
             "(from the box culvert design)."
else:
    s = _scale()
    inp = WingwallInput(
        length_ft=float(length),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        wall_height_ft=float(wall_height),
        foreslope_height_ft=float(foreslope_height),
        cutoff_wall_height_ft=float(cutoff_height),
        footing_width_ft=float(footing_width),
        box_wall_thickness_in=float(box_wall_thickness),
    )
    try:
        emit = bchw_emit(
            inp, foreslope_run_ft=float(foreslope_run),
            footing_thickness_ft=(float(footing_thickness)
                                  if globals().get("footing_thickness")
                                  else 1.5),
            rebar=(bool(rebar) if globals().get("rebar") is not None
                   else True))
    except ValueError as exc:
        emit = None
        report = "INPUT ERROR: {}".format(exc)

    if emit:
        geometry = []
        for obj in emit.objects:
            if obj.kind == "prism":
                g = _prism_brep(obj, s)
                solids.append(g)
            elif obj.kind == "polyline":
                g = _polyline_crv(obj, s)
                rebar_crvs.append(g)
            else:
                g = _pt(obj.points[0], s)
            geometry.append(g)

        lines = ["ODOT BCHW box culvert wingwall (rev. 01-21-2022)",
                 "{} solids, {} bars".format(
                     len([g for g in solids if g]), len(rebar_crvs))]
        for item, rec in pay_item_quantities(emit).items():
            lines.append("  {}  {:,.1f} {}  {}".format(
                item, rec["qty"], rec["unit"], rec["desc"]))
        if globals().get("bake"):
            n = _bake(emit, geometry)
            lines.append("BAKED {} tagged objects to Culvert::* layers.".format(n))
        report = "\n".join(lines)
