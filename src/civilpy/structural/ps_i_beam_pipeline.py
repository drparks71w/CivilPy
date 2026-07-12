#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""L1 design + verification of ODOT PSID-1-13 prestressed I-beam lines.

The box-beam slice verifies pre-engineered PSBDD table designs; PSID-1-13
has **no companion design-data sheet**, so this module both *designs* the
strand pattern on the sheet's permissible grid
(:func:`civilpy.structural.odot.ps_i_beam.strand_grid`) and re-derives
the governing checks for one interior beam line — the prestressed-I
analog of :mod:`civilpy.structural.box_beam_pipeline`:

* HL-93 demands from the same :func:`~civilpy.structural.girder_pipeline
  .girder_line_envelope` machinery, distributed with the **type-k**
  I-girder factors (LRFD 4.6.2.2.2b/3a, ``Kg`` from the composite
  girder/deck geometry);
* a straight, fully-bonded strand pattern chosen as the smallest even
  count that passes Service III tension (5.9.2.3.2b) and Strength I
  flexure (5.6.3) — sheet 10's 0.6 in Grade 270 low-relaxation strand
  at 0.217 in^2, jacked to 0.75 f_pu;
* elastic shortening (5.9.3.2.3a) + approximate lump-sum time-dependent
  losses (5.9.3.3);
* concrete stresses at transfer (5.9.2.3.1, at the 60-diameter transfer
  length and midspan) and service (5.9.2.3.2, composite section for
  loads applied after the deck cures).  When the fully-bonded pattern
  overstresses the beam end at transfer, the designer **debonds** end
  strands (outermost bottom-row strands first — the standard's own
  remedy, sheet 10 detail item 4) in pairs up to the 5.9.4.3.3 cap
  (45 % of the total, the 8th-Edition-and-later limit; pass 0.25 for
  pre-2018 designs); the end check then runs on the bonded subset at
  its transfer length while midspan keeps the full pattern.  Only when
  the cap can't fix the end — or midspan release compression itself is
  over, the true long-span limit at ODOT's 5.0 ksi ``f'ci`` ceiling —
  does the result carry a ``debond_note`` flag / failed check;
* release camber (elastic: prestress hog minus self-weight sag at
  ``E_ci``).

The WF web locations the sheet marks "must be draped if utilized" are
never used by the straight-pattern designer.  Units: kip / inch / ksi
internally; spans, spacings and uniform loads enter in feet and klf.
Simple spans only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural.aashto.lrfd.distribution import (
    longitudinal_stiffness_kg,
    moment_df_interior,
    shear_df_interior,
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
from civilpy.structural.odot.ps_i_beam import (
    FWS_PSF,
    STRAND_AREA_IN2,
    STRAND_DIAMETER_IN,
    STRAND_FPU_KSI,
    i_beam_diaphragm_stations_ft,
    ps_i_beam_section,
    strand_centroid_in,
    strand_grid,
)

F_PJ_KSI = 0.75 * STRAND_FPU_KSI    #: jacking stress, low-relaxation (5.9.2.2)
CONCRETE_KCF = 0.150
DECK_FC_KSI = 4.5                   #: ODOT Class QC2 deck concrete


def _ec_ksi(fc_ksi: float) -> float:
    """Concrete modulus (ksi), 57000*sqrt(f'c psi) convention — the same
    one the box/pier modules use."""
    return 1820.0 * math.sqrt(fc_ksi)


# ── composite (beam + deck) elastic section ───────────────────────────────
@dataclass(frozen=True)
class CompositeSection:
    """Transformed composite section of one interior beam and its deck
    tributary width.  Inches; the deck is transformed into beam concrete
    by the deck/beam modular ratio.  The haunch locates the slab
    vertically but its area is neglected (conservative on the moduli)."""

    b_eff_in: float
    n_deck_beam: float          # E_deck / E_beam
    t_struct_in: float
    haunch_in: float
    area_in2: float
    ybc_in: float               # composite centroid above beam bottom
    i_in4: float
    sbc_in3: float              # beam bottom
    stc_beam_in3: float         # beam top


def composite_section(name: str, spacing_ft: float, *,
                      t_struct_in: float, haunch_in: float,
                      fc_beam_ksi: float,
                      fc_deck_ksi: float = DECK_FC_KSI) -> CompositeSection:
    """Transformed composite properties for an interior line: effective
    flange width = beam spacing (4.6.2.6.1), structural deck thickness
    only (the wearing course carries as DW, not stiffness)."""
    s = ps_i_beam_section(name)
    n = _ec_ksi(fc_deck_ksi) / _ec_ksi(fc_beam_ksi)
    b_eff = spacing_ft * 12.0
    b_tr = b_eff * n
    a_slab = b_tr * t_struct_in
    z_slab = s.depth_in + haunch_in + t_struct_in / 2.0
    a = s.area_in2 + a_slab
    ybc = (s.area_in2 * s.yb_in + a_slab * z_slab) / a
    i_slab = b_tr * t_struct_in ** 3 / 12.0
    i = (s.i_in4 + s.area_in2 * (ybc - s.yb_in) ** 2
         + i_slab + a_slab * (z_slab - ybc) ** 2)
    return CompositeSection(
        b_eff_in=b_eff, n_deck_beam=n, t_struct_in=t_struct_in,
        haunch_in=haunch_in, area_in2=a, ybc_in=ybc, i_in4=i,
        sbc_in3=i / ybc, stc_beam_in3=i / (s.depth_in - ybc))


# ── the designed line ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class PSIBeamDesign:
    """A designed strand pattern for one PSID-1-13 beam line."""

    section: object
    span_ft: float
    spacing_ft: float
    n_strands: int
    pattern: tuple = ()
    ybar_in: float = 0.0        # strand centroid above bottom
    e_in: float = 0.0           # eccentricity about the gross beam section
    fci_ksi: float = 4.0
    fc_ksi: float = 5.5
    #: Strands debonded at each end (outermost bottom-row first); 0 when
    #: the fully-bonded pattern passes transfer.
    n_debonded: int = 0

    @property
    def a_ps_in2(self) -> float:
        return self.n_strands * STRAND_AREA_IN2


@dataclass(frozen=True)
class PSIBeamLineChecks:
    """Everything :func:`ps_i_beam_line_checks` derives for one interior
    beam line.  Moments in kip-ft; stresses in ksi (compression
    positive); ``checks`` values are
    :class:`~civilpy.structural.aashto.lrfd.core.CheckResult`."""

    design: PSIBeamDesign
    composite: CompositeSection
    df_moment: float
    df_shear: float
    midspan_moments: dict = field(default_factory=dict)
    losses: dict = field(default_factory=dict)
    stresses: dict = field(default_factory=dict)
    checks: dict = field(default_factory=dict)
    camber_release_in: float = 0.0
    debond_note: str = ""

    @property
    def all_ok(self) -> bool:
        return all(c.ok for c in self.checks.values())

    def summary(self) -> str:
        d = self.design
        bond = (f"{d.n_debonded} debonded each end" if d.n_debonded
                else "fully bonded")
        lines = [f"{d.section.name} @ {d.span_ft:g} ft, S = "
                 f"{d.spacing_ft:g} ft: {d.n_strands} x "
                 f"{STRAND_DIAMETER_IN:g} in strands, "
                 f"e = {d.e_in:.2f} in (straight, {bond})",
                 f"  DF moment {self.df_moment:.3f} / shear "
                 f"{self.df_shear:.3f} (type k, 4.6.2.2.2b/3a)",
                 f"  losses: ES {self.losses['elastic_shortening']:.1f} + "
                 f"LT {self.losses['longterm']:.1f} ksi -> "
                 f"f_pe = {self.losses['f_pe']:.1f} ksi"]
        for name, chk in self.checks.items():
            ratio = (chk.demand / (chk.phi * chk.capacity)
                     if chk.demand is not None and chk.capacity else 0.0)
            lines.append(f"  {'PASS' if chk.ok else 'FAIL'}  {name}: "
                         f"D/C = {ratio:.2f} ({chk.article})")
        lines.append(f"  release camber: {self.camber_release_in:+.2f} in "
                     "(elastic estimate)")
        if self.debond_note:
            lines.append(f"  NOTE: {self.debond_note}")
        return "\n".join(lines)


# ── MIDAS spoke ───────────────────────────────────────────────────────────
def structural_model_from_ps_i(name: str, span_ft: float, n_beams: int, *,
                               spacing_ft: float, deck_t_in: float = 8.5,
                               haunch_in: float = 2.0,
                               diaphragms: bool = True,
                               dead_loads: bool = True,
                               barrier_klf: float = 0.0,
                               fws_klf: float | None = None):
    """Build the :class:`~civilpy.structural.structural_model
    .StructuralModel` hub for a prestressed I-beam bridge — one line of
    beam elements per girder broken at the sheet 5 intermediate-
    diaphragm stations, transverse diaphragm elements there, a pin +
    roller per line, and DC1/DC2/DW beam loads matching
    :func:`ps_i_beam_line_checks` exactly.

    Elements carry the PSID section name as their section label plus the
    published constants in metadata (``section.area_in2`` /
    ``section.i_in4``) for a value-type section on the MAPI side.
    ``fws_klf`` is bridge-total; it defaults to the sheet 10 design
    loading (60 psf over ``n_beams * spacing_ft``)."""
    from civilpy.structural.structural_model import StructuralModel, Units

    sec = ps_i_beam_section(name)
    span = float(span_ft)
    if fws_klf is None:
        fws_klf = FWS_PSF / 1000.0 * spacing_ft * n_beams

    stations = [0.0, *i_beam_diaphragm_stations_ft(span), span]
    stations = sorted(set(round(s, 6) for s in stations))

    model = StructuralModel(units=Units(force="kips", length="ft"))
    grid: dict[tuple[int, int], str] = {}
    beam_elems: dict[int, list] = {}
    for b in range(n_beams):
        y_c = b * spacing_ft
        for i, st in enumerate(stations):
            grid[(b, i)] = model.add_node(
                st, y_c, sec.depth_in / 12.0, label=f"PSI{b + 1}_S{i}").id
        elems = []
        for i in range(len(stations) - 1):
            e = model.add_element(
                grid[(b, i)], grid[(b, i + 1)], role="girder",
                midas_type="BEAM", section=name, material="ps_concrete")
            e.metadata.update({
                "gdr.line": str(b + 1), "gdr.family": "ps_i",
                "section.area_in2": sec.area_in2,
                "section.i_in4": sec.i_in4})
            elems.append(e.id)
        beam_elems[b] = elems
        model.add_restraint(grid[(b, 0)], fix_x=True, fix_y=True,
                            fix_z=True).preset = "fixed"
        model.add_restraint(grid[(b, len(stations) - 1)], fix_x=False,
                            fix_y=True, fix_z=True).preset = "expansion"

    if diaphragms:
        for b in range(n_beams - 1):
            for i in range(1, len(stations) - 1):
                e = model.add_element(grid[(b, i)], grid[(b + 1, i)],
                                      role="diaphragm", midas_type="BEAM")
                e.metadata["gdr.kind"] = "diaphragm"

    if dead_loads:
        w_sw = sec.weight_plf / 1000.0
        w_deck = spacing_ft * deck_t_in / 12.0 * CONCRETE_KCF
        w_haunch = (sec.top_flange_width_in / 12.0) * (haunch_in / 12.0) \
            * CONCRETE_KCF
        dc2 = barrier_klf / n_beams
        dw = fws_klf / n_beams
        for elems in beam_elems.values():
            for eid in elems:
                model.add_beam_load(eid, -(w_sw + w_deck + w_haunch),
                                    case="DC1")
                if dc2:
                    model.add_beam_load(eid, -dc2, case="DC2")
                if dw:
                    model.add_beam_load(eid, -dw, case="DW")

    return model


# ── the line designer + checker ───────────────────────────────────────────
def ps_i_beam_line_checks(name: str, span_ft: float, n_beams: int, *,
                          spacing_ft: float, deck_t_in: float = 8.5,
                          sacrificial_in: float = 1.0,
                          haunch_in: float = 2.0,
                          n_strands: int | None = None,
                          fci_ksi: float = 4.0, fc_ksi: float = 5.5,
                          barrier_klf: float = 0.0,
                          fws_klf: float | None = None,
                          humidity_pct: float = 70.0,
                          max_debond_fraction: float = 0.45
                          ) -> PSIBeamLineChecks:
    """Design (or verify, when ``n_strands`` is given) one interior
    PSID-1-13 beam line and re-derive its governing LRFD checks.

    ``deck_t_in`` is the full slab; ``sacrificial_in`` (the ODOT
    monodeck wearing course) is excluded from the composite stiffness
    but its weight stays in DC1.  ``barrier_klf`` / ``fws_klf`` are
    bridge-total, shared equally across the beams; ``fws_klf`` defaults
    to the sheet 10 design loading (60 psf across the deck).
    ``fci_ksi`` / ``fc_ksi`` default to the low end of the sheet 10
    designer-selected ranges (conservative for the stress checks)."""
    sec = ps_i_beam_section(name)
    span = float(span_ft)
    t_struct = deck_t_in - sacrificial_in
    comp = composite_section(name, spacing_ft, t_struct_in=t_struct,
                             haunch_in=haunch_in, fc_beam_ksi=fc_ksi)
    if fws_klf is None:
        fws_klf = FWS_PSF / 1000.0 * spacing_ft * n_beams

    # ── live-load distribution (type k) ───────────────────────────────────
    e_g = sec.yt_in + haunch_in + t_struct / 2.0
    kg = longitudinal_stiffness_kg(1.0 / comp.n_deck_beam, sec.i_in4,
                                   sec.area_in2, e_g)
    df_m = moment_df_interior(spacing_ft, span, t_struct, kg, n_beams)
    df_v = shear_df_interior(spacing_ft, span, t_struct, n_beams)
    g_m = df_m.governing
    g_v = df_v.governing

    # ── per-beam uniform loads (klf) ──────────────────────────────────────
    w_sw = sec.weight_plf / 1000.0
    w_deck = spacing_ft * deck_t_in / 12.0 * CONCRETE_KCF
    w_haunch = (sec.top_flange_width_in / 12.0) * (haunch_in / 12.0) \
        * CONCRETE_KCF
    dc1 = w_sw + w_deck + w_haunch
    dc2 = barrier_klf / n_beams
    dw = fws_klf / n_beams

    # ── envelope (same machinery as the steel/box slices) ─────────────────
    stations, moments = girder_line_envelope(
        [0.0, span], dc1_klf=dc1, dc2_klf=dc2, dw_klf=dw, gdf=g_m)
    mid = len(stations) // 2
    m_sw = w_sw * span ** 2 / 8.0
    m_slab = (w_deck + w_haunch) * span ** 2 / 8.0
    m_dc2 = moments["dc2"][mid]
    m_dw = moments["dw"][mid]
    m_ll = moments["ll_pos"][mid]
    midspan = {"sw": m_sw, "slab": m_slab, "dc2": m_dc2, "dw": m_dw,
               "ll": m_ll}

    # ── strand pattern: verify the given count or find the smallest even
    #    count passing Service III tension + Strength I flexure ────────────
    grid = strand_grid(name)
    n_straight_max = len(grid) - len(sec.draped_required)
    tension_limit = 0.19 * math.sqrt(fc_ksi)      # 5.9.2.3.2b, <= 0.6 ksi
    tension_limit = min(tension_limit, 0.6)

    def _pattern_state(n):
        pattern = grid[:n]
        ybar = strand_centroid_in(pattern)
        e = sec.yb_in - ybar
        a_ps = n * STRAND_AREA_IN2
        # losses (iterate ES on the transfer stress at the strand cg)
        f_pt = F_PJ_KSI
        es = 0.0
        for _ in range(3):
            p_t = a_ps * f_pt
            f_cgp = (p_t / sec.area_in2 + p_t * e ** 2 / sec.i_in4
                     - (m_sw * 12.0) * e / sec.i_in4)
            es = ps_elastic_shortening_loss(
                f_cgp, e_ct=_ec_ksi(fci_ksi)).capacity
            f_pt = F_PJ_KSI - es
        lt = ps_approximate_longterm_loss(
            f_pi=F_PJ_KSI, a_ps=a_ps, a_g=sec.area_in2, f_ci=fci_ksi,
            humidity_pct=humidity_pct).capacity
        f_pe = F_PJ_KSI - es - lt
        return pattern, ybar, e, a_ps, f_pt, f_pe, es, lt

    def _service_bot(a_ps, e, f_pe):
        p_e = a_ps * f_pe
        m_beam_only = (m_sw + m_slab) * 12.0
        m_comp = (m_dc2 + m_dw + 0.8 * m_ll) * 12.0
        return (p_e / sec.area_in2 + p_e * e / sec.sb_in3
                - m_beam_only / sec.sb_in3 - m_comp / comp.sbc_in3)

    def _strength(a_ps, ybar):
        m_u = (1.25 * (m_sw + m_slab + m_dc2) + 1.5 * m_dw
               + 1.75 * m_ll) * 12.0
        d_p = sec.depth_in + haunch_in + t_struct - ybar
        return ps_flexural_resistance(
            a_ps=a_ps, f_pu=STRAND_FPU_KSI, d_p=d_p, f_c=DECK_FC_KSI,
            b=comp.b_eff_in, b_w=sec.web_in, h_f=t_struct, m_u=m_u)

    if n_strands is None:
        chosen = None
        for n in range(2, n_straight_max + 1, 2):
            pattern, ybar, e, a_ps, f_pt, f_pe, es, lt = _pattern_state(n)
            if -_service_bot(a_ps, e, f_pe) > tension_limit:
                continue
            if not _strength(a_ps, ybar).ok:
                continue
            chosen = n
            break
        if chosen is None:
            raise ValueError(
                f"{name} @ {span:g} ft / S = {spacing_ft:g} ft: no "
                f"straight fully-bonded pattern (max {n_straight_max} "
                "strands) satisfies Service III + Strength I — use a "
                "deeper section or tighter spacing")
        n_strands = chosen
    elif not 0 < n_strands <= n_straight_max:
        raise ValueError(
            f"n_strands must be within 1..{n_straight_max} straight "
            f"locations for {name}, not {n_strands}")

    pattern, ybar, e, a_ps, f_pt, f_pe, es, lt = _pattern_state(n_strands)
    p_t = a_ps * f_pt
    p_e = a_ps * f_pe
    losses = {"elastic_shortening": es, "longterm": lt,
              "total": es + lt, "f_pt": f_pt, "f_pe": f_pe}

    # ── transfer stresses (5.9.4.3.1: 60 strand diameters).  Midspan uses
    #    the full pattern; the end section uses the bonded subset, with
    #    end strands debonded in pairs (5.9.4.3.3 cap) until it passes ────
    l_t_ft = 60.0 * STRAND_DIAMETER_IN / 12.0
    m_lt = w_sw * l_t_ft * (span - l_t_ft) / 2.0    # kip-ft at x = l_t
    comp_limit = 0.65 * fci_ksi                     # 5.9.2.3.1a
    ten_limit_t = 0.24 * math.sqrt(fci_ksi)        # 5.9.2.3.1b, bonded reinf

    def _end_stresses(n_db):
        bonded = pattern[n_db:]
        p_b = len(bonded) * STRAND_AREA_IN2 * f_pt
        e_b = sec.yb_in - strand_centroid_in(list(bonded))
        top = (p_b / sec.area_in2 - p_b * e_b / sec.st_in3
               + m_lt * 12.0 / sec.st_in3)
        bot = (p_b / sec.area_in2 + p_b * e_b / sec.sb_in3
               - m_lt * 12.0 / sec.sb_in3)
        return top, bot

    top_mid = (p_t / sec.area_in2 - p_t * e / sec.st_in3
               + m_sw * 12.0 / sec.st_in3)
    bot_mid = (p_t / sec.area_in2 + p_t * e / sec.sb_in3
               - m_sw * 12.0 / sec.sb_in3)

    n_db_cap = int(max_debond_fraction * n_strands) // 2 * 2
    n_debonded = 0
    top_end, bot_end = _end_stresses(0)
    while (max(bot_end, top_end) > comp_limit
           or -min(top_end, bot_end) > ten_limit_t) \
            and n_debonded + 2 <= n_db_cap:
        n_debonded += 2
        top_end, bot_end = _end_stresses(n_debonded)

    design = PSIBeamDesign(
        section=sec, span_ft=span, spacing_ft=spacing_ft,
        n_strands=n_strands, pattern=tuple(pattern), ybar_in=ybar,
        e_in=e, fci_ksi=fci_ksi, fc_ksi=fc_ksi, n_debonded=n_debonded)

    transfer_comp = max(top_end, bot_end, top_mid, bot_mid)
    transfer_ten = max(0.0, -min(top_end, top_mid, bot_end, bot_mid))

    # ── service stresses at midspan (composite for post-deck loads) ───────
    m_beam_only = (m_sw + m_slab) * 12.0
    m_comp = (m_dc2 + m_dw) * 12.0
    top_perm = (p_e / sec.area_in2 - p_e * e / sec.st_in3
                + m_beam_only / sec.st_in3 + m_comp / comp.stc_beam_in3)
    top_total = top_perm + m_ll * 12.0 / comp.stc_beam_in3
    bot_serv3 = _service_bot(a_ps, e, f_pe)
    service_ten = max(0.0, -bot_serv3)

    stresses = {"transfer_top_end": top_end, "transfer_bot_end": bot_end,
                "transfer_top_mid": top_mid, "transfer_bot_mid": bot_mid,
                "service_top_permanent": top_perm,
                "service_top_total": top_total,
                "service_bot_serviceIII": bot_serv3}

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
        "Strength I flexure": _strength(a_ps, ybar),
    }

    debond_note = ""
    if not (checks["transfer compression"].ok
            and checks["transfer tension"].ok):
        debond_note = (
            f"transfer stresses still exceed 5.9.2.3.1 with "
            f"{n_debonded} of {n_strands} strands debonded (the "
            f"{max_debond_fraction:.0%} 5.9.4.3.3 cap) — the pattern "
            "needs draping or a higher release strength (designer "
            "detail per PSID-1-13 sheet 10)")

    # ── release camber (elastic, straight strands => uniform P*e) ─────────
    e_ci = _ec_ksi(fci_ksi)
    l_in = span * 12.0
    hog = p_t * e * l_in ** 2 / (8.0 * e_ci * sec.i_in4)
    sag = 5.0 * (w_sw / 12.0) * l_in ** 4 / (384.0 * e_ci * sec.i_in4)
    camber = hog - sag

    return PSIBeamLineChecks(
        design=design, composite=comp, df_moment=g_m, df_shear=g_v,
        midspan_moments=midspan, losses=losses, stresses=stresses,
        checks=checks, camber_release_in=camber, debond_note=debond_note)
