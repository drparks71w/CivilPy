#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""CivilPy command-line interface.

``civilpy`` with no arguments opens the interactive shell (the primary
UI: Tab completion, ``/help``, ``/commands``); with arguments it runs one
command and exits (``civilpy boring parse hole.xml -o hole.xlsx``).  The
architecture and roadmap live in ``docs/CLI_ROADMAP.md``.
"""

from __future__ import annotations

import sys
from typing import List, Optional


def civilpy_cli(argv: Optional[List[str]] = None) -> int:
    """Console-script entry point (``[project.scripts] civilpy``)."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from civilpy.cli.shell import run_shell

        return run_shell()
    from civilpy.cli.batch import main

    return main(argv)
