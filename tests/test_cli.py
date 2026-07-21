#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Entry-point smoke tests; the CLI internals are covered in tests/cli/."""

from civilpy.cli import civilpy_cli


def test_help_exits_clean(capsys):
    assert civilpy_cli(["--help"]) == 0
    assert "GROUP" in capsys.readouterr().out


def test_version(capsys):
    assert civilpy_cli(["--version"]) == 0
    assert "civilpy" in capsys.readouterr().out


def test_no_verb_prints_group_help(capsys):
    assert civilpy_cli(["hydro"]) == 0
    assert "scour-pier" in capsys.readouterr().out
