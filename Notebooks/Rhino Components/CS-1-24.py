# r: civilpy
"""ODOT CS-1-24 Continuous Slab Bridge — GHPython (Rhino 8, CPython 3)
source.

Drop-in Grasshopper component for SCD CS-1-24 (rev. 01-16-2026): the slab
solid and A/B/C/D/E longitudinal reinforcing mats for a three-span
continuous slab bridge, end spans 14-46 ft (interior span always 1.25x
the end span). All engineering content comes from
``civilpy.structural.odot.continuous_slab_bridge``; this script only
draws. CPP-1-08 is the companion pier, CPA-1-08 the companion abutment.

The slab is generated with the first (upstream) bearing line at x = 0,
one edge at y = 0, z = 0 at the top of slab (slab extends down
``thickness``, uniform -- haunches over the piers are not modeled). Skew
shears the plan into a parallelogram (0-25 deg per the sheet).

Component inputs (Type Hint / Access in parentheses):
    end_span  (int,   Item)  end span, ft (14-46, tabulated)
    width     (float, Item)  slab width, ft
    skew      (float, Item)  degrees (optional, 0; max 25)
    bake      (bool,  Item)  write display geometry to Deck::CS-1-24
Outputs:
    slab    (Brep, Item)   the slab solid
    rebar   (Curve, List)  A/B/C/D/E longitudinal bars
    outline (Curve, Item)  plan outline at the top of slab
    piers   (Point, List)  pier centerline stations (on the roadway CL)
    report  (str)

Baked geometry is display-only and carries no gdr.* tags. Uses the
Deck:: layer group (this SCD is the deck/superstructure itself).
"""

"""
# //TODO - Missing # r: civilpy
- Right and Front orientation flipped
- Rebar appears under the slab
- No option for "edge beams"
- Slab doesn't preview, only rebar
- No transverse Rebar
- Needs an "over the side drainage" boolean toggle
- End span is kind of a weird input, should either probably be total span, or main/center span
- Width doesn't actually change the # of A/B/C/D Bars (might actually be correct, I need to verify that aspect)
- A/B bars are correctly centered over the piers like the standard outlines
- Future improvements: figure out calculation formulas the standard is based on and integrate those into the functions
    to allow for changes like modifying rebar from epoxy to stainless or GFRP
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.continuous_slab_bridge import (
    ContinuousSlabInput,
    layout_continuous_slab,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _slab_solid(outline, thickness_in, s):
    poly = rg.Polyline([_pt(p, s) for p in outline]
                       + [_pt(outline[0], s)]).ToNurbsCurve()
    ext = rg.Extrusion.Create(poly, -thickness_in / 12.0 * s, True)
    return ext.ToBrep() if ext else None


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Deck::CS-1-24", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Deck", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Deck"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "CS-1-24"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(170, 170, 175)
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
        elif isinstance(o, rg.Point3d):
            doc.Objects.AddPoint(o, a)
        else:
            continue
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

slab, outline_curve = None, None
rebar, piers = [], []

if not globals().get("end_span") or not globals().get("width"):
    report = "Connect at least: end_span (ft, 14-46), width (ft). " \
             "Optional: skew (deg, max 25), bake."
else:
    s = _scale()
    inp = ContinuousSlabInput(
        end_span_ft=int(end_span),
        width_ft=float(width),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
    )
    try:
        layout = layout_continuous_slab(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        slab = _slab_solid(layout.outline, layout.thickness_in, s)
        outline_curve = rg.Polyline(
            [_pt(p, s) for p in layout.outline]
            + [_pt(layout.outline[0], s)]).ToNurbsCurve()
        for bar in layout.bars:
            rebar.append(rg.LineCurve(_pt(bar.points[0], s),
                                      _pt(bar.points[-1], s)))
        piers = [rg.Point3d(x * s, 0.0, 0.0) for x in layout.pier_stations]

        counts = {}
        for bar in layout.bars:
            counts[bar.mark] = counts.get(bar.mark, 0) + 1
        report_lines = [
            "ODOT CS-1-24 continuous slab bridge (rev. 01-16-2026)",
        ] + list(layout.notes[:2]) + [
            "Bars: " + ", ".join("{} x {}".format(v, k)
                                 for k, v in sorted(counts.items())),
            layout.notes[2],
        ]
        if globals().get("bake"):
            n = _bake([slab, outline_curve] + rebar + piers)
            report_lines.append(
                "BAKED {} objects to Deck::CS-1-24 (display only).".format(n))
        report = "\n".join(report_lines)
