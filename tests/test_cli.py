#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

from io import StringIO
import sys
from civilpy.CLI import civilpy_cli


def test_civilpy_cli_prints(capsys):
    civilpy_cli()
    captured = capsys.readouterr()
    assert "CivilPy" in captured.out
