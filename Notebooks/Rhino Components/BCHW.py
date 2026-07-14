"""ODOT BCHW Concrete Headwalls for Precast Box Culverts — GHPython
(Rhino 8, CPython 3) source.

Drop-in Grasshopper component for the BCHW Design Data sheets (1/6-6/6):
the **complete culvert-end assembly**, resolved from the sheet tables by
``civilpy.structural.odot.box_culvert_headwall.design_headwall`` and
emitted by ``civilpy.structural.rhino_bchw.bchw_emit`` — both wingwalls
placed per headwall type, the foreslope wall on top of the box (barrel
opening clear), footings + cutoff walls, a display-only precast box
stub, and the X/Y/V/W/Z reinforcing series. Quantities are the sheet's
tabulated values. All engineering content comes from those modules; this
script only draws.

Headwall types (sheet 1/6): "A" when the culvert is normal to the
roadway (both wingwalls at 45 deg), "B" for roadway skews of 0/15/30/45
deg (one 45 deg wingwall + one straight), "C" where site constraints
keep both wingwalls parallel to the roadway.

Frame: culvert axis = +x, headwall face through the origin, z = 0 at the
top of footing, y = 0 on the culvert centerline.

Component inputs (Type Hint / Access in parentheses):
    headwall_type (str, Item)   "A" | "B" | "C"
    box_span      (float, Item) ft, 8-20 in 2 ft increments
    box_rise      (float, Item) ft, 4-10 in 1 ft increments
    slab_thickness (float, Item) box top/bottom slab, in (optional, 10)
    skew          (float, Item) roadway skew theta, deg — Type B is
                                tabulated for 0/15/30/45 (optional, 0)
    foreslope_height (float, Item) 6 or 18 in (optional, 6)
    box_stub      (float, Item) display-only box length behind the
                                headwall, ft (optional, 4; 0 skips)
    rebar         (bool, Item)  draw the bar centerlines (optional, True)
    bake          (bool, Item)  write tagged geometry to Culvert layers
Outputs:
    solids     (Brep, List)   wingwalls / foreslope / cutoffs / footings / box
    rebar_crvs (Curve, List)  reinforcing bar centerlines
    report     (str)          resolved design + sheet quantity rollup

Baked objects carry their full ``bim.*`` / ``pay.*`` / ``mat.*`` user
text on the ``Culvert::*`` layers, so ``read_bim_quantities`` regenerates
the sheet's estimated quantities from the saved document.
"""

import sys

import Rhino
import Rhino.Geometry as rg

# DEV RELOAD: drop cached civilpy modules so every recompute re-imports
# from the editable install -- a 'git pull' takes effect on the next
# solve with no Rhino restart. Remove (or guard) once running a pinned
# release instead of the development checkout.
for _name in [n for n in list(sys.modules) if n.startswith("civilpy")]:
    del sys.modules[_name]

from civilpy.structural.odot.box_culvert_headwall import HeadwallInput
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

if not (globals().get("headwall_type") and globals().get("box_span")
        and globals().get("box_rise")):
    report = "Connect headwall_type ('A'|'B'|'C'), box_span (ft, 8-20), " \
             "box_rise (ft, 4-10). Optional: slab_thickness (in, 10), " \
             "skew (deg; Type B: 0/15/30/45), foreslope_height (in, 6 or " \
             "18), box_stub (ft, 4), rebar (bool), bake. Dimensions, " \
             "reinforcing, and quantities come from the Design Data " \
             "sheet tables."
else:
    s = _scale()
    try:
        inp = HeadwallInput(
            headwall_type=str(headwall_type).strip().upper(),
            box_span_ft=float(box_span),
            box_rise_ft=float(box_rise),
            box_slab_thickness_in=(float(slab_thickness)
                                   if globals().get("slab_thickness")
                                   else 10.0),
            roadway_skew_deg=(float(skew) if globals().get("skew")
                              else 0.0),
            foreslope_wall_height_in=(float(foreslope_height)
                                      if globals().get("foreslope_height")
                                      else 6.0),
        )
        emit = bchw_emit(
            inp,
            box_stub_ft=(float(box_stub)
                         if globals().get("box_stub") is not None else 4.0),
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

        d = emit.design
        row = d.row
        lines = [
            "ODOT BCHW Type {} headwall".format(inp.headwall_type),
            "H required {:.2f} ft -> design height {:g} ft "
            "(footing design {})".format(d.H_required, d.H,
                                         row.footing_design),
            "wingwalls: L1 {:g} / L2 {:g} ft, roots h1 {:g} / h2 {:g} ft, "
            "t {:g} in".format(row.L1, row.L2, row.h1, row.h2, d.t_wall_in),
            "X #{} @ {:g} in, Y #{} @ {:g} in (ext. {:g} ft)".format(
                row.x_bar, row.x_spa_in, row.y_bar, row.y_spa_in, row.c),
            "{} solids, {} bars".format(
                len([g for g in solids if g]), len(rebar_crvs)),
        ]
        for item, rec in pay_item_quantities(emit).items():
            lines.append("  {}  {:,.1f} {}  {}".format(
                item, rec["qty"], rec["unit"], rec["desc"]))
        if globals().get("bake"):
            n = _bake(emit, geometry)
            lines.append(
                "BAKED {} tagged objects to Culvert::* layers.".format(n))
        report = "\n".join(lines)
