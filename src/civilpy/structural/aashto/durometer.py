durometer_strain_factors = {
    "50": {
        "12": .1697,
        "9": .1413,
        "6": .1166,
        "5": .0858,
        "4": .0627,
        "3": .0414
    },
    "60": {
        "12": .1967,
        "9": .1701,
        "6": .1446,
        "5": .1053,
        "4": .0730,
        "3": .0464
    }
}

def find_closest_key(user_input, durometer_values, category):
    """Return the strain-factor table key nearest to *user_input*.

    AASHTO shape-factor tables are defined at discrete values (3, 4, 5, 6, 9,
    12). When a designer provides an intermediate shape factor this function
    finds the nearest tabulated key so the correct strain factor can be looked
    up.

    Args:
        user_input: Shape factor value to match (numeric or string).
        durometer_values (dict): Nested dict keyed by durometer → shape factor
            → strain factor (e.g. ``durometer_strain_factors``).
        category (str): Durometer hardness category key (e.g. ``"50"``).

    Returns:
        str: The integer key in *durometer_values[category]* closest to
        *user_input*, returned as a string.
    """
    # Convert keys to numbers and compute the closest match
    values = map(float, durometer_values[category].keys())
    closest_key = min(values, key=lambda x: abs(x - float(user_input)))
    return str(int(closest_key))

#  CivilPy
#  Copyright (C) $originalComment.match("Copyright \(C\) (\d+)", 1)-2026 Dane Parks
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

# This got done because AASHTO lists strain as the independent variable, which
# seems wrong. So x and y in the formulas got twisted around during this
# This function results in the inverse of the y = Ax^1.3 formula
def get_strain_from_stress(stress, durometer, shape_factor):
    """Calculate elastomer compressive strain from applied stress.

    Inverts the AASHTO power-law relationship ``stress = A * strain^1.3``
    (where *A* is the durometer/shape-factor dependent coefficient) to solve
    for strain given a known stress. AASHTO tables list strain as the
    independent variable, so this inversion is necessary for stress-driven
    design workflows.

    Args:
        stress (float): Applied compressive stress on the bearing (ksi).
        durometer (int): Rubber hardness (50 or 60 Shore A).
        shape_factor (float): Bearing shape factor S = LW / [2t(L+W)].

    Returns:
        float: Compressive strain (dimensionless) corresponding to *stress*.
    """
    shape_factor = find_closest_key(shape_factor, durometer_strain_factors, str(durometer))
    return (stress / durometer_strain_factors[str(durometer)][shape_factor]) ** (1 / 1.3)
