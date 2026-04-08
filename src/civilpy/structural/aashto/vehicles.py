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

class HL93Load:
    """
    AASHTO HL-93 design vehicle load per AASHTO LRFD Bridge Design Specifications.

    The HL-93 live load consists of a design truck (or tandem) combined with a
    design lane load. This class represents the design truck component: a 3-axle
    vehicle with 8-kip front axle and two 32-kip rear axles.
    """

    def __init__(self):
        """
        Initialize the HL-93 design truck with standard AASHTO axle loads and spacings.

        Axle loads (kips) and reference spacings (ft) are per AASHTO LRFD Table 3.6.1.2.2-1.
        The rear axle spacing varies between 14 ft and 30 ft; the governing spacing
        for a given span is the one that maximizes the load effect.

        Attributes:
            axels (dict): Axle configuration with keys ``'spacing'``, ``1``, ``2``, ``3``.
                Each numbered key maps to a dict with ``'load'`` (kips) and
                ``'dist'`` (ft from axle 1, or list of allowable spacings for axle 3).
        """
        self.axels = {
            'spacing': 6,
            1: {'load': 8, 'dist': 0},
            2: {'load': 32, 'dist': 14},
            3: {'load': 32, 'dist': [14, 30]}
        }
