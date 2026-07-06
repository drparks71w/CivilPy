#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Concrete deck slab design by the approximate elastic (strip) method.

The LRFD 9.7.3 deck design path: the transverse strip widths of Table
4.6.2.1.3-1 (cast-in-place concrete rows), the Appendix A4 (Table A4-1)
HL-93 live-load moments those strips produce, and a flexural check chain
that reuses the Section 5 reinforced-concrete checks.  This is the method
the Ohio BDM mandates for decks (see
:mod:`civilpy.structural.odot.deck_design`) — the empirical method of LRFD
9.7.2 is deliberately not implemented.

Table A4-1 was transcribed from the specification and spot-validated
against state design aids (e.g. the 7'-0" span / 3 in section value of
5.17 kip-ft/ft quoted in Illinois DOT design guide 3.2.1).  Per the
appendix, the tabulated moments include the multiple-presence factor and
the 33% dynamic load allowance and apply to decks supported on at least
three girders with at least 14 ft between exterior-girder centerlines;
interpolation between tabulated values is permitted.

Units follow the package convention (kip, inch, ksi) except where a name
says otherwise: girder spacings and overhang distances are in feet and
distributed moments in kip-ft per ft of deck width, matching how the spec
tabulates them.
"""

import math

from civilpy.structural.aashto.lrfd.core import CheckResult, article
from civilpy.structural.aashto.lrfd.concrete import (
    rc_crack_control_spacing,
    rc_minimum_reinforcement,
    rc_rectangular_flexural_resistance,
)
from civilpy.structural.steel import Rebar

#: Strength I load factors for the deck strip (LRFD Table 3.4.1-1); the
#: A4-1 live-load moments already include IM and multiple presence.
STRENGTH_I = {"DC": 1.25, "DW": 1.50, "LL": 1.75}

#: Service I factors (crack control) — all unity.
SERVICE_I = {"DC": 1.00, "DW": 1.00, "LL": 1.00}


# ── Table 4.6.2.1.3-1, cast-in-place concrete rows ───────────────────────

@article("4.6.2.1.3", "Equivalent Strip Widths for Deck Slabs")
def deck_equivalent_strip(case: str, s_ft: float) -> float:
    """Transverse equivalent strip width (in) for a cast-in-place concrete
    deck (Table 4.6.2.1.3-1).

    ``case`` is ``"positive"`` / ``"negative"`` with ``s_ft`` the girder
    spacing S (ft), or ``"overhang"`` with ``s_ft`` the distance X (ft)
    from the wheel load to the point of support.
    """
    if s_ft < 0:
        raise ValueError("spacing/distance must be non-negative")
    if case == "positive":
        return 26.0 + 6.6 * s_ft
    if case == "negative":
        return 48.0 + 3.0 * s_ft
    if case == "overhang":
        return 45.0 + 10.0 * s_ft
    raise ValueError(f"unknown strip case {case!r}; use positive/negative/overhang")


# ── Appendix A4, Table A4-1 ──────────────────────────────────────────────

#: Design-section offsets (in from girder centerline) tabulated for the
#: negative moments in Table A4-1.
A4_NEGATIVE_OFFSETS: tuple[float, ...] = (0.0, 3.0, 6.0, 9.0, 12.0, 18.0, 24.0)

# span_ft: (positive, (negative at each A4_NEGATIVE_OFFSETS entry)),
# kip-ft/ft, transcribed from Table A4-1.
_A4_ROWS: dict[float, tuple[float, tuple[float, ...]]] = {
    4.00: (4.68, (2.68, 2.07, 1.74, 1.60, 1.50, 1.34, 1.25)),
    4.25: (4.66, (2.73, 2.25, 1.95, 1.74, 1.57, 1.33, 1.20)),
    4.50: (4.63, (3.00, 2.58, 2.19, 1.90, 1.65, 1.32, 1.18)),
    4.75: (4.64, (3.38, 2.90, 2.43, 2.07, 1.74, 1.29, 1.20)),
    5.00: (4.65, (3.74, 3.20, 2.66, 2.24, 1.83, 1.26, 1.12)),
    5.25: (4.67, (4.06, 3.47, 2.89, 2.41, 1.95, 1.28, 0.98)),
    5.50: (4.71, (4.36, 3.73, 3.11, 2.58, 2.07, 1.30, 0.99)),
    5.75: (4.77, (4.63, 3.97, 3.31, 2.73, 2.19, 1.32, 1.02)),
    6.00: (4.83, (4.88, 4.19, 3.50, 2.88, 2.31, 1.39, 1.07)),
    6.25: (4.91, (5.10, 4.39, 3.68, 3.02, 2.42, 1.45, 1.13)),
    6.50: (5.00, (5.31, 4.57, 3.84, 3.15, 2.53, 1.50, 1.20)),
    6.75: (5.10, (5.50, 4.74, 3.99, 3.27, 2.64, 1.58, 1.28)),
    7.00: (5.21, (5.98, 5.17, 4.36, 3.56, 2.84, 1.63, 1.37)),
    7.25: (5.32, (6.13, 5.31, 4.49, 3.68, 2.96, 1.65, 1.51)),
    7.50: (5.44, (6.26, 5.43, 4.61, 3.78, 3.15, 1.88, 1.72)),
    7.75: (5.56, (6.38, 5.54, 4.71, 3.88, 3.30, 2.21, 1.94)),
    8.00: (5.69, (6.48, 5.65, 4.81, 3.98, 3.43, 2.49, 2.16)),
    8.25: (5.83, (6.58, 5.74, 4.90, 4.06, 3.53, 2.74, 2.37)),
    8.50: (5.99, (6.66, 5.82, 4.98, 4.14, 3.61, 2.96, 2.58)),
    8.75: (6.14, (6.74, 5.90, 5.06, 4.22, 3.67, 3.15, 2.79)),
    9.00: (6.29, (6.81, 5.97, 5.13, 4.28, 3.71, 3.31, 3.00)),
    9.25: (6.44, (6.87, 6.03, 5.19, 4.40, 3.82, 3.47, 3.20)),
    9.50: (6.59, (7.15, 6.31, 5.46, 4.66, 4.04, 3.68, 3.39)),
    9.75: (6.74, (7.51, 6.65, 5.80, 4.94, 4.21, 3.89, 3.58)),
    10.00: (6.89, (7.85, 6.99, 6.13, 5.26, 4.41, 4.09, 3.77)),
    10.25: (7.03, (8.19, 7.32, 6.45, 5.58, 4.71, 4.29, 3.96)),
    10.50: (7.17, (8.52, 7.64, 6.77, 5.89, 5.02, 4.48, 4.15)),
    10.75: (7.32, (8.83, 7.95, 7.08, 6.20, 5.32, 4.68, 4.34)),
    11.00: (7.46, (9.14, 8.26, 7.38, 6.50, 5.62, 4.86, 4.52)),
    11.25: (7.60, (9.44, 8.55, 7.67, 6.79, 5.91, 5.04, 4.70)),
    11.50: (7.74, (9.72, 8.84, 7.96, 7.07, 6.19, 5.22, 4.87)),
    11.75: (7.88, (10.01, 9.12, 8.24, 7.36, 6.47, 5.40, 5.05)),
    12.00: (8.01, (10.28, 9.40, 8.51, 7.63, 6.74, 5.56, 5.21)),
    12.25: (8.15, (10.55, 9.67, 8.78, 7.90, 7.02, 5.75, 5.38)),
    12.50: (8.28, (10.81, 9.93, 9.04, 8.16, 7.28, 5.97, 5.54)),
    12.75: (8.41, (11.06, 10.18, 9.30, 8.42, 7.54, 6.18, 5.70)),
    13.00: (8.54, (11.31, 10.43, 9.55, 8.67, 7.79, 6.38, 5.86)),
    13.25: (8.66, (11.55, 10.67, 9.80, 8.92, 8.04, 6.59, 6.01)),
    13.50: (8.78, (11.79, 10.91, 10.03, 9.16, 8.28, 6.79, 6.16)),
    13.75: (8.90, (12.02, 11.14, 10.27, 9.40, 8.52, 6.99, 6.30)),
    14.00: (9.02, (12.24, 11.37, 10.50, 9.63, 8.76, 7.18, 6.45)),
    14.25: (9.14, (12.46, 11.59, 10.72, 9.85, 8.99, 7.38, 6.58)),
    14.50: (9.25, (12.67, 11.81, 10.94, 10.08, 9.21, 7.57, 6.72)),
    14.75: (9.36, (12.88, 12.02, 11.16, 10.30, 9.44, 7.76, 6.86)),
    15.00: (9.47, (13.09, 12.23, 11.37, 10.51, 9.65, 7.94, 7.02)),
}

A4_SPANS: tuple[float, ...] = tuple(sorted(_A4_ROWS))


def _a4_bracket(s_ft: float) -> tuple[float, float, float]:
    """Bounding tabulated spans and the interpolation fraction for S."""
    if not A4_SPANS[0] <= s_ft <= A4_SPANS[-1]:
        raise ValueError(
            f"girder spacing {s_ft} ft is outside Table A4-1 "
            f"({A4_SPANS[0]}-{A4_SPANS[-1]} ft); run a strip analysis instead"
        )
    lo = max(s for s in A4_SPANS if s <= s_ft)
    hi = min(s for s in A4_SPANS if s >= s_ft)
    frac = 0.0 if hi == lo else (s_ft - lo) / (hi - lo)
    return lo, hi, frac


@article("A4", "Deck Slab Design Table — Positive Moment")
def deck_ll_positive_moment(s_ft: float) -> float:
    """Maximum HL-93 positive live-load moment (kip-ft/ft, IM and multiple
    presence included) from Table A4-1, interpolating between tabulated
    girder spacings."""
    lo, hi, frac = _a4_bracket(s_ft)
    return _A4_ROWS[lo][0] + frac * (_A4_ROWS[hi][0] - _A4_ROWS[lo][0])


def deck_ll_negative_moment(s_ft: float, design_section_in: float) -> float:
    """Maximum HL-93 negative live-load moment (kip-ft/ft) from Table A4-1
    at a design section ``design_section_in`` inches from the girder
    centerline (LRFD 4.6.2.1.6), interpolating in both span and offset.
    Offsets beyond the tabulated 24 in use the 24 in column (conservative).
    """
    if design_section_in < 0:
        raise ValueError("design section offset must be non-negative")
    x = min(design_section_in, A4_NEGATIVE_OFFSETS[-1])
    lo, hi, frac = _a4_bracket(s_ft)

    def at_span(span: float) -> float:
        negs = _A4_ROWS[span][1]
        io = max(i for i, o in enumerate(A4_NEGATIVE_OFFSETS) if o <= x)
        ih = min(i for i, o in enumerate(A4_NEGATIVE_OFFSETS) if o >= x)
        if io == ih:
            return negs[io]
        f = (x - A4_NEGATIVE_OFFSETS[io]) / (
            A4_NEGATIVE_OFFSETS[ih] - A4_NEGATIVE_OFFSETS[io])
        return negs[io] + f * (negs[ih] - negs[io])

    return at_span(lo) + frac * (at_span(hi) - at_span(lo))


# ── Dead-load strip moments ──────────────────────────────────────────────

def deck_dead_load_moment(w_ksf: float, s_ft: float,
                          coefficient: float = 10.0) -> float:
    """Approximate dead-load moment (kip-ft/ft) of the continuous transverse
    strip: ``w*S^2/c`` with the customary ``c = 10`` used for deck strips
    continuous over three or more supports (used for both the positive and
    negative regions).  Pass ``coefficient=8.0`` for a simple-span strip.
    For staged decks or unusual framing, analyze the strip explicitly
    (e.g. :mod:`civilpy.structural.continuous_beam`) instead.
    """
    if coefficient <= 0:
        raise ValueError("coefficient must be positive")
    return w_ksf * s_ft ** 2 / coefficient


# ── Flexural design chain for a 1-ft strip ───────────────────────────────

def _cracked_service_stress(m_service_kipft: float, a_s: float, d_s: float,
                            f_c: float, b: float = 12.0) -> float:
    """Steel stress (ksi) under a service moment (kip-ft/ft) from a cracked
    elastic section analysis of the 1-ft strip, with n = Es/Ec and Ec per
    the LRFD C5.4.2.4 simplification (1820*sqrt(f'c))."""
    n = 29000.0 / (1820.0 * math.sqrt(f_c))
    rho = a_s / (b * d_s)
    k = math.sqrt((rho * n) ** 2 + 2.0 * rho * n) - rho * n
    j = 1.0 - k / 3.0
    return m_service_kipft * 12.0 / (a_s * j * d_s)


def deck_strip_checks(
    *,
    bar_size: int,
    spacing_in: float,
    t_structural: float,
    cover_in: float,
    m_dc: float,
    m_dw: float,
    m_ll: float,
    f_c: float = 4.5,
    f_y: float = 60.0,
    exposure_class_2: bool = True,
) -> list[CheckResult]:
    """Run the LRFD Section 5 check chain for one face of a deck strip.

    Moments are unfactored magnitudes in kip-ft/ft for the face being
    checked (positive moments for the bottom mat, negative for the top);
    Strength I and Service I factoring happens here.  ``t_structural`` is
    the structural deck thickness (in) — for ODOT decks the total thickness
    minus the monolithic wearing surface — and ``cover_in`` the clear cover
    on the tension face.  Returns the 5.6.3.2 flexure, 5.6.3.3 minimum
    reinforcement, and 5.6.7 crack control results in that order.
    """
    if t_structural <= 0 or spacing_in <= 0:
        raise ValueError("thickness and spacing must be positive")

    bar = Rebar(bar_size)
    dia = float(bar.diameter.magnitude)
    a_s = float(bar.area.magnitude) * 12.0 / spacing_in  # in^2/ft
    d_s = t_structural - cover_in - dia / 2.0
    if d_s <= 0:
        raise ValueError("cover consumes the whole structural thickness")

    m_u = (STRENGTH_I["DC"] * m_dc + STRENGTH_I["DW"] * m_dw
           + STRENGTH_I["LL"] * m_ll) * 12.0  # kip-in/ft
    m_service = (SERVICE_I["DC"] * m_dc + SERVICE_I["DW"] * m_dw
                 + SERVICE_I["LL"] * m_ll)    # kip-ft/ft

    flexure = rc_rectangular_flexural_resistance(
        a_s=a_s, f_y=f_y, f_c=f_c, b=12.0, d_s=d_s, m_u=m_u)

    s_c = 12.0 * t_structural ** 2 / 6.0
    minimum = rc_minimum_reinforcement(
        m_n=flexure.capacity, phi=flexure.phi, f_c=f_c, s_c=s_c, m_u=m_u)

    f_ss = _cracked_service_stress(m_service, a_s, d_s, f_c)
    crack = rc_crack_control_spacing(
        d_c=cover_in + dia / 2.0,
        h=t_structural,
        f_ss=f_ss,
        f_y=f_y,
        spacing=spacing_in,
        exposure_class_2=exposure_class_2,
    )
    crack.details["f_ss"] = f_ss
    crack.details["A_s_per_ft"] = a_s
    crack.details["d_s"] = d_s
    return [flexure, minimum, crack]
