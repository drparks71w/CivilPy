"""ODOT SB-1-24 Single Span Slab Bridge — GHPython (Rhino 8, CPython 3)
source.

Drop-in Grasshopper component for SCD SB-1-24 (rev. 01-16-2026): the slab
solid and A/B/M/N longitudinal reinforcing mats for a single span slab
bridge, spans 11-38 ft. All engineering content comes from
``civilpy.structural.odot.slab_bridge``; this script only draws.

The slab is generated with the upstream bearing line at x = 0, one edge
at y = 0, and z = 0 at the top of slab (slab extends down ``thickness``).
Skew shears the plan into a parallelogram (0-25 deg per the sheet).

Component inputs (Type Hint / Access in parentheses):
    span            (int,   Item)  span, ft (11-38, tabulated)
    width           (float, Item)  slab width, ft
    skew            (float, Item)  degrees (optional, 0; max 25)
    edge_condition  (str,   Item)  "over_the_side" or "parapet" (optional,
                                  "over_the_side")
    bake            (bool,  Item)  write display geometry to Deck::SB-1-24
Outputs:
    slab    (Brep, Item)   the slab solid
    rebar   (Curve, List)  A/B/M/N longitudinal bars
    outline (Curve, Item)  plan outline at the top of slab
    report  (str)

Baked geometry is display-only and carries no gdr.* tags. Uses the
Deck:: layer group (this is the deck/superstructure itself, not an SCD
plan-insert accessory) -- see docs/Rhino Design Philosophy.md.
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.slab_bridge import (
    SlabBridgeInput,
    layout_slab_bridge,
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
    idx = doc.Layers.FindByFullPath("Deck::SB-1-24", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Deck", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Deck"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "SB-1-24"
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
        else:
            continue
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

slab, outline_curve = None, None
rebar = []

if not globals().get("span") or not globals().get("width"):
    report = "Connect at least: span (ft, 11-38), width (ft). Optional: " \
             "skew (deg, max 25), edge_condition ('over_the_side'/" \
             "'parapet'), bake."
else:
    s = _scale()
    inp = SlabBridgeInput(
        span_ft=int(span),
        width_ft=float(width),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        edge_condition=str(edge_condition)
        if globals().get("edge_condition") else "over_the_side",
    )
    try:
        layout = layout_slab_bridge(inp)
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

        counts = {}
        for bar in layout.bars:
            counts[bar.mark] = counts.get(bar.mark, 0) + 1
        report_lines = [
            "ODOT SB-1-24 single span slab bridge (rev. 01-16-2026)",
        ] + list(layout.notes[:2]) + [
            "Bars: " + ", ".join("{} x {}".format(v, k)
                                 for k, v in sorted(counts.items())),
            layout.notes[2],
        ]
        if globals().get("bake"):
            n = _bake([slab, outline_curve] + rebar)
            report_lines.append(
                "BAKED {} objects to Deck::SB-1-24 (display only).".format(n))
        report = "\n".join(report_lines)
