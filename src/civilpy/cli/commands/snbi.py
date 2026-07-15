#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""``snbi`` commands: FHWA SNBI submission validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from civilpy.cli import ui
from civilpy.cli.io_ import Column, CommandResult, ResultTable
from civilpy.cli.registry import CliError, CommandSpec, require


@dataclass(frozen=True)
class SnbiValidateInput:
    """Inputs for ``snbi validate``."""

    path: str = field(metadata={
        "positional": True, "kind": "path", "exts": (".json",),
        "doc": "SNBI submission: a JSON bridge record, or an array of them",
    })


def _record_label(record, index: int) -> str:  # noqa: ANN001
    if isinstance(record, dict) and record.get("BID01"):
        return str(record["BID01"])
    return f"record {index + 1}"


def run_validate(inp: SnbiValidateInput, ctx) -> CommandResult:  # noqa: ANN001
    require("pydantic", "validation")
    from pydantic import ValidationError

    from civilpy.state.ohio.snbi import Bridge

    path = Path(inp.path).expanduser()
    if not path.exists():
        raise CliError(f"no such file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"{path.name} is not valid JSON: {exc}")

    records = data if isinstance(data, list) else [data]
    if not records:
        raise CliError(f"{path.name}: no bridge records to validate")

    error_rows = []
    passed = 0
    with ui.progress("Validating SNBI records", total=len(records)) as advance:
        for i, record in enumerate(records):
            label = _record_label(record, i)
            if not isinstance(record, dict):
                error_rows.append(
                    (label, "(record)", "record is not a JSON object", "type")
                )
                advance(note=label)
                continue
            try:
                Bridge.model_validate(record)
                passed += 1
            except ValidationError as exc:
                for err in exc.errors():
                    loc = ".".join(str(part) for part in err["loc"]) or "(record)"
                    error_rows.append((label, loc, err["msg"], err["type"]))
            advance(note=label)

    failed = len(records) - passed
    tables = [ResultTable(
        title="SNBI validation",
        columns=[
            Column("Records"), Column("Passed"), Column("Failed"),
            Column("Errors"),
        ],
        rows=[(len(records), passed, failed, len(error_rows))],
        notes=[] if not failed else [
            f"{failed} record(s) failed FHWA SNBI validation"
        ],
    )]
    if error_rows:
        tables.append(ResultTable(
            title="Errors",
            columns=[
                Column("Bridge"), Column("Item"), Column("Problem"),
                Column("Check"),
            ],
            rows=error_rows,
        ))
    return CommandResult(
        tables=tables,
        input_files=[str(path)],
        exit_code=1 if failed else 0,
    )


SPECS = [
    CommandSpec(
        name="snbi validate",
        summary="Validate a JSON SNBI submission against the FHWA rules",
        description=(
            "Checks every bridge record in a JSON file against the FHWA "
            "SNBI data-validation rules (data types, character sets, "
            "enumerated codes, and cross-field consistency). Prints a "
            "summary plus one row per violation, and exits nonzero when "
            "any record fails — so a submission can be gated in CI."
        ),
        input_model=SnbiValidateInput,
        runner="civilpy.cli.commands.snbi:run_validate",
        requires=("pydantic",),
    ),
]
