#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Registry for AASHTO LRFD-LTS checks.

Shares the :class:`CheckResult` type with the bridge LRFD package but keeps
its own article registry — LTS article numbers (e.g. "5.10") would collide
with BDS numbering in a single dict.
"""

from __future__ import annotations

from civilpy.structural.aashto.lrfd.core import CheckResult

# Registry of check functions keyed by LTS article number, populated by the
# @lts_article decorator as check modules are imported.
LTS_ARTICLES: dict[str, callable] = {}


def lts_article(number: str, name: str):
    """Register a check function under its LRFD-LTS article number."""

    def decorator(func):
        func.article_number = number
        func.article_name = name
        LTS_ARTICLES[number] = func
        return func

    return decorator


__all__ = ["CheckResult", "LTS_ARTICLES", "lts_article"]
