#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""BrIM emit layer for prestressed I-beam bridges (PSID-1-13).

The prestressed-I counterpart of :mod:`~civilpy.structural.rhino_box_bim`
(work-plan phase 6): the executed design line from
:func:`~civilpy.structural.ps_i_beam_pipeline.ps_i_beam_line_checks`
drives the drawn geometry — the strand rows are the *designed* pattern,
not a free parameter.

* each beam as one true-profile I-prism (:func:`~civilpy.structural.odot
  .ps_i_beam.ps_i_beam_profile` — tapered flanges, no fillet radii),
  tagged ``bim.type = ps_i_beam`` carrying the 515 member pay item
  (strands, embedded sole plates, and anchorage steel are included in
  the member per sheet 10);
* a schematic strand-row polyline per occupied row of the designed
  pattern, with the row's end-debonded count in its tags;
* 2 in design haunches over each top flange (BDM 309.3.5) and the CIP
  deck slab (511 superstructure concrete);
* cast-in-place intermediate diaphragms at the sheet 5 stations
  (midspan up to 80 ft, quarter points beyond), one 515 intermediate-
  diaphragm count per station-bay;
* elastomeric bearing pads under each beam end (516 item);
* the ``gdr.*`` girder centerline per beam (``gdr.family = ps_i``) so
  the line-girder tooling reads the model back.

Drawn by the same ``draw_bim_emit.py`` driver and read back by the same
:func:`~civilpy.structural.rhino_bim.read_bim_quantities` as the steel
and box slices.  Coordinates are feet: X spans 0..span, Y across the
beams (beam 1 at ``y = overhang``), Z = 0 at the beam soffit.

Like the box slice: skew is not yet supported, the deck is drawn flat
(no crown), and no railing is emitted here — place one with the barrier
tooling.  End/pier diaphragms belong to the substructure phase.
"""

from __future__ import annotations

from dataclasses import dataclass

from civilpy.structural import bim
from civilpy.structural.odot.ps_i_beam import (
    DIAPHRAGM_FC_KSI,
    ps_i_beam_profile,
    i_beam_diaphragm_stations_ft,
)
from civilpy.structural.ps_i_beam_pipeline import (
    PSIBeamLineChecks,
    ps_i_beam_line_checks,
)
from civilpy.structural.rhino_bim import (
    BEARING_PLIES,
    BEARING_PLY_IN,
    BEARING_SIDE_IN,
    BridgeEmit,
    EmitObject,
)
from civilpy.structural.rhino_layers import (
    LAYER_BEARINGS,
    LAYER_BRIDGE_DECK,
    LAYER_DIAPHRAGMS,
    LAYER_GIRDERS,
    LAYER_HAUNCHES,
    LAYER_TENDONS,
)

CONCRETE_PCF = 150.0
#: Display thickness for the CIP intermediate diaphragms (the project
#: plans size them; sheet 9 details the connection) — cosmetic only.
DIAPHRAGM_THICKNESS_IN = 10.0


@dataclass(frozen=True)
class PSIBridgeInput:
    """One prestressed I-beam bridge on the PSID-1-13 standard.

    ``section`` is a PSID-1-13 section name (``"WF48-49"``,
    ``"AASHTO Type 3"``, ...).  Beam 1's centerline sits at
    ``y = overhang_ft``; the deck edges run ``overhang_ft`` beyond each
    exterior beam centerline."""

    section: str
    span_ft: float
    n_beams: int
    spacing_ft: float
    overhang_ft: float = 2.5
    deck_t_in: float = 8.5
    haunch_in: float = 2.0
    skew_deg: float = 0.0
    fci_ksi: float = 4.0
    fc_ksi: float = 5.5
    barrier_klf: float = 0.0
    n_strands: int | None = None


def _rect_prism(layer: str, x0: float, x1: float, y0: float, y1: float,
                z0: float, z1: float, tags: dict) -> EmitObject:
    """Axis-aligned rectangular prism: base loop at ``z0`` extruded up."""
    return EmitObject(
        kind="prism", layer=layer,
        points=((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)),
        vector=(0.0, 0.0, z1 - z0), tags=tags)


def ps_i_bridge_emit(inp: PSIBridgeInput, *,
                     checks: PSIBeamLineChecks | None = None,
                     concrete_pcf: float = CONCRETE_PCF) -> BridgeEmit:
    """Build the tagged BrIM geometry for one prestressed I-beam bridge.

    ``checks`` short-circuits the design step with an already-executed
    :func:`~civilpy.structural.ps_i_beam_pipeline.ps_i_beam_line_checks`
    result (it must match the input's section/span/spacing); otherwise
    the line is designed here.  Raises ``ValueError`` for a skewed
    layout (not yet supported) or when no passing pattern exists."""
    if inp.skew_deg != 0.0:
        raise ValueError("skewed PS I-beam layouts are not supported yet")
    if checks is None:
        checks = ps_i_beam_line_checks(
            inp.section, inp.span_ft, inp.n_beams,
            spacing_ft=inp.spacing_ft, deck_t_in=inp.deck_t_in,
            haunch_in=inp.haunch_in, n_strands=inp.n_strands,
            fci_ksi=inp.fci_ksi, fc_ksi=inp.fc_ksi,
            barrier_klf=inp.barrier_klf)
    design = checks.design
    sec = design.section

    span = float(inp.span_ft)
    depth_ft = sec.depth_in / 12.0
    haunch_ft = inp.haunch_in / 12.0
    deck_t_ft = inp.deck_t_in / 12.0
    z_deck0 = depth_ft + haunch_ft
    width_ft = (inp.n_beams - 1) * inp.spacing_ft + 2.0 * inp.overhang_ft
    beam_cy = sec.area_in2 / 144.0 * span / 27.0
    fc_psi = inp.fc_ksi * 1000.0

    objects: list[EmitObject] = []
    doc_tags = {
        "bim.units": "ft",
        "bim.family": "ps_i",
        "bim.section": inp.section,
        "bim.span_ft": f"{span:g}",
        "bim.n_beams": str(inp.n_beams),
        "bim.spacing_ft": f"{inp.spacing_ft:g}",
        "bim.overhang_ft": f"{inp.overhang_ft:g}",
        "bim.deck_t_in": f"{inp.deck_t_in:g}",
        "bim.n_strands": str(design.n_strands),
        "bim.n_debonded": str(design.n_debonded),
        "gdr.family": "ps_i",
    }
    objects.append(EmitObject(
        kind="point", layer=LAYER_GIRDERS, points=((0.0, 0.0, 0.0),),
        tags={"bim.type": "bridge", "bim.id": "BRIDGE", **doc_tags}))

    profile = ps_i_beam_profile(inp.section)

    # strand rows of the designed pattern; the debonded strands are the
    # earliest-filled (outermost bottom-row) locations
    debonded = set(design.pattern[:design.n_debonded])
    rows: dict[float, dict[str, int]] = {}
    for y, z in design.pattern:
        row = rows.setdefault(z, {"n": 0, "db": 0})
        row["n"] += 1
        if (y, z) in debonded:
            row["db"] += 1

    pad_side_ft = BEARING_SIDE_IN / 12.0
    pad_t_ft = BEARING_PLIES * BEARING_PLY_IN / 12.0

    for i in range(inp.n_beams):
        line = i + 1
        y_c = inp.overhang_ft + i * inp.spacing_ft
        bid = f"PSI{line}"

        # gdr contract: the centerline the line-girder tooling consumes
        objects.append(EmitObject(
            kind="polyline", layer=LAYER_GIRDERS,
            points=((0.0, y_c, depth_ft), (span, y_c, depth_ft)),
            tags={"gdr.kind": "girder", "gdr.family": "ps_i",
                  "gdr.section": inp.section, "gdr.line": str(line),
                  "bim.id": bid}))

        # the beam itself: true-profile prism extruded down the span
        loop = tuple((0.0, y_c + y / 12.0, z / 12.0) for y, z in profile)
        objects.append(EmitObject(
            kind="prism", layer=LAYER_GIRDERS, points=loop,
            vector=(span, 0.0, 0.0),
            tags=bim.ps_i_beam_tags(
                bid, section=inp.section, depth_in=sec.depth_in,
                span_ft=span, fc_psi=fc_psi, n_strands=design.n_strands,
                n_debonded=design.n_debonded, concrete_cy=beam_cy,
                count=1)))

        for z_in, row in sorted(rows.items()):
            objects.append(EmitObject(
                kind="polyline", layer=LAYER_TENDONS,
                points=((0.0, y_c, z_in / 12.0), (span, y_c, z_in / 12.0)),
                tags=bim.tendon_tags(
                    f"{bid}-ROW{z_in:g}", strands=row["n"], row_in=z_in,
                    debonded=row["db"] or None)))

        # 2 in design haunch over the top flange (BDM 309.3.5)
        half_tf = sec.top_flange_width_in / 24.0
        objects.append(_rect_prism(
            LAYER_HAUNCHES, 0.0, span, y_c - half_tf, y_c + half_tf,
            depth_ft, z_deck0,
            bim.haunch_tags(
                f"HNCH-{bid}", depth_in=inp.haunch_in,
                width_in=sec.top_flange_width_in, fc_psi=4500.0,
                volume_cy=(sec.top_flange_width_in / 12.0)
                * haunch_ft * span / 27.0)))

        for x_end, sign, end in ((0.0, 1.0, "S"), (span, -1.0, "E")):
            objects.append(_rect_prism(
                LAYER_BEARINGS, x_end, x_end + sign * pad_side_ft,
                y_c - pad_side_ft / 2.0, y_c + pad_side_ft / 2.0,
                -pad_t_ft, 0.0,
                bim.bearing_tags(
                    f"{bid}-BRG-{end}",
                    fixity="fixed" if end == "S" else "expansion",
                    total_thickness_in=BEARING_PLIES * BEARING_PLY_IN)))

    # ── CIP intermediate diaphragms between beams (sheet 5 stations),
    #    hanging from the deck soffit down to the bottom-flange taper ──────
    t_dia_ft = DIAPHRAGM_THICKNESS_IN / 12.0
    z_dia0 = 0.25 * depth_ft
    for k, x_d in enumerate(i_beam_diaphragm_stations_ft(span), start=1):
        for b in range(inp.n_beams - 1):
            y0 = inp.overhang_ft + b * inp.spacing_ft
            objects.append(_rect_prism(
                LAYER_DIAPHRAGMS, x_d - t_dia_ft / 2.0, x_d + t_dia_ft / 2.0,
                y0, y0 + inp.spacing_ft, z_dia0, z_deck0,
                bim.diaphragm_tags(
                    f"DIA-{k}-B{b + 1}",
                    thickness_in=DIAPHRAGM_THICKNESS_IN,
                    fc_psi=DIAPHRAGM_FC_KSI * 1000.0,
                    item="515E30000", count=1)))

    # ── CIP deck slab (flat; the crowned deck belongs to the layout
    #    integration, same as the box slice's topping) ─────────────────────
    objects.append(_rect_prism(
        LAYER_BRIDGE_DECK, 0.0, span, 0.0, width_ft,
        z_deck0, z_deck0 + deck_t_ft,
        bim.deck_tags(
            "DECK", thickness_in=inp.deck_t_in, slope_pct=0.0,
            crown_offset_ft=0.0, fc_psi=4500.0,
            volume_cy=span * width_ft * deck_t_ft / 27.0)))

    return BridgeEmit(inputs=inp, layout=None, objects=tuple(objects),
                      doc_tags=doc_tags)
