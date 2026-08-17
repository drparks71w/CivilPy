#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""BrIM emit layer for prestressed adjacent box-beam bridges.

The :mod:`~civilpy.structural.rhino_box_beam` legacy writer ported to the
transport-neutral emit architecture: the same
PSBD-1-25 / PSBDD-1-25 standard-design content —

* box members as four wall prisms each (hollow tube, square-drawn void
  corners), every part tagged ``bim.type = box_beam`` with the beam id;
  one part per beam carries the 515 member pay item (strands, tie rods,
  and precast diaphragms are included in the member);
* a schematic strand-row polyline per active row of the PSBDD-1-25
  pattern (2 / 4 / 6 in above the soffit — straight, boxes debond rather
  than harp);
* transverse diaphragms and tie rods at the standard stations;
* standard bearing pads under each beam end (516 item);
* the composite topping slab when the design line calls for one
  (511 superstructure concrete);
* the ``gdr.*`` girder centerline per beam (``gdr.family = box``) so the
  ``BoxBeamLines`` importer and line-girder tooling still work.

Drawn by the same ``draw_bim_emit.py`` driver and read back by the same
:func:`~civilpy.structural.rhino_bim.read_bim_quantities` as the steel
slice.  Coordinates are feet: X spans 0..span, Y across the beams
(beam 1 edge at y = 0), Z = 0 at the box soffit.

Skewed layouts (up to the standard's 30 deg cap) shear the plan by
``y * tan(skew)``: beam ends, bearings and the topping edge follow the
skewed support lines, and the diaphragm / tie-rod lines run parallel to
the supports — the tie rods must pass straight through every beam, which
is exactly why PSBD-1-25 widens the solid diaphragm block on the bias
(``solid_diaphragm_block_in``).  Because the shear leaves each section's
length along X unchanged, every emitted quantity is identical to the
square bridge's.  No railing is emitted — the barrier family on boxes
differs from the deck-girder SBR standard.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from civilpy.structural import bim
from civilpy.structural.odot import (
    BEARING_PADS,
    BOX_MAX_SKEW_DEG,
    BOX_FLANGE_THICKNESS_IN,
    BOX_WEB_THICKNESS_IN,
    COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN,
    COMPOSITE_SLAB_WEARING_SURFACE_IN,
    TIE_ROD,
    box_beam_design,
    box_section_properties,
    diaphragm_stations_ft,
)
from civilpy.structural.rhino_bim import BridgeEmit, EmitObject
from civilpy.structural.rhino_layers import (
    LAYER_BEARINGS,
    LAYER_BOX_BEAMS,
    LAYER_BRIDGE_DECK,
    LAYER_DIAPHRAGMS,
    LAYER_GIRDERS,
    LAYER_TENDONS,
    LAYER_TIE_RODS,
)

CONCRETE_PCF = 150.0
#: Display thickness for the precast diaphragms (PSBD-1-25 gives count and
#: stations but no thickness in the carried section) — cosmetic only.
DIAPHRAGM_THICKNESS_IN = 8.0


@dataclass(frozen=True)
class BoxBridgeInput:
    """One adjacent box-beam bridge on the ODOT standard designs.

    ``box`` is a PSBDD-1-25 designation (``"CB27-48"`` composite /
    ``"B27-48"`` non-composite); ``span_ft`` must be one of that box's
    cataloged spans.  Beams sit edge to edge (adjacent), beam 1 at
    ``y = 0``."""

    #: PSBDD-1-25 box designation: ``"CB27-48"`` composite /
    #: ``"B27-48"`` non-composite -- a key of the PSBD span tables in
    #: :mod:`civilpy.structural.odot.box_beam_design`.
    box: str
    span_ft: float
    n_beams: int
    skew_deg: float = 0.0
    fc_psi: float = 6000.0


def _rect_prism(layer: str, x0: float, x1: float, y0: float, y1: float,
                z0: float, z1: float, tags: dict,
                shear: float = 0.0) -> EmitObject:
    """Rectangular prism: base loop at ``z0`` extruded up.  A non-zero
    ``shear`` (``tan`` of the skew angle) offsets each corner's X by
    ``y * shear``, turning the plan rectangle into the parallelogram a
    skew-sawn member actually is; the length along X — and therefore the
    volume — is unchanged."""
    return EmitObject(
        kind="prism", layer=layer,
        points=((x0 + y0 * shear, y0, z0), (x1 + y0 * shear, y0, z0),
                (x1 + y1 * shear, y1, z0), (x0 + y1 * shear, y1, z0)),
        vector=(0.0, 0.0, z1 - z0), tags=tags)


def box_beam_bridge_emit(inp: BoxBridgeInput, *,
                         concrete_pcf: float = CONCRETE_PCF) -> BridgeEmit:
    """Build the tagged BrIM geometry for one adjacent box-beam bridge.

    Raises ``KeyError`` (naming the valid spans) when ``span_ft`` is not
    a cataloged design for ``box``, and ``ValueError`` for a skew beyond
    the standard's 30 deg cap."""
    if abs(inp.skew_deg) > BOX_MAX_SKEW_DEG:
        raise ValueError(
            f"skew {inp.skew_deg:g} deg exceeds the PSBD-1-25 limit of "
            f"{BOX_MAX_SKEW_DEG:g} deg")
    shear = math.tan(math.radians(inp.skew_deg))
    design = box_beam_design(inp.box, int(inp.span_ft))
    section = box_section_properties(design.depth)
    composite = design.beam_type == "composite"

    width_ft = section.width / 12.0
    depth_ft = design.depth / 12.0
    flange_ft = BOX_FLANGE_THICKNESS_IN / 12.0
    web_ft = BOX_WEB_THICKNESS_IN / 12.0
    span = float(inp.span_ft)
    bridge_width_ft = inp.n_beams * width_ft
    beam_cy = section.area / 144.0 * span / 27.0

    objects: list[EmitObject] = []
    doc_tags = {
        "bim.units": "ft",
        "bim.family": "box",
        "bim.box": inp.box,
        "bim.beam_type": design.beam_type,
        "bim.span_ft": f"{span:g}",
        "bim.n_beams": str(inp.n_beams),
        "bim.composite": str(composite).lower(),
        "bim.skew_deg": f"{inp.skew_deg:g}",
        "gdr.family": "box",
    }
    objects.append(EmitObject(
        kind="point", layer=LAYER_BOX_BEAMS, points=((0.0, 0.0, 0.0),),
        tags={"bim.type": "bridge", "bim.id": "BRIDGE", **doc_tags}))

    strand_rows = ((2.0, design.strands_2in), (4.0, design.strands_4in),
                   (6.0, design.strands_6in))
    pad = BEARING_PADS[design.bearing_type]
    pad_l, pad_w = pad.length / 12.0, pad.width / 12.0
    pad_t = pad.total_thickness / 12.0

    for i in range(inp.n_beams):
        line = i + 1
        y_lo = i * width_ft
        y_hi = y_lo + width_ft
        y_c = (y_lo + y_hi) / 2.0
        bid = f"BB{line}"

        x_c = y_c * shear                 # this beam's skew offset
        # gdr contract: the centerline the BoxBeamLines importer consumes
        objects.append(EmitObject(
            kind="polyline", layer=LAYER_GIRDERS,
            points=((x_c, y_c, depth_ft), (span + x_c, y_c, depth_ft)),
            tags={"gdr.kind": "girder", "gdr.family": "box",
                  "gdr.box": inp.box, "gdr.beam_type": design.beam_type,
                  "gdr.line": str(line), "bim.id": bid}))

        # hollow tube: top/bottom flange + both webs; the top flange
        # carries the member count (one per beam)
        walls = (
            ("top_flange", y_lo, y_hi, depth_ft - flange_ft, depth_ft, 1),
            ("bottom_flange", y_lo, y_hi, 0.0, flange_ft, None),
            ("left_web", y_lo, y_lo + web_ft, flange_ft,
             depth_ft - flange_ft, None),
            ("right_web", y_hi - web_ft, y_hi, flange_ft,
             depth_ft - flange_ft, None),
        )
        for part, yy0, yy1, zz0, zz1, count in walls:
            objects.append(_rect_prism(
                LAYER_BOX_BEAMS, 0.0, span, yy0, yy1, zz0, zz1,
                bim.box_beam_tags(
                    f"{bid}-{part.upper()}", box=inp.box,
                    depth_in=design.depth, beam_type=design.beam_type,
                    part=part, span_ft=span, fc_psi=inp.fc_psi,
                    n_strands=design.n_strands,
                    concrete_cy=beam_cy if count else None, count=count),
                shear=shear))

        for h_in, n_strands in strand_rows:
            if n_strands <= 0:
                continue
            z = h_in / 12.0
            objects.append(EmitObject(
                kind="polyline", layer=LAYER_TENDONS,
                points=((x_c, y_c, z), (span + x_c, y_c, z)),
                tags=bim.tendon_tags(f"{bid}-ROW{h_in:g}",
                                     strands=n_strands, row_in=h_in)))

        for x_end, sign, end in ((0.0, 1.0, "S"), (span, -1.0, "E")):
            objects.append(_rect_prism(
                LAYER_BEARINGS, x_end, x_end + sign * pad_l,
                y_c - pad_w / 2.0, y_c + pad_w / 2.0, -pad_t, 0.0,
                bim.bearing_tags(f"{bid}-BRG-{end}", fixity="expansion",
                                 total_thickness_in=pad.total_thickness),
                shear=shear))

    t_dia = DIAPHRAGM_THICKNESS_IN / 12.0
    tie_z = TIE_ROD.vertical_position(design.depth) / 12.0
    for k, x_d in enumerate(diaphragm_stations_ft(span, design.depth),
                            start=1):
        objects.append(_rect_prism(
            LAYER_DIAPHRAGMS, x_d - t_dia / 2.0, x_d + t_dia / 2.0,
            0.0, bridge_width_ft, flange_ft, depth_ft - flange_ft,
            bim.diaphragm_tags(f"DIA-{k}",
                               thickness_in=DIAPHRAGM_THICKNESS_IN,
                               fc_psi=inp.fc_psi, pay=False),
            shear=shear))
        objects.append(EmitObject(
            kind="polyline", layer=LAYER_TIE_RODS,
            points=((x_d, 0.0, tie_z),
                    (x_d + bridge_width_ft * shear, bridge_width_ft, tie_z)),
            tags=bim.tie_rod_tags(f"TIE-{k}", diameter_in=TIE_ROD.diameter,
                                  station_ft=x_d)))

    if composite:
        t_top = (COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN
                 + COMPOSITE_SLAB_WEARING_SURFACE_IN) / 12.0
        objects.append(_rect_prism(
            LAYER_BRIDGE_DECK, 0.0, span, 0.0, bridge_width_ft,
            depth_ft, depth_ft + t_top, shear=shear,
            tags=
            bim.deck_tags(
                "TOPPING",
                thickness_in=COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN
                + COMPOSITE_SLAB_WEARING_SURFACE_IN,
                slope_pct=0.0, crown_offset_ft=0.0, fc_psi=4500.0,
                volume_cy=span * bridge_width_ft * t_top / 27.0)))

    return BridgeEmit(inputs=inp, layout=None, objects=tuple(objects),
                      doc_tags=doc_tags)
