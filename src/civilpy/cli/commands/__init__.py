#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""CLI command modules.

Each module exports ``SPECS`` (a list of
:class:`~civilpy.cli.registry.CommandSpec`) and keeps its top-level
imports light — heavy civilpy modules are imported inside the runner
functions so ``civilpy --help`` stays fast.  Register new modules in
:data:`civilpy.cli.registry.COMMAND_MODULES`.
"""
