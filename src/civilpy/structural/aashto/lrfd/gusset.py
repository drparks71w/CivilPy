#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.
"""Gusset-plate resistance checks for truss joints.

Two families are provided so historic ratings can be reproduced before the
current provisions are applied to the same geometry:

* **LRFD 6.14.2.8 / MBE 6A.6.12** (2013 interims onward, NCHRP 12-84):
  fastener resistance, Whitmore tension (yield / fracture), Whitmore
  compression (6.14.2.8.4 column with K and Lmid, and the partial-shear-plane
  check for compression chords), plate shear with the Omega = 0.88 shear-yield
  reduction (6.14.2.8.3), block shear (6.13.4), and the edge-slenderness limit
  (6.14.2.8.7).
* **FHWA-IF-09-014 in Load Factor terms** as implemented by the 2012 ODOT
  gusset spreadsheet (``lfr_*`` functions): rivet shear / bearing "rivet
  count" check, Whitmore tension on the effective area An + beta*Ag,
  Whitmore compression as an AASHTO 10.54 column (K = 1.2, Cc), block shear
  1 = phi(0.58 Fy Avg + Fu Atn) and 2 = phi(0.58 Fu Avn + Fy Atg), global
  shear yield with Omega = 0.74 and fracture on the net section.  The 2012
  CUY-10-1613 workbook (Burgess & Niple / ODOT OSE) is the reference: its
  joint-42133 and joint-11000 numbers are reproduced in the tests.

All inputs are geometric quantities from
:mod:`civilpy.structural.gusset_geometry` (areas in in^2 already integrated
over the remaining thickness, lengths in inches) plus material strengths in
ksi; results are :class:`~civilpy.structural.aashto.lrfd.core.CheckResult`
with ``capacity`` = nominal resistance (kip) and ``phi`` set, unless the
docstring says the factored resistance is returned.
"""
from __future__ import annotations

import math

from civilpy.structural.aashto.lrfd.core import CheckResult

E_STEEL = 29000.0


# --------------------------------------------------------------------------- #
# rating factors
# --------------------------------------------------------------------------- #
def lfr_rating_factor(capacity_factored: float, dl: float, ll: float,
                      f1: float = 1.3, f2: float = 2.17) -> float:
    """Load-factor rating RF = (C - f1*DL) / (f2*LL).  Inventory f2 = 2.17
    (1.3 x 1.67), operating f2 = 1.3.  ``ll`` must already carry impact and
    multiple presence if the rating wants them (the 2012 ODOT gusset sheet
    applied NEITHER -- it used the STAAD live-load axials as they were)."""
    if ll <= 0:
        return float("inf")
    return (capacity_factored - f1 * abs(dl)) / (f2 * ll)


# --------------------------------------------------------------------------- #
# 2009-guidance / Load Factor versions (2012 ODOT sheet)
# --------------------------------------------------------------------------- #
def lfr_rivet_check(n_fasteners: int, d: float, t_gusset_total: float, t_base_total: float,
                    connection_length: float, fv_rivet: float = 28.0, fy_plate: float = 45.0,
                    omega_shear: float = 0.74, phi_bearing: float = 0.9,
                    long_joint_limit: float = 50.0, long_joint_factor: float = 0.8) -> CheckResult:
    """2012 sheet check 3 "Minimum Rivet Count": factored capacity of the
    member-end fastener group = min(rivet shear n*Ar*(Omega*Fv)*(0.8 if the
    connection is longer than 50 in), bearing on the gussets n*d*t*(phi Fy),
    bearing on the member base metal).  ``capacity`` is the *factored*
    value (phi already inside), ``phi`` = 1.0."""
    a_r = math.pi * d ** 2 / 4.0
    f_v = omega_shear * fv_rivet
    c_shear = n_fasteners * a_r * f_v * (long_joint_factor if connection_length > long_joint_limit else 1.0)
    c_bear = n_fasteners * d * t_gusset_total * phi_bearing * fy_plate
    c_base = n_fasteners * d * t_base_total * phi_bearing * fy_plate
    c = min(c_shear, c_bear, c_base)
    return CheckResult(article="FHWA-09 / AASHTO 10.16.14", name="Rivet shear and bearing (LFR)",
                       capacity=c, phi=1.0,
                       details={"C_shear": c_shear, "C_bearing_gusset": c_bear, "C_bearing_base": c_base,
                                "Fv": f_v, "governing": min((c_shear, "shear"), (c_bear, "bearing_gusset"),
                                                              (c_base, "bearing_base"))[1]})


def lfr_whitmore_tension(a_gross: float, a_net: float, fy: float = 45.0, beta: float = 0.15) -> CheckResult:
    """2012 sheet check 4: tension on the Whitmore section with the effective
    area Ae = An + beta*Ag; capacity = Fy*Ae (the sheet applies no phi
    here).  Areas for both plates."""
    a_e = a_net + beta * a_gross
    return CheckResult(article="FHWA-09 §3.4 (LFR)", name="Whitmore tension (LFR, Ae = An + beta Ag)",
                       capacity=fy * a_e, phi=1.0, details={"Ae": a_e})


def lfr_whitmore_compression(a_gross: float, t: float, lc: float, fy: float = 45.0,
                             k: float = 1.2, phi: float = 0.85) -> CheckResult:
    """2012 sheet check 2: Whitmore section as an AASHTO 10.54 column,
    r = t/sqrt(12), KL/r with K = 1.2 and L = Lc; Fcr = Fy(1 - (KL/r)^2 /
    (2 Cc^2)) for KL/r <= Cc, else pi^2 E/(KL/r)^2.  ``capacity`` is the
    nominal Fcr*Ag; ``phi`` = 0.85."""
    r = t / math.sqrt(12.0)
    klr = k * lc / r
    cc = math.sqrt(2 * math.pi ** 2 * E_STEEL / fy)
    if klr <= cc:
        fcr = fy * (1 - klr ** 2 / (2 * cc ** 2))
    else:
        fcr = math.pi ** 2 * E_STEEL / klr ** 2
    return CheckResult(article="AASHTO 10.54 (LFR)", name="Whitmore compression buckling (LFR)",
                       capacity=fcr * a_gross, phi=phi, details={"KL/r": klr, "Cc": cc, "Fcr": fcr})


def lfr_block_shear(a_vg: float, a_vn: float, a_tg: float, a_tn: float,
                    fy: float = 45.0, fu: float = 70.0, phi: float = 0.85) -> CheckResult:
    """2012 sheet checks 5/6: capacity 1 = phi(0.58 Fy Avg + Fu Atn),
    capacity 2 = phi(0.58 Fu Avn + Fy Atg); the smaller governs.
    ``capacity`` is factored (phi inside), ``phi`` = 1.0."""
    c1 = phi * (0.58 * fy * a_vg + fu * a_tn)
    c2 = phi * (0.58 * fu * a_vn + fy * a_tg)
    return CheckResult(article="FHWA-09 §3.6 (LFR)", name="Block shear (LFR)", capacity=min(c1, c2), phi=1.0,
                       details={"C1": c1, "C2": c2})


def lfr_global_shear(a_gross: float, a_net: float, fy: float = 45.0, fu: float = 70.0,
                     omega: float = 0.74, phi_fracture: float = 0.85) -> CheckResult:
    """2012 sheet check 8: shear yield on the gross section 0.58 Fy Avg
    reduced by Omega = 0.74 and shear fracture phi 0.58 Fu Avn; the smaller
    governs.  Areas for both plates along the full plate width / height."""
    c_y = omega * 0.58 * fy * a_gross
    c_f = phi_fracture * 0.58 * fu * a_net
    return CheckResult(article="FHWA-09 §3.7 (LFR)", name="Global shear yield / fracture (LFR)",
                       capacity=min(c_y, c_f), phi=1.0, details={"C_yield": c_y, "C_fracture": c_f})


# --------------------------------------------------------------------------- #
# LRFD 6.14.2.8 / MBE 6A.6.12
# --------------------------------------------------------------------------- #
def fastener_shear_resistance(n_fasteners: int, d: float, fu_fastener: float, planes: int = 1,
                              threads_excluded: bool = True, rivet: bool = False,
                              connection_length: float = 0.0) -> CheckResult:
    """Factored shear resistance of the fastener group (6.13.2.7; rivets per
    MBE 6A.6.12.6.1 with the rivet shear strength taken as 0.75 Fu on the
    rivet area, phi_s = 0.80).  Joints longer than 38 in between extreme
    fasteners take the 0.83 reduction."""
    a = math.pi * d ** 2 / 4.0
    if rivet:
        rn = 0.75 * fu_fastener * a * planes * n_fasteners
    else:
        c = 0.56 if threads_excluded else 0.45
        rn = c * fu_fastener * a * planes * n_fasteners
    if connection_length > 38.0:
        rn *= 0.83
    return CheckResult(article="6.13.2.7 / MBE 6A.6.12.6.1", name="Fastener group shear",
                       capacity=rn, phi=0.80, details={"per_fastener": rn / max(n_fasteners, 1)})


def whitmore_tension_resistance(a_gross: float, a_net: float, fy: float, fu: float,
                                u: float = 1.0) -> CheckResult:
    """6.14.2.8.5 / 6.8.2.1: lesser of phi_y Fy Ag (0.95) and phi_u Fu An U
    (0.80).  ``capacity`` holds the governing *factored* value, phi = 1.0."""
    r_y = 0.95 * fy * a_gross
    r_u = 0.80 * fu * a_net * u
    return CheckResult(article="6.14.2.8.5", name="Whitmore tension (yield / fracture)",
                       capacity=min(r_y, r_u), phi=1.0, details={"R_yield": r_y, "R_fracture": r_u})


def whitmore_compression_resistance(a_gross: float, t: float, l_mid: float, fy: float,
                                    k: float = 0.5, phi_cg: float = 0.75) -> CheckResult:
    """6.14.2.8.4: Whitmore section as a column with K = 0.5 (0.75 where the
    gusset is not braced by an adjacent member -- pass ``k``), L = Lmid,
    r = t/sqrt(12); Pn per 6.9.4.1 (Pe >= 0.44 Po: 0.658^(Po/Pe) Po, else
    0.877 Pe); phi_cg = 0.75."""
    r = t / math.sqrt(12.0)
    klr = k * l_mid / r
    po = fy * a_gross
    pe = math.pi ** 2 * E_STEEL * a_gross / klr ** 2 if klr > 0 else float("inf")
    pn = 0.658 ** (po / pe) * po if pe >= 0.44 * po else 0.877 * pe
    return CheckResult(article="6.14.2.8.4", name="Whitmore compression", capacity=pn, phi=phi_cg,
                       details={"KL/r": klr, "Pe": pe, "Po": po})


def partial_shear_plane_resistance(a_vg_partial: float, a_g_compression: float, fy: float,
                                   t: float, l_mid: float, k: float = 0.5, phi_cs: float = 0.75,
                                   omega: float = 0.88) -> CheckResult:
    """6.14.2.8.4 chord-splice / partial shear plane: the compression member
    force is resisted by the sum of shear yield on the partial plane
    (omega 0.58 Fy Avg,partial) and compression on the Whitmore section
    beyond it.  Simplified form: Pr = phi_cs (omega 0.58 Fy Avg_partial) +
    phi_cg Pn(Whitmore).  Returns the *factored* total, phi = 1.0."""
    shear = phi_cs * omega * 0.58 * fy * a_vg_partial
    comp = whitmore_compression_resistance(a_g_compression, t, l_mid, fy, k)
    return CheckResult(article="6.14.2.8.4 (partial shear plane)", name="Partial shear plane + Whitmore compression",
                       capacity=shear + comp.factored_capacity, phi=1.0,
                       details={"R_shear_partial": shear, "R_whitmore": comp.factored_capacity})


def plate_shear_resistance(a_gross: float, a_net: float, fy: float, fu: float,
                           omega: float = 0.88) -> CheckResult:
    """6.14.2.8.3: shear yield phi_vy (1.0) * 0.58 Fy Avg * Omega, shear
    rupture phi_vu (0.80) * 0.58 Fu Avn; the smaller *factored* value is
    returned (phi = 1.0)."""
    r_y = 1.0 * 0.58 * fy * a_gross * omega
    r_u = 0.80 * 0.58 * fu * a_net
    return CheckResult(article="6.14.2.8.3", name="Gusset plate shear", capacity=min(r_y, r_u), phi=1.0,
                       details={"R_yield": r_y, "R_rupture": r_u})


def block_shear_resistance(a_vg: float, a_vn: float, a_tn: float, fy: float, fu: float,
                           u_bs: float = 1.0, r_p: float = 1.0) -> CheckResult:
    """6.13.4 block shear: Rn = Rp(0.58 Fu Avn + Ubs Fu Atn) <= Rp(0.58 Fy
    Avg + Ubs Fu Atn), phi_bs = 0.80."""
    rn = r_p * min(0.58 * fu * a_vn + u_bs * fu * a_tn, 0.58 * fy * a_vg + u_bs * fu * a_tn)
    return CheckResult(article="6.13.4", name="Block shear rupture", capacity=rn, phi=0.80,
                       details={"Rp": r_p, "Ubs": u_bs})


def edge_slenderness_ok(unsupported_edge: float, t: float, fy: float, e: float = E_STEEL) -> CheckResult:
    """6.14.2.8.7: unstiffened free edge L/t <= 2.06 sqrt(E/Fy)."""
    limit = 2.06 * math.sqrt(e / fy)
    return CheckResult(article="6.14.2.8.7", name="Edge slenderness", capacity=limit * t,
                       demand=unsupported_edge, phi=1.0, details={"limit_L_over_t": limit})
