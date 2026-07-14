# r: civilpy
"""ODOT HW-2.1 Half-Height Headwall (circular pipe) — GHPython
(Rhino 8, CPython 3) source.

Drop-in Grasshopper component for the drawable subset of SCD HW-2.1
(rev. 07-15-2022): the rectangular cast-in-place headwall of the circular
corrugated-metal / plastic pipe table (end treatment "A").  All
engineering content comes from ``civilpy.structural.odot.headwall``; this
script only draws.

The headwall is generated with its front face on the XZ plane (y = 0,
wall behind at -y), the centreline at x = 0, and z = 0 at the flow line /
wall base.  The battered wall (front vertical, back 12 in at the top to T
at the base) is swept the full width W and the circular pipe opening is
cut through it along Y.  For the concrete-pipe table (HW-2.2) set
``concrete`` True.

Component inputs (Type Hint / Access in parentheses):
    diameter  (float, Item)  pipe inside diameter D, inches (tabulated)
    concrete  (bool,  Item)  use the HW-2.2 concrete-pipe table (optional)
    bake      (bool,  Item)  write display geometry to Culvert::HW-2.1
Outputs:
    wall    (Brep, Item)   the headwall solid with the pipe opening cut
    opening (Curve, Item)  the circular pipe opening on the front face
    report  (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

"""
# //TODO - missing civilpy import
- 1. Error running script: No overload for method 'Surface.ToBrep{}' takes '1' arguments(<class 'bool'>) [54:1]
- Probably all the same issues as HW-1.1.py too, check it's TODOs
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot import headwall as hwmod
from civilpy.structural.odot.headwall import HeadwallInput, layout_headwall

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _wall_solid(side_profile, width_ft, s):
    """Sweep the battered YZ side profile (at x = -W/2) the full width W
    in +X into a closed solid."""
    poly = rg.Polyline([_pt(p, s) for p in side_profile]
                       + [_pt(side_profile[0], s)]).ToNurbsCurve()
    path = rg.Vector3d(width_ft * s, 0.0, 0.0)
    ext = rg.Extrusion.CreateExtrusion(poly, path)
    return ext.ToBrep(True) if ext else None


def _pipe_cutter(center, dia_ft, thickness_ft, s):
    """A cylinder along Y spanning the wall thickness, oversized so the
    boolean cleanly cuts the front and back faces."""
    c = _pt(center, s)
    over = thickness_ft * s
    base = rg.Point3d(c.X, c.Y - thickness_ft * s, c.Z)
    axis = rg.Line(base, rg.Point3d(c.X, c.Y + thickness_ft * s, c.Z))
    circle = rg.Circle(rg.Plane(base, rg.Vector3d.YAxis), dia_ft * s / 2.0)
    cyl = rg.Cylinder(circle, axis.Length)
    return cyl.ToBrep(True, True)


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Culvert::HW-2.1", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Culvert", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Culvert"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "HW-2.1"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(150, 150, 130)
        idx = doc.Layers.Add(lyr)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = idx
    n = 0
    for o in objs:
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

wall, opening = None, None

if not globals().get("diameter"):
    report = "Connect: diameter (in, a tabulated pipe size). Optional: " \
             "concrete (bool, HW-2.2 table), bake."
else:
    s = _scale()
    inp = HeadwallInput(
        diameter_in=float(diameter),
        concrete=bool(concrete) if globals().get("concrete") else False,
    )
    try:
        layout = layout_headwall(inp)
    except (ValueError, KeyError) as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        solid = _wall_solid(layout.side_profile, layout.width_ft, s)
        cutter = _pipe_cutter(layout.pipe_center, layout.pipe_diameter_ft,
                              layout.base_thickness_ft, s)
        wall = solid
        if solid and cutter:
            diff = rg.Brep.CreateBooleanDifference(solid, cutter, TOL)
            if diff and len(diff) > 0:
                wall = diff[0]
        # the pipe opening traced on the front face (y = 0)
        c = _pt(layout.pipe_center, s)
        opening = rg.Circle(
            rg.Plane(rg.Point3d(c.X, 0.0, c.Z), rg.Vector3d.YAxis),
            layout.pipe_diameter_ft * s / 2.0).ToNurbsCurve()

        report_lines = [
            "ODOT HW-2.1 half-height headwall (rev. 07-15-2022)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([wall, opening])
            report_lines.append(
                "BAKED {} objects to Culvert::HW-2.1 (display only).".format(n))
        report = "\n".join(report_lines)
