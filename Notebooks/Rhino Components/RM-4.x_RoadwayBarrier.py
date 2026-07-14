# r: civilpy
"""ODOT RM-4.3 / RM-4.5 / RM-4.8 / RM-4.9 Roadway Single Slope Barrier —
GHPython (Rhino 8, CPython 3) source.

Drop-in Grasshopper component for the at-grade (roadway) single-slope
barrier family: Types B/B1 (RM-4.3, rev. 2025-07-18), Type D (RM-4.5, rev.
2026-01-16), Type N (RM-4.8, rev. 2026-01-16). Type E (RM-4.9) is cataloged
but its concrete face is not dimensioned on the drawing, so it is refused
here (see ``civilpy.structural.odot.roadway_barrier`` docstring); Types
C/C1 draw as their fixed-height B/B1 base body only (the project-variable
upper extension is not modeled).

All engineering content comes from
``civilpy.structural.odot.roadway_barrier``; this script only draws a
straight extrusion of the symmetric cross-section along the X axis,
centered on the world Y=0 line. Rotate/move the baked geometry (or the
component's placement plane) onto the actual alignment.

Component inputs (Type Hint / Access in parentheses):
    designation (str,   Item)  "Type B", "Type B1", "Type C", "Type C1",
                                "Type D", or "Type N"
    length      (float, Item)  barrier run length, ft
    bake        (bool,  Item)  write display geometry to Site::RM-4.x
Outputs:
    section  (Curve, Item)  the symmetric cross-section polyline (closed)
    solid    (Brep,  Item)  extruded barrier body
    report   (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

"""
# //TODO - add # r: civilpy
- Ignoring these SCDs for now, focus on PCB
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.roadway_barrier import (
    RoadwayBarrierInput,
    layout_roadway_barrier,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Inches, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Site::RM-4.x Barrier", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Site", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Site"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "RM-4.x Barrier"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(160, 160, 160)
        idx = doc.Layers.Add(lyr)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = idx
    n = 0
    for o in objs:
        if o is None:
            continue
        if isinstance(o, rg.Brep):
            doc.Objects.AddBrep(o, a)
        elif isinstance(o, rg.Curve):
            doc.Objects.AddCurve(o, a)
        else:
            continue
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

section, solid = None, None

if not globals().get("designation") or not globals().get("length"):
    report = "Connect: designation ('Type B'/'Type B1'/'Type C'/'Type C1'/" \
             "'Type D'/'Type N'), length (ft). Optional: bake."
else:
    s = _scale()
    try:
        layout = layout_roadway_barrier(
            RoadwayBarrierInput(designation=str(designation), length_ft=float(length)))
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        pts = [rg.Point3d(0.0, off * s, z * s) for (off, z) in layout.profile]
        pts.append(pts[0])
        section = rg.PolylineCurve(pts)

        length_units = layout.length_ft * 12.0 * s
        path = rg.LineCurve(rg.Point3d(0, 0, 0), rg.Point3d(length_units, 0, 0))
        extrusion = rg.Extrusion.CreateExtrusion(section, rg.Vector3d(length_units, 0, 0))
        solid = extrusion.ToBrep() if extrusion else None

        report_lines = list(layout.notes)
        if globals().get("bake"):
            n = _bake([section, solid])
            report_lines.append(
                "BAKED {} objects to Site::RM-4.x Barrier (display only).".format(n))
        report = "\n".join(report_lines)
