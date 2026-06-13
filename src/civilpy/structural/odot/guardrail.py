#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

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

Sources (SCD number — latest cited revision):
    MGS-2.1  Midwest Guardrail System, Standard Type MGS   (rev. 2026-01-16)
    MGS-4.3  Guardrail Transitions                         (rev. 2025-07-18)
    MGS-3.1  MGS Bridge Terminal Assembly, Type 1          (rev. 2026-01-16)
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
               2, "2026-01-16", "special"),
    MGSDrawing("MGS-2.3", "Long-Span Guardrail",
               1, "2025-07-18", "special"),
    MGSDrawing("MGS-2.4", "Socketed Weak Post Attached to Headwall",
               2, "2026-01-16", "special"),
    MGSDrawing("MGS-3.1", "MGS Bridge Terminal Assembly, Type 1",
               2, "2026-01-16", "bridge_terminal",
               connects_to=("BR-1-13", "TST-1-99", "RM-4.6"),
               notes="Connects guardrail to deflector-parapet bridge railings "
               "(BR-1-13, single-slope SBR), twin steel tube (TST-1-99), and "
               "concrete barrier end sections (RM-4.6). 12 ft-6 in nested "
               "thrie beam + 6 ft-3 in thrie + 6 ft-3 in asymmetrical "
               "transition; posts 1-6 at quarter spacing."),
    MGSDrawing("MGS-3.2", "MGS Bridge Terminal Assembly, Type 2",
               1, "2025-07-18", "bridge_terminal"),
    MGSDrawing("MGS-3.3", "MGS Bridge Terminal Assembly, Type TST-2",
               2, "2026-01-16", "bridge_terminal",
               connects_to=("TST-2-21",),
               notes="Terminal assembly connecting MGS to the three steel "
               "tube bridge railing (TST-2-21)."),
    MGSDrawing("MGS-4.1", "MGS Type A Anchor Assembly",
               1, "2025-07-18", "anchor"),
    MGSDrawing("MGS-4.2", "MGS Type T Anchor Assembly",
               7, "2025-07-18", "anchor"),
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
               2, "2018-01-19", "bridge"),
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
