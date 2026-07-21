#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""``spanwire`` commands: span-wire signal support analysis (SWISS
replacement).

Load lists ride in compact string specs so they fit flag-style input:

* ``--loads "30:55:1.6,60:90"`` — ``x:weight[:area]`` (ft, lb, sq ft)
* ``--signals "30:3BA,60:5CA"`` — ``x:CODE`` looked up in the ODOT catalog
* wye specs prefix a leg number and use ``;`` between entries:
  ``--signals "1:30:3BA;3:60:5CA"``

``spanwire system`` reads a JSON file for the closed configurations
(delta/box) and arbitrary topologies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal, Optional

from civilpy.cli.io_ import Column, CommandResult, ResultTable
from civilpy.cli.registry import CliError, CommandSpec

ODOT_DESIGN_FACTOR_FLOOR = 1.8


# ── shared parsing helpers ───────────────────────────────────────────────────


def _parse_loads(spec: Optional[str], signals: Optional[str], catalog_loader):
    """Parse ``x:weight[:area]`` and ``x:CODE`` specs into SpanLoads."""
    from civilpy.structural.spanwire import SpanLoad

    loads = []
    for chunk in _chunks(spec):
        parts = chunk.split(":")
        if len(parts) not in (2, 3):
            raise CliError(f"bad load spec {chunk!r}: use x:weight[:area]")
        try:
            x, weight = float(parts[0]), float(parts[1])
            area = float(parts[2]) if len(parts) == 3 else 0.0
        except ValueError:
            raise CliError(f"bad load spec {chunk!r}: use x:weight[:area]")
        loads.append(SpanLoad(x, weight, area))
    for chunk in _chunks(signals):
        parts = chunk.split(":")
        if len(parts) != 2:
            raise CliError(f"bad signal spec {chunk!r}: use x:CODE")
        catalog = catalog_loader()
        code = parts[1].upper()
        if code not in catalog.signals:
            raise CliError(f"unknown signal code {code!r}: try 'spanwire catalog'")
        head = catalog.signals[code]
        try:
            x = float(parts[0])
        except ValueError:
            raise CliError(f"bad signal spec {chunk!r}: use x:CODE")
        loads.append(SpanLoad(x, head.weight_lb, head.area_sqft, head.code))
    return loads


def _chunks(spec: Optional[str], sep: str = ","):
    if not spec:
        return []
    return [c.strip() for c in spec.split(sep) if c.strip()]


def _split_leg(chunk: str):
    leg, _, rest = chunk.partition(":")
    try:
        return int(leg), rest
    except ValueError:
        raise CliError(f"bad leg prefix in {chunk!r}: use leg:x:...")


def _segment_table(solution) -> ResultTable:
    rows = [
        (
            seg.name,
            seg.tension_relation,
            seg.horizontal_tension_lb,
            seg.start_elevation_ft - seg.end_elevation_ft,
            seg.start_reaction_lb,
            seg.end_reaction_lb,
            seg.low_point_x_ft,
            seg.low_point_elevation_ft,
        )
        for seg in solution.segments
    ]
    return ResultTable(
        title="Span values",
        columns=[
            Column("Segment"),
            Column("Tension relation", None, ".5f"),
            Column("H", "lb", ".1f"),
            Column("Elev diff start-end", "ft", ".2f"),
            Column("Start reaction", "lb", ".2f"),
            Column("End reaction", "lb", ".2f"),
            Column("Low point x", "ft", ".2f"),
            Column("Low point elev", "ft", ".2f"),
        ],
        rows=rows,
    )


def _pole_table(system, solution, clearance, pavement, factor) -> ResultTable:
    from civilpy.structural.spanwire import pole_base_moment

    tensions = solution.pole_tensions()
    elevations = (
        system.attachment_elevations(solution, clearance, pavement)
        if clearance is not None
        else {p: None for p in tensions}
    )
    rows = []
    for pole in sorted(tensions):
        tension = tensions[pole]
        elevation = elevations[pole]
        moment = (
            pole_base_moment(tension, elevation - pavement, factor)
            if elevation is not None
            else None
        )
        rows.append((pole, tension, tension * factor, elevation, moment))
    return ResultTable(
        title="Pole values",
        columns=[
            Column("Pole"),
            Column("Stringing tension", "lb", ".1f"),
            Column("Max wire load", "lb", ".1f"),
            Column("Attachment elev", "ft", ".2f"),
            Column("Base moment", "ft-lb", ".0f"),
        ],
        rows=rows,
    )


def _factor_and_notes(loads_by_segment) -> tuple:
    from civilpy.structural.spanwire import swiss_design_factor

    weight = sum(p.weight_lb for loads in loads_by_segment for p in loads)
    area = sum(p.area_sqft for loads in loads_by_segment for p in loads)
    notes = []
    if weight > 0:
        computed = swiss_design_factor(weight, area)
        factor = max(computed, ODOT_DESIGN_FACTOR_FLOOR)
        notes.append(
            f"legacy design factor {computed:.2f} (42 psf ASD parity; ODOT "
            f"floor {ODOT_DESIGN_FACTOR_FLOOR} applied -> {factor:.2f}). For "
            "new design, factor wind per civilpy.structural.aashto.lts."
        )
    else:
        factor = ODOT_DESIGN_FACTOR_FLOOR
        notes.append(f"no attachment loads: design factor floor {factor} used")
    return factor, notes


# ── spanwire catalog ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CatalogInput:
    """Inputs for ``spanwire catalog`` (ODOT SWISS hardware tables)."""

    kind: Literal["signals", "signs", "wires"] = field(
        default="signals", metadata={"doc": "which catalog table to list"}
    )
    match: Optional[str] = field(default=None, metadata={
        "doc": "case-insensitive substring filter on code/category/material",
    })


def run_catalog(inp: CatalogInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.structural.spanwire import load_codelist

    catalog = load_codelist()
    needle = (inp.match or "").lower()

    def keep(*fields):
        return not needle or any(needle in str(f).lower() for f in fields)

    if inp.kind == "signals":
        rows = [
            (s.code, s.category, s.sections, s.lens_size_in, s.material,
             s.weight_lb, s.height_ft, s.area_sqft)
            for s in catalog.signals.values()
            if keep(s.code, s.category, s.material)
        ]
        table = ResultTable(
            title="Signal heads (ODOT CodeList)",
            columns=[
                Column("Code"), Column("Category"), Column("Sections"),
                Column("Lens", "in"), Column("Material"),
                Column("Weight", "lb", ".1f"), Column("Height", "ft", ".1f"),
                Column("Area", "sq ft", ".2f"),
            ],
            rows=rows,
        )
    elif inp.kind == "signs":
        rows = [
            (s.code, s.category, s.weight_psf, s.hanger_lb, s.area_factor)
            for s in catalog.signs.values() if keep(s.code, s.category)
        ]
        table = ResultTable(
            title="Sign panels (ODOT CodeList)",
            columns=[
                Column("Code"), Column("Category"),
                Column("Weight", "psf", ".1f"), Column("Hanger", "lb", ".1f"),
                Column("Area factor", None, ".2f"),
            ],
            rows=rows,
        )
    else:
        rows = [
            (w.code, w.category, w.section, w.weight_plf)
            for w in catalog.wires.values() if keep(w.code, w.category, w.section)
        ]
        table = ResultTable(
            title="Wires (ODOT CodeList)",
            columns=[
                Column("Code"), Column("Category"), Column("Section"),
                Column("Weight", "lb/ft", ".2f"),
            ],
            rows=rows,
        )
    if not rows:
        table.notes.append("no catalog entries matched the filter")
    return CommandResult(tables=[table])


# ── spanwire simple ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SimpleInput:
    """Inputs for ``spanwire simple`` (single span between two poles)."""

    length: float = field(metadata={
        "doc": "horizontal span length pole-to-pole, ft", "positional": True,
    })
    sag: float = field(metadata={"doc": "required sag, ft (typ. 3-5% of span)"})
    wire_weight: float = field(default=1.0, metadata={
        "doc": "wire weight, lb/ft (ODOT default 1.0; 1.5 with heavy cabling)",
    })
    loads: Optional[str] = field(default=None, metadata={
        "doc": "custom loads, 'x:weight[:area]' comma-separated",
    })
    signals: Optional[str] = field(default=None, metadata={
        "doc": "catalog signals, 'x:CODE' comma-separated",
    })
    end_elevation: float = field(default=0.0, metadata={
        "doc": "end attachment elevation relative to start, ft",
    })
    clearance: Optional[float] = field(default=None, metadata={
        "doc": "min clearance ground-to-wire, ft: adds attachment elevations "
               "and base moments (ODOT typ. 20.5)",
    })
    pavement_elevation: float = field(default=0.0, metadata={
        "doc": "pavement elevation under the low point, ft",
    })


def run_simple(inp: SimpleInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.structural.spanwire import (
        SimpleSpan, load_codelist, pole_base_moment,
    )

    loads = _parse_loads(inp.loads, inp.signals, load_codelist)
    span = SimpleSpan(
        inp.length,
        wire_weight_plf=inp.wire_weight,
        end_elevation_ft=inp.end_elevation,
        loads=loads,
    )
    try:
        sol = span.solve(inp.sag)
    except ValueError as exc:
        raise CliError(str(exc))

    factor, notes = _factor_and_notes([loads])
    rows = [
        ("Stringing tension H", sol.horizontal_tension_lb, "lb"),
        ("Max wire load (H x factor)", sol.horizontal_tension_lb * factor, "lb"),
        ("Sag achieved", sol.sag_ft, "ft"),
        ("Start reaction", sol.start_reaction_lb, "lb"),
        ("End reaction", sol.end_reaction_lb, "lb"),
        ("Low point x", sol.low_point_x_ft, "ft"),
        ("Low point elevation", sol.low_point_elevation_ft, "ft"),
        ("Total load", span.total_load_lb, "lb"),
    ]
    if inp.clearance is not None:
        start, end = span.attachment_elevations(
            sol, inp.clearance, inp.pavement_elevation
        )
        rows += [
            ("Start attachment elevation", start, "ft"),
            ("End attachment elevation", end, "ft"),
            ("Start base moment", pole_base_moment(
                sol.horizontal_tension_lb, start - inp.pavement_elevation, factor
            ), "ft-lb"),
            ("End base moment", pole_base_moment(
                sol.horizontal_tension_lb, end - inp.pavement_elevation, factor
            ), "ft-lb"),
        ]
    summary = ResultTable(
        title=f"Simple span — {inp.length:g} ft, sag {inp.sag:g} ft",
        columns=[Column("Quantity"), Column("Value", None, ".2f"), Column("Unit")],
        rows=rows,
        notes=notes,
    )
    tables = [summary]
    if loads:
        tables.append(ResultTable(
            title="Loads",
            columns=[
                Column("Label"), Column("x", "ft", ".1f"),
                Column("Weight", "lb", ".1f"), Column("Area", "sq ft", ".2f"),
            ],
            rows=[(p.label or "-", p.x_ft, p.weight_lb, p.area_sqft)
                  for p in span.loads],
        ))
    return CommandResult(tables=tables)


# ── spanwire wye ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WyeInput:
    """Inputs for ``spanwire wye`` (three poles on one bullring)."""

    lengths: str = field(metadata={
        "doc": "three leg lengths, ft, comma-separated (pole to bullring)",
        "positional": True,
    })
    bearings: str = field(metadata={
        "doc": "three plan bearings of the legs, degrees CCW from east",
    })
    sag: float = field(metadata={"doc": "required system sag, ft"})
    wire_weight: float = field(default=1.0, metadata={
        "doc": "wire weight on all segments, lb/ft",
    })
    loads: Optional[str] = field(default=None, metadata={
        "doc": "custom loads 'leg:x:weight[:area]', ';'-separated",
    })
    signals: Optional[str] = field(default=None, metadata={
        "doc": "catalog signals 'leg:x:CODE', ';'-separated",
    })
    clearance: Optional[float] = field(default=None, metadata={
        "doc": "min clearance ground-to-wire, ft: adds pole table elevations",
    })
    pavement_elevation: float = field(default=0.0, metadata={
        "doc": "pavement elevation under the low point, ft",
    })


def run_wye(inp: WyeInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.structural.spanwire import SpanWireSystem, load_codelist

    lengths = _floats(inp.lengths, 3, "lengths")
    bearings = _floats(inp.bearings, 3, "bearings")

    per_leg: dict[str, list] = {}
    for chunk in _chunks(inp.loads, ";"):
        leg, rest = _split_leg(chunk)
        per_leg.setdefault(f"P{leg}R1", []).extend(
            _parse_loads(rest, None, load_codelist)
        )
    for chunk in _chunks(inp.signals, ";"):
        leg, rest = _split_leg(chunk)
        per_leg.setdefault(f"P{leg}R1", []).extend(
            _parse_loads(None, rest, load_codelist)
        )

    try:
        system = SpanWireSystem.wye(
            tuple(lengths), tuple(bearings),
            loads=per_leg, wire_weight_plf=inp.wire_weight,
        )
        sol = system.solve(inp.sag)
    except ValueError as exc:
        raise CliError(str(exc))

    factor, notes = _factor_and_notes(per_leg.values())
    tables = [_segment_table(sol),
              _pole_table(system, sol, inp.clearance, inp.pavement_elevation,
                          factor)]
    tables[0].notes.extend(notes)
    return CommandResult(tables=tables)


def _floats(spec: str, count: int, what: str):
    values = _chunks(spec)
    try:
        floats = [float(v) for v in values]
    except ValueError:
        raise CliError(f"bad {what} {spec!r}: use {count} comma-separated numbers")
    if len(floats) != count:
        raise CliError(f"{what} needs exactly {count} values, got {len(floats)}")
    return floats


# ── spanwire system (JSON) ───────────────────────────────────────────────────


@dataclass(frozen=True)
class SystemInput:
    """Inputs for ``spanwire system`` (wye/delta/box/custom from JSON)."""

    config: str = field(metadata={
        "doc": "JSON system definition (see command description)",
        "positional": True, "kind": "path", "exts": (".json",),
    })


SYSTEM_JSON_DOC = """\
JSON schema, by "configuration":
  "wye":    {"lengths": [l1,l2,l3], "bearings": [b1,b2,b3]}
  "delta":  {"rings": [[x,y]x3], "tail_lengths": [...], "tail_bearings": [...]}
  "box":    {"rings": [[x,y]x4], "tail_lengths": [...], "tail_bearings": [...]}
  "custom": {"poles": {"P1": [x,y], ...}, "rings": {"R1": [x,y], ...},
             "segments": [{"name","start","end"}, ...]}
plus common keys: "required_sag_ft" (required), "wire_weight_plf",
"loads" {segment: [{"x_ft","weight_lb","area_sqft"} | {"x_ft","signal"}]},
"pole_attachment_elevations" {pole: ft}, "balance_pole",
"clearance_ft", "pavement_elevation_ft".  Bearings: degrees CCW from east;
segment names: tails "P1R1".., interior sides "R1R2"..."""


def run_system(inp: SystemInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.structural.spanwire import (
        SegmentDef, SpanLoad, SpanWireSystem, load_codelist,
    )

    try:
        config = json.loads(open(inp.config, encoding="utf-8").read())
    except OSError as exc:
        raise CliError(f"no such file: {exc.filename or inp.config}")
    except json.JSONDecodeError as exc:
        raise CliError(f"{inp.config}: invalid JSON ({exc})")

    def load_list(entries):
        loads = []
        for entry in entries:
            if "signal" in entry:
                catalog = load_codelist()
                code = str(entry["signal"]).upper()
                if code not in catalog.signals:
                    raise CliError(f"unknown signal code {code!r}")
                head = catalog.signals[code]
                loads.append(SpanLoad(float(entry["x_ft"]), head.weight_lb,
                                      head.area_sqft, head.code))
            else:
                loads.append(SpanLoad(
                    float(entry["x_ft"]), float(entry["weight_lb"]),
                    float(entry.get("area_sqft", 0.0)),
                    str(entry.get("label", "")),
                ))
        return loads

    loads = {name: load_list(entries)
             for name, entries in config.get("loads", {}).items()}
    wire = float(config.get("wire_weight_plf", 0.0))
    elevations = config.get("pole_attachment_elevations")
    shape = config.get("configuration", "custom")

    try:
        if shape == "wye":
            system = SpanWireSystem.wye(
                tuple(config["lengths"]), tuple(config["bearings"]),
                loads=loads, wire_weight_plf=wire,
                pole_attachment_elevations=elevations,
            )
        elif shape in ("delta", "box"):
            builder = getattr(SpanWireSystem, shape)
            system = builder(
                tuple(tuple(p) for p in config["rings"]),
                tuple(config["tail_lengths"]), tuple(config["tail_bearings"]),
                loads=loads, wire_weight_plf=wire,
                pole_attachment_elevations=elevations,
                balance_pole=config.get("balance_pole", "P2"),
            )
        elif shape == "custom":
            segments = [
                SegmentDef(
                    s["name"], s["start"], s["end"],
                    float(s.get("wire_weight_plf", wire)),
                    tuple(loads.get(s["name"], ())),
                )
                for s in config["segments"]
            ]
            system = SpanWireSystem(
                {n: tuple(p) for n, p in config["poles"].items()},
                {n: tuple(p) for n, p in config.get("rings", {}).items()},
                segments,
                pole_attachment_elevations=elevations,
                balance_pole=config.get("balance_pole"),
            )
        else:
            raise CliError(f"unknown configuration {shape!r}")
        sol = system.solve(float(config["required_sag_ft"]))
    except KeyError as exc:
        raise CliError(f"{inp.config}: missing key {exc}")
    except ValueError as exc:
        raise CliError(str(exc))

    factor, notes = _factor_and_notes(loads.values())
    if sol.balance_pole is not None:
        direction = "counterclockwise" if sol.balance_rotation_deg > 0 else "clockwise"
        if sol.in_balance:
            notes.append("system is in balance")
        else:
            notes.append(
                f"for system balance rotate {sol.balance_pole} "
                f"{abs(sol.balance_rotation_deg):.1f} degrees {direction} — "
                "results use the rotated (balanced) position "
                f"{tuple(round(c, 2) for c in sol.balanced_pole_position)}"
            )
    tables = [
        _segment_table(sol),
        _pole_table(system, sol, config.get("clearance_ft"),
                    float(config.get("pavement_elevation_ft", 0.0)), factor),
    ]
    tables[0].notes.extend(notes)
    return CommandResult(tables=tables, input_files=[inp.config])


SPECS = [
    CommandSpec(
        name="spanwire catalog",
        summary="List ODOT signal/sign/wire hardware from the SWISS CodeList",
        input_model=CatalogInput,
        runner="civilpy.cli.commands.spanwire:run_catalog",
    ),
    CommandSpec(
        name="spanwire simple",
        summary="Sag-tension solve for a single span between two poles",
        input_model=SimpleInput,
        runner="civilpy.cli.commands.spanwire:run_simple",
    ),
    CommandSpec(
        name="spanwire wye",
        summary="Wye span: three poles on one bullring, tension relations + sag",
        input_model=WyeInput,
        runner="civilpy.cli.commands.spanwire:run_wye",
    ),
    CommandSpec(
        name="spanwire system",
        summary="Full system (wye/delta/box/custom) from a JSON definition",
        input_model=SystemInput,
        runner="civilpy.cli.commands.spanwire:run_system",
        description=SYSTEM_JSON_DOC,
    ),
]
