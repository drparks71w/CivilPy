#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""``odot`` commands: Ohio DOT standards lookups, TIMS records, plan tiffs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from civilpy.cli import ui
from civilpy.cli.io_ import Column, CommandResult, ResultTable
from civilpy.cli.registry import CliError, CommandSpec, require


@dataclass(frozen=True)
class SlabInput:
    """Inputs for ``odot slab`` (concrete slab bridge deck standards)."""

    span_length: int = field(metadata={
        "positional": True,
        "doc": "span length in feet (simple: 11-38 ft, continuous: 14-46 ft)",
    })
    continuous: bool = field(default=False, metadata={
        "doc": "use the continuous-span tables instead of simple-span",
    })
    edge: Literal["drainage", "parapet"] = field(default="drainage", metadata={
        "doc": "deck edge detail: over-side drainage or parapet",
    })


_BAR_KEY = re.compile(r"^([a-z])_bar_(spacing|size|length|no|num|a|f)$")


def run_slab(inp: SlabInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.state.ohio.DOT.odot_concrete_slab_generator import (
        get_deck_parameters,
    )

    try:
        params = get_deck_parameters(
            inp.span_length,
            continuous_span=inp.continuous,
            over_side_drainage=(inp.edge == "drainage"),
        )
    except ValueError as exc:
        raise CliError(str(exc))

    deck = ResultTable(
        title=f"ODOT concrete slab deck — {params['bridge_type']} span",
        columns=[Column("Parameter"), Column("Value"), Column("Unit")],
        rows=[
            ("Span length", params["span_length"], "ft"),
            ("Deck thickness", params["thickness"], "in"),
            ("Top cover", params["top_cover"], "in"),
            ("Edge detail", params["edge_type"].replace("_", " "), None),
            ("Edge dimension d", params.get("edge_d"), "in"),
            ("Edge dimension x", params.get("edge_x"), "in"),
        ],
    )

    bars: dict = {}
    for key, value in params.items():
        m = _BAR_KEY.match(key)
        if m:
            bars.setdefault(m.group(1).upper(), {})[m.group(2)] = value
    bar_rows = [
        (
            f"{letter} bar",
            f"#{data['size']}" if data.get("size") else None,
            data.get("spacing"),
            data.get("no") or data.get("num"),
            data.get("length"),
        )
        for letter, data in sorted(bars.items())
        if data.get("size")
    ]
    reinforcement = ResultTable(
        title="Reinforcement",
        columns=[
            Column("Bar"), Column("Size"), Column("Spacing", "in"),
            Column("Count"), Column("Length", "ft"),
        ],
        rows=bar_rows,
        notes=(
            [f"U-bar lap: {params['u_bar_lap']} in"]
            if params.get("u_bar_lap") else []
        ),
    )
    return CommandResult(tables=[deck, reinforcement])


@dataclass(frozen=True)
class BridgeInput:
    """Inputs for ``odot bridge`` (TIMS bridge inventory lookup)."""

    sfn: str = field(metadata={
        "positional": True,
        "doc": "Structure File Number, e.g. 2100992",
    })


def _epoch_ms_year(value) -> Optional[str]:  # noqa: ANN001
    """TIMS date fields are epoch milliseconds (pre-1970 goes negative)."""
    if value is None:
        return None
    try:
        from datetime import datetime, timedelta

        return (datetime(1970, 1, 1) + timedelta(seconds=value / 1000)).strftime("%Y")
    except (TypeError, ValueError, OSError):
        return str(value)


def run_bridge(inp: BridgeInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.state.ohio.DOT.TIMS import (
        NBI_DESIGN_TYPE_CODES,
        NBI_MATERIAL_CODES,
        TIMSBridge,
    )

    with ui.spinner(f"Querying TIMS for SFN {inp.sfn}"):
        try:
            bridge = TIMSBridge(inp.sfn)
        except (ValueError, RuntimeError) as exc:
            raise CliError(str(exc))

    def get(attr):  # noqa: ANN001
        return getattr(bridge, attr, None)

    material = NBI_MATERIAL_CODES.get(str(get("main_str_mtl_cd")), None)
    design = NBI_DESIGN_TYPE_CODES.get(str(get("main_str_type_cd")), None)
    summary = ResultTable(
        title=f"TIMS bridge SFN {inp.sfn}",
        columns=[Column("Field"), Column("Value")],
        rows=[
            ("Route carried", get("str_loc_carried")),
            ("NLFID", get("nlfid")),
            ("County / District", f"{get('county_cd')} / {get('district')}"),
            ("Latitude", get("latitude_dd")),
            ("Longitude", get("longitude_dd")),
            ("Year built", _epoch_ms_year(get("yr_built"))),
            ("Lanes on", get("lanes_on")),
            ("Main span material", material or get("main_str_mtl_cd")),
            ("Main span type", design or get("main_str_type_cd")),
            ("Sufficiency rating", get("suff_rating")),
            ("Deck condition", get("deck_summary")),
            ("Superstructure condition", get("sups_summary")),
            ("Substructure condition", get("subs_summary")),
        ],
    )
    record = ResultTable(
        title="Full TIMS record",
        columns=[Column("Field"), Column("Value")],
        rows=sorted(
            (k, v) for k, v in vars(bridge).items() if not k.startswith("_")
        ),
    )
    return CommandResult(tables=[summary, record])


@dataclass(frozen=True)
class TiffJoinInput:
    """Inputs for ``odot tiff-join``."""

    folder: str = field(metadata={
        "positional": True, "kind": "path", "exts": (),
        "doc": "folder of single-page .tif scans (plan sheets), joined in "
               "natural filename order",
    })
    dest: Optional[str] = field(default=None, metadata={
        "kind": "path", "exts": (".tif", ".tiff"),
        "doc": "output multi-page tiff (default: <folder name>.tiff next "
               "to the folder)",
    })


@dataclass(frozen=True)
class TiffSplitInput:
    """Inputs for ``odot tiff-split``."""

    path: str = field(metadata={
        "positional": True, "kind": "path", "exts": (".tif", ".tiff"),
        "doc": "multi-page tiff (a joined plan set) to split into pages",
    })
    dest: Optional[str] = field(default=None, metadata={
        "kind": "path", "exts": (),
        "doc": "output folder (default: <file stem>_pages next to the file)",
    })


def run_tiff_join(inp: TiffJoinInput, ctx) -> CommandResult:  # noqa: ANN001
    tifftools = require("tifftools", "geo")
    from natsort import natsorted

    folder = Path(inp.folder).expanduser()
    if not folder.is_dir():
        raise CliError(f"not a folder: {folder}")
    files = natsorted(
        [f for f in folder.iterdir()
         if f.suffix.lower() in (".tif", ".tiff")],
        key=str,
    )
    if not files:
        raise CliError(f"no .tif files in {folder}")

    dest = (Path(inp.dest).expanduser() if inp.dest
            else folder.parent / f"{folder.name}.tiff")
    ifds, skipped = [], []
    with ui.progress("Reading tiff pages", total=len(files)) as advance:
        for f in files:
            try:
                ifds.extend(tifftools.read_tiff(str(f))["ifds"])
            except Exception as exc:  # scan sets often hold a bad page
                skipped.append(f"{f.name}: {exc}")
            advance(note=f.name)
    if not ifds:
        raise CliError("no readable tiff pages found")
    tifftools.write_tiff(ifds, str(dest), allowExisting=True)

    table = ResultTable(
        title="Joined plan set",
        columns=[
            Column("Output"), Column("Pages"), Column("Source files"),
            Column("Size", "MB", ".1f"),
        ],
        rows=[(str(dest), len(ifds), len(files),
               dest.stat().st_size / 1e6)],
        notes=[f"skipped {msg}" for msg in skipped],
    )
    return CommandResult(tables=[table], input_files=[str(f) for f in files])


def run_tiff_split(inp: TiffSplitInput, ctx) -> CommandResult:  # noqa: ANN001
    tifftools = require("tifftools", "geo")

    path = Path(inp.path).expanduser()
    if not path.exists():
        raise CliError(f"no such file: {path}")
    try:
        ifds = tifftools.read_tiff(str(path))["ifds"]
    except Exception as exc:
        raise CliError(f"could not read {path.name}: {exc}")
    if not ifds:
        raise CliError(f"{path.name} holds no pages")

    dest = (Path(inp.dest).expanduser() if inp.dest
            else path.parent / f"{path.stem}_pages")
    dest.mkdir(parents=True, exist_ok=True)
    digits = max(3, len(str(len(ifds))))
    rows = []
    with ui.progress("Writing pages", total=len(ifds)) as advance:
        for i, ifd in enumerate(ifds, start=1):
            out = dest / f"{path.stem}_p{i:0{digits}d}.tif"
            tifftools.write_tiff([ifd], str(out), allowExisting=True)
            rows.append((i, out.name, out.stat().st_size / 1e6))
            advance(note=out.name)

    table = ResultTable(
        title=f"Split into {dest}",
        columns=[Column("Page"), Column("File"), Column("Size", "MB", ".2f")],
        rows=rows,
    )
    return CommandResult(tables=[table], input_files=[str(path)])


SPECS = [
    CommandSpec(
        name="odot slab",
        summary="Concrete slab bridge deck parameters from ODOT standards",
        description=(
            "Looks up deck thickness, cover, edge details, and the full "
            "reinforcement schedule for an ODOT standard concrete slab "
            "bridge, from the simple-span or continuous-span tables."
        ),
        input_model=SlabInput,
        runner="civilpy.cli.commands.odot:run_slab",
    ),
    CommandSpec(
        name="odot bridge",
        summary="Look up a bridge in ODOT TIMS by Structure File Number",
        description=(
            "Queries the public TIMS bridge inventory REST service for one "
            "SFN and reports a condition/characteristics summary plus the "
            "full inventory record — exportable to xlsx for QA against "
            "AssetWise."
        ),
        input_model=BridgeInput,
        runner="civilpy.cli.commands.odot:run_bridge",
    ),
    CommandSpec(
        name="odot tiff-join",
        summary="Join single-page plan scans into one multi-page tiff",
        description=(
            "Merges a folder of single-page .tif plan sheets into one "
            "multi-page tiff in natural filename order (sheet_2 before "
            "sheet_10) — the format ODOT plan archives circulate in."
        ),
        input_model=TiffJoinInput,
        runner="civilpy.cli.commands.odot:run_tiff_join",
        requires=("tifftools",),
    ),
    CommandSpec(
        name="odot tiff-split",
        summary="Split a multi-page tiff plan set into one file per sheet",
        input_model=TiffSplitInput,
        runner="civilpy.cli.commands.odot:run_tiff_split",
        requires=("tifftools",),
    ),
]
