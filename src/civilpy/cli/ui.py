#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Shared terminal presentation for the CivilPy CLI.

Everything the CLI prints flows through the one :func:`console` defined
here, styled by the CivilPy theme (docs/CLI_ROADMAP.md §3a), so color use
is consistent and lives in exactly one place.  The :func:`progress` /
:func:`spinner` context managers wrap :mod:`rich.progress` so command
modules never construct progress UI directly; both degrade to start/end
log lines when the output is not a live terminal or ``--quiet`` is set.
"""

from __future__ import annotations

from contextlib import contextmanager

from rich.console import Console
from rich.table import Table
from rich.theme import Theme
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

CIVILPY_THEME = Theme(
    {
        "civilpy.ok": "green",
        "civilpy.warn": "yellow",
        "civilpy.err": "bold red",
        "civilpy.value": "cyan",
        "civilpy.unit": "dim",
        "civilpy.path": "magenta underline",
        "civilpy.heading": "bold blue",
        "civilpy.dim": "dim",
    }
)

_console: Console = Console(theme=CIVILPY_THEME, highlight=False)
_quiet = False


def console() -> Console:
    """The one shared, themed console."""
    return _console


def set_quiet(quiet: bool) -> None:
    """Suppress status chatter (results still print) and live progress."""
    global _quiet
    _quiet = quiet


def is_quiet() -> bool:
    return _quiet


def ok(message: str) -> None:
    if not _quiet:
        _console.print(f"[civilpy.ok]✓[/] {message}")


def warn(message: str) -> None:
    _console.print(f"[civilpy.warn]⚠ {message}[/]")


def error(message: str) -> None:
    _console.print(f"[civilpy.err]✗ {message}[/]")


def _live_ok() -> bool:
    return not _quiet and _console.is_terminal


@contextmanager
def progress(description: str, total: int):
    """Determinate progress bar for per-item work (>5 s rule, §3a).

    Yields ``advance(n=1, note=None)``.  Non-TTY / quiet: logs start and
    end instead of animating.
    """
    if _live_ok():
        bar = Progress(
            SpinnerColumn(style="civilpy.value"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=_console,
            transient=True,
        )
        with bar:
            task = bar.add_task(description, total=total)

            def advance(n: int = 1, note: str = None):  # noqa: ANN001
                if note:
                    bar.update(task, description=f"{description} — {note}")
                bar.advance(task, n)

            yield advance
        ok(f"{description} ({total})")
    else:
        if not _quiet:
            _console.print(f"{description}… ({total} items)")

        def advance(n: int = 1, note: str = None):  # noqa: ANN001
            return None

        yield advance
        if not _quiet:
            _console.print(f"{description} done.")


@contextmanager
def spinner(description: str):
    """Indeterminate spinner with elapsed time, for single long calls
    (network requests, external engines)."""
    if _live_ok():
        bar = Progress(
            SpinnerColumn(style="civilpy.value"),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=_console,
            transient=True,
        )
        with bar:
            bar.add_task(description, total=None)
            yield
        ok(description)
    else:
        if not _quiet:
            _console.print(f"{description}…")
        yield
        if not _quiet:
            _console.print(f"{description} done.")


def _format_cell(value, fmt: str = None) -> str:  # noqa: ANN001
    if value is None:
        return "[civilpy.dim]–[/]"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float) and fmt:
        return format(value, fmt)
    if isinstance(value, float):
        return format(value, "g")
    return str(value)


def render_table(result_table) -> None:  # noqa: ANN001
    """Render one :class:`civilpy.cli.io_.ResultTable` as a rich table:
    title in the heading style, units dimmed in the header, numeric
    columns right-aligned."""
    table = Table(
        title=result_table.title,
        title_style="civilpy.heading",
        title_justify="left",
        header_style="bold",
        border_style="civilpy.dim",
    )
    for col in result_table.columns:
        header = col.name
        if col.unit:
            header += f"\n[civilpy.unit]({col.unit})[/]"
        numeric = all(
            isinstance(row[result_table.columns.index(col)], (int, float, type(None)))
            for row in result_table.rows
        )
        table.add_column(header, justify="right" if numeric else "left")
    for row in result_table.rows:
        table.add_row(
            *[_format_cell(v, c.fmt) for v, c in zip(row, result_table.columns)]
        )
    _console.print(table)
    for note in result_table.notes:
        _console.print(f"  [civilpy.warn]⚠ {note}[/]")


def render_result(result) -> None:  # noqa: ANN001
    """Render every table in a :class:`civilpy.cli.io_.CommandResult`."""
    for result_table in result.tables:
        render_table(result_table)
