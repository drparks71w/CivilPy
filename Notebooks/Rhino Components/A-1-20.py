"""ODOT A-1-20 Typical Abutment Detail — GHPython (Rhino 8, CPython 3)
source.

Drop-in Grasshopper component for A-1-20 (rev. 01-19-2024): the backwall
+ footing + one flared wingwall for a girder-bridge abutment with
expansion joints, from project-supplied dimensions.

**GUIDANCE ONLY.** Sheet 1's own General note: "Treat the abutment
dimensions, construction joints and reinforcing shown in this drawing as
MINIMUM VALUES and perform a complete design for the abutment. Do not
reference these drawings in the contract plans and do not use as
standalone construction drawings." This component is a visual check
against that guidance, not a substitute for the abutment design -- see
``civilpy.structural.odot.typical_abutment``'s module docstring.

The abutment is generated with the backwall centerline at x = 0 (top of
footing, z = 0), y = 0 at the backwall's near face.

Component inputs (Type Hint / Access in parentheses):
    width           (float, Item)  abutment/deck width, ft
    skew            (float, Item)  degrees (optional, 0)
    wingwall_length (float, Item)  ft (<= 8 ft without an extended footing)
    footing_depth   (float, Item)  ft
    backwall_height (float, Item)  ft
    bake            (bool,  Item)  write display geometry to Substructure::A-1-20
Outputs:
    backwall  (Brep, Item)   backwall solid
    footing   (Brep, Item)   footing solid
    wingwall  (Curve, Item)  wingwall flared outline
    report    (str)

Baked geometry is display-only and carries no gdr.* tags. Uses the
Substructure:: layer group (a true NBIS substructure element).
"""

"""
# //TODO - The following notes are all issues that are appearing in the resulting Rhino Object

- The Wingwall is being represented as a square wireframe, not as an actual wingwall.
- The 'width' and 'depth' parameters are flopped, The "Right" viewport shows the wingwall getting longer, when the "Front" viewport
    should probably be the one getting wider when you adjust the width parameter. 
- All views should be assumed to be along a roadway alignment. So width should adjust from a centerpoint (located on the alignment)
- The wingwall orientation similarly should be able to be adjusted so they turn back away from the span
- Need a toggle for "near"/"far" abutment to be able to determine things like which way the wingwall orientations go (away from the span)
- Wingwalls need a terrain model of some form to interact with to determine things like necessary height. The SCD shows a 2:1 slope from
    the outside of the wingwall that isn't possible to depict without an understanding of the terrain (can be generated in python from
    Ohio "OGRIP" data sources).
- Missing multiple components of the actual backwall. The footing is mostly generating correctly, but piles are non-existent,
    The stem/backwall isn't represented, the bridge seat in front of it is missing, none of those things appear to be
    sloped the way they're depicted in the actual SCDs (3/4" between beam seats for water drainage, 1/8" / ft terrain slope along front of abutment).
- Drainage components not shown (6" NPCPP pipe)
- Completely missing important details like Rebar, PEJF, Construction Joints, Rock Channel protection, etc.
- Need some kind of distiction which types of structure designs it's appropriate to utilize with, semi-integral, integral, neither) 
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.typical_abutment import (
    AbutmentInput,
    layout_typical_abutment,
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
    idx = doc.Layers.FindByFullPath("Substructure::A-1-20", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Substructure", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Substructure"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "A-1-20"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(120, 90, 70)
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

backwall, footing, wingwall = None, None, None

_required = ("width", "wingwall_length", "footing_depth", "backwall_height")
if not all(globals().get(k) for k in _required):
    report = "Connect all of: width, wingwall_length, footing_depth, " \
             "backwall_height (ft). Optional: skew (deg), bake. " \
             "GUIDANCE ONLY -- see the report once connected."
else:
    s = _scale()
    inp = AbutmentInput(
        width_ft=float(width),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        wingwall_length_ft=float(wingwall_length),
        footing_depth_ft=float(footing_depth),
        backwall_height_ft=float(backwall_height),
    )
    try:
        layout = layout_typical_abutment(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        backwall = _prism(layout.backwall_outline, inp.backwall_height_ft, s)
        footing = _prism(layout.footing_outline, inp.footing_depth_ft, s)
        wingwall = rg.Polyline(
            [_pt(p, s) for p in layout.wingwall_outline]
            + [_pt(layout.wingwall_outline[0], s)]).ToNurbsCurve()

        report_lines = [
            "ODOT A-1-20 typical abutment (rev. 01-19-2024)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([backwall, footing, wingwall])
            report_lines.append(
                "BAKED {} objects to Substructure::A-1-20 (display "
                "only).".format(n))
        report = "\n".join(report_lines)
