#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT single span slab bridges (SB-1-24).

Transcribed from Ohio DOT Standard Bridge Drawing **SB-1-24**, "Single
Span Slab Bridges" (rev. 01-16-2026, 2 sheets). The drawing remains the
controlling document.

Sheet 1's ``SLAB DATA`` table gives the slab thickness and the A/B/M/N
longitudinal reinforcing bar spacing/size for spans 11-38 ft; sheet 2's
``EDGE BEAM SLAB DATA`` table gives the edge-beam depth ``D``, taper
``X``, and D/E-bar spacing/size for the two edge conditions (over-the-side
drainage vs. a concrete parapet, which allows a shallower edge beam).

Design basis (sheet 2 notes): AASHTO LRFD 9th Ed. + ODOT BDM (July 2023);
HL-93; FWS 60 lb/ft^2; 1 in monolithic wearing surface; concrete f'c =
4500 psi; reinforcing steel min. yield 60,000 psi, epoxy coated.
Applicable for roadway widths >= 24 ft and skew <= 25 deg. For skew
0 < theta <= 25 deg, longitudinal bars stay parallel to the roadway
centerline and transverse bars parallel to the pier/abutment skew line
(the slab plan is a skewed parallelogram, same shear convention as every
other flared/skewed layout in this package).

Conventions: X along stations, Y transverse, Z up; feet in plan, inches
for section dimensions. The layout origin sits at the upstream bearing
line, y = 0 at one slab edge, z = 0 at the top of slab.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "SB-1-24"
REVISION = "01-16-2026"

# ── design data (sheet 2 notes) ──────────────────────────────────────────

ROADWAY_WIDTH_MIN_FT = 24.0
SKEW_MAX_DEG = 25.0
DESIGN_METHOD = "LRFD"
DESIGN_SPEC = "AASHTO LRFD Bridge Design Specifications, 9th Ed. + ODOT BDM (July 2023)"
DESIGN_LOADING = "HL-93"
FUTURE_WEARING_SURFACE_PSF = 60.0
WEARING_SURFACE_THICKNESS_IN = 1.0   # one inch monolithic
CONCRETE_STRENGTH_PSI = 4500.0
REBAR_YIELD_PSI = 60000.0

#: Bearing-seat width at each abutment, inches (elevation view "9"/COS(theta)").
BEARING_SEAT_IN = 9.0

#: Lap splice lengths by bar size, feet: {size: {"top"/"bot": length_ft}}.
#: No.5 gives both faces; larger sizes are bottom-face laps only (sheet 2).
LAP_SPLICE_FT = {
    5: {"top": 3.0 + 10.0 / 12.0, "bot": 3.0 + 8.0 / 12.0},
    7: {"bot": 4.0 + 5.0 / 12.0},
    8: {"bot": 7.0 + 3.0 / 12.0},
    9: {"bot": 8.0 + 11.0 / 12.0},
    10: {"bot": 10.0 + 11.0 / 12.0},
}

EDGE_BEAM_PARAPET_REDUCTION_IN = 18.0  # min slab edge depth w/ a concrete parapet


def standard_hook_bar_length_ft(span_ft: float) -> float:
    """A/D/E-bar standard-hook length: ``span + 10"`` (the bending-diagram
    formula shared by all three bar marks)."""
    return span_ft + 10.0 / 12.0


def bridge_length_ft(span_ft: float, skew_deg: float = 0.0) -> float:
    """``BRIDGE LENGTH = SPAN + (1.5' / COS(theta))`` (sheet 1)."""
    return span_ft + 1.5 / math.cos(math.radians(skew_deg))


# ── SLAB DATA (sheet 1) ───────────────────────────────────────────────────

@dataclass(frozen=True)
class BarSpec:
    spacing_in: float
    size: int


@dataclass(frozen=True)
class SlabDesign:
    """One ``SLAB DATA`` table row (sheet 1)."""

    span_ft: int
    thickness_in: float
    a_bar: BarSpec   # bottom mat, primary (varies by span)
    b_bar: BarSpec   # top mat
    m_bar: BarSpec   # additional bottom longitudinal bars
    n_bar: BarSpec   # additional top longitudinal bars


def _row(span, t, a_spa, a_sz, b_spa=12.0, b_sz=5,
         m_spa=10.0, m_sz=5, n_spa=12.0, n_sz=5) -> SlabDesign:
    return SlabDesign(
        span_ft=span, thickness_in=t,
        a_bar=BarSpec(a_spa, a_sz), b_bar=BarSpec(b_spa, b_sz),
        m_bar=BarSpec(m_spa, m_sz), n_bar=BarSpec(n_spa, n_sz),
    )


#: SB-1-24 ``SLAB DATA``, keyed by span (ft). B/M/N bars never vary across
#: spans on this sheet (12 in #5 / 10 in #5 / 12 in #5) -- transcribed in
#: full per row anyway, since a future revision could change that.
SLAB_DESIGNS: dict[int, SlabDesign] = {
    d.span_ft: d for d in (
        _row(11, 11 + 1 / 4.0, 6, 7), _row(12, 11 + 3 / 4.0, 6, 7),
        _row(13, 12 + 1 / 2.0, 6, 7), _row(14, 13.0, 6, 7),
        _row(15, 13 + 1 / 2.0, 6, 7), _row(16, 14.0, 6, 7),
        _row(17, 14 + 3 / 4.0, 7, 8), _row(18, 15 + 1 / 4.0, 7, 8),
        _row(19, 15 + 3 / 4.0, 7, 8), _row(20, 16 + 1 / 4.0, 7, 8),
        _row(21, 16 + 3 / 4.0, 6, 8), _row(22, 17 + 1 / 4.0, 6, 8),
        _row(23, 17 + 3 / 4.0, 6, 8), _row(24, 18 + 1 / 4.0, 6, 8),
        _row(25, 18 + 3 / 4.0, 6, 8), _row(26, 19 + 1 / 4.0, 7, 9),
        _row(27, 19 + 3 / 4.0, 7, 9), _row(28, 20 + 1 / 2.0, 7, 9),
        _row(29, 21.0, 7, 9), _row(30, 21 + 1 / 2.0, 6, 9),
        _row(31, 22 + 1 / 4.0, 6, 9), _row(32, 22 + 3 / 4.0, 6, 9),
        _row(33, 23 + 1 / 4.0, 6, 9), _row(34, 23 + 3 / 4.0, 6, 9),
        _row(35, 24 + 1 / 4.0, 6, 9), _row(36, 25.0, 7, 10),
        _row(37, 25 + 1 / 2.0, 7, 10), _row(38, 26.0, 7, 10),
    )
}


def slab_design(span_ft: int) -> SlabDesign:
    """Look up the SB-1-24 slab design for a span (feet, 11-38 tabulated).

    Raises ``ValueError`` naming the valid spans otherwise."""
    try:
        return SLAB_DESIGNS[int(span_ft)]
    except (KeyError, ValueError):
        raise ValueError(
            f"SB-1-24 tabulates spans 11-38 ft, not {span_ft!r}") from None


# ── EDGE BEAM SLAB DATA (sheet 2) ─────────────────────────────────────────

@dataclass(frozen=True)
class EdgeBarSpec:
    depth_in: float    # D
    taper_in: float    # X
    bar_size: int
    bar_count: int


@dataclass(frozen=True)
class EdgeBeamDesign:
    """One ``EDGE BEAM SLAB DATA`` table row (sheet 2): the edge-beam depth
    and D/E-bar schedule for both edge conditions."""

    span_ft: int
    over_the_side: EdgeBarSpec   # over-the-side drainage edge, D-bars
    parapet: EdgeBarSpec         # concrete parapet edge, E-bars (shallower)


def _edge_row(span, d_ots, x_ots, dsz, dn, d_par, x_par, esz, en) -> EdgeBeamDesign:
    return EdgeBeamDesign(
        span_ft=span,
        over_the_side=EdgeBarSpec(d_ots, x_ots, dsz, dn),
        parapet=EdgeBarSpec(d_par, x_par, esz, en),
    )


#: SB-1-24 ``EDGE BEAM SLAB DATA``, keyed by span (ft).
EDGE_BEAM_DESIGNS: dict[int, EdgeBeamDesign] = {
    d.span_ft: d for d in (
        _edge_row(11, 20, 45, 7, 8, 18, 57, 7, 8),
        _edge_row(12, 20, 45, 7, 8, 18, 57, 7, 8),
        _edge_row(13, 20, 45, 7, 8, 18, 57, 7, 8),
        _edge_row(14, 20, 45, 7, 8, 18, 57, 7, 8),
        _edge_row(15, 20, 45, 7, 8, 18, 57, 7, 8),
        _edge_row(16, 20, 45, 7, 8, 18, 57, 8, 7),
        _edge_row(17, 20, 45, 8, 7, 18, 57, 8, 8),
        _edge_row(18, 20, 45, 8, 7, 18, 57, 8, 8),
        _edge_row(19, 20, 48, 8, 8, 18, 60, 8, 9),
        _edge_row(20, 20, 48, 8, 8, 18, 60, 8, 10),
        _edge_row(21, 20, 48, 9, 8, 18, 60, 8, 10),
        _edge_row(22, 20, 48, 9, 8, 18, 60, 9, 9),
        _edge_row(23, 20, 48, 9, 8, 18, 60, 9, 10),
        _edge_row(24, 20, 48, 9, 9, 18 + 1 / 4.0, 60, 9, 10),
        _edge_row(25, 20, 48, 9, 9, 18 + 3 / 4.0, 60, 9, 10),
        _edge_row(26, 20, 48, 10, 8, 19 + 1 / 4.0, 60, 9, 11),
        _edge_row(27, 20, 48, 10, 8, 19 + 3 / 4.0, 63, 10, 9),
        _edge_row(28, 20 + 1 / 2.0, 48, 10, 9, 20 + 1 / 2.0, 63, 10, 10),
        _edge_row(29, 21.0, 48, 10, 9, 21.0, 63, 10, 10),
        _edge_row(30, 21 + 1 / 2.0, 48, 10, 9, 21 + 1 / 2.0, 63, 10, 10),
        _edge_row(31, 22 + 1 / 4.0, 48, 10, 9, 22.0, 63, 10, 10),
        _edge_row(32, 22 + 3 / 4.0, 48, 10, 9, 22 + 3 / 4.0, 63, 10, 10),
        _edge_row(33, 23 + 1 / 4.0, 48, 10, 9, 23 + 1 / 4.0, 63, 10, 11),
        _edge_row(34, 23 + 3 / 4.0, 48, 10, 10, 23 + 3 / 4.0, 63, 10, 11),
        _edge_row(35, 24 + 1 / 4.0, 48, 10, 10, 24 + 1 / 4.0, 63, 10, 11),
        _edge_row(36, 25.0, 48, 10, 10, 25.0, 63, 10, 11),
        _edge_row(37, 25 + 1 / 2.0, 48, 10, 10, 25 + 1 / 2.0, 63, 10, 12),
        _edge_row(38, 26.0, 48, 10, 10, 26.0, 63, 10, 12),
    )
}


def edge_beam_design(span_ft: int) -> EdgeBeamDesign:
    """Look up the SB-1-24 edge-beam design for a span (feet, 11-38).

    Raises ``ValueError`` naming the valid spans otherwise."""
    try:
        return EDGE_BEAM_DESIGNS[int(span_ft)]
    except (KeyError, ValueError):
        raise ValueError(
            f"SB-1-24 tabulates spans 11-38 ft, not {span_ft!r}") from None


# ── layout ───────────────────────────────────────────────────────────────

import numpy as np


@dataclass(frozen=True)
class SlabBridgeInput:
    """Inputs for a single-span slab bridge.

    ``edge_condition`` selects the edge-beam schedule: ``"over_the_side"``
    (drainage over the fascia) or ``"parapet"`` (shallower edge beam under
    a concrete parapet, per the sheet's edge-beam option)."""

    span_ft: int
    width_ft: float
    skew_deg: float = 0.0
    edge_condition: str = "over_the_side"


class SlabBridgeComponent:
    """BridgeComponent implementation for a single-span slab bridge (SB-1-24)."""

    def __init__(self, inp: SlabBridgeInput):
        self.inp = inp
        self.layout = layout_slab_bridge(inp)

    def geometry(self) -> dict:
        """Returns the layout primitives for Rhino/Grasshopper."""
        return {
            "layout": self.layout,
            "span": self.inp.span_ft,
            "width": self.inp.width_ft,
            "skew": self.inp.skew_deg
        }

    def calculate_l1_envelope(self, *, samples: int = 41):
        """Calculates the L1 equivalent-strip moment envelope for the slab.

        This uses the pure-Python `girder_line_envelope` which applies HL-93
        live loads via influence lines and uniform dead loads, scaled by the
        AASHTO equivalent strip width.

        Returns
        -------
        tuple[list[float], dict[str, list[float]]]
            (stations, moments) ready for `place_splices` or results plotting.
        """
        from civilpy.structural.aashto.lrfd.distribution import slab_equivalent_strip
        from civilpy.structural.girder_pipeline import girder_line_envelope

        design = slab_design(self.inp.span_ft)
        # AASHTO LRFD 4.6.2.3: n_lanes for width.
        # SB-1-24 is for roadway width >= 24ft, so at least 2 lanes.
        n_lanes = int(math.floor(self.inp.width_ft / 12.0))
        # Strip width (E) in feet for one lane loaded.
        e_ft = slab_equivalent_strip(self.inp.span_ft, self.inp.width_ft, n_lanes,
                                     multi_lane=True, skew_deg=self.inp.skew_deg)

        # Girder Distribution Factor (GDF) for a 1-ft wide strip: 1 / E
        gdf = 1.0 / e_ft

        # Dead Loads (kip/ft for a 1-ft wide strip)
        # DC1: Slab weight (150 pcf) + 1" monolithic wearing surface.
        # Note: BDM says f'c=4500 psi. Concrete weight typically 150 pcf.
        t_tot_ft = (design.thickness_in) / 12.0
        dc1_klf = 1.0 * t_tot_ft * 0.150

        # DC2: Barrier/SDL. ODOT Standard barrier is ~475 lb/ft per side.
        # Distributed across the full width.
        dc2_klf = (2 * 0.475) / self.inp.width_ft

        # DW: Future Wearing Surface (60 psf)
        dw_klf = 0.060 * 1.0

        stations, moments = girder_line_envelope(
            supports=[0.0, self.inp.span_ft],
            dc1_klf=dc1_klf,
            dc2_klf=dc2_klf,
            dw_klf=dw_klf,
            n_sections=samples,
            gdf=gdf
        )

        return stations, moments

    def structural_model(self, level: str = "L1") -> "StructuralModel":
        """Returns a MIDAS-ready StructuralModel (L1 strip or L2 grillage)."""
        from civilpy.structural.structural_model import StructuralModel, LoadCase
        from civilpy.structural.aashto.lrfd.distribution import slab_equivalent_strip
        hub = StructuralModel()
        design = slab_design(int(self.inp.span_ft))

        if level == "L1":
            # 1. Nodes
            n1 = hub.add_node(0, 0, 0, label="Support_A")
            n2 = hub.add_node(self.inp.span_ft, 0, 0, label="Support_B")

            # 2. Element
            elem = hub.add_element(n1.id, n2.id,
                                   role="main_slab",
                                   member_type="beam",
                                   midas_type="BEAM",
                                   section=f"Slab_{design.thickness_in}in")

            # 3. Restraints
            hub.add_restraint(n1.id, preset="pin")
            hub.add_restraint(n2.id, preset="roller-v")

            # 4. Loads (L1 equivalent strip)
            n_lanes = int(math.floor(self.inp.width_ft / 12.0))
            e_ft = slab_equivalent_strip(self.inp.span_ft, self.inp.width_ft, n_lanes,
                                         multi_lane=True, skew_deg=self.inp.skew_deg)
            gdf = 1.0 / e_ft

            # Uniform loads on the beam (kip/ft)
            t_tot_ft = design.thickness_in / 12.0
            dc1_klf = t_tot_ft * 0.150 * gdf
            dc2_klf = ((2 * 0.475) / self.inp.width_ft) * gdf
            dw_klf = 0.060 * gdf

            hub.add_beam_load(elem.id, dc1_klf, case="DC1")
            hub.add_beam_load(elem.id, dc2_klf, case="DC2")
            hub.add_beam_load(elem.id, dw_klf, case="DW")

        elif level == "L2":
            # Refined grillage model (L2)
            # Create a mesh of beam elements
            # Longitudinal elements: 1ft spacing
            # Transverse elements: 4ft spacing approx
            dx = 2.0  # Longitudinal segments
            dy = 2.0  # Transverse spacing
            nx = int(math.ceil(self.inp.span_ft / dx))
            ny = int(math.ceil(self.inp.width_ft / dy))
            dx = self.inp.span_ft / nx
            dy = self.inp.width_ft / ny

            tan_skew = math.tan(math.radians(self.inp.skew_deg))

            nodes_grid = {} # (i, j) -> node
            for i in range(nx + 1):
                x_base = i * dx
                for j in range(ny + 1):
                    y = j * dy
                    x = x_base + y * tan_skew
                    nodes_grid[(i, j)] = hub.add_node(x, y, 0)

            t_tot_ft = design.thickness_in / 12.0
            dc1_area = t_tot_ft * 0.150  # kip/ft^2

            # Longitudinal elements
            for j in range(ny + 1):
                width = dy if (0 < j < ny) else 0.5 * dy
                dc1_klf = dc1_area * width
                for i in range(nx):
                    el = hub.add_element(nodes_grid[(i, j)].id, nodes_grid[(i+1, j)].id,
                                         role="longitudinal_strip", member_type="beam",
                                         midas_type="BEAM", section=f"Slab_{design.thickness_in}in")
                    hub.add_beam_load(el.id, dc1_klf, case="DC1")

            # Transverse elements
            for i in range(nx + 1):
                for j in range(ny):
                    hub.add_element(nodes_grid[(i, j)].id, nodes_grid[(i, j+1)].id,
                                   role="transverse_strip", member_type="beam",
                                   midas_type="BEAM", section=f"Slab_{design.thickness_in}in")

            # Supports at i=0 and i=nx
            for j in range(ny + 1):
                hub.add_restraint(nodes_grid[(0, j)].id, preset="pin")
                hub.add_restraint(nodes_grid[(nx, j)].id, preset="roller-v")

        elif level == "L3":
            # Full FEA model (L3) - Plate elements
            dx = 2.0
            dy = 2.0
            nx = int(math.ceil(self.inp.span_ft / dx))
            ny = int(math.ceil(self.inp.width_ft / dy))
            dx = self.inp.span_ft / nx
            dy = self.inp.width_ft / ny

            tan_skew = math.tan(math.radians(self.inp.skew_deg))

            nodes_grid = {}
            for i in range(nx + 1):
                x_base = i * dx
                for j in range(ny + 1):
                    y = j * dy
                    x = x_base + y * tan_skew
                    nodes_grid[(i, j)] = hub.add_node(x, y, 0)

            # Plate elements (4-node quads)
            for i in range(nx):
                for j in range(ny):
                    # Nodes in CCW order for MIDAS
                    quad_nodes = [
                        nodes_grid[(i, j)].id,
                        nodes_grid[(i+1, j)].id,
                        nodes_grid[(i+1, j+1)].id,
                        nodes_grid[(i, j+1)].id
                    ]
                    hub.add_element(quad_nodes[0], quad_nodes[1],
                                   role="slab_plate", midas_type="PLATE",
                                   section=f"Slab_{design.thickness_in}in",
                                   nodes=quad_nodes)

            # Supports
            for j in range(ny + 1):
                hub.add_restraint(nodes_grid[(0, j)].id, preset="pin")
                hub.add_restraint(nodes_grid[(nx, j)].id, preset="roller-v")

        return hub

    def reconcile_analysis(self, midas_results: dict | None = None) -> dict:
        """Compares pure-Python L1 results with MIDAS results.

        If `midas_results` is provided (e.g. from `MidasCivil.beam_forces`), it
        calculates the error/reconciliation between the two models.
        """
        stations, python_moments = self.calculate_l1_envelope()

        report = {
            "python": {
                "stations": stations,
                "moments": python_moments
            },
            "reconciliation": {}
        }

        if midas_results:
            # Placeholder for actual MIDAS result mapping
            # This would map MIDAS beam forces back to the L1 envelope stations
            report["midas"] = midas_results
            # report["reconciliation"]["max_moment_error"] = ...

        return report

    def extract_bearing_reactions(self, model: "StructuralModel") -> dict:
        """Extracts vertical reactions at supports from the StructuralModel results."""
        reactions = {"A": 0.0, "B": 0.0}
        # Look for nodes with labels "Support_A" and "Support_B" (from L1)
        # or nodes at x=0 and x=L (from L2/L3)
        for case in model.results.values():
            for node_id, force_vec in case.reactions.items():
                node = model.nodes[node_id]
                # force_vec: (FX, FY, FZ, MX, MY, MZ)
                fz = force_vec[2]
                if node.label == "Support_A" or math.isclose(node.x, 0.0, abs_tol=1e-3):
                    reactions["A"] += fz
                elif node.label == "Support_B" or math.isclose(node.x, self.inp.span_ft, abs_tol=1e-3):
                    reactions["B"] += fz
        
        return reactions


@dataclass(frozen=True)
class BarRun:
    mark: str
    size: int
    points: tuple[Point, ...]


@dataclass(frozen=True)
class SlabBridgeLayout:
    """The generated slab bridge.  ``outline`` is the skewed plan
    parallelogram at z = 0 (top of slab); the slab extends down
    ``thickness_in``.  ``bars`` are the A/B/M/N longitudinal runs."""

    inputs: SlabBridgeInput
    outline: tuple[Point, Point, Point, Point]
    thickness_in: float
    bridge_length_ft: float
    bars: tuple[BarRun, ...]
    edge_beam: EdgeBarSpec
    notes: tuple[str, ...] = field(default_factory=tuple)


def _bar_run(mark: str, size: int, spacing_in: float, width_ft: float,
            length_ft: float, z_ft: float, tan_skew: float,
            edge_clear_ft: float = 0.25) -> tuple[BarRun, ...]:
    """Evenly spaced longitudinal bars across ``width_ft``, each sheared by
    the skew (same convention as approach_slab / sleeper_slab)."""
    usable = width_ft - 2.0 * edge_clear_ft
    n = max(2, int(math.ceil(usable * 12.0 / spacing_in)) + 1)
    runs = []
    for i in range(n):
        y = edge_clear_ft + usable * i / (n - 1)
        u = y * tan_skew
        runs.append(BarRun(mark, size,
                           ((u, y, z_ft), (u + length_ft, y, z_ft))))
    return tuple(runs)


def layout_slab_bridge(inp: SlabBridgeInput) -> SlabBridgeLayout:
    """Generate a single-span slab bridge: plan outline, thickness, and
    the A/B/M/N longitudinal bar mats.

    Raises ``ValueError`` for an untabulated span, an unknown
    ``edge_condition``, or a skew beyond the sheet's 25 deg limit."""
    design = slab_design(inp.span_ft)
    edge = edge_beam_design(inp.span_ft)
    if inp.edge_condition not in ("over_the_side", "parapet"):
        raise ValueError(
            "SB-1-24 edge_condition is 'over_the_side' or 'parapet', "
            f"not {inp.edge_condition!r}")
    if abs(inp.skew_deg) > SKEW_MAX_DEG + 1e-9:
        raise ValueError(
            f"SB-1-24 is applicable for skew <= {SKEW_MAX_DEG:g} deg; "
            f"{inp.skew_deg:g} deg exceeds it")

    edge_spec = edge.over_the_side if inp.edge_condition == "over_the_side" \
        else edge.parapet
    W = inp.width_ft
    L = bridge_length_ft(inp.span_ft, inp.skew_deg)
    tan_skew = math.tan(math.radians(inp.skew_deg))
    T = design.thickness_in

    def pt(u: float, y: float) -> Point:
        return (u + y * tan_skew, y, 0.0)

    outline = (pt(0.0, 0.0), pt(0.0, W), pt(L, W), pt(L, 0.0))

    a_len = standard_hook_bar_length_ft(inp.span_ft)
    z_bot = -(T - 2.5) / 12.0     # bottom mat, ~2.5 in clear (sheet elevation)
    z_top = -2.5 / 12.0           # top mat, ~2.5 in clear

    bars = (
        _bar_run("A", design.a_bar.size, design.a_bar.spacing_in, W,
                a_len, z_bot, tan_skew)
        + _bar_run("B", design.b_bar.size, design.b_bar.spacing_in, W,
                  a_len, z_top, tan_skew)
        + _bar_run("M", design.m_bar.size, design.m_bar.spacing_in, W,
                  a_len, z_bot, tan_skew)
        + _bar_run("N", design.n_bar.size, design.n_bar.spacing_in, W,
                  a_len, z_top, tan_skew)
    )

    notes = (
        f"SB-1-24 single span slab bridge: span {inp.span_ft:g} ft, "
        f"T {T:g} in, width {W:g} ft, skew {inp.skew_deg:g} deg "
        f"({inp.edge_condition}), bridge length {L:.2f} ft",
        f"Edge beam: D {edge_spec.depth_in:g} in, X {edge_spec.taper_in:g} in, "
        f"{edge_spec.bar_count} x #{edge_spec.bar_size} "
        f"{'D' if inp.edge_condition == 'over_the_side' else 'E'}-bars",
        "Not modeled: edge-beam taper solid (D/X detail), bent A/B-bar "
        "ends near the abutments, U401/U402 edge-beam lap bars, camber, "
        "abutment diaphragm (see CPA-1-08), transverse/edge-beam "
        "reinforcing.",
    )

    return SlabBridgeLayout(
        inputs=inp,
        outline=outline,
        thickness_in=T,
        bridge_length_ft=L,
        bars=bars,
        edge_beam=edge_spec,
        notes=notes,
    )
