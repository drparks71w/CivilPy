"""ODOT AS-1-15 Reinforced Concrete Approach Slab — GHPython (Rhino 8,
CPython 3) source.

Drop-in Grasshopper component for SCD AS-1-15 (rev. 01-20-2023).  All
engineering content (the reinforcing-steel table, bar counts/lengths,
section geometry, anchor-bar rules) comes from
``civilpy.structural.odot.approach_slab``; this script only draws.

Component inputs (Type Hint / Access in parentheses):
    length     (float, Item)  approach slab length L, ft (15/20/25/30)
    width      (float, Item)  approach slab width W, ft (see the sheet's
                              width-dimension figure)
    skew       (float, Item)  skew angle, degrees (optional, 0)
    end_thickness (float, Item)  X at the abutment end, in (optional, = T;
                              never less than T)
    seat_length   (float, Item)  bearing on seat/backwall, in (optional,
                              9; sheet allows 6 to 12)
    backwall      (float, Item)  backwall thickness, in (optional, 14;
                              selects D801 vs D802 anchor bars)
    bake       (bool, Item)   True = write display geometry to the
                              SCD::AS-1-15 layer in the active document
Outputs:
    slab    (Brep, Item)   the approach slab solid
    rebar   (Curve, List)  every bar (A, B501, C, D801/D802)
    outline (Curve, Item)  plan outline at the top of slab
    report  (str)

Baked geometry is display-only and carries no gdr.* tags (per the
contract, readers ignore untagged geometry).
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.approach_slab import (
    ApproachSlabInput,
    layout_approach_slab,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    """Feet (layout units) -> current document units."""
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _slab_solid(layout, s):
    """Sweep the longitudinal section profile across the width along the
    skewed transverse direction (a shear extrusion, so the skewed plan
    parallelogram and the seat profile are both exact)."""
    import math
    prof = rg.Polyline(
        [rg.Point3d(u * s, 0.0, z * s) for u, z in layout.profile]
        + [rg.Point3d(layout.profile[0][0] * s, 0.0,
                      layout.profile[0][1] * s)]).ToNurbsCurve()
    w = layout.inputs.width_ft
    tan_skew = math.tan(math.radians(layout.inputs.skew_deg))
    vec = rg.Vector3d(w * tan_skew * s, w * s, 0.0)
    srf = rg.Surface.CreateExtrusion(prof, vec)
    if srf is None:
        return None
    brep = srf.ToBrep()
    capped = brep.CapPlanarHoles(TOL)
    return capped or brep


def _bake(slab, curves, outline):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd

    def layer(path, color):
        idx = doc.Layers.FindByFullPath(path, -1)
        if idx >= 0:
            return idx
        parent = None
        full = ""
        for name in path.split("::"):
            full = name if not full else full + "::" + name
            idx = doc.Layers.FindByFullPath(full, -1)
            if idx < 0:
                lyr = Rhino.DocObjects.Layer()
                lyr.Name = name
                if parent is not None:
                    lyr.ParentLayerId = doc.Layers[parent].Id
                lyr.Color = color
                idx = doc.Layers.Add(lyr)
            parent = idx
        return idx

    lay_slab = layer("SCD::AS-1-15", sd.Color.FromArgb(160, 160, 160))
    lay_bars = layer("SCD::AS-1-15::Rebar", sd.Color.FromArgb(170, 40, 40))

    def attrs(lay):
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex = lay
        return a

    n = 0
    if slab:
        doc.Objects.AddBrep(slab, attrs(lay_slab))
        n += 1
    if outline:
        doc.Objects.AddCurve(outline, attrs(lay_slab))
        n += 1
    for c in curves:
        doc.Objects.AddCurve(c, attrs(lay_bars))
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

slab, rebar, outline = None, [], None

if not globals().get("length") or not globals().get("width"):
    report = "Connect at least: length (15/20/25/30 ft) and width (ft)."
else:
    s = _scale()
    inp = ApproachSlabInput(
        length_ft=float(length),
        width_ft=float(width),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        end_thickness_in=(float(end_thickness)
                          if globals().get("end_thickness") else None),
        seat_length_in=(float(seat_length)
                        if globals().get("seat_length") else 9.0),
        backwall_thickness_in=(float(backwall)
                               if globals().get("backwall") else 14.0),
    )
    try:
        layout = layout_approach_slab(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        slab = _slab_solid(layout, s)
        for bar in layout.bars:
            pts = [_pt(p, s) for p in bar.points]
            rebar.append(rg.PolylineCurve(pts) if len(pts) > 2
                         else rg.LineCurve(pts[0], pts[1]))
        outline = rg.Polyline(
            [_pt(p, s) for p in layout.outline]
            + [_pt(layout.outline[0], s)]).ToNurbsCurve()

        d = layout.design
        counts = {}
        for bar in layout.bars:
            counts[bar.mark] = counts.get(bar.mark, 0) + 1
        sched = ", ".join("{} x {}".format(v, k)
                          for k, v in sorted(counts.items()))
        report_lines = [
            "ODOT AS-1-15 approach slab (rev. 01-20-2023)",
            "L = {:g} ft, T = {:g} in, W = {:g} ft, skew = {:g} deg".format(
                d.length_ft, d.thickness_in, inp.width_ft, inp.skew_deg),
            "Bars: " + sched,
            "A bars {} @ K = {:g} in; B501 bottom @ N = {:g} in "
            "(5 sp. @ 6 in at bridge end); B501 top & C bars @ 6 in".format(
                d.a_bar_mark, d.a_bar_spacing_in, d.b501_bottom_spacing_in),
            "Anchor bars: {} x {:.2f} ft (paid under Item 509)".format(
                layout.anchor_mark, layout.anchor_length_ft),
            "Item 526 estimated quantity: {:.1f} SY".format(
                layout.pay_area_sy),
        ] + list(layout.notes[2:])
        if globals().get("bake"):
            n = _bake(slab, rebar, outline)
            report_lines.append("BAKED {} objects to SCD::AS-1-15 "
                                "(display only, untagged).".format(n))
        report = "\n".join(report_lines)
