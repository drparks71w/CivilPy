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

"""Ohio DOT structural steel rockers and bolsters (RB-1-55).

Dimension and capacity table transcribed from the Ohio DOT Standard Bridge
Drawing RB-1-55, "Rockers and Bolsters for Steel and Girder Bridges"
(Office of Structural Engineering, 1955-03-01, rev. 2024-07-19).

Each row pairs a bolster (fixed bearing) with a rocker (expansion bearing)
of the same rated capacity; the number in the ``B-xxx`` / ``R-xxx``
designation is the maximum load in kips.  The dimension letters key the
figure on RB-1-55 and are stored in ``dims`` (all inches).  Per the
drawing, this design is limited to anticipated movement of 2 in or less.

Dimensions in inches, weights in pounds, load in pounds.  Spot-checked
against the drawing in the test suite.
"""

from dataclasses import dataclass

#: Dimension letters in RB-1-55 table column order.
DIM_LETTERS: tuple[str, ...] = (
    "A", "B", "C", "D", "F", "G", "H", "K", "L", "M", "R", "T", "Y",
)

#: Maximum anticipated movement this bearing design allows, inches.
MAX_MOVEMENT = 2.0


@dataclass(frozen=True)
class RockerBolster:
    """One RB-1-55 rocker/bolster capacity line.

    ``bolster_no`` is empty for the smallest line (R-75 has no matching
    bolster).  ``dims`` is keyed by the letters in :data:`DIM_LETTERS`.
    """

    capacity_kips: int
    bolster_no: str
    rocker_no: str
    dims: dict[str, float]
    weight_bolster_lb: float | None
    weight_rocker_lb: float
    max_load_lb: float


def _row(capacity, bolster_no, rocker_no, dim_values, wt_b, wt_r):
    return RockerBolster(
        capacity_kips=capacity,
        bolster_no=bolster_no,
        rocker_no=rocker_no,
        dims=dict(zip(DIM_LETTERS, dim_values)),
        weight_bolster_lb=wt_b,
        weight_rocker_lb=wt_r,
        max_load_lb=capacity * 1000.0,
    )


# Columns: A, B, C, D, F, G, H, K, L, M, R, T, Y  (inches)
_CATALOG: list[RockerBolster] = [
    _row(75, "", "R-75",
         (2.5, 8, 2.5, 1.75, 0.5, 7, 9.625, 9, 18, 16, 5.5, 1.5, 1.1875),
         None, 205),
    _row(100, "B-100", "R-100",
         (2.5, 10, 2.5, 2, 0.5, 7.5, 10.625, 9, 19, 17, 6.5, 1.5, 1.1875),
         225, 250),
    _row(125, "B-125", "R-125",
         (3, 11, 3, 2, 0.5, 8, 12.125, 10.5, 20, 18, 7.5, 1.5, 1.4375),
         295, 315),
    _row(150, "B-150", "R-150",
         (3, 12, 3, 2.25, 0.5, 8.5, 13.375, 11.5, 22, 19, 8.5, 1.75, 1.4375),
         360, 400),
    _row(175, "B-175", "R-175",
         (3, 14, 3.5, 2.5, 0.5, 9, 15.125, 12, 23, 20, 9.5, 2, 1.4375),
         455, 505),
    _row(200, "B-200", "R-200",
         (3, 16, 3.5, 2.75, 0.625, 9, 16.375, 12, 24, 21, 10.5, 2.25, 1.4375),
         540, 605),
    _row(225, "B-225", "R-225",
         (3, 17, 3.5, 2.75, 0.625, 9, 16.875, 13, 25, 22, 11, 2.25, 1.4375),
         590, 665),
    _row(250, "B-250", "R-250",
         (3.5, 18, 3.5, 2.75, 0.75, 10, 17.625, 13, 26, 23, 11.5, 2.5, 1.6875),
         695, 775),
    _row(275, "B-275", "R-275",
         (3.5, 19, 3.5, 3.25, 0.75, 12, 18.375, 14, 27, 24, 12, 2.75, 1.6875),
         800, 945),
    _row(300, "B-300", "R-300",
         (3.5, 20, 3.5, 3.25, 0.75, 12, 19.125, 14, 28, 25, 12.5, 3, 1.6875),
         895, 1050),
]


#: Rocker/bolster lines keyed by capacity in kips.
ROCKER_BOLSTERS: dict[int, RockerBolster] = {r.capacity_kips: r for r in _CATALOG}


def rocker_bolster(capacity_kips: int) -> RockerBolster:
    """Look up a rocker/bolster line by rated capacity in kips (75..300)."""
    return ROCKER_BOLSTERS[capacity_kips]


def smallest_for_load(load_lb: float) -> RockerBolster:
    """The lightest standard rocker/bolster whose maximum load covers
    ``load_lb``; raises ``ValueError`` if the load exceeds the 300-kip line."""
    for r in _CATALOG:
        if r.max_load_lb >= load_lb:
            return r
    raise ValueError(f"load {load_lb} lb exceeds the largest RB-1-55 line")
