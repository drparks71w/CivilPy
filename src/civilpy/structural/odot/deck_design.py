#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT standard reinforced concrete deck designs (BDM 309.3).

Design policy, the minimum-thickness formula, and the standard deck design
table transcribed from the Ohio DOT *Bridge Design Manual*, 2020 Edition,
January 2026 revision, Section 309.3 "Reinforced Concrete Deck on
Longitudinal Members" (pp. 3-187 ff.) and Figure 309-3 (p. 3-188).  The
manual remains the controlling document.

Three things are carried here:

``minimum_deck_thickness`` (BDM 309.3.1)
    ``Tmin (in) = (S + 17)(12) / 36 >= 8.5``, S = effective span length in
    feet per LRFD 9.7.2.3, rounded **up** to the nearest 1/4 in.  The 1 in
    monolithic wearing surface is included in this thickness but excluded
    from structural design (BDM 309.1.A).

``POLICY`` (BDM 309.3.2 / 309.2)
    The non-negotiable design requirements: approximate elastic (strip)
    method of LRFD 9.7.3 only — the empirical method (LRFD 9.7.2) and
    refined methods are prohibited — HL-93 live load, 0.06 ksf future
    wearing surface, covers, exposure factor, and the standard materials
    (class QC2 concrete at f'c = 4.5 ksi, Grade 60 epoxy-coated bars).

``STANDARD_DECK_DESIGNS`` (BDM Figure 309-3)
    The pre-engineered deck designs for effective spans of 7.0 ft to
    14.0 ft in 0.5 ft steps: thicknesses, transverse and longitudinal mats,
    and the additional overhang bars.  ``standard_deck_design`` looks a
    design up by effective span (rounded up to the next 0.5 ft per the
    figure's note 2.k) and enforces the figure's assumption limits.

Railing designations cross-reference the SCDs cataloged in
:mod:`civilpy.structural.odot.bridge_railing`.  Bar sizes are standard
US designators resolved through :class:`civilpy.structural.steel.Rebar`.
Lengths in inches unless a name says otherwise; spans in feet.
"""

import math
from dataclasses import dataclass

from civilpy.structural.steel import Rebar

# ── BDM 309.3.2 / 309.2 design policy ────────────────────────────────────

#: Analysis method mandated by BDM 309.3.2.
DESIGN_METHOD = "LRFD 9.7.3 approximate elastic (equivalent strip)"

#: Methods BDM 309.3.2 explicitly prohibits for ODOT deck design.
PROHIBITED_METHODS = (
    "LRFD 9.7.2 empirical design",
    "refined methods of analysis",
)


@dataclass(frozen=True)
class DeckDesignPolicy:
    """ODOT concrete deck design requirements (BDM 309.3.2, 309.2, and the
    Figure 309-3 design assumptions).  Thicknesses/covers in inches,
    pressures in ksf, strengths in ksi."""

    method: str = DESIGN_METHOD
    live_load: str = "HL-93"
    future_wearing_surface_ksf: float = 0.06   # BDM 309.3.2 dead load
    monolithic_wearing_surface: float = 1.0    # BDM 309.1.A; non-structural
    top_cover: float = 2.5                     # BDM 309.2, all CIP decks
    bottom_cover: float = 1.5                  # to transverse steel, 309.3.2
    exposure_factor: float = 0.75              # LRFD 5.6.7 gamma_e
    f_c: float = 4.5                           # class QC2 (BDM 304.2.1)
    f_y: float = 60.0                          # Grade 60 (Fig. 309-3 note 2e)
    concrete_class: str = "QC2"                # BDM 309.2
    epoxy_coated: bool = True                  # BDM 309.2


#: The BDM deck design policy; treat as read-only.
POLICY = DeckDesignPolicy()


# ── BDM 309.3.1 minimum thickness ────────────────────────────────────────

def minimum_deck_thickness(effective_span_ft: float) -> float:
    """Minimum total deck thickness (in) per BDM 309.3.1.

    ``Tmin = (S + 17)(12)/36 >= 8.5 in`` rounded up to the nearest 1/4 in,
    where ``effective_span_ft`` is the effective span length per LRFD
    9.7.2.3.  Includes the 1 in monolithic wearing surface; subtract
    :attr:`DeckDesignPolicy.monolithic_wearing_surface` for the structural
    design thickness.
    """
    if effective_span_ft <= 0:
        raise ValueError("effective span must be positive")
    t = (effective_span_ft + 17.0) * 12.0 / 36.0
    t = max(t, 8.5)
    return math.ceil(t * 4.0 - 1e-9) / 4.0


def structural_design_thickness(total_thickness: float) -> float:
    """Deck thickness used in structural design (in): the total thickness
    minus the monolithic wearing surface (BDM 309.3.1 / 309.1.A)."""
    return total_thickness - POLICY.monolithic_wearing_surface


# ── BDM Figure 309-3 standard designs ────────────────────────────────────

@dataclass(frozen=True)
class BarMat:
    """One reinforcing mat: bar size at a uniform spacing (in)."""

    size: int       # standard US bar designator, e.g. 5 for a #5
    spacing: float  # in, center-to-center

    @property
    def area_per_ft(self) -> float:
        """Provided steel area (in^2/ft of deck)."""
        return float(Rebar(self.size).area.magnitude) * 12.0 / self.spacing

    def __str__(self) -> str:
        return f"#{self.size} @ {self.spacing:g} in"


@dataclass(frozen=True)
class StandardDeckDesign:
    """One row of BDM Figure 309-3.

    ``deck_thickness`` and ``overhang_thickness`` are totals including the
    1 in monolithic wearing surface.  ``overhang_bar_size`` /
    ``overhang_cutoff`` are the additional overhang bar and the length (in)
    beyond the fascia beam/girder centerline where it is no longer required
    (note 5); both are ``None`` where the figure tabulates none.
    Longitudinal spacings exclude the additional negative-moment
    reinforcement required over piers (note 6; LRFD 6.10.1.7 / 5.6.3.2).
    """

    effective_span_ft: float
    deck_thickness: float          # in
    overhang_thickness: float      # in (see TST overrides, note 2.k)
    transverse_top: BarMat
    transverse_bottom: BarMat
    longitudinal_top: BarMat
    longitudinal_bottom: BarMat
    overhang_bar_size: int | None
    overhang_cutoff: float | None  # in


def _row(span, t, t_oh, tt_s, tt_sp, oh, cut, tb_s, tb_sp, lt_s, lt_sp,
         lb_s, lb_sp) -> StandardDeckDesign:
    return StandardDeckDesign(
        effective_span_ft=span,
        deck_thickness=t,
        overhang_thickness=t_oh,
        transverse_top=BarMat(tt_s, tt_sp),
        transverse_bottom=BarMat(tb_s, tb_sp),
        longitudinal_top=BarMat(lt_s, lt_sp),
        longitudinal_bottom=BarMat(lb_s, lb_sp),
        overhang_bar_size=oh,
        overhang_cutoff=cut,
    )


#: BDM Figure 309-3, one entry per tabulated effective span.
STANDARD_DECK_DESIGNS: tuple[StandardDeckDesign, ...] = (
    #    span  t      t_oh   ─transv top─  overhang   ─trans bot─  ─long top─  ─long bot─
    _row(7.0,  8.50,  10.50, 5, 6.00, 5, 54.0, 5, 6.00, 4, 12.50, 5, 10.75),
    _row(7.5,  8.50,  10.50, 5, 6.00, 5, 54.0, 5, 6.00, 4, 12.00, 5, 10.25),
    _row(8.0,  8.50,  10.50, 5, 6.00, 5, 54.0, 5, 6.00, 4, 11.50, 5, 9.75),
    _row(8.5,  8.50,  10.50, 5, 5.75, 4, 54.0, 5, 5.75, 4, 11.00, 5, 9.25),
    _row(9.0,  8.75,  10.75, 5, 5.75, 4, 54.0, 5, 5.75, 4, 11.00, 5, 9.25),
    _row(9.5,  9.00,  11.00, 5, 5.75, 4, 54.0, 5, 5.75, 4, 11.00, 5, 9.25),
    _row(10.0, 9.00,  11.00, 5, 5.25, 4, 48.0, 5, 5.25, 4, 10.00, 5, 8.75),
    _row(10.5, 9.25,  11.25, 5, 5.25, 4, 48.0, 5, 5.25, 4, 10.00, 5, 8.75),
    _row(11.0, 9.50,  11.50, 5, 5.00, 4, 48.0, 5, 5.00, 4, 9.50,  5, 8.75),
    _row(11.5, 9.50,  11.50, 6, 5.75, 4, 28.0, 5, 5.75, 4, 7.75,  5, 8.75),
    _row(12.0, 9.75,  11.75, 6, 5.75, 4, 28.0, 5, 5.75, 4, 7.75,  5, 8.75),
    _row(12.5, 10.00, 12.00, 6, 5.75, None, None, 5, 5.75, 4, 7.75, 5, 8.75),
    _row(13.0, 10.00, 12.00, 6, 5.75, None, None, 5, 5.75, 4, 7.75, 5, 8.75),
    _row(13.5, 10.25, 12.25, 6, 5.75, None, None, 5, 5.75, 4, 7.75, 5, 8.75),
    _row(14.0, 10.50, 12.50, 6, 5.75, None, None, 5, 5.75, 4, 7.75, 5, 8.75),
)

#: Figure 309-3 note 2 assumption limits.
MIN_BEAM_LINES = 4          # note 2.a
MAX_BEAM_SPACING_FT = 15.0  # note 2.b
MAX_OVERHANG_FT = 4.0       # note 2.j, cl fascia beam/girder to deck edge

#: Railing SCDs the overhang design is valid for (note 2.k); designations
#: resolve through :func:`civilpy.structural.odot.bridge_railing.railing`.
VALID_RAILINGS: tuple[str, ...] = (
    "BR-1-13", "SBR-1-20", "SBR-2-20", "SBR-3-20", "BR-2-15",
    "TST-1-99", "TST-2-21",
)

#: Note 2.k minimum overhang deck thickness overrides for the steel-tube
#: railings (in); these govern over the tabulated overhang thickness.
MIN_OVERHANG_THICKNESS: dict[str, float] = {
    "TST-1-99": 18.0,
    "TST-2-21": 20.0,
}

_SPANS = tuple(d.effective_span_ft for d in STANDARD_DECK_DESIGNS)
_BY_SPAN = {d.effective_span_ft: d for d in STANDARD_DECK_DESIGNS}


def standard_deck_design(
    effective_span_ft: float,
    *,
    railing: str | None = None,
    beam_lines: int | None = None,
    beam_spacing_ft: float | None = None,
    overhang_ft: float | None = None,
) -> StandardDeckDesign:
    """Look up the BDM Figure 309-3 standard design for an effective span.

    ``effective_span_ft`` is the effective span length per LRFD 9.7.3.2; it
    is rounded **up** to the next tabulated 0.5 ft increment (note 2.k).
    The optional keywords assert the figure's design assumptions —
    ``railing`` (SCD designation, note 2.k), ``beam_lines`` (>= 4, note
    2.a), ``beam_spacing_ft`` (<= 15 ft, note 2.b) and ``overhang_ft``
    (<= 4 ft, note 2.j) — and raise ``ValueError`` when the standard
    designs do not apply, in which case the deck must be designed per BDM
    309.3.2 instead.
    """
    rounded = math.ceil(effective_span_ft * 2.0 - 1e-9) / 2.0
    if rounded < _SPANS[0]:
        rounded = _SPANS[0]
    if rounded > _SPANS[-1]:
        raise ValueError(
            f"effective span {effective_span_ft} ft exceeds the "
            f"{_SPANS[-1]} ft limit of BDM Figure 309-3; design the deck "
            "per BDM 309.3.2"
        )
    if railing is not None and railing not in VALID_RAILINGS:
        raise ValueError(
            f"overhang design is not valid for railing {railing!r}; "
            f"Figure 309-3 covers {', '.join(VALID_RAILINGS)}"
        )
    if beam_lines is not None and beam_lines < MIN_BEAM_LINES:
        raise ValueError(
            f"standard designs assume >= {MIN_BEAM_LINES} beam/girder "
            f"lines, got {beam_lines}"
        )
    if beam_spacing_ft is not None and beam_spacing_ft > MAX_BEAM_SPACING_FT:
        raise ValueError(
            f"standard designs assume beam spacing <= "
            f"{MAX_BEAM_SPACING_FT} ft c/c, got {beam_spacing_ft} ft"
        )
    if overhang_ft is not None and overhang_ft > MAX_OVERHANG_FT:
        raise ValueError(
            f"standard designs assume overhang <= {MAX_OVERHANG_FT} ft, "
            f"got {overhang_ft} ft"
        )
    return _BY_SPAN[rounded]


def overhang_thickness(design: StandardDeckDesign,
                       railing: str | None = None) -> float:
    """Overhang deck thickness (in) for a standard design, applying the
    note 2.k minimums for the TST steel-tube railings when they govern."""
    t = design.overhang_thickness
    if railing in MIN_OVERHANG_THICKNESS:
        t = max(t, MIN_OVERHANG_THICKNESS[railing])
    return t


# ── BDM 309.3.5 haunch requirements ──────────────────────────────────────

#: Minimum design haunch (in) between top of beam/girder flange and bottom
#: of deck (BDM 309.3.5).  Haunches absorb unforeseen camber variation so
#: the slab never thins below design.
MIN_DESIGN_HAUNCH = 2.0


@dataclass(frozen=True)
class Haunch:
    """A concrete haunch per BDM 309.3.5: sides vertical and aligned with
    the edges of the top flange, so the haunch cross-section is simply
    ``flange_width x depth``.  Depths/widths in inches."""

    depth: float         # in, top of flange to bottom of deck
    flange_width: float  # in, girder top-flange width (haunch width)

    def __post_init__(self):
        if self.depth < MIN_DESIGN_HAUNCH:
            raise ValueError(
                f"design haunch {self.depth} in is below the BDM 309.3.5 "
                f"minimum of {MIN_DESIGN_HAUNCH} in"
            )
        if self.flange_width <= 0:
            raise ValueError("flange width must be positive")

    @property
    def area(self) -> float:
        """Cross-sectional area (in^2)."""
        return self.depth * self.flange_width

    def dead_load_klf(self, unit_weight_kcf: float = 0.150) -> float:
        """Haunch self-weight per foot of girder (kip/ft)."""
        return self.area / 144.0 * unit_weight_kcf


def haunch_depth_at(design_haunch: float, camber_residual: float) -> float:
    """Theoretical haunch depth (in) at a station where the girder sits
    ``camber_residual`` inches BELOW its theoretical profile (positive =
    girder low -> deeper haunch; negative = girder high -> shallower).
    The result may fall below :data:`MIN_DESIGN_HAUNCH` — that is the
    signal the design haunch must be increased, not clamped away.
    """
    return design_haunch + camber_residual


# ── BDM 309.3.4.1 secondary (longitudinal top) reinforcement ─────────────

def secondary_longitudinal_reinforcement(main: BarMat) -> BarMat:
    """Minimum longitudinal top-mat (secondary) reinforcement per BDM
    309.3.4.1: at least 1/3 of the main (transverse) reinforcement, spaced
    uniformly, detailed as #4 bars — unless that would put the #4s closer
    than 3 in, in which case a larger bar at >= 3 in spacing is returned.

    Applies the 1/3 rule to the *provided* main steel, which is slightly
    conservative against BDM Figure 309-3 (whose longitudinal mats derive
    from the required steel); for spans the figure tabulates, use the
    figure's mats — this helper is for custom designs outside it.
    """
    required = main.area_per_ft / 3.0  # in^2/ft
    for size in (4, 5, 6):
        area = float(Rebar(size).area.magnitude)
        spacing = area * 12.0 / required
        if spacing >= 3.0 or size == 6:
            # round spacing DOWN to 1/4 in so the provided area governs
            return BarMat(size, math.floor(min(spacing, 18.0) * 4.0) / 4.0)
    raise AssertionError("unreachable")
