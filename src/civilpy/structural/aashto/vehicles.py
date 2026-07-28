#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""AASHTO design and rating vehicles.

Axle-load/spacing definitions for the HL-93 design load (truck, tandem,
lane) plus legal and permit rating vehicles, with helpers to step axle
trains across influence lines for moving-load maxima.

The rating-vehicle catalog (:data:`RATING_VEHICLES`) carries the AASHTO
legal trucks (MBE Fig. D6A-1), the specialized hauling vehicles
(MBE Fig. D6A-2), the FAST-Act emergency vehicles, and the Ohio legal
trucks (ODOT BDM Section 908) as :class:`RatingVehicle` axle trains ready
for :meth:`InfluenceLine.maximize_axle_train
<civilpy.structural.influence_lines.InfluenceLine.maximize_axle_train>`
and :func:`~civilpy.structural.continuous_beam.moving_load_envelope`.
"""

from dataclasses import dataclass

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

    Reduction formula (L > 25 ft)::

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


@dataclass(frozen=True)
class RatingVehicle:
    """A rating vehicle as an axle train: loads (kip) at running positions
    (ft from the first axle), the form the moving-load tools consume.

    ``lane_load_klf`` is nonzero only for loadings whose definition includes
    a uniform lane component (HL-93); impact / dynamic load allowance is a
    rating-method choice and is left to the caller.
    """

    name: str
    axle_loads_kip: tuple
    axle_positions_ft: tuple
    reference: str = ""
    lane_load_klf: float = 0.0

    def __post_init__(self):
        if len(self.axle_loads_kip) != len(self.axle_positions_ft):
            raise ValueError(f"{self.name}: axle loads and positions differ "
                             f"in length")
        if list(self.axle_positions_ft) != sorted(self.axle_positions_ft):
            raise ValueError(f"{self.name}: axle positions must be "
                             f"non-decreasing")

    @property
    def gvw_kip(self) -> float:
        """Gross vehicle weight (kip)."""
        return float(sum(self.axle_loads_kip))

    @property
    def gvw_tons(self) -> float:
        """Gross vehicle weight (US tons)."""
        return self.gvw_kip / 2.0

    @property
    def wheelbase_ft(self) -> float:
        """First-to-last axle distance (ft)."""
        return float(self.axle_positions_ft[-1] - self.axle_positions_ft[0])

    @property
    def axle_spacings_ft(self) -> tuple:
        """Distances between consecutive axles (ft)."""
        p = self.axle_positions_ft
        return tuple(b - a for a, b in zip(p, p[1:]))

    def train(self) -> tuple:
        """``(loads, positions)`` for the axle-train steppers
        (:meth:`InfluenceLine.maximize_axle_train
        <civilpy.structural.influence_lines.InfluenceLine.maximize_axle_train>`,
        :func:`~civilpy.structural.continuous_beam.moving_load_envelope`)."""
        return list(self.axle_loads_kip), list(self.axle_positions_ft)

    def __repr__(self) -> str:
        return (f"RatingVehicle({self.name}: {self.gvw_kip:g} kip GVW, "
                f"{len(self.axle_loads_kip)} axles over "
                f"{self.wheelbase_ft:g} ft)")


#: AASHTO legal trucks (MBE 3rd Ed. Fig. D6A-1) — the routine commercial
#: configurations, and the three vehicles of the FHWA legal-load rating
#: mandate (ODOT BDM 908.3).
LEGAL_TRUCKS = {
    "Type 3": RatingVehicle(
        "Type 3", (16.0, 17.0, 17.0), (0.0, 15.0, 19.0),
        reference="AASHTO MBE Fig. D6A-1"),
    "Type 3S2": RatingVehicle(
        "Type 3S2", (10.0, 15.5, 15.5, 15.5, 15.5),
        (0.0, 11.0, 15.0, 37.0, 41.0),
        reference="AASHTO MBE Fig. D6A-1"),
    "Type 3-3": RatingVehicle(
        "Type 3-3", (12.0, 12.0, 12.0, 16.0, 14.0, 14.0),
        (0.0, 15.0, 19.0, 34.0, 50.0, 54.0),
        reference="AASHTO MBE Fig. D6A-1"),
}

#: Specialized hauling vehicles (MBE 3rd Ed. Fig. D6A-2): single-unit
#: multi-axle trucks introduced by the FHWA SHV rating requirement.
SHV_TRUCKS = {
    "SU4": RatingVehicle(
        "SU4", (12.0, 8.0, 17.0, 17.0), (0.0, 10.0, 14.0, 18.0),
        reference="AASHTO MBE Fig. D6A-2"),
    "SU5": RatingVehicle(
        "SU5", (12.0, 8.0, 8.0, 17.0, 17.0), (0.0, 10.0, 14.0, 18.0, 22.0),
        reference="AASHTO MBE Fig. D6A-2"),
    "SU6": RatingVehicle(
        "SU6", (11.5, 8.0, 8.0, 17.0, 17.0, 8.0),
        (0.0, 10.0, 14.0, 18.0, 22.0, 26.0),
        reference="AASHTO MBE Fig. D6A-2"),
    "SU7": RatingVehicle(
        "SU7", (11.5, 8.0, 8.0, 17.0, 17.0, 8.0, 8.0),
        (0.0, 10.0, 14.0, 18.0, 22.0, 26.0, 30.0),
        reference="AASHTO MBE Fig. D6A-2"),
}

#: FAST-Act emergency vehicles (23 U.S.C. 127(r); FHWA EV rating memo).
EMERGENCY_VEHICLES = {
    "EV2": RatingVehicle(
        "EV2", (24.0, 33.5), (0.0, 15.0),
        reference="FHWA FAST Act EV; AASHTO MBE interim"),
    "EV3": RatingVehicle(
        "EV3", (24.0, 31.0, 31.0), (0.0, 15.0, 19.0),
        reference="FHWA FAST Act EV; AASHTO MBE interim"),
}

#: Ohio legal loads (ODOT BDM Section 908): the 2F1/3F1/4F1 single-unit
#: trucks and the 5C1 semitrailer.
OHIO_LEGAL_TRUCKS = {
    "2F1": RatingVehicle(
        "2F1", (10.0, 20.0), (0.0, 10.0),
        reference="ODOT BDM Section 908"),
    "3F1": RatingVehicle(
        "3F1", (12.0, 17.0, 17.0), (0.0, 10.0, 14.0),
        reference="ODOT BDM Section 908"),
    "4F1": RatingVehicle(
        "4F1", (12.0, 14.0, 14.0, 14.0), (0.0, 10.0, 14.0, 18.0),
        reference="ODOT BDM Section 908"),
    "5C1": RatingVehicle(
        "5C1", (12.0, 17.0, 17.0, 17.0, 17.0),
        (0.0, 12.0, 16.0, 47.0, 51.0),
        reference="ODOT BDM Section 908"),
}

#: Ohio state permit loads (ODOT BDM Figure 908.3-5).  BDM 908.3: "ODOT
#: bridges shall also be rated for state permit loads shown in this
#: section by policy"; rating for these is used for internal planning and
#: screening.
OHIO_PERMIT_TRUCKS = {
    "S-PL60T": RatingVehicle(
        "S-PL60T", (13.0, 24.25, 24.25, 19.5, 19.5, 19.5),
        (0.0, 14.5, 18.75, 56.083, 60.583, 65.083),
        reference="ODOT BDM Figure 908.3-5 (120 kip / 60 ton)"),
    "S-PL65T": RatingVehicle(
        "S-PL65T", (10.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0),
        (0.0, 10.0, 14.0, 18.0, 40.0, 44.0, 48.0),
        reference="ODOT BDM Figure 908.3-5 (130 kip / 65 ton)"),
}

#: Design-load trucks in axle-train form.  The HS-20 truck is the Standard
#: Spec design/rating baseline; the HL-93 entry is the design truck at the
#: 14-ft (governing short/medium-span) rear spacing with its lane load —
#: sweep the 14-30 ft rear spacing via :meth:`InfluenceLine.hl93_effect
#: <civilpy.structural.influence_lines.InfluenceLine.hl93_effect>` when the
#: variable spacing matters (negative moment over supports).
DESIGN_TRUCKS = {
    "HS20": RatingVehicle(
        "HS20", (8.0, 32.0, 32.0), (0.0, 14.0, 28.0),
        reference="AASHTO Std. Spec. Art. 3.7"),
    "HL-93": RatingVehicle(
        "HL-93", (8.0, 32.0, 32.0), (0.0, 14.0, 28.0),
        reference="AASHTO LRFD Art. 3.6.1.2", lane_load_klf=0.64),
}

#: Every rating vehicle above, keyed by name.
RATING_VEHICLES = {
    **DESIGN_TRUCKS, **LEGAL_TRUCKS, **SHV_TRUCKS,
    **EMERGENCY_VEHICLES, **OHIO_LEGAL_TRUCKS, **OHIO_PERMIT_TRUCKS,
}

#: Everything ODOT BDM 908.3 requires a bridge to be rated for: the ten
#: commercial legal vehicles, the two emergency vehicles, and the two
#: state permit loads.
BDM_908_RATING_LOADS = (
    "2F1", "3F1", "5C1",                       # S-2F1, S-3F1, S-5C1
    "SU4", "SU5", "SU6", "SU7",
    "Type 3", "Type 3S2", "Type 3-3",
    "EV2", "EV3",
    "S-PL60T", "S-PL65T",
)
