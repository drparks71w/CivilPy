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

"""Ohio DOT prestressed concrete box beam construction details (PSBD-1-25).

Transcribed from the Ohio DOT Standard Bridge Drawing PSBD-1-25,
"Prestressed Concrete Box Beam Details" (Office of Structural Engineering,
2025-07-18, rev. 2026-01-16, 6 sheets).  Captured here: design-stress and
material specs, transverse tie rod and anchor dowel details, shear-key
grouting, intermediate-diaphragm placement rules, the available beam
depths, and the standard steel-reinforced elastomeric bearing pads (B1/B2)
with their design data.

NOT included: the standard box-beam *section dimensions*, *strand patterns*,
and *load ratings*.  PSBD-1-25 states those live on the companion design
data sheet PSBDD-1-25, which is not part of this transcription
(:data:`DESIGN_DATA_SHEET`).

Lengths are in inches, forces in kips, stresses/moduli in ksi unless a
field name says otherwise.  Values are spot-checked against the drawing in
the test suite; the drawing remains the controlling document.
"""

from dataclasses import dataclass

#: Companion design data sheet (section dims, strand tables, load ratings)
#: referenced by PSBD-1-25 but not transcribed here.
DESIGN_DATA_SHEET = "PSBDD-1-25"

#: Standard box-beam depths, inches (PSBD-1-25 sheet 4/6).
BOX_BEAM_DEPTHS: tuple[int, ...] = (17, 21, 27, 33, 42)

#: Maximum structure skew this standard applies to, degrees.
MAX_SKEW_DEG = 30.0


@dataclass(frozen=True)
class BoxBeamDesignSpec:
    """Design-stress and material specifications (PSBD-1-25 sheet 1/6).

    Concrete strengths are designer-selected ranges; the strand and
    reinforcing values are fixed by the standard.  Stresses in ksi.
    """

    #: Designer-selected 28-day concrete strength range, ksi.
    fc_28day_range: tuple[float, float] = (5.5, 7.0)
    #: Designer-selected release strength range, ksi.
    fci_release_range: tuple[float, float] = (4.0, 5.0)
    #: Cast-in-place (composite topping) concrete strength, ksi.
    fc_cast_in_place: float = 4.5
    #: Reinforcing steel minimum yield, ksi (C&MS 709.00).
    fy_reinforcing: float = 60.0
    #: Prestressing strand grade (ASTM A416, C&MS 711.27).
    strand_grade: int = 270
    #: Strand diameter, inches (0.5 in, 7-wire low-relaxation).
    strand_diameter: float = 0.5
    #: Nominal strand cross-sectional area options, in^2.
    strand_area_options: tuple[float, ...] = (0.153, 0.167)


#: Box-beam design/material specification (PSBD-1-25 sheet 1/6).
DESIGN_SPEC = BoxBeamDesignSpec()


@dataclass(frozen=True)
class TieRodDetail:
    """Transverse tie rod details (PSBD-1-25 sheets 1 & 4)."""

    diameter: float = 1.0           # in, ASTM A307 Grade 307A
    thread_root_min_diameter: float = 0.838  # in (rolled threads)
    torque_ft_lb: float = 250.0
    plate_washer: str = "4 x 4 x 1/2"
    hole_min_diameter: float = 2.0  # in
    hole_max_diameter: float = 3.0  # in
    max_beams_per_rod: int = 3

    def vertical_position(self, beam_depth: int) -> float:
        """Tie-rod height above the beam soffit, inches: 9 in for 17-27 in
        deep beams, 14 in for 33-42 in deep beams (sheet 4/6)."""
        if beam_depth not in BOX_BEAM_DEPTHS:
            raise ValueError(f"non-standard beam depth {beam_depth} in")
        return 9.0 if beam_depth <= 27 else 14.0


#: Transverse tie rod detail (PSBD-1-25).
TIE_ROD = TieRodDetail()


@dataclass(frozen=True)
class AnchorDowelDetail:
    """Anchor dowel details (PSBD-1-25 sheets 1 & 5)."""

    diameter: float = 1.0           # in, ASTM A311 Grade 1018 smooth rod
    beam_hole_diameter: float = 2.0  # in (2.5 in with compression seal joint)
    beam_hole_diameter_compression_seal: float = 2.5  # in (per EXJ-3-82)
    fixed_substructure_hole_min: float = 1.0625   # in (1-1/16)
    expansion_substructure_hole_min: float = 1.25  # in (1-1/4)


#: Anchor dowel detail (PSBD-1-25).
ANCHOR_DOWEL = AnchorDowelDetail()


@dataclass(frozen=True)
class ShearKeyDetail:
    """Shear-key details between adjacent box beams (PSBD-1-25 sheets 1 & 5)."""

    #: Grout fill depth from top of beam to bottom of throat, inches.
    grout_depth_from_top: float = 5.0
    #: Backer rod diameter for composite beams, inches (min).
    composite_backer_rod_min: float = 2.0
    #: End shear key depth at integral/semi-integral abutments, inches.
    end_shear_key_depth: float = 1.0
    #: End shear key width at integral/semi-integral abutments, inches.
    end_shear_key_width: float = 38.0


#: Shear-key detail (PSBD-1-25).
SHEAR_KEY = ShearKeyDetail()


def diaphragm_count(span_ft: float) -> int:
    """Number of intermediate diaphragms for a span, per PSBD-1-25 sheet 4/6:
    1 for spans <= 50 ft, 2 for 50 ft < span <= 75 ft, 3 for spans > 75 ft."""
    if span_ft <= 50.0:
        return 1
    if span_ft <= 75.0:
        return 2
    return 3


def diaphragm_end_offset(beam_depth: int) -> float:
    """Distance from beam end to the end diaphragm, inches (PSBD-1-25 sheet
    4/6): 24 in for 17/21 in deep beams, 30 in for 27/33/42 in deep beams."""
    if beam_depth not in BOX_BEAM_DEPTHS:
        raise ValueError(f"non-standard beam depth {beam_depth} in")
    return 24.0 if beam_depth <= 21 else 30.0


@dataclass(frozen=True)
class BearingPad:
    """A standard steel-reinforced elastomeric bearing pad (PSBD-1-25 sheet
    6/6 table).  Lengths in inches, load in kips, expansion length in feet."""

    name: str
    length: float           # L, in
    width: float            # W, in
    total_thickness: float  # T, in
    t_external: float       # te, in (external elastomer layer)
    t_internal: float       # ti, in (internal elastomer layer)
    t_steel: float          # ts, in (12 gage internal laminate)
    n_laminates: int        # N
    max_total_load: float   # kips
    max_expansion_length: float  # ft
    max_movement: float     # in (one direction)
    rotation_capacity: float = 0.024  # radians


#: Standard elastomeric bearing pads B1 and B2 (PSBD-1-25 sheet 6/6).
BEARING_PADS: dict[str, BearingPad] = {
    "B1": BearingPad("B1", 7.0, 11.0, 1.409, 0.35, 0.50, 0.1046, 2, 36.0,
                     92.0, 0.530),
    "B2": BearingPad("B2", 9.0, 14.0, 2.014, 0.35, 0.50, 0.1046, 3, 74.0,
                     147.0, 0.847),
}


@dataclass(frozen=True)
class BearingDesignData:
    """Elastomeric bearing design data (PSBD-1-25 sheet 6/6)."""

    durometer: int = 50
    #: Allowable compressive stress, ksi.
    allowable_compressive_stress: float = 1.25
    #: Shear modulus at 73 F for maximum compressive strength, ksi.
    shear_modulus_compressive: float = 0.095
    #: Shear modulus at 73 F for horizontal forces, ksi.
    shear_modulus_horizontal: float = 0.130
    #: 25-year creep deflection / instantaneous deflection, percent.
    creep_deflection_percent: float = 25.0
    #: Bearings required per beam.
    bearings_per_beam: int = 4
    #: Governing spec edition.
    spec_edition: str = "AASHTO LRFD BDS 10th Edition (2024)"


#: Elastomeric bearing design data (PSBD-1-25 sheet 6/6).
BEARING_DESIGN_DATA = BearingDesignData()


def bearing_pad(name: str) -> BearingPad:
    """Look up a standard bearing pad by name (``"B1"`` or ``"B2"``)."""
    return BEARING_PADS[name]
