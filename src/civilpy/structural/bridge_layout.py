#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Parametric steel-girder bridge layout for the Rhino/Grasshopper front end.

Pure geometry/engineering layout — no Rhino imports — so the whole bridge
description is computable and testable outside Rhino.  A Grasshopper
component (see ``Notebooks/res``) feeds user inputs into
:func:`layout_bridge` and turns the returned primitives into Rhino
geometry; every primitive carries the ``gdr.*`` user-text tags the
:mod:`civilpy.structural.rhino_gdr` reader (and therefore the MIDAS
pipeline) consumes, so a generated model is immediately analyzable.

Engineering content comes from the sibling modules and is not duplicated
here: deck thickness/mats from the ODOT BDM standard designs
(:mod:`civilpy.structural.odot.deck_design`), haunches per BDM 309.3.5,
section dimensions from :func:`civilpy.structural.steel.W`, barriers from
the :mod:`civilpy.structural.odot.bridge_railing` SCD catalog.

Conventions (matching the gdr contract): plan frame with X = stations
along the layout centerline, Y = transverse (girder 1 at the lowest Y),
Z = up.  **Plan coordinates and lengths in feet; section dimensions in
inches** (names carry ``_in`` suffixes).  Z = 0 is the TOP OF DECK; the
structure hangs below it.  Skew is the angle (degrees) between a support
line and the perpendicular to the centerline — positive skew rotates
support lines counterclockwise in plan, so points at +Y shift toward +X.
Supports are parallel (constant skew).  Decks are flat (no crown or cross
slope yet) and deck plan edges stop at the end support lines.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural.odot import bridge_railing
from civilpy.structural.odot.deck_design import (
    Haunch,
    POLICY,
    StandardDeckDesign,
    minimum_deck_thickness,
    overhang_thickness,
    standard_deck_design,
    structural_design_thickness,
)
from civilpy.structural.steel import Rebar

Point = tuple[float, float, float]  # (x, y, z) feet


# ── inputs ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BridgeInput:
    """Everything a Grasshopper slider panel specifies.

    ``deck_thickness_in`` of ``None`` means "use the ODOT standard design"
    (BDM Figure 309-3, which also fixes the rebar mats); giving a value
    switches to a custom deck and skips the standard-design table (the
    BDM 309.3.1 minimum is still enforced).  ``railing`` is an SCD
    designation from the :mod:`~civilpy.structural.odot.bridge_railing`
    catalog (e.g. ``"SBR-1-20"``).
    """

    spans_ft: tuple[float, ...]
    girder_count: int
    girder_spacing_ft: float
    girder_label: str            # AISC W label, e.g. "W36X150"
    overhang_ft: float
    railing: str = "SBR-1-20"
    grade: str = "Grade 50"
    skew_deg: float = 0.0
    design_haunch_in: float = 2.0
    deck_thickness_in: float | None = None
    deck_fc_ksi: float = POLICY.f_c


# ── outputs ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GirderSection:
    """W-shape display dimensions (in), pulled from the AISC database."""

    label: str
    depth: float
    flange_width: float
    flange_thickness: float
    web_thickness: float
    fillet_k: float


@dataclass(frozen=True)
class GirderLine:
    line_no: int
    start: Point
    end: Point
    tags: dict[str, str]


@dataclass(frozen=True)
class BearingPoint:
    line_no: int
    station_index: int
    location: Point
    fixity: str
    tags: dict[str, str]


@dataclass(frozen=True)
class HaunchRun:
    """One haunch prism: the girder line at deck-soffit level plus the
    section (width x depth, in) to extrude along it."""

    line_no: int
    start: Point
    end: Point
    width_in: float
    depth_in: float


@dataclass(frozen=True)
class RebarSet:
    """One family of deck bars for the generator to instantiate.

    ``direction`` is ``"transverse"`` or ``"longitudinal"``; ``mat`` is
    ``"top"`` / ``"bottom"``.  ``depth_in`` is the bar centerline depth
    below the top of deck.  ``angle_deg`` rotates transverse bars in plan
    (0 = perpendicular to the centerline; the BDM 309.3.4.2 skew rule is
    applied by the layout).  ``extent`` is ``"deck"`` for full-width/length
    mats or ``"overhang"`` for the additional overhang bars, which run
    from each deck edge to ``overhang_cutoff_in`` beyond the fascia girder
    centerline.
    """

    name: str
    direction: str
    mat: str
    size: int
    spacing_in: float
    depth_in: float
    angle_deg: float = 0.0
    extent: str = "deck"
    overhang_cutoff_in: float | None = None


@dataclass(frozen=True)
class BarrierRun:
    designation: str
    edge: str            # "left" (+Y) or "right" (-Y)
    line: tuple[Point, Point]  # along the deck edge at deck-top level
    height_in: float | None
    base_width_in: float | None
    weight_plf: float | None


@dataclass(frozen=True)
class DeckSlab:
    """Plan outline (counterclockwise, z = 0 at deck top), thicknesses, and
    the mats.  ``outline`` corners run girder-1 start edge -> girder-N
    start edge -> girder-N end edge, honoring skew."""

    outline: tuple[Point, Point, Point, Point]
    thickness_in: float
    overhang_thickness_in: float
    structural_thickness_in: float
    rebar: tuple[RebarSet, ...]


@dataclass(frozen=True)
class BridgeLayout:
    """The full generated bridge: geometry primitives plus the document
    tags (``doc_tags``) the ``.3dm`` must carry for the Python reader."""

    inputs: BridgeInput
    section: GirderSection
    effective_span_ft: float
    girders: tuple[GirderLine, ...]
    bearings: tuple[BearingPoint, ...]
    haunches: tuple[HaunchRun, ...]
    deck: DeckSlab
    barriers: tuple[BarrierRun, ...]
    standard_design: StandardDeckDesign | None
    doc_tags: dict[str, str] = field(default_factory=dict)

    @property
    def total_length_ft(self) -> float:
        return sum(self.inputs.spans_ft)

    @property
    def deck_width_ft(self) -> float:
        n, s = self.inputs.girder_count, self.inputs.girder_spacing_ft
        return (n - 1) * s + 2.0 * self.inputs.overhang_ft


# ── helpers ───────────────────────────────────────────────────────────────

def girder_section(label: str) -> GirderSection:
    """Resolve an AISC W label to display dimensions via ``steel.W``."""
    from civilpy.structural import steel

    w = steel.W(label)
    k = getattr(w, "k_design", None)
    return GirderSection(
        label=label,
        depth=float(w.depth.magnitude),
        flange_width=float(w.flange_width.magnitude),
        flange_thickness=float(w.flange_thickness.magnitude),
        web_thickness=float(w.web_thickness.magnitude),
        fillet_k=float(k.magnitude) if k is not None else 0.0,
    )


def effective_span_ft(spacing_ft: float, section: GirderSection) -> float:
    """Effective deck span (ft) per LRFD 9.7.2.3 for slabs on steel
    girders: clear distance between flange tips plus the flange overhang
    (tip to web face) — i.e. ``S - bf/2 - tw/2``."""
    s = spacing_ft - (section.flange_width / 2.0
                      + section.web_thickness / 2.0) / 12.0
    if s <= 0:
        raise ValueError("girder flanges overlap: spacing too small")
    return s


def default_fixity(station_index: int, station_count: int) -> str:
    """Bearing-fixity starting point, mirroring the C# plugin's rule: a
    single span is fixed at its first bearing; a continuous unit at the
    interior support nearest mid-length; everything else expansion."""
    fixed = 0 if station_count == 2 else station_count // 2
    return "fixed" if station_index == fixed else "expansion"


def railing_by_scd(scd: str) -> bridge_railing.BridgeRailing:
    """First cataloged railing on the given SCD (e.g. ``"SBR-1-20"``)."""
    for r in bridge_railing.BRIDGE_RAILINGS.values():
        if r.scd == scd:
            return r
    raise ValueError(f"no cataloged railing on SCD {scd!r}")


# ── the generator ─────────────────────────────────────────────────────────

def layout_bridge(inp: BridgeInput) -> BridgeLayout:
    """Generate the full bridge layout from the Grasshopper-level inputs.

    Raises ``ValueError`` when the inputs violate the ODOT standard-design
    assumptions (unless a custom ``deck_thickness_in`` is given) or are
    geometrically impossible.
    """
    if not inp.spans_ft or any(s <= 0 for s in inp.spans_ft):
        raise ValueError("spans must be positive")
    if inp.girder_count < 2:
        raise ValueError("at least two girder lines are required")
    if inp.girder_spacing_ft <= 0 or inp.overhang_ft < 0:
        raise ValueError("spacing must be positive and overhang non-negative")
    if abs(inp.skew_deg) >= 60.0:
        raise ValueError("skew beyond 60 degrees is not supported")

    section = girder_section(inp.girder_label)
    eff_span = effective_span_ft(inp.girder_spacing_ft, section)
    tan_skew = math.tan(math.radians(inp.skew_deg))

    # Deck thickness + mats: ODOT standard design unless overridden.
    design: StandardDeckDesign | None
    if inp.deck_thickness_in is None:
        design = standard_deck_design(
            eff_span,
            railing=inp.railing,
            beam_lines=inp.girder_count,
            beam_spacing_ft=inp.girder_spacing_ft,
            overhang_ft=inp.overhang_ft,
        )
        t_deck = design.deck_thickness
        t_overhang = overhang_thickness(design, inp.railing)
    else:
        design = None
        t_min = minimum_deck_thickness(eff_span)
        if inp.deck_thickness_in < t_min:
            raise ValueError(
                f"deck thickness {inp.deck_thickness_in} in is below the "
                f"BDM 309.3.1 minimum of {t_min} in for a {eff_span:.2f} ft "
                "effective span"
            )
        t_deck = inp.deck_thickness_in
        t_overhang = t_deck + 2.0

    haunch = Haunch(depth=inp.design_haunch_in,
                    flange_width=section.flange_width)

    # Elevations (ft, deck top = 0).
    z_soffit = -t_deck / 12.0
    z_girder_top = z_soffit - haunch.depth / 12.0
    z_girder_bot = z_girder_top - section.depth / 12.0

    # Girder lines, bearings, haunches.
    total = sum(inp.spans_ft)
    stations = [0.0]
    for s in inp.spans_ft:
        stations.append(stations[-1] + s)

    girders, bearings, haunches = [], [], []
    for g in range(inp.girder_count):
        y = g * inp.girder_spacing_ft
        line_no = g + 1
        shift = y * tan_skew
        start = (stations[0] + shift, y, z_girder_top)
        end = (stations[-1] + shift, y, z_girder_top)
        tags = {
            "gdr.kind": "girder",
            "gdr.line": str(line_no),
            "gdr.shape": inp.girder_label,
            "gdr.grade": inp.grade,
        }
        girders.append(GirderLine(line_no, start, end, tags))
        haunches.append(HaunchRun(
            line_no,
            (start[0], y, z_soffit), (end[0], y, z_soffit),
            width_in=section.flange_width, depth_in=haunch.depth,
        ))
        for i, st in enumerate(stations):
            fixity = default_fixity(i, len(stations))
            bearings.append(BearingPoint(
                line_no, i, (st + shift, y, z_girder_bot), fixity,
                tags={
                    "gdr.kind": "support",
                    "gdr.line": str(line_no),
                    "gdr.fixity": fixity,
                },
            ))

    # Deck outline (skewed parallelogram covering overhangs).
    y_lo = -inp.overhang_ft
    y_hi = (inp.girder_count - 1) * inp.girder_spacing_ft + inp.overhang_ft
    outline = (
        (stations[0] + y_lo * tan_skew, y_lo, 0.0),
        (stations[0] + y_hi * tan_skew, y_hi, 0.0),
        (stations[-1] + y_hi * tan_skew, y_hi, 0.0),
        (stations[-1] + y_lo * tan_skew, y_lo, 0.0),
    )

    # Rebar sets from the standard design (custom decks carry no mats —
    # they are designed per BDM 309.3.2, e.g. deck_strip_checks).
    rebar: list[RebarSet] = []
    if design is not None:
        # BDM 309.3.4.2: skew >= 15 deg -> transverse steel perpendicular
        # to the centerline; below that it may follow the abutments.
        bar_angle = inp.skew_deg if abs(inp.skew_deg) < 15.0 else 0.0

        def dia(size: int) -> float:
            return float(Rebar(size).diameter.magnitude)

        d_lt = dia(design.longitudinal_top.size)
        d_tt = dia(design.transverse_top.size)
        d_tb = dia(design.transverse_bottom.size)
        d_lb = dia(design.longitudinal_bottom.size)
        cover_top, cover_bot = POLICY.top_cover, POLICY.bottom_cover

        # BDM 309.3.4.1: longitudinal secondary bars sit ABOVE the top
        # transverse primary; bottom transverse sits on the bottom cover.
        rebar = [
            RebarSet("longitudinal top", "longitudinal", "top",
                     design.longitudinal_top.size,
                     design.longitudinal_top.spacing,
                     cover_top + d_lt / 2.0),
            RebarSet("transverse top", "transverse", "top",
                     design.transverse_top.size,
                     design.transverse_top.spacing,
                     cover_top + d_lt + d_tt / 2.0, angle_deg=bar_angle),
            RebarSet("transverse bottom", "transverse", "bottom",
                     design.transverse_bottom.size,
                     design.transverse_bottom.spacing,
                     t_deck - cover_bot - d_tb / 2.0, angle_deg=bar_angle),
            RebarSet("longitudinal bottom", "longitudinal", "bottom",
                     design.longitudinal_bottom.size,
                     design.longitudinal_bottom.spacing,
                     t_deck - cover_bot - d_tb - d_lb / 2.0),
        ]
        if design.overhang_bar_size is not None:
            rebar.append(RebarSet(
                "additional overhang", "transverse", "top",
                design.overhang_bar_size,
                design.transverse_top.spacing,
                cover_top + d_lt + d_tt / 2.0 + dia(design.overhang_bar_size),
                angle_deg=bar_angle, extent="overhang",
                overhang_cutoff_in=design.overhang_cutoff,
            ))

    deck = DeckSlab(
        outline=outline,
        thickness_in=t_deck,
        overhang_thickness_in=t_overhang,
        structural_thickness_in=structural_design_thickness(t_deck),
        rebar=tuple(rebar),
    )

    # Barriers along both edges.
    rail = railing_by_scd(inp.railing)
    barriers = (
        BarrierRun(inp.railing, "right", (outline[0], outline[3]),
                   rail.height, rail.base_width, rail.weight_per_ft),
        BarrierRun(inp.railing, "left", (outline[1], outline[2]),
                   rail.height, rail.base_width, rail.weight_per_ft),
    )

    # Document-level tags for the rhino_gdr reader (structural thickness,
    # per the contract; effective flange width = interior girder spacing,
    # LRFD 4.6.2.6).
    doc_tags = {
        "gdr.deck_t": f"{structural_design_thickness(t_deck):g}",
        "gdr.deck_weff": f"{inp.girder_spacing_ft * 12.0:g}",
        "gdr.deck_fc": f"{inp.deck_fc_ksi:g}",
    }

    return BridgeLayout(
        inputs=inp,
        section=section,
        effective_span_ft=eff_span,
        girders=tuple(girders),
        bearings=tuple(bearings),
        haunches=tuple(haunches),
        deck=deck,
        barriers=barriers,
        standard_design=design,
        doc_tags=doc_tags,
    )


# ── rebar instantiation ───────────────────────────────────────────────────

@dataclass(frozen=True)
class RebarSegment:
    """One physical bar: a straight segment at the set's depth."""

    start: Point
    end: Point
    rebar_set: RebarSet


def _clip_interval(lo: float, hi: float, a: float, b: float,
                   c_lo: float, c_hi: float) -> tuple[float, float]:
    """Intersect the t-interval [lo, hi] with c_lo <= a + b*t <= c_hi."""
    if abs(b) < 1e-12:
        return (lo, hi) if c_lo <= a <= c_hi else (1.0, 0.0)
    t0, t1 = (c_lo - a) / b, (c_hi - a) / b
    if t0 > t1:
        t0, t1 = t1, t0
    return max(lo, t0), min(hi, t1)


def deck_rebar_segments(layout: BridgeLayout,
                        side_cover_in: float = 2.0) -> list[RebarSegment]:
    """Instantiate every deck bar as a straight segment (feet, deck-top
    z = 0 frame), clipped to the deck plan inset by ``side_cover_in`` on
    the edges.  The Grasshopper generator draws these directly; nothing
    here needs Rhino.

    The deck plan is the skewed parallelogram ``y in [y_lo, y_hi]``,
    ``u = x - y*tan(skew) in [0, L]``.
    """
    inp = layout.inputs
    tan_skew = math.tan(math.radians(inp.skew_deg))
    cos_skew = math.cos(math.radians(inp.skew_deg))
    c = side_cover_in / 12.0
    y_lo = -inp.overhang_ft
    y_hi = (inp.girder_count - 1) * inp.girder_spacing_ft + inp.overhang_ft
    length = layout.total_length_ft
    # edge-inset bounds: sides in y, skewed ends in u (perpendicular inset)
    y0, y1 = y_lo + c, y_hi - c
    u0, u1 = c / cos_skew, length - c / cos_skew
    big = length + (y_hi - y_lo) * (1.0 + abs(tan_skew))

    segments: list[RebarSegment] = []
    for rs in layout.deck.rebar:
        z = -rs.depth_in / 12.0
        step = rs.spacing_in / 12.0

        if rs.direction == "longitudinal":
            # constant-y bars: u from u0 to u1 -> x = u + y*tan
            y = y0
            while y <= y1 + 1e-9:
                segments.append(RebarSegment(
                    (u0 + y * tan_skew, y, z), (u1 + y * tan_skew, y, z), rs))
                y += step
            continue

        # transverse bars along d = (sin a, cos a), spaced perpendicular to
        # themselves -> step along u is spacing / cos(angle - skew)-ish;
        # angle is 0 (perpendicular) or = skew (parallel to abutments), so
        # stepping in u by spacing / cos(angle) keeps the true c/c spacing.
        a = math.radians(rs.angle_deg)
        d = (math.sin(a), math.cos(a))
        step_u = step / math.cos(a)

        if rs.extent == "overhang":
            cutoff_ft = (rs.overhang_cutoff_in or 0.0) / 12.0
            spans_y = (
                (y0, min(y_lo + inp.overhang_ft + cutoff_ft, y1)),   # right
                (max(y_hi - inp.overhang_ft - cutoff_ft, y0), y1),   # left
            )
        else:
            spans_y = ((y0, y1),)

        for band_lo, band_hi in spans_y:
            if band_hi <= band_lo:
                continue
            u = u0 + step_u / 2.0
            while u <= u1 + 1e-9:
                # bar through (x0, 0) with x0 chosen so u(point) = u at y=0
                o = (u, 0.0, z)
                t_lo, t_hi = _clip_interval(
                    -big, big, o[1], d[1], band_lo, band_hi)
                # u(t) = (x - y*tan) = u + t*(sin a - cos a * tan)
                t_lo, t_hi = _clip_interval(
                    t_lo, t_hi, u, d[0] - d[1] * tan_skew, u0, u1)
                if t_hi > t_lo:
                    segments.append(RebarSegment(
                        (o[0] + t_lo * d[0], t_lo * d[1], z),
                        (o[0] + t_hi * d[0], t_hi * d[1], z), rs))
                u += step_u
    return segments
