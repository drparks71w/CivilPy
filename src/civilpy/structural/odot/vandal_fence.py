#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT vandal protection fence (VPF-1-24).

Transcribed from Ohio DOT Standard Bridge Drawing VPF-1-24, "Vandal
Protection Fence" (rev. 01-17-2025, 6 sheets). The drawing remains the
controlling document.

Mostly a materials/hardware specification (posts, rails, fabric, tension
wire, fittings, base plates, anchors -- General Notes 1-25) rather than a
dimensioned standard; the one genuine geometric table is the three post
sections (sheet 2), each pairing a post type with its base plate and
maximum spacing. The designer specifies which post type/base plate to
use and the actual post spacing on a project's own schematic deck plan
(sheet 1, note 25).

Conventions match the rest of this package: X along the fence run, Y
transverse (fixed at the railing face), Z up; feet in plan. The origin
sits at the first post, z = 0 at the base plate.
"""

from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "VPF-1-24"
REVISION = "01-17-2025"

# ── materials (General Notes 1-16) ────────────────────────────────────────

LINE_POST_OD_IN = 2.880          # Grade 2 pipe, 710.03 Type I, Fy=50 ksi
LINE_POST_WEIGHT_PLF = 4.64
RAIL_OD_IN = 1.660               # top/bottom/line rails, same grade pipe
RAIL_WEIGHT_PLF = 1.84
POST_SLEEVE_OD_IN = 3.500         # ASTM A53, Fy=25 ksi min
FABRIC_MESH_IN = 1.0              # 1x1 in diamond mesh
FABRIC_WIRE_DIA_IN = 0.120         # 11 gage, ASTM F668
TENSION_WIRE_DIA_IN = 0.177        # aluminized steel coil spring wire
TENSION_WIRE_MAX_SAG_IN = 0.25    # after tensioning
FASTENER_SPEC = "5/8 in dia ASTM A325 high strength bolts, galvanized"
FILLET_WELD_SPEC = "C&MS 513"

PAY_ITEM = ("607", "FOOT", "VANDAL PROTECTION FENCE")


@dataclass(frozen=True)
class PostSection:
    """One VPF-1-24 post section (sheet 2)."""

    name: str                 # "PS-1", "PS-2/BP-1", "PS-2/BP-2"
    base_plate: str            # "BP-1", "BP-2", "BP-3"
    height_ft: float
    max_spacing_ft: float
    curved: bool = False
    curve_radius_ft: float | None = None   # PS-1 only
    note: str = ""


#: VPF-1-24 post sections, keyed by name.
POST_SECTIONS: dict[str, PostSection] = {
    "PS-1": PostSection(
        "PS-1", "BP-3", 9.0 + 11.875 / 12.0, 7.0, curved=True,
        curve_radius_ft=2.0 + 8.0 / 12.0,
        note="12 ft curved fence; extends over a steel railing on a "
             "concrete barrier"),
    "PS-2/BP-1": PostSection(
        "PS-2", "BP-1", 6.0, 10.0,
        note="6 ft straight fence on single slope railing"),
    "PS-2/BP-2": PostSection(
        "PS-2", "BP-2", 6.0, 5.0,
        note="6 ft straight fence on deflector railing (closer spacing)"),
}


def post_section(name: str) -> PostSection:
    """Look up a VPF-1-24 post section ("PS-1", "PS-2/BP-1", "PS-2/BP-2").

    Raises ``ValueError`` naming the valid names otherwise."""
    try:
        return POST_SECTIONS[name]
    except KeyError:
        raise ValueError(
            f"VPF-1-24 post sections are {list(POST_SECTIONS)}, "
            f"not {name!r}") from None


# ── layout ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FenceRunInput:
    length_ft: float
    post_name: str = "PS-2/BP-1"
    spacing_ft: float | None = None   # defaults to the section's max


@dataclass(frozen=True)
class FenceRunLayout:
    """The generated fence run: ``post_stations_ft`` are evenly-spaced post
    positions along the run (never exceeding the section's max spacing);
    ``top_rail``/``bottom_rail`` are the rail lines at post height / base."""

    inputs: FenceRunInput
    section: PostSection
    post_stations_ft: tuple[float, ...]
    top_rail: tuple[Point, Point]
    bottom_rail: tuple[Point, Point]
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_fence_run(inp: FenceRunInput) -> FenceRunLayout:
    """Generate a fence run: evenly-spaced posts (spacing never exceeding
    the section's tabulated maximum) plus top/bottom rail lines.

    Raises ``ValueError`` for a non-positive length or an unknown post
    section name."""
    if inp.length_ft <= 0.0:
        raise ValueError("FenceRunInput.length_ft must be positive")
    section = post_section(inp.post_name)
    spacing = inp.spacing_ft or section.max_spacing_ft
    if spacing > section.max_spacing_ft + 1e-9:
        raise ValueError(
            f"{inp.post_name} spacing is {section.max_spacing_ft:g} ft "
            f"max; {spacing:g} ft exceeds it")

    import math
    n_spaces = max(1, math.ceil(inp.length_ft / spacing - 1e-9))
    actual_spacing = inp.length_ft / n_spaces
    post_stations = tuple(i * actual_spacing for i in range(n_spaces + 1))

    top_rail = ((0.0, 0.0, section.height_ft), (inp.length_ft, 0.0, section.height_ft))
    bottom_rail = ((0.0, 0.0, 0.0), (inp.length_ft, 0.0, 0.0))

    notes = (
        f"VPF-1-24 fence run: {inp.post_name} ({section.base_plate}), "
        f"{len(post_stations)} posts @ {actual_spacing:.2f} ft "
        f"(max {section.max_spacing_ft:g} ft), height {section.height_ft:.2f} ft",
        "Not modeled: fabric mesh, tension wire/bars, base plate/anchor "
        "detail, post caps/fittings, deflection joints, curved top radius "
        "geometry (PS-1's curve is noted, not swept).",
    )

    return FenceRunLayout(
        inputs=inp, section=section, post_stations_ft=post_stations,
        top_rail=top_rail, bottom_rail=bottom_rail, notes=notes,
    )
