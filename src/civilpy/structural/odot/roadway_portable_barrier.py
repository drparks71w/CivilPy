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
