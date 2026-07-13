"""ODOT EXJ-4-87 Strip Seal Expansion Joint (Steel Stringer) — GHPython
(Rhino 8, CPython 3) source.

Drop-in Grasshopper component for EXJ-4-87 (rev. 01-19-2024): the skewed
joint centerline plus a support-angle length marker at each stringer,
sized by the sheet's own a1/a2/a3/a4 formulas. All engineering content
comes from ``civilpy.structural.odot.strip_seal_joint``; this script
only draws. The strip-seal gland itself is manufacturer-generic and not
drawn.

Component inputs (Type Hint / Access in parentheses):
    width             (float, Item)  deck width, ft
    skew              (float, Item)  degrees (optional, 0)
    stringer_stations (float, List)  transverse (Y) stringer positions, ft
    top_flange_width  (float, Item)  in (optional, 12)
    bake              (bool,  Item)  write display geometry to
                                    Superstructure::EXJ-4-87
Outputs:
    joint_line      (Curve, Item)  skewed joint centerline
    support_angles  (Curve, List)  one segment per stringer
    report          (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

"""
# //TODO - Missing r: civilpy
- Shows up as only a single line with a has mark over each stringer, no 3D shape
- Should take in as inputs other objects instead of a series, stringer object, station, alignment, etc.
- Missing a ton of details including shear studs, cover plates, retainers glands
- Missing 3 other standards EXJ-2-81, EXJ-3-82, EXJ-6-17
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.strip_seal_joint import (
    StripSealJointInput,
    layout_strip_seal_joint,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Superstructure::EXJ-4-87", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Superstructure", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Superstructure"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "EXJ-4-87"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(200, 30, 30)
        idx = doc.Layers.Add(lyr)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = idx
    n = 0
    for o in objs:
        if o is None:
            continue
        doc.Objects.AddCurve(o, a)
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

joint_line = None
support_angles = []

if not globals().get("width") or not globals().get("stringer_stations"):
    report = "Connect at least: width (ft), stringer_stations (ft, list). " \
             "Optional: skew (deg), top_flange_width (in, default 12), bake."
else:
    s = _scale()
    inp = StripSealJointInput(
        width_ft=float(width),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        stringer_stations_ft=tuple(float(v) for v in stringer_stations),
        top_flange_width_in=float(top_flange_width)
        if globals().get("top_flange_width") else 12.0,
    )
    try:
        layout = layout_strip_seal_joint(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        joint_line = rg.LineCurve(_pt(layout.joint_line[0], s),
                                  _pt(layout.joint_line[1], s))
        for run in layout.support_angles:
            support_angles.append(
                rg.LineCurve(_pt(run.points[0], s), _pt(run.points[1], s)))

        report_lines = [
            "ODOT EXJ-4-87 strip seal joint, steel stringers (rev. 01-19-2024)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([joint_line] + support_angles)
            report_lines.append(
                "BAKED {} objects to Superstructure::EXJ-4-87 (display "
                "only).".format(n))
        report = "\n".join(report_lines)
