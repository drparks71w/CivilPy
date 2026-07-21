#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""``report`` commands: publish calculation notebooks as clean documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from civilpy.cli import ui
from civilpy.cli.io_ import Column, CommandResult, ResultTable
from civilpy.cli.registry import CliError, CommandSpec, require


@dataclass(frozen=True)
class NotebookInput:
    """Inputs for ``report notebook``."""

    path: str = field(metadata={
        "positional": True, "kind": "path", "exts": (".ipynb",),
        "doc": "Jupyter notebook to export (cells tagged remove_cell / "
               "remove_input / remove_output are filtered)",
    })
    format: Literal["webpdf", "pdf", "latex"] = field(
        default="webpdf", metadata={
            "doc": "webpdf renders in a headless browser; pdf/latex go "
                   "through LaTeX",
        })
    text_width: str = field(default="70ch", metadata={
        "doc": "cap on markdown line length in webpdf exports (CSS size; "
               "'none' disables)",
    })
    branding: Optional[Literal["odot"]] = field(default=None, metadata={
        "doc": "style the webpdf export with an agency palette and title "
               "block",
    })


def run_notebook(inp: NotebookInput, ctx) -> CommandResult:  # noqa: ANN001
    require("nbformat", "jupyter")
    require("nbconvert", "jupyter")

    path = Path(inp.path).expanduser()
    if not path.exists():
        raise CliError(f"no such file: {path}")
    if path.suffix.lower() != ".ipynb":
        raise CliError(f"{path.name} is not a .ipynb notebook")
    if inp.branding and inp.format != "webpdf":
        raise CliError("--branding applies to the webpdf format only")

    from civilpy.general.jupyter import notebook_converter

    text_width = None if inp.text_width.lower() in ("none", "") else inp.text_width
    out = path.with_suffix(".tex" if inp.format == "latex" else ".pdf")
    with ui.spinner(f"Exporting {path.name} → {out.name} ({inp.format})"):
        try:
            notebook_converter(
                str(path), format=inp.format, text_width=text_width,
                branding=inp.branding,
            )
        except (RuntimeError, OSError, ImportError) as exc:
            hints = {
                "webpdf": "webpdf needs a headless browser: pip install "
                          "playwright && playwright install chromium",
                "pdf": "pdf export needs a LaTeX installation (xelatex) "
                       "and pandoc",
                "latex": "latex export needs pandoc",
            }
            raise CliError(f"export failed: {exc}\n  {hints[inp.format]}")

    if not out.exists():
        raise CliError(f"exporter finished but {out} was not written")

    table = ResultTable(
        title="Notebook export",
        columns=[
            Column("Notebook"), Column("Format"), Column("Output"),
            Column("Size", "KB", ".0f"),
        ],
        rows=[(path.name, inp.format, str(out), out.stat().st_size / 1024)],
    )
    return CommandResult(tables=[table], input_files=[str(path)])


SPECS = [
    CommandSpec(
        name="report notebook",
        summary="Export a calculation notebook to PDF/LaTeX with tag filtering",
        description=(
            "Renders a Jupyter notebook to a publishable document via "
            "nbconvert. Cells tagged remove_cell, remove_input, or "
            "remove_output are stripped, markdown is capped at a readable "
            "line length, and --branding odot applies the ODOT palette "
            "and a title block at export time."
        ),
        input_model=NotebookInput,
        runner="civilpy.cli.commands.report:run_notebook",
        requires=("nbconvert",),
    ),
]
