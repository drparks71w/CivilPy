# r: civilpy
"""ODOT steel-girder bridge generator — GHPython (Rhino 8, CPython 3) source.

Successor to "ODOT - Steel Girder, Concrete Deck.gh": all engineering
decisions now come from civilpy (`bridge_layout.layout_bridge`), so the
component only turns the returned layout into Rhino geometry.  Deck
thickness + rebar mats follow ODOT BDM Figure 309-3, haunches BDM 309.3.5,
barriers the SCD catalog, and everything the MIDAS pipeline needs is
carried as gdr.* tags when baked.

Component inputs (Zoom in and add; Type Hint / Access in parentheses):
    spans           (float, List)  span lengths, ft
    girder_count    (int, Item)
    girder_spacing  (float, Item)  ft, c/c
    section_label   (str, Item)    e.g. "W36X150"
    overhang        (float, Item)  ft, cl fascia girder to deck edge
    railing         (str, Item)    SCD, e.g. "SBR-1-20" (optional)
    skew            (float, Item)  degrees from perpendicular (optional)
    haunch          (float, Item)  design haunch, in (optional, min 2.0)
    deck_thickness  (float, Item)  in; omit to use the BDM standard design
    bake            (bool, Item)   True = bake tagged model for the
                                   civilpy rhino_gdr -> MIDAS pipeline
Outputs:
    girders   (Brep, List)   solid girders (display)
    deck      (Brep, Item)   deck slab solid
    haunches  (Brep, List)
    barriers  (Brep, List)   simple barrier extrusions (placeholder profile)
    rebar     (Curve, List)  every deck bar, faithfully placed
    bearings  (Point3d, List)
    report    (str)

The unbaked outputs are plain geometry for preview; `bake=True` writes the
girder CENTERLINES and bearing points with their gdr.* user text (plus the
document-level gdr.deck_* strings) to the active document — that tagged
file is what `civilpy.structural.rhino_gdr` reads.  Solids are display
only, deliberately untagged, matching the plugin contract.

The deck is a closed crowned solid: the layout's ``deck_profile_yz``
cross-section (crowned top, parallel soffit, thickened overhangs) lofted
between the two skewed ends.  Girders, haunches, bearings, and both rebar
mats all hang from the crowned surface (transverse bars crank at the
crown).

Not yet modeled (reported, not silently ignored): drainage
(scuppers/drip strips), splices.
"""

import math

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.bridge_layout import (
    BridgeInput,
    deck_rebar_segments,
    layout_bridge,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    """Feet (layout units) -> current document units."""
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _i_profile_curve(section, plane, s_in):
    """Closed I-shape profile with true k-fillets on `plane` (section dims
    in inches scaled by s_in), improved from the original script."""
    d, bf = section.depth * s_in, section.flange_width * s_in
    tf, tw = section.flange_thickness * s_in, section.web_thickness * s_in
    r = max((section.fillet_k - section.flange_thickness) * s_in, 1e-4)
    hb, hw = bf / 2.0, tw / 2.0

    def P(u, v):
        return plane.PointAt(u, v - d / 2.0)  # centroid on the plane origin

    segs = []

    def line(a, b):
        segs.append(rg.LineCurve(a, b))

    def fillet(p_from, p_to, center_uv, bulge_uv):
        cu, cv = center_uv
        bu, bv = bulge_uv
        mid = P(cu + bu * r / math.sqrt(2), cv + bv * r / math.sqrt(2))
        segs.append(rg.Arc(p_from, mid, p_to).ToNurbsCurve())

    # right half going down, then mirror-ordered left half going up
    line(P(-hb, d), P(hb, d))
    line(P(hb, d), P(hb, d - tf))
    line(P(hb, d - tf), P(hw + r, d - tf))
    fillet(P(hw + r, d - tf), P(hw, d - tf - r), (hw + r, d - tf - r), (-1, 1))
    line(P(hw, d - tf - r), P(hw, tf + r))
    fillet(P(hw, tf + r), P(hw + r, tf), (hw + r, tf + r), (-1, -1))
    line(P(hw + r, tf), P(hb, tf))
    line(P(hb, tf), P(hb, 0))
    line(P(hb, 0), P(-hb, 0))
    line(P(-hb, 0), P(-hb, tf))
    line(P(-hb, tf), P(-(hw + r), tf))
    fillet(P(-(hw + r), tf), P(-hw, tf + r), (-(hw + r), tf + r), (1, -1))
    line(P(-hw, tf + r), P(-hw, d - tf - r))
    fillet(P(-hw, d - tf - r), P(-(hw + r), d - tf),
           (-(hw + r), d - tf - r), (1, 1))
    line(P(-(hw + r), d - tf), P(-hb, d - tf))
    line(P(-hb, d - tf), P(-hb, d))

    joined = rg.Curve.JoinCurves(segs, TOL, False)
    return joined[0] if joined and len(joined) == 1 else None


def _sweep_profile(profile, path):
    breps = rg.Brep.CreateFromSweep(path, profile, True, TOL)
    if breps:
        capped = breps[0].CapPlanarHoles(TOL)
        return capped or breps[0]
    return None


def _girder_solid(section, start, end, s):
    path = rg.LineCurve(start, end)
    tangent = path.TangentAtStart
    x_axis = rg.Vector3d.CrossProduct(rg.Vector3d.ZAxis, tangent)
    if not x_axis.Unitize():
        return None
    y_axis = rg.Vector3d.CrossProduct(tangent, x_axis)
    plane = rg.Plane(start, x_axis, y_axis)
    profile = _i_profile_curve(section, plane, s / 12.0)
    return _sweep_profile(profile, path) if profile else None


def _box_along(p0, p1, width, height, up=-1.0):
    """Axis-aligned-in-section box extruded from p0 to p1: `width` centered
    on the line, `height` extruded in +Z (up=1) or -Z (up=-1)."""
    run = p1 - p0
    side = rg.Vector3d.CrossProduct(rg.Vector3d.ZAxis, run)
    if not side.Unitize():
        return None
    a = p0 - side * (width / 2.0)
    profile = rg.Polyline([
        a, a + side * width,
        a + side * width + rg.Vector3d(0, 0, up * height),
        a + rg.Vector3d(0, 0, up * height), a,
    ]).ToNurbsCurve()
    return _sweep_profile(profile, rg.LineCurve(p0, p1))


def _deck_solid(layout, s):
    """Closed crowned deck: the layout's (y, z) section profile mapped onto
    each skewed end plane and lofted straight between them."""
    tan_skew = math.tan(math.radians(layout.inputs.skew_deg))
    prof = layout.deck_profile_yz()
    length = layout.total_length_ft
    ends = []
    for u in (0.0, length):
        pts = [rg.Point3d((u + y * tan_skew) * s, y * s, z * s)
               for y, z in prof]
        ends.append(rg.Polyline(pts + [pts[0]]).ToNurbsCurve())
    lofted = rg.Brep.CreateFromLoft(ends, rg.Point3d.Unset, rg.Point3d.Unset,
                                    rg.LoftType.Straight, False)
    if not lofted:
        return None
    capped = lofted[0].CapPlanarHoles(TOL)
    return capped or lofted[0]


def _bake(layout, seg_curves, s):
    doc = Rhino.RhinoDoc.ActiveDoc

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

    import System.Drawing as sd
    lay_lines = layer("Girders::Lines", sd.Color.FromArgb(40, 40, 40))
    lay_bear = layer("Girders::Bearings", sd.Color.FromArgb(0, 110, 200))
    lay_disp = layer("Girders::Display", sd.Color.FromArgb(160, 160, 160))

    def attrs(lay, tags=None):
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex = lay
        for k, v in (tags or {}).items():
            a.SetUserString(k, v)
        return a

    n = 0
    for g in layout.girders:
        doc.Objects.AddLine(
            rg.Line(_pt(g.start, s), _pt(g.end, s)), attrs(lay_lines, g.tags))
        n += 1
    for b in layout.bearings:
        doc.Objects.AddPoint(_pt(b.location, s), attrs(lay_bear, b.tags))
        n += 1
    for crv in seg_curves:
        doc.Objects.Add(crv.ToNurbsCurve() if hasattr(crv, "ToNurbsCurve")
                        else crv, attrs(lay_disp))
        n += 1
    for k, v in layout.doc_tags.items():
        doc.Strings.SetString(k, v)
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

girders, haunches, barriers, rebar, bearings = [], [], [], [], []
deck = None
report_lines = []

if not globals().get("spans") or not globals().get("section_label"):
    report = "Connect at least: spans, girder_count, girder_spacing, " \
             "section_label, overhang."
else:
    s = _scale()
    inp = BridgeInput(
        spans_ft=tuple(float(x) for x in spans),
        girder_count=int(girder_count),
        girder_spacing_ft=float(girder_spacing),
        girder_label=str(section_label),
        overhang_ft=float(overhang),
        railing=str(railing) if globals().get("railing") else "SBR-1-20",
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        design_haunch_in=float(haunch) if globals().get("haunch") else 2.0,
        deck_thickness_in=(float(deck_thickness)
                           if globals().get("deck_thickness") else None),
    )
    try:
        layout = layout_bridge(inp)
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        for g in layout.girders:
            solid = _girder_solid(layout.section, _pt(g.start, s),
                                  _pt(g.end, s), s)
            if solid:
                girders.append(solid)
        for h in layout.haunches:
            box = _box_along(_pt(h.start, s), _pt(h.end, s),
                             h.width_in * s / 12.0, h.depth_in * s / 12.0)
            if box:
                haunches.append(box)
        deck = _deck_solid(layout, s)
        for b in layout.barriers:
            if b.height_in and b.base_width_in:
                box = _box_along(_pt(b.line[0], s), _pt(b.line[1], s),
                                 b.base_width_in * s / 12.0,
                                 b.height_in * s / 12.0, up=1.0)
                if box:
                    barriers.append(box)
        segs = deck_rebar_segments(layout)
        rebar = [rg.Polyline([_pt(p, s) for p in x.points]).ToNurbsCurve()
                 for x in segs]
        bearings = [_pt(b.location, s) for b in layout.bearings]

        d = layout.standard_design
        report_lines += [
            "ODOT girder bridge: {} spans, {} girders @ {} ft, {}".format(
                len(inp.spans_ft), inp.girder_count, inp.girder_spacing_ft,
                inp.girder_label),
            "Effective deck span (9.7.2.3): {:.2f} ft".format(
                layout.effective_span_ft),
            "Deck: {} in total / {} in structural; overhang {} in".format(
                layout.deck.thickness_in, layout.deck.structural_thickness_in,
                layout.deck.overhang_thickness_in),
            ("Mats (BDM Fig. 309-3, eff span {} ft): trans top #{}@{}, "
             "bottom #{}@{}".format(d.effective_span_ft,
                                    d.transverse_top.size,
                                    d.transverse_top.spacing,
                                    d.transverse_bottom.size,
                                    d.transverse_bottom.spacing)
             if d else "Custom deck thickness: design mats per BDM 309.3.2 "
                       "(civilpy deck_strip_checks)"),
            "Haunch: {} in x girder flange (BDM 309.3.5)".format(
                inp.design_haunch_in),
            "Crown at y = {:.2f} ft, cross slope {:g}% (bars crank at the "
            "crown)".format(layout.crown_y_ft, inp.cross_slope_pct),
            "{} rebar segments generated".format(len(rebar)),
            "NOT modeled yet: drainage, splices.",
        ]
        if globals().get("bake"):
            n = _bake(layout, rebar, s)
            report_lines.append(
                "BAKED {} tagged objects + gdr.deck_* doc keys — file is "
                "readable by civilpy.structural.rhino_gdr.".format(n))
        report = "\n".join(report_lines)
