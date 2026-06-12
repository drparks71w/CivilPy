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

"""Design-year / spec-edition handling for historical bridge designs.

Checks in this package implement the **current** LRFD edition by default.
Bridges are long-lived, so checks whose governing *values* changed between
editions accept an optional ``design_year``; passing the year the bridge
was designed selects the values in force at that time.  Checks without a
``design_year`` parameter are value-stable across the editions this package
tracks (equation renumbering alone doesn't matter — functions are keyed to
current numbering).

Known value changes wired into checks so far:

========== ======================= ====================================
Year       Article (current num.)  Change
========== ======================= ====================================
2005       5.6.7                   z-factor crack check replaced by the
                                   max-spacing method (use
                                   ``rc_crack_control_z_factor`` for
                                   pre-2005 designs)
2012       5.6.3.3                 1.2*Mcr replaced by gamma_1*gamma_3
2016       5.9.2.3.1a              transfer compression 0.60 -> 0.65 f'ci
========== ======================= ====================================
"""

# (first publication year, label) for each LRFD edition
LRFD_EDITIONS = [
    (1994, "1st"),
    (1998, "2nd"),
    (2004, "3rd"),
    (2007, "4th"),
    (2010, "5th"),
    (2012, "6th"),
    (2014, "7th"),
    (2017, "8th"),
    (2020, "9th"),
    (2024, "10th"),
]


def lrfd_edition(design_year: int | None = None) -> str:
    """Label of the LRFD edition in force for a given design year (the
    latest edition published in or before that year).  ``None`` means
    current."""
    if design_year is None:
        return LRFD_EDITIONS[-1][1]
    label = LRFD_EDITIONS[0][1]
    for year, name in LRFD_EDITIONS:
        if design_year >= year:
            label = name
    return label
