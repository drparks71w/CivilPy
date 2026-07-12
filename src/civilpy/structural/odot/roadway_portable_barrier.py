#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT standard roadway (at-grade) portable concrete barriers.

Office of Roadway Engineering successors to Structural Engineering's
PCB-91 (:mod:`civilpy.structural.odot.portable_barrier`): the same New
Jersey shape family, reused here via :class:`~civilpy.structural.odot
.bridge_railing.BridgeRailing` so ``name`` containing ``"portable"``
routes through :func:`civilpy.structural.rhino_barrier.shape_family`'s
freestanding symmetric F-shape profile exactly as PCB-91 does.

Both are pin-and-loop / hinge-bar connected precast segments, NOT
suitable at bridge deck edges or similar dropoffs (a fixed anchored
barrier or bridge-mounted PCB is required there instead).

Sources (SCD number — drawing date / latest cited revision):
    RM-4.2  32 in Portable Concrete Barrier, New Jersey shape, pin & loop
            connection                                    (rev. 2026-01-16)
    RM-4.1  50 in Portable Concrete Barrier + 50->32 in transition section
            (hinge bar connection)                        (rev. 2020-01-17)
"""

from dataclasses import dataclass

from civilpy.structural.odot.bridge_railing import BridgeRailing


@dataclass(frozen=True)
class TransitionSection:
    """A tapered end section joining two different barrier heights."""

    scd: str
    name: str
    height_from_in: float
    height_to_in: float
    length_ft: float
    notes: str = ""


_CATALOG: list[BridgeRailing] = [
    # ============================================================ RM-4.2
    # 32 in portable concrete barrier, New Jersey shape, pin & loop
    # connection. Segments 10'-0" min to 20'-0" max (hinge-bar loop
    # spacing varies with length: 4 spaces @ 19" for 10', 6 @ 16.7" for
    # 12', 11 @ 17.8" for 20'). May be cast with rebar (Y301/X501) or
    # welded wire fabric (6x6 W2.9/W2.9 WWF + 2 longitudinal #4 bars).
    # f'c >= 4000 psi (CMS 499); connecting hardware galvanized per
    # CMS 711.02/711.09. Not for use at bridge deck edges/dropoffs (use
    # the Structural Engineering PCB-91 bridge-mounted barrier there).
    BridgeRailing(
        scd="RM-4.2", scd_date="2026-01-16",
        designation="RM Portable (32 in, pin & loop)",
        name="Portable concrete barrier, 32 in, New Jersey shape, pin & loop",
        shape="New Jersey", material="precast concrete", test_level="",
        height=32.0, base_width=24.0, top_width=6.0, f_c=4.0,
        segment_length_ft=(10.0, 12.0, 20.0),
        notes="Office of Roadway Engineering successor to PCB-91: pin & "
        "loop connection (vs. PCB-91's hinge bar + through-bolt), segments "
        "10-20 ft (vs. PCB-91's fixed 10/12 ft). Not for bridge deck edges "
        "or similar dropoffs. Drawing states no numeric NCHRP/MASH test "
        "level.",
    ),
    # ============================================================ RM-4.1
    # 50 in portable concrete barrier. Segments 12'-0" to 14'-0", hinge
    # bar Type A/B loops + vertical pin connection (3/4 in dia., ASTM
    # A36). Only the 50" Transition Section's 32 in end may attach to an
    # Impact Attenuator or to RM-4.2's 32 in barrier -- never connect an
    # Impact Attenuator directly to the 50 in end. Marked
    # "PCB-RXX-350-TL3" (XX = year cast).
    BridgeRailing(
        scd="RM-4.1", scd_date="2020-01-17",
        designation="RM Portable (50 in, hinge bar)",
        name="Portable concrete barrier, 50 in, New Jersey shape, hinge bar",
        shape="New Jersey", material="precast concrete", test_level="TL-3",
        height=50.0, base_width=24.0, top_width=12.0, f_c=4.0,
        segment_length_ft=(12.0, 14.0),
        notes="Marked PCB-RXX-350-TL3. Not to be used on bridge deck edges "
        "or similar dropoffs -- the only suitable barrier there is the 32 "
        "in PCB per Structural Engineering's PCB-91 (or an approved "
        "alternative). Mates to a 32 in barrier (RM-4.2 or PCB-91) only "
        "through the 50 in Transition Section; Impact Attenuators may only "
        "attach to that transition's 32 in end.",
    ),
]

#: Catalog keyed by ``designation``.
ROADWAY_PORTABLE_BARRIERS: dict[str, BridgeRailing] = {
    b.designation: b for b in _CATALOG
}

#: The RM-4.1 50 in -> 32 in taper joining the two roadway PCB families.
TRANSITION_50_TO_32 = TransitionSection(
    scd="RM-4.1", name="50 in to 32 in portable barrier transition section",
    height_from_in=50.0, height_to_in=32.0, length_ft=6.0,
    notes="Tapers RM-4.1's 50 in barrier down to a 32 in end compatible "
    "with RM-4.2 or PCB-91; only this 32 in end may attach to an Impact "
    "Attenuator or to Guardrail per RM-4.2 notes/MT-101.80.",
)


def roadway_portable_barrier(designation: str) -> BridgeRailing:
    """Look up a roadway portable barrier by its ``designation`` (e.g.
    ``"RM Portable (32 in, pin & loop)"``)."""
    try:
        return ROADWAY_PORTABLE_BARRIERS[designation]
    except KeyError:
        raise ValueError(
            f"unknown roadway portable barrier {designation!r}; choose one "
            f"of {sorted(ROADWAY_PORTABLE_BARRIERS)}"
        )


# ═══════════════ RM-4.7 thrie-beam transition between PCB types ═══════════
#
# Transcribed from SCD RM-4.7, "Thrie-Beam Transition for Portable
# Concrete Barrier" (rev. 2025-01-17, 3 sheets, one connection pair per
# sheet).  A 6 ft-3 in nested 12-gauge thrie-beam bridges the <= 1 ft
# gap between two 32 in PCB runs of different shape families, with a
# thrie-beam terminal connector (SCD MGS-1.1) bolted to each barrier
# end and a common galvanized toe plate along the base.

RM47_SCD = "RM-4.7"
RM47_REVISION = "2025-01-17"

#: Nested thrie-beam element bridging the joint.
THRIE_BEAM_ELEMENT = "6 ft-3 in nested 12-gauge thrie-beam"
#: Maximum plan gap between the two PCB ends.
PCB_GAP_MAX_IN = 12.0
#: Minimum distance from the PCB end to the terminal connector.
CONNECTOR_END_DISTANCE_MIN_IN = 6.0
#: Terminal-connector through bolts: 7/8 in dia ASTM A325 or A449; at
#: least 5 installed, 3 in the outer vertical row, >= 6 in from the
#: segment end and >= 3 in from lifting holes/voids.
CONNECTOR_BOLT_SPEC = '7/8" dia through bolts, ASTM A325 or A449'
CONNECTOR_BOLTS_MIN = 5
#: Terminal-connector steel spacer (CMS 711.01, galvanized 711.02):
#: 6 x 10 x 1/4 in plate with 1 in dia holes; add spacers to fit field
#: conditions.
SPACER_PLATE_IN = (6.0, 10.0, 0.25)
#: Toe plate along the base (CMS 711.01, galvanized 711.02): 9 ft-0 in
#: x 5-1/2 in x 5/8 in with 24 holes (1 in dia) at 4-3/4 in; anchors
#: 7/8 x 6 in (CMS 712.01 or FF-S325 Grp VIII Type 1), >= 4 per end.
TOE_PLATE_IN = (108.0, 5.5, 0.625)
TOE_PLATE_ANCHOR_SPEC = '7/8" x 6" anchors, CMS 712.01'
TOE_PLATE_ANCHORS_MIN_PER_END = 4
#: Deployment limits (general notes, all sheets).
USE_LIMIT = "once per mile with project engineer approval"
UNANCHORED_PCB_MIN_FT = 100.0


@dataclass(frozen=True)
class ThrieBeamPCBTransition:
    """One RM-4.7 connection pair (one sheet each).  ``barrier_a`` /
    ``barrier_b`` name the generic/proprietary 32 in PCB shapes joined;
    the hardware set is common to all three pairs."""

    sheet: int
    barrier_a: str
    barrier_b: str
    notes: str = ""


#: RM-4.7 connection pairs keyed by ``(a, b)`` shape names.
THRIE_BEAM_PCB_TRANSITIONS: dict[tuple[str, str], ThrieBeamPCBTransition] = {
    (t.barrier_a, t.barrier_b): t
    for t in (
        ThrieBeamPCBTransition(
            1, 'Generic 32" New Jersey shape PCB', 'Generic 32" F-shape PCB',
            notes="May also connect barriers of the same shape. Not "
            "approved for the J-J Hook 32 in New Jersey shape PCB."),
        ThrieBeamPCBTransition(
            2, 'Generic 32" New Jersey shape PCB', 'J-J Hook 32" F-shape PCB'),
        ThrieBeamPCBTransition(
            3, 'Generic 32" F-shape PCB', 'J-J Hook 32" F-shape PCB'),
    )
}


def thrie_beam_pcb_transition(barrier_a: str,
                              barrier_b: str) -> ThrieBeamPCBTransition:
    """Look up the RM-4.7 pair joining two PCB shapes (order-free).
    Raises ``ValueError`` naming the cataloged pairs otherwise — in
    particular there is **no** approved pair involving the J-J Hook
    32 in New Jersey shape PCB."""
    for (a, b), t in THRIE_BEAM_PCB_TRANSITIONS.items():
        if {a, b} == {barrier_a, barrier_b}:
            return t
    raise ValueError(
        f"RM-4.7 has no transition joining {barrier_a!r} to {barrier_b!r}; "
        f"cataloged pairs are {sorted(THRIE_BEAM_PCB_TRANSITIONS)}")


def thrie_beam_transition_notes() -> tuple[str, ...]:
    """The deployment / payment rules common to every RM-4.7 pair."""
    return (
        f"ODOT {RM47_SCD} thrie-beam transition for portable concrete "
        f"barrier (rev. {RM47_REVISION})",
        f"{THRIE_BEAM_ELEMENT} across a {PCB_GAP_MAX_IN:g} in max gap; "
        "thrie-beam terminal connector (SCD MGS-1.1) each end, "
        f"{CONNECTOR_BOLT_SPEC} ({CONNECTOR_BOLTS_MIN} min, outer "
        "vertical row filled first, 6 in min from the segment end).",
        "Galvanized terminal-connector spacer plate(s) "
        f"{SPACER_PLATE_IN[0]:g} x {SPACER_PLATE_IN[1]:g} x "
        f"{SPACER_PLATE_IN[2]:g} in and toe plate "
        f"{TOE_PLATE_IN[0] / 12.0:g} ft x {TOE_PLATE_IN[1]:g} x "
        f"{TOE_PLATE_IN[2]:g} in ({TOE_PLATE_ANCHOR_SPEC}, "
        f"{TOE_PLATE_ANCHORS_MIN_PER_END} min per end).",
        f"Use {USE_LIMIT}; {UNANCHORED_PCB_MIN_FT:g} ft of unanchored "
        "PCB required each side; traffic on either or both sides.",
        "Incidental to pay Item 622 - Portable Barrier, Unanchored "
        "(all hardware, material, labor, installation, and removal).",
    )
