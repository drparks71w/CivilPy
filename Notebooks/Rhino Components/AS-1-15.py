"""ODOT AS-1-15 Reinforced Concrete Approach Slab — GHPython (Rhino 8,
CPython 3) source.

Drop-in Grasshopper component for SCD AS-1-15 (rev. 01-20-2023).  All
engineering content (the reinforcing-steel table, bar counts/lengths,
section geometry, anchor-bar rules) comes from
``civilpy.structural.odot.approach_slab``; placement, layers, and the
``bim.*``/``pay.*``/``rebar.*`` tagging come from
``civilpy.structural.rhino_approach_slab.approach_slab_emit``; this
script only draws.

NOTE on ``# r: civilpy``: intentionally absent.  That directive
pip-installs civilpy from PyPI into Rhino's ``site-envs`` cache, which
shadows the editable dev install.  While tracking the development
branch, install civilpy editable into Rhino's CPython instead; the
dev-reload block below makes a ``git pull`` take effect on the next
recompute.  Reinstate ``# r: civilpy>=X.Y.Z`` only for a pinned release.

Component inputs (Type Hint / Access, and the GH widget each wants):
    length     (float, Item)  slab length L, ft — the sheet tabulates
                              exactly 15/20/25/30, so feed from a
                              **Value List** (dropdown), not a slider
    width      (float, Item)  slab width W, ft (see the sheet's
                              width-dimension figure) — **Number Slider**
    skew       (float, Item)  skew, deg (optional, 0; < 60) — **Number
                              Slider**
    side       (str, Item)    "near" | "far" abutment (optional, near).
                              near = low-station end (slab runs
                              down-station from the bridge limit); far =
                              high-station end.  **Value List**
    alignment  (No Type Hint, Item)  optional
                              civilpy.transportation.alignment.Alignment
                              from an upstream component; places the slab
                              on the roadway centerline in world
                              coordinates
    station    (float, Item)  bridge-limit station, ft (required with
                              alignment) — **Number Slider / Panel**
    offset     (float, Item)  slab-center offset from the centerline, ft
                              right-positive (optional, 0; the width
                              always builds symmetrically about this
                              center) — **Number Slider**
    end_thickness (float, Item)  X at the abutment end, in (optional,
                              = T; never less than T) — **Number Slider**
    seat_length   (float, Item)  bearing on seat/backwall, in (optional,
                              9; sheet allows 6 to 12) — **Number Slider**
    backwall      (float, Item)  backwall thickness, in (optional, 14;
                              selects D801 vs D802 anchor bars) —
                              **Number Slider**
    bake       (bool, Item)   write tagged geometry to the
                              Deck::Approach Slab layers — **Button**
Outputs:
    slab    (Brep)        the approach slab solid
    rebar   (Curve list)  every bar centerline (A, B501, C, D801/D802)
    outline (Curve)       plan outline at the top of slab
    preview (Mesh list)   vertex-colored preview: the slab shaded light
                          blue, every bar an orange pipe at its true
                          tagged diameter (``rebar.dia_in``)
    report  (str)         design summary + pay-item rollup

Preview: the ``slab``/``rebar``/``outline`` outputs carry data for
downstream components but their default (red) previews are switched off
each solve; the ``preview`` meshes carry their colors themselves, so no
Custom Preview component is needed.  Colors come from
``rhino_layers.DEFAULT_COLORS``, so the on-canvas preview matches the
baked layers.  Set ``HIDE_DEFAULT_PREVIEWS = False`` below to get the
stock red previews back.

New params since the 2026-07 rebuild (add them to the component; the
script binds by name): inputs ``side``, ``alignment`` (No Type Hint),
``station``, ``offset``; output ``preview``.

Without an alignment the slab sits on a default due-north tangent with
the bridge limit at the origin (stations along +Y, transverse along
+X): the Front viewport looks up-station at the slab end (adjusting
``width`` grows it across the screen) and Right shows the longitudinal
section.  Baked objects carry full user text — the slab the ITEM 526
plan area, the anchor bars their ITEM 509 weights, and every bar its
``rebar.dia_in`` — so estimates and future clash/BIM checks read
straight from the saved document.
"""

import sys

import Rhino
import Rhino.Geometry as rg

# DEV RELOAD: drop cached civilpy modules so every recompute re-imports
# from the editable install -- a 'git pull' takes effect on the next
# solve with no Rhino restart. Remove (or guard) once running a pinned
# release instead of the development checkout.
for _name in [n for n in list(sys.modules) if n.startswith("civilpy")]:
    del sys.modules[_name]

from civilpy.structural.odot.approach_slab import ApproachSlabInput
from civilpy.structural.rhino_approach_slab import approach_slab_emit
from civilpy.structural.rhino_bim import pay_item_quantities
from civilpy.structural.rhino_layers import (
    DEFAULT_COLORS,
    LAYER_APPROACH_SLAB,
    LAYER_APPROACH_SLAB_REBAR,
)

TOL = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance

#: Preview colors track the baked layer colors (single source of truth).
SLAB_RGB = DEFAULT_COLORS[LAYER_APPROACH_SLAB]
REBAR_RGB = DEFAULT_COLORS[LAYER_APPROACH_SLAB_REBAR]
HIDE_DEFAULT_PREVIEWS = True


def _scale():
    """Feet (emit units) -> current document units."""
    return Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Feet, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _pt(p, s):
    return rg.Point3d(p[0] * s, p[1] * s, p[2] * s)


def _prism_brep(obj, s):
    """Loft the emit prism's loop along its (possibly sheared) vector."""
    loop = [_pt(p, s) for p in obj.points]
    a = rg.Polyline(loop + [loop[0]]).ToNurbsCurve()
    b = a.DuplicateCurve()
    b.Translate(rg.Vector3d(*[c * s for c in obj.vector]))
    lofted = rg.Brep.CreateFromLoft([a, b], rg.Point3d.Unset,
                                    rg.Point3d.Unset, rg.LoftType.Straight,
                                    False)
    if not lofted:
        return None
    return lofted[0].CapPlanarHoles(TOL) or lofted[0]


def _polyline_crv(obj, s):
    return rg.Polyline([_pt(p, s) for p in obj.points]).ToNurbsCurve()


def _monotone(mesh, rgb):
    """Stamp one color on every vertex; GH previews vertex-colored
    meshes in their own colors with no Custom Preview component."""
    import System.Drawing as sd
    mesh.VertexColors.CreateMonotoneMesh(sd.Color.FromArgb(*rgb[:3]))
    return mesh


def _slab_preview(brep):
    parts = rg.Mesh.CreateFromBrep(brep, rg.MeshingParameters.Default)
    if not parts:
        return None
    m = rg.Mesh()
    for p in parts:
        m.Append(p)
    return _monotone(m, SLAB_RGB)


def _bar_preview(crv, dia_in, s):
    """The bar as a pipe at its true diameter (the emit's rebar.dia_in)."""
    m = rg.Mesh.CreateFromCurvePipe(
        crv, dia_in / 24.0 * s, 6, 1, rg.MeshPipeCapStyle.Flat, True)
    return _monotone(m, REBAR_RGB) if m else None


def _hide_default_previews():
    """Keep slab/rebar/outline as data outputs but stop their stock red
    preview — the colored ``preview`` meshes replace it."""
    try:
        for p in ghenv.Component.Params.Output:
            if p.NickName in ("slab", "rebar", "outline"):
                p.Hidden = HIDE_DEFAULT_PREVIEWS
    except Exception:
        pass    # not running inside a GH component; nothing to hide


def _ensure_layer(doc, path, rgb):
    import System.Drawing as sd
    idx = doc.Layers.FindByFullPath(path, -1)
    if idx >= 0:
        return idx
    parent, accum = None, ""
    for name in path.split("::"):
        accum = name if not accum else accum + "::" + name
        idx = doc.Layers.FindByFullPath(accum, -1)
        if idx < 0:
            lyr = Rhino.DocObjects.Layer()
            lyr.Name = name
            if parent is not None:
                lyr.ParentLayerId = doc.Layers[parent].Id
            lyr.Color = sd.Color.FromArgb(*rgb[:3])
            idx = doc.Layers.Add(lyr)
        parent = idx
    return idx


def _bake(emit, geometry):
    doc = Rhino.RhinoDoc.ActiveDoc
    n = 0
    for obj, geom in zip(emit.objects, geometry):
        if geom is None:
            continue
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex = _ensure_layer(
            doc, obj.layer, DEFAULT_COLORS.get(obj.layer, (128, 128, 128)))
        for k, v in obj.tags.items():
            a.SetUserString(k, str(v))
        if isinstance(geom, rg.Brep):
            doc.Objects.AddBrep(geom, a)
        else:
            doc.Objects.AddCurve(geom, a)
        n += 1
    doc.Views.Redraw()
    return n


# ── main ──────────────────────────────────────────────────────────────────

slab, rebar, outline, preview = None, [], None, []
_hide_default_previews()

if not globals().get("length") or not globals().get("width"):
    report = "Connect at least: length (15/20/25/30 ft, use a Value " \
             "List) and width (ft). Optional: skew (deg), side " \
             "('near'|'far'), alignment (+ station, offset), " \
             "end_thickness (in), seat_length (in), backwall (in), bake."
else:
    s = _scale()
    inp = ApproachSlabInput(
        length_ft=float(length),
        width_ft=float(width),
        skew_deg=float(skew) if globals().get("skew") else 0.0,
        end_thickness_in=(float(end_thickness)
                          if globals().get("end_thickness") else None),
        seat_length_in=(float(seat_length)
                        if globals().get("seat_length") else 9.0),
        backwall_thickness_in=(float(backwall)
                               if globals().get("backwall") else 14.0),
    )
    try:
        emit = approach_slab_emit(
            inp,
            side=(str(side).strip().lower() if globals().get("side")
                  else "near"),
            alignment=globals().get("alignment"),
            station_ft=(float(station) if globals().get("station") is not None
                        else None),
            offset_ft=float(offset) if globals().get("offset") else 0.0,
        )
    except ValueError as exc:
        emit = None
        report = "INPUT ERROR: {}".format(exc)

    if emit:
        geometry = []
        for obj in emit.objects:
            if obj.kind == "prism":
                g = _prism_brep(obj, s)
                slab = g
                if g:
                    pm = _slab_preview(g)
                    if pm:
                        preview.append(pm)
            else:
                g = _polyline_crv(obj, s)
                if obj.tags.get("bim.type") == "rebar":
                    rebar.append(g)
                    pm = _bar_preview(
                        g, float(obj.tags.get("rebar.dia_in", 0.625)), s)
                    if pm:
                        preview.append(pm)
                elif obj.tags.get("bim.id") == "APS-OUTLINE":
                    outline = g
            geometry.append(g)

        d = emit.layout.design
        counts = {}
        for bar in emit.layout.bars:
            counts[bar.mark] = counts.get(bar.mark, 0) + 1
        sched = ", ".join("{} x {}".format(v, k)
                          for k, v in sorted(counts.items()))
        lines = [
            "ODOT AS-1-15 approach slab (rev. 01-20-2023), {} abutment"
            .format(emit.side),
            "L = {:g} ft, T = {:g} in, W = {:g} ft, skew = {:g} deg".format(
                d.length_ft, d.thickness_in, inp.width_ft, inp.skew_deg),
            "Bars: " + sched,
            "A bars {} @ K = {:g} in; B501 bottom @ N = {:g} in "
            "(5 sp. @ 6 in at bridge end); B501 top & C bars @ 6 in".format(
                d.a_bar_mark, d.a_bar_spacing_in, d.b501_bottom_spacing_in),
            "Anchor bars: {} x {:.2f} ft (paid under Item 509)".format(
                emit.layout.anchor_mark, emit.layout.anchor_length_ft),
        ]
        if "aps.station_ft" in emit.doc_tags:
            lines.append("Placed at sta. {} ft, offset {} ft".format(
                emit.doc_tags["aps.station_ft"],
                emit.doc_tags["aps.offset_ft"]))
        for item, rec in pay_item_quantities(emit).items():
            lines.append("  {}  {:,.1f} {}  {}".format(
                item, rec["qty"], rec["unit"], rec["desc"]))
        lines += list(emit.layout.notes[2:])
        if globals().get("bake"):
            n = _bake(emit, geometry)
            lines.append("BAKED {} tagged objects to Deck::Approach Slab "
                         "layers.".format(n))
        report = "\n".join(lines)
