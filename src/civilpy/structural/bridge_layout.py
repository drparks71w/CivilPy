#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Parametric steel-girder bridge layout for the Rhino/Grasshopper front end.

Pure geometry/engineering layout — no Rhino imports — so the whole bridge
description is computable and testable outside Rhino.  A Grasshopper
component (see ``Notebooks/Rhino Components``) feeds user inputs into
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
Supports are parallel (constant skew) and deck plan edges stop at the end
support lines.  The deck is **crowned**: the top surface peaks at the
roadway crown (``crown_offset_ft``, default mid-width) and falls at
``cross_slope_pct`` to each side, and everything hung from it — soffit,
haunches, girder seats, bearing seats, and both rebar mats — follows that
surface.  Z = 0 is the top of deck *at the crown*.
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
    cross_slope_pct: float = 2.0
    """Deck cross slope, percent. The roadway crowns at ``crown_offset_ft`` and
    falls this grade to each side, so the girder **seat elevations vary across
    the width** (they follow the crown/cross-slope, at full precision -- not
    rounded).  ``0.0`` is a flat deck."""
    crown_offset_ft: float | None = None
    """Transverse offset (ft, girder 1 at 0) of the roadway crown / high point.
    ``None`` centers it on the girder group."""
    composite: bool = True
    """Whether the deck acts compositely with the girders (shear studs / rebar
    extending into the deck).  Drives the deck-to-girder connection in the
    refined-grillage analysis model (:func:`grillage_model_from_layout`): a
    composite deck is rigidly tied to the girders (full plane-section action);
    a non-composite deck bears on the girders vertically but is free to slip
    longitudinally.  Both are used in practice, so the design engineer sets
    it -- it materially changes the girder demands for steel *and* prestressed
    concrete superstructures."""


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
    section (width x depth, in) to extrude along it.

    The square cross-section is deliberate: BDM 309.3.5 (2020 Ed.) says
    "Detail the sides of the haunch as vertical and aligned with the edges
    of the top flange" — no sloped forming at any depth — with a 2 in
    minimum design haunch (see Figures 309-7/309-8)."""

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
    """Plan outline (counterclockwise, each corner at the local deck-top
    elevation of the crowned surface), thicknesses, and the mats.
    ``outline`` corners run girder-1 start edge -> girder-N start edge ->
    girder-N end edge, honoring skew."""

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

    @property
    def crown_y_ft(self) -> float:
        """Transverse offset of the roadway crown (girder 1 at y = 0)."""
        inp = self.inputs
        if inp.crown_offset_ft is not None:
            return inp.crown_offset_ft
        return (inp.girder_count - 1) * inp.girder_spacing_ft / 2.0

    def deck_top_z(self, y: float) -> float:
        """Top-of-deck elevation (ft) at transverse offset ``y``: 0 at the
        crown, falling at ``cross_slope_pct`` to each side."""
        return -abs(y - self.crown_y_ft) * self.inputs.cross_slope_pct / 100.0

    def deck_soffit_z(self, y: float) -> float:
        """Deck-soffit elevation (ft) at ``y``, parallel to the top surface
        (uniform slab; the overhang thickening past the fascia girders is
        additional and belongs to :meth:`deck_profile_yz`)."""
        return self.deck_top_z(y) - self.deck.thickness_in / 12.0

    def deck_profile_yz(self) -> tuple[tuple[float, float], ...]:
        """Closed deck cross-section as ``(y, z)`` pairs — the crowned top,
        the parallel soffit, and the thickened overhangs per BDM Figure
        309-4: the overhang soffit runs at ``overhang_thickness_in`` below
        the top (parallel to it) from the deck edge to the **outboard
        top-flange tip** of the fascia girder, where it steps up to the
        uniform ``thickness_in`` soffit.  With the standard ``t + 2`` in
        overhang and a 2 in design haunch that step lands exactly at the
        flange-top / haunch-bottom plane, reproducing the figure.  Order:
        along the top from ``y_lo`` to ``y_hi`` (crown included when
        interior), then back along the soffit.  A backend maps ``(y, z)``
        into 3D at each bridge end (``x = station + y*tan(skew)``) and
        lofts the two profiles into the deck solid.
        """
        inp = self.inputs
        y_lo = -inp.overhang_ft
        y_hi = (inp.girder_count - 1) * inp.girder_spacing_ft + inp.overhang_ft
        half_bf = self.section.flange_width / 2.0 / 12.0
        # overhang/uniform break: outboard flange tip, kept inside the edge
        y_b1 = max(min(-half_bf, 0.0), y_lo)
        y_bn = min((inp.girder_count - 1) * inp.girder_spacing_ft + half_bf,
                   y_hi)
        t = self.deck.thickness_in / 12.0
        t_oh = self.deck.overhang_thickness_in / 12.0
        crown = self.crown_y_ft

        top_ys = [y_lo, y_hi]
        if y_lo < crown < y_hi:
            top_ys.insert(1, crown)
        top = [(y, self.deck_top_z(y)) for y in top_ys]

        # soffit walked back from y_hi to y_lo: thick overhang, step at the
        # flange tip, uniform slab (with crown break) between the tips
        mid_ys = sorted({y_b1, y_bn} | ({crown} if y_b1 < crown < y_bn
                                        else set()), reverse=True)
        bot: list[tuple[float, float]] = []
        if y_hi > y_bn + 1e-9:
            bot += [(y_hi, self.deck_top_z(y_hi) - t_oh),
                    (y_bn, self.deck_top_z(y_bn) - t_oh)]
        bot += [(y, self.deck_top_z(y) - t) for y in mid_ys]
        if y_lo < y_b1 - 1e-9:
            bot += [(y_b1, self.deck_top_z(y_b1) - t_oh),
                    (y_lo, self.deck_top_z(y_lo) - t_oh)]
        return tuple(top + bot)


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

    # Elevations (ft): deck top = 0 AT THE CROWN, and the whole section —
    # soffit, girder seats, bearing seats — hangs from the local deck
    # surface, so seat elevations vary across the width.
    cross = inp.cross_slope_pct / 100.0
    crown_y = (inp.crown_offset_ft if inp.crown_offset_ft is not None
               else (inp.girder_count - 1) * inp.girder_spacing_ft / 2.0)

    def top_z(y: float) -> float:
        return -abs(y - crown_y) * cross

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
        z_soffit = top_z(y) - t_deck / 12.0
        z_girder_top = z_soffit - haunch.depth / 12.0
        z_girder_bot = z_girder_top - section.depth / 12.0
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

    # Deck outline (skewed parallelogram covering overhangs); each corner
    # sits on the crowned top surface at its own y.
    y_lo = -inp.overhang_ft
    y_hi = (inp.girder_count - 1) * inp.girder_spacing_ft + inp.overhang_ft
    outline = (
        (stations[0] + y_lo * tan_skew, y_lo, top_z(y_lo)),
        (stations[0] + y_hi * tan_skew, y_hi, top_z(y_hi)),
        (stations[-1] + y_hi * tan_skew, y_hi, top_z(y_hi)),
        (stations[-1] + y_lo * tan_skew, y_lo, top_z(y_lo)),
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
    """One physical bar: a polyline at the set's depth below the **local**
    deck surface, so bars follow the crown/cross-slope.  ``points`` has two
    vertices for a straight bar and three when a transverse bar crosses the
    crown (the crank at the high point); ``start``/``end`` are the first and
    last vertices."""

    points: tuple[Point, ...]
    rebar_set: RebarSet

    @property
    def start(self) -> Point:
        return self.points[0]

    @property
    def end(self) -> Point:
        return self.points[-1]

    @property
    def length_ft(self) -> float:
        return sum(math.dist(a, b)
                   for a, b in zip(self.points[:-1], self.points[1:]))


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
    """Instantiate every deck bar (feet), clipped to the deck plan inset by
    ``side_cover_in`` on the edges.  The Grasshopper generator draws these
    directly; nothing here needs Rhino.

    Bars sit ``depth_in`` below the **local** deck surface, so both mats
    follow the crown/cross-slope and stay inside the slab (a level bar
    would exit the soffit at the crown and the top surface at the edges).
    A transverse bar whose run crosses the crown is emitted as one
    3-vertex polyline cranked at the high point.

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
    crown_y = layout.crown_y_ft
    crowned = inp.cross_slope_pct != 0.0

    def bar_z(y: float, depth_in: float) -> float:
        return layout.deck_top_z(y) - depth_in / 12.0

    segments: list[RebarSegment] = []
    for rs in layout.deck.rebar:
        step = rs.spacing_in / 12.0

        if rs.direction == "longitudinal":
            # constant-y bars: u from u0 to u1 -> x = u + y*tan; constant y
            # means constant elevation on the crowned surface
            y = y0
            while y <= y1 + 1e-9:
                z = bar_z(y, rs.depth_in)
                segments.append(RebarSegment((
                    (u0 + y * tan_skew, y, z),
                    (u1 + y * tan_skew, y, z)), rs))
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
                t_lo, t_hi = _clip_interval(
                    -big, big, 0.0, d[1], band_lo, band_hi)
                # u(t) = (x - y*tan) = u + t*(sin a - cos a * tan)
                t_lo, t_hi = _clip_interval(
                    t_lo, t_hi, u, d[0] - d[1] * tan_skew, u0, u1)
                if t_hi > t_lo:
                    def vertex(t: float) -> Point:
                        y = t * d[1]
                        return (u + t * d[0], y, bar_z(y, rs.depth_in))

                    ts = [t_lo, t_hi]
                    if crowned and d[1] > 1e-12:
                        t_c = crown_y / d[1]     # param where the bar crosses
                        if t_lo + 1e-9 < t_c < t_hi - 1e-9:
                            ts.insert(1, t_c)    # crank at the crown
                    segments.append(RebarSegment(
                        tuple(vertex(t) for t in ts), rs))
                u += step_u
    return segments


# ── layout -> canonical StructuralModel hub (the analysis/MIDAS spoke) ───────

CONCRETE_UNIT_WT_KCF = 0.150
FWS_KSF = 0.060                     # ODOT future wearing surface, 60 psf
#: Preliminary concrete-parapet weight per foot of barrier height, lb/ft/ft,
#: used only when the SCD catalog has no tabulated ``weight_per_ft``.  Calibrated
#: so a 42 in single-slope (ODOT SBR-1) comes out ~455 plf; replace with the
#: real barrier weight for final design.
NOMINAL_PARAPET_PLF_PER_FT = 130.0


def _barrier_weight_plf(barrier) -> float | None:
    """Barrier weight (lb/ft): the cataloged value, or a preliminary estimate
    from the barrier height (:data:`NOMINAL_PARAPET_PLF_PER_FT`) when the SCD
    carries none.  ``None`` only if neither a weight nor a height is known."""
    if barrier.weight_plf not in (None, 0.0):
        return barrier.weight_plf
    if barrier.height_in:
        return NOMINAL_PARAPET_PLF_PER_FT * barrier.height_in / 12.0
    return None


def _girder_weight_plf(label: str) -> float:
    """Nominal weight (lb/ft) of an AISC W-shape from its label: the number
    after ``X`` (``W36X150`` -> 150), which is the section's weight per foot by
    the AISC naming convention.  Falls back to the ``steel.W`` database when the
    label is not in the ``WxxXyyy`` form."""
    try:
        return float(label.upper().split("X")[1])
    except (IndexError, ValueError):
        from civilpy.structural import steel
        w = steel.W(label)
        return float(getattr(w, "weight").magnitude)


def _tributary_widths(inp: "BridgeInput") -> list[float]:
    """Deck tributary width (ft) carried by each girder line: interior girders
    take the full spacing, fascia girders take half the spacing plus their
    overhang."""
    n, s, oh = inp.girder_count, inp.girder_spacing_ft, inp.overhang_ft
    trib = []
    for g in range(n):
        if g == 0 or g == n - 1:
            trib.append(oh + s / 2.0)
        else:
            trib.append(s)
    return trib


def girder_line_loads(layout: "BridgeLayout", girder_index: int) -> dict:
    """Uniform dead loads (klf, positive = downward) on one girder line.

    ``girder_index`` is 0-based (0 = first fascia).  Returns ``{"dc1", "dc2",
    "dw"}``: DC1 = girder self-weight + wet deck slab on the girder's tributary
    width; DC2 = the barrier weight, on fascia girders only; DW = future
    wearing surface on the tributary width.  These are the per-line loads the
    hub applies and the native line-girder envelope (``girder_pipeline``)
    consumes -- preliminary magnitudes (no haunch/cross-slope), same basis as
    :func:`structural_model_from_layout`.
    """
    inp = layout.inputs
    n = inp.girder_count
    if not 0 <= girder_index < n:
        raise IndexError(f"girder_index {girder_index} out of range 0..{n - 1}")
    trib = _tributary_widths(inp)[girder_index]
    t_deck_ft = layout.deck.thickness_in / 12.0
    dc1 = (_girder_weight_plf(inp.girder_label) / 1000.0
           + CONCRETE_UNIT_WT_KCF * t_deck_ft * trib)
    dw = FWS_KSF * trib
    dc2 = 0.0
    if girder_index in (0, n - 1):
        edge = "right" if girder_index == 0 else "left"
        for br in layout.barriers:
            if br.edge == edge:
                w = _barrier_weight_plf(br)
                if w:
                    dc2 += w / 1000.0
    return {"dc1": dc1, "dc2": dc2, "dw": dw}


def structural_model_from_layout(layout: "BridgeLayout", *,
                                 diaphragms: bool = True,
                                 dead_loads: bool = True):
    """Build the canonical :class:`StructuralModel` hub straight from a
    :class:`BridgeLayout` -- no Rhino ``.3dm`` round-trip.

    This is the faithful full-bridge analysis model the MIDAS spoke consumes
    (via :func:`civilpy.structural.midas_models.midas_payloads`): **every**
    girder line is a continuous chain of beam elements broken at every support
    station, each carrying its resolved AISC section and steel grade; each
    bearing becomes a 6-DOF restraint (fixed or expansion) on its girder node;
    and, when ``diaphragms`` is set, a transverse beam ties adjacent girders at
    every support line.  Contrast the equivalent-strip slab model -- here the
    whole grid goes to MIDAS, so it can host traffic lanes for a moving-load run.

    With ``dead_loads`` the three dead-load cases are applied as downward
    (negative ``GZ``) uniform beam loads on the girder elements:

    * ``DC1`` (non-composite): girder self-weight + the wet deck slab on each
      girder's tributary width,
    * ``DC2`` (composite SDL): each barrier's weight on its fascia girder,
    * ``DW``: future wearing surface (:data:`FWS_KSF`) on the tributary width.

    Haunch weight, cross-slope, and the exact wearing-surface extent (roadway
    only) are preliminary-level approximations; refine per BDM for final design.

    Returns the :class:`StructuralModel` (units kips/ft).
    """
    from civilpy.structural.structural_model import StructuralModel, Units

    inp = layout.inputs
    model = StructuralModel(units=Units(force="kips", length="ft"))

    # support stations along the layout centerline
    stations = [0.0]
    for s in inp.spans_ft:
        stations.append(stations[-1] + s)
    tan_skew = math.tan(math.radians(inp.skew_deg))

    # nodes + girder elements, one continuous chain per girder line
    node_grid: dict[tuple[int, int], str] = {}   # (girder, station idx) -> id
    girder_elems: dict[int, list[str]] = {}
    for gl in layout.girders:
        g = gl.line_no - 1
        y = g * inp.girder_spacing_ft
        z = gl.start[2]
        shift = y * tan_skew
        for i, st in enumerate(stations):
            node_grid[(g, i)] = model.add_node(
                st + shift, y, z, label=f"G{gl.line_no}_S{i}").id
        elems = []
        for i in range(len(stations) - 1):
            e = model.add_element(
                node_grid[(g, i)], node_grid[(g, i + 1)], role="girder",
                midas_type="BEAM", section=gl.tags.get("gdr.shape"),
                material=inp.grade)
            e.metadata["gdr.line"] = str(gl.line_no)
            elems.append(e.id)
        girder_elems[g] = elems

    # bearings -> restraints on the girder node at each support station
    for bp in layout.bearings:
        g = bp.line_no - 1
        nid = node_grid.get((g, bp.station_index))
        if nid is None:
            continue
        dof = {"fix_x": True, "fix_y": True, "fix_z": True} if bp.fixity == "fixed" \
            else {"fix_x": False, "fix_y": True, "fix_z": True}
        model.add_restraint(nid, **dof).preset = bp.fixity

    # transverse diaphragms between adjacent girders at every support line
    if diaphragms:
        for g in range(inp.girder_count - 1):
            for i in range(len(stations)):
                a, b = node_grid.get((g, i)), node_grid.get((g + 1, i))
                if a and b:
                    model.add_element(a, b, role="diaphragm",
                                      midas_type="BEAM").metadata[
                        "gdr.kind"] = "diaphragm"

    if dead_loads:
        for g, elems in girder_elems.items():
            w = girder_line_loads(layout, g)
            for eid in elems:
                model.add_beam_load(eid, -w["dc1"], case="DC1")
                model.add_beam_load(eid, -w["dw"], case="DW")
                if w["dc2"]:
                    model.add_beam_load(eid, -w["dc2"], case="DC2")

    return model


def grillage_model_from_layout(layout: "BridgeLayout", *,
                               composite: bool | None = None,
                               seg_target_ft: float | None = None,
                               dead_loads: bool = True,
                               girder_subset: list[int] | None = None):
    """Build the **refined-grillage** hub: bare-steel girder beams plus a
    physical deck of plate elements, tied together with rigid links.

    This is the "deck as plate, girder as frame" model MIDAS recommends when
    the full deck surface is needed (moving-load traffic lanes) -- unlike
    :func:`structural_model_from_layout`, which is a line-girder grid with no
    deck.  The deck's longitudinal stiffness lives entirely in the plate
    elements and the girders stay bare steel, so **the deck stiffness is never
    double-counted** (the trap of pairing a composite girder *section* with
    deck plates).

    The ``composite`` toggle (defaulting to ``layout.inputs.composite``) sets
    the deck-to-girder connection, mirroring whether the real bridge has shear
    studs / rebar extending into the deck:

    * **composite** -- a fully rigid link (all 6 DOF) at every deck node over a
      girder, so slab and girder share plane sections (transformed-section
      action emerges from the geometry).
    * **non-composite** -- the deck bears on the girders vertically and is
      located transversely/rotationally, but longitudinal slip (DX) is free, so
      the slab adds no composite flexural stiffness to the girder; a single
      longitudinal anchor at the fixed-bearing line removes rigid-body drift.

    ``seg_target_ft`` is the target longitudinal plate length (default: the
    girder spacing, giving roughly square plates); each span is divided into a
    whole number of segments nearest that target, always keeping a node on
    every support line.  Dead loads (DC1/DC2/DW) are applied to the girders as
    in :func:`structural_model_from_layout`; the plates carry stiffness only
    (self-weight is not separately activated, so the slab weight is not
    double-counted).

    ``girder_subset`` (0-based, contiguous) builds only those girder lines and
    the deck they carry -- a **construction phase**.  The phase deck runs from
    the outer overhang (where a fascia girder is included) to the mid-bay
    **closure joint** where the phase is cut from the girders not yet built, so
    the phase's inner girder carries a deck cantilever to that joint.  This is
    the stage-1 (or stage-2) structure a closure-pour analysis needs -- see
    :mod:`civilpy.structural.construction_staging`.

    Returns the :class:`StructuralModel` (units kips/ft) with
    ``rigid_links`` populated.
    """
    from civilpy.structural.structural_model import StructuralModel, Units

    inp = layout.inputs
    if composite is None:
        composite = inp.composite
    section = layout.section
    n = inp.girder_count
    spacing = inp.girder_spacing_ft
    overhang = inp.overhang_ft
    tan_skew = math.tan(math.radians(inp.skew_deg))
    seg_target = seg_target_ft or spacing

    subset = sorted(range(n) if girder_subset is None else girder_subset)
    if not subset or subset != list(range(subset[0], subset[-1] + 1)):
        raise ValueError("girder_subset must be a contiguous set of 0-based "
                         f"girder indices within 0..{n - 1}")

    # Elevations (ft, deck top = 0): girder nodes at the steel centroid, deck
    # nodes at slab mid-plane, so a rigid link spans the true composite lever.
    t_deck_ft = layout.deck.thickness_in / 12.0
    haunch_ft = inp.design_haunch_in / 12.0
    depth_ft = section.depth / 12.0

    # Deck crown + cross slope: the deck (and the girder seats hung a fixed
    # distance below it) fall from the crown to each side, so seat elevations
    # vary across the width -- computed, not rounded (Dane's correction).
    # ``layout.deck_top_z`` is the single source of the crowned surface.
    def z_deck(y):
        return layout.deck_top_z(y) - t_deck_ft / 2.0

    def z_girder(y):
        return layout.deck_top_z(y) - t_deck_ft - haunch_ft - depth_ft / 2.0

    # Longitudinal stations: subdivide each span, keep a node on every support.
    supports = [0.0]
    for s in inp.spans_ft:
        supports.append(supports[-1] + s)
    stations: list[float] = []
    for a, b in zip(supports[:-1], supports[1:]):
        nseg = max(1, round((b - a) / seg_target))
        stations.extend(a + (b - a) * k / nseg for k in range(nseg))
    stations.append(supports[-1])
    sup_j = [min(range(len(stations)), key=lambda i: abs(stations[i] - sp))
             for sp in supports]
    # station index of the fixed bearing line (for the non-composite anchor)
    fixed_support = next((bp.station_index for bp in layout.bearings
                          if bp.fixity == "fixed"), 0)
    fixed_j = sup_j[fixed_support]

    model = StructuralModel(units=Units(force="kips", length="ft"))

    # Transverse deck edges: outer overhang where a fascia girder is in the
    # phase, else the mid-bay closure joint to the girders not yet built.
    left = -overhang if subset[0] == 0 else subset[0] * spacing - spacing / 2.0
    right = (subset[-1] * spacing + overhang if subset[-1] == n - 1
             else subset[-1] * spacing + spacing / 2.0)
    deck_ys = [left] + [g * spacing for g in subset] + [right]
    gcol = {g: k + 1 for k, g in enumerate(subset)}   # deck column over girder g

    # Nodes: a girder node and a deck node column per station.
    gnode: dict[tuple[int, int], str] = {}
    dnode: dict[tuple[int, int], str] = {}
    for i, st in enumerate(stations):
        for g in subset:
            y = g * spacing
            gnode[(g, i)] = model.add_node(st + y * tan_skew, y, z_girder(y),
                                           label=f"G{g + 1}_S{i}").id
        for c, y in enumerate(deck_ys):
            dnode[(c, i)] = model.add_node(st + y * tan_skew, y, z_deck(y),
                                           label=f"D{c}_S{i}").id

    # Bare-steel girder beam chains.
    girder_elems: dict[int, list[str]] = {g: [] for g in subset}
    for g in subset:
        for i in range(len(stations) - 1):
            e = model.add_element(gnode[(g, i)], gnode[(g, i + 1)],
                                  role="girder", midas_type="BEAM",
                                  section=inp.girder_label, material=inp.grade)
            e.metadata["gdr.line"] = str(g + 1)
            girder_elems[g].append(e.id)

    # Deck plate mesh (interior bays + edge/closure strips).
    t_name = f"DECK-{layout.deck.thickness_in:g}in"
    conc_name = f"Deck-{int(round(inp.deck_fc_ksi * 1000))}psi"
    for i in range(len(stations) - 1):
        for c in range(len(deck_ys) - 1):
            quad = [dnode[(c, i)], dnode[(c + 1, i)],
                    dnode[(c + 1, i + 1)], dnode[(c, i + 1)]]
            e = model.add_element(quad[0], quad[1], role="deck",
                                  midas_type="PLATE", section=t_name,
                                  material=conc_name, nodes=quad)
            e.metadata["gdr.kind"] = "deck"

    # Deck-to-girder connection = the composite toggle.
    full = "111111"
    slip = "011111"        # free DX (longitudinal slip) -> non-composite
    for g in subset:
        c = gcol[g]
        for i in range(len(stations)):
            dof = full if (composite or i == fixed_j) else slip
            model.add_rigid_link(gnode[(g, i)], [dnode[(c, i)]], dof=dof)

    # Restraints at the support lines.
    for bp in layout.bearings:
        g = bp.line_no - 1
        nid = gnode.get((g, sup_j[bp.station_index]))
        if nid is None:
            continue
        dof = {"fix_x": True, "fix_y": True, "fix_z": True} if bp.fixity == "fixed" \
            else {"fix_x": False, "fix_y": True, "fix_z": True}
        model.add_restraint(nid, **dof).preset = bp.fixity

    if dead_loads:
        for g, elems in girder_elems.items():
            w = girder_line_loads(layout, g)
            for eid in elems:
                model.add_beam_load(eid, -w["dc1"], case="DC1")
                model.add_beam_load(eid, -w["dw"], case="DW")
                if w["dc2"]:
                    model.add_beam_load(eid, -w["dc2"], case="DC2")

    return model
