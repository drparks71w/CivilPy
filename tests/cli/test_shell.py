#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Shell internals: completion, toolbar docs, slash commands, load."""

import pytest

from civilpy.cli import shell
from civilpy.cli.batch import build_parser
from civilpy.cli.session import CliContext

from tests.geotechnical.test_boring import DIGGS_FIXTURE


@pytest.fixture()
def ctx():
    return CliContext(interactive=True)


def _complete(text, ctx):
    state = shell._State(text, ctx)
    return [t for t, _ in shell._completions(state) if t.startswith(state.word)]


def test_completes_groups_then_verbs(ctx):
    assert "hydro" in _complete("", ctx)
    assert "load" in _complete("", ctx)
    assert _complete("hydro ", ctx) == ["channel", "scour-pier"]


def test_completes_flags_choices_and_partial(ctx):
    flags = _complete("hydro scour-pier ", ctx)
    assert "--velocity" in flags and "--shape" in flags
    assert _complete("hydro scour-pier --shape ", ctx) == [
        "round", "square", "cylinder", "sharp", "group",
    ]
    assert _complete("hydro scour-pier --pi", ctx) == [
        "--pier-width", "--pier-length",
    ]


def test_slash_completion(ctx):
    assert "/commands" in _complete("/", ctx)


def test_toolbar_doc_for_pending_value(ctx):
    state = shell._State("hydro scour-pier --velocity ", ctx)
    arg = state.pending_arg()
    assert arg.name == "velocity"
    assert "ft/s" in arg.describe()


def test_load_and_object_completion(ctx, tmp_path):
    diggs = tmp_path / "B-001.xml"
    diggs.write_text(DIGGS_FIXTURE)
    loaded = ctx.workspace.load(str(diggs))
    assert loaded[0].kind == "boring"
    names = _complete("hydro scour-pier --boring ", ctx)
    assert loaded[0].name in names
    assert ctx.workspace.resolve_boring(loaded[0].name) is loaded[0].obj


def test_dispatch_slash_and_command(ctx, capsys):
    parser = build_parser()
    assert shell._dispatch("/commands", ctx, parser) is True
    assert "hydro channel" in capsys.readouterr().out
    assert shell._dispatch("/find scour", ctx, parser) is True
    assert "scour-pier" in capsys.readouterr().out
    assert shell._dispatch("odot slab 20", ctx, parser) is True
    assert "16.25" in capsys.readouterr().out
    assert ctx.workspace.log  # /log has the one-shot line
    assert shell._dispatch("/quit", ctx, parser) is False


def test_dispatch_unknown_slash(ctx, capsys):
    assert shell._dispatch("/nope", ctx, build_parser()) is True
    assert "unknown slash command" in capsys.readouterr().out
