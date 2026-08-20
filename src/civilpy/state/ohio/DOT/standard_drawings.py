#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ODOT standard-drawing number conventions.

ODOT standard construction / bridge drawing numbers encode the year the
sheet was issued as a trailing suffix — ``CSB-1-55`` is the 1955 sheet,
``PSID-1-99`` the 1999 revision, ``SBR-1-13`` the 2013 railing.  The
suffix is two digits historically and four on some modern sheets.  This
module is the one decoder both the standards-catalog date backfill and
the era-registry queries share.
"""
from __future__ import annotations

import re

__all__ = ["year_from_drawing_no", "drawing_family"]

#: trailing -YY or -YYYY suffix (a trailing "M" marks metric sheets:
#: ``CSB-1-93M``); tolerate a stray sheet-of suffix like ``RB-1-55.2``.
#: Modern dotted series (``TC-41.20``, ``MGS-1.1``) carry no year: they
#: have a single dash and a dotted series number, so the year suffix
#: requires either a second dash before it (``CSB-1-55``) or, on a
#: single-dash number, an undotted suffix (``PCB-91``).
_SUFFIX = re.compile(
    r"-\w+-(\d{2}|\d{4})(?:M)?(?:\.\d+)?$|"
    r"^[A-Z]+-(\d{2}|\d{4})(?:M)?$", re.IGNORECASE)

def year_from_drawing_no(drawing_no: str | None) -> int | None:
    """The issue year encoded in a drawing number, or None.

    Two-digit suffixes pivot on the current year: a suffix that would
    land in the future reads as 19xx (ODOT's drawing program reaches the
    1920s, and no sheet is dated ahead of its issue).

    >>> year_from_drawing_no("CSB-1-55")
    1955
    >>> year_from_drawing_no("SBR-1-13")
    2013
    >>> year_from_drawing_no("MGS-1.1")   # dotted series: no year suffix
    """
    if not drawing_no:
        return None
    m = _SUFFIX.search(drawing_no.strip())
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    if len(raw) == 4:
        year = int(raw)
        return year if 1900 <= year <= 2099 else None
    import datetime
    year = 2000 + int(raw)
    if year > datetime.date.today().year:
        year -= 100
    return year


def drawing_family(drawing_no: str | None) -> str | None:
    """The series identity with the year suffix stripped — ``CSB-1-55``
    and ``CSB-1-93M`` are revisions of family ``CSB-1``; dotted modern
    series (``MGS-1.1``) are their own family unchanged.  Point-in-time
    catalog queries group revisions by this key."""
    if not drawing_no:
        return None
    no = drawing_no.strip().upper()
    if not no:
        return None
    if year_from_drawing_no(no) is not None:
        return re.sub(r"-(\d{2}|\d{4})(?:M)?(?:\.\d+)?$", "", no)
    return no
