"""Prestressed concrete adjacent box-beam bridges in Rhino (stage **G9**, the
precast-girder companion to the steel line-girder pipeline in
:mod:`civilpy.structural.rhino_gdr`).

Box beams are a different structural system from the steel-girder pipeline:
full-length precast members that sit side by side (spacing = beam width, no
gap) rather than field-spliced curves needing shape transitions. This module
lays out a straight, zero-skew box-beam bridge from three inputs -- a
standard box designation (:data:`~civilpy.structural.odot.BOX_DESIGNATIONS`,
e.g. ``"CB27-48"``), a span, and a beam count -- and writes the geometry a
``BoxBeamLines`` Rhino command imports:

* one **girder-line curve** per beam (``gdr.kind=girder``, ``gdr.family=box``)
  so the line-girder-style downstream tooling can still find the framing;
* the true **box-beam solid**, built as four wall meshes (top/bottom flange,
  two webs) using the wall thickness read off PSBD-1-25 sheet 3
  (:data:`~civilpy.structural.odot.BOX_WALL_THICKNESS_IN`) -- a hollow tube,
  not a solid rectangle, though the void corners are drawn square rather than
  filleted (cosmetic simplification, same category as the steel pipeline's
  display W-shapes);
* a schematic **prestressing tendon** centerline per active strand row (2 in
  / 4 in / 6 in above the soffit, from the PSBDD-1-25 strand pattern) run the
  full beam length -- straight, since box beams debond rather than harp;
  a full per-strand model is a possible future refinement;
* transverse **diaphragms** at the PSBD-1-25 sheet 4/6 count and (for
  multiples) evenly-spaced stations between the end offsets
  (:func:`~civilpy.structural.odot.diaphragm_stations_ft`);
* **tie rods** at each diaphragm station, at the PSBD-1-25 tie-rod height
  (:data:`~civilpy.structural.odot.TIE_ROD`);
* a **bearing pad** footprint at each beam end, sized from the design's
  standard pad (:data:`~civilpy.structural.odot.BEARING_PADS`);
* an optional **composite topping slab**, when the box's design table calls
  for one, at the standard structural thickness plus wearing surface.

Skewed layouts are not yet supported (``skew_deg`` stays 0); the PSBD-1-25
skew rules for diaphragm/tie-rod offset (sheet 2/6) are a follow-up. This is
display geometry plus engineering tags, same as the deck/barrier modules; it
does not yet wire a box-beam bridge into the MIDAS payload builder (a
different structural idealization from the line-girder model).

``rhino3dm`` is an optional dependency imported lazily.
"""

#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

from __future__ import annotations

import uuid
from dataclasses import dataclass

from civilpy.structural.odot import (
    BEARING_PADS,
    BOX_FLANGE_THICKNESS_IN,
    BOX_WEB_THICKNESS_IN,
    COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN,
    COMPOSITE_SLAB_WEARING_SURFACE_IN,
    TIE_ROD,
    box_beam_design,
    box_section_properties,
    diaphragm_count,
    diaphragm_stations_ft,
)
from civilpy.structural.rhino_gdr import GTAG, _box_mesh, _fmt_num, _require_rhino3dm
from civilpy.structural.rhino_layers import (
    LAYER_BEARINGS, LAYER_BOX_BEAMS, LAYER_BRIDGE_DECK, LAYER_DIAPHRAGMS,
    LAYER_GIRDERS, LAYER_TENDONS, LAYER_TIE_RODS, ensure_layer,
)

#: Concrete unit weight (pcf) for the box-beam and topping-slab self-weight.
CONCRETE_PCF = 150.0
#: Cosmetic diaphragm thickness -- PSBD-1-25 gives the count and end offset
#: but not a thickness in the section carried here; this is a display value
#: only, not sourced from the drawing.
DIAPHRAGM_THICKNESS_IN = 8.0


@dataclass
class BoxBeamBridgeModel:
    """Summary of a generated box-beam bridge: what was placed and its
    engineering payload. Lengths in the units named; loads in klf."""

    box: str
    beam_type: str
    depth_in: float
    width_in: float
    span_ft: float
    n_beams: int
    bridge_width_ft: float
    n_strands: int
    bearing_type: str
    composite: bool
    self_weight_klf_per_beam: float
    #: ``diaphragm_count`` -- the INTERMEDIATE diaphragms only.  The bridge
    #: also has two end diaphragms, so ``n_diaphragm_objects`` is this + 2.
    n_diaphragms: int
    n_beam_solids: int
    n_tendons: int
    n_tie_rods: int
    n_bearing_pads: int
    n_diaphragm_objects: int
    n_slab: int = 0


def _tag_common(r3, layer_index, kind, **extra):
    a = r3.ObjectAttributes()
    a.LayerIndex = layer_index
    a.SetUserString(GTAG + "kind", kind)
    a.SetUserString(GTAG + "id", str(uuid.uuid4()))
    for k, v in extra.items():
        a.SetUserString(GTAG + k, v if isinstance(v, str) else _fmt_num(v))
    return a


def _add_layers(f, r3):
    return {
        "girder": ensure_layer(f, LAYER_GIRDERS),
        "beam": ensure_layer(f, LAYER_BOX_BEAMS),
        "tendon": ensure_layer(f, LAYER_TENDONS),
        "diaphragm": ensure_layer(f, LAYER_DIAPHRAGMS),
        "tie_rod": ensure_layer(f, LAYER_TIE_RODS),
        "bearing": ensure_layer(f, LAYER_BEARINGS),
        "slab": ensure_layer(f, LAYER_BRIDGE_DECK),
    }


def build_box_beams(*, out_path, box: str, span_ft: float, n_beams: int,
                    x0_ft: float = 0.0, y0_ft: float = 0.0,
                    concrete_pcf: float = CONCRETE_PCF,
                    unit_system=None) -> BoxBeamBridgeModel:
    """Lay out a straight, zero-skew adjacent box-beam bridge and write it to
    ``out_path`` (a ``.3dm`` the ``BoxBeamLines`` command imports).

    ``box`` is a standard designation from
    :data:`~civilpy.structural.odot.BOX_DESIGNATIONS` (e.g. ``"CB27-48"``,
    composite; or ``"B27-48"``, non-composite); ``span_ft`` must be one of
    that box's cataloged spans (:func:`~civilpy.structural.odot.box_beam_design`
    raises a ``KeyError`` naming the valid spans otherwise). Beams are placed
    edge to edge starting at ``(x0_ft, y0_ft)``, each spanning the full width
    (no gap, per "adjacent box beam"). Returns a :class:`BoxBeamBridgeModel`.
    """
    design = box_beam_design(box, int(span_ft))
    section = box_section_properties(design.depth)
    r3 = _require_rhino3dm()

    width_ft = section.width / 12.0
    depth_ft = design.depth / 12.0
    flange_ft = BOX_FLANGE_THICKNESS_IN / 12.0
    web_ft = BOX_WEB_THICKNESS_IN / 12.0
    bridge_width_ft = n_beams * width_ft
    composite = design.beam_type == "composite"
    self_weight_klf = section.area / 144.0 * concrete_pcf / 1000.0

    f = r3.File3dm()
    f.Settings.ModelUnitSystem = unit_system or r3.UnitSystem.Feet
    lay = _add_layers(f, r3)

    n_beam_solids = n_tendons = n_tie_rods = n_bearing_pads = 0
    strand_rows = ((2.0, design.strands_2in), (4.0, design.strands_4in),
                   (6.0, design.strands_6in))

    for i in range(n_beams):
        y_lo = y0_ft + i * width_ft
        y_hi = y_lo + width_ft
        y_c = (y_lo + y_hi) / 2.0
        x0, x1 = x0_ft, x0_ft + span_ft

        # ── girder-line curve (line-girder-style downstream compatibility) ─
        line = r3.LineCurve(r3.Point3d(x0, y_c, depth_ft),
                             r3.Point3d(x1, y_c, depth_ft))
        ga = r3.ObjectAttributes()
        ga.LayerIndex = lay["girder"]
        ga.SetUserString(GTAG + "kind", "girder")
        ga.SetUserString(GTAG + "id", str(uuid.uuid4()))
        ga.SetUserString(GTAG + "family", "box")
        ga.SetUserString(GTAG + "box", box)
        ga.SetUserString(GTAG + "beam_type", design.beam_type)
        ga.SetUserString(GTAG + "line", str(i + 1))
        f.Objects.AddCurve(line, ga)

        # ── box-beam solid: four wall meshes (hollow tube, square voids) ──
        for (yy0, yy1, zz0, zz1) in (
            (y_lo, y_hi, depth_ft - flange_ft, depth_ft),    # top flange
            (y_lo, y_hi, 0.0, flange_ft),                     # bottom flange
            (y_lo, y_lo + web_ft, flange_ft, depth_ft - flange_ft),  # left web
            (y_hi - web_ft, y_hi, flange_ft, depth_ft - flange_ft),  # right web
        ):
            ba = _tag_common(r3, lay["beam"], "box_beam",
                              box=box, depth=design.depth, line=str(i + 1))
            f.Objects.AddMesh(_box_mesh(r3, x0, x1, yy0, yy1, zz0, zz1), ba)
            n_beam_solids += 1

        # ── schematic tendon centerlines (one per active strand row) ──────
        for h_in, count in strand_rows:
            if count <= 0:
                continue
            z = h_in / 12.0
            ta = _tag_common(r3, lay["tendon"], "tendon",
                              **{"tendon.strands": count, "tendon.row": h_in,
                                 "line": str(i + 1)})
            f.Objects.AddCurve(
                r3.LineCurve(r3.Point3d(x0, y_c, z), r3.Point3d(x1, y_c, z)), ta)
            n_tendons += 1

        # ── bearing pads at each end ───────────────────────────────────────
        pad = BEARING_PADS[design.bearing_type]
        pad_l, pad_w, pad_t = pad.length / 12.0, pad.width / 12.0, pad.total_thickness / 12.0
        for x_end in (x0, x1):
            sign = 1.0 if x_end == x0 else -1.0
            pa = _tag_common(r3, lay["bearing"], "bearing_pad",
                              **{"bearing_pad.type": design.bearing_type,
                                 "line": str(i + 1)})
            f.Objects.AddMesh(_box_mesh(
                r3, x_end, x_end + sign * pad_l,
                y_c - pad_w / 2, y_c + pad_w / 2, -pad_t, 0.0), pa)
            n_bearing_pads += 1

    # ── diaphragms + tie rods (full bridge width, once per station) ───────
    n_diaphragm_objects = n_tie_rods_total = 0
    stations = diaphragm_stations_ft(span_ft, design.depth)
    tie_rod_z = TIE_ROD.vertical_position(design.depth) / 12.0
    diaphragm_t_ft = DIAPHRAGM_THICKNESS_IN / 12.0
    y_lo_all, y_hi_all = y0_ft, y0_ft + bridge_width_ft
    for x_d in stations:
        da = _tag_common(r3, lay["diaphragm"], "diaphragm",
                          **{"diaphragm.station": x_d})
        f.Objects.AddMesh(_box_mesh(
            r3, x_d - diaphragm_t_ft / 2, x_d + diaphragm_t_ft / 2,
            y_lo_all, y_hi_all, flange_ft, depth_ft - flange_ft), da)
        n_diaphragm_objects += 1

        ra = _tag_common(r3, lay["tie_rod"], "tie_rod",
                          **{"tie_rod.station": x_d,
                             "tie_rod.max_beams_per_rod": TIE_ROD.max_beams_per_rod,
                             "tie_rod.diameter": TIE_ROD.diameter})
        f.Objects.AddCurve(
            r3.LineCurve(r3.Point3d(x_d, y_lo_all, tie_rod_z),
                        r3.Point3d(x_d, y_hi_all, tie_rod_z)), ra)
        n_tie_rods_total += 1

    # ── optional composite topping slab ────────────────────────────────────
    n_slab = 0
    if composite:
        t_struct_ft = COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN / 12.0
        t_wear_ft = COMPOSITE_SLAB_WEARING_SURFACE_IN / 12.0
        sa = _tag_common(r3, lay["slab"], "deck",
                          **{"deck.t": COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN,
                             "deck.wearing_surface": COMPOSITE_SLAB_WEARING_SURFACE_IN})
        f.Objects.AddMesh(_box_mesh(
            r3, x0_ft, x0_ft + span_ft, y_lo_all, y_hi_all,
            depth_ft, depth_ft + t_struct_ft + t_wear_ft), sa)
        n_slab = 1

    if not f.Write(str(out_path), 7):
        raise IOError(f"could not write box-beam model to {out_path}")

    return BoxBeamBridgeModel(
        box=box, beam_type=design.beam_type, depth_in=design.depth,
        width_in=section.width, span_ft=span_ft, n_beams=n_beams,
        bridge_width_ft=bridge_width_ft, n_strands=design.n_strands,
        bearing_type=design.bearing_type, composite=composite,
        self_weight_klf_per_beam=self_weight_klf,
        n_diaphragms=diaphragm_count(span_ft), n_beam_solids=n_beam_solids,
        n_tendons=n_tendons, n_tie_rods=n_tie_rods_total,
        n_bearing_pads=n_bearing_pads, n_diaphragm_objects=n_diaphragm_objects,
        n_slab=n_slab)


def read_box_beam_model(path):
    """Read the ``gdr.kind=girder | box_beam | tendon | diaphragm | tie_rod |
    bearing_pad | deck`` objects back from a box-beam ``.3dm``: a list of
    dicts with ``kind``, ``id``, and an ``attrs`` map of every ``gdr.*`` tag
    on the object (numeric values as ``float`` where they parse). Round-trips
    :func:`build_box_beams` and mirrors what the ``BoxBeamLines`` importer
    carries."""
    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError(f"could not read 3dm file: {path}")
    kinds = {"girder", "box_beam", "tendon", "diaphragm", "tie_rod",
             "bearing_pad", "deck"}
    out = []
    for obj in f.Objects:
        us = dict(obj.Attributes.GetUserStrings() or {})
        kind = us.get(GTAG + "kind")
        if kind not in kinds:
            continue
        attrs = {}
        for k, v in us.items():
            if not k.startswith(GTAG) or k == GTAG + "kind" or k == GTAG + "id":
                continue
            key = k[len(GTAG):]
            try:
                attrs[key] = float(v)
            except ValueError:
                attrs[key] = v
        out.append({"kind": kind, "id": us.get(GTAG + "id", ""), "attrs": attrs})
    return out
