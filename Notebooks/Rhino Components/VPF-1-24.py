"""ODOT VPF-1-24 Vandal Protection Fence — GHPython (Rhino 8, CPython 3)
source.

Drop-in Grasshopper component for VPF-1-24 (rev. 01-17-2025): post
markers plus top/bottom rail lines for a fence run. All engineering
content comes from ``civilpy.structural.odot.vandal_fence``; this script
only draws. Fabric mesh, tension wire, and base plate/anchor hardware
are not drawn.

Component inputs (Type Hint / Access in parentheses):
    length     (float, Item)  fence run length, ft
    post       (str,   Item)  "PS-1", "PS-2/BP-1", or "PS-2/BP-2"
                              (optional, "PS-2/BP-1")
    spacing    (float, Item)  ft (optional, the section's own max)
    bake       (bool,  Item)  write display geometry to Site::VPF-1-24
Outputs:
    posts       (Point, List)  post base positions
    top_rail    (Curve, Item)  rail at post height
    bottom_rail (Curve, Item)  rail at the base
    report      (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

"""
# //TODO - add # r: civilpy
- Currently just shows 2 lines and post base points. Fine for now, minor detail for Midas Workflow
- Probably needs to be based on a parapet/bridge railing in the majority of cases
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.vandal_fence import FenceRunInput, layout_fence_run

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Site::VPF-1-24", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Site", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Site"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "VPF-1-24"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(150, 140, 120)
        idx = doc.Layers.Add(lyr)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = idx
    n = 0
    for o in objs:
        if o is None:
            continue
        if isinstance(o, rg.Curve):
            doc.Objects.AddCurve(o, a)
        elif isinstance(o, rg.Point3d):
            doc.Objects.AddPoint(o, a)
        else:
            continue
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

posts, top_rail, bottom_rail = [], None, None

if not globals().get("length"):
    report = "Connect: length (ft). Optional: post ('PS-1'/'PS-2/BP-1'/" \
             "'PS-2/BP-2', default 'PS-2/BP-1'), spacing (ft), bake."
else:
    s = _scale()
    inp = FenceRunInput(
        length_ft=float(length),
        post_name=str(post) if globals().get("post") else "PS-2/BP-1",
        spacing_ft=float(spacing) if globals().get("spacing") else None,
    )
    try:
        layout = layout_fence_run(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        posts = [_pt((x, 0.0, 0.0), s) for x in layout.post_stations_ft]
        top_rail = rg.LineCurve(_pt(layout.top_rail[0], s), _pt(layout.top_rail[1], s))
        bottom_rail = rg.LineCurve(_pt(layout.bottom_rail[0], s), _pt(layout.bottom_rail[1], s))

        report_lines = [
            "ODOT VPF-1-24 vandal protection fence (rev. 01-17-2025)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake(posts + [top_rail, bottom_rail])
            report_lines.append(
                "BAKED {} objects to Site::VPF-1-24 (display only).".format(n))
        report = "\n".join(report_lines)
