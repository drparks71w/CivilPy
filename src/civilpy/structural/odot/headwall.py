#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT cast-in-place half-height headwalls (HW-2.1, HW-2.2).

Cast-in-place headwall dimension tables transcribed from two Ohio DOT
Standard Bridge Drawings (Office of Structural Engineering)::

    HW-2.1  Half-Height Headwalls for Corrugated Metal Pipe and Plastic
            Pipe  (2018-07-20, rev. 2022-07-15)
    HW-2.2  Half-Height Headwalls for Concrete Pipe  (rev. 2018-07-20)

For each pipe size the table gives headwall width ``W``, height ``H``,
thickness ``T``, and the cast-in-place concrete quantity.  HW-2.1 is keyed
by circular-pipe diameter ``D`` (the corrugated-metal/plastic primary
table; its pipe-arch tables are not transcribed here).  HW-2.2 carries both
a circular table (by diameter) and an elliptical table (by rise and span).

The data lives in the ``res/hw_2_*.csv`` files and is loaded once at import.
All dimensions are inches; concrete quantity is cubic yards.  Spot-checked
against the drawings in the test suite.
"""

import csv
import os
from dataclasses import dataclass, field

_RES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res")
_CSV_PATH = os.path.join(_RES_DIR, "hw_2_1_circular.csv")
_CSV_22_CIRC = os.path.join(_RES_DIR, "hw_2_2_circular.csv")
_CSV_22_ELLIP = os.path.join(_RES_DIR, "hw_2_2_elliptical.csv")


@dataclass(frozen=True)
class Headwall:
    """One HW-2.1 circular-pipe headwall line.

    ``diameter`` is the pipe inside diameter D; ``width`` (W), ``height``
    (H) and ``thickness`` (T) are the headwall dimensions; ``concrete_cy``
    is the cast-in-place concrete quantity.  ``note`` flags special rows
    (e.g. pipe sizes between end treatments A and B).
    """

    diameter: float       # D, in
    width: float          # W, in
    height: float         # H, in
    thickness: float      # T, in
    concrete_cy: float    # cubic yards
    note: str = ""


@dataclass(frozen=True)
class EllipticalHeadwall:
    """One HW-2.2 elliptical-pipe headwall line.

    ``rise`` and ``span`` are the pipe rise R and span; ``width`` (W),
    ``height`` (H) and ``thickness`` (T) are the headwall dimensions;
    ``concrete_cy`` is the cast-in-place concrete quantity.  All inches.
    """

    rise: float           # R, in
    span: float           # in
    width: float          # W, in
    height: float         # H, in
    thickness: float      # T, in
    concrete_cy: float    # cubic yards


def _load_circular(path: str) -> list[Headwall]:
    rows: list[Headwall] = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(
                Headwall(
                    diameter=float(r["d_in"]),
                    width=float(r["w_in"]),
                    height=float(r["h_in"]),
                    thickness=float(r["t_in"]),
                    concrete_cy=float(r["concrete_cy"]),
                    note=r.get("note", "") or "",
                )
            )
    return rows


def _load_elliptical(path: str) -> list[EllipticalHeadwall]:
    rows: list[EllipticalHeadwall] = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(
                EllipticalHeadwall(
                    rise=float(r["rise_in"]),
                    span=float(r["span_in"]),
                    width=float(r["w_in"]),
                    height=float(r["h_in"]),
                    thickness=float(r["t_in"]),
                    concrete_cy=float(r["concrete_cy"]),
                )
            )
    return rows


# ---- HW-2.1 (corrugated metal / plastic pipe), circular -----------------
#: HW-2.1 circular-pipe headwalls, ordered by pipe diameter.
HEADWALLS_CIRCULAR: list[Headwall] = _load_circular(_CSV_PATH)

#: Circular headwalls keyed by pipe diameter (inches).
HEADWALLS_BY_DIAMETER: dict[float, Headwall] = {
    h.diameter: h for h in HEADWALLS_CIRCULAR
}

# ---- HW-2.2 (concrete pipe), circular and elliptical --------------------
#: HW-2.2 concrete-pipe circular headwalls, ordered by diameter.
HEADWALLS_CONCRETE_CIRCULAR: list[Headwall] = _load_circular(_CSV_22_CIRC)

#: HW-2.2 concrete circular headwalls keyed by pipe diameter (inches).
HEADWALLS_CONCRETE_BY_DIAMETER: dict[float, Headwall] = {
    h.diameter: h for h in HEADWALLS_CONCRETE_CIRCULAR
}

#: HW-2.2 concrete-pipe elliptical headwalls, ordered by rise.
HEADWALLS_CONCRETE_ELLIPTICAL: list[EllipticalHeadwall] = _load_elliptical(
    _CSV_22_ELLIP
)


def headwall_for_diameter(diameter: float, concrete: bool = False) -> Headwall:
    """Look up the circular headwall for a pipe diameter (inches).

    ``concrete=False`` uses the HW-2.1 corrugated-metal/plastic table;
    ``concrete=True`` uses the HW-2.2 concrete-pipe table.  Raises
    ``KeyError`` if the diameter is not a tabulated size."""
    table = (
        HEADWALLS_CONCRETE_BY_DIAMETER if concrete else HEADWALLS_BY_DIAMETER
    )
    return table[diameter]


def elliptical_headwall_for_rise(rise: float) -> EllipticalHeadwall:
    """Look up the HW-2.2 concrete elliptical headwall by pipe rise (inches)."""
    for h in HEADWALLS_CONCRETE_ELLIPTICAL:
        if h.rise == rise:
            return h
    raise KeyError(f"no HW-2.2 elliptical headwall for rise {rise} in")


# ── geometry / layout (circular pipe, end treatment "A") ─────────────────
#
# The drawable subset is the rectangular cast-in-place headwall of the
# circular tables (HW-2.1 corrugated-metal/plastic, HW-2.2 concrete): a
# wall of tabulated width W and height H, front face vertical, back face
# battered from HEADWALL_TOP_THICKNESS_IN at the top to the tabulated T at
# the base, pierced by the circular pipe opening (flow line at the base
# datum, so the pipe centre sits D/2 above it).  The concrete cover over
# the pipe crown is therefore H - D; on the drawing this reaches its 6 in
# minimum exactly at D = 48 in, which is the end-treatment A/B boundary.
# Sizes with less than 6 in cover use end treatment "B" (the top is bevel-
# cut by 2:1 slopes tangent to the pipe) and the pipe-arch / elliptical
# tables are not drawn here -- both raise (see SCD_BUILD_QUESTIONS.md).

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "HW-2.1"
REVISION = "07-15-2022"

HEADWALL_TOP_THICKNESS_IN = 12.0  # wall thickness at the top (profile view)
MIN_COVER_IN = 6.0                # min concrete over the pipe crown (note)
EMBANKMENT_SLOPE = 2.0            # 2:1 fill / channel slope


@dataclass(frozen=True)
class HeadwallInput:
    """Inputs for a circular-pipe headwall solid.

    ``diameter_in`` is a tabulated pipe inside diameter D; ``concrete``
    selects the HW-2.2 concrete-pipe table instead of the HW-2.1
    corrugated-metal/plastic table."""

    diameter_in: float
    concrete: bool = False


@dataclass(frozen=True)
class HeadwallLayout:
    """The generated headwall.  ``front_outline`` is the vertical front
    face (counterclockwise in the X-Z plane at y = 0); ``side_profile`` is
    the battered wall cross-section in the Y-Z plane at x = -W/2 (front
    vertical, back battered 12 in -> T); the solid is ``side_profile``
    swept the full width W in +X with the circular ``pipe`` opening
    (centre ``pipe_center``, diameter ``pipe_diameter_ft``) cut through
    it along Y.  Origin: x = 0 on the wall centreline, y = 0 at the front
    face (wall behind, -y), z = 0 at the flow line / wall base."""

    inputs: HeadwallInput
    table: Headwall
    front_outline: tuple[Point, Point, Point, Point]
    side_profile: tuple[Point, Point, Point, Point]
    pipe_center: Point
    pipe_diameter_ft: float
    width_ft: float
    height_ft: float
    base_thickness_ft: float
    top_thickness_ft: float
    cover_in: float
    concrete_cy: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_headwall(inp: HeadwallInput) -> HeadwallLayout:
    """Generate the rectangular circular-pipe headwall solid (end
    treatment "A").

    Raises ``KeyError`` for a pipe diameter that is not a tabulated size
    and ``ValueError`` for a size whose cover over the pipe crown drops
    below the 6 in minimum (end treatment "B", not modeled here)."""
    hw = headwall_for_diameter(inp.diameter_in, concrete=inp.concrete)
    cover_in = hw.height - inp.diameter_in
    if cover_in < MIN_COVER_IN - 1e-9:
        raise ValueError(
            f"pipe diameter {inp.diameter_in:g} in leaves {cover_in:g} in "
            f"cover (< {MIN_COVER_IN:g} in): this is HW end treatment 'B' "
            "(top bevel-cut 2:1 tangent to the pipe), which is not modeled "
            "here -- see HW-2.1 sheets 1-4 and SCD_BUILD_QUESTIONS.md")

    W = hw.width / 12.0
    H = hw.height / 12.0
    T = hw.thickness / 12.0
    Tt = HEADWALL_TOP_THICKNESS_IN / 12.0
    D = inp.diameter_in / 12.0

    front_outline = ((-W / 2.0, 0.0, 0.0), (W / 2.0, 0.0, 0.0),
                     (W / 2.0, 0.0, H), (-W / 2.0, 0.0, H))
    # front face vertical at y = 0; back face battered Tt (top) -> T (base)
    side_profile = ((-W / 2.0, 0.0, 0.0), (-W / 2.0, 0.0, H),
                    (-W / 2.0, -Tt, H), (-W / 2.0, -T, 0.0))
    pipe_center = (0.0, -T / 2.0, D / 2.0)

    notes = (
        f"HW-2.1 circular headwall for {inp.diameter_in:g} in "
        f"{'concrete' if inp.concrete else 'CMP/plastic'} pipe: "
        f"W {hw.width:g} x H {hw.height:g} x T {hw.thickness:g} in, "
        f"{hw.concrete_cy:g} CY",
        f"Cover over pipe crown: {cover_in:g} in (6 in min at D = 48 in).",
        "Not modeled: end treatment 'B' (top 2:1 bevel tangent to pipe, "
        "cover < 6 in), the pipe-arch and elliptical tables, the anchor "
        "bolt/cable/eyebolt options, and the 6 in inlet headwall extension.",
    )

    return HeadwallLayout(
        inputs=inp,
        table=hw,
        front_outline=front_outline,
        side_profile=side_profile,
        pipe_center=pipe_center,
        pipe_diameter_ft=D,
        width_ft=W,
        height_ft=H,
        base_thickness_ft=T,
        top_thickness_ft=Tt,
        cover_in=cover_in,
        concrete_cy=hw.concrete_cy,
        notes=notes,
    )
