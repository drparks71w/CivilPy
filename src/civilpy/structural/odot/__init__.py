#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Catalog of Ohio DOT Standard Construction Drawings (SCDs).

This package transcribes the geometry, reinforcement, and design data
published on Ohio Department of Transportation standard bridge and roadway
drawings into structured, queryable Python objects.  Each catalog entry
cites its SCD number and revision date; the underlying drawings are
public-domain Ohio DOT documents.

Sub-modules:

``bridge_railing``
    Bridge railings and barriers (BR, SBR, TST, DBR, TBR, PCB series),
    each carrying its NCHRP 350 / MASH crash test level so it links to the
    Table A13.2-1 design forces in :mod:`civilpy.structural.aashto.lrfd`.
"""

from civilpy.structural.odot.bridge_railing import (
    BRIDGE_RAILINGS,
    BridgeRailing,
    railing,
    railings_for_test_level,
)

__all__ = [
    "BridgeRailing",
    "BRIDGE_RAILINGS",
    "railing",
    "railings_for_test_level",
]
