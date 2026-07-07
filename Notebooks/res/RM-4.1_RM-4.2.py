"""ODOT RM-4.1 / RM-4.2 Roadway Portable Concrete Barrier — GHPython
(Rhino 8, CPython 3) source.

Drop-in Grasshopper component for the at-grade portable concrete barrier
family: 32 in pin & loop (RM-4.2, rev. 2026-01-16) and 50 in hinge bar
(RM-4.1, rev. 2020-01-17). All engineering content comes from
``civilpy.structural.odot.roadway_portable_barrier``; this script draws
the freestanding symmetric New Jersey shape (the same "portable" family
as PCB-91's F-shape) extruded along the X axis, centered on world Y=0.

Component inputs (Type Hint / Access in parentheses):
    designation (str,   Item)  "RM Portable (32 in, pin & loop)" or
                                "RM Portable (50 in, hinge bar)"
    length      (float, Item)  barrier run length, ft
    bake        (bool,  Item)  write display geometry to Site::RM-4.1_RM-4.2
Outputs:
    section  (Curve, Item)  the symmetric cross-section polyline (closed)
    solid    (Brep,  Item)  extruded barrier body
    report   (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.roadway_portable_barrier import (
    roadway_portable_barrier,
)
from civilpy.structural.rhino_barrier import barrier_profile

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Site::RM-4.1_RM-4.2 Barrier", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Site", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Site"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "RM-4.1_RM-4.2 Barrier"
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
    report = "Connect: designation ('RM Portable (32 in, pin & loop)' or " \
             "'RM Portable (50 in, hinge bar)'), length (ft). Optional: bake."
else:
    s = _scale()
    try:
        b = roadway_portable_barrier(str(designation))
    except ValueError as exc:
        b = None
        report = "INPUT ERROR: {}".format(exc)

    if b is not None:
        height_ft = b.height / 12.0
        prof_ft = barrier_profile(b, height_ft, side=0)  # (offset_ft, z_ft)
        pts = [rg.Point3d(0.0, off * s, z * s) for (off, z) in prof_ft]
        pts.append(pts[0])
        section = rg.PolylineCurve(pts)

        length_units = float(length) * s
        extrusion = rg.Extrusion.CreateExtrusion(section, rg.Vector3d(length_units, 0, 0))
        solid = extrusion.ToBrep() if extrusion else None

        report_lines = [
            "ODOT {} {} (rev. {})".format(b.scd, b.name, b.scd_date),
            b.notes,
        ]
        if globals().get("bake"):
            n = _bake([section, solid])
            report_lines.append(
                "BAKED {} objects to Site::RM-4.1_RM-4.2 Barrier (display "
                "only).".format(n))
        report = "\n".join(report_lines)
