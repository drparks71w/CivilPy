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

"""Ohio DOT cast-in-place half-height headwalls (HW-2.1).

Cast-in-place headwall dimension table transcribed from the Ohio DOT
Standard Bridge Drawing HW-2.1, "Half-Height Headwalls for Corrugated Metal
Pipe and Plastic Pipe" (Office of Structural Engineering, 2018-07-20, rev.
2022-07-15).

This module carries the *circular* pipe table (the primary headwall
dimension table): for each pipe diameter ``D`` it gives headwall width
``W``, height ``H``, thickness ``T``, and the concrete quantity.  The
companion pipe-arch tables on the same sheet are not transcribed here.

The table data lives in ``res/hw_2_1_circular.csv`` and is loaded once at
import.  All dimensions are inches; concrete quantity is cubic yards.
Spot-checked against the drawing in the test suite.
"""

import csv
import os
from dataclasses import dataclass

_RES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res")
_CSV_PATH = os.path.join(_RES_DIR, "hw_2_1_circular.csv")


@dataclass(frozen=True)
class Headwall:
    """One HW-2.1 circular-pipe headwall line.

    ``diameter`` is the pipe inside diameter D; ``width`` (W), ``height``
    (H) and ``thickness`` (T) are the headwall dimensions; ``concrete_cy``
    is the cast-in-place concrete quantity.  ``note`` flags special rows
    (e.g. pipe sizes between end treatments A and B).
    """

    diameter: float       # D, in
    width: float          # W, in
    height: float         # H, in
    thickness: float      # T, in
    concrete_cy: float    # cubic yards
    note: str = ""


def _load() -> list[Headwall]:
    rows: list[Headwall] = []
    with open(_CSV_PATH, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(
                Headwall(
                    diameter=float(r["d_in"]),
                    width=float(r["w_in"]),
                    height=float(r["h_in"]),
                    thickness=float(r["t_in"]),
                    concrete_cy=float(r["concrete_cy"]),
                    note=r.get("note", "") or "",
                )
            )
    return rows


#: HW-2.1 circular-pipe headwalls, ordered by pipe diameter.
HEADWALLS_CIRCULAR: list[Headwall] = _load()

#: Circular headwalls keyed by pipe diameter (inches).
HEADWALLS_BY_DIAMETER: dict[float, Headwall] = {
    h.diameter: h for h in HEADWALLS_CIRCULAR
}


def headwall_for_diameter(diameter: float) -> Headwall:
    """Look up the circular headwall for a given pipe diameter (inches).

    Raises ``KeyError`` if the diameter is not a tabulated size."""
    return HEADWALLS_BY_DIAMETER[diameter]
