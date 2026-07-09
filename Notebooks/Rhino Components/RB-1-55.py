"""ODOT RB-1-55 Rockers and Bolsters — GHPython (Rhino 8, CPython 3) source.

Drop-in Grasshopper component for SCD RB-1-55 (rev. 07-19-2024): a
matched bolster (fixed bearing) + rocker (expansion bearing) pair for a
given rated capacity. All engineering content comes from
``civilpy.structural.odot.rocker_bolster``; this script only draws.

Drawable subset: a base (masonry) plate shared by both, a tapered body
narrowing to width A, flat on the bolster and capped by the curved
bearing surface (TOP BEARING DETAIL radius) on the rocker. Flange plate,
welds, anchor bolts, dowels, and reinforcing are cataloged, not drawn --
see the module docstring.

Component inputs (Type Hint / Access in parentheses):
    capacity  (int,  Item)  rated capacity, kips (75, 100, 125, ..., 300)
    spacing   (float, Item)  ft apart to place the bolster/rocker pair
                            (optional, 3 ft)
    bake      (bool, Item)  write display geometry to
                            Superstructure::RB-1-55
Outputs:
    bolster  (Brep, Item)  bolster solid (flat top)
    rocker   (Brep, Item)  rocker solid (curved top)
    report   (str)

Baked geometry is display-only and carries no gdr.* tags. Uses the
Superstructure:: layer group (bearings are a superstructure element, per
Gdr.cs's LayerBearings).
"""

"""
# //TODO - Missing r: civilpy
- No Preview of objects
- Front/Right Orientation Swapped
- displays two objects, neither really look like a bolster or a rocker
- Outputs to a dedicated layer fine (under superstructure) should use it's common name though in the layer
- Needs 3 distinct parts bottom flange plate 
- Needs to generate a bolster or a rocker, not both
- Needs to be oriented off of a steel girder's bottom flange and abutment seat
- Needs Anchor bolts
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.rocker_bolster import (
    layout_rocker_bolster,
    rocker_bolster,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
IN_PER_FT = 12.0


def _scale():
    """Inches (layout units) -> current document units."""
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Inches, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s, x_offset=0.0):
    return rg.Point3d((p[0] + x_offset) * s, p[1] * s, p[2] * s)


def _frustum_to_flat_top(base_outline, top_outline, height_in, s, x_offset=0.0):
    base = [_pt(p, s, x_offset) for p in base_outline]
    top = [rg.Point3d(p.X, p.Y, p.Z + height_in * s) for p in
           [_pt(q, s, x_offset) for q in top_outline]]
    loft = rg.Brep.CreateFromLoft(
        [rg.Polyline(base + [base[0]]).ToNurbsCurve(),
         rg.Polyline(top + [top[0]]).ToNurbsCurve()],
        rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Straight, False)
    if not loft:
        return None
    brep = loft[0]
    capped = brep.CapPlanarHoles(TOL)
    return capped or brep


def _rocker_cap(base_outline, height_in, radius_in, s, x_offset=0.0):
    """A half-cylinder cap (axis along Y/transverse) on top of the frustum,
    radius from the TOP BEARING DETAIL formula."""
    y0 = base_outline[0][1]
    y1 = base_outline[2][1]
    center = _pt((0.0, y0, height_in), s, x_offset)
    axis_end = _pt((0.0, y1, height_in), s, x_offset)
    plane = rg.Plane(center, rg.Vector3d(0, 0, 1), rg.Vector3d(1, 0, 0))
    circle = rg.Circle(plane, radius_in * s)
    arc = rg.Arc(circle, rg.Interval(0, Rhino.RhinoMath.ToRadians(180)))
    rail = rg.LineCurve(center, axis_end)
    sweep = rg.SweepOneRail()
    result = sweep.PerformSweep(rail, arc.ToNurbsCurve())
    if result and len(result) > 0:
        return result[0].CapPlanarHoles(TOL) or result[0]
    return None


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Superstructure::RB-1-55", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Superstructure", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Superstructure"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "RB-1-55"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(0, 110, 200)
        idx = doc.Layers.Add(lyr)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = idx
    n = 0
    for o in objs:
        if o is None:
            continue
        doc.Objects.AddBrep(o, a)
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

bolster, rocker = None, None

if not globals().get("capacity"):
    report = "Connect: capacity (kips: 75/100/125/.../300). Optional: " \
             "spacing (ft, default 3), bake."
else:
    s = _scale()
    spa_in = (float(spacing) if globals().get("spacing") else 3.0) * IN_PER_FT

    try:
        rb = rocker_bolster(int(capacity))
        layout = layout_rocker_bolster(rb)
    except (KeyError, ValueError) as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        base = _frustum_to_flat_top(layout.base_outline, layout.base_outline,
                                    layout.base_thickness_in, s,
                                    x_offset=-spa_in / 2.0)
        body = _frustum_to_flat_top(layout.base_outline, layout.bolster_top,
                                    layout.bolster_height_in
                                    - layout.base_thickness_in, s,
                                    x_offset=-spa_in / 2.0)
        bolster = body

        rbase = _frustum_to_flat_top(layout.base_outline, layout.base_outline,
                                     layout.base_thickness_in, s,
                                     x_offset=spa_in / 2.0)
        rbody = _frustum_to_flat_top(layout.base_outline, layout.bolster_top,
                                     layout.rocker_height_in
                                     - layout.base_thickness_in, s,
                                     x_offset=spa_in / 2.0)
        rcap = _rocker_cap(layout.base_outline, layout.rocker_height_in,
                          layout.rocker_top_radius_in, s,
                          x_offset=spa_in / 2.0)
        rocker = rbody

        report_lines = [
            "ODOT RB-1-55 rocker/bolster (rev. 07-19-2024)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([base, bolster, rbase, rocker, rcap])
            report_lines.append(
                "BAKED {} objects to Superstructure::RB-1-55 (display "
                "only).".format(n))
        report = "\n".join(report_lines)
