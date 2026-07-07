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

Lengths are in inches unless noted. Concrete strength ``f_c`` in ksi.

Sources (SCD number — drawing date / latest cited revision):
    RM-4.3  Single slope barrier, Types B, B1, C, C1  (rev. 2025-07-18)
    RM-4.5  Single slope barrier, Type D              (rev. 2026-01-16)
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
