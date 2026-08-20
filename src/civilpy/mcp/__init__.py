# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""civilpy's Model Context Protocol servers.

``civilpy.mcp.pw_server`` exposes the ODOT ProjectWise navigator
(project trees, classified document queries, completion checks, review
summaries) as MCP tools + ``pw://`` resources, over either the live
datasource (on-box) or committed recon snapshots (anywhere).

The ``mcp`` SDK is an optional dependency: ``pip install civilpy[mcp]``.
Everything except the server loop itself works without it.
"""
