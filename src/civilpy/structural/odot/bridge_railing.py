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

"""Ohio DOT standard bridge railings and barriers.

Geometry, reinforcement, and design data transcribed from the Ohio DOT
Standard Bridge Drawings (Office of Structural Engineering).  Each entry
records the crash test level stated on the drawing's design-criteria note;
that key indexes the Table A13.2-1 design forces carried in
:mod:`civilpy.structural.aashto.lrfd.railing`, so a cataloged railing can be
fed straight into the yield-line and deck-overhang checks there.

Lengths are in inches and areas in square inches unless a field name says
otherwise.  Concrete strength ``f_c`` and reinforcing/structural-steel
yields are in ksi.  Values are spot-checked against the cited drawings in
the test suite; the drawings remain the controlling document for detailing.

Sources (SCD number — drawing date / latest cited revision):
    BR-1-13   New Jersey shape concrete bridge railing      (rev. 2014-01-17)
    BR-2-15   Bridge sidewalk railing with concrete barrier (rev. 2024-07-19)
    SBR-1-20  Single slope concrete bridge railing, 42 in   (rev. 2024-07-19)
    SBR-2-20  Single slope concrete median railing, 57 in   (rev. 2024-07-19)
    SBR-3-20  Single slope concrete bridge railing, 36 in   (rev. 2024-07-19)
    TST-1-99  Twin steel tube bridge railing                (rev. 2021-01-15)
    TST-2-21  Three steel tube bridge railing               (rev. 2025-01-17)
    DBR-2-73  Deep beam bridge guardrail                    (rev. 2002-07-19)
    DBR-3-11  Deep beam bridge retrofit railing             (2011-07-15)
    TBR-1-11  Thrie beam retrofit railing                   (rev. 2013-01-18)
    PCB-91    Portable concrete barrier                     (rev. 2020-07-17)
"""

from dataclasses import dataclass

from civilpy.structural.aashto.lrfd.railing import (
    TEST_LEVEL_LOADS,
    TestLevelLoad,
)


@dataclass(frozen=True)
class BridgeRailing:
    """One Ohio DOT standard bridge railing / barrier configuration.

    ``test_level`` is the NCHRP 350 / MASH level stated on the drawing
    (``"TL-2"`` .. ``"TL-6"``); it keys :data:`TEST_LEVEL_LOADS`.  An empty
    string means the drawing states no numeric crash test level.  Fields
    left as ``None`` / ``""`` are not called out (or not applicable) on the
    drawing.

    Concrete-parapet entries populate ``section_area`` (gross area of the
    standard, non-transition section), ``f_c``/``f_y``, and the vertical-bar
    fields.  Post-and-beam steel railings populate ``post_shape``,
    ``post_spacing``, ``rail_element``, and ``f_y_steel`` instead.
    """

    scd: str
    scd_date: str
    designation: str
    name: str
    shape: str
    material: str
    test_level: str
    height: float | None = None
    base_width: float | None = None
    top_width: float | None = None
    section_area: float | None = None
    f_c: float | None = None
    f_y: float | None = None
    #: Maximum on-center spacing of vertical reinforcing bars, inches.
    vertical_bar_spacing: float | None = None
    #: Standard-bar designation numbers present in the section (#5, #6, ...).
    bar_sizes: tuple[int, ...] = ()
    #: Length of the standard approach transition section, feet.
    transition_length_ft: float | None = None
    #: Concrete volume of one transition section, cubic yards.
    transition_volume_cy: float | None = None
    #: Steel post shape for post-and-beam railings (e.g. ``"W6x25"``).
    post_shape: str = ""
    #: Maximum post spacing, inches.
    post_spacing: float | None = None
    #: Longitudinal rail element(s) (e.g. ``"2 - TS 8x4x5/16"``).
    rail_element: str = ""
    #: Structural / tube steel minimum yield, ksi.
    f_y_steel: float | None = None
    #: Unit weight of the railing, lb/ft.
    weight_per_ft: float | None = None
    #: Precast segment length(s), feet (portable barrier).
    segment_length_ft: tuple[float, ...] = ()
    notes: str = ""

    def test_level_load(self) -> TestLevelLoad | None:
        """The Table A13.2-1 design forces for this railing's test level, or
        ``None`` if the drawing states no numeric crash test level."""
        return TEST_LEVEL_LOADS.get(self.test_level)

    def meets_minimum_height(self) -> bool | None:
        """Whether the railing's height satisfies the minimum rail height
        ``H`` for its test level (Table A13.2-1, ``h_min``).  ``None`` when
        the height or test level is not recorded.

        For combination and post-and-beam railings ``height`` may be the
        crashworthy element height only; treat the result accordingly.
        """
        tl = self.test_level_load()
        if tl is None or self.height is None:
            return None
        return self.height >= tl.h_min

    def design_force_check(
        self, m_c: float, m_w: float, m_b: float = 0.0, end_region: bool = False
    ):
        """Run the AASHTO A13.3.1 yield-line check for this railing against
        its own test-level design forces.

        Only meaningful for concrete-parapet entries.  ``m_c`` (kip-ft/ft),
        ``m_w`` and ``m_b`` (kip-ft) are the wall's flexural resistances;
        the railing's catalog ``height`` (in) is converted to feet.  Returns
        a :class:`~civilpy.structural.aashto.lrfd.core.CheckResult` whose
        ``demand`` is the Table A13.2-1 transverse force ``Ft``.
        """
        from civilpy.structural.aashto.lrfd.railing import (
            parapet_test_level_check,
        )

        if not self.test_level:
            raise ValueError(f"{self.designation} has no crash test level")
        if self.height is None:
            raise ValueError(f"{self.designation} has no recorded height")
        return parapet_test_level_check(
            test_level=self.test_level,
            m_c=m_c,
            m_w=m_w,
            h_ft=self.height / 12.0,
            m_b=m_b,
            end_region=end_region,
        )


# Ordered so that the catalog reads top-to-bottom by SCD number.
_CATALOG: list[BridgeRailing] = [
    # ============================================================ BR-1-13
    # New Jersey (NJ) safety-shape concrete parapet, two heights.  Design-
    # criteria note (sheet 9/9): the 36 in parapet meets NCHRP 350 TL-4 and
    # the 42 in parapet meets NCHRP 350 TL-5; f'c = 4.5 ksi, fy = 60 ksi.
    # Standard vertical bars at 12 in max o.c. (Y6 = #6, Y5 = #5; X5/X6
    # longitudinal).  14 ft approach transitions to deep-beam guardrail.
    BridgeRailing(
        scd="BR-1-13",
        scd_date="2014-01-17",
        designation="BR-1 (36 in)",
        name="New Jersey shape concrete bridge railing, 36 in",
        shape="New Jersey",
        material="reinforced concrete",
        test_level="TL-4",
        height=36.0,
        base_width=18.0,
        top_width=8.0,
        section_area=423.25,
        f_c=4.5,
        f_y=60.0,
        vertical_bar_spacing=12.0,
        bar_sizes=(5, 6),
        transition_length_ft=14.0,
        transition_volume_cy=1.63,
        notes="GFRP deflection-joint stiffening at sawcut joints <= 15 ft o.c.",
    ),
    BridgeRailing(
        scd="BR-1-13",
        scd_date="2014-01-17",
        designation="BR-1 (42 in)",
        name="New Jersey shape concrete bridge railing, 42 in",
        shape="New Jersey",
        material="reinforced concrete",
        test_level="TL-5",
        height=42.0,
        base_width=18.0,
        top_width=8.0,
        section_area=474.50,
        f_c=4.5,
        f_y=60.0,
        vertical_bar_spacing=12.0,
        bar_sizes=(5, 6),
        transition_length_ft=14.0,
        transition_volume_cy=1.71,
        notes="Taller TL-5 variant of the 36 in BR-1; transition vertical "
        "bars at 9 in o.c.",
    ),
    # ============================================================ BR-2-15
    # Bridge sidewalk railing with concrete barrier: a 42 in (3 ft-6 in)
    # crashworthy concrete barrier carrying a twin steel tube pedestrian
    # rail on top.  Design criteria (sheet 5/5): NCHRP 350 TL-4, AASHTO
    # LRFD BDS 2014; f'c = 4.5 ksi, fy = 60 ksi, tube fy = 46 ksi.  HSS
    # 4x4x3/16 posts at 6 ft-6 in carry two HSS 4x3x1/4 rails.
    BridgeRailing(
        scd="BR-2-15",
        scd_date="2024-07-19",
        designation="BR-2 (sidewalk barrier + twin tube)",
        name="Bridge sidewalk railing with concrete barrier (twin steel tube)",
        shape="combination (barrier + steel tube)",
        material="reinforced concrete + steel",
        test_level="TL-4",
        height=42.0,
        top_width=12.0,
        f_c=4.5,
        f_y=60.0,
        f_y_steel=46.0,
        vertical_bar_spacing=12.0,
        bar_sizes=(5,),
        post_shape="HSS 4x4x3/16",
        post_spacing=78.0,
        rail_element="2 - HSS 4x3x1/4",
        notes="The 42 in concrete barrier is the TL-4 crashworthy element; a "
        "twin steel tube pedestrian rail mounts on top (combined height "
        "higher). Optional vandal protection fence (VPF-1-24).",
    ),
    # ============================================================ SBR-3-20
    # Single-slope concrete parapet, 36 in.  Design criteria (sheet 5/5):
    # NCHRP 350 & MASH TL-4, AASHTO LRFD BDS 9th Ed.; f'c = 4.5 ksi, fy = 60
    # ksi; GFRP horizontal/stiffening bars (C&MS 705.28, E = 8700 ksi).
    BridgeRailing(
        scd="SBR-3-20",
        scd_date="2020-01-17",
        designation="SBR-3 (36 in)",
        name="Single slope concrete bridge railing, 36 in",
        shape="single slope",
        material="reinforced concrete",
        test_level="TL-4",
        height=36.0,
        base_width=18.0,
        section_area=524.0,
        f_c=4.5,
        f_y=60.0,
        vertical_bar_spacing=12.0,
        bar_sizes=(4, 5, 6),
        transition_length_ft=14.0,
        transition_volume_cy=1.74,
        notes="GFRP horizontal (X4) and stiffening (Y401/Y402) bars; steel "
        "vertical bars.",
    ),
    # ============================================================ SBR-1-20
    # Single-slope concrete parapet, 42 in.  Design criteria (sheet 5/5):
    # NCHRP 350 & MASH TL-5, AASHTO LRFD BDS 9th Ed.; f'c = 4.5 ksi, fy = 60
    # ksi; GFRP horizontal/stiffening bars (C&MS 705.28, E = 8700 ksi).
    BridgeRailing(
        scd="SBR-1-20",
        scd_date="2020-01-17",
        designation="SBR-1 (42 in)",
        name="Single slope concrete bridge railing, 42 in",
        shape="single slope",
        material="reinforced concrete",
        test_level="TL-5",
        height=42.0,
        base_width=18.0,
        section_area=588.0,
        f_c=4.5,
        f_y=60.0,
        vertical_bar_spacing=12.0,
        bar_sizes=(4, 5, 6),
        transition_length_ft=14.0,
        transition_volume_cy=1.82,
        notes="GFRP horizontal (X4) and stiffening (Y401/Y402) bars; steel "
        "vertical bars.",
    ),
    # ============================================================ SBR-2-20
    # Single-slope concrete *median* barrier, 57 in.  Design criteria
    # (sheet 5/5): the single Type B1 barrier meets NCHRP 350 & MASH TL-3;
    # the back-to-back pair (6 in max gap) meets NCHRP 350 & MASH TL-5.
    # f'c = 4.5 ksi, fy = 60 ksi.  Section area = 9.05 sq ft = 1303.2 sq in
    # per barrier.
    BridgeRailing(
        scd="SBR-2-20",
        scd_date="2020-07-17",
        designation="SBR-2 (57 in median)",
        name="Single slope concrete median bridge railing, 57 in, Type B1",
        shape="single slope median",
        material="reinforced concrete",
        test_level="TL-3",
        height=57.0,
        base_width=33.75,
        top_width=12.0,
        section_area=1303.2,
        f_c=4.5,
        f_y=60.0,
        vertical_bar_spacing=24.0,
        bar_sizes=(4, 5, 8),
        notes="Single (Type B1) median barrier; #8 dowels in the unreinforced "
        "median run. Vertical bars at 24 in o.c. for Type B1.",
    ),
    BridgeRailing(
        scd="SBR-2-20",
        scd_date="2020-07-17",
        designation="SBR-2 (57 in median, back-to-back)",
        name="Single slope back-to-back concrete median bridge railing, 57 in",
        shape="single slope median",
        material="reinforced concrete",
        test_level="TL-5",
        height=57.0,
        base_width=33.75,
        top_width=12.0,
        section_area=1303.2,
        f_c=4.5,
        f_y=60.0,
        vertical_bar_spacing=7.0,
        bar_sizes=(4, 5, 6),
        notes="Two SBR-2 barriers back-to-back with 6 in max gap; vertical "
        "bars at 7 in o.c.",
    ),
    # ============================================================ TST-1-99
    # Twin steel tube railing.  General notes (sheet 4/4): accepted to NCHRP
    # 350 TL-4.  Two TS 8x4x5/16 tubes on W6x25 posts at 6 ft-3 in max
    # spacing.  Tube fy = 46 ksi, other steel fy = 50 ksi, reinf fy = 60
    # ksi.  Not for box-beam bridges with overhang > 2 in or top flange
    # < 5 in.
    BridgeRailing(
        scd="TST-1-99",
        scd_date="1999-07-06",
        designation="TST-1 (twin steel tube)",
        name="Twin steel tube bridge railing",
        shape="post-and-beam (twin tube)",
        material="steel",
        test_level="TL-4",
        f_y=60.0,
        post_shape="W6x25",
        post_spacing=75.0,
        rail_element="2 - TS 8x4x5/16",
        f_y_steel=46.0,
        notes="NCHRP 350 TL-4. Measurement = flush-post length + 4 ft-11 in. "
        "Not for box-beam bridges with overhang > 2 in or top flange < 5 in.",
    ),
    # ============================================================ TST-2-21
    # Three steel tube railing.  General notes (sheet 15/15): MASH TL-4
    # (transition to MGS guardrail is MASH TL-3).  Three HSS tubes on
    # fabricated posts (post length 4 ft-6 in).  HSS & plate fy = 50 ksi,
    # reinf fy = 60 ksi, f'c = 4.5 ksi.  Unit weight 80 lb/ft at 8 ft posts.
    BridgeRailing(
        scd="TST-2-21",
        scd_date="2021-07-16",
        designation="TST-2 (three steel tube)",
        name="Three steel tube bridge railing",
        shape="post-and-beam (three tube)",
        material="steel",
        test_level="TL-4",
        f_c=4.5,
        f_y=60.0,
        post_spacing=96.0,
        rail_element="3 - HSS tube",
        f_y_steel=50.0,
        weight_per_ft=80.0,
        notes="MASH TL-4 (transition to MGS guardrail is MASH TL-3). Post "
        "length 4 ft-6 in; min box-beam depth 17 in; max future wearing "
        "surface 3 in.",
    ),
    # ============================================================ DBR-2-73
    # Deep beam bridge guardrail (legacy, 1973).  W6x25 posts at 6 ft-3 in
    # max; TS 8x4x0.1875 tube behind the deep-beam rail (12 ft-6 in min
    # splice).  Posts ASTM A709 Gr 36/50, anchors A325.  The drawing states
    # no numeric NCHRP/MASH test level (predates NCHRP 350).
    BridgeRailing(
        scd="DBR-2-73",
        scd_date="1973-04-10",
        designation="DBR-2 (deep beam)",
        name="Deep beam bridge guardrail",
        shape="post-and-beam (deep beam)",
        material="steel",
        test_level="",
        post_shape="W6x25",
        post_spacing=75.0,
        rail_element="deep beam rail + TS 8x4x0.1875",
        f_y_steel=36.0,
        notes="Legacy 1973 guardrail; drawing states no numeric crash test "
        "level. See DBR-3-11 for the NCHRP 350 TL-3 retrofit upgrade.",
    ),
    # ============================================================ DBR-3-11
    # Deep beam bridge retrofit railing.  Upgrade retrofit to DBR-2-73,
    # accepted by FHWA to NCHRP 350 TL-3 (acceptance letter HSSD/B-207,
    # 2010-11-10).  Adds a W-beam rail + HSS 8x4x3/16 rubrail and L6x4x3/8
    # support angle to the existing W6x25 posts at 6 ft-3 in.
    BridgeRailing(
        scd="DBR-3-11",
        scd_date="2011-07-15",
        designation="DBR-3 (deep beam retrofit)",
        name="Deep beam bridge retrofit railing",
        shape="post-and-beam (deep beam retrofit)",
        material="steel",
        test_level="TL-3",
        height=29.0,
        post_shape="W6x25",
        post_spacing=75.0,
        rail_element="W-beam rail + HSS 8x4x3/16",
        f_y_steel=36.0,
        notes="NCHRP 350 TL-3 retrofit of DBR-2-73 (FHWA HSSD/B-207). HSS "
        "rubrail continuous over >= 3 posts.",
    ),
    # ============================================================ TBR-1-11
    # Thrie beam retrofit railing.  Adapts bridges built to retired
    # standards AR-1-57 and BR-1-65 (1 ft / 2 ft safety curbs) to a thrie
    # beam rail (AASHTO M180 Type II Class B, 10 ga) on W6x25 posts with
    # 6x8 wood blocks at 6 ft-3 in.  f'c = 4.0 ksi.  Acceptable for use on
    # the NHS; the drawing states no numeric NCHRP/MASH test level.
    BridgeRailing(
        scd="TBR-1-11",
        scd_date="2011-10-21",
        designation="TBR-1 (thrie beam retrofit)",
        name="Thrie beam retrofit railing",
        shape="post-and-beam (thrie beam)",
        material="steel on concrete curb",
        test_level="",
        height=25.5,
        f_c=4.0,
        post_shape="W6x25",
        post_spacing=75.0,
        rail_element="thrie beam (M180 Type II Class B)",
        notes="Retrofit for AR-1-57 / BR-1-65 railings with 1 ft or 2 ft "
        "safety curbs. NHS-acceptable; no numeric crash test level stated.",
    ),
    # ============================================================ PCB-91
    # Bridge-mounted portable concrete barrier.  Description note: compliant
    # with NCHRP 350 — TL-3 unanchored, TL-4 when fully anchored on the
    # traffic side.  f'c = 4.0 ksi; #5 bars, 3/4 in hinge bars; 10 ft or
    # 12 ft segments; 32 in tall, 24 in base.
    BridgeRailing(
        scd="PCB-91",
        scd_date="1992-04-24",
        designation="PCB (portable, unanchored)",
        name="Portable concrete barrier, unanchored",
        shape="New Jersey",
        material="precast concrete",
        test_level="TL-3",
        height=32.0,
        base_width=24.0,
        f_c=4.0,
        bar_sizes=(5,),
        segment_length_ft=(10.0, 12.0),
        notes="Pin-and-loop hinge connection; #8/#5 reinforcement per 509.02. "
        "Anchor fully on the traffic side for TL-4 (see PCB anchored entry).",
    ),
    BridgeRailing(
        scd="PCB-91",
        scd_date="1992-04-24",
        designation="PCB (portable, anchored)",
        name="Portable concrete barrier, fully anchored (traffic side)",
        shape="New Jersey",
        material="precast concrete",
        test_level="TL-4",
        height=32.0,
        base_width=24.0,
        f_c=4.0,
        bar_sizes=(5,),
        segment_length_ft=(10.0, 12.0),
        notes="Same barrier as the unanchored PCB; fully anchored on the "
        "traffic side it satisfies NCHRP 350 TL-4.",
    ),
]


#: Catalog keyed by ``designation``.
BRIDGE_RAILINGS: dict[str, BridgeRailing] = {r.designation: r for r in _CATALOG}


def railing(designation: str) -> BridgeRailing:
    """Look up a railing by its ``designation`` (e.g. ``"BR-1 (36 in)"``)."""
    return BRIDGE_RAILINGS[designation]


def railings_for_test_level(test_level: str) -> list[BridgeRailing]:
    """All cataloged railings rated for ``test_level`` (e.g. ``"TL-4"``)."""
    return [r for r in _CATALOG if r.test_level == test_level]
