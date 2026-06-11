"""
CivilPy
Copyright (C) 2019-2026 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from io import StringIO
import sys
from civilpy.CLI import civilpy_cli


def test_civilpy_cli_prints(capsys):
    civilpy_cli()
    captured = capsys.readouterr()
    assert "CivilPy" in captured.out
