"""ODOT DS-1-92 Drip Strip — GHPython (Rhino 8, CPython 3) source.

Drop-in Grasshopper component for SCD DS-1-92 (rev. 07-15-22): the
stainless steel drip strips for structures with over-the-side drainage.
All engineering content comes from ``civilpy.structural.odot.drip_strip``;
this script only draws.

The strips are generated along one fascia edge running in +X, with the
top of deck at Z = 0 and the fascia face at Y = 0 (legs point toward -Y,
i.e. off the right/-Y edge; mirror or orient the output for the far
side).  Feed the bridge generator's deck edge length and its railing-post
stations to decorate an existing model.

Component inputs (Type Hint / Access in parentheses):
    length   (float, Item)  fascia length, ft
    railing  (str, Item)    "DBR-2-73" | "TST-1-99" | "TST-2-21"
    posts    (float, List)  railing post stations, ft (optional; upper
                            strips are placed only where given)
    bake     (bool, Item)   write display geometry to Site::DS-1-92
Outputs:
    strips  (Brep, List)   upper + lower strip solids (final 45-deg bend)
    report  (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

import math

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot import drip_strip as ds

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _strip_solid(run, root_z_ft, s):
    """One strip piece: the bent open profile, thickened to the sheet
    gage and extruded along +X over the run."""
    prof_in = ds.strip_profile_in(run.kind)
    x0 = run.start_ft * s
    pts = [rg.Point3d(x0, -h * s / 12.0, root_z_ft * s + v * s / 12.0)
           for h, v in prof_in]
    poly = rg.PolylineCurve(pts)
    vec = rg.Vector3d((run.end_ft - run.start_ft) * s, 0.0, 0.0)
    srf = rg.Surface.CreateExtrusion(poly, vec)
    if srf is None:
        return None
    t = ds.GAGE_THICKNESS_IN * s / 12.0
    solid = rg.Brep.CreateFromOffsetFace(
        srf.ToBrep().Faces[0], t, TOL, False, True)
    return solid or srf.ToBrep()


def _bake(breps):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Site::DS-1-92", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Site", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Site"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "DS-1-92"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(120, 120, 140)
        idx = doc.Layers.Add(lyr)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = idx
    n = 0
    for b in breps:
        doc.Objects.AddBrep(b, a)
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

strips = []

if not globals().get("length") or not globals().get("railing"):
    report = "Connect at least: length (ft) and railing " \
             "(DBR-2-73 / TST-1-99 / TST-2-21)."
else:
    s = _scale()
    post_list = tuple(float(x) for x in posts) if globals().get("posts") \
        else ()
    try:
        p = ds.placement(str(railing))
        runs = ds.drip_strip_runs(float(length), post_list, str(railing))
    except ValueError as exc:
        runs = None
        report = "INPUT ERROR: {}".format(exc)

    if runs:
        root_z = -p.root_depth_in / 12.0
        for run in runs:
            solid = _strip_solid(run, root_z, s)
            if solid:
                strips.append(solid)
        report_lines = [
            "ODOT DS-1-92 drip strips (rev. 07-15-22), one fascia edge",
            "Railing {}: upper strips {:g} in at {} posts, root {:g} in "
            "below deck surface".format(p.railing,
                                        p.upper_strip_length_in,
                                        len(post_list), p.root_depth_in),
            "Lower strip continuous {:g} ft; pay length (this edge) "
            "{:.1f} ft ({})".format(float(length),
                                    ds.pay_length_ft(runs), ds.PAY_ITEM),
            "Material: min {} gage ASTM A167 Type 304 stainless, mill "
            "finish".format(ds.MIN_GAGE),
            "Not modeled: perforations (1-1/2 in holes @ 4 in, view G-G), "
            "post-anchor field notching, box-beam spike fastening, splice "
            "butts.",
        ]
        if globals().get("bake"):
            n = _bake(strips)
            report_lines.append(
                "BAKED {} objects to Site::DS-1-92 (display only).".format(n))
        report = "\n".join(report_lines)
