"""ODOT SB-1-24 Single Span Slab Bridge — GHPython (Rhino 8, CPython 3) source.

Drop-in Grasshopper component for SCD SB-1-24 (rev. 01-16-2026): the slab
solid and A/B/M/N longitudinal reinforcing mats for a single span slab
bridge, spans 11-38 ft. All engineering content and the tagged, transport
-neutral geometry come from ``civilpy.structural.rhino_slab.slab_emit``; this
script only realizes those records as ``Rhino.Geometry`` and (optionally)
bakes them with their ``slab.*`` user-text attributes.

The slab is generated with the upstream bearing line at x = 0, one edge at
y = 0, and z = 0 at the top of slab (slab extends DOWN ``thickness``). Skew
shears the plan into a parallelogram (0-25 deg per the sheet).

Component inputs (Type Hint / Access in parentheses):
    span            (int,   Item)  span, ft (11-38, tabulated)
    width           (float, Item)  slab width, ft
    skew            (float, Item)  degrees (optional, 0; max 25)
    edge_condition  (str,   Item)  "over_the_side" or "parapet" (optional)
    conc_pay_item   (str,   Item)  ODOT CMS item for the slab concrete (optional)
    rebar_pay_item  (str,   Item)  ODOT CMS item for the reinforcing (optional)
    bake            (bool,  Item)  write tagged geometry to Deck::Bridge Deck /
                                   Deck::Rebar
Outputs:
    slab    (Brep, Item)   the slab solid
    rebar   (Curve, List)  A/B/M/N longitudinal bars
    outline (Curve, Item)  plan outline at the top of slab
    report  (str)

**Baked geometry carries ``slab.*`` user-text** (see ``rhino_slab``): the slab
gets material/thickness/f'c/pay-item, each bar its mark/size/diameter/area/mat
/epoxy/pay-item, and a ``slab.kind=bridge`` marker point carries the bridge
-wide parameters (span/width/skew/thickness) MIDAS reads downstream. This is
what lets ``civilpy`` rebuild the analysis model and the L1 design checks from
the Rhino document alone -- the "engineer experimenting in a notebook" loop.

Fixes vs. the prior revision (its own TODO block): the slab used to extrude
UP (rebar appeared below the concrete) because the outline winds clockwise;
``slab_emit`` normalizes the winding so the solid extrudes down and the bars
sit inside it. Layers are the shared ``Deck::`` taxonomy, not ``Deck::SB-1-24``.
"""

"""
# //TODO (still open, see Validation TODOs.md)
- Standard shows hooked "A-Bars"; only straight runs modeled
- No transverse rebar, no edge-beam taper solid (D/X), no U401/U402 lap bars
- Elevation not tied to alignment/abutment (needs terrain)
- No rebar-conflict checks against approach slabs / parapet types yet
"""

import Rhino
import Rhino.Geometry as rg
import System

from civilpy.structural.rhino_slab import slab_emit, TAG
from civilpy.structural.odot.slab_bridge import SlabBridgeInput

_DOC = Rhino.RhinoDoc.ActiveDoc
_LAYER_COLORS = {
    "Deck": (170, 170, 175),
    "Deck::Bridge Deck": (170, 170, 175),
    "Deck::Rebar": (60, 120, 200),
}


def _scale():
    return Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Feet, _DOC.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _solid(obj, s):
    poly = rg.Polyline([_pt(p, s) for p in obj.points]
                       + [_pt(obj.points[0], s)]).ToNurbsCurve()
    ext = rg.Extrusion.Create(poly, obj.extrude_ft * s, True)
    return ext.ToBrep() if ext else None


def _polyline(obj, s):
    pts = [_pt(p, s) for p in obj.points]
    if obj.closed:
        pts.append(pts[0])
    return rg.Polyline(pts).ToPolylineCurve()


def _ensure_layer(full_path):
    idx = _DOC.Layers.FindByFullPath(full_path, -1)
    if idx >= 0:
        return idx
    parent_id, accum, leaf = None, "", -1
    for part in full_path.split("::"):
        accum = part if not accum else accum + "::" + part
        found = _DOC.Layers.FindByFullPath(accum, -1)
        if found >= 0:
            leaf, parent_id = found, _DOC.Layers[found].Id
            continue
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = part
        r, g, b = _LAYER_COLORS.get(accum, (128, 128, 128))
        lyr.Color = System.Drawing.Color.FromArgb(r, g, b)
        if parent_id is not None:
            lyr.ParentLayerId = parent_id
        leaf = _DOC.Layers.Add(lyr)
        parent_id = _DOC.Layers[leaf].Id
    return leaf


def _bake(emit, s):
    """Bake every emit object with its slab.* user text; return the count."""
    layer_idx = {}
    n = 0
    for obj in emit.objects:
        if obj.layer not in layer_idx:
            layer_idx[obj.layer] = _ensure_layer(obj.layer)
        attr = Rhino.DocObjects.ObjectAttributes()
        attr.LayerIndex = layer_idx[obj.layer]
        attr.Name = obj.tags.get(TAG + "mark") or obj.tags.get(TAG + "kind")
        for k, v in obj.tags.items():
            attr.SetUserString(k, v)
        pts = [_pt(p, s) for p in obj.points]
        gid = System.Guid.Empty
        if obj.kind == "point":
            gid = _DOC.Objects.AddPoint(pts[0], attr)
        elif obj.kind == "solid":
            brep = _solid(obj, s)
            if brep:
                gid = _DOC.Objects.AddBrep(brep, attr)
        else:
            gid = _DOC.Objects.AddCurve(_polyline(obj, s), attr)
        if gid != System.Guid.Empty:
            n += 1
    _DOC.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

slab, outline_curve = None, None
rebar = []

if not globals().get("span") or not globals().get("width"):
    report = ("Connect at least: span (ft, 11-38), width (ft). Optional: skew "
              "(deg, max 25), edge_condition ('over_the_side'/'parapet'), "
              "conc_pay_item, rebar_pay_item, bake.")
else:
    s = _scale()
    inp = SlabBridgeInput(
        span_ft=int(span),
        width_ft=float(width),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        edge_condition=str(edge_condition)
        if globals().get("edge_condition") else "over_the_side",
    )
    pay = {}
    if globals().get("conc_pay_item"):
        pay["concrete"] = str(conc_pay_item)
    if globals().get("rebar_pay_item"):
        pay["rebar"] = str(rebar_pay_item)

    try:
        emit = slab_emit(inp, pay_items=pay)
    except ValueError as exc:
        emit = None
        report = "INPUT ERROR: {}".format(exc)

    if emit:
        for obj in emit.objects:
            kind = obj.tags.get(TAG + "kind", "")
            if kind == "slab":
                slab = _solid(obj, s)
            elif kind == "rebar":
                rebar.append(_polyline(obj, s))
            elif kind == "":       # cosmetic plan outline
                outline_curve = _polyline(obj, s)

        layout = emit.layout
        counts = {}
        for obj in emit.of_kind("rebar"):
            m = obj.tags[TAG + "mark"]
            counts[m] = counts.get(m, 0) + 1
        report_lines = [
            "ODOT SB-1-24 single span slab bridge (rev. 01-16-2026)",
        ] + list(layout.notes[:2]) + [
            "Bars: " + ", ".join("{} x {}".format(v, k)
                                 for k, v in sorted(counts.items())),
            layout.notes[2],
        ]
        if globals().get("bake"):
            n = _bake(emit, s)
            report_lines.append(
                "BAKED {} objects (with slab.* user text) to Deck::Bridge "
                "Deck / Deck::Rebar.".format(n))
        report = "\n".join(report_lines)
