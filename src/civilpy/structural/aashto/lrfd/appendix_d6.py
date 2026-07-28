#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""AASHTO LRFD Appendix D6 — fundamental flexural properties of composite
I-sections: the plastic moment ``Mp`` (D6.1, Tables D6.1-1 and D6.1-2), the
yield moment ``My`` (D6.2.2 / D6.2.3), and the elastic web compression
depth ``Dc`` (D6.3.1).  ``Dcp`` (D6.3.2) falls out of the plastic-moment
solution and is reported on its result.

Units follow the package convention: kip, inch, ksi.  Moments are kip-in.

Geometry convention: the section is described *as built* — deck on top,
then haunch, then the steel.  For **positive** flexure the compression
flange is the top flange; for **negative** flexure the deck is cracked
(only its longitudinal rebar acts) and the compression flange is the
bottom flange.  Rebar depths ``c_rt`` / ``c_rb`` are measured from the top
of the slab to the layer centers.  Haunch concrete is treated as a void
(standard design practice — the haunch depth varies along the span and its
concrete is ignored).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural.aashto.lrfd.core import article


@dataclass
class PlasticMomentResult:
    """Solution of the Table D6.1-1 / D6.1-2 plastic-moment analysis.

    ``case`` is the table's roman-numeral row; ``y_bar`` the tabulated
    :math:`\\bar{Y}` measured within the element containing the PNA (from
    the *top* of that element); ``y_pna`` the PNA depth from the top of
    the slab; ``dp`` the 6.10.7.3 ductility depth (top of slab to PNA);
    ``dt`` the total composite depth; ``dcp`` the D6.3.2 depth of web in
    compression at ``Mp``.  ``forces`` holds the plastic component forces
    (kip) keyed by the spec's symbols.
    """

    flexure: str
    case: str
    pna: str
    y_bar: float
    y_pna: float
    mp: float
    dp: float
    dt: float
    dcp: float
    forces: dict = field(default_factory=dict)


@article("D6.1", "Plastic Moment of a Composite Section")
def plastic_moment(
    *,
    flexure: str = "positive",
    # compression flange (top for positive flexure, bottom for negative)
    b_c: float,
    t_c: float,
    f_yc: float,
    # web
    d_web: float,
    t_w: float,
    f_yw: float,
    # tension flange
    b_t: float,
    t_t: float,
    f_yt: float,
    # concrete deck (participates in positive flexure only)
    f_c: float = 0.0,
    b_s: float = 0.0,
    t_s: float = 0.0,
    t_haunch: float = 0.0,
    # longitudinal deck reinforcement, layer centers from top of slab
    a_rt: float = 0.0,
    c_rt: float = 0.0,
    a_rb: float = 0.0,
    c_rb: float = 0.0,
    f_yr: float = 60.0,
) -> PlasticMomentResult:
    """Plastic moment of a composite I-section per Appendix D6.1.

    Positive flexure walks the seven PNA cases of Table D6.1-1 (web, top
    flange, then five deck positions); negative flexure the two cases of
    Table D6.1-2 (deck concrete ignored, rebar kept).  The first case
    whose force-balance condition holds governs, exactly as tabulated.

    Returns a :class:`PlasticMomentResult`; ``mp`` is in kip-in.
    """
    p_c = f_yc * b_c * t_c
    p_w = f_yw * d_web * t_w
    p_t = f_yt * b_t * t_t
    p_rt = f_yr * a_rt
    p_rb = f_yr * a_rb
    forces = {"Pc": p_c, "Pw": p_w, "Pt": p_t, "Prt": p_rt, "Prb": p_rb}

    if flexure == "positive":
        p_s = 0.85 * f_c * b_s * t_s
        forces["Ps"] = p_s
        # component centerlines, measured from the top of the slab
        y_top_steel = t_s + t_haunch
        y_c = y_top_steel + t_c / 2.0
        y_w = y_top_steel + t_c + d_web / 2.0
        y_t = y_top_steel + t_c + d_web + t_t / 2.0
        y_s = t_s / 2.0
        d_total = t_s + t_haunch + t_c + d_web + t_t

        def rebar_terms(y_pna):
            return p_rt * abs(y_pna - c_rt) + p_rb * abs(y_pna - c_rb)

        # Case I — PNA in the web
        if p_t + p_w >= p_c + p_s + p_rb + p_rt:
            y_bar = (d_web / 2.0) * (
                (p_t - p_c - p_s - p_rt - p_rb) / p_w + 1.0)
            if y_bar > d_web:
                raise ValueError(
                    "PNA falls in the tension flange — outside Table "
                    "D6.1-1 (tension-flange force exceeds everything "
                    "above the web)")
            y_pna = y_top_steel + t_c + y_bar
            mp = (p_w / (2.0 * d_web)) * (
                y_bar ** 2 + (d_web - y_bar) ** 2) + (
                p_s * abs(y_pna - y_s) + rebar_terms(y_pna)
                + p_c * abs(y_pna - y_c) + p_t * abs(y_t - y_pna))
            return PlasticMomentResult(
                flexure, "I", "web", y_bar, y_pna, mp, y_pna, d_total,
                y_bar, forces)

        # Case II — PNA in the top (compression) flange
        if p_t + p_w + p_c >= p_s + p_rb + p_rt:
            y_bar = (t_c / 2.0) * (
                (p_w + p_t - p_s - p_rt - p_rb) / p_c + 1.0)
            y_pna = y_top_steel + y_bar
            mp = (p_c / (2.0 * t_c)) * (
                y_bar ** 2 + (t_c - y_bar) ** 2) + (
                p_s * abs(y_pna - y_s) + rebar_terms(y_pna)
                + p_w * abs(y_w - y_pna) + p_t * abs(y_t - y_pna))
            return PlasticMomentResult(
                flexure, "II", "top flange", y_bar, y_pna, mp, y_pna,
                d_total, 0.0, forces)

        # Cases III-VII — PNA in the concrete deck.  The slab compression
        # block is the deck above the PNA, so the slab term is
        # (y_bar^2 * Ps) / (2 ts) and the steel/rebar components are lumped.
        def deck_mp(y_bar, include_rt=True, include_rb=True):
            steel = (p_c * abs(y_c - y_bar) + p_w * abs(y_w - y_bar)
                     + p_t * abs(y_t - y_bar))
            bars = 0.0
            if include_rt:
                bars += p_rt * abs(y_bar - c_rt)
            if include_rb:
                bars += p_rb * abs(y_bar - c_rb)
            return (y_bar ** 2 * p_s) / (2.0 * t_s) + steel + bars

        steel_sum = p_t + p_w + p_c
        if steel_sum >= (c_rb / t_s) * p_s + p_rb + p_rt:
            y_bar = t_s * (steel_sum - p_rt - p_rb) / p_s
            case, pna = "III", "deck, below Prb"
        elif steel_sum + p_rb >= (c_rb / t_s) * p_s + p_rt:
            y_bar = c_rb
            case, pna = "IV", "deck, at Prb"
        elif steel_sum + p_rb >= (c_rt / t_s) * p_s + p_rt:
            y_bar = t_s * (steel_sum + p_rb - p_rt) / p_s
            case, pna = "V", "deck, between rebar layers"
        elif steel_sum + p_rb + p_rt >= (c_rt / t_s) * p_s:
            y_bar = c_rt
            case, pna = "VI", "deck, at Prt"
        else:
            y_bar = t_s * (steel_sum + p_rb + p_rt) / p_s
            case, pna = "VII", "deck, above Prt"
        mp = deck_mp(y_bar,
                     include_rt=case != "VI",
                     include_rb=case != "IV")
        return PlasticMomentResult(
            flexure, case, pna, y_bar, y_bar, mp, y_bar, d_total, 0.0,
            forces)

    if flexure != "negative":
        raise ValueError(f"flexure must be 'positive' or 'negative', "
                         f"got {flexure!r}")

    # ---- negative flexure, Table D6.1-2: cracked deck, rebar only ------
    # As built: tension flange on top, compression flange on the bottom.
    y_top_steel = t_s + t_haunch
    y_t = y_top_steel + t_t / 2.0
    y_w = y_top_steel + t_t + d_web / 2.0
    y_c = y_top_steel + t_t + d_web + t_c / 2.0
    d_total = t_s + t_haunch + t_t + d_web + t_c

    # Case I — PNA in the web (y_bar from the top of the web)
    if p_c + p_w >= p_t + p_rb + p_rt:
        y_bar = (d_web / 2.0) * ((p_c - p_t - p_rt - p_rb) / p_w + 1.0)
        y_pna = y_top_steel + t_t + y_bar
        mp = (p_w / (2.0 * d_web)) * (
            y_bar ** 2 + (d_web - y_bar) ** 2) + (
            p_rt * abs(y_pna - c_rt) + p_rb * abs(y_pna - c_rb)
            + p_t * abs(y_pna - y_t) + p_c * abs(y_c - y_pna))
        return PlasticMomentResult(
            flexure, "I", "web", y_bar, y_pna, mp, y_pna, d_total,
            d_web - y_bar, forces)

    # Case II — PNA in the top (tension) flange; the whole web is in
    # compression, so Dcp = D
    if p_c + p_w + p_t >= p_rb + p_rt:
        y_bar = (t_t / 2.0) * ((p_w + p_c - p_rt - p_rb) / p_t + 1.0)
        y_pna = y_top_steel + y_bar
        mp = (p_t / (2.0 * t_t)) * (
            y_bar ** 2 + (t_t - y_bar) ** 2) + (
            p_rt * abs(y_pna - c_rt) + p_rb * abs(y_pna - c_rb)
            + p_w * abs(y_w - y_pna) + p_c * abs(y_c - y_pna))
        return PlasticMomentResult(
            flexure, "II", "top flange", y_bar, y_pna, mp, y_pna,
            d_total, d_web, forces)

    raise ValueError(
        "PNA falls above the steel in negative flexure — outside "
        "Table D6.1-2 (rebar force exceeds the whole steel section)")


@dataclass
class YieldMomentResult:
    """Solution of the D6.2.2 / D6.2.3 staged yield-moment equations.

    ``m_ad_top`` / ``m_ad_bot`` are the additional short-term-section
    moments that bring each flange to ``Fy``; ``my`` is the governing
    (lesser) total.  All moments kip-in.
    """

    my: float
    my_top: float
    my_bot: float
    m_ad_top: float
    m_ad_bot: float

    @property
    def governing_flange(self) -> str:
        return "top" if self.my_top <= self.my_bot else "bottom"


@article("D6.2.2", "Yield Moment of a Composite Section")
def yield_moment_composite(
    *,
    m_d1: float,
    m_d2: float,
    s_nc_top: float,
    s_nc_bot: float,
    s_lt_top: float,
    s_lt_bot: float,
    s_st_top: float,
    s_st_bot: float,
    f_y_top: float,
    f_y_bot: float,
) -> YieldMomentResult:
    """Yield moment of a composite section (D6.2.2, Eqs. D6.2.2-1/-2).

    The composite girder is loaded in stages, so first yield is a staged
    sum: ``MD1`` rides the noncomposite moduli, ``MD2`` the long-term
    composite moduli, and the *additional* moment ``MAD`` that first
    brings a flange to ``Fy`` rides the short-term moduli.  ``My`` is the
    lesser of the two flange totals ``MD1 + MD2 + MAD``.

    For **negative** flexure (D6.2.3) pass the cracked steel-plus-rebar
    section modulus for *both* the long-term and short-term arguments —
    the equations are otherwise identical.  Moments kip-in, moduli in^3.
    """
    m_ad_top = s_st_top * (f_y_top - m_d1 / s_nc_top - m_d2 / s_lt_top)
    m_ad_bot = s_st_bot * (f_y_bot - m_d1 / s_nc_bot - m_d2 / s_lt_bot)
    my_top = m_d1 + m_d2 + m_ad_top
    my_bot = m_d1 + m_d2 + m_ad_bot
    return YieldMomentResult(
        my=min(my_top, my_bot), my_top=my_top, my_bot=my_bot,
        m_ad_top=m_ad_top, m_ad_bot=m_ad_bot)


@article("D6.3.1", "Depth of Web in Compression in the Elastic Range")
def web_compression_depth_elastic(
    f_c_comp: float,
    f_t_tens: float,
    d_steel: float,
    t_fc: float,
) -> float:
    """Elastic depth of web in compression ``Dc`` for a composite section
    (Eq. D6.3.1-1): the compressed share of the steel depth, less the
    compression-flange thickness, floored at zero.

    ``f_c_comp`` / ``f_t_tens`` are the *magnitudes* of the sum of the
    staged flange stresses caused by the loads considered (ksi);
    ``d_steel`` is the steel section depth.
    """
    dc = (f_c_comp / (f_c_comp + f_t_tens)) * d_steel - t_fc
    return max(dc, 0.0)
