#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""``hydro`` commands: open-channel hydraulics and HEC-18 scour.

US customary units throughout (ft, ft/s, cfs; grain sizes in mm), matching
:mod:`civilpy.water_resources`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from civilpy.cli.io_ import Column, CommandResult, ResultTable
from civilpy.cli.registry import CliError, CommandSpec


@dataclass(frozen=True)
class ChannelInput:
    """Inputs for ``hydro channel``."""

    q: float = field(metadata={
        "positional": True, "doc": "discharge Q in cfs",
    })
    width: float = field(metadata={
        "doc": "channel bottom width in ft (rectangular section)",
    })
    n: float = field(default=0.013, metadata={
        "doc": "Manning roughness n (0.013 finished concrete)",
    })
    slope: float = field(default=0.002, metadata={
        "doc": "longitudinal bed slope, ft/ft",
    })
    depth: Optional[float] = field(default=None, metadata={
        "doc": "optional flow depth in ft: adds Froude/energy/profile "
               "classification at that depth",
    })


def run_channel(inp: ChannelInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.water_resources.open_channel import RectangularChannel

    ch = RectangularChannel(width=inp.width, n=inp.n, slope=inp.slope)
    yc = ch.critical_depth(inp.q)
    yn = ch.normal_depth(inp.q)
    rows = [
        ("Critical depth yc", yc, "ft"),
        ("Normal depth yn", yn, "ft"),
        ("Froude at yn", ch.froude(inp.q, yn), None),
        ("Regime", "mild (yn > yc)" if yn > yc else "steep (yn < yc)", None),
        ("Minimum specific energy", ch.specific_energy(inp.q, yc), "ft"),
    ]
    if inp.depth is not None:
        rows += [
            ("Froude at given depth", ch.froude(inp.q, inp.depth), None),
            ("Specific energy at depth", ch.specific_energy(inp.q, inp.depth), "ft"),
            ("GVF profile class", ch.classify_profile(inp.q, inp.depth), None),
        ]
    table = ResultTable(
        title=f"Rectangular channel — Q = {inp.q:g} cfs, b = {inp.width:g} ft",
        columns=[Column("Quantity"), Column("Value", None, ".3f"), Column("Unit")],
        rows=rows,
    )
    return CommandResult(tables=[table])


@dataclass(frozen=True)
class PierScourInput:
    """Inputs for ``hydro scour-pier`` (HEC-18 CSU local pier scour)."""

    velocity: float = field(metadata={
        "doc": "approach flow velocity V1 in ft/s",
    })
    depth: float = field(metadata={
        "doc": "approach flow depth y1 in ft",
    })
    pier_width: float = field(metadata={
        "doc": "pier width a (normal to flow) in ft",
    })
    boring: Optional[str] = field(default=None, metadata={
        "kind": "path", "exts": (".xml",),
        "doc": "bed gradation source: a loaded boring name or DIGGS file "
               "(reads D50/D95 for the armoring factor K4)",
    })
    bed_depth: float = field(default=0.0, metadata={
        "doc": "depth in the boring, ft, of the streambed gradation to use",
    })
    shape: Literal["round", "square", "cylinder", "sharp", "group"] = field(
        default="round", metadata={
            "doc": "pier nose shape for K1 (HEC-18 Table 7.1)",
        })
    pier_length: Optional[float] = field(default=None, metadata={
        "doc": "pier length in ft (with --skew, sets angle-of-attack K2)",
    })
    skew: float = field(default=0.0, metadata={
        "doc": "flow angle of attack in degrees",
    })


def run_scour_pier(inp: PierScourInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.water_resources import scour

    input_files = []
    if inp.boring:
        borehole = ctx.workspace.resolve_boring(inp.boring)
        result = scour.pier_scour_from_boring(
            borehole,
            streambed_depth_ft=inp.bed_depth,
            approach_velocity_fps=inp.velocity,
            approach_depth_ft=inp.depth,
            pier_width_ft=inp.pier_width,
            pier_length_ft=inp.pier_length,
            skew_deg=inp.skew,
            shape=inp.shape,
        )
        if inp.boring.endswith(".xml"):
            input_files.append(inp.boring)
    else:
        k1 = scour.PIER_SHAPE_K1[inp.shape]
        k2 = 1.0
        if inp.pier_length is not None and inp.skew:
            k2 = scour.angle_of_attack_factor(
                inp.pier_length, inp.pier_width, inp.skew)
        ys = scour.pier_scour_csu(
            inp.velocity, inp.depth, inp.pier_width, k1=k1, k2=k2)
        result = scour.PierScourResult(
            scour_depth_ft=ys,
            froude=scour.froude_number(inp.velocity, inp.depth),
            k1=k1, k2=k2, k3=1.1, k4=1.0,
        )

    rows = [
        ("Local pier scour ys", result.scour_depth_ft, "ft"),
        ("Approach Froude Fr1", result.froude, None),
        ("K1 (nose shape)", result.k1, None),
        ("K2 (angle of attack)", result.k2, None),
        ("K3 (bed condition)", result.k3, None),
        ("K4 (armoring)", result.k4, None),
        ("D50", result.d50_mm, "mm"),
        ("D95", result.d95_mm, "mm"),
    ]
    notes = []
    if inp.boring and result.d50_mm is None:
        notes.append("boring has no gradation near the bed depth; K4 = 1.0")
    if not inp.boring:
        notes.append("no bed gradation given: armoring K4 = 1.0 (conservative)")
    table = ResultTable(
        title="HEC-18 local pier scour (CSU equation)",
        columns=[Column("Quantity"), Column("Value", None, ".2f"), Column("Unit")],
        rows=rows,
        notes=notes,
    )
    return CommandResult(tables=[table], input_files=input_files)


SPECS = [
    CommandSpec(
        name="hydro channel",
        summary="Rectangular open-channel flow: critical/normal depth, Froude",
        input_model=ChannelInput,
        runner="civilpy.cli.commands.hydro:run_channel",
    ),
    CommandSpec(
        name="hydro scour-pier",
        summary="HEC-18 local pier scour, with bed gradation from a boring",
        description=(
            "Local pier scour by the CSU equation (HEC-18 Eq. 7.1). With "
            "--boring, D50/D95 come from the particle-size analysis nearest "
            "--bed-depth in the log and set the coarse-bed armoring factor "
            "K4; otherwise K4 = 1.0."
        ),
        input_model=PierScourInput,
        runner="civilpy.cli.commands.hydro:run_scour_pier",
    ),
]
