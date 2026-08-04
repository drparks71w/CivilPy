# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""``pdf`` commands: accessibility retrofits for drawing PDFs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from civilpy.cli import ui
from civilpy.cli.io_ import Column, CommandResult, ResultTable
from civilpy.cli.registry import CliError, CommandSpec, require


@dataclass(frozen=True)
class TagInput:
    """Inputs for ``pdf tag``."""

    path: str = field(metadata={
        "positional": True, "kind": "path", "exts": (".pdf",),
        "doc": "untagged drawing PDF (straight from the CAD exporter)",
    })
    manifest: Optional[str] = field(default=None, metadata={
        "kind": "path", "exts": (".json",),
        "doc": "sheet manifest JSON (title + per-page alt texts); "
               "alternative to --title/--alt",
    })
    title: Optional[str] = field(default=None, metadata={
        "doc": "document title (shown by AT instead of the filename)",
    })
    alt: Optional[str] = field(default=None, metadata={
        "doc": "alt text describing the drawing, applied to every page",
    })
    dest: Optional[str] = field(default=None, metadata={
        "kind": "path",
        "doc": "output path (default: <input>_tagged.pdf alongside input)",
    })
    language: str = field(default="en-US", metadata={
        "doc": "document language identifier written to /Lang",
    })


def run_tag(inp: TagInput, ctx) -> CommandResult:  # noqa: ANN001
    require("pikepdf", "pdf")

    from civilpy.general.pdf_ua import SheetManifest, tag_drawing_pdf

    src = Path(inp.path).expanduser()
    if not src.exists():
        raise CliError(f"no such file: {src}")
    if inp.manifest and (inp.title or inp.alt):
        raise CliError("pass --manifest or --title/--alt, not both")

    if inp.manifest:
        manifest_path = Path(inp.manifest).expanduser()
        if not manifest_path.exists():
            raise CliError(f"no such manifest: {manifest_path}")
        manifest = SheetManifest.from_json(manifest_path)
    elif inp.title and inp.alt:
        manifest = SheetManifest(title=inp.title, alt_texts=(inp.alt,),
                                 language=inp.language)
    else:
        raise CliError("describe the sheet: --manifest file.json, or "
                       "--title and --alt together")

    dst = (Path(inp.dest).expanduser() if inp.dest
           else src.with_name(f"{src.stem}_tagged.pdf"))
    with ui.spinner(f"Tagging {src.name} → {dst.name} (PDF/UA Figure-per-page)"):
        try:
            report = tag_drawing_pdf(src, dst, manifest)
        except ValueError as exc:
            raise CliError(str(exc))

    table = ResultTable(
        title="Tagged PDF",
        columns=[Column("Input"), Column("Output"), Column("Pages"),
                 Column("Title"), Column("Warnings")],
        rows=[(src.name, str(dst), report.pages, manifest.title,
               len(report.warnings))],
        notes=list(report.warnings) + [
            "Structural retrofit only — verify with veraPDF/PAC and "
            "review the alt text before publishing."],
    )
    return CommandResult(tables=[table], input_files=[str(src)])


SPECS = [
    CommandSpec(
        name="pdf tag",
        summary="Retrofit a drawing PDF with PDF/UA tags (Figure per page)",
        description=(
            "Wraps each page of an untagged CAD-exported PDF in a tagged "
            "Figure with alt text, and adds the PDF/UA document plumbing "
            "(structure tree, metadata, language, display title). The "
            "exporter's content streams are never modified. See "
            "docs/Accessible_Drawings.md for scope and the manifest schema."
        ),
        input_model=TagInput,
        runner="civilpy.cli.commands.pdf:run_tag",
        requires=("pikepdf",),
    ),
]
