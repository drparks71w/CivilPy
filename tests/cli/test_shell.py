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


# ── token splitting and filesystem completion ─────────────────────────────

class TestSplit:
    def test_respects_quotes(self):
        assert shell._split('load "my file.xml" as b1') == [
            "load", "my file.xml", "as", "b1"]

    def test_unterminated_quote_falls_back_to_whitespace(self):
        """Half-typed quotes must not crash the completer."""
        assert shell._split('load "half typed') == ["load", '"half', "typed"]


class TestPathCandidates:
    def test_lists_directories_and_filtered_files(self, tmp_path, monkeypatch):
        (tmp_path / "sub").mkdir()
        (tmp_path / "keep.xml").write_text("x")
        (tmp_path / "skip.txt").write_text("x")
        monkeypatch.chdir(tmp_path)
        got = dict(shell._path_candidates("", (".xml",)))
        assert any(k.startswith("sub") and v == "directory"
                   for k, v in got.items())
        assert any(k.endswith("keep.xml") for k in got)
        assert not any(k.endswith("skip.txt") for k in got)

    def test_no_ext_filter_lists_every_file(self, tmp_path, monkeypatch):
        (tmp_path / "a.txt").write_text("x")
        monkeypatch.chdir(tmp_path)
        assert any(k.endswith("a.txt")
                   for k, _ in shell._path_candidates("", ()))

    def test_filters_by_stem(self, tmp_path, monkeypatch):
        (tmp_path / "alpha.xml").write_text("x")
        (tmp_path / "beta.xml").write_text("x")
        monkeypatch.chdir(tmp_path)
        got = [k for k, _ in shell._path_candidates("al", (".xml",))]
        assert len(got) == 1 and got[0].endswith("alpha.xml")

    def test_hidden_files_need_an_explicit_dot(self, tmp_path, monkeypatch):
        (tmp_path / ".secret.xml").write_text("x")
        (tmp_path / "plain.xml").write_text("x")
        monkeypatch.chdir(tmp_path)
        assert not any(".secret" in k
                       for k, _ in shell._path_candidates("", (".xml",)))
        assert any(".secret" in k
                   for k, _ in shell._path_candidates(".s", (".xml",)))

    def test_missing_directory_yields_nothing(self, tmp_path):
        assert shell._path_candidates(str(tmp_path / "nope") + "/", ()) == []

    def test_unreadable_directory_is_swallowed(self, tmp_path, monkeypatch):
        def boom(self):
            raise OSError("permission denied")
        monkeypatch.setattr(shell.Path, "iterdir", boom)
        assert shell._path_candidates(str(tmp_path) + "/", ()) == []

    def test_trailing_slash_lists_inside_the_directory(self, tmp_path):
        (tmp_path / "inner.xml").write_text("x")
        got = [k for k, _ in
               shell._path_candidates(str(tmp_path) + "/", (".xml",))]
        assert any(k.endswith("inner.xml") for k in got)


# ── completion branches ───────────────────────────────────────────────────

class TestCompletionBranches:
    def test_bare_slash_lists_slash_commands(self, ctx):
        got = dict(shell._completions(shell._State("/", ctx)))
        assert set(got) == set(shell.SLASH_COMMANDS)

    def test_help_and_find_complete_full_command_names(self, ctx):
        for head in ("/help ", "/find "):
            names = [t for t, _ in
                     shell._completions(shell._State(head, ctx))]
            assert "hydro channel" in names

    def test_other_slash_commands_take_no_arguments(self, ctx):
        assert shell._completions(shell._State("/units ", ctx)) == []

    def test_bare_help_completes_groups_then_stops(self, ctx):
        first = [t for t, _ in shell._completions(shell._State("help ", ctx))]
        assert "hydro" in first
        assert shell._completions(shell._State("help hydro ", ctx)) == []

    def test_unknown_group_verb_offers_nothing(self, ctx):
        assert shell._completions(shell._State("nope nope ", ctx)) == []

    def test_boolean_flag_takes_no_value(self, ctx):
        state = shell._State("hydro scour-pier ", ctx)
        bools = [a for a in state.spec.args if a.is_bool]
        if bools:
            after = shell._State(f"hydro scour-pier {bools[0].flag} ", ctx)
            assert shell._completions(after) == []

    def test_flag_list_always_offers_output(self, ctx):
        """Once the positional is supplied the completer offers flags."""
        flags = dict(shell._completions(
            shell._State("hydro channel 100 ", ctx)))
        assert flags["-o"].startswith("write results")

    def test_used_flags_drop_out_of_the_list(self, ctx):
        state = shell._State("hydro scour-pier --shape round ", ctx)
        assert "--shape" not in [a.flag for a in state.unused_flags()]

    def test_unused_flags_empty_without_a_spec(self, ctx):
        assert shell._State("hydro ", ctx).unused_flags() == []

    def test_pending_arg_none_without_a_spec(self, ctx):
        assert shell._State("hydro ", ctx).pending_arg() is None

    def test_pending_arg_none_while_typing_a_flag(self, ctx):
        assert shell._State("hydro scour-pier --ve", ctx).pending_arg() is None


class TestCompleterAdapter:
    def test_yields_prompt_toolkit_completions(self, ctx):
        pytest.importorskip("prompt_toolkit")
        from prompt_toolkit.document import Document
        completer = shell._make_completer(ctx)
        out = list(completer.get_completions(Document("hyd"), None))
        assert [c.text for c in out] == ["hydro"]
        assert out[0].start_position == -3

    def test_display_meta_is_truncated(self, ctx):
        """Long group summaries are clipped so the dropdown stays readable."""
        pytest.importorskip("prompt_toolkit")
        from prompt_toolkit.document import Document
        completer = shell._make_completer(ctx)
        metas = [c.display_meta_text
                 for c in completer.get_completions(Document(""), None)
                 if c.display_meta]
        assert metas, "group completions carry verb-list metadata"
        assert all(len(m) <= 70 for m in metas)


class TestToolbar:
    @staticmethod
    def _text(ctx, buffer_text, monkeypatch):
        import prompt_toolkit.application as app

        class _Buf:
            text = buffer_text

        class _App:
            current_buffer = _Buf()

        monkeypatch.setattr(app, "get_app", lambda: _App())
        return shell._toolbar(ctx)()

    def test_default_hint(self, ctx, monkeypatch):
        assert "Tab completes" in self._text(ctx, "", monkeypatch)

    def test_shows_command_summary(self, ctx, monkeypatch):
        """With every positional supplied the toolbar falls back to the
        command's own summary."""
        out = self._text(ctx, "hydro channel 100 ", monkeypatch)
        assert "hydro channel" in out

    def test_shows_pending_value_doc(self, ctx, monkeypatch):
        out = self._text(ctx, "hydro scour-pier --velocity ", monkeypatch)
        assert "--velocity" in out and "ft/s" in out

    def test_shows_doc_for_a_flag_being_typed(self, ctx, monkeypatch):
        out = self._text(ctx, "hydro scour-pier --velocity", monkeypatch)
        assert "--velocity" in out

    def test_positional_shows_its_name_not_a_flag(self, ctx, monkeypatch):
        out = self._text(ctx, "hydro channel ", monkeypatch)
        assert out.lstrip().startswith("q:")


# ── slash-command bodies ──────────────────────────────────────────────────

class TestSlashCommandBodies:
    def test_banner_prints_version(self, capsys):
        shell._print_banner()
        assert "CivilPy" in capsys.readouterr().out

    def test_help_for_one_command_tabulates_arguments(self, capsys):
        shell._cmd_help(["hydro", "scour-pier"])
        out = capsys.readouterr().out
        assert "hydro scour-pier" in out
        assert "velocity" in out
        assert "results.xlsx" in out

    def test_help_for_unknown_command_errors(self, capsys):
        shell._cmd_help(["nope", "nope"])
        assert "no command" in capsys.readouterr().out

    def test_help_with_a_group_lists_that_group(self, capsys):
        shell._cmd_help(["hydro"])
        out = capsys.readouterr().out
        assert "hydro channel" in out and "odot" not in out

    def test_bare_help_lists_all_and_explains_itself(self, capsys):
        shell._cmd_help([])
        out = capsys.readouterr().out
        assert "hydro channel" in out
        assert "argument docs" in out

    def test_commands_filtered_by_group(self, capsys):
        shell._cmd_commands(group="hydro")
        out = capsys.readouterr().out
        assert "hydro channel" in out and "odot slab" not in out

    def test_find_requires_a_term(self, capsys):
        shell._cmd_find([])
        assert "usage: /find" in capsys.readouterr().out

    def test_find_reports_no_matches(self, capsys):
        shell._cmd_find(["zzzznotathing"])
        assert "nothing matches" in capsys.readouterr().out

    def test_find_searches_argument_docs_too(self, capsys):
        shell._cmd_find(["velocity"])
        assert "scour-pier" in capsys.readouterr().out

    def test_objects_empty_hints_at_load(self, ctx, capsys):
        shell._cmd_objects(ctx)
        assert "nothing loaded" in capsys.readouterr().out

    def test_objects_tabulates_what_is_loaded(self, ctx, tmp_path, capsys):
        diggs = tmp_path / "B-002.xml"
        diggs.write_text(DIGGS_FIXTURE)
        ctx.workspace.load(str(diggs))
        shell._cmd_objects(ctx)
        out = capsys.readouterr().out
        assert "boring" in out

    def test_units_cheatsheet(self, capsys):
        shell._cmd_units()
        out = capsys.readouterr().out
        assert "ft" in out and "units" in out

    def test_load_requires_a_path(self, ctx, capsys):
        shell._cmd_load(ctx, [])
        assert "usage: load" in capsys.readouterr().out

    def test_load_names_the_object_and_logs_it(self, ctx, tmp_path, capsys):
        diggs = tmp_path / "B-003.xml"
        diggs.write_text(DIGGS_FIXTURE)
        shell._cmd_load(ctx, [str(diggs), "as", "myboring"])
        assert "myboring" in capsys.readouterr().out
        assert "myboring" in ctx.workspace.objects
        assert any("as myboring" in line for line in ctx.workspace.log)

    def test_load_reports_a_bad_file(self, ctx, tmp_path, capsys):
        bad = tmp_path / "bad.xml"
        bad.write_text("<not-diggs/>")
        shell._cmd_load(ctx, [str(bad)])
        assert capsys.readouterr().out.strip()


# ── dispatch table ────────────────────────────────────────────────────────

class TestDispatch:
    @pytest.fixture()
    def parser(self):
        return build_parser()

    def test_blank_line_is_a_no_op(self, ctx, parser):
        assert shell._dispatch("", ctx, parser) is True
        assert shell._dispatch("   ", ctx, parser) is True

    @pytest.mark.parametrize("word", ["/quit", "/exit", "quit", "exit"])
    def test_every_exit_word_stops_the_loop(self, ctx, parser, word):
        assert shell._dispatch(word, ctx, parser) is False

    def test_clear_clears_the_console(self, ctx, parser, monkeypatch):
        from civilpy.cli import ui
        cleared = []
        real = ui.console()
        monkeypatch.setattr(type(real), "clear",
                            lambda self: cleared.append(True))
        assert shell._dispatch("/clear", ctx, parser) is True
        assert cleared == [True]

    @pytest.mark.parametrize("line,expected", [
        ("/help", "hydro channel"),
        ("help", "hydro channel"),
        ("/help hydro scour-pier", "velocity"),
        ("/commands hydro", "hydro channel"),
        ("/units", "ft"),
        ("/objects", "nothing loaded"),
    ])
    def test_slash_commands_render(self, ctx, parser, capsys, line, expected):
        assert shell._dispatch(line, ctx, parser) is True
        assert expected in capsys.readouterr().out

    def test_log_when_empty(self, ctx, parser, capsys):
        assert shell._dispatch("/log", ctx, parser) is True
        assert "nothing run yet" in capsys.readouterr().out

    def test_log_replays_what_ran(self, ctx, parser, capsys):
        shell._dispatch("odot slab 20", ctx, parser)
        capsys.readouterr()
        shell._dispatch("/log", ctx, parser)
        assert "odot slab 20" in capsys.readouterr().out

    def test_load_through_dispatch(self, ctx, parser, tmp_path, capsys):
        diggs = tmp_path / "B-004.xml"
        diggs.write_text(DIGGS_FIXTURE)
        assert shell._dispatch(f"load {diggs}", ctx, parser) is True
        assert ctx.workspace.objects
        assert capsys.readouterr().out.strip()


# ── the interactive loop ──────────────────────────────────────────────────

class _FakeSession:
    """Replays scripted input; a line may be an exception to raise."""

    def __init__(self, lines):
        self._lines = list(lines)
        self.kwargs = None

    def prompt(self, _message):
        if not self._lines:
            raise EOFError
        nxt = self._lines.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


@pytest.fixture()
def fake_prompt(monkeypatch):
    pytest.importorskip("prompt_toolkit")
    import prompt_toolkit
    made = {}

    def _factory(lines):
        def _PromptSession(**kwargs):
            session = _FakeSession(lines)
            session.kwargs = kwargs
            made["session"] = session
            return session
        monkeypatch.setattr(prompt_toolkit, "PromptSession", _PromptSession)
        return made
    return _factory


class TestRunShell:
    def test_runs_lines_then_exits_on_eof(self, fake_prompt, capsys):
        fake_prompt(["/units"])
        assert shell.run_shell() == 0
        out = capsys.readouterr().out
        assert "CivilPy" in out       # banner
        assert "bye" in out

    def test_quit_breaks_the_loop_before_later_lines(self, fake_prompt,
                                                     capsys):
        """Anything queued after /quit must never execute."""
        fake_prompt(["/quit", "/units"])
        assert shell.run_shell() == 0
        out = capsys.readouterr().out
        assert "bye" in out
        assert "grain sizes" not in out   # the /units panel never rendered

    def test_keyboard_interrupt_keeps_the_shell_alive(self, fake_prompt,
                                                     capsys):
        fake_prompt([KeyboardInterrupt(), "/units"])
        assert shell.run_shell() == 0
        assert "ft" in capsys.readouterr().out

    def test_cli_errors_are_reported_not_fatal(self, fake_prompt, capsys,
                                               monkeypatch):
        from civilpy.cli import batch as batch_mod
        from civilpy.cli.registry import CliError

        def boom(*a, **k):
            raise CliError("bad input")
        monkeypatch.setattr(batch_mod, "execute", boom)
        fake_prompt(["hydro channel 10", "/units"])
        assert shell.run_shell() == 0
        out = capsys.readouterr().out
        assert "bad input" in out
        assert "ft" in out            # the shell carried on

    def test_unexpected_exceptions_are_caught(self, fake_prompt, capsys,
                                              monkeypatch):
        from civilpy.cli import batch as batch_mod

        def boom(*a, **k):
            raise ZeroDivisionError("oops")
        monkeypatch.setattr(batch_mod, "execute", boom)
        fake_prompt(["hydro channel 10"])
        assert shell.run_shell() == 0
        assert "ZeroDivisionError: oops" in capsys.readouterr().out

    def test_session_is_wired_with_completer_and_toolbar(self, fake_prompt):
        made = fake_prompt([])
        shell.run_shell()
        kwargs = made["session"].kwargs
        assert kwargs["completer"] is not None
        assert callable(kwargs["bottom_toolbar"])
        assert kwargs["complete_while_typing"] is True


class TestRemainingCompletionBranches:
    def test_load_completes_loadable_files(self, ctx, tmp_path, monkeypatch):
        (tmp_path / "survey.xml").write_text("x")
        (tmp_path / "notes.md").write_text("x")
        monkeypatch.chdir(tmp_path)
        got = [t for t, _ in shell._completions(shell._State("load ", ctx))]
        assert any(t.endswith("survey.xml") for t in got)
        assert not any(t.endswith("notes.md") for t in got)

    def test_pending_arg_never_returns_a_switch(self, ctx):
        """pending_arg only ever yields a positional or a value-taking flag,
        which is why _completions' is_bool guard is unreachable."""
        args = {a.flag: a for a in shell._State("odot slab ", ctx).spec.args}
        assert args["--continuous"].is_bool
        for line in ("odot slab --continuous ", "odot slab 20 --continuous "):
            arg = shell._State(line, ctx).pending_arg()
            assert arg is None or not arg.is_bool

    def test_non_boring_path_arg_completes_only_the_filesystem(
            self, ctx, tmp_path, monkeypatch):
        """A path argument that isn't --boring must not offer session
        objects."""
        diggs = tmp_path / "B-010.xml"
        diggs.write_text(DIGGS_FIXTURE)
        loaded = ctx.workspace.load(str(diggs))
        (tmp_path / "some.json").write_text("{}")
        monkeypatch.chdir(tmp_path)
        got = [t for t, _ in
               shell._completions(shell._State("snbi validate ", ctx))]
        assert any(t.endswith("some.json") for t in got)
        assert loaded[0].name not in got

    def test_plain_value_arg_offers_no_candidates(self, ctx):
        """A float argument has nothing to complete."""
        state = shell._State("hydro channel ", ctx)
        arg = state.pending_arg()
        assert arg is not None and not arg.choices and arg.kind != "path"
        assert shell._completions(state) == []


class TestHelpWithoutDescription:
    def test_command_lacking_a_description_still_tabulates(self, capsys):
        from civilpy.cli.registry import find_spec
        assert not find_spec("hydro", "channel").description
        shell._cmd_help(["hydro", "channel"])
        out = capsys.readouterr().out
        assert "hydro channel" in out
        assert "argument" in out
