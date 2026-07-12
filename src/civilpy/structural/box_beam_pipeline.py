#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""L1 verification of the ODOT standard box-beam designs.

The PSBDD-1-25 tables are pre-engineered designs; this module is the
pure-Python gate that *re-derives* the governing checks for one design
line — the box-beam analog of the steel slice's line-girder envelope
(work-plan 5.2/5.3):

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
    BOX_WALL_THICKNESS_IN,
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
                             wall_in: float = BOX_WALL_THICKNESS_IN
                             ) -> float:
    """St. Venant torsion constant of the closed box (thin-wall,
    C4.6.2.2.1-3): ``J = 4 A0^2 / (s/t)`` with the shear-flow path on the
    wall midline."""
    b0 = width_in - wall_in
    d0 = depth_in - wall_in
    return 4.0 * (b0 * d0) ** 2 / (2.0 * (b0 + d0) / wall_in)


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
            b=sec.width, b_w=2.0 * BOX_WALL_THICKNESS_IN,
            h_f=t_struct + BOX_WALL_THICKNESS_IN, m_u=m_u)
    else:
        d_p = design.depth - ybar
        flexure = ps_flexural_resistance(
            a_ps=a_ps, f_pu=F_PU_KSI, d_p=d_p, f_c=fc_ksi,
            b=sec.width, b_w=2.0 * BOX_WALL_THICKNESS_IN,
            h_f=BOX_WALL_THICKNESS_IN, m_u=m_u)

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
