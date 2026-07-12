#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT standard roadway (at-grade) single-slope concrete barriers.

Office of Roadway Engineering counterparts of the Office of Structural
Engineering's bridge parapets in :mod:`civilpy.structural.odot.bridge_railing`
-- same 5.25:1 single-slope face, but freestanding at grade (median or
shoulder) rather than backed against a deck edge. ``shape`` carries
``"single slope"`` so :func:`civilpy.structural.rhino_barrier.shape_family`
routes these through the same profile-sweep engine; unlike a deck-edge
parapet a roadway barrier is placed with ``side=0`` (freestanding, symmetric
about its centerline).

Types B/B1/D/N are fully dimensioned on their drawings (fixed height, top,
and base width). Types C/C1 are *variable-height* siblings of B/B1 -- the
drawings show a project-defined upper extension ("Varies ... See Plans for
dimensions") added above the fixed B/B1 body, so no formula is transcribed
for the extension; ``height``/``base_width`` here are the B/B1 base-body
values and ``notes`` records the variable range. Type E (RM-4.9) differs
structurally -- a shorter 36 in barrier on a cast-in-place moment slab
foundation with a curved/vertical face -- and its concrete envelope is not
dimensioned on the drawing (only the rebar cage is); its catalog entry
therefore omits ``top_width``/``base_width`` rather than inventing them, and
:func:`layout_roadway_barrier` raises if asked to build its profile.

Two companion drawings extend the same profile engine along the run:

* **RM-4.6 end sections** (:func:`layout_barrier_end_section`): the
  cast-in-place taper that steps a Type B / B1 / D barrier down to a
  32 in vertical-faced end for a Bridge Terminal Assembly or impact
  attenuator connection — profiles at the drawing's stations, ready to
  loft.
* **RM-4.4 transitions** (:func:`layout_barrier_transition`): the
  plan-view widening that wraps a Type B/B1/C/C1 barrier around a sign
  support / light tower foundation or a bridge pier — half-width per
  station over the 40 ft tapers.

Lengths are in inches unless noted. Concrete strength ``f_c`` in ksi.

Sources (SCD number — drawing date / latest cited revision):
    RM-4.3  Single slope barrier, Types B, B1, C, C1  (rev. 2025-07-18)
    RM-4.4  Single slope barrier transitions          (rev. 2025-01-17)
    RM-4.5  Single slope barrier, Type D              (rev. 2026-01-16)
    RM-4.6  Concrete barrier end sections, Types B, B1, D (rev. 2025-07-18)
    RM-4.8  Single slope barrier, Type N (general design) (rev. 2026-01-16)
    RM-4.9  Single slope barrier, Type E, moment slab foundation (rev. 2025-07-18)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoadwayBarrier:
    """One Ohio DOT standard roadway single-slope barrier type.

    Mirrors the field names :func:`civilpy.structural.rhino_barrier
    .barrier_profile` reads (``shape``, ``height``, ``base_width``,
    ``top_width``) so the same profile-sweep engine renders these as it does
    the structural bridge parapets.
    """

    scd: str
    scd_date: str
    designation: str
    name: str
    shape: str
    material: str = "reinforced concrete"
    height: float | None = None
    top_width: float | None = None
    base_width: float | None = None
    slope_h_to_v: float | None = None
    f_c: float | None = None
    #: Foundation: "pavement" (cast on/dowelled to pavement), "leveling pad"
    #: (RM-4.8 Type N), "compacted soil" (RM-4.5 Type D), or "moment slab"
    #: (RM-4.9 Type E).
    foundation: str = "pavement"
    #: Max unsealed-joint / contraction-joint spacing, ft.
    joint_spacing_ft: float | None = None
    notes: str = ""


_CATALOG: list[RoadwayBarrier] = [
    # ============================================================ RM-4.3
    # Single slope barrier, Types B/B1 (cast on new/existing pavement) and
    # C/C1 (variable-height siblings). Sheet 1: dimensions for B/B1. Sheet
    # 2: "See Sheet 1 for Types B and B1"; C/C1 add a project-variable
    # extension above the B/B1 body ("Varies, 24 in max. See Plans for
    # dimensions"), giving an overall height range of 42-66 in (C) / 57-81
    # in (D1... C1). 5.25:1 face slope; 20 ft max unsealed joint spacing;
    # 4000 psi concrete (CMS 499); #8 x 12 in epoxy dowels at construction
    # joints (CMS 622.02).
    RoadwayBarrier(
        scd="RM-4.3", scd_date="2025-07-18", designation="Type B",
        name="Single slope barrier, Type B (concrete pavement)",
        shape="single slope", height=42.0, top_width=12.0, base_width=28.0,
        slope_h_to_v=5.25, f_c=4.0, foundation="pavement",
        joint_spacing_ft=20.0,
        notes="Cast on new concrete pavement (8+12+8 in base split); "
        "asphalt-pavement variant uses the same body with an alternate "
        "59 in extended toe (not modeled).",
    ),
    RoadwayBarrier(
        scd="RM-4.3", scd_date="2025-07-18", designation="Type B1",
        name="Single slope barrier, Type B1 (asphalt pavement)",
        shape="single slope", height=57.0, top_width=12.0, base_width=33.75,
        slope_h_to_v=5.25, f_c=4.0, foundation="pavement",
        joint_spacing_ft=20.0,
        notes="Taller (57 in) variant of Type B for asphalt pavement "
        "(10.875+12+10.875 in base split).",
    ),
    RoadwayBarrier(
        scd="RM-4.3", scd_date="2025-07-18", designation="Type C",
        name="Single slope barrier, Type C (variable height, asphalt)",
        shape="single slope", height=42.0, top_width=12.0, base_width=28.0,
        slope_h_to_v=5.25, f_c=4.0, foundation="pavement",
        joint_spacing_ft=20.0,
        notes="Variable-height sibling of Type B: an additional 0-24 in "
        "extension is added above this 42 in body per project plans (sheet "
        "gives no formula for the extension geometry); overall height "
        "ranges 42-66 in. Height/base values here are the fixed Type B "
        "base body only.",
    ),
    RoadwayBarrier(
        scd="RM-4.3", scd_date="2025-07-18", designation="Type C1",
        name="Single slope barrier, Type C1 (variable height, concrete)",
        shape="single slope", height=57.0, top_width=12.0, base_width=33.75,
        slope_h_to_v=5.25, f_c=4.0, foundation="pavement",
        joint_spacing_ft=20.0,
        notes="Variable-height sibling of Type B1: an additional 0-24 in "
        "extension above this 57 in body per project plans; overall height "
        "ranges 57-81 in. Height/base values here are the fixed Type B1 "
        "base body only.",
    ),
    # ============================================================ RM-4.5
    # Type D: 42 in barrier at obstructions, founded on compacted soil (not
    # pavement) with a 20:1 permissible batter behind and a 2:1 max side
    # slope beyond. Same 5.25:1 face / 12 in top as Type B.
    RoadwayBarrier(
        scd="RM-4.5", scd_date="2026-01-16", designation="Type D",
        name="Single slope barrier, Type D (obstructions, compacted soil)",
        shape="single slope", height=42.0, top_width=12.0, base_width=28.0,
        slope_h_to_v=5.25, f_c=4.0, foundation="compacted soil",
        joint_spacing_ft=20.0,
        notes="Used at obstructions (light poles, piers, etc.) in the "
        "median/shoulder; founded on compacted soil (20 in min shoulder, "
        "20:1 permissible batter, 2:1 max embankment beyond) rather than "
        "doweled to pavement. Longitudinal steel not required when top "
        "width >= 12 in. Transitions to MGS Bridge Terminal Assembly, "
        "Type 1/2 (SCD MGS-3.1) at each end; End Sections per RM-4.6.",
    ),
    # ============================================================ RM-4.8
    # Type N: General-design 81 in barrier, cast on either new pavement (9
    # in concrete leveling pad over Item 304 aggregate base) or existing
    # pavement, with a 1 in PEJF expansion joint at pavement interfaces.
    RoadwayBarrier(
        scd="RM-4.8", scd_date="2026-01-16", designation="Type N",
        name="Single slope barrier, Type N (general design)",
        shape="single slope", height=81.0, top_width=12.0,
        base_width=42.875, slope_h_to_v=5.25, f_c=4.0,
        foundation="leveling pad", joint_spacing_ft=10.0,
        notes="Tallest of the family (81 in); cast on a 9 in concrete "
        "leveling pad (Item 451, Class QC 1P) over Item 304 aggregate base "
        "for new pavement, or doweled to a sawcut existing pavement edge. "
        "1 in PEJF (CMS 705.03) at the leveling pad / pavement interface, "
        "sealed with CMS 705.04. #8 x 12 in epoxy dowels; 4 in min raceway "
        "clearance to conduits (2 in ITS / 4 in lighting).",
    ),
    # ============================================================ RM-4.9
    # Type E: 36 in barrier on a cast-in-place moment slab foundation (MASH
    # TL-4). The drawing dimensions the rebar cage (Bar S/Bar U, #4/#5) and
    # moment slab (5 ft min width, 1 ft min thickness) in detail but does
    # NOT call out the outer concrete face envelope -- unlike B/B1/C/C1/D/N
    # its top/base width are not transcribed here (see module docstring).
    RoadwayBarrier(
        scd="RM-4.9", scd_date="2025-07-18", designation="Type E",
        name="Single slope barrier, Type E (moment slab foundation)",
        shape="single slope (moment slab)", height=36.0,
        top_width=None, base_width=None, slope_h_to_v=None, f_c=None,
        foundation="moment slab", joint_spacing_ft=100.0,
        notes="MASH TL-4. Mounted on a cast-in-place moment slab (5 ft min "
        "width, 1 ft min thickness, 6 - #5 bars @ 5 equal spaces plus Bar U "
        "#4 stirrups at 6 in) rather than doweled to pavement/leveling pad. "
        "Bar S (#4) vertical face bars at 6 in o.c.; 3/4 in PEJF at "
        "20 ft min / 100 ft max barrier-segment joints and at the moment "
        "slab / adjacent pavement interface. Concrete face envelope (top/"
        "base width) is not dimensioned on this sheet -- only the rebar "
        "cage is -- so it is not transcribed; coordinate with plans or "
        "treat RM-4.3 Type B's 42 in profile as a rough visual stand-in. "
        "Transitions from RM-4.5's 42 in Type D barrier (see sheet 3).",
    ),
]

#: Catalog keyed by ``designation`` (e.g. ``"Type B"``, ``"Type N"``).
ROADWAY_BARRIERS: dict[str, RoadwayBarrier] = {b.designation: b for b in _CATALOG}


def roadway_barrier(designation: str) -> RoadwayBarrier:
    """Look up a roadway barrier type by its ``designation`` (e.g.
    ``"Type B"``, ``"Type N"``)."""
    try:
        return ROADWAY_BARRIERS[designation]
    except KeyError:
        raise ValueError(
            f"unknown roadway barrier type {designation!r}; choose one of "
            f"{sorted(ROADWAY_BARRIERS)}"
        )


@dataclass(frozen=True)
class RoadwayBarrierInput:
    """Inputs for one straight run of a roadway single-slope barrier."""

    designation: str
    length_ft: float


@dataclass(frozen=True)
class RoadwayBarrierLayout:
    """Symmetric cross-section plus run length for a roadway barrier.

    ``profile`` is a closed list of ``(offset_in, z_in)`` vertices, ``offset``
    measured from the barrier centerline and ``z`` from its base -- the same
    convention :func:`civilpy.structural.rhino_barrier.barrier_profile` uses
    for a freestanding (``side=0``) section.
    """

    barrier: RoadwayBarrier
    length_ft: float
    profile: tuple[tuple[float, float], ...]
    notes: tuple[str, ...] = ()


def layout_roadway_barrier(inp: RoadwayBarrierInput) -> RoadwayBarrierLayout:
    """Build the symmetric single-slope cross-section for ``inp``."""
    if inp.length_ft <= 0.0:
        raise ValueError("length_ft must be > 0")
    b = roadway_barrier(inp.designation)
    if b.top_width is None or b.base_width is None or b.height is None:
        raise ValueError(
            f"{b.designation} ({b.scd}) does not have a dimensioned concrete "
            f"face on its drawing -- {b.notes}"
        )
    t, base, h = b.top_width, b.base_width, b.height
    profile = (
        (-base / 2.0, 0.0), (base / 2.0, 0.0),
        (t / 2.0, h), (-t / 2.0, h),
    )
    notes = [f"ODOT {b.scd} {b.name} (rev. {b.scd_date})"]
    if b.notes:
        notes.append(b.notes)
    return RoadwayBarrierLayout(
        barrier=b, length_ft=inp.length_ft, profile=profile, notes=tuple(notes))


# ═════════════════════════ RM-4.6 barrier end sections ════════════════════

@dataclass(frozen=True)
class BarrierEndSection:
    """One RM-4.6 cast-in-place concrete barrier end section.

    Steps the parent single-slope barrier down to a 32 in tall,
    vertical-faced end that a Bridge Terminal Assembly (SCD MGS-3.1/3.2/
    3.3, Item 606) or impact attenuator attaches to; the single-slope
    faces transition to vertical over 10 ft to prevent snagging, and the
    concrete end carries a 4:1 plan flare over the last 16 in.  Paid as
    Item 622 "Concrete Barrier End Section, Type _", Each."""

    scd: str
    scd_date: str
    designation: str
    parent: str                  #: RM-4.3 / RM-4.5 barrier designation
    total_length_ft: float
    #: Full parent-profile run before the face transition, ft (the
    #: Type B1 body also tapers 57 -> 42 in tall across it).
    body_length_ft: float
    face_transition_ft: float    #: vertical-face transition length
    vertical_run_in: float       #: full-height vertical-face run
    end_taper_in: float          #: 4:1 concrete end flare
    end_height_in: float
    end_width_in: float          #: overall width across the curbs
    end_core_width_in: float     #: vertical-faced core between curbs
    median: bool = True          #: median (two-sided) vs roadside
    notes: str = ""


_END_SECTIONS: list[BarrierEndSection] = [
    # Sheet 1: Type B (median, two-sided): 30 ft = 16 ft body + 10 ft
    # barrier-face transition + 32 in vertical + 16 in end taper. End is
    # 32 in tall over a 32 in overall / 24 in core width (4 in curbs).
    BarrierEndSection(
        scd="RM-4.6", scd_date="2025-07-18", designation="Type B",
        parent="Type B", total_length_ft=30.0, body_length_ft=16.0,
        face_transition_ft=10.0, vertical_run_in=32.0, end_taper_in=16.0,
        end_height_in=32.0, end_width_in=32.0, end_core_width_in=24.0,
        median=True,
        notes="Median end section for the 42 in Type B; X501-X505 #5 / "
        "Y601-Y603 #6 cage per the sheet 1 steel list."),
    # Sheet 2: Type B1 (median): same 30 ft stationing; the 57 in body
    # tapers to 42 in across the 16 ft, then matches Type B's sections.
    BarrierEndSection(
        scd="RM-4.6", scd_date="2025-07-18", designation="Type B1",
        parent="Type B1", total_length_ft=30.0, body_length_ft=16.0,
        face_transition_ft=10.0, vertical_run_in=32.0, end_taper_in=16.0,
        end_height_in=32.0, end_width_in=32.0, end_core_width_in=24.0,
        median=True,
        notes="Median end section for the 57 in Type B1; the top tapers "
        "57 -> 42 in over the 16 ft body, then follows the Type B "
        "transition. X511-X515 / Y611-Y613 cage per the sheet 2 list."),
    # Sheet 3: Type D (roadside, traffic one side only): 14 ft = 10 ft
    # face transition + 32 in vertical + 16 in end taper; 20 in wide end
    # (16 in core + 4 in curb on the traffic side).
    BarrierEndSection(
        scd="RM-4.6", scd_date="2025-07-18", designation="Type D",
        parent="Type D", total_length_ft=14.0, body_length_ft=0.0,
        face_transition_ft=10.0, vertical_run_in=32.0, end_taper_in=16.0,
        end_height_in=32.0, end_width_in=20.0, end_core_width_in=16.0,
        median=False,
        notes="Roadside end section for the 42 in Type D (traffic on one "
        "side); single-slope traffic face only. X521-X524 / Y621-Y623 "
        "cage per the sheet 3 list."),
]

#: RM-4.6 end sections keyed by designation.
BARRIER_END_SECTIONS: dict[str, BarrierEndSection] = {
    e.designation: e for e in _END_SECTIONS}


def barrier_end_section(designation: str) -> BarrierEndSection:
    """Look up an RM-4.6 end section by designation (``"Type B"``,
    ``"Type B1"``, ``"Type D"``)."""
    try:
        return BARRIER_END_SECTIONS[designation]
    except KeyError:
        raise ValueError(
            f"unknown barrier end section {designation!r}; choose one of "
            f"{sorted(BARRIER_END_SECTIONS)}")


def _end_profile(e: BarrierEndSection) -> tuple[tuple[float, float], ...]:
    """The 32 in vertical-faced end cross-section: core between 4 in
    curb ledges (7 in tall on the sheet's sections), symmetric for a
    median section, curb on the traffic side only for Type D."""
    hc = e.end_core_width_in / 2.0
    hw = e.end_width_in / 2.0
    h = e.end_height_in
    curb_h = 7.0
    if e.median:
        return ((-hw, 0.0), (hw, 0.0), (hw, curb_h), (hc, curb_h),
                (hc, h), (-hc, h), (-hc, curb_h), (-hw, curb_h))
    # roadside (Type D): vertical back face, curb ledge on the traffic
    # side only — the core's back face runs flush with the base's
    curb_w = e.end_width_in - e.end_core_width_in
    return ((-hw, 0.0), (hw, 0.0), (hw, curb_h), (hw - curb_w, curb_h),
            (hw - curb_w, h), (-hw, h))


@dataclass(frozen=True)
class BarrierEndSectionLayout:
    """Stationed cross-sections of an RM-4.6 end section, ready to loft.

    ``stations`` is a tuple of ``(station_ft, profile)`` pairs from the
    parent-barrier joint (station 0) to the end; each profile is a
    closed ``(offset_in, z_in)`` loop in the roadway-barrier convention.
    The 4:1 plan end flare inside the last 16 in is described in
    ``notes`` rather than drawn (it rounds the very end plan corners)."""

    end_section: BarrierEndSection
    stations: tuple[tuple[float, tuple[tuple[float, float], ...]], ...]
    notes: tuple[str, ...] = ()


def layout_barrier_end_section(designation: str) -> BarrierEndSectionLayout:
    """Build the lofting stations for an RM-4.6 end section."""
    e = barrier_end_section(designation)
    parent = roadway_barrier(e.parent)
    body = layout_roadway_barrier(
        RoadwayBarrierInput(e.parent, max(e.body_length_ft, 0.1))).profile
    end_prof = _end_profile(e)

    stations: list[tuple[float, tuple]] = [(0.0, body)]
    x = e.body_length_ft
    if e.body_length_ft > 0.0 and e.parent == "Type B1":
        # the B1 body tapers 57 -> 42 in tall across the 16 ft run
        b = roadway_barrier("Type B")
        body_42 = ((-b.base_width / 2.0, 0.0), (b.base_width / 2.0, 0.0),
                   (b.top_width / 2.0, 42.0), (-b.top_width / 2.0, 42.0))
        stations.append((x, body_42))
    elif e.body_length_ft > 0.0:
        stations.append((x, body))
    x += e.face_transition_ft
    stations.append((x, end_prof))          # faces now vertical, 32 in tall
    x += e.vertical_run_in / 12.0
    stations.append((x, end_prof))
    x += e.end_taper_in / 12.0
    stations.append((x, end_prof))          # flared plan end (see notes)

    notes = (
        f"ODOT {e.scd} concrete barrier end section, {e.designation} "
        f"(rev. {e.scd_date}); parent barrier {parent.scd} {e.parent}",
        "Faces transition from single-slope to vertical over the 10 ft "
        "barrier face transition (anti-snagging note on the sheet); the "
        "last 16 in carries a 4:1 concrete end flare (not modeled as "
        "geometry here).",
        "Connect to a Bridge Terminal Assembly per SCD MGS-3.1/3.2/3.3 "
        "(Item 606) or an impact attenuator; paid as Item 622 - Concrete "
        f"Barrier End Section, {e.designation}, Each.",
    )
    return BarrierEndSectionLayout(end_section=e, stations=tuple(stations),
                                   notes=notes)


# ═════════════════════════ RM-4.4 barrier transitions ═════════════════════

#: RM-4.4 plan-taper length each side of the obstruction, ft.
TRANSITION_TAPER_FT = 40.0
#: Flat run at a sign support / light tower foundation, ft.
SIGN_SUPPORT_RUN_FT = 10.0
#: Flat run beyond each pier column face, ft.
PIER_RUN_EACH_SIDE_FT = 5.0
#: Foundation-width band the sheet allows at a sign support, inches.
SIGN_SUPPORT_WIDTH_RANGE_IN = (36.0, 48.0)
#: Barrier width at a protected pier column, inches.
PIER_PROTECTION_WIDTH_IN = 48.0
#: Raceways cast into the widened barrier (RACEWAY PLACEMENT detail).
TRANSITION_RACEWAYS = ("2 in ITS raceway (HDPE per SS809)",
                       "4 in lighting raceway (CMS 625.12)")


@dataclass(frozen=True)
class BarrierTransitionLayout:
    """Plan-view widening of an RM-4.4 single-slope barrier transition.

    ``stations`` is a tuple of ``(station_ft, width_in)`` pairs of the
    barrier's overall plan width from the start of the first taper; the
    cross-section at any station keeps the parent barrier's height and
    5.25:1 faces with the extra width filled solid between them."""

    barrier: RoadwayBarrier
    kind: str                    # "sign support" | "pier"
    obstruction_width_in: float
    stations: tuple[tuple[float, float], ...]
    total_length_ft: float
    notes: tuple[str, ...] = ()


def layout_barrier_transition(designation: str, kind: str, *,
                              obstruction_width_in: float | None = None,
                              obstruction_length_ft: float = 0.0
                              ) -> BarrierTransitionLayout:
    """Build the RM-4.4 plan-width stations for a barrier transition.

    ``designation`` is an RM-4.3 type (B/B1/C/C1); ``kind`` is
    ``"sign support"`` (light tower / sign foundation, 36-48 in wide,
    10 ft run) or ``"pier"`` (48 in wide pier column protection;
    ``obstruction_length_ft`` is the variable column run between the
    two 5 ft shoulders).  Raises ``ValueError`` for other barrier types
    or a sign-support width outside the sheet's 36-48 in band."""
    b = roadway_barrier(designation)
    if designation not in ("Type B", "Type B1", "Type C", "Type C1"):
        raise ValueError(
            "RM-4.4 transitions apply to RM-4.3 Types B/B1/C/C1, not "
            f"{designation!r}")
    if kind == "sign support":
        w = obstruction_width_in if obstruction_width_in is not None else 48.0
        lo, hi = SIGN_SUPPORT_WIDTH_RANGE_IN
        if not lo <= w <= hi:
            raise ValueError(
                f"sign support width must match the foundation diameter, "
                f"{lo:g}-{hi:g} in, not {w:g}")
        run = SIGN_SUPPORT_RUN_FT
    elif kind == "pier":
        w = PIER_PROTECTION_WIDTH_IN
        run = 2.0 * PIER_RUN_EACH_SIDE_FT + max(obstruction_length_ft, 0.0)
    else:
        raise ValueError(f"kind must be 'sign support' or 'pier', not {kind!r}")

    w0 = b.top_width or 12.0
    stations = (
        (0.0, w0),
        (TRANSITION_TAPER_FT, w),
        (TRANSITION_TAPER_FT + run, w),
        (2.0 * TRANSITION_TAPER_FT + run, w0),
    )
    notes = (
        f"ODOT RM-4.4 single slope barrier transition (rev. 2025-01-17), "
        f"{b.scd} {designation} at a {kind}",
        "Widths are the barrier's overall plan width; faces keep the "
        "5.25:1 single slope and full barrier height, solid concrete "
        "between faces (4000 psi, CMS 499).",
        "20 ft max contraction-joint spacing; 3/4 in expansion joints "
        "(CMS 705.03) at the indicated positions; reinforced end "
        "anchorage (RM-4.3) only at the expansion joint entering the "
        "pier protection.",
        "Raceways: " + "; ".join(TRANSITION_RACEWAYS) + "; spacers every "
        "10 ft, incidental to the barrier.",
        "Paid per foot as Item 622 - Concrete Barrier, Single Slope, "
        "Type __; reinforced end anchors Each as Item 622 - Concrete "
        "Barrier, End Anchorage, Reinforced.",
    )
    return BarrierTransitionLayout(
        barrier=b, kind=kind, obstruction_width_in=w,
        stations=stations, total_length_ft=stations[-1][0], notes=notes)
