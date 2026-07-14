#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Basic line-girder shear / moment / deflection tool.

The simplest useful form of a line-girder run, with **no Rhino or MIDAS
dependence**: pick a handful of settings (barrier type, AASHTO vehicle, deck
thickness, span arrangement, girder size/spacing), get back

1. the loads the tool derived from each selection (klf per girder, plus the
   AASHTO distribution factors), and
2. shear, moment, and deflection diagrams for an **interior and an exterior
   girder** — dead load exactly, live load as a stepped-vehicle /
   patterned-lane envelope.

The beam solver behind the diagrams is
:class:`~civilpy.structural.continuous_beam.ContinuousBeam`; it and the
envelope logic here are verified against the AISC Steel Construction Manual
Table 3-23 beam cases in ``tests/structural/test_line_girder_tool.py``
(cases 1, 29, 30, 43, 44) and ``tests/structural/test_beam_bending.py``.

Simplifications, kept loud on purpose (this is a first-pass tool):

* equal spans, prismatic girder, bare-steel ``I`` for every deflection
  (no composite section);
* both barriers shared equally by all girders (a common DC2 practice);
* HL-93 negative moment uses a single truck (the 90 % two-truck rule of
  3.6.1.3.1 is a refinement this tool skips);
* live-load deflection distributes ``m x n_lanes / n_girders`` per
  AASHTO 2.5.2.6.2, using the truck alone.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np

from civilpy.structural.aashto.lrfd.distribution import (
    lever_rule_exterior,
    longitudinal_stiffness_kg,
    moment_df_exterior,
    moment_df_interior,
    multiple_presence_factor,
    shear_df_exterior,
    shear_df_interior,
)
from civilpy.structural.aashto.vehicles import HS20Load
from civilpy.structural.continuous_beam import ContinuousBeam
from civilpy.structural.odot.bridge_railing import BRIDGE_RAILINGS

#: Reinforced-concrete unit weight (kcf) for deck and barrier dead load.
CONCRETE_KCF = 0.150

#: Axle trains (loads kip, offsets ft) per selectable design vehicle.  HL-93
#: rear-axle spacing varies 14-30 ft; stepping both bounding trains captures
#: the governing spread for negative moment over interior supports.
VEHICLES = {
    "HL-93 (design truck + lane)": {
        "trains": [([8.0, 32.0, 32.0], [0.0, 14.0, 28.0]),
                   ([8.0, 32.0, 32.0], [0.0, 14.0, 44.0])],
        "lane_klf": 0.64, "im": 0.33,
    },
    "HL-93 (design tandem + lane)": {
        "trains": [([25.0, 25.0], [0.0, 4.0])],
        "lane_klf": 0.64, "im": 0.33,
    },
    "HL-93 (governing of truck/tandem + lane)": {
        "trains": [([8.0, 32.0, 32.0], [0.0, 14.0, 28.0]),
                   ([8.0, 32.0, 32.0], [0.0, 14.0, 44.0]),
                   ([25.0, 25.0], [0.0, 4.0])],
        "lane_klf": 0.64, "im": 0.33,
    },
    # Standard-Spec truck for older ratings: no lane load here (truck loading
    # governs typical spans); impact from 50/(L+125) <= 0.30.
    "HS20-44 (truck only, Std. Spec. impact)": {
        "trains": [([8.0, 32.0, 32.0], [0.0, 14.0, 28.0])],
        "lane_klf": 0.0, "im": None,
    },
}


def barrier_weight_klf(designation: str) -> float:
    """Dead load of one barrier run (klf) from the ODOT railing catalog:
    gross concrete area x unit weight, else the catalog steel weight."""
    try:
        r = BRIDGE_RAILINGS[designation]
    except KeyError:
        raise KeyError(
            f"unknown barrier designation {designation!r}; choose one of "
            f"{sorted(BRIDGE_RAILINGS)}") from None
    if r.section_area:
        return r.section_area / 144.0 * CONCRETE_KCF
    if r.weight_per_ft:
        return r.weight_per_ft / 1000.0
    return 0.0


#: Catalog barriers with a computable dead weight — the dropdown choices.
BARRIER_CHOICES = tuple(
    d for d in BRIDGE_RAILINGS if barrier_weight_klf(d) > 0.0)


@dataclass
class BridgeConfig:
    """One dropdown's worth of settings for the basic line-girder tool."""

    n_spans: int = 3
    span_ft: float = 50.0            # equal spans
    #: AISC W-shape label from :mod:`civilpy.structural.steel`.
    girder: str = "W24X104"
    n_girders: int = 5
    spacing_ft: float = 7.0
    overhang_ft: float = 2.5         # deck edge beyond the exterior girder
    deck_t_in: float = 8.5
    haunch_in: float = 1.0           # top of girder to bottom of deck (for Kg)
    #: A key of :data:`BARRIER_CHOICES` (catalog railings with a
    #: computable dead weight).
    barrier: str = "SBR-1 (42 in)"
    #: A key of :data:`VEHICLES` (HL-93 truck / tandem / governing,
    #: HS-20 and the Ohio legal trucks).
    vehicle: str = "HL-93 (governing of truck/tandem + lane)"
    fws_ksf: float = 0.060           # future wearing surface
    e_ksi: float = 29000.0

    @property
    def supports(self) -> list[float]:
        return [i * self.span_ft for i in range(self.n_spans + 1)]

    @property
    def deck_width_ft(self) -> float:
        return (self.n_girders - 1) * self.spacing_ft + 2 * self.overhang_ft

    @property
    def barrier_base_ft(self) -> float:
        base_in = BRIDGE_RAILINGS[self.barrier].base_width
        return (base_in / 12.0) if base_in else 1.0

    @property
    def roadway_ft(self) -> float:
        return self.deck_width_ft - 2 * self.barrier_base_ft

    @property
    def n_lanes(self) -> int:
        return max(1, int(self.roadway_ft // 12.0))


@dataclass
class GirderLoads:
    """The per-girder loads the tool derived from the user's selections."""

    label: str
    trib_ft: float          # tributary deck width
    girder_klf: float       # steel self weight
    deck_klf: float         # wet slab on the tributary width
    dc1_klf: float          # girder + deck (non-composite dead load)
    barrier_klf: float      # this girder's share of both barrier runs
    dc2_klf: float          # superimposed dead load (= barrier share)
    dw_klf: float           # future wearing surface
    df_moment: float        # AASHTO 4.6.2.2 live-load DF (lanes/girder)
    df_shear: float
    df_deflection: float    # m * n_lanes / n_girders (2.5.2.6.2)
    im: float               # dynamic load allowance on the axles
    lane_klf: float         # design lane load (no IM)

    @property
    def dead_total_klf(self) -> float:
        return self.dc1_klf + self.dc2_klf + self.dw_klf


def _w_shape(designation: str):
    from civilpy.structural.steel import W
    return W(designation)


def compute_loads(cfg: BridgeConfig) -> dict[str, GirderLoads]:
    """Loads + distribution factors for the interior and exterior girders."""
    shape = _w_shape(cfg.girder)
    girder_klf = float(shape.W.to("lbf/ft").magnitude) / 1000.0
    depth_in = float(shape.depth.to("in").magnitude)
    i_x = float(shape.I_x.to("in**4").magnitude)
    area = float(shape.A.to("in**2").magnitude)

    deck_klf_per_ft = cfg.deck_t_in / 12.0 * CONCRETE_KCF   # klf per trib ft
    barrier_share = 2.0 * barrier_weight_klf(cfg.barrier) / cfg.n_girders
    veh = VEHICLES[cfg.vehicle]
    im = (HS20Load.impact_factor(cfg.span_ft) if veh["im"] is None
          else veh["im"])
    df_defl = (multiple_presence_factor(cfg.n_lanes) * cfg.n_lanes
               / cfg.n_girders)

    # interior: AASHTO 4.6.2.2.2b / 4.6.2.2.3a type (a) cross-section
    e_g = depth_in / 2.0 + cfg.haunch_in + cfg.deck_t_in / 2.0
    k_g = longitudinal_stiffness_kg(8.0, i_x, area, e_g)
    df_m_int = moment_df_interior(cfg.spacing_ft, cfg.span_ft, cfg.deck_t_in,
                                  k_g, cfg.n_girders)
    df_v_int = shear_df_interior(cfg.spacing_ft, cfg.span_ft, cfg.deck_t_in,
                                 cfg.n_girders)

    # exterior: lever rule (one lane) + e-factor on the interior DF (multi)
    d_e = cfg.overhang_ft - cfg.barrier_base_ft
    lever = lever_rule_exterior(cfg.spacing_ft, d_e)
    df_m_ext = moment_df_exterior(df_m_int, d_e, one_lane_lever_rule=lever)
    df_v_ext = shear_df_exterior(df_v_int, d_e, one_lane_lever_rule=lever)

    trib_int = cfg.spacing_ft
    trib_ext = cfg.spacing_ft / 2.0 + cfg.overhang_ft

    def _loads(label, trib, df_m, df_v):
        deck = deck_klf_per_ft * trib
        return GirderLoads(
            label=label, trib_ft=trib, girder_klf=girder_klf, deck_klf=deck,
            dc1_klf=girder_klf + deck, barrier_klf=barrier_share,
            dc2_klf=barrier_share, dw_klf=cfg.fws_ksf * trib,
            df_moment=df_m.governing, df_shear=df_v.governing,
            df_deflection=df_defl, im=im, lane_klf=veh["lane_klf"])

    return {"interior": _loads("interior", trib_int, df_m_int, df_v_int),
            "exterior": _loads("exterior", trib_ext, df_m_ext, df_v_ext)}


# ---------------------------------------------------------------------------
# Live-load envelopes
# ---------------------------------------------------------------------------

def moving_load_envelope(supports, trains, *, n: int = 401,
                         xs=None,
                         step: float | None = None,
                         e_ksi: float | None = None,
                         i_in4: float | None = None):
    """Step each axle train (both travel directions) across the beam and
    envelope shear, moment, and (optionally) deflection at ``n`` stations.

    ``trains`` is a list of ``(axle_loads_kip, offsets_ft)`` pairs; axles off
    the beam contribute nothing.  Stations are ``n`` even samples (or ``xs``
    when given).  Returns a dict with ``stations`` and the
    ``v_max/v_min/m_max/m_min`` envelopes (kip, kip-ft), plus ``d_min``
    (inches, most-downward) when ``e_ksi``/``i_in4`` are given.
    """
    supports = [float(s) for s in supports]
    length = supports[-1] - supports[0]
    if step is None:
        step = max(length / 400.0, 0.25)
    xs = (np.linspace(supports[0], supports[-1], n) if xs is None
          else np.asarray(xs, dtype=float))
    v_max = np.zeros_like(xs)
    v_min = np.zeros_like(xs)
    m_max = np.zeros_like(xs)
    m_min = np.zeros_like(xs)
    d_min = np.zeros_like(xs)
    with_defl = e_ksi is not None and i_in4 is not None

    seen = set()
    for axles, offsets in trains:
        axles = list(axles)
        offsets = np.asarray(offsets, dtype=float)
        # both travel directions: the mirrored train reverses the axle order
        for loads_dir, offs in ((axles, offsets),
                                (axles[::-1], offsets[-1] - offsets[::-1])):
            key = (tuple(loads_dir), tuple(np.round(offs, 6)))
            if key in seen:                      # symmetric train
                continue
            seen.add(key)
            train_len = float(offs[-1])
            for x0 in np.arange(supports[0] - train_len,
                                supports[-1] + step / 2.0, step):
                beam = ContinuousBeam(supports)
                on_beam = False
                for p, o in zip(loads_dir, offs):
                    if supports[0] <= x0 + o <= supports[-1]:
                        beam.add_point(p, x0 + o)
                        on_beam = True
                if not on_beam:
                    continue
                _, v, m = beam.diagrams(xs)
                np.maximum(v_max, v, out=v_max)
                np.minimum(v_min, v, out=v_min)
                np.maximum(m_max, m, out=m_max)
                np.minimum(m_min, m, out=m_min)
                if with_defl:
                    _, d = beam.deflection_diagram(e_ksi, i_in4, xs=xs)
                    np.minimum(d_min, d, out=d_min)
    out = {"stations": list(xs), "v_max": v_max, "v_min": v_min,
           "m_max": m_max, "m_min": m_min}
    if with_defl:
        out["d_min"] = d_min
    return out


def lane_load_envelope(supports, w_klf: float, *, n: int = 401, xs=None):
    """Envelope of a uniform lane load placed on every combination of spans
    (the adverse-span patterning of AASHTO 3.6.1.3.1, done exhaustively —
    at most ``2**n_spans - 1`` load cases).  Same return keys as
    :func:`moving_load_envelope` (without deflection)."""
    supports = [float(s) for s in supports]
    xs = (np.linspace(supports[0], supports[-1], n) if xs is None
          else np.asarray(xs, dtype=float))
    v_max = np.zeros_like(xs)
    v_min = np.zeros_like(xs)
    m_max = np.zeros_like(xs)
    m_min = np.zeros_like(xs)
    n_spans = len(supports) - 1
    if w_klf:
        for r in range(1, n_spans + 1):
            for combo in itertools.combinations(range(n_spans), r):
                beam = ContinuousBeam(supports)
                for i in combo:
                    beam.add_udl(w_klf, supports[i], supports[i + 1])
                _, v, m = beam.diagrams(xs)
                np.maximum(v_max, v, out=v_max)
                np.minimum(v_min, v, out=v_min)
                np.maximum(m_max, m, out=m_max)
                np.minimum(m_min, m, out=m_min)
    return {"stations": list(xs), "v_max": v_max, "v_min": v_min,
            "m_max": m_max, "m_min": m_min}


# ---------------------------------------------------------------------------
# The tool: settings -> loads -> diagrams
# ---------------------------------------------------------------------------

@dataclass
class GirderDiagrams:
    """Sampled diagrams for one girder (kip / kip-ft / inches; station ft)."""

    loads: GirderLoads
    stations: list[float]
    v_dead: np.ndarray
    m_dead: np.ndarray
    d_dead: np.ndarray
    v_ll_pos: np.ndarray     # DF x (train x (1+IM) + lane) envelopes
    v_ll_neg: np.ndarray
    m_ll_pos: np.ndarray
    m_ll_neg: np.ndarray
    d_ll: np.ndarray         # deflection-DF x (1+IM) x truck envelope

    @property
    def v_total_pos(self):
        return self.v_dead + self.v_ll_pos

    @property
    def v_total_neg(self):
        return self.v_dead + self.v_ll_neg

    @property
    def m_total_pos(self):
        return self.m_dead + self.m_ll_pos

    @property
    def m_total_neg(self):
        return self.m_dead + self.m_ll_neg

    @property
    def d_total(self):
        return self.d_dead + self.d_ll


@dataclass
class LineGirderResult:
    """Everything :func:`analyze` produced: config, loads, and diagrams."""

    config: BridgeConfig
    loads: dict[str, GirderLoads]
    girders: dict[str, GirderDiagrams] = field(default_factory=dict)


def analyze(cfg: BridgeConfig, *, n: int = 401) -> LineGirderResult:
    """Run the basic line-girder tool for one configuration."""
    loads = compute_loads(cfg)
    veh = VEHICLES[cfg.vehicle]
    i_x = float(_w_shape(cfg.girder).I_x.to("in**4").magnitude)
    supports = cfg.supports

    # station grid: n even samples plus the exact support stations, so the
    # peak negative moment over each pier is sampled, not straddled
    xs = np.unique(np.concatenate(
        [np.linspace(supports[0], supports[-1], n), supports]))

    # one unit-live-load pass, scaled per girder by its DF afterwards
    train = moving_load_envelope(supports, veh["trains"], xs=xs,
                                 e_ksi=cfg.e_ksi, i_in4=i_x)
    lane = lane_load_envelope(supports, veh["lane_klf"], xs=xs)

    result = LineGirderResult(config=cfg, loads=loads)
    for name, gl in loads.items():
        beam = ContinuousBeam(supports).add_udl(gl.dead_total_klf)
        _, v_dead, m_dead = beam.diagrams(xs)
        _, d_dead = beam.deflection_diagram(cfg.e_ksi, i_x, xs=xs)
        im_f = 1.0 + gl.im
        result.girders[name] = GirderDiagrams(
            loads=gl, stations=xs,
            v_dead=v_dead, m_dead=m_dead, d_dead=np.asarray(d_dead),
            v_ll_pos=gl.df_shear * (im_f * train["v_max"] + lane["v_max"]),
            v_ll_neg=gl.df_shear * (im_f * train["v_min"] + lane["v_min"]),
            m_ll_pos=gl.df_moment * (im_f * train["m_max"] + lane["m_max"]),
            m_ll_neg=gl.df_moment * (im_f * train["m_min"] + lane["m_min"]),
            d_ll=gl.df_deflection * im_f * train["d_min"],
        )
    return result


def loads_table(result: LineGirderResult):
    """The loads the tool associated with each selection, as a DataFrame
    (rows = load items, columns = interior / exterior girder)."""
    import pandas as pd

    cfg = result.config
    rows = {
        "tributary width (ft)": lambda g: g.trib_ft,
        f"girder self weight, {cfg.girder} (klf)": lambda g: g.girder_klf,
        f"deck, {cfg.deck_t_in:g} in slab (klf)": lambda g: g.deck_klf,
        "DC1 = girder + deck (klf)": lambda g: g.dc1_klf,
        f"DC2 = barrier share, {cfg.barrier} (klf)": lambda g: g.dc2_klf,
        f"DW = wearing surface, {cfg.fws_ksf:g} ksf (klf)": lambda g: g.dw_klf,
        "total dead load (klf)": lambda g: g.dead_total_klf,
        "LL distribution factor - moment": lambda g: g.df_moment,
        "LL distribution factor - shear": lambda g: g.df_shear,
        "LL distribution factor - deflection": lambda g: g.df_deflection,
        "dynamic load allowance IM": lambda g: g.im,
        "design lane load (klf)": lambda g: g.lane_klf,
    }
    return pd.DataFrame(
        {name: [f(gl) for f in rows.values()]
         for name, gl in result.loads.items()},
        index=list(rows)).round(3)


def plot_diagrams(result: LineGirderResult, figsize=(12, 9)):
    """Shear / moment / deflection, interior and exterior girder side by side.

    Gray = dead load alone; colored band = dead + live-load envelope."""
    import matplotlib.pyplot as plt

    cfg = result.config
    fig, axes = plt.subplots(3, 2, figsize=figsize, sharex=True, sharey="row")
    for col, (name, g) in enumerate(result.girders.items()):
        xs = g.stations
        ax_v, ax_m, ax_d = axes[0][col], axes[1][col], axes[2][col]
        ax_v.set_title(f"{name} girder")

        ax_v.plot(xs, g.v_dead, color="0.55", lw=1.5, label="dead load")
        ax_v.fill_between(xs, g.v_total_neg, g.v_total_pos,
                          color="#4477aa", alpha=0.25)
        ax_v.plot(xs, g.v_total_pos, color="#4477aa", lw=1.8,
                  label="dead + LL envelope")
        ax_v.plot(xs, g.v_total_neg, color="#4477aa", lw=1.8)

        ax_m.plot(xs, g.m_dead, color="0.55", lw=1.5)
        ax_m.fill_between(xs, g.m_total_neg, g.m_total_pos,
                          color="#994455", alpha=0.25)
        ax_m.plot(xs, g.m_total_pos, color="#994455", lw=1.8)
        ax_m.plot(xs, g.m_total_neg, color="#994455", lw=1.8)

        ax_d.plot(xs, g.d_dead, color="0.55", lw=1.5)
        ax_d.plot(xs, g.d_total, color="#117733", lw=1.8)
        ax_d.axhline(-cfg.span_ft * 12.0 / 800.0, color="#117733", ls=":",
                     lw=1.2, label="L/800")

        for ax in (ax_v, ax_m, ax_d):
            for s in cfg.supports:
                ax.axvline(s, color="0.85", lw=1, zorder=0)
            ax.axhline(0, color="0.6", lw=0.8)
            ax.grid(alpha=0.25)
        ax_d.set_xlabel("station (ft)")
    axes[0][0].set_ylabel("shear (kip)")
    axes[1][0].set_ylabel("moment (kip·ft)")
    axes[2][0].set_ylabel("deflection (in)")
    axes[0][0].legend(fontsize=8, loc="lower left")
    axes[2][0].legend(fontsize=8, loc="lower left")
    fig.suptitle(
        f"{cfg.n_spans} × {cfg.span_ft:g} ft  ·  {cfg.girder}  ·  "
        f"{cfg.n_girders} girders @ {cfg.spacing_ft:g} ft  ·  "
        f"{cfg.deck_t_in:g} in deck  ·  {cfg.barrier}  ·  {cfg.vehicle}",
        y=1.0, fontsize=11)
    fig.tight_layout()
    return fig
