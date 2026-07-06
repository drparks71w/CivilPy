"""ODOT PCB-91 Portable Concrete Barrier — GHPython (Rhino 8, CPython 3)
source.

Drop-in Grasshopper component for SCD PCB-91 (rev. 07-17-2020).  All
engineering content comes from
``civilpy.structural.odot.portable_barrier`` (geometry) and the
``bridge_railing`` catalog (crash test levels); this script only draws.

The run is generated along +X with the deck surface at Z = 0 and the
barrier centered on Y = 0.

Component inputs (Type Hint / Access in parentheses):
    segments        (int, Item)    number of segments in the run
    segment_length  (float, Item)  10 or 12 ft (optional, 10)
    joint_gap       (float, Item)  in, 0 to 1.75 (optional, 0.25 closed)
    anchored        (bool, Item)   True = show anchor-hole markers and
                                   report the TL-4 anchored configuration
    bake            (bool, Item)   write display geometry to SCD::PCB-91
Outputs:
    barriers (Brep, List)     one solid per segment (lifting slot cut)
    profile  (Curve, Item)    the NJ-shape section at the run start
    anchors  (Point3d, List)  anchor-hole centers on the deck (if anchored)
    report   (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot import portable_barrier as pb

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _profile_curve(x_ft, s):
    pts = [rg.Point3d(x_ft * s, -x * s / 12.0, y * s / 12.0)
           for x, y in pb.profile_points_in()]
    pts.append(pts[0])
    return rg.PolylineCurve(pts)


def _segment_solid(seg, s):
    prof = _profile_curve(seg.start_ft, s)
    vec = rg.Vector3d(seg.length_ft * s, 0.0, 0.0)
    srf = rg.Surface.CreateExtrusion(prof, vec)
    if srf is None:
        return None
    brep = srf.ToBrep().CapPlanarHoles(TOL) or srf.ToBrep()
    # drainage / lifting slot, centered along the segment
    cx = (seg.start_ft + seg.end_ft) / 2.0 * s
    w = pb.SLOT_WIDTH_IN * s / 12.0
    h = pb.SLOT_HEIGHT_IN * s / 12.0
    ln = pb.SLOT_LENGTH_IN * s / 12.0
    slot = rg.Box(rg.Plane.WorldXY,
                  rg.Interval(cx - ln / 2.0, cx + ln / 2.0),
                  rg.Interval(-w / 2.0, w / 2.0),
                  rg.Interval(-h * 0.01, h)).ToBrep()
    cut = rg.Brep.CreateBooleanDifference([brep], [slot], TOL)
    return cut[0] if cut and len(cut) == 1 else brep


def _bake(breps, curves, pts):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("SCD::PCB-91", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("SCD", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "SCD"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "PCB-91"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(150, 150, 150)
        idx = doc.Layers.Add(lyr)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = idx
    n = 0
    for b in breps:
        doc.Objects.AddBrep(b, a)
        n += 1
    for c in curves:
        doc.Objects.AddCurve(c, a)
        n += 1
    for p in pts:
        doc.Objects.AddPoint(p, a)
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

barriers, anchors = [], []
profile = None

if not globals().get("segments"):
    report = "Connect at least: segments (count). Optional: " \
             "segment_length (10/12 ft), joint_gap (in), anchored, bake."
else:
    s = _scale()
    seg_len = float(segment_length) if globals().get("segment_length") \
        else 10.0
    gap = float(joint_gap) if globals().get("joint_gap") is not None \
        else pb.CLOSED_JOINT_GAP_IN
    try:
        run = pb.barrier_run(int(segments), seg_len, gap)
    except ValueError as exc:
        run = None
        report = "INPUT ERROR: {}".format(exc)

    if run:
        for seg in run:
            solid = _segment_solid(seg, s)
            if solid:
                barriers.append(solid)
        profile = _profile_curve(0.0, s)
        if globals().get("anchored"):
            y = (pb.BASE_WIDTH_IN / 2.0 - 5.0) * s / 12.0
            for seg in run:
                for st in pb.anchor_hole_stations_ft(seg_len):
                    x = (seg.start_ft + st) * s
                    anchors.append(rg.Point3d(x, -y, 0.0))
                    anchors.append(rg.Point3d(x, y, 0.0))
        tl = "TL-4 (fully anchored, traffic side)" \
            if globals().get("anchored") else "TL-3 (unanchored)"
        report_lines = [
            "ODOT PCB-91 portable concrete barrier (rev. 07-17-2020)",
            "{} segments x {:g} ft, joint gap {:g} in -> run {:.2f} ft"
            .format(len(run), seg_len, gap, pb.run_length_ft(run)),
            "NJ shape {:g} in tall x {:g} in base; NCHRP 350 {}".format(
                pb.HEIGHT_IN, pb.BASE_WIDTH_IN, tl),
            "Joints: 3/4 in hinge bars + 1-1/4 in H.S. bolt; fully open "
            "({:g} in max gap) before tightening".format(
                pb.OPEN_JOINT_MAX_GAP_IN),
            "Anchors: 1 in H.S. bolts in 1-1/4 in holes @ 2'-0\" c/c, "
            "min embed {:g} in, grout 705.20".format(pb.ANCHOR_MIN_EMBED_IN),
            "Not modeled: hinge-bar loops and joint hardware, #5 bar "
            "loops @ 12 in, top/end 3/4 in chamfers on segment ends, "
            "permissible 10 in / 1 in radii, PCB-BXX-350 markings.",
        ]
        if globals().get("bake"):
            n = _bake(barriers, [profile] if profile else [], anchors)
            report_lines.append(
                "BAKED {} objects to SCD::PCB-91 (display only).".format(n))
        report = "\n".join(report_lines)
