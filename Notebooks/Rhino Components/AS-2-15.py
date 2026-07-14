# r: civilpy
"""ODOT AS-2-15 Approach Slab Installation (sleeper slab) — GHPython
(Rhino 8, CPython 3) source.

Drop-in Grasshopper component for the drawable subset of SCD AS-2-15
(rev. 01-20-2023): the reinforced concrete sleeper slab under the
approach-slab / pavement joint (Type A and Type C installations; Type B
has no sleeper slab).  All engineering content comes from
``civilpy.structural.odot.sleeper_slab``; this script only draws.

The sleeper is generated with its centerline (the joint) on the YZ plane
at X = 0, the y = 0 edge at the origin, and Z = 0 at the TOP of the
sleeper slab.  When pairing with the AS-1-15 component, move it so the
centerline sits at the approach end of the approach slab, one approach
slab thickness (T) below its top surface.

Component inputs (Type Hint / Access in parentheses):
    width         (float, Item)  approach slab width W, ft
    skew          (float, Item)  degrees (optional, 0)
    installation  (str, Item)    "A" or "C" (optional, "A")
    bake          (bool, Item)   write display geometry to Site::AS-2-15
Outputs:
    sleeper  (Brep, Item)    the sleeper slab solid
    rebar    (Curve, List)   SS501 + SS502 bars
    joint    (Brep, Item)    polymer modified asphalt joint block (Type A)
    drain    (Brep, Item)    aggregate drain prism below the slab
    pipe     (Curve, Item)   6 in underdrain centerline
    report   (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

"""
# //TODO - Missing civilpy import (same as the others # r: civilpy)
- Skew is Okay, but rebar extends well beyond the actual sleeper slab, shape doesn't represent the actual
    sleeper slab, it's two rectangles one inside the larger one instead of being an L shape as expected
    front/right orientation flipped like with other SCDs tested so far.
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot import sleeper_slab as ss
from civilpy.structural.odot.sleeper_slab import (
    SleeperSlabInput,
    layout_sleeper_slab,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _prism(outline, depth_ft, s):
    poly = rg.Polyline([_pt(p, s) for p in outline]
                       + [_pt(outline[0], s)]).ToNurbsCurve()
    ext = rg.Extrusion.Create(poly, -depth_ft * s, True)
    return ext.ToBrep() if ext else None


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Site::AS-2-15", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Site", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Site"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "AS-2-15"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(140, 140, 160)
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

sleeper, joint, drain, pipe = None, None, None, None
rebar = []

if not globals().get("width"):
    report = "Connect at least: width (ft). Optional: skew (deg), " \
             "installation ('A'/'C'), bake."
else:
    s = _scale()
    inp = SleeperSlabInput(
        width_ft=float(width),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        installation=str(installation)
        if globals().get("installation") else "A",
    )
    try:
        layout = layout_sleeper_slab(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        sleeper = _prism(layout.outline, layout.thickness_in / 12.0, s)
        for bar in layout.bars:
            rebar.append(rg.LineCurve(_pt(bar.points[0], s),
                                      _pt(bar.points[-1], s)))
        # PMA joint block sits ON the sleeper top
        jw = ss.PMA_JOINT_THICKNESS_IN / 12.0
        j = _prism(layout.pma_joint, -jw, s)   # extrude upward
        joint = j
        drain = _prism(layout.aggregate_drain,
                       ss.AGGREGATE_DRAIN_DEPTH_FT, s)
        pipe = rg.LineCurve(_pt(layout.underdrain[0], s),
                            _pt(layout.underdrain[1], s))

        counts = {}
        for bar in layout.bars:
            counts[bar.mark] = counts.get(bar.mark, 0) + 1
        report_lines = [
            "ODOT AS-2-15 approach slab installation (rev. 01-20-2023)",
        ] + list(layout.notes[:2]) + [
            "Bars: " + ", ".join("{} x {}".format(v, k)
                                 for k, v in sorted(counts.items())),
            "Sleeper slab measured length: {:.2f} ft (LF along the skew)"
            .format(layout.measured_length_ft),
            layout.notes[2],
        ]
        if globals().get("bake"):
            n = _bake([sleeper, joint, drain, pipe] + rebar)
            report_lines.append(
                "BAKED {} objects to Site::AS-2-15 (display only).".format(n))
        report = "\n".join(report_lines)
