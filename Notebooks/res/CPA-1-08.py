"""ODOT CPA-1-08 Capped Pile Abutment — GHPython (Rhino 8, CPython 3)
source.

Drop-in Grasshopper component for CPA-1-08 (rev. 01-19-2024), SB-1-24's
companion abutment: the cap + pile line + one flared wingwall, from
dimensions the engineer supplies (this sheet has no dimension table for
the overall geometry -- only a handful of fixed section constants and a
reinforcing bend legend; see
``civilpy.structural.odot.capped_pile_abutment``'s module docstring). All
engineering content comes from that module; this script only draws.

The abutment is generated with the cap centerline at x = 0 (bridge seat,
z = 0), y = 0 at the cap's transverse centerline.

Component inputs (Type Hint / Access in parentheses):
    wingwall_length (float, Item)  W, ft
    skew            (float, Item)  degrees (optional, 0)
    n_piles         (int,   Item)  pile count (>= 2)
    pile_spacing    (float, Item)  ft
    footing_depth   (float, Item)  ft, cap/footing depth below bridge seat
    bake            (bool,  Item)  write display geometry to Substructure::CPA-1-08
Outputs:
    cap       (Brep, Item)   cap solid
    piles     (Point, List)  pile centerline points (top of pile)
    wingwall  (Curve, Item)  wingwall flared outline
    report    (str)

Baked geometry is display-only and carries no gdr.* tags. Uses the
Substructure:: layer group (this is the abutment, an NBIS substructure
element) -- see docs/Rhino Design Philosophy.md.
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.capped_pile_abutment import (
    AbutmentInput,
    layout_capped_pile_abutment,
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
    idx = doc.Layers.FindByFullPath("Substructure::CPA-1-08", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Substructure", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Substructure"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "CPA-1-08"
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
        elif isinstance(o, rg.Point3d):
            doc.Objects.AddPoint(o, a)
        else:
            continue
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

cap, wingwall = None, None
piles = []

_required = ("wingwall_length", "n_piles", "pile_spacing", "footing_depth")
if not all(globals().get(k) for k in _required):
    report = "Connect all of: wingwall_length, n_piles, pile_spacing, " \
             "footing_depth (ft). Optional: skew (deg), bake. CPA-1-08 " \
             "has no dimension table for the overall geometry -- every " \
             "value is project-specific (from the abutment design)."
else:
    s = _scale()
    inp = AbutmentInput(
        wingwall_length_ft=float(wingwall_length),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        n_piles=int(n_piles),
        pile_spacing_ft=float(pile_spacing),
        footing_depth_ft=float(footing_depth),
    )
    try:
        layout = layout_capped_pile_abutment(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        cap = _prism(layout.cap_outline, inp.footing_depth_ft, s)
        piles = [_pt(p, s) for p in layout.pile_points]
        wingwall = rg.Polyline(
            [_pt(p, s) for p in layout.wingwall_outline]
            + [_pt(layout.wingwall_outline[0], s)]).ToNurbsCurve()

        report_lines = [
            "ODOT CPA-1-08 capped pile abutment (rev. 01-19-2024)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([cap, wingwall] + piles)
            report_lines.append(
                "BAKED {} objects to Substructure::CPA-1-08 (display "
                "only).".format(n))
        report = "\n".join(report_lines)
