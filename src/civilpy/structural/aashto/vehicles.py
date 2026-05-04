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
            axels (dict): Axle configuration with keys ``'spacing'``, ``'lane_load_klf'``,
                ``1``, ``2``, ``3``. Each numbered key maps to a dict with ``'load'`` (kips)
                and ``'dist'`` (ft from axle 1, or list of allowable spacings for axle 3).
        """
        self.axels = {
            'spacing': 6,
            1: {'load': 8, 'dist': 0},
            2: {'load': 32, 'dist': 14},
            3: {'load': 32, 'dist': [14, 30]}
        }
        self.lane_load_klf = 0.64
        self.dynamic_load_allowance = 0.33


class HS20Load:
    """
    AASHTO HS-20-44 design truck per AASHTO Standard Specifications for Highway
    Bridges, 17th Ed., Article 3.7.

    HS-20 predates LRFD and is used for load rating of older structures and for
    permit routing. The axle pattern (8-32-32 kip) is identical to the HL-93
    design truck, but the rear axle spacing is fixed at 14 ft (not variable),
    and the lane load uses separate concentrated loads for moment vs. shear.
    """

    def __init__(self):
        # Axle loads in kips; distances in feet from axle 1.
        self.axles = {
            'axle_width_ft': 6,
            1: {'load_kip': 8,  'dist_ft': 0},
            2: {'load_kip': 32, 'dist_ft': 14},
            3: {'load_kip': 32, 'dist_ft': 28},  # fixed 14 ft rear spacing
        }
        # Lane load per AASHTO Standard Spec Article 3.11.3
        self.lane_load_klf = 0.64                # kip/ft uniform
        self.lane_concentrated_moment_kip = 18   # concentrated load for moment
        self.lane_concentrated_shear_kip  = 26   # concentrated load for shear
        # Impact factor = 50 / (L + 125), max 0.30; L in feet.
        # Caller must compute based on span length.
        self.impact_formula = "50 / (L + 125), max 0.30"

    @staticmethod
    def impact_factor(span_length_ft: float) -> float:
        """Return the HS-20 impact factor for the given span length (ft)."""
        return min(0.30, 50.0 / (span_length_ft + 125.0))

    def total_axle_load_kip(self) -> float:
        """Sum of all axle loads in kips."""
        return sum(a['load_kip'] for k, a in self.axles.items() if isinstance(k, int))


class PedestrianLoad:
    """
    Pedestrian live load per AASHTO LRFD Guide Specifications for Design of
    Pedestrian Bridges, 2nd Ed. (2009), Article 4.1.

    The basic uniform load is 90 psf. For bridges with loaded lengths greater
    than 25 ft, a reduced load may be used per the formula below, with a
    minimum of 20 psf.

    Reduction formula (L > 25 ft):
        w = max(20, min(90, 240 / L + 20))  [psf]
    where L is the loaded span length in feet.
    """

    def __init__(self, span_length_ft: float = 25.0, tributary_width_ft: float = 6.0):
        self.span_length_ft    = span_length_ft
        self.tributary_width_ft = tributary_width_ft
        self.dynamic_load_allowance = 0.0  # no impact for pedestrian per Guide Spec

    @property
    def uniform_load_psf(self) -> float:
        """Design pedestrian load in psf for the configured span length."""
        if self.span_length_ft <= 25.0:
            return 90.0
        return max(20.0, min(90.0, 240.0 / self.span_length_ft + 20.0))

    @property
    def uniform_load_klf(self) -> float:
        """Design pedestrian load in kip/ft over the tributary width."""
        return self.uniform_load_psf * self.tributary_width_ft / 1000.0

    def __repr__(self) -> str:
        return (
            f"PedestrianLoad(span={self.span_length_ft} ft, "
            f"width={self.tributary_width_ft} ft, "
            f"w={self.uniform_load_psf:.1f} psf, "
            f"{self.uniform_load_klf:.4f} klf)"
        )
