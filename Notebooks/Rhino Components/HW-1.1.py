# r: civilpy
"""ODOT HW-1.1 Full-Height Headwall — GHPython (Rhino 8, CPython 3) source.

Drop-in Grasshopper component for the drawable subset of SCD HW-1.1
(rev. 07-18-2025): the full-height headwall + wingwall unit for a circular
culvert pipe, 42-84 in, skewed or non-skewed.  All engineering content
comes from ``civilpy.structural.odot.full_height_headwall``; this script
only draws.

The unit is generated as three flat panels -- a vertical center face at the
culvert centerline (width = pipe diameter, height = the tabulated H) and
two wingwall planes swept from its top corners down to the tabulated
height at each wingwall's far end (Type A: symmetric 45 deg flare; Type B,
skew > 10 deg: asymmetric flare split by the skew).  Origin: x = 0 on the
culvert centerline, y = 0 at the headwall front face (wall behind, +y
downstream), z = 0 at the flow line / wall base.  Wall thickness/batter,
the footing, reinforcing, and weepholes are not drawn (see the report).

Component inputs (Type Hint / Access in parentheses):
    diameter  (float, Item)  pipe inside diameter D, inches (tabulated)
    skew      (float, Item)  degrees (optional, 0; snapped to the nearest
                              tabulated bucket -- see the report)
    bake      (bool,  Item)  write display geometry to Culvert::HW-1.1
Outputs:
    center   (Brep, Item)   the vertical center-face panel
    wing1    (Brep, Item)   the acute-side wingwall panel
    wing2    (Brep, Item)   the obtuse-side wingwall panel
    opening  (Curve, Item)  the pipe opening traced on the center face
    report   (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

"""
# //TODO - Missing # r: civilpy
- One of the few who's orientation does not need corrected (front and right are the correct viewpoints.
- Needs a "Near"/"Far" designation and an alignment to determine which way the wing walls point
- Walls are currently 2D instead of 3D
- Needs to take terrain and groundlines into account
- Doesn't currently account for drainage weep holes or slab underneath headwalls
- Once baked the "diameter becomes 2D, still missing thickness and rebar though
- No control over wingwall
- Skew only seems to change the wingwalls, not the opening itself
- 
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot import full_height_headwall as fhh
from civilpy.structural.odot.full_height_headwall import (
    HeadwallInput,
    layout_full_height_headwall,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _quad_panel(quad, s):
    pts = [_pt(p, s) for p in quad]
    return rg.Brep.CreateFromCornerPoints(pts[0], pts[1], pts[2], pts[3], TOL)


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Culvert::HW-1.1", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Culvert", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Culvert"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "HW-1.1"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(130, 150, 150)
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

center, wing1, wing2, opening = None, None, None, None

if not globals().get("diameter"):
    report = "Connect: diameter (in, a tabulated pipe size). Optional: " \
             "skew (deg), bake."
else:
    s = _scale()
    inp = HeadwallInput(
        diameter_in=float(diameter),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
    )
    try:
        layout = layout_full_height_headwall(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        center = _quad_panel(layout.center_face, s)
        wing1 = _quad_panel(layout.wing1, s)
        wing2 = _quad_panel(layout.wing2, s)

        D_ft = inp.diameter_in / 12.0
        H = layout.table.height_ft
        opening = rg.Circle(
            rg.Plane(_pt((0.0, 0.0, D_ft / 2.0), s), rg.Vector3d.YAxis),
            D_ft * s / 2.0).ToNurbsCurve()

        report_lines = [
            "ODOT HW-1.1 full-height headwall (rev. 07-18-2025)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([center, wing1, wing2, opening])
            report_lines.append(
                "BAKED {} objects to Culvert::HW-1.1 (display only).".format(n))
        report = "\n".join(report_lines)
