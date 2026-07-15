#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""``road`` commands: geometric design curve calculators."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from civilpy.cli.io_ import Column, CommandResult, ResultTable
from civilpy.cli.registry import CommandSpec


@dataclass(frozen=True)
class VCurveInput:
    """Inputs for ``road vcurve`` (equal-tangent parabolic curve)."""

    g1: float = field(metadata={"doc": "entering grade, percent (signed)"})
    g2: float = field(metadata={"doc": "exiting grade, percent (signed)"})
    length: float = field(metadata={"doc": "curve length L in ft"})
    pvi_station: float = field(default=0.0, metadata={
        "doc": "PVI station in ft (e.g. 1250 for 12+50)",
    })
    pvi_elevation: float = field(default=0.0, metadata={
        "doc": "PVI elevation in ft",
    })
    interval: float = field(default=50.0, metadata={
        "doc": "station interval for the elevation table, ft",
    })


def run_vcurve(inp: VCurveInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.transportation.curves import VerticalCurve, station_str

    curve = VerticalCurve(inp.g1, inp.g2, inp.length,
                          pvi_station_ft=inp.pvi_station,
                          pvi_elevation_ft=inp.pvi_elevation)
    rows = [
        ("Type", "crest" if curve.is_crest else "sag", None),
        ("Grade change A", curve.a_pct, "%"),
        ("K value", curve.k_value, "ft/%"),
        ("BVC", station_str(curve.bvc_station), None),
        ("BVC elevation", curve.bvc_elevation, "ft"),
        ("EVC", station_str(curve.evc_station), None),
        ("EVC elevation", curve.evc_elevation, "ft"),
        ("External distance E", curve.external_distance(), "ft"),
    ]
    high_low = curve.high_low_point()
    if high_low is not None:
        label = "High point" if curve.is_crest else "Low point"
        rows.append((label, station_str(high_low[0]), None))
        rows.append((f"{label} elevation", high_low[1], "ft"))
    summary = ResultTable(
        title=f"Vertical curve — g1 {inp.g1:+g}%, g2 {inp.g2:+g}%, "
              f"L {inp.length:g} ft",
        columns=[Column("Quantity"), Column("Value", None, ".2f"), Column("Unit")],
        rows=rows,
    )

    elev_rows = []
    station = curve.bvc_station
    while station < curve.evc_station - 1e-9:
        elev_rows.append((station_str(station), curve.elevation_at(station),
                          curve.grade_at(station)))
        station += inp.interval
    elev_rows.append((station_str(curve.evc_station),
                      curve.evc_elevation, inp.g2))
    profile = ResultTable(
        title="Profile",
        columns=[Column("Station"), Column("Elevation", "ft", ".2f"),
                 Column("Grade", "%", ".2f")],
        rows=elev_rows,
    )
    return CommandResult(tables=[summary, profile])


@dataclass(frozen=True)
class HCurveInput:
    """Inputs for ``road hcurve`` (simple circular curve, arc definition)."""

    radius: float = field(metadata={"doc": "curve radius R in ft"})
    delta: float = field(metadata={
        "doc": "deflection angle between tangents, degrees",
    })
    pi_station: float = field(default=0.0, metadata={
        "doc": "PI station in ft",
    })
    speed: Optional[float] = field(default=None, metadata={
        "doc": "design speed in mph: adds the side-friction demand check "
               "(e + f = V²/15R)",
    })
    superelevation: float = field(default=0.08, metadata={
        "doc": "superelevation rate e (with --speed), ft/ft",
    })


def run_hcurve(inp: HCurveInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.transportation.curves import HorizontalCurve, station_str

    curve = HorizontalCurve(inp.radius, inp.delta, pi_station_ft=inp.pi_station)
    rows = [
        ("Tangent T", curve.tangent_ft, "ft"),
        ("Arc length L", curve.length_ft, "ft"),
        ("Long chord C", curve.chord_ft, "ft"),
        ("External E", curve.external_ft, "ft"),
        ("Middle ordinate M", curve.middle_ordinate_ft, "ft"),
        ("Degree of curve D", curve.degree_of_curve_deg, "deg"),
        ("PC", station_str(curve.pc_station), None),
        ("PI", station_str(inp.pi_station), None),
        ("PT", station_str(curve.pt_station), None),
    ]
    notes = []
    if inp.speed is not None:
        f_demand = curve.side_friction_demand(inp.speed, inp.superelevation)
        rows.append((f"Side friction demand f (e = {inp.superelevation:g})",
                     f_demand, None))
        if f_demand > 0.15:
            notes.append(
                f"f = {f_demand:.3f} exceeds ~0.15: check against the AASHTO "
                f"Green Book f_max for {inp.speed:g} mph"
            )
    table = ResultTable(
        title=f"Horizontal curve — R {inp.radius:g} ft, Δ {inp.delta:g}°",
        columns=[Column("Quantity"), Column("Value", None, ".2f"), Column("Unit")],
        rows=rows,
        notes=notes,
    )
    return CommandResult(tables=[table])


SPECS = [
    CommandSpec(
        name="road vcurve",
        summary="Vertical (parabolic) curve: K, BVC/EVC, high/low point, profile",
        input_model=VCurveInput,
        runner="civilpy.cli.commands.road:run_vcurve",
    ),
    CommandSpec(
        name="road hcurve",
        summary="Horizontal (circular) curve: T, L, C, E, M, PC/PT stations",
        input_model=HCurveInput,
        runner="civilpy.cli.commands.road:run_hcurve",
    ),
]
