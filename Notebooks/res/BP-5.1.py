"""ODOT BP-5.1 Concrete Curbs and Combined Curb & Gutter — GHPython
(Rhino 8, CPython 3) source.

Drop-in Grasshopper component for BP-5.1 (rev. 01-16-2026): a straight
run of one cataloged curb cross section. All engineering content comes
from ``civilpy.structural.odot.concrete_curb``; this script only draws
a schematic extrusion (see that module's docstring for what is/isn't
modeled -- fillets/arcs are approximated as straight chamfers).

Component inputs (Type Hint / Access in parentheses):
    curb_type   (str,   Item)  e.g. "Type 1", "Type 2", "Type 9"
                                (see civilpy.structural.odot.concrete_curb
                                .CURB_TYPES for every accepted label)
    length      (float, Item)  run length, ft
    gutter_t    (float, Item)  gutter-plate thickness T, in (optional;
                                only used by the variable-height types
                                9/10/11, default 9 in)
    bake        (bool,  Item)  write display geometry to Site::BP-5.1
Outputs:
    section  (Curve, Item)  the cross-section polyline (closed)
    solid    (Brep,  Item)  extruded curb body
    report   (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.concrete_curb import curb_profile_in
from civilpy.structural.odot.concrete_curb import curb_type as _curb_type

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Inches, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Site::BP-5.1", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Site", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Site"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "BP-5.1"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(170, 170, 170)
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

if not globals().get("curb_type") or not globals().get("length"):
    report = "Connect: curb_type ('Type 1'..'Type 11', see " \
             "concrete_curb.CURB_TYPES), length (ft). Optional: gutter_t " \
             "(in, only for Types 9/10/11), bake."
else:
    s = _scale()
    gutter_t = float(gutter_t) if globals().get("gutter_t") else None
    try:
        c = _curb_type(str(curb_type))
        prof_in = curb_profile_in(str(curb_type), gutter_plate_t_in=gutter_t)
    except ValueError as exc:
        c, prof_in = None, None
        report = "INPUT ERROR: {}".format(exc)

    if prof_in:
        pts = [rg.Point3d(0.0, off * s, z * s) for (off, z) in prof_in]
        pts.append(pts[0])
        section = rg.PolylineCurve(pts)

        length_units = float(length) * 12.0 * s
        extrusion = rg.Extrusion.CreateExtrusion(section, rg.Vector3d(length_units, 0, 0))
        solid = extrusion.ToBrep() if extrusion else None

        report_lines = [
            "ODOT BP-5.1 {} ({})".format(c.name, ", ".join(c.sheet_labels)),
            c.notes,
        ]
        if globals().get("bake"):
            n = _bake([section, solid])
            report_lines.append(
                "BAKED {} objects to Site::BP-5.1 (display only).".format(n))
        report = "\n".join(report_lines)
