"""ODOT BD-1-11 Bearing Details for Box Beam Bridges — GHPython (Rhino 8,
CPython 3) source.

Drop-in Grasshopper component for SCD BD-1-11 (rev. 07-20-2018): the
beveled steel load plate used under a box-beam elastomeric bearing to
take out roadway-grade rotation, sized to the standard B1/B2 bearing pad
(``civilpy.structural.odot.box_beam``). All engineering content comes
from that module; this script only draws.

Use this drawing only when the elastomeric bearing alone cannot
accommodate the roadway-grade rotation (sheet's own General note).
Anchor rods/recesses, plate washers, the preformed bearing pad, bearing
markings, and the box-beam anchor-hole spacing (which varies by 36 in
vs. 48 in box width, not tabulated on this sheet) are not drawn.

The plate is generated with its bottom face centered at the origin,
z = 0; x = bearing length (along the beam), y = bearing width.

Component inputs (Type Hint / Access in parentheses):
    bearing_pad  (str,   Item)  "B1" or "B2"
    grade        (float, Item)  longitudinal roadway grade, rise/run
                                (optional, 0; e.g. 0.04 for 4%)
    skew         (float, Item)  degrees (optional, 0)
    bake         (bool,  Item)  write display geometry to
                                Superstructure::BD-1-11
Outputs:
    plate   (Brep, Item)  the beveled load plate solid
    report  (str)

Baked geometry is display-only and carries no gdr.* tags. Uses the
Superstructure:: layer group (bearings are a superstructure element).
"""

"""
# //TODO - Civilpy Import, verify orientation similar to other objects.
- Generates no preview geometry whatsover.
- Should probably have the threaded anchor rod included in the output
- skew has no effect
- Needs to generate 2 plates along a beam centerline, the beam will be dependent on the roadway centerline
- Layer it generates to should probably be called "Load Plate" within the "Superstructure Category" (not BD-1-11)
- Doesn't have any of the necessary user-text attributes that are expected (goes for basically all items generated from
    this stuff. The goal is to have a fully enabled 
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.box_beam import layout_load_plate

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Inches, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _loft_solid(bottom, top, s):
    bpts = [_pt(p, s) for p in bottom] + [_pt(bottom[0], s)]
    tpts = [_pt(p, s) for p in top] + [_pt(top[0], s)]
    loft = rg.Brep.CreateFromLoft(
        [rg.Polyline(bpts).ToNurbsCurve(), rg.Polyline(tpts).ToNurbsCurve()],
        rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Straight, False)
    if not loft:
        return None
    brep = loft[0]
    return brep.CapPlanarHoles(TOL) or brep


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Superstructure::BD-1-11", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Superstructure", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Superstructure"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "BD-1-11"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(0, 110, 200)
        idx = doc.Layers.Add(lyr)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = idx
    n = 0
    for o in objs:
        if o is None:
            continue
        doc.Objects.AddBrep(o, a)
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

plate = None

if not globals().get("bearing_pad"):
    report = "Connect: bearing_pad (str: 'B1' or 'B2'). Optional: " \
             "grade (rise/run, default 0), skew (deg, default 0), bake."
else:
    s = _scale()
    try:
        layout = layout_load_plate(
            str(bearing_pad),
            longitudinal_grade=float(grade) if globals().get("grade") else 0.0,
            skew_deg=float(skew) if globals().get("skew") else 0.0,
        )
    except (KeyError, ValueError) as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        plate = _loft_solid(layout.bottom_face, layout.top_face, s)

        report_lines = [
            "ODOT BD-1-11 beveled load plate (rev. 07-20-2018)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([plate])
            report_lines.append(
                "BAKED {} objects to Superstructure::BD-1-11 (display "
                "only).".format(n))
        report = "\n".join(report_lines)
