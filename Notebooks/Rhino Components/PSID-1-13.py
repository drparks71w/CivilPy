"""ODOT PSID-1-13 Prestressed Concrete I-Beam — GHPython (Rhino 8,
CPython 3) source.

Drop-in Grasshopper component for SCD PSID-1-13 (rev. 07-18-2025): a
simplified I-beam solid (straight-line profile, no bulb/fillet radii)
for one of the six standard sections. All engineering content comes from
``civilpy.structural.odot.ps_i_beam``; this script only draws. Strand
pattern, rebar, and end-block details are cataloged as notes only.

Component inputs (Type Hint / Access in parentheses):
    section  (str,   Item)  "AASHTO Type 2", "AASHTO Type 3",
                            "AASHTO Type 4", "Modified AASHTO Type 4 (60in)",
                            "Modified AASHTO Type 4 (66in)", or
                            "Modified AASHTO Type 4 (72in)"
    length   (float, Item)  beam length, ft
    bake     (bool,  Item)  write display geometry to
                            Superstructure::PSID-1-13
Outputs:
    beam    (Brep, Item)  beam solid
    report  (str)

Baked geometry is display-only and carries no gdr.* tags.
"""

"""
# //TODO - Add # r: civilpy
- Didn't Generate a preview
- One of the most complicated to generate, used test values "AASHTO Type 3", length=60.00, bake=true
- No prestressing strands or details shown like rebar.
- Uses default layer, needs to be in the correct superstructure -> girders -> rebar or similar 
- Needs to be able to interact with deck (integral)
- Needs to have section type and strand details to be able to communicate w/ Midas
- Needs shipping holes, extra rebar along debonded length of strand, etc.
- Need to be able to design diaphragms between the girders
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.odot.ps_i_beam import layout_ps_i_beam

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance


def _scale():
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Inches, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _beam_solid(profile, length_ft, s):
    poly = rg.Polyline([rg.Point3d(p[0] * s, 0.0, p[1] * s) for p in profile]
                       + [rg.Point3d(profile[0][0] * s, 0.0, profile[0][1] * s)]
                       ).ToNurbsCurve()
    ft_to_in = 12.0
    ext = rg.Extrusion.Create(poly, length_ft * ft_to_in * s, True)
    return ext.ToBrep() if ext else None


def _bake(objs):
    doc = Rhino.RhinoDoc.ActiveDoc
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath("Superstructure::PSID-1-13", -1)
    if idx < 0:
        parent = doc.Layers.FindByFullPath("Superstructure", -1)
        if parent < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = "Superstructure"
            parent = doc.Layers.Add(lyr)
        lyr = Rhino.DocObjects.Layer()
        lyr.Name = "PSID-1-13"
        lyr.ParentLayerId = doc.Layers[parent].Id
        lyr.Color = sd.Color.FromArgb(40, 40, 40)
        idx = doc.Layers.Add(lyr)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = idx
    n = 0
    for o in objs:
        if o is None:
            continue
        doc.Objects.AddBrep(o, a)
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

beam = None

if not globals().get("section") or not globals().get("length"):
    report = "Connect: section (str, e.g. 'AASHTO Type 2'), length (ft). " \
             "Optional: bake."
else:
    s = _scale()
    try:
        layout = layout_ps_i_beam(str(section), float(length))
    except ValueError as exc:
        layout = None
        report = "INPUT ERROR: {}".format(exc)

    if layout:
        beam = _beam_solid(layout.profile, layout.length_ft, s)

        report_lines = [
            "ODOT PSID-1-13 prestressed I-beam (rev. 07-18-2025)",
        ] + list(layout.notes)
        if globals().get("bake"):
            n = _bake([beam])
            report_lines.append(
                "BAKED {} objects to Superstructure::PSID-1-13 (display "
                "only).".format(n))
        report = "\n".join(report_lines)
