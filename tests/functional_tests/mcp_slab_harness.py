"""MCP test harness: draw a civilpy SB-1-24 slab emit into a live Rhino doc.

**Test-only. Not importable from civilpy runtime and carries no civilpy
import.** The MCP server is a test convenience, not a production dependency
(many users drive the Grasshopper components with no AI in the loop), so the
civilpy <-> Rhino boundary here is a plain JSON file, not a shared module:

    dev venv:  slab_emit(...) -> EmitObject records -> emit.json
    Rhino py:  this script    -> emit.json -> RhinoCommon geometry + user text

Run the civilpy side with ``dump_emit`` (below) in the dev venv, then execute
``draw_emit`` inside Rhino via ``mcp__rhino__run_python`` (it injects
``__rhino_doc__``; do not trust ``scriptcontext``). The geometry and the
``slab.*`` user strings match what ``rhino_slab.write_slab_bridge`` bakes
offline, so a visual check here validates the same records the offline .3dm
backend and the GH component consume.
"""

import json


def dump_emit(path, span_ft, width_ft, skew_deg=0.0,
              edge_condition="over_the_side", pay_items=None):
    """civilpy side (dev venv): serialize a slab emit to ``path`` as JSON."""
    from civilpy.structural.odot.slab_bridge import SlabBridgeInput
    from civilpy.structural.rhino_slab import slab_emit

    emit = slab_emit(
        SlabBridgeInput(span_ft=int(span_ft), width_ft=float(width_ft),
                        skew_deg=float(skew_deg), edge_condition=edge_condition),
        pay_items=pay_items)
    payload = {
        "doc_tags": emit.doc_tags,
        "objects": [{"kind": o.kind, "layer": o.layer, "points": o.points,
                     "tags": o.tags, "extrude_ft": o.extrude_ft,
                     "closed": o.closed} for o in emit.objects],
    }
    with open(path, "w") as f:
        json.dump(payload, f)
    return len(payload["objects"])


# ── Rhino side (runs inside Rhino's Python; no civilpy import) ─────────────

DEFAULT_COLORS = {
    "Deck": (170, 170, 175),
    "Deck::Bridge Deck": (170, 170, 175),
    "Deck::Rebar": (60, 120, 200),
}


def _ensure_layer(doc, full_path):
    """Walk a ``Group::Leaf`` path, creating missing layers; return leaf index.
    Mirrors ``rhino_layers.ensure_layer`` but for the live RhinoCommon doc."""
    import Rhino
    import System.Drawing as sd

    idx = doc.Layers.FindByFullPath(full_path, -1)
    if idx >= 0:
        return idx
    parent_id, accum, leaf = None, "", -1
    for part in full_path.split("::"):
        accum = part if not accum else accum + "::" + part
        found = doc.Layers.FindByFullPath(accum, -1)
        if found >= 0:
            leaf = found
            parent_id = doc.Layers[found].Id
            continue
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = part
        r, g, b = DEFAULT_COLORS.get(accum, (128, 128, 128))
        lyr.Color = sd.Color.FromArgb(r, g, b)
        if parent_id is not None:
            lyr.ParentLayerId = parent_id
        leaf = doc.Layers.Add(lyr)
        parent_id = doc.Layers[leaf].Id
    return leaf


def draw_emit(doc, emit_json_path):
    """Rhino side: draw ``emit.json`` into ``doc`` with ``slab.*`` user text.

    Returns a summary dict. ``doc`` is the MCP-injected ``__rhino_doc__``.
    Feet -> document units via ``UnitScale`` (the emit is authored in feet).
    """
    import Rhino
    import Rhino.Geometry as rg
    import System

    with open(emit_json_path) as f:
        payload = json.load(f)

    s = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Feet, doc.ModelUnitSystem)

    def p3(pt):
        return rg.Point3d(pt[0] * s, pt[1] * s, pt[2] * s)

    layer_idx = {}
    counts = {"point": 0, "solid": 0, "curve": 0, "failed": 0}
    ids = []

    for obj in payload["objects"]:
        layer = obj["layer"]
        if layer not in layer_idx:
            layer_idx[layer] = _ensure_layer(doc, layer)
        attr = Rhino.DocObjects.ObjectAttributes()
        attr.LayerIndex = layer_idx[layer]
        attr.Name = obj["tags"].get("slab.mark") or obj["tags"].get("slab.kind")
        for k, v in obj["tags"].items():
            attr.SetUserString(k, v)

        pts = [p3(p) for p in obj["points"]]
        gid = None
        if obj["kind"] == "point":
            gid = doc.Objects.AddPoint(pts[0], attr)
        elif obj["kind"] == "solid":
            poly = rg.Polyline(pts + [pts[0]]).ToNurbsCurve()
            ext = rg.Extrusion.Create(poly, obj["extrude_ft"] * s, True)
            if ext:
                gid = doc.Objects.AddExtrusion(ext, attr)
        else:
            poly = rg.Polyline(pts + [pts[0]] if obj["closed"] else pts)
            gid = doc.Objects.AddPolyline(poly, attr)

        if gid and gid != System.Guid.Empty:
            counts[obj["kind"]] += 1
            ids.append(str(gid))
        else:
            counts["failed"] += 1

    doc.Views.Redraw()
    return {"drawn": counts, "layers": sorted(layer_idx),
            "doc_tags": payload["doc_tags"], "object_ids": ids}
