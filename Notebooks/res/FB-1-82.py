"""ODOT FB-1-82 Fixed Bearings — GHPython (Rhino 8, CPython 3) source.

Drop-in Grasshopper component for SCD FB-1-82 (rev. 07-19-2024): a
pin-bearing fixed-bearing assembly (masonry plate + bearing pin + top
plate) for a given rated load. All engineering content comes from
``civilpy.structural.odot.fixed_bearing``; this script only draws.

Anchor rods, welds, and bearing seat reinforcing are cataloged, not
drawn -- see the module docstring.

Component inputs (Type Hint / Access in parentheses):
    designation  (str,  Item)  "F-50", "F-100", ..., "F-400"
    bake         (bool, Item)  write display geometry to
                              Superstructure::FB-1-82
Outputs:
    base  (Brep, Item)  masonry plate solid
    pin   (Brep, Item)  bearing pin cylinder
    top   (Brep, Item)  top plate solid
    report (str)

Baked geometry is display-only and carries no gdr.* tags. Uses the
Superstructure:: layer group (bearings are a superstructure element).
"""

"""
# //TODO - Missing # r: civilpy
- Preview only shows connecting pin and top plate, doesn't show bottom plate, top pin retainer or any anchor rods
- Needs to take into account abutment seat and skew, girders should probably an input, 
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.fixed_bearing import (
    fixed_bearing,
    layout_fixed_bearing,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Inches, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _prism(outline, z0, z1, s):
    poly = rg.Polyline([rg.Point3d(p[0] * s, p[1] * s, z0 * s) for p in outline]
                       + [rg.Point3d(outline[0][0] * s, outline[0][1] * s,
                                     z0 * s)]).ToNurbsCurve()
    ext = rg.Extrusion.Create(poly, (z1 - z0) * s, True)
    return ext.ToBrep() if ext else None


def _cylinder(center, diameter_in, length_in, s):
    plane = rg.Plane(_pt(center, s), rg.Vector3d.YAxis)
    circle = rg.Circle(plane, diameter_in / 2.0 * s)
    cyl = rg.Cylinder(circle, length_in * s)
    return cyl.ToBrep(True, True)


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Superstructure::FB-1-82", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Superstructure", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Superstructure"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "FB-1-82"
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

base, pin, top = None, None, None

if not globals().get("designation"):
    report = "Connect: designation (str: 'F-50', 'F-100', ..., 'F-400'). " \
             "Optional: bake."
else:
    s = _scale()
    try:
        fb = fixed_bearing(str(designation))
        layout = layout_fixed_bearing(fb)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        base = _prism(layout.base_outline, 0.0, layout.base_thickness_in, s)
        top = _prism(layout.top_outline, layout.top_z_in,
                    layout.top_z_in + 0.5, s)
        pin_len = max(o[1] for o in layout.top_outline) - \
            min(o[1] for o in layout.top_outline)
        pin = _cylinder(
            (layout.pin_center[0], -pin_len / 2.0, layout.pin_center[2]),
            layout.pin_diameter_in, pin_len, s)

        report_lines = [
            "ODOT FB-1-82 fixed bearing (rev. 07-19-2024)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([base, pin, top])
            report_lines.append(
                "BAKED {} objects to Superstructure::FB-1-82 (display "
                "only).".format(n))
        report = "\n".join(report_lines)
