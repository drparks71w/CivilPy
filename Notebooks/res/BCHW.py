"""ODOT BCHW Box Culvert Headwall/Wingwall — GHPython (Rhino 8, CPython 3)
source.

Drop-in Grasshopper component for the BCHW plan insert (rev. 01-21-2022):
one cast-in-place wingwall + foreslope wall, from dimensions the engineer
supplies (this sheet has no dimension table -- every length is
project-specific; see ``civilpy.structural.odot.box_culvert_headwall``'s
module docstring). All engineering content comes from that module; this
script only draws.

The wingwall is generated with the box culvert wall face at y = 0 (the
wingwall flares out to y = length), x = 0 on the box culvert centerline,
z = 0 at the top of footing.

Component inputs (Type Hint / Access in parentheses):
    length       (float, Item)  wingwall length L, ft
    skew         (float, Item)  box culvert skew, degrees (optional, 0)
    wall_height  (float, Item)  foreslope wall height H, ft
    foreslope_height (float, Item)  hf, ft
    cutoff_height    (float, Item)  hcw, ft
    footing_width    (float, Item)  Wf, ft
    box_wall_thickness (float, Item)  t box, in
    bake         (bool, Item)   write display geometry to Culvert::BCHW
Outputs:
    wingwall  (Curve, Item)  wingwall flared outline
    foreslope (Curve, Item)  Section A-A foreslope-wall profile
    footing   (Curve, Item)  footing plan outline
    report    (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.box_culvert_headwall import (
    WingwallInput,
    layout_wingwall,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _polyline(pts, s, closed=False):
    poly = [_pt(p, s) for p in pts]
    if closed:
        poly.append(poly[0])
    return rg.Polyline(poly).ToNurbsCurve()


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Culvert::BCHW", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Culvert", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Culvert"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "BCHW"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(130, 150, 150)
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

wingwall, foreslope, footing = None, None, None

_required = ("length", "wall_height", "foreslope_height", "cutoff_height",
             "footing_width", "box_wall_thickness")
if not all(globals().get(k) for k in _required):
    report = "Connect all of: length, wall_height, foreslope_height, " \
             "cutoff_height, footing_width, box_wall_thickness (ft/in). " \
             "Optional: skew (deg), bake. BCHW has no dimension table -- " \
             "every value is project-specific (from the box culvert design)."
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
        layout = layout_wingwall(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        wingwall = _polyline(layout.wingwall_outline, s, closed=True)
        foreslope = _polyline(layout.foreslope_section, s)
        footing = _polyline(layout.footing_outline, s, closed=True)

        report_lines = [
            "ODOT BCHW box culvert wingwall (rev. 01-21-2022)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([wingwall, foreslope, footing])
            report_lines.append(
                "BAKED {} objects to Culvert::BCHW (display only).".format(n))
        report = "\n".join(report_lines)
