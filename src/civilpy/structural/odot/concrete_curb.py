#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ODOT BP-5.1 Standard Concrete Curbs and Combined Curb & Gutter.

Transcribed from Ohio DOT Standard Roadway Construction Drawing
**BP-5.1** (rev. 01-16-2026, 2 sheets), which catalogs 13 named curb/
combined-curb-and-gutter face profiles (Types 1 through 11, several
with lettered substrate variants). Each is a small, fixed cross
section -- no span table or design formula -- so, consistent with how
:mod:`civilpy.structural.odot.bridge_railing` catalogs a parapet's
``height``/``top_width``/``base_width`` without modeling its exact toe
kick, each entry here is a schematic ``(height, top_width, base_width)``
trapezoid of the curb's OWN concrete (not the paved gutter pad it may
tie into, and not the exact fillet/rolled-curb arc -- those are
approximated as straight chamfers/ramps). The drawing remains the
controlling document for the true face geometry.

Several sheet labels differ only by the pavement/base course the same
curb face sits on (Types 2/2-A/2-B, 3/3-A/3-B, 4/4-A/4-B all share one
profile); those are consolidated into one catalog entry whose
``sheet_labels`` records every name the profile answers to.

``height`` is ``None`` for the three types (9, 10, 11) whose height is
the project-specified gutter-plate thickness ``T`` (general note:
"Thickness of gutter plate T shall be 9 in unless otherwise shown on
the plans") -- ``DEFAULT_GUTTER_PLATE_T_IN`` gives that 9 in default.

Lengths are in inches.

Source: BP-5.1 (rev. 01-16-2026).
"""

from __future__ import annotations

from dataclasses import dataclass

SCD = "BP-5.1"
REVISION = "01-16-2026"

#: General note: gutter plate thickness T defaults to 9 in unless the
#: plans show otherwise (governs Types 9, 10, 11's variable height).
DEFAULT_GUTTER_PLATE_T_IN = 9.0
#: General note: 1 in transverse expansion joints, Item 705.03 filler /
#: 705.04 sealer, at curb-and-gutter expansion joints and approach slabs.
EXPANSION_JOINT_WIDTH_IN = 1.0
#: Dimensional tolerances (general note): curb -3/32 to +1/4 in, gutter 0
#: to +1/8 in.
CURB_TOLERANCE_IN = (-3.0 / 32.0, 0.25)
GUTTER_TOLERANCE_IN = (0.0, 1.0 / 8.0)


@dataclass(frozen=True)
class CurbType:
    """One BP-5.1 curb / combined curb-and-gutter cross section.

    ``height`` is the curb's own face height (in), ``None`` when it is
    the project-variable gutter-plate thickness ``T``. ``top_width`` /
    ``base_width`` describe a schematic trapezoid of the curb's concrete
    only (see module docstring for what is and isn't modeled).
    """

    sheet_labels: tuple[str, ...]
    name: str
    height: float | None
    top_width: float
    base_width: float
    toe_radius: float | None = None
    notes: str = ""


_CATALOG: list[CurbType] = [
    CurbType(
        sheet_labels=("Type 1",), name="Asphalt curb (wedge)",
        height=6.0, top_width=4.0, base_width=9.0,
        notes="Sits on the asphalt concrete surface course over base; "
        "42 deg battered face, 2 in top radius (approximated here as a "
        "straight-line wedge).",
    ),
    CurbType(
        sheet_labels=("Type 2", "Type 2-A", "Type 2-B"),
        name="Vertical curb, integral gutter pad",
        height=6.0, top_width=5.0, base_width=6.0, toe_radius=3.0,
        notes="Monolithic with new concrete pavement (Type 2), an asphalt "
        "wearing course over concrete base (Type 2-A), or a concrete base "
        "course under a wearing course (Type 2-B) -- same curb face on all "
        "three. Integral gutter pad extends 2'-6\" (30 in) beyond the toe "
        "unless the plans show otherwise, sloped 12:1 down to the pavement.",
    ),
    CurbType(
        sheet_labels=("Type 3", "Type 3-A", "Type 3-B"),
        name="Mountable (rolled) curb",
        height=4.0, top_width=0.0, base_width=10.0,
        notes="Rounds flush with the pavement over a 10 in radius arc "
        "(Type 3 on concrete pavement, 3-A on asphalt, 3-B on a wearing "
        "course over concrete base) -- approximated here as a straight "
        "ramp from pavement to the 4 in curb top, not the true arc.",
    ),
    CurbType(
        sheet_labels=("Type 4", "Type 4-A", "Type 4-B"),
        name="Vertical curb, no integral gutter",
        height=6.0, top_width=5.0, base_width=6.0, toe_radius=3.0,
        notes="Same face as Type 2 (concrete pavement / wearing course "
        "over concrete base / wearing course over base course "
        "respectively) but without an integral gutter pad; back width is "
        "project-specified ('as shown on Typical Sections in Plans').",
    ),
    CurbType(
        sheet_labels=("Type 4-C",), name="Tall curb at approach slab joint",
        height=16.0, top_width=5.0, base_width=6.0,
        notes="Used where the curb meets a pavement/approach-slab "
        "expansion joint; 1 in preformed joint filler (Item 705.03) + "
        "joint sealer (Item 705.04), full curb height per the general "
        "JOINTS note.",
    ),
    CurbType(
        sheet_labels=("Type 6",), name="Tall curb at joint (18 in)",
        height=18.0, top_width=6.0, base_width=8.0,
        notes="Taller sibling of Type 4-C (18 in vs 16 in); same "
        "preformed-joint-filler / sealer detail at pavement joints.",
    ),
    CurbType(
        sheet_labels=("Type 7",), name="Median curb against earth",
        height=10.0, top_width=6.5, base_width=8.0,
        notes="Backed by earth (not pavement/base); 1 in preformed joint "
        "filler at the pavement side.",
    ),
    CurbType(
        sheet_labels=("Type 8",), name="Median curb, shoulder/pavement joint",
        height=9.0, top_width=9.0, base_width=12.0,
        notes="Asphalt pavement or shoulder on one face, pavement on the "
        "other, with a joint-sealed interface between them.",
    ),
    CurbType(
        sheet_labels=("Type 9",), name="Variable-height curb, gutter pad",
        height=None, top_width=9.0, base_width=21.0,
        notes="Height is the project gutter-plate thickness T (default "
        f"{DEFAULT_GUTTER_PLATE_T_IN:g} in). Top cross slope matches the "
        "roadway cross slope; 9 in nose + 12 in gutter pad.",
    ),
    CurbType(
        sheet_labels=("Type 10",), name="Variable-height curb, no gutter pad",
        height=None, top_width=9.0, base_width=9.0,
        notes=f"Height is T (default {DEFAULT_GUTTER_PLATE_T_IN:g} in); "
        "no integral gutter pad, back width per the Typical Sections.",
    ),
    CurbType(
        sheet_labels=("Type 10-A",), name="Tall curb, 45 deg chamfer",
        height=18.0, top_width=17.0, base_width=18.0,
        notes="6 in nose + 12 in pavement-contact width; 45 deg chamfer at "
        "the top corner (1 in / 2 in radii), approximated here as a 1 in "
        "top setback.",
    ),
    CurbType(
        sheet_labels=("Type 10-B",), name="Curb at joint (14 in)",
        height=14.0, top_width=6.0, base_width=6.0,
        notes="Preformed-joint-filler detail like Type 10-A but shorter "
        "(14 in) and without the 45 deg chamfer.",
    ),
    CurbType(
        sheet_labels=("Type 11",), name="Wide curb, compound curve face",
        height=None, top_width=6.0, base_width=24.0,
        notes="Height is T (default the "
        f"{DEFAULT_GUTTER_PLATE_T_IN:g} in gutter-plate thickness, per "
        "Typical Sections). Face is a compound curve (18 in toe radius, "
        "X=4-3/4 in / Y=4-5/8 in offsets) approximated here as a "
        "9+9+6 in straight-segment trapezoid.",
    ),
]

#: Catalog keyed by every sheet label it answers to (so ``"Type 2-A"``
#: and ``"Type 2-B"`` both resolve to the Type 2 entry).
CURB_TYPES: dict[str, CurbType] = {
    label: c for c in _CATALOG for label in c.sheet_labels
}


def curb_type(label: str) -> CurbType:
    """Look up a curb cross section by any of its sheet labels (e.g.
    ``"Type 2"``, ``"Type 2-A"``, ``"Type 10-B"``)."""
    try:
        return CURB_TYPES[label]
    except KeyError:
        raise ValueError(
            f"unknown BP-5.1 curb type {label!r}; choose one of "
            f"{sorted(CURB_TYPES)}"
        )


def curb_height_in(label: str, *, gutter_plate_t_in: float | None = None) -> float:
    """Resolved curb height (in): the catalog ``height`` if fixed, else the
    project ``gutter_plate_t_in`` (defaulting to
    :data:`DEFAULT_GUTTER_PLATE_T_IN`) for the variable-height types."""
    c = curb_type(label)
    if c.height is not None:
        return c.height
    return gutter_plate_t_in if gutter_plate_t_in is not None else DEFAULT_GUTTER_PLATE_T_IN


def curb_profile_in(label: str, *, gutter_plate_t_in: float | None = None
                    ) -> tuple[tuple[float, float], ...]:
    """Schematic closed trapezoid profile (in) for ``label``, ``(offset,
    z)`` counterclockwise from the back-bottom corner, ``offset`` measured
    from the curb's back face and ``z`` up from the pavement surface."""
    c = curb_type(label)
    h = curb_height_in(label, gutter_plate_t_in=gutter_plate_t_in)
    return ((0.0, 0.0), (c.base_width, 0.0), (c.top_width, h), (0.0, h))
