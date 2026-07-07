"""ODOT CPP-1-08 Capped Pile Pier — GHPython (Rhino 8, CPython 3) source.

Drop-in Grasshopper component for CPP-1-08 (rev. 07-21-2017), CS-1-24's
companion pier: the rounded-end pier cap solid and pile line, generated
from the sheet's own pier-length formula (3'-0" + (slab width - 4'-4")
/cos(skew)) plus a fixed cap width/end-radius. All engineering content
comes from ``civilpy.structural.odot.capped_pile_pier``; this script only
draws.

The pier is generated with the pier centerline at x = 0 (top of cap,
z = 0), y = 0 on the roadway centerline.

Component inputs (Type Hint / Access in parentheses):
    slab_width    (float, Item)  bridge slab width, ft
    skew          (float, Item)  degrees (optional, 0; max 30)
    n_piles       (int,   Item)  pile count (>= 2)
    pile_spacing  (float, Item)  ft (max 7.5)
    cap_depth     (float, Item)  ft (optional, 2.0 -- the sheet default)
    bake          (bool,  Item)  write display geometry to Substructure::CPP-1-08
Outputs:
    cap     (Brep, Item)   rounded-end cap solid
    piles   (Point, List)  pile centerline points (top of pile)
    report  (str)

Baked geometry is display-only and carries no gdr.* tags. Uses the
Substructure:: layer group (a true NBIS substructure element).
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.capped_pile_pier import (
    CAP_DEPTH_FT,
    PierInput,
    layout_capped_pile_pier,
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
    idx = doc.Layers.FindByFullPath("Substructure::CPP-1-08", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Substructure", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Substructure"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "CPP-1-08"
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
        elif isinstance(o, rg.Point3d):
            doc.Objects.AddPoint(o, a)
        else:
            continue
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

cap = None
piles = []

_required = ("slab_width", "n_piles", "pile_spacing")
if not all(globals().get(k) for k in _required):
    report = "Connect at least: slab_width (ft), n_piles (>= 2), " \
             "pile_spacing (ft, max 7.5). Optional: skew (deg, max 30), " \
             "cap_depth (ft, default 2.0), bake."
else:
    s = _scale()
    inp = PierInput(
        slab_width_ft=float(slab_width),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        n_piles=int(n_piles),
        pile_spacing_ft=float(pile_spacing),
        cap_depth_ft=float(cap_depth) if globals().get("cap_depth") else CAP_DEPTH_FT,
    )
    try:
        layout = layout_capped_pile_pier(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        cap = _prism(layout.cap_outline, inp.cap_depth_ft, s)
        piles = [_pt(p, s) for p in layout.pile_points]

        report_lines = [
            "ODOT CPP-1-08 capped pile pier (rev. 07-21-2017)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([cap] + piles)
            report_lines.append(
                "BAKED {} objects to Substructure::CPP-1-08 (display "
                "only).".format(n))
        report = "\n".join(report_lines)
