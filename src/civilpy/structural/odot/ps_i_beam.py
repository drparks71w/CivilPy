#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT prestressed concrete I-beam bridge details (PSID-1-13).

Transcribed from Ohio DOT Standard Bridge Drawing PSID-1-13, "Prestressed
Concrete I-Beam Bridge Details" (rev. 07-18-2025, 10 sheets). The drawing
remains the controlling document.

Thirteen standard sections:

* **AASHTO Type 2/3/4** and three deepened "Modified AASHTO Type 4"
  webs (60/66/72 in overall depth) -- sheet 1's ``SECTION PROPERTIES``
  table. The Modified Type 4s keep Type 4's 26 in bottom flange but
  carry a *wide, thin* top flange (36 in for the 60/66, 48 in for the
  72 -- verified against sheet 1's own dimension strings and the
  shipping-strand offsets), **not** Type 4's 20 in flange.
* **WF36-49 .. WF72-49** wide-flange sections (sheets 2-3, sheet 3's
  ``SECTION PROPERTIES`` table): 49 in top flange, 40 in bottom flange,
  8 in web, 62 permissible bottom-flange strand locations each.

Beyond the section tables this module also catalogs, per section, the
sheet's **permissible strand grid** (the ``+`` marks: 2 in lattice both
ways, exact per-row offsets extracted from the drawing's vector marks --
row totals reconcile with the sheet's stated 26/40/52/62 permissible
location counts), the WF web locations that **must be draped if
utilized** (sheet 2 note), the Modified-AASHTO/WF **shipping strand**
locations, and the sheet 10 design constants (0.6 in Grade 270
low-relaxation strand at 0.217 in^2, designer-selected ``f'c`` /
``f'ci`` ranges, HL-93 + 60 psf FWS, spacing < 14 ft, skew < 45 deg).

No PSIDD companion *design-data* sheet exists (unlike PSBD/PSBDD for
box beams), so there are no tabulated standard strand patterns;
:mod:`civilpy.structural.ps_i_beam_pipeline` designs a pattern on this
grid instead.

Lengths in inches, area in in^2, weight in lb/ft, moment of inertia in
in^4, section moduli in in^3, unless noted. Spot-checked against the
drawing in the test suite.
"""

from dataclasses import dataclass, field

Point = tuple[float, float]  # (y, z) inches, section profile

SCD = "PSID-1-13"
REVISION = "07-18-2025"

# ── sheet 10 design constants ────────────────────────────────────────────
#: Nominal strand area (in^2) -- 0.6 in seven-wire strand (sheet 10).
STRAND_AREA_IN2 = 0.217
#: Strand diameter, inches.
STRAND_DIAMETER_IN = 0.6
#: Strand ultimate strength, ksi (711.27 / ASTM A416 Grade 270, low-lax).
STRAND_FPU_KSI = 270.0
#: Designer-selected 28-day strength range, ksi (sheet 10).
FC_RANGE_KSI = (5.5, 7.0)
#: Designer-selected release strength range, ksi (sheet 10).
FCI_RANGE_KSI = (4.0, 5.0)
#: Future wearing surface dead load, lb/ft^2 (sheet 10 design loading).
FWS_PSF = 60.0
#: The standard applies to beam spacings under 14 ft and skews under 45
#: degrees (sheet 10 general notes).
MAX_BEAM_SPACING_FT = 14.0
MAX_SKEW_DEG = 45.0
#: Diaphragm concrete (Item 511), ksi.
DIAPHRAGM_FC_KSI = 4.5
#: Shipping strands are debonded except the last 10 ft each end (sheet 10).
SHIPPING_STRAND_BOND_FT = 10.0

REBAR_EPOXY_NOTE = "401-series bars (marked '(d)') shall be epoxy-coated"
WWR_NOTE = "all reinforcing steel may be replaced with equivalent welded wire reinforcement (WWR)"


@dataclass(frozen=True)
class PSIBeamSection:
    """One PSID-1-13 standard section (sheet 1 / sheet 3 SECTION
    PROPERTIES tables).

    ``strand_rows`` is the sheet's permissible strand grid: a tuple of
    ``(z, (y, ...))`` rows -- ``z`` inches above the beam bottom, ``y``
    transverse offsets from the beam centerline (2 in lattice).  The row
    totals equal ``max_bottom_flange_strands``.  ``draped_required``
    lists the grid locations the sheet marks "if utilized, these strand
    locations must be draped" (WF sections' upper web column).
    ``shipping_strand_locations`` are the optional debonded shipping
    strands the fabricator may add in the top flange (Modified AASHTO /
    WF sheets; the sheet ties them to general-note bonding rules --
    see :data:`SHIPPING_STRAND_BOND_FT`)."""

    name: str
    depth_in: float
    area_in2: float
    weight_plf: float
    yb_in: float           # centroid above bottom
    yt_in: float            # centroid below top
    i_in4: float
    sb_in3: float
    st_in3: float
    vol_surf_ratio: float
    top_flange_width_in: float
    bottom_flange_width_in: float
    max_bottom_flange_strands: int
    web_in: float = 8.0
    strand_rows: tuple = ()
    draped_required: tuple = ()
    shipping_strand_locations: tuple = ()


# ── permissible strand grids (vector-extracted from the sheets; the row
#    totals reconcile with each diagram's stated permissible count) ───────
def _rows(*rows):
    return tuple((float(z), tuple(float(y) for y in ys)) for z, ys in rows)


_TYPE2_ROWS = _rows(  # 26 locations
    (2, (-6, -4, 0, 4, 6)),
    (4, (-6, -4, -2, 0, 2, 4, 6)),
    (6, (-6, -4, 0, 4, 6)),
    (8, (-4, -2, 0, 2, 4)),
    (10, (-2, 0, 2)),
    (12, (0,)),
)
_TYPE3_ROWS = _rows(  # 40 locations
    (2, (-7, -5, 5, 7)),
    (4, (-9, -7, -5, -3, -1, 1, 3, 5, 7, 9)),
    (6, (-9, -7, -5, 5, 7, 9)),
    (8, (-7, -5, -3, -1, 1, 3, 5, 7)),
    (10, (-5, -3, -1, 1, 3, 5)),
    (12, (-3, -1, 1, 3)),
    (14, (-1, 1)),
)
_TYPE4_ROWS = _rows(  # 52 locations (Type 4 and all Modified Type 4s)
    (2, (-10, -8, -6, -4, 0, 4, 6, 8, 10)),
    (4, (-10, -8, -6, -4, 0, 4, 6, 8, 10)),
    (6, (-10, -8, -6, -4, 0, 4, 6, 8, 10)),
    (8, (-10, -8, -6, -4, 0, 4, 6, 8, 10)),
    (10, (-8, -6, -4, 0, 4, 6, 8)),
    (12, (-6, -4, 0, 4, 6)),
    (14, (-4, 0, 4)),
    (16, (0,)),
)
_WF_ROWS = _rows(  # 62 locations (all WF sections)
    (2, (-16, -14, -12, -10, -8, -6, -4, 0, 4, 6, 8, 10, 12, 14, 16)),
    (4, (-18, -16, -14, -12, -10, -8, -6, -4, 0, 4, 6, 8, 10, 12, 14, 16, 18)),
    (6, (-14, -12, -10, -8, -6, -4, 0, 4, 6, 8, 10, 12, 14)),
    (8, (-10, -8, -6, -4, 0, 4, 6, 8, 10)),
    (10, (-6, -4, 0, 4, 6)),
    (12, (0,)),
    (14, (0,)),
    (16, (0,)),
)
#: WF web locations that must be draped if utilized (sheet 2 legend).
_WF_DRAPED = ((0.0, 14.0), (0.0, 16.0))


def _shipping(depth_in: float) -> tuple:
    """Modified-AASHTO / WF shipping strand locations: six in the top
    flange at +/-6, +/-8, +/-10 in, 3 in below the top surface."""
    z = depth_in - 3.0
    return tuple((float(y), z) for y in (-10, -8, -6, 6, 8, 10))


def _wf(name, depth, area, weight, yb, yt, i, sb, st, vs):
    return PSIBeamSection(
        name, depth, area, weight, yb, yt, i, sb, st, vs,
        top_flange_width_in=49.0, bottom_flange_width_in=40.0,
        max_bottom_flange_strands=62, web_in=8.0, strand_rows=_WF_ROWS,
        draped_required=_WF_DRAPED,
        shipping_strand_locations=_shipping(depth))


#: PSID-1-13 standard I-beam sections, keyed by name.
PS_I_BEAM_SECTIONS: dict[str, PSIBeamSection] = {
    "AASHTO Type 2": PSIBeamSection(
        "AASHTO Type 2", 36.0, 369.0, 384.0, 15.83, 20.17, 50_979, 3_221,
        2_527, 3.371, 12.0, 18.0, 26, web_in=6.0, strand_rows=_TYPE2_ROWS),
    "AASHTO Type 3": PSIBeamSection(
        "AASHTO Type 3", 45.0, 560.0, 583.0, 20.27, 24.73, 125_390, 6_185,
        5_071, 4.056, 16.0, 22.0, 40, web_in=7.0, strand_rows=_TYPE3_ROWS),
    "AASHTO Type 4": PSIBeamSection(
        "AASHTO Type 4", 54.0, 789.0, 822.0, 24.73, 29.27, 260_741, 10_542,
        8_909, 4.741, 20.0, 26.0, 52, web_in=8.0, strand_rows=_TYPE4_ROWS),
    "Modified AASHTO Type 4 (60in)": PSIBeamSection(
        "Modified AASHTO Type 4 (60in)", 60.0, 860.0, 896.0, 28.74, 31.26,
        384_705, 13_385, 12_307, 4.089, 36.0, 26.0, 52, web_in=8.0,
        strand_rows=_TYPE4_ROWS,
        shipping_strand_locations=_shipping(60.0)),
    "Modified AASHTO Type 4 (66in)": PSIBeamSection(
        "Modified AASHTO Type 4 (66in)", 66.0, 908.0, 946.0, 31.58, 34.42,
        492_212, 15_588, 14_299, 4.085, 36.0, 26.0, 52, web_in=8.0,
        strand_rows=_TYPE4_ROWS,
        shipping_strand_locations=_shipping(66.0)),
    "Modified AASHTO Type 4 (72in)": PSIBeamSection(
        "Modified AASHTO Type 4 (72in)", 72.0, 1015.0, 1058.0, 36.52, 35.48,
        684_726, 18_749, 19_299, 3.947, 48.0, 26.0, 52, web_in=8.0,
        strand_rows=_TYPE4_ROWS,
        shipping_strand_locations=_shipping(72.0)),
    "WF36-49": _wf("WF36-49", 36.0, 878.3, 915.0, 18.2, 17.8,
                   145_592, 8_000, 8_179, 4.160),
    "WF42-49": _wf("WF42-49", 42.0, 926.3, 965.0, 21.1, 20.9,
                   217_461, 10_306, 10_405, 4.152),
    "WF48-49": _wf("WF48-49", 48.0, 974.3, 1015.0, 24.0, 24.0,
                   305_994, 12_750, 12_750, 4.144),
    "WF54-49": _wf("WF54-49", 54.0, 1022.3, 1065.0, 27.0, 27.0,
                   412_056, 15_261, 15_261, 4.137),
    "WF60-49": _wf("WF60-49", 60.0, 1070.3, 1115.0, 29.9, 30.1,
                   536_513, 17_944, 17_824, 4.131),
    "WF66-49": _wf("WF66-49", 66.0, 1118.3, 1165.0, 32.9, 33.1,
                   680_229, 20_676, 20_551, 4.125),
    "WF72-49": _wf("WF72-49", 72.0, 1166.3, 1215.0, 35.8, 36.2,
                   844_069, 23_577, 23_317, 4.120),
}


def ps_i_beam_section(name: str) -> PSIBeamSection:
    """Look up a PSID-1-13 standard section by name.

    Raises ``ValueError`` naming the valid sections otherwise."""
    try:
        return PS_I_BEAM_SECTIONS[name]
    except KeyError:
        raise ValueError(
            f"PSID-1-13 sections are {list(PS_I_BEAM_SECTIONS)}, "
            f"not {name!r}") from None


# ── layout (simplified I-shape; bulb radius/haunch fillets not modeled) ──

@dataclass(frozen=True)
class PSIBeamLayout:
    """A simplified I-shaped cross-section profile (top flange, web,
    bottom flange) -- straight-line approximation, no fillet/bulb radii --
    extruded ``length_ft``. Profile points (y, z) inches, y transverse,
    z up from the bottom; the beam centerline is y = 0."""

    section: PSIBeamSection
    profile: tuple[Point, ...]
    length_ft: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_ps_i_beam(name: str, length_ft: float,
                     web_thickness_in: float = 8.0,
                     flange_thickness_in: float = 8.0) -> PSIBeamLayout:
    """Generate a simplified I-beam cross-section profile for ``name``
    (:func:`ps_i_beam_section`), extruded ``length_ft``.

    Raises ``ValueError`` for a non-positive length or an unknown section
    name."""
    if length_ft <= 0.0:
        raise ValueError("length_ft must be positive")
    s = ps_i_beam_section(name)
    D = s.depth_in
    tw = web_thickness_in
    tf = flange_thickness_in
    top_w, bot_w = s.top_flange_width_in, s.bottom_flange_width_in

    profile = (
        (-bot_w / 2.0, 0.0), (bot_w / 2.0, 0.0),
        (bot_w / 2.0, tf), (tw / 2.0, tf),
        (tw / 2.0, D - tf), (top_w / 2.0, D - tf),
        (top_w / 2.0, D), (-top_w / 2.0, D),
        (-top_w / 2.0, D - tf), (-tw / 2.0, D - tf),
        (-tw / 2.0, tf), (-bot_w / 2.0, tf),
    )

    notes = (
        f"PSID-1-13 {name}: depth {D:g} in, area {s.area_in2:g} in^2, "
        f"weight {s.weight_plf:g} lb/ft, I {s.i_in4:,.0f} in^4, length "
        f"{length_ft:g} ft",
        f"Max {s.max_bottom_flange_strands} permissible bottom flange "
        "strand locations (strand pattern itself is project-specific).",
        "Simplified straight-line I-shape -- true bulb/fillet radii, "
        "strand pattern, shipping strands, WWR/rebar (A/B/C/D/E/F/G "
        "series bars), and end-block details are not modeled.",
    )

    return PSIBeamLayout(section=s, profile=profile, length_ft=length_ft,
                         notes=notes)


# ── true tapered outlines (straight-line; fillet/chamfer radii omitted) ──
#
# Half-outline breakpoints (half_width, z) bottom-up per section family,
# from each diagram's dimension stack.  AASHTO 2/3/4 close exactly (the
# polygon area reproduces the published area to the ~1 in^2 the chamfers
# remove); the Modified Type 4 / WF top-flange edge split between the
# vertical edge and the underside slope is read off the sheet to the
# nearest inch, so those polygon areas run a few percent over the
# published values -- quantities should use the published area/weight,
# not the drawn outline (see SCD_BUILD_QUESTIONS.md).
_HALF_OUTLINES: dict[str, tuple[Point, ...]] = {
    "AASHTO Type 2": ((9, 0), (9, 6), (3, 12), (3, 27), (6, 30), (6, 36)),
    "AASHTO Type 3": ((11, 0), (11, 7), (3.5, 14.5), (3.5, 33.5),
                      (8, 38), (8, 45)),
    "AASHTO Type 4": ((13, 0), (13, 8), (4, 17), (4, 40), (10, 46),
                      (10, 54)),
    "Modified AASHTO Type 4 (60in)": (
        (13, 0), (13, 8), (4, 17), (4, 51), (18, 56), (18, 60)),
    "Modified AASHTO Type 4 (66in)": (
        (13, 0), (13, 8), (4, 17), (4, 57), (18, 62), (18, 66)),
    "Modified AASHTO Type 4 (72in)": (
        (13, 0), (13, 8), (4, 17), (4, 63), (24, 68), (24, 72)),
}


def _wf_half_outline(depth: float) -> tuple[Point, ...]:
    return ((20, 0), (20, 5.5), (6, 12.5), (4, 14.5), (4, depth - 11),
            (21.5, depth - 6), (24.5, depth - 3), (24.5, depth))


def ps_i_beam_profile(name: str) -> tuple[Point, ...]:
    """The true tapered cross-section outline of a PSID-1-13 section as
    closed-polygon vertices ``(y, z)`` in inches, ``y`` transverse from
    the beam centerline, ``z`` up from the bottom -- counter-clockwise,
    starting at the bottom-left corner.  Straight-line approximation:
    fillet and 3/4 in chamfer radii are not modeled (unlike
    :func:`layout_ps_i_beam`, the flange tapers *are*)."""
    s = ps_i_beam_section(name)
    half = (_HALF_OUTLINES.get(name) or _wf_half_outline(s.depth_in))
    right = [(w, z) for (w, z) in half]
    left = [(-w, z) for (w, z) in reversed(half)]
    return tuple(right + left)


# ── strand pattern helpers ────────────────────────────────────────────────
def strand_grid(name: str) -> list[Point]:
    """Every permissible bottom-flange/web strand location of a section
    as ``(y, z)`` inches, in the standard fill order: row by row from
    the bottom up, outermost locations first within a row (the fill
    order keeps each partial pattern symmetric and its centroid low).

    Locations in :attr:`PSIBeamSection.draped_required` come last so a
    straight-strand design never occupies them by accident."""
    s = ps_i_beam_section(name)
    draped = set(s.draped_required)
    pts: list[Point] = []
    for z, ys in s.strand_rows:
        row = [(y, z) for y in sorted(ys, key=lambda y: (-abs(y), y))
               if (y, z) not in draped]
        pts.extend(row)
    pts.extend(s.draped_required)
    return pts


def strand_pattern(name: str, n_strands: int) -> list[Point]:
    """The first ``n_strands`` locations of :func:`strand_grid` --
    the pattern the pipeline's designer uses.  Raises ``ValueError``
    when ``n_strands`` exceeds the section's permissible locations."""
    grid = strand_grid(name)
    if not 0 < n_strands <= len(grid):
        raise ValueError(
            f"{name} has {len(grid)} permissible strand locations, "
            f"cannot place {n_strands}")
    return grid[:n_strands]


def strand_centroid_in(pattern: list[Point]) -> float:
    """Height of a strand pattern's centroid above the beam bottom (in)."""
    if not pattern:
        raise ValueError("empty strand pattern")
    return sum(z for _, z in pattern) / len(pattern)


def i_beam_diaphragm_stations_ft(span_ft: float) -> list[float]:
    """Intermediate-diaphragm centerline stations (ft from the span
    start) per sheet 5: one at midspan for spans up to 80 ft, at the
    quarter points beyond that.  (Cast-in-place required under 60 in
    deep beams; 60/66/72 in beams may use the sheet 9 galvanized-steel
    diaphragms instead -- sheet 10 general notes.)"""
    if span_ft <= 0.0:
        raise ValueError("span_ft must be positive")
    if span_ft <= 80.0:
        return [span_ft / 2.0]
    return [span_ft / 4.0, span_ft / 2.0, 3.0 * span_ft / 4.0]
