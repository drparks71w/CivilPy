#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT Midwest Guardrail System (MGS) roadway drawings.

Geometry and layout transcribed from the Ohio DOT Standard Roadway
Construction Drawings, MGS series (Office of Roadway Engineering).  The
standard system parameters (rail height, post spacing, blockouts, post
sections) come from MGS-2.1; the series registry maps every MGS drawing and
flags the bridge terminal assemblies that connect a guardrail run to the
bridge railings cataloged in :mod:`civilpy.structural.odot.bridge_railing`.

Lengths are in inches unless a field name says otherwise.  Values are
spot-checked against the cited drawings in the test suite; the drawings
remain the controlling document for detailing.

Beyond the MGS-2.1 system parameters this module carries the three
**bridge terminal assemblies** as typed post-by-post layouts
(:data:`BRIDGE_TERMINALS` / :func:`layout_bridge_terminal`) — the
guardrail-to-bridge-railing hardware — and a standard-
run post/panel layout (:func:`layout_mgs_run`).

Sources (SCD number — latest cited revision):
    MGS-2.1  Midwest Guardrail System, Standard Type MGS   (rev. 2026-01-16)
    MGS-3.1  MGS Bridge Terminal Assembly, Type 1          (rev. 2026-01-16)
    MGS-3.2  MGS Bridge Terminal Assembly, Type 2          (rev. 2025-07-18)
    MGS-3.3  MGS Bridge Terminal Assembly, Type TST-2      (rev. 2026-01-16)
    MGS-4.3  Guardrail Transitions                         (rev. 2025-07-18)
    (plus the full MGS series registry, MGS_DRAWINGS)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PostSpacing:
    """One MGS post-spacing option and the blockout height it requires
    (MGS-2.1 sheets P.1-P.2).  ``spacing`` and ``blockout_height`` in inches."""

    name: str
    spacing: float
    blockout_height: float


#: MGS post-spacing options (on-center spacing and required blockout height).
MGS_POST_SPACINGS: dict[str, PostSpacing] = {
    "standard": PostSpacing("standard", 75.0, 12.0),   # 6 ft-3 in, 12 in block
    "half": PostSpacing("half", 37.5, 10.0),           # 3 ft-1.5 in, 10 in block
    "quarter": PostSpacing("quarter", 18.75, 14.0),    # 1 ft-6.75 in, 14 in block
}


@dataclass(frozen=True)
class SteelPost:
    """An MGS steel beam post section (MGS-2.1 sheet P.2 table).  All
    dimensions in inches."""

    designation: str
    fabrication: str  # "rolled" or "welded"
    depth: float
    flange_width: float
    flange_thickness: float
    web_thickness: float


#: MGS steel beam post sections (MGS-2.1 sheet P.2).
MGS_STEEL_POSTS: dict[str, SteelPost] = {
    "W6x8.5 rolled": SteelPost("W6x8.5", "rolled", 5.8, 3.94, 0.193, 0.170),
    "W6x9 rolled": SteelPost("W6x9", "rolled", 5.9, 3.94, 0.215, 0.170),
    "6x8.5 welded": SteelPost("6x8.5", "welded", 6.0, 3.94, 0.193, 0.170),
    "6x9 welded": SteelPost("6x9", "welded", 6.0, 3.94, 0.215, 0.170),
}


@dataclass(frozen=True)
class MGSStandard:
    """Standard Type MGS guardrail parameters (MGS-2.1).

    Heights/lengths in inches; ``rail_panel_lengths`` (between splices) and
    transition rate are in feet.
    """

    scd: str = "MGS-2.1"
    scd_date: str = "2026-01-16"
    #: Standard rail height to top of W-beam, inches.
    rail_height: float = 31.0
    #: Construction tolerance on initial install, inches (+/-).
    rail_height_tolerance_new: float = 1.0
    #: Tolerance for existing guardrail after resurfacing, inches (+/-).
    rail_height_tolerance_existing: float = 3.0
    rail: str = "12 gauge W-beam (CMS 606.02)"
    #: W-beam panel lengths between splices, feet.
    rail_panel_lengths: tuple[float, ...] = (12.5, 25.0)
    #: Standard post length (steel / rectangular wood), inches.
    standard_post_length: float = 72.0
    #: Round wood post length, inches.
    round_wood_post_length: float = 68.0
    #: Long post length (steel / rectangular wood near slope break), inches.
    long_post_length: float = 97.0
    #: Standard embedment (steel / rectangular wood), inches.
    embedment: float = 40.0
    #: Round wood post embedment, inches.
    round_wood_embedment: float = 36.0
    #: Post bolt diameter, inches.
    post_bolt_diameter: float = 0.625
    #: Nominal blockout cross-section, inches.
    blockout_section: str = "6 x 12"
    #: Max rail-height transition rate (MGS-4.3), inches of height per foot.
    transition_rate_in_per_ft: float = 2.0 / 25.0

    def post_spacing(self, name: str = "standard") -> float:
        """On-center post spacing (inches) for ``"standard"``, ``"half"``,
        or ``"quarter"`` spacing."""
        return MGS_POST_SPACINGS[name].spacing


#: The standard Type MGS guardrail (MGS-2.1).
MGS = MGSStandard()


@dataclass(frozen=True)
class MGSDrawing:
    """One drawing in the Ohio DOT MGS roadway series.

    ``category`` is one of ``standard``, ``special``, ``bridge_terminal``,
    ``transition``, ``anchor``, ``terminal``, ``layout``, ``bridge``.
    ``connects_to`` lists bridge-railing SCD numbers a terminal assembly
    ties into, where stated on the drawing.
    """

    scd: str
    title: str
    sheets: int
    scd_date: str
    category: str
    connects_to: tuple[str, ...] = ()
    notes: str = ""


_DRAWINGS: list[MGSDrawing] = [
    MGSDrawing("MGS-2.1", "Midwest Guardrail System, Standard Type MGS",
               7, "2026-01-16", "standard",
               notes="31 in rail height; W-beam on W6x8.5/W6x9 steel, 6x8 "
               "rectangular wood, or 7.25 in round wood posts."),
    MGSDrawing("MGS-2.2", "Barrier Design with Rub Rail",
               2, "2026-01-16", "special",
               notes="Standard MGS with a rub rail below the W-beam for "
               "curbed/vulnerable-user locations."),
    MGSDrawing("MGS-2.3", "Long-Span Guardrail",
               1, "2025-07-18", "special",
               notes="Unposted MGS span over low-fill culverts (posts "
               "omitted across the structure); 31 in rail height kept. "
               "Paid per foot as Item 606 - Guardrail, Type MGS, "
               "Long-Span."),
    MGSDrawing("MGS-2.4", "Socketed Weak Post Attached to Headwall",
               2, "2026-01-16", "special",
               notes="Weak posts grouted into sockets cast in an HW-"
               "series headwall where embedment is impossible. Paid per "
               "foot as Item 606 - Guardrail, Type MGS With Socketed "
               "Posts."),
    MGSDrawing("MGS-3.1", "MGS Bridge Terminal Assembly, Type 1",
               2, "2026-01-16", "bridge_terminal",
               connects_to=("BR-1-13", "TST-1-99", "RM-4.6"),
               notes="Connects guardrail to deflector-parapet bridge railings "
               "(BR-1-13, single-slope SBR), twin steel tube (TST-1-99), and "
               "concrete barrier end sections (RM-4.6). 12 ft-6 in nested "
               "thrie beam + 6 ft-3 in thrie + 6 ft-3 in asymmetrical "
               "transition; posts 1-6 at quarter spacing."),
    MGSDrawing("MGS-3.2", "MGS Bridge Terminal Assembly, Type 2",
               1, "2025-07-18", "bridge_terminal",
               connects_to=("RM-4.5", "RM-4.6"),
               notes="Trailing-end connection (one-directional roadways "
               "only): W-beam terminal connector through-bolted to an "
               "11x10x5/8 in bearing plate on the wall end."),
    MGSDrawing("MGS-3.3", "MGS Bridge Terminal Assembly, Type TST-2",
               2, "2026-01-16", "bridge_terminal",
               connects_to=("TST-2-21",),
               notes="Terminal assembly connecting MGS to the three steel "
               "tube bridge railing (TST-2-21)."),
    MGSDrawing("MGS-4.1", "MGS Type A Anchor Assembly",
               1, "2025-07-18", "anchor",
               notes="Buried anchor block terminating a run away from "
               "traffic: 18'-9\" rail into a reinforced concrete anchor. "
               "Paid Each as Item 606 - Anchor Assembly, Type A (or "
               "Barrier Design, Type A)."),
    MGSDrawing("MGS-4.2", "MGS Type T Anchor Assembly",
               7, "2025-07-18", "anchor",
               notes="Crashworthy tangent end terminal: 12'-6\" rounded-"
               "end 12-gauge W-beam on breakaway posts with a Type 2 BCT "
               "anchor cable and bearing plate. Paid Each as Item 606 - "
               "Anchor Assembly, MGS Type T."),
    MGSDrawing("MGS-4.3", "Guardrail Transitions",
               1, "2025-07-18", "transition",
               notes="Type 5-to-MGS transition: ramp rail height 27 in to "
               "31 in at max 2 in per 25 ft; half-spacing post between."),
    MGSDrawing("MGS-4.5", "MGS Buried in Backslope End Terminal",
               2, "2025-07-18", "terminal"),
    MGSDrawing("MGS-5.2", "Introduction of Guardrail Runs (Foreslopes 6:1 "
               "or Flatter)", 1, "2016-07-15", "layout"),
    MGSDrawing("MGS-5.3", "Introduction of Guardrail Runs (Foreslopes 6:1 "
               "or Steeper)", 1, "2016-07-15", "layout"),
    MGSDrawing("MGS-6.1", "Guardrail at Bridges",
               2, "2018-01-19", "bridge",
               notes="Arrangement of runs at structures: 25 ft bridge "
               "terminal + 12'-6\" min MGS, 7:1 max taper / flare arcs, "
               "driveway and side-road opening treatments; anchor "
               "assemblies per L&D Vol. 1 603-3."),
    MGSDrawing("MGS-6.2", "MGS Guardrail at Piers",
               1, "2025-07-18", "bridge"),
    MGSDrawing("MGS-6.3", "Thrie Beam Bullnose with Steel Breakaway Posts",
               8, "2025-07-18", "terminal"),
]


#: MGS drawing series keyed by SCD number.
MGS_DRAWINGS: dict[str, MGSDrawing] = {d.scd: d for d in _DRAWINGS}


def mgs_drawing(scd: str) -> MGSDrawing:
    """Look up an MGS drawing by SCD number (e.g. ``"MGS-3.1"``)."""
    return MGS_DRAWINGS[scd]


def bridge_terminal_assemblies() -> list[MGSDrawing]:
    """The MGS bridge terminal assemblies (transitions to bridge railings)."""
    return [d for d in _DRAWINGS if d.category == "bridge_terminal"]


def terminals_for_railing(scd: str) -> list[MGSDrawing]:
    """MGS terminal assemblies that connect to bridge railing ``scd``
    (e.g. ``"TST-2-21"``)."""
    return [d for d in _DRAWINGS if scd in d.connects_to]


# ═════════════════ bridge terminal assemblies (MGS-3.x) ═══════════════════

@dataclass(frozen=True)
class TerminalPostGroup:
    """A run of identical posts within a bridge terminal assembly.
    ``first``/``last`` are 1-based post numbers; lengths in inches."""

    first: int
    last: int
    post: str
    length_in: float
    blockout: str

    @property
    def count(self) -> int:
        return self.last - self.first + 1


@dataclass(frozen=True)
class BridgeTerminalAssembly:
    """One MGS bridge terminal assembly (SCD MGS-3.1 / 3.2 / 3.3).

    ``post_spacings_in`` are the successive c/c spacings starting from
    ``origin`` (each sheet's own stationing direction);
    ``start_offset_in`` is the distance from the origin to post 1.
    ``rail_elements`` list the transition rail pieces in the same
    order.  Payment is Item 606, Each."""

    scd: str
    scd_date: str
    designation: str
    origin: str                      #: what post 1 is measured from
    start_offset_in: float
    post_spacings_in: tuple[float, ...]
    post_groups: tuple[TerminalPostGroup, ...] = ()
    rail_elements: tuple[str, ...] = ()
    connection: str = ""
    curb_note: str = ""
    connects_to: tuple[str, ...] = ()
    pay_item: str = ""
    notes: str = ""

    @property
    def n_posts(self) -> int:
        return len(self.post_spacings_in) + 1

    def post_stations_in(self) -> tuple[float, ...]:
        """Post centers (inches) from ``origin``."""
        x = self.start_offset_in
        out = [x]
        for s in self.post_spacings_in:
            x += s
            out.append(x)
        return tuple(out)

    @property
    def length_in(self) -> float:
        """Origin to the last post, inches."""
        return self.post_stations_in()[-1]


BRIDGE_TERMINALS: dict[str, BridgeTerminalAssembly] = {
    # ── MGS-3.1 Type 1: thrie-beam BTA to deflector parapets (BR-1-13 /
    # single-slope SBR), TST-1-99, or RM-4.6 concrete barrier end
    # sections.  13 posts: 9 quarter-spaces then 3 half-spaces.
    "Type 1": BridgeTerminalAssembly(
        scd="MGS-3.1", scd_date="2026-01-16", designation="Type 1",
        origin="parapet / barrier end",
        start_offset_in=22.75,
        post_spacings_in=(18.75,) * 9 + (37.5,) * 3,
        post_groups=(
            TerminalPostGroup(1, 6, "W6x9 steel or 6x8 wood", 78.0,
                              '6"x12"x19" (or 6"x12"x22") wood'),
            TerminalPostGroup(7, 13, "standard MGS post (MGS-2.1)", 72.0,
                              '6"x12"x19" posts 7-12; standard '
                              '6"x12"x14" at post 13'),
        ),
        rail_elements=("12'-6\" nested thrie beam",
                       "6'-3\" thrie beam",
                       "6'-3\" asymmetrical W-to-thrie transition (10 ga)"),
        connection="five 7/8 in anchors each side (Item 712.01 or "
        "FF-S325 Grp VIII Type 1) into a concrete barrier end section; "
        "7/8 in ASTM A325/A449 through bolts into Bearing Plate A for a "
        "one-sided parapet connection",
        curb_note="Type 4A/4B/4C curb (BP-5.1) required under the "
        "thrie-beam portion at concrete barrier/parapet connections, "
        "not extending past post 11; no curb at TST bridge rail.",
        connects_to=("BR-1-13", "SBR-1-20", "TST-1-99", "RM-4.6"),
        pay_item="Item 606 - MGS Bridge Terminal Assembly, Type 1 (or "
        "Type 1, Barrier Design), Each",
        notes="49 in min post embedment at posts 1-6. An 18'-9\" thrie "
        "beam may replace the 12'-6\" + 6'-3\" pair. Place the first "
        "MGS post 3'-1 1/2\" past the BTA; provide at least 12'-6\" of "
        "MGS guardrail before the end anchor."),
    # ── MGS-3.2 Type 2: trailing-end connection, one-directional
    # roadways only — a single W-beam terminal connector on a bearing
    # plate; everything downstream is standard MGS.
    "Type 2": BridgeTerminalAssembly(
        scd="MGS-3.2", scd_date="2025-07-18", designation="Type 2",
        origin="trailing end of parapet / barrier",
        start_offset_in=37.5,
        post_spacings_in=(),
        post_groups=(
            TerminalPostGroup(1, 1, "standard MGS post (MGS-2.1)", 72.0,
                              "standard MGS blockout"),
        ),
        rail_elements=("single W-beam rail with W-beam terminal "
                       "connector, splice lapped in the direction of "
                       "traffic",),
        connection='7/8 in ASTM A325/A449 through bolts into an '
        '11" x 10" x 5/8" bearing plate (four 1 in dia holes)',
        connects_to=("RM-4.5", "RM-4.6"),
        pay_item="Item 606 - MGS Bridge Terminal Assembly, Type 2, Each",
        notes="Trailing ends on one-directional roadways only — do not "
        "use within the clear zone of opposing traffic. Keep the first "
        "panel tangential to the roadway before applying standard "
        "flares."),
    # ── MGS-3.3 Type TST-2: W-to-thrie transition to the three steel
    # tube bridge railing (TST-2-21).  10 posts drawn from the MGS side.
    "Type TST-2": BridgeTerminalAssembly(
        scd="MGS-3.3", scd_date="2026-01-16", designation="Type TST-2",
        origin="MGS end (last standard-run post)",
        start_offset_in=0.0,
        post_spacings_in=(37.5, 37.5, 37.5, 18.75, 18.75, 18.75, 18.75,
                          37.5, 37.5),
        post_groups=(
            TerminalPostGroup(1, 3, "W6x9 steel", 72.0,
                              '6"x12"x14 3/4" wood'),
            TerminalPostGroup(4, 7, "W6x9 steel", 72.0,
                              '6"x12"x19" wood'),
            TerminalPostGroup(8, 10, "W6x15 steel", 84.0,
                              '6"x12"x19" wood'),
        ),
        rail_elements=("6'-3\" 10-gauge W-to-thrie symmetrical "
                       "transition segment",
                       "6'-3\" 12-gauge single thrie beam segment",
                       "12'-6\" nested 12-gauge thrie beam segment"),
        connection="thrie beam terminates 11 3/8 in past post 10 at the "
        "TST-2-21 connection (see TST-2-21 for the bridge-side details)",
        connects_to=("TST-2-21",),
        pay_item="Item 606 - MGS Bridge Terminal Assembly, Type TST-2, "
        "Each",
        notes="Posts 1-7 embed 3'-4\"; posts 8-10 embed 4'-4\". Rail "
        "rises from the 31 in MGS height to 2'-10\" thrie at the TST."),
}


def bridge_terminal(designation: str) -> BridgeTerminalAssembly:
    """Look up a bridge terminal assembly (``"Type 1"``, ``"Type 2"``,
    ``"Type TST-2"``)."""
    try:
        return BRIDGE_TERMINALS[designation]
    except KeyError:
        raise ValueError(
            f"unknown MGS bridge terminal {designation!r}; choose one of "
            f"{sorted(BRIDGE_TERMINALS)}")


@dataclass(frozen=True)
class BridgeTerminalLayout:
    """Post stations and members of one MGS bridge terminal assembly."""

    terminal: BridgeTerminalAssembly
    post_stations_in: tuple[float, ...]
    posts: tuple[tuple[int, str, float, str], ...]  # (no, post, length, blockout)
    length_in: float
    notes: tuple[str, ...] = ()


def layout_bridge_terminal(designation: str) -> BridgeTerminalLayout:
    """Expand a :data:`BRIDGE_TERMINALS` entry into per-post members."""
    t = bridge_terminal(designation)
    stations = t.post_stations_in()
    posts = []
    for g in t.post_groups:
        for n in range(g.first, g.last + 1):
            if n <= len(stations):
                posts.append((n, g.post, g.length_in, g.blockout))
    notes = (
        f"ODOT {t.scd} MGS bridge terminal assembly, {t.designation} "
        f"(rev. {t.scd_date}); stationed from the {t.origin}",
        "Rail: " + " + ".join(t.rail_elements),
        f"Connection: {t.connection}",
        t.pay_item,
    )
    if t.curb_note:
        notes = (*notes, t.curb_note)
    if t.notes:
        notes = (*notes, t.notes)
    return BridgeTerminalLayout(
        terminal=t, post_stations_in=stations, posts=tuple(posts),
        length_in=t.length_in, notes=notes)


# ═════════════════════ standard MGS run layout (MGS-2.1) ══════════════════

@dataclass(frozen=True)
class MGSRunLayout:
    """Posts and W-beam panels of one straight standard-MGS run."""

    length_ft: float
    spacing: PostSpacing
    post_stations_ft: tuple[float, ...]
    n_panels: int
    panel_length_ft: float
    rail_height_in: float = 31.0
    notes: tuple[str, ...] = ()


def layout_mgs_run(length_ft: float, *, spacing: str = "standard",
                   panel_length_ft: float = 25.0) -> MGSRunLayout:
    """Lay out a straight MGS-2.1 guardrail run: posts at the chosen
    spacing (``"standard"`` / ``"half"`` / ``"quarter"``) and W-beam
    panels of ``panel_length_ft`` (12.5 or 25 ft between splices).
    Raises ``ValueError`` for a non-positive length, an unknown spacing,
    or a non-standard panel length."""
    if length_ft <= 0.0:
        raise ValueError("length_ft must be > 0")
    if panel_length_ft not in MGS.rail_panel_lengths:
        raise ValueError(
            f"panel_length_ft must be one of {MGS.rail_panel_lengths}")
    try:
        sp = MGS_POST_SPACINGS[spacing]
    except KeyError:
        raise ValueError(
            f"spacing must be one of {sorted(MGS_POST_SPACINGS)}, "
            f"not {spacing!r}") from None
    step_ft = sp.spacing / 12.0
    n = int(length_ft // step_ft)
    stations = tuple(round(i * step_ft, 6) for i in range(n + 1))
    n_panels = int(-(-length_ft // panel_length_ft))
    notes = (
        f"ODOT {MGS.scd} standard Type MGS (rev. {MGS.scd_date}): "
        f"{MGS.rail} at {MGS.rail_height:g} in "
        f"(+/- {MGS.rail_height_tolerance_new:g} in new construction)",
        f"{sp.name} post spacing {sp.spacing:g} in with "
        f"{sp.blockout_height:g} in blockouts; standard posts "
        f"{MGS.standard_post_length:g} in long, {MGS.embedment:g} in "
        "embedment.",
    )
    return MGSRunLayout(
        length_ft=length_ft, spacing=sp, post_stations_ft=stations,
        n_panels=n_panels, panel_length_ft=panel_length_ft,
        rail_height_in=MGS.rail_height, notes=notes)
