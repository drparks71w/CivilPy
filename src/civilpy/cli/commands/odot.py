#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""``odot`` commands: Ohio DOT standards lookups."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from civilpy.cli.io_ import Column, CommandResult, ResultTable
from civilpy.cli.registry import CliError, CommandSpec


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
]
