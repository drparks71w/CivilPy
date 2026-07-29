#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""L1 verification of the ODOT standard box-beam designs.

The PSBDD-1-25 tables are pre-engineered designs; this module is the
pure-Python gate that *re-derives* the governing checks for one design
line — the box-beam analog of the steel line-girder envelope:

* HL-93 demands from the same :func:`~civilpy.structural.girder_pipeline
  .girder_line_envelope` influence-line machinery the steel slice uses,
  distributed with the **adjacent-box** factors (LRFD 4.6.2.2.2b/3c,
  type "g" cross-section) — torsion constant from the thin-wall closed
  section;
* prestress per the tabulated strand pattern: elastic shortening
  (5.9.3.2.3a) + the approximate lump-sum time-dependent loss (5.9.3.3).
  The transfer check assumes **every strand fully bonded** at the
  transfer length — conservative for the longest catalog spans, where
  the standard drawing debonds strands near the ends (a D/C slightly
  over 1.0 on transfer tension there reproduces exactly the condition
  debonding exists to fix, not a defect in the tabulated design);
* concrete stress checks at transfer (5.9.2.3.1) and service
  (5.9.2.3.2, Service III tension with the 0.8 live-load factor);
* Strength I flexural resistance (5.6.3) against the factored envelope;
* release/erection camber passed through from the design line (the
  sheet's own tabulated values).

Units: kip / inch / ksi internally; spans and uniform loads enter in
feet and klf.  Simple spans only (the PSBD standard's scope).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural.aashto.lrfd.distribution import (
    moment_df_interior_box,
    shear_df_interior_box,
)
from civilpy.structural.aashto.lrfd.prestressed import (
    ps_approximate_longterm_loss,
    ps_elastic_shortening_loss,
    ps_flexural_resistance,
    ps_service_compression_check,
    ps_service_tension_check,
    ps_transfer_compression_check,
    ps_transfer_tension_check,
)
from civilpy.structural.girder_pipeline import girder_line_envelope
from civilpy.structural.odot import (
    BOX_FLANGE_THICKNESS_IN,
    BOX_WEB_THICKNESS_IN,
    COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN,
    COMPOSITE_SLAB_WEARING_SURFACE_IN,
    box_beam_design,
    box_section_properties,
)
from civilpy.structural.odot.box_beam_design import strand_group_height_in

F_PU_KSI = 270.0
F_PJ_KSI = 0.75 * F_PU_KSI       #: jacking stress, low-relaxation (5.9.2.2)
CONCRETE_KCF = 0.150
TOPPING_FC_KSI = 4.5             #: PSBD cast-in-place topping strength


def box_torsion_constant_in4(depth_in: float, width_in: float = 48.0,
                             web_in: float = BOX_WEB_THICKNESS_IN,
                             flange_in: float = BOX_FLANGE_THICKNESS_IN
                             ) -> float:
    """St. Venant torsion constant of the closed box (thin-wall,
    C4.6.2.2.1-3): ``J = 4 A0^2 / sum(s/t)`` with the shear-flow path on
    the wall midlines, webs and flanges at their own thicknesses.  Bredt
    is conservative here -- these walls are thick relative to the cell, and
    an exact St. Venant solve runs ~10-15% higher."""
    b0 = width_in - web_in
    d0 = depth_in - flange_in
    return 4.0 * (b0 * d0) ** 2 / (2.0 * d0 / web_in + 2.0 * b0 / flange_in)


def _ec_ksi(fc_ksi: float) -> float:
    """Concrete modulus (ksi), 57000*sqrt(f'c psi) convention — the same
    one the pier/cap modules use."""
    return 1820.0 * math.sqrt(fc_ksi)


@dataclass(frozen=True)
class BoxBeamLineChecks:
    """Everything :func:`box_beam_line_checks` derives for one interior
    beam of one PSBDD-1-25 design line.  Moments in kip-ft; stresses in
    ksi (compression positive); ``checks`` values are
    :class:`~civilpy.structural.aashto.lrfd.core.CheckResult`."""

    design: object
    df_moment: float
    df_shear: float
    midspan_moments: dict = field(default_factory=dict)
    losses: dict = field(default_factory=dict)
    stresses: dict = field(default_factory=dict)
    checks: dict = field(default_factory=dict)
    camber_release_in: float = 0.0
    camber_erection_in: float = 0.0

    @property
    def all_ok(self) -> bool:
        return all(c.ok for c in self.checks.values())

    def summary(self) -> str:
        d = self.design
        lines = [f"{d.box} @ {d.span} ft ({d.beam_type}), "
                 f"{d.n_strands} strands, e = {d.e_beam:g} in:",
                 f"  DF moment {self.df_moment:.3f} / shear "
                 f"{self.df_shear:.3f} (adjacent box, 4.6.2.2.2b/3c)",
                 f"  losses: ES {self.losses['elastic_shortening']:.1f} + "
                 f"LT {self.losses['longterm']:.1f} ksi -> "
                 f"f_pe = {self.losses['f_pe']:.1f} ksi"]
        for name, chk in self.checks.items():
            ratio = (chk.demand / (chk.phi * chk.capacity)
                     if chk.demand is not None and chk.capacity else 0.0)
            lines.append(f"  {'PASS' if chk.ok else 'FAIL'}  {name}: "
                         f"D/C = {ratio:.2f} ({chk.article})")
        lines.append(f"  camber: {self.camber_release_in:g} in release, "
                     f"{self.camber_erection_in:g} in erection (tabulated)")
        return "\n".join(lines)


@dataclass(frozen=True)
class BoxBeamDeadLoads:
    """Per-beam uniform dead loads (klf) for an adjacent box-beam bridge,
    split into the LRFD load cases and traceable to the BDM article that
    sets each one.

    ``dc1`` acts on the bare beam (the beam itself plus a wet CIP deck),
    ``dc2`` on the composite section (barriers, railings) and ``dw`` is
    the wearing-surface case that takes the LRFD 3.4.1 gamma of 1.50
    rather than 1.25.
    """

    beam: float = 0.0          #: beam self weight, klf
    deck: float = 0.0          #: CIP deck incl. monolithic wearing surface
    barrier: float = 0.0       #: railing / barrier share
    asphalt: float = 0.0       #: asphalt wearing surface in place today
    fws: float = 0.0           #: future wearing surface allowance
    sources: dict = field(default_factory=dict)

    @property
    def dc1(self) -> float:
        return self.beam + self.deck

    @property
    def dc2(self) -> float:
        return self.barrier

    @property
    def dw(self) -> float:
        return self.asphalt + self.fws

    def summary(self) -> str:
        rows = [("beam", self.beam), ("deck", self.deck),
                ("barrier", self.barrier), ("asphalt", self.asphalt),
                ("FWS", self.fws)]
        lines = [f"  {n:<9}{w:7.4f} klf   {self.sources.get(n, '')}"
                 for n, w in rows if w]
        return "\n".join([*lines,
                          f"  {'DC1':<9}{self.dc1:7.4f} klf   (beam + deck, "
                          f"on the non-composite section)",
                          f"  {'DC2':<9}{self.dc2:7.4f} klf",
                          f"  {'DW':<9}{self.dw:7.4f} klf"])


def box_beam_dead_loads(box: str, span_ft: float, n_beams: int, *,
                        barrier_klf: float = 0.0,
                        fws_ksf: float | None = None,
                        asphalt_in: float | None = None,
                        deck_in: float | None = None,
                        composite: bool | None = None) -> BoxBeamDeadLoads:
    """The BDM's dead loads for one interior beam, in klf.

    The wearing surface is **not** a free choice -- BDM 309.1 ties it to
    whether the beam is composite:

    * composite (a ``CB`` design): a 6 in CIP deck, of which the top 1 in
      is the monolithic wearing surface that 309.1.A excludes from the
      composite section but not from the load.  No asphalt.
    * non-composite (a ``B`` design): no deck; a 3 in minimum asphalt
      concrete wearing surface (309.1.B), 8 in maximum (308.2.3.3), at
      the BDM 909.A unit weight of **145 pcf** -- not LRFD's 140.

    Both get the BDM 303.1.2 future wearing surface of 0.060 ksf on top,
    which the manual states unconditionally; pass ``fws_ksf=0.0`` for the
    two cases that exempt it (temporary structures, BDM 501, and the dead
    load used for shop camber, BDM 308.2.2.1.f).

    ``barrier_klf`` is the bridge total and is shared equally across the
    beams, which is the standard's own assumption for adjacent units and
    what BDM 308.2.2.1.f endorses for camber.  Deck and wearing-surface
    loads are computed on each beam's own 4 ft width, so a deck
    overhanging the fascia beams (up to 8 in per side, BDM 308.2.3.3.c)
    is not included -- add it to ``barrier_klf`` if you carry it.
    """
    from civilpy.structural.odot import (
        BDM_ASPHALT_MAX_IN, BDM_ASPHALT_MIN_IN, BDM_ASPHALT_PCF,
        BDM_CONCRETE_PCF, BDM_FUTURE_WEARING_SURFACE_KSF,
    )

    design = box_beam_design(box, int(span_ft))
    sec = box_section_properties(design.depth)
    if composite is None:
        composite = design.beam_type == "composite"
    width_ft = sec.width / 12.0
    fws_ksf = (BDM_FUTURE_WEARING_SURFACE_KSF if fws_ksf is None
               else float(fws_ksf))

    src = {"beam": f"{sec.area:g} in^2 x {BDM_CONCRETE_PCF:g} pcf "
                   f"(BDM 909.B)",
           "FWS": f"{fws_ksf:g} ksf x {width_ft:g} ft (BDM 303.1.2)"}
    loads = {"beam": sec.area / 144.0 * BDM_CONCRETE_PCF / 1000.0,
             "fws": fws_ksf * width_ft}

    if composite:
        if deck_in is None:
            deck_in = (COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN
                       + COMPOSITE_SLAB_WEARING_SURFACE_IN)
        loads["deck"] = width_ft * deck_in / 12.0 * BDM_CONCRETE_PCF / 1000.0
        src["deck"] = (
            f"{deck_in:g} in x {width_ft:g} ft x {BDM_CONCRETE_PCF:g} pcf "
            f"({COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN:g} in structural + "
            f"{COMPOSITE_SLAB_WEARING_SURFACE_IN:g} in monolithic WS, "
            f"BDM 308.2.3.3.c / 309.1.A)")
        if asphalt_in:
            raise ValueError(
                f"BDM 309.1.B allows an asphalt wearing surface only on "
                f"non-composite prestressed box beams; {box} at {span_ft:g} ft "
                f"is a composite design, which takes the 1 in monolithic "
                f"concrete wearing surface of 309.1.A instead")
    else:
        if asphalt_in is None:
            asphalt_in = BDM_ASPHALT_MIN_IN
        if asphalt_in and not (BDM_ASPHALT_MIN_IN <= asphalt_in
                               <= BDM_ASPHALT_MAX_IN):
            raise ValueError(
                f"asphalt wearing surface {asphalt_in:g} in is outside the "
                f"BDM range for a non-composite box beam bridge: "
                f"{BDM_ASPHALT_MIN_IN:g} in minimum (BDM 309.1.B) to "
                f"{BDM_ASPHALT_MAX_IN:g} in maximum (BDM 308.2.3.3)")
        loads["asphalt"] = (width_ft * asphalt_in / 12.0
                            * BDM_ASPHALT_PCF / 1000.0)
        src["asphalt"] = (f"{asphalt_in:g} in x {width_ft:g} ft x "
                          f"{BDM_ASPHALT_PCF:g} pcf (BDM 309.1.B, 909.A)")
        if deck_in:
            raise ValueError(
                f"{box} at {span_ft:g} ft is a non-composite design and "
                f"carries no CIP deck; pass composite=True to override")

    if barrier_klf:
        src["barrier"] = (f"{barrier_klf:g} klf bridge total / {n_beams} "
                          f"beams (BDM 308.2.2.1.f)")
    return BoxBeamDeadLoads(
        beam=loads["beam"], deck=loads.get("deck", 0.0),
        barrier=barrier_klf / n_beams, asphalt=loads.get("asphalt", 0.0),
        fws=loads["fws"], sources=src)


def structural_model_from_box(box: str, span_ft: float, n_beams: int, *,
                              ties: bool = True, dead_loads: bool = True,
                              shear_keys: bool = True,
                              deck: bool | None = None,
                              barrier_klf: float = 0.0,
                              fws_klf: float | None = None,
                              fws_ksf: float | None = None,
                              asphalt_in: float | None = None,
                              deck_in: float | None = None,
                              fc_ksi: float = 5.5,
                              mesh_ft: float = 5.0):
    """Build the :class:`~civilpy.structural.structural_model
    .StructuralModel` hub for an adjacent box-beam bridge — the MIDAS
    spoke: one line of beam elements per box, transverse ties at the
    diaphragm stations, the grouted shear key between each pair of boxes,
    the composite deck, and the BDM dead loads.

    **Vertical datum: z = 0 is the top of the beams.**  Every section
    rides the default center-center offset, so each node line sits at its
    own section's centroid — girders at ``Yb - D``, shear keys at their
    own centroid, the deck at its mid-surface — and the assembly lines up
    in a rendered view without any section offsets to keep in sync.

    Geometry
        ``mesh_ft`` sets the target longitudinal segment length.  The
        diaphragm stations are always nodes; this subdivides between them,
        which both resolves the moving-load influence lines and gives the
        deck plates a sane aspect ratio.  Pass ``mesh_ft=0`` for the
        diaphragm stations alone.

    Shear keys (``shear_keys``)
        A longitudinal beam element line at each joint carrying the actual
        grout cross-section from
        :func:`~civilpy.structural.psc_section.shear_key_shape` — about
        48 in^2 on a 27 in box, 2 1/2 in wide, so it reads clearly in a
        non-hidden view instead of hiding inside the beams.  It is tied to
        the boxes each side by the transverse ties, which are split at the
        key rather than run past it: that is the physical load path (tie
        rod through the diaphragm, grout key in vertical shear) and it
        needs no element type beyond ``BEAM``.  The key's own longitudinal
        stiffness is ~0.25% of one box's, so it does not meaningfully
        stiffen the span — it is there to be seen and to carry shear.

    Deck (``deck``, defaults to on for a composite design)
        The 5 in **structural** thickness of the BDM 308.2.3.3.c deck as
        plate elements at their mid-surface, rigid-linked to every girder
        node in all 6 DOF — full composite action, and the deck's own
        concrete modulus rather than a transformed width.  The 1 in
        monolithic wearing surface is deliberately *not* in the plates:
        BDM 309.1.A excludes it from the composite section.  It is in the
        loads.

        .. warning::
           The deck plates carry **stiffness only**.  Their weight is in
           the ``DC1`` beam loads, where it belongs — the deck is wet when
           it is placed, so the bare beam carries it.  Do not add a
           self-weight load case on top of this or the deck is counted
           twice.  This is a single-stage idealization: for the transfer
           and service stress checks, which need the load on the section
           that was there at the time, use :func:`box_beam_line_checks`.

    Dead loads (``dead_loads``)
        From :func:`box_beam_dead_loads` — see there for the BDM articles.
        ``fws_klf`` is accepted for backward compatibility as a bridge
        total in klf; prefer ``fws_ksf``, which defaults to the BDM
        303.1.2 value of 0.060 ksf and needs no deck-width bookkeeping.
    """
    from civilpy.structural.psc_section import (
        shape_centroid_in, shear_key_shape)
    from civilpy.structural.structural_model import StructuralModel, Units

    design = box_beam_design(box, int(span_ft))
    sec = box_section_properties(design.depth)
    composite = design.beam_type == "composite"
    span = float(span_ft)
    width_ft = sec.width / 12.0
    depth_in = float(design.depth)
    j = box_torsion_constant_in4(design.depth, sec.width)
    if deck is None:
        deck = composite
    if deck and not composite:
        raise ValueError(
            f"{box} at {span:g} ft is a non-composite design (BDM 309.1.B "
            f"puts asphalt on it, not a CIP deck); pass deck=False")

    fc_psi = 1000.0 * float(fc_ksi)
    stations = _stations_ft(span, design.depth, mesh_ft)

    # z = 0 at top of beam; each node line sits at its section's centroid
    z_girder = (sec.yb - depth_in) / 12.0
    model = StructuralModel(units=Units(force="kips", length="ft"))
    grid: dict[tuple[int, int], str] = {}
    beam_elems: dict[int, list] = {}
    for b in range(n_beams):
        y_c = (b + 0.5) * width_ft
        for i, st in enumerate(stations):
            grid[(b, i)] = model.add_node(
                st, y_c, z_girder, label=f"BB{b + 1}_S{i}").id
        elems = []
        for i in range(len(stations) - 1):
            e = model.add_element(
                grid[(b, i)], grid[(b, i + 1)], role="girder",
                midas_type="BEAM", section=box,
                material=f"PS-{fc_psi:.0f}psi")
            e.metadata.update({
                "gdr.line": str(b + 1), "gdr.family": "box",
                "sect.kind": "psc", "sect.family": "box",
                "sect.designation": box,
                "matl.fc_psi": fc_psi,
                "matl.unit_wt_pcf": _bdm_concrete_pcf(),
                "section.area_in2": sec.area, "section.i_in4": sec.i,
                "section.j_in4": j})
            elems.append(e.id)
        beam_elems[b] = elems
        model.add_restraint(grid[(b, 0)], fix_x=True, fix_y=True,
                            fix_z=True).preset = "fixed"
        model.add_restraint(grid[(b, len(stations) - 1)], fix_x=False,
                            fix_y=True, fix_z=True).preset = "expansion"

    # ── grouted shear keys, one line per joint ────────────────────────────
    key_grid: dict[tuple[int, int], str] = {}
    if shear_keys and n_beams > 1:
        key_shape = shear_key_shape(box)
        z_key = (shape_centroid_in(key_shape)[1] - depth_in) / 12.0
        key_name = key_shape.name
        for b in range(n_beams - 1):
            y_j = (b + 1) * width_ft                  # the joint centerline
            for i, st in enumerate(stations):
                key_grid[(b, i)] = model.add_node(
                    st, y_j, z_key, label=f"KEY{b + 1}_S{i}").id
            for i in range(len(stations) - 1):
                e = model.add_element(
                    key_grid[(b, i)], key_grid[(b, i + 1)], role="shear-key",
                    midas_type="BEAM", section=key_name,
                    material="GROUT-5000psi")
                e.metadata.update({
                    "gdr.kind": "shear-key", "sect.kind": "psc",
                    "sect.family": "shear-key", "sect.designation": box,
                    "matl.fc_psi": 5000.0,
                    "matl.unit_wt_pcf": _bdm_concrete_pcf()})

    # ── transverse ties, split at the key so it picks up vertical shear ───
    if ties:
        tie_meta = {"gdr.kind": "tie", "sect.kind": "rect",
                    "sect.width_in": 6.0, "sect.height_in": depth_in - 11.0,
                    "matl.fc_psi": fc_psi,
                    "matl.unit_wt_pcf": _bdm_concrete_pcf()}
        tie_at = _tie_station_indices(stations, span, design.depth)
        for b in range(n_beams - 1):
            for i in tie_at:
                waypoints = ([grid[(b, i)], key_grid[(b, i)],
                              grid[(b + 1, i)]] if key_grid
                             else [grid[(b, i)], grid[(b + 1, i)]])
                for a, c in zip(waypoints, waypoints[1:]):
                    e = model.add_element(a, c, role="diaphragm",
                                          midas_type="BEAM",
                                          section=f"TIE-{box}",
                                          material=f"PS-{fc_psi:.0f}psi")
                    e.metadata.update(tie_meta)

    # ── composite deck: plates at mid-surface, rigid-linked to the boxes ──
    if deck:
        t_struct = (COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN if deck_in is None
                    else float(deck_in) - COMPOSITE_SLAB_WEARING_SURFACE_IN)
        z_deck = (t_struct / 2.0) / 12.0
        # a deck column over every girder line AND every joint, so the keys
        # tie into the slab they are cast against instead of dangling
        columns = [round(0.5 * k * width_ft, 6)
                   for k in range(2 * n_beams + 1)]
        col_of_y = {y: c for c, y in enumerate(columns)}
        deck_grid: dict[tuple[int, int], str] = {}
        for c, y in enumerate(columns):
            for i, st in enumerate(stations):
                deck_grid[(c, i)] = model.add_node(
                    st, y, z_deck, label=f"DK{c}_S{i}").id
        for c in range(len(columns) - 1):
            for i in range(len(stations) - 1):
                e = model.add_element(
                    deck_grid[(c, i)], deck_grid[(c, i + 1)],
                    midas_type="PLATE", role="deck",
                    section=f"DECK-{t_struct:g}in", material="Deck-4500psi",
                    nodes=[deck_grid[(c, i)], deck_grid[(c, i + 1)],
                           deck_grid[(c + 1, i + 1)], deck_grid[(c + 1, i)]])
                e.metadata["matl.unit_wt_pcf"] = _bdm_concrete_pcf()
        for b in range(n_beams):
            c = col_of_y[round((b + 0.5) * width_ft, 6)]
            for i in range(len(stations)):
                model.add_rigid_link(grid[(b, i)], [deck_grid[(c, i)]],
                                     dof="111111")
        for b in range(n_beams - 1):
            if not key_grid:
                break
            c = col_of_y[round((b + 1) * width_ft, 6)]
            for i in range(len(stations)):
                model.add_rigid_link(deck_grid[(c, i)], [key_grid[(b, i)]],
                                     dof="111111")
    elif key_grid:
        # no deck to hang from: the keys and tie rods ARE the transverse
        # load path on a non-composite adjacent box bridge, so the grout
        # bears against both beam faces at every station
        for b in range(n_beams - 1):
            for i in range(len(stations)):
                for other in (grid[(b, i)], grid[(b + 1, i)]):
                    e = model.add_element(other, key_grid[(b, i)],
                                          role="diaphragm", midas_type="BEAM",
                                          section=f"KEYBRG-{box}",
                                          material="GROUT-5000psi")
                    e.metadata.update({
                        "gdr.kind": "key-contact", "sect.kind": "rect",
                        "sect.width_in": 2.0 * _psbd_recess_in(),
                        "sect.height_in": depth_in - 11.0,
                        "matl.fc_psi": 5000.0,
                        "matl.unit_wt_pcf": _bdm_concrete_pcf()})

    if dead_loads:
        w = box_beam_dead_loads(
            box, span, n_beams, barrier_klf=barrier_klf,
            fws_ksf=(fws_klf / n_beams / width_ft if fws_ksf is None
                     and fws_klf is not None else fws_ksf),
            asphalt_in=asphalt_in,
            deck_in=deck_in, composite=composite)
        for elems in beam_elems.values():
            for eid in elems:
                model.add_beam_load(eid, -w.dc1, case="DC1")
                if w.dc2:
                    model.add_beam_load(eid, -w.dc2, case="DC2")
                if w.dw:
                    model.add_beam_load(eid, -w.dw, case="DW")

    return model


def _bdm_concrete_pcf() -> float:
    from civilpy.structural.odot import BDM_CONCRETE_PCF

    return BDM_CONCRETE_PCF


def _psbd_recess_in() -> float:
    from civilpy.structural.odot import KEYWAY_RECESS_DEPTH_IN

    return KEYWAY_RECESS_DEPTH_IN


def _stations_ft(span: float, depth_in: float, mesh_ft: float) -> list[float]:
    """Longitudinal node stations: the diaphragm stations, subdivided to
    roughly ``mesh_ft``."""
    from civilpy.structural.odot import diaphragm_stations_ft

    key = sorted(set(round(s, 6) for s in
                     [0.0, *diaphragm_stations_ft(span, depth_in), span]))
    if not mesh_ft or mesh_ft <= 0:
        return key
    out: list[float] = []
    for a, b in zip(key, key[1:]):
        n = max(1, int(round((b - a) / float(mesh_ft))))
        out.extend(round(a + (b - a) * k / n, 6) for k in range(n))
    out.append(key[-1])
    return sorted(set(out))


def _tie_station_indices(stations: list[float], span: float,
                         depth_in: float) -> list[int]:
    """Indices into ``stations`` of the interior diaphragm stations."""
    from civilpy.structural.odot import diaphragm_stations_ft

    want = {round(s, 6) for s in diaphragm_stations_ft(span, depth_in)}
    return [i for i, s in enumerate(stations)
            if round(s, 6) in want and 0 < i < len(stations) - 1]


def box_beam_line_checks(box: str, span_ft: float, n_beams: int, *,
                         strand_area_in2: float = 0.153,
                         fci_ksi: float = 4.0, fc_ksi: float = 5.5,
                         barrier_klf: float = 0.0,
                         fws_klf: float = 0.0,
                         humidity_pct: float = 70.0
                         ) -> BoxBeamLineChecks:
    """Re-derive the governing LRFD checks for one interior beam of a
    PSBDD-1-25 standard design.

    ``barrier_klf`` / ``fws_klf`` are bridge-total railing and future
    wearing surface, shared equally across the beams (the standard's own
    assumption for adjacent units).  ``fci_ksi`` / ``fc_ksi`` default to
    the low end of the sheet's designer-selected ranges (conservative
    for the stress checks)."""
    design = box_beam_design(box, int(span_ft))
    sec = box_section_properties(design.depth)
    composite = design.beam_type == "composite"
    span = float(span_ft)

    # ── live-load distribution (adjacent box, type "g") ───────────────────
    j = box_torsion_constant_in4(design.depth, sec.width)
    df_m = moment_df_interior_box(sec.width, span, sec.i, j, n_beams)
    df_v = shear_df_interior_box(sec.width, span, sec.i, j)
    g_m = max(df_m.one_lane, df_m.multi_lane)
    g_v = max(df_v.one_lane, df_v.multi_lane)

    # ── per-beam uniform loads (klf) ──────────────────────────────────────
    w_sw = sec.area / 144.0 * CONCRETE_KCF
    t_top_in = (COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN
                + COMPOSITE_SLAB_WEARING_SURFACE_IN)
    w_top = (sec.width / 12.0) * (t_top_in / 12.0) * CONCRETE_KCF \
        if composite else 0.0
    dc2 = barrier_klf / n_beams
    dw = fws_klf / n_beams

    # ── envelope (same machinery as the steel slice) ──────────────────────
    stations, moments = girder_line_envelope(
        [0.0, span], dc1_klf=w_sw + w_top, dc2_klf=dc2, dw_klf=dw, gdf=g_m)
    mid = len(stations) // 2
    m_sw = w_sw * span ** 2 / 8.0
    m_top = w_top * span ** 2 / 8.0
    m_dc2 = moments["dc2"][mid]
    m_dw = moments["dw"][mid]
    m_ll = moments["ll_pos"][mid]
    midspan = {"sw": m_sw, "topping": m_top, "dc2": m_dc2, "dw": m_dw,
               "ll": m_ll}

    # ── prestress + losses ────────────────────────────────────────────────
    a_ps = design.n_strands * strand_area_in2
    e = design.e_beam
    e_ci = _ec_ksi(fci_ksi)
    f_pt = F_PJ_KSI
    es = 0.0
    for _ in range(3):
        p_t = a_ps * f_pt
        f_cgp = (p_t / sec.area + p_t * e ** 2 / sec.i
                 - (m_sw * 12.0) * e / sec.i)
        es = ps_elastic_shortening_loss(f_cgp, e_ct=e_ci).capacity
        f_pt = F_PJ_KSI - es
    lt = ps_approximate_longterm_loss(
        f_pi=F_PJ_KSI, a_ps=a_ps, a_g=sec.area, f_ci=fci_ksi,
        humidity_pct=humidity_pct).capacity
    f_pe = F_PJ_KSI - es - lt
    p_t = a_ps * f_pt
    p_e = a_ps * f_pe
    losses = {"elastic_shortening": es, "longterm": lt,
              "total": es + lt, "f_pt": f_pt, "f_pe": f_pe}

    # ── transfer stresses at the transfer length (5.9.4.3.1: 60 strand
    #    diameters — the prestress is only fully effective there, and the
    #    self-weight moment at that section relieves the top) and midspan ──
    l_t_ft = 60.0 * 0.5 / 12.0
    m_lt = w_sw * l_t_ft * (span - l_t_ft) / 2.0    # kip-ft at x = l_t
    top_end = (p_t / sec.area - p_t * e / sec.zt + m_lt * 12.0 / sec.zt)
    bot_end = (p_t / sec.area + p_t * e / sec.zb - m_lt * 12.0 / sec.zb)
    top_mid = (p_t / sec.area - p_t * e / sec.zt + m_sw * 12.0 / sec.zt)
    bot_mid = (p_t / sec.area + p_t * e / sec.zb - m_sw * 12.0 / sec.zb)
    transfer_comp = max(bot_end, bot_mid, top_end, top_mid)
    transfer_ten = max(0.0, -min(top_end, top_mid, bot_end, bot_mid))

    # ── service stresses at midspan (composite section for loads after
    #    the topping cures; everything on the beam when non-composite) ─────
    zt2 = sec.ztc if composite else sec.zt
    zb2 = sec.zbc if composite else sec.zb
    m_beam_only = (m_sw + m_top) * 12.0
    m_comp = (m_dc2 + m_dw) * 12.0
    top_perm = (p_e / sec.area - p_e * e / sec.zt
                + m_beam_only / sec.zt + m_comp / zt2)
    top_total = top_perm + m_ll * 12.0 / zt2
    bot_serv3 = (p_e / sec.area + p_e * e / sec.zb
                 - m_beam_only / sec.zb
                 - (m_comp + 0.8 * m_ll * 12.0) / zb2)
    service_ten = max(0.0, -bot_serv3)

    stresses = {"transfer_top_end": top_end, "transfer_bot_end": bot_end,
                "transfer_top_mid": top_mid, "transfer_bot_mid": bot_mid,
                "service_top_permanent": top_perm,
                "service_top_total": top_total,
                "service_bot_serviceIII": bot_serv3}

    # ── Strength I flexure ────────────────────────────────────────────────
    m_u = (1.25 * (m_sw + m_top + m_dc2) + 1.5 * m_dw
           + 1.75 * m_ll) * 12.0
    ybar = strand_group_height_in(design)
    if composite:
        t_struct = COMPOSITE_SLAB_STRUCTURAL_THICKNESS_IN
        d_p = design.depth + t_struct - ybar
        flexure = ps_flexural_resistance(
            a_ps=a_ps, f_pu=F_PU_KSI, d_p=d_p, f_c=TOPPING_FC_KSI,
            b=sec.width, b_w=2.0 * BOX_WEB_THICKNESS_IN,
            h_f=t_struct + BOX_FLANGE_THICKNESS_IN, m_u=m_u)
    else:
        d_p = design.depth - ybar
        flexure = ps_flexural_resistance(
            a_ps=a_ps, f_pu=F_PU_KSI, d_p=d_p, f_c=fc_ksi,
            b=sec.width, b_w=2.0 * BOX_WEB_THICKNESS_IN,
            h_f=BOX_FLANGE_THICKNESS_IN, m_u=m_u)

    checks = {
        "transfer compression": ps_transfer_compression_check(
            fci_ksi, stress=transfer_comp),
        "transfer tension": ps_transfer_tension_check(
            fci_ksi, stress=transfer_ten, bonded_reinforcement=True),
        "service compression": ps_service_compression_check(
            fc_ksi, stress_permanent=max(0.0, top_perm),
            stress_total=max(0.0, top_total)),
        "service III tension": ps_service_tension_check(
            fc_ksi, stress=service_ten),
        "Strength I flexure": flexure,
    }

    return BoxBeamLineChecks(
        design=design, df_moment=g_m, df_shear=g_v,
        midspan_moments=midspan, losses=losses, stresses=stresses,
        checks=checks, camber_release_in=design.camber_d0,
        camber_erection_in=design.camber_d30)
