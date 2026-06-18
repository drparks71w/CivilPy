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

"""Ohio DOT cast-in-place half-height headwalls (HW-2.1, HW-2.2).

Cast-in-place headwall dimension tables transcribed from two Ohio DOT
Standard Bridge Drawings (Office of Structural Engineering):

    HW-2.1  Half-Height Headwalls for Corrugated Metal Pipe and Plastic
            Pipe  (2018-07-20, rev. 2022-07-15)
    HW-2.2  Half-Height Headwalls for Concrete Pipe  (rev. 2018-07-20)

For each pipe size the table gives headwall width ``W``, height ``H``,
thickness ``T``, and the cast-in-place concrete quantity.  HW-2.1 is keyed
by circular-pipe diameter ``D`` (the corrugated-metal/plastic primary
table; its pipe-arch tables are not transcribed here).  HW-2.2 carries both
a circular table (by diameter) and an elliptical table (by rise and span).

The data lives in the ``res/hw_2_*.csv`` files and is loaded once at import.
All dimensions are inches; concrete quantity is cubic yards.  Spot-checked
against the drawings in the test suite.
"""

import csv
import os
from dataclasses import dataclass

_RES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res")
_CSV_PATH = os.path.join(_RES_DIR, "hw_2_1_circular.csv")
_CSV_22_CIRC = os.path.join(_RES_DIR, "hw_2_2_circular.csv")
_CSV_22_ELLIP = os.path.join(_RES_DIR, "hw_2_2_elliptical.csv")


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


@dataclass(frozen=True)
class EllipticalHeadwall:
    """One HW-2.2 elliptical-pipe headwall line.

    ``rise`` and ``span`` are the pipe rise R and span; ``width`` (W),
    ``height`` (H) and ``thickness`` (T) are the headwall dimensions;
    ``concrete_cy`` is the cast-in-place concrete quantity.  All inches.
    """

    rise: float           # R, in
    span: float           # in
    width: float          # W, in
    height: float         # H, in
    thickness: float      # T, in
    concrete_cy: float    # cubic yards


def _load_circular(path: str) -> list[Headwall]:
    rows: list[Headwall] = []
    with open(path, newline="") as fh:
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


def _load_elliptical(path: str) -> list[EllipticalHeadwall]:
    rows: list[EllipticalHeadwall] = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(
                EllipticalHeadwall(
                    rise=float(r["rise_in"]),
                    span=float(r["span_in"]),
                    width=float(r["w_in"]),
                    height=float(r["h_in"]),
                    thickness=float(r["t_in"]),
                    concrete_cy=float(r["concrete_cy"]),
                )
            )
    return rows


# ---- HW-2.1 (corrugated metal / plastic pipe), circular -----------------
#: HW-2.1 circular-pipe headwalls, ordered by pipe diameter.
HEADWALLS_CIRCULAR: list[Headwall] = _load_circular(_CSV_PATH)

#: Circular headwalls keyed by pipe diameter (inches).
HEADWALLS_BY_DIAMETER: dict[float, Headwall] = {
    h.diameter: h for h in HEADWALLS_CIRCULAR
}

# ---- HW-2.2 (concrete pipe), circular and elliptical --------------------
#: HW-2.2 concrete-pipe circular headwalls, ordered by diameter.
HEADWALLS_CONCRETE_CIRCULAR: list[Headwall] = _load_circular(_CSV_22_CIRC)

#: HW-2.2 concrete circular headwalls keyed by pipe diameter (inches).
HEADWALLS_CONCRETE_BY_DIAMETER: dict[float, Headwall] = {
    h.diameter: h for h in HEADWALLS_CONCRETE_CIRCULAR
}

#: HW-2.2 concrete-pipe elliptical headwalls, ordered by rise.
HEADWALLS_CONCRETE_ELLIPTICAL: list[EllipticalHeadwall] = _load_elliptical(
    _CSV_22_ELLIP
)


def headwall_for_diameter(diameter: float, concrete: bool = False) -> Headwall:
    """Look up the circular headwall for a pipe diameter (inches).

    ``concrete=False`` uses the HW-2.1 corrugated-metal/plastic table;
    ``concrete=True`` uses the HW-2.2 concrete-pipe table.  Raises
    ``KeyError`` if the diameter is not a tabulated size."""
    table = (
        HEADWALLS_CONCRETE_BY_DIAMETER if concrete else HEADWALLS_BY_DIAMETER
    )
    return table[diameter]


def elliptical_headwall_for_rise(rise: float) -> EllipticalHeadwall:
    """Look up the HW-2.2 concrete elliptical headwall by pipe rise (inches)."""
    for h in HEADWALLS_CONCRETE_ELLIPTICAL:
        if h.rise == rise:
            return h
    raise KeyError(f"no HW-2.2 elliptical headwall for rise {rise} in")
