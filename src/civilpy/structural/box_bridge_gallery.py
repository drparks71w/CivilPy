"""Generate four synthetic, reviewable bridge models and steel clash reports."""
from collections import Counter
from dataclasses import asdict, replace
import json
from pathlib import Path

from civilpy.structural.box_bridge_details import BoxDetailInput, LIMITATIONS, detailed_box_bridge_emit
from civilpy.structural.rebar_clash import check_clearance
from civilpy.structural.rhino_bim import BridgeEmit, emit_to_3dm, emit_to_json, EmitObject


PAIRS = (
    ("rail_anchors", "beam_rebar"), ("rail_anchors", "deck_rebar"),
    ("rail_anchors", "tie_rods"), ("rail_short_anchors", "beam_rebar"),
    ("approach_anchors", "abutment_rebar"), ("approach_rebar", "abutment_rebar"),
    ("approach_anchors", "approach_rebar"), ("bearing_dowels", "abutment_rebar"),
)

SCENARIOS = (
    BoxDetailInput(abutment="integral", foundation="piles", railing="DBR-3", terminal="buried", scenario_id="integral"),
    BoxDetailInput(abutment="semi-integral", foundation="spread", railing="DBR-3", terminal="type_a", scenario_id="semi-integral", grade_pct=-.5, profile_rise_in=2.),
    BoxDetailInput(abutment="seat", foundation="spread", railing="DBR-3", terminal="trailing_t", scenario_id="seat", grade_pct=.5, crown=False, profile_rise_in=0.),
    BoxDetailInput(abutment="seat", foundation="shafts", railing="TST-2", terminal="trailing_t", scenario_id="seat-shafts", grade_pct=.5),
)


def layer_color(layer):
    name = layer.lower()
    return ([240,50,50] if 'clash' in name else
            [240,170,45] if 'anchor' in name else [60,160,220] if 'rebar' in name else
            [145,105,65] if 'blockout' in name or 'timber' in name else [168,145,107] if 'soil' in name or 'terrain' in name else
            [90,95,100] if 'roadway_context' in name else
            [100,135,165] if 'railing' in name or 'end_treatment' in name else [25,160,180] if 'drain' in name else
            [90,90,100] if 'bearing' in name else [190,190,185])


def style_file(path, doc_tags):
    import rhino3dm
    document = rhino3dm.File3dm.Read(str(path))
    for layer in document.Layers:
        layer.Color = (*layer_color(layer.Name), 255)
        layer.Visible = not any(t in layer.Name for t in ("Centerlines", "CLASH REVIEW", "terrain_context"))
    for key, value in doc_tags.items():
        document.Strings[key] = str(value)
    styled = path.with_name(path.stem + '.styled.3dm')
    if not document.Write(str(styled), 7):
        raise OSError(f"Could not save styled model: {path}")
    styled.replace(path)


def generate(output):
    """Write four mesh models, a combined gallery, JSON and clash reports.

    ``output`` accepts a path or string. Native slab refinement is available
    separately through :mod:`civilpy.structural.rhino_box_slabs` in Rhino 8.
    Returns reports keyed by scenario ID. Existing generated files are replaced.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    gallery, reports = [], {}
    for index, inp in enumerate(SCENARIOS):
        kind = inp.scenario_id
        model = detailed_box_bridge_emit(inp)
        clashes = check_clearance(model.objects, PAIRS)
        report = {"inputs": asdict(inp), "status": "coordination example with unresolved details",
                  "limitations": LIMITATIONS, "checked_pairs": PAIRS,
                  "clash_count": len(clashes), "categories": dict(Counter(c.category for c in clashes)),
                  "clashes": [asdict(c) for c in clashes], "object_count": len(model.objects),
                  "bearing_count": len(model.of_type("bearing")), "notes": model.doc_tags}
        reports[kind] = report
        involved = {ident for c in clashes for ident in (c.first, c.second)}
        markers = tuple(EmitObject("polyline", kind+"::CLASH REVIEW", o.points,
                         {"bim.type": "clash_review", "bim.id": o.tags["bim.id"]+"-review"})
                        for o in model.objects if o.tags.get("bim.id") in involved)
        model = replace(model, objects=model.objects+markers)
        emit_to_3dm(model, output/(kind+".3dm"), mesh=True)
        style_file(output/(kind+".3dm"), model.doc_tags)
        payload = json.loads(emit_to_json(model))
        for layer in payload['layers']:
            payload['layers'][layer] = layer_color(layer)
        (output/(kind+".json")).write_text(json.dumps(payload), encoding="utf-8")
        (output/(kind+".clashes.json")).write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
        for o in model.objects:
            gallery.append(replace(o, points=tuple((x,y+index*90,z) for x,y,z in o.points)))
        print(f"{kind}: {len(model.objects)} objects; {len(clashes)} clashes; {report['bearing_count']} bearings", flush=True)
    combined = BridgeEmit(None, None, tuple(gallery), {"bim.units": "ft", "detail.limitations": " | ".join(LIMITATIONS)})
    emit_to_3dm(combined, output/"Box Bridge Detail Gallery.3dm", mesh=True)
    style_file(output/"Box Bridge Detail Gallery.3dm", combined.doc_tags)
    data = json.loads(emit_to_json(combined))
    for kind in reports:
        data['layers'].update(json.loads((output/(kind+'.json')).read_text())['layers'])
    (output/"gallery.json").write_text(json.dumps(data), encoding="utf-8")
    (output/"summary.json").write_text(json.dumps(reports, indent=2)+"\n", encoding="utf-8")
    return reports


def main(argv=None):
    """Generate the four documented coordination examples from the CLI."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('box_bridge_details'),
                        help='Output directory (default: ./box_bridge_details)')
    args = parser.parse_args(argv)
    generate(args.output)
    print('Portable mesh models generated. For native Rhino slabs, run '
          'civilpy.structural.rhino_box_slabs.refine(doc, output) in Rhino 8.')


if __name__ == '__main__':
    main()
