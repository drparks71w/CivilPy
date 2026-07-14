# r: civilpy
"""ODOT EXJ-5-93 Strip Seal Expansion Joint (Box Beam) — GHPython
(Rhino 8, CPython 3) source.

Drop-in Grasshopper component for EXJ-5-93 (rev. 01-19-2024): the skewed
joint centerline (sized by the sheet's own joint-length formula) plus a
marker at each beam-to-beam gap where a plate "A"/"B"/"C" group sits. All
engineering content comes from
``civilpy.structural.odot.strip_seal_joint_box_beam``; this script only
draws. The strip-seal gland itself is manufacturer-generic and not drawn.

Component inputs (Type Hint / Access in parentheses):
    n_beams     (int,   Item)  number of box beams (>= 2)
    beam_width  (float, Item)  in (36 or 48, tabulated)
    skew        (float, Item)  degrees (optional, 0)
    bake        (bool,  Item)  write display geometry to
                                Superstructure::EXJ-5-93
Outputs:
    joint_line  (Curve, Item)  skewed joint centerline
    gap_points  (Point, List)  beam-to-beam gap stations on the joint line
    report      (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

"""
# //TODO - Missing # r: civilpy
- just shows string points in preview, no joint or 3D object
- needs to display plates, shear studs, cover plates, retainers glands
- should take stringers, deck, curbs, etc. into consideration, station is really probably the only designer dependent 
    variable
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.strip_seal_joint_box_beam import (
    BoxBeamJointInput,
    layout_box_beam_joint,
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
    idx = doc.Layers.FindByFullPath("Superstructure::EXJ-5-93", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Superstructure", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Superstructure"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "EXJ-5-93"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(200, 30, 30)
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

joint_line = None
gap_points = []

if not globals().get("n_beams") or not globals().get("beam_width"):
    report = "Connect: n_beams (>= 2), beam_width (in: 36 or 48). " \
             "Optional: skew (deg), bake."
else:
    s = _scale()
    inp = BoxBeamJointInput(
        n_beams=int(n_beams),
        beam_width_in=float(beam_width),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
    )
    try:
        layout = layout_box_beam_joint(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        joint_line = rg.LineCurve(_pt(layout.joint_line[0], s),
                                  _pt(layout.joint_line[1], s))
        tan_skew = (layout.joint_line[1][0] - layout.joint_line[0][0]) / \
            layout.length_ft if layout.length_ft else 0.0
        for y in layout.beam_gap_stations_ft:
            gap_points.append(_pt((y * tan_skew, y, 0.0), s))

        report_lines = [
            "ODOT EXJ-5-93 strip seal joint, box beams (rev. 01-19-2024)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([joint_line] + gap_points)
            report_lines.append(
                "BAKED {} objects to Superstructure::EXJ-5-93 (display "
                "only).".format(n))
        report = "\n".join(report_lines)
