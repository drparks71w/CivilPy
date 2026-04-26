#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
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

"""
Wood structural design per NDS (National Design Specification) 2024.

Provides section property lookups, NDS adjustment factor calculations,
member design checks (bending, shear, compression, tension, deflection),
timber bridge design per AASHTO LRFD, and bolted connection design.

References:
    - AWC, *National Design Specification (NDS) for Wood Construction*, 2024.
    - Breyer, D. et al., *Design of Wood Structures -- ASD/LRFD*, 8th Ed.
    - AASHTO LRFD Bridge Design Specifications, 9th Ed., Section 8 & 9.
    - USDA Forest Service, *Timber Bridge Design*, Construction, Inspection
      and Maintenance (LTRC/LTAP).
"""

import math
import os

import numpy as np
import pandas as pd

from civilpy.general import units

# ---------------------------------------------------------------------------
# Load CSV reference data
# ---------------------------------------------------------------------------
_res_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res")

_lumber_sizes = pd.read_csv(os.path.join(_res_dir, "lumber_sizes.csv"))
_wood_ref = pd.read_csv(os.path.join(_res_dir, "wood_reference_values.csv"))
_glulam_ref = pd.read_csv(os.path.join(_res_dir, "glulam_reference_values.csv"))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOAD_DURATION_FACTORS = {
    "permanent": 0.90,
    "normal": 1.00,
    "2_month": 1.15,
    "7_day": 1.25,
    "10_min": 1.60,
    "impact": 2.00,
}

TIMBER_BRIDGE_LOAD_COMBOS = {
    "Strength I": {"DC": 1.25, "DW": 1.50, "LL_IM": 1.75},
    "Strength II": {"DC": 1.25, "DW": 1.50, "LL_IM": 1.35},
    "Strength IV": {"DC": 1.50, "DW": 1.50, "LL_IM": 0.00},
    "Service I": {"DC": 1.00, "DW": 1.00, "LL_IM": 1.00},
    "Service III": {"DC": 1.00, "DW": 1.00, "LL_IM": 0.80},
}

WEARING_SURFACE_WEIGHTS = {
    "asphalt_2in": 18.0 * units("lbf/ft^2"),
    "asphalt_3in": 27.0 * units("lbf/ft^2"),
    "timber_plank_3in": 8.75 * units("lbf/ft^2"),
    "timber_plank_4in": 11.67 * units("lbf/ft^2"),
    "gravel_6in": 60.0 * units("lbf/ft^2"),
}

PRESERVATIVE_TREATMENT = {
    "CCA": {"incised": False, "retention_pcf": 0.60},
    "ACQ": {"incised": True, "retention_pcf": 0.40},
    "CA-C": {"incised": True, "retention_pcf": 0.21},
    "creosote": {"incised": False, "retention_pcf": 10.0},
    "penta": {"incised": False, "retention_pcf": 0.50},
}

# NDS Table 4.3.8 -- Incising factors
_INCISING_FACTORS = {
    "Fb": 0.80, "Ft": 0.80, "Fv": 0.80, "Fc_perp": 1.00,
    "Fc": 0.80, "E": 0.95, "Emin": 0.95,
}

# NDS Table N1 -- Format conversion factor KF (ASD -> LRFD)
_KF = {
    "Fb": 2.54, "Ft": 2.70, "Fv": 2.88, "Fc_perp": 1.67,
    "Fc": 2.40, "E": 1.00, "Emin": 1.76,
}

# NDS Table N2 -- Resistance factors phi (LRFD)
_PHI = {
    "Fb": 0.85, "Ft": 0.80, "Fv": 0.75, "Fc_perp": 0.90,
    "Fc": 0.90, "E": 1.00, "Emin": 0.85,
}

# NDS Table N3 -- Time effect factor lambda (LRFD)
_LAMBDA = {
    "permanent": 0.60,
    "normal": 0.80,
    "2_month": 0.80,
    "7_day": 0.80,
    "10_min": 1.00,
    "impact": 1.00,
}

# NDS Table 3.3.3 -- Effective length coefficients
_EFFECTIVE_LENGTH_COEFF = {
    "uniform": 1.63,
    "concentrated_center": 1.37,
    "concentrated_quarter": 1.10,
    "equal_end_moments": 1.84,
    "cantilever_uniform": 1.33,
    "cantilever_point": 1.87,
}

# NDS Table 4.3.1 -- Size factors CF for sawn lumber (Dimension lumber)
# Keys: (size_class, property) -> CF
# For 2x4: CF(Fb)=1.5, CF(Ft)=1.5, CF(Fc)=1.15
# For 2x6: CF(Fb)=1.3, CF(Ft)=1.3, CF(Fc)=1.1
# For 2x8: CF(Fb)=1.2, CF(Ft)=1.2, CF(Fc)=1.05
# For 2x10: CF(Fb)=1.1, CF(Ft)=1.1, CF(Fc)=1.0
# For 2x12: CF(Fb)=1.0, CF(Ft)=1.0, CF(Fc)=1.0
# For 2x14+: CF(Fb)=0.9, CF(Ft)=0.9, CF(Fc)=0.9
_SIZE_FACTORS = {
    ("2x4", "Fb"): 1.5, ("2x4", "Ft"): 1.5, ("2x4", "Fc"): 1.15,
    ("2x6", "Fb"): 1.3, ("2x6", "Ft"): 1.3, ("2x6", "Fc"): 1.1,
    ("2x8", "Fb"): 1.2, ("2x8", "Ft"): 1.2, ("2x8", "Fc"): 1.05,
    ("2x10", "Fb"): 1.1, ("2x10", "Ft"): 1.1, ("2x10", "Fc"): 1.0,
    ("2x12", "Fb"): 1.0, ("2x12", "Ft"): 1.0, ("2x12", "Fc"): 1.0,
    ("2x14", "Fb"): 0.9, ("2x14", "Ft"): 0.9, ("2x14", "Fc"): 0.9,
    ("2x16", "Fb"): 0.9, ("2x16", "Ft"): 0.9, ("2x16", "Fc"): 0.9,
}

# NDS Table 4.3.7 -- Flat use factors Cfu for sawn lumber (dimension)
_FLAT_USE_FACTORS = {
    "2x4": 1.10, "2x6": 1.15, "2x8": 1.15,
    "2x10": 1.20, "2x12": 1.20, "2x14": 1.20,
}


# ===================================================================
# Section Classes
# ===================================================================

class LumberSection:
    """Sawn lumber section with NDS reference design values.

    Looks up actual dimensions from the lumber sizes table and reference
    design values from the NDS Supplement tables.

    Args:
        nominal_width: Nominal width in inches (e.g. 2, 4, 6, 8).
        nominal_depth: Nominal depth in inches (e.g. 4, 6, 8, 10, 12).
        species: Species group (e.g. "Douglas Fir-Larch", "Southern Pine").
        grade: Lumber grade (e.g. "Select Structural", "No. 1", "No. 2").

    Example:
        >>> beam = LumberSection(6, 12, "Douglas Fir-Larch", "No. 1")
        >>> float(beam.b.magnitude)
        5.5
        >>> float(beam.d.magnitude)
        11.25
    """

    def __init__(self, nominal_width, nominal_depth, species, grade):
        self.nominal_width = nominal_width
        self.nominal_depth = nominal_depth
        self.species = species
        self.grade = grade
        self.member_type = "sawn_lumber"

        # Look up actual dimensions
        size_row = _lumber_sizes[
            (_lumber_sizes["Nominal_Width"] == nominal_width)
            & (_lumber_sizes["Nominal_Depth"] == nominal_depth)
        ]
        if size_row.empty:
            sizes = _lumber_sizes[['Nominal_Width','Nominal_Depth']].drop_duplicates()
            available = sorted(
                str(int(r.Nominal_Width)) + "x" + str(int(r.Nominal_Depth))
                for _, r in sizes.iterrows()
            )
            raise ValueError(
                f"No lumber size found for {nominal_width}x{nominal_depth}. "
                f"Available sizes: {available}"
            )
        row = size_row.iloc[0]
        self.b = row["Actual_Width"] * units("in")
        self.d = row["Actual_Depth"] * units("in")
        self.A = row["Area"] * units("in^2")
        self.Sx = row["Sx"] * units("in^3")
        self.Ix = row["Ix"] * units("in^4")
        self.Sy = row["Sy"] * units("in^3")
        self.Iy = row["Iy"] * units("in^4")
        self.rx = row["rx"] * units("in")
        self.ry = row["ry"] * units("in")

        # Determine NDS size classification for reference values
        self.size_class = self._determine_size_class()

        # Look up reference design values
        ref_row = _wood_ref[
            (_wood_ref["Species"] == species)
            & (_wood_ref["Grade"] == grade)
            & (_wood_ref["Size_Class"] == self.size_class)
        ]
        if ref_row.empty:
            available = _wood_ref[_wood_ref["Species"] == species][
                ["Grade", "Size_Class"]
            ].drop_duplicates()
            raise ValueError(
                f"No reference values for {species} / {grade} / {self.size_class}. "
                f"Available:\n{available.to_string(index=False)}"
            )
        ref = ref_row.iloc[0]
        self.Fb = ref["Fb"] * units("lbf/in^2")
        self.Ft = ref["Ft"] * units("lbf/in^2")
        self.Fv = ref["Fv"] * units("lbf/in^2")
        self.Fc_perp = ref["Fc_perp"] * units("lbf/in^2")
        self.Fc = ref["Fc"] * units("lbf/in^2")
        self.E = ref["E"] * units("lbf/in^2")
        self.Emin = ref["Emin"] * units("lbf/in^2")
        self.specific_gravity = ref["Specific_Gravity"]

        # Wet service factors stored per property
        self._CM = {
            "Fb": ref["CM_Fb"], "Ft": ref["CM_Ft"], "Fv": ref["CM_Fv"],
            "Fc_perp": ref["CM_Fc_perp"], "Fc": ref["CM_Fc"],
            "E": ref["CM_E"], "Emin": ref["CM_Emin"],
        }

        # Self-weight assuming 35 pcf for softwood
        density = 35.0 if self.specific_gravity < 0.55 else 50.0
        self.weight = (self.A.magnitude / 144.0) * density * units("lbf/ft")

    def _determine_size_class(self):
        nw, nd = self.nominal_width, self.nominal_depth
        if nw >= 5 and nd >= 5:
            # Beams & Stringers: width >= 5, depth > width + 2
            if nd > nw + 2:
                return "5x5_and_larger_B&S"
            else:
                return "5x5_and_larger_P&T"
        # Dimension lumber
        if nd == 4:
            return "2x4"
        if nw <= 4:
            # Individual sizes for CF lookup
            if nd <= 8:
                return f"2x{nd}" if nd == 6 else "2x6-2x8"
            elif nd <= 12:
                return f"2x{nd}" if nd == 10 else "2x10-2x12"
            else:
                return f"2x{nd}"
        # Fallback for CSV lookup (grouped)
        if nd <= 8:
            return "2x6-2x8"
        elif nd <= 12:
            return "2x10-2x12"
        return "2x10-2x12"

    def _cf_size_class(self):
        """Size class key for CF lookup."""
        nw, nd = self.nominal_width, self.nominal_depth
        if nw >= 5:
            return None  # B&S and P&T don't use CF table
        return f"2x{nd}"

    def __repr__(self):
        return (
            f"LumberSection({self.nominal_width}x{self.nominal_depth}, "
            f"{self.species}, {self.grade})"
        )


class GlulamSection:
    """Glued laminated timber section with NDS reference design values.

    Args:
        width: Actual width in inches (e.g. 5.125, 6.75, 8.75, 10.75).
        depth: Actual depth in inches.
        combination: Glulam combination symbol (e.g. "24F-V4", "20F-V7").
        species: Species group (e.g. "Douglas Fir", "Southern Pine").

    Example:
        >>> beam = GlulamSection(6.75, 30, "24F-V4", "Douglas Fir")
        >>> float(beam.Fb_pos.magnitude)
        2400.0
    """

    def __init__(self, width, depth, combination, species):
        self.width_val = width
        self.depth_val = depth
        self.combination = combination
        self.species = species
        self.member_type = "glulam"

        self.b = width * units("in")
        self.d = depth * units("in")
        self.A = width * depth * units("in^2")
        self.Sx = width * depth**2 / 6.0 * units("in^3")
        self.Ix = width * depth**3 / 12.0 * units("in^4")
        self.Sy = depth * width**2 / 6.0 * units("in^3")
        self.Iy = depth * width**3 / 12.0 * units("in^4")
        self.rx = (self.Ix / self.A) ** 0.5
        self.ry = (self.Iy / self.A) ** 0.5

        # Look up reference design values
        ref_row = _glulam_ref[
            (_glulam_ref["Combination"] == combination)
            & (_glulam_ref["Species"] == species)
        ]
        if ref_row.empty:
            available = _glulam_ref[["Combination", "Species"]].drop_duplicates()
            raise ValueError(
                f"No glulam values for {combination} / {species}. "
                f"Available:\n{available.to_string(index=False)}"
            )
        ref = ref_row.iloc[0]
        self.Fb_pos = ref["Fb_pos"] * units("lbf/in^2")
        self.Fb_neg = ref["Fb_neg"] * units("lbf/in^2")
        self.Fb = self.Fb_pos  # Default to positive face
        self.Ft = ref["Ft"] * units("lbf/in^2")
        self.Fv = ref["Fv"] * units("lbf/in^2")
        self.Fc_perp = ref["Fc_perp"] * units("lbf/in^2")
        self.Fc = ref["Fc"] * units("lbf/in^2")
        self.E = ref["E"] * units("lbf/in^2")
        self.Emin = ref["Emin"] * units("lbf/in^2")
        self.specific_gravity = 0.50  # Typical for DF glulam

        self._CM = {
            "Fb": ref["CM_Fb"], "Ft": ref["CM_Ft"], "Fv": ref["CM_Fv"],
            "Fc_perp": ref["CM_Fc_perp"], "Fc": ref["CM_Fc"],
            "E": ref["CM_E"], "Emin": ref["CM_Emin"],
        }

        # Self-weight at 35 pcf
        self.weight = (self.A.magnitude / 144.0) * 35.0 * units("lbf/ft")

    def __repr__(self):
        return (
            f"GlulamSection({self.width_val}x{self.depth_val}, "
            f"{self.combination}, {self.species})"
        )


# ===================================================================
# Adjustment Factors
# ===================================================================

class AdjustmentFactors:
    """NDS adjustment factor calculator.

    Computes all applicable adjustment factors for a wood member and
    returns adjusted design values. Works with both sawn lumber and
    glulam sections.

    Args:
        section: A LumberSection or GlulamSection instance.
        method: "ASD" or "LRFD". Default "ASD".
    """

    def __init__(self, section, method="ASD"):
        self.section = section
        self.method = method.upper()

    def CD(self, load_duration="normal"):
        """Load duration factor per NDS Table 2.3.2."""
        if load_duration not in LOAD_DURATION_FACTORS:
            raise ValueError(
                f"Unknown load duration '{load_duration}'. "
                f"Options: {list(LOAD_DURATION_FACTORS.keys())}"
            )
        return LOAD_DURATION_FACTORS[load_duration]

    def CM(self, prop, wet_service=False):
        """Wet service factor per NDS Table 4.3.3 / 5.3.3.

        Args:
            prop: Property name ("Fb", "Ft", "Fv", "Fc_perp", "Fc", "E", "Emin").
            wet_service: True if in-service moisture content > 19%.
        """
        if not wet_service:
            return 1.0
        return self.section._CM.get(prop, 1.0)

    def Ct(self, temperature_f, prop, wet_service=False):
        """Temperature factor per NDS Table 2.3.3.

        Args:
            temperature_f: Maximum sustained temperature in deg F.
            prop: Property name.
            wet_service: True if wet service conditions.
        """
        if temperature_f <= 100:
            return 1.0
        if prop in ("E", "Emin"):
            if temperature_f <= 125:
                return 0.90
            return 0.90  # >=125F
        if prop in ("Fb", "Ft", "Fv", "Fc"):
            if not wet_service:
                if temperature_f <= 125:
                    return 0.80
                return 0.70
            else:
                if temperature_f <= 125:
                    return 0.70
                return 0.50
        # Fc_perp
        if not wet_service:
            if temperature_f <= 125:
                return 0.80
            return 0.70
        if temperature_f <= 125:
            return 0.70
        return 0.50

    def CL(self, lu, load_type="uniform"):
        """Beam stability factor per NDS 3.3.3.

        Args:
            lu: Unbraced length (Pint length quantity). Use 0 if fully braced.
            load_type: Loading condition for effective length calculation.
        """
        lu_in = lu.to("in").magnitude
        if lu_in == 0:
            return 1.0

        d = self.section.d.to("in").magnitude
        b = self.section.b.to("in").magnitude

        le = effective_beam_length(lu, load_type).to("in").magnitude

        RB = math.sqrt(le * d / b**2)
        if RB > 50:
            raise ValueError(f"Slenderness ratio RB = {RB:.1f} > 50. Section is too slender.")

        # Need E'min for FbE
        Emin_val = self.section.Emin.to("lbf/in^2").magnitude
        FbE = 1.20 * Emin_val / RB**2

        # Fb* = Fb with all factors except CL and CV
        Fb_star = self.section.Fb.to("lbf/in^2").magnitude
        # (In a full check, Fb* includes CD*CM*Ct*CF*Ci*Cr, but for CL
        #  we need the ratio FbE/Fb* -- caller should pre-adjust Fb_star
        #  or we use the reference value as conservative approximation)

        return beam_stability_factor_from_ratio(FbE, Fb_star)

    def CF(self, prop="Fb"):
        """Size factor for sawn lumber per NDS Table 4.3.1.

        Returns 1.0 for glulam or Beams & Stringers / Posts & Timbers.
        """
        s = self.section
        if s.member_type == "glulam":
            return 1.0
        key = s._cf_size_class()
        if key is None:
            return 1.0  # B&S, P&T -- CF = 1.0 (already in tabulated values)
        return _SIZE_FACTORS.get((key, prop), 1.0)

    def Ci(self, prop, incised=False):
        """Incising factor per NDS Table 4.3.8."""
        if not incised:
            return 1.0
        return _INCISING_FACTORS.get(prop, 1.0)

    def Cr(self, repetitive=False):
        """Repetitive member factor. 1.15 if 3+ members <= 12 in. deep, spaced <= 24 in. o.c."""
        if not repetitive:
            return 1.0
        return 1.15

    def Cp(self, le, axis="strong"):
        """Column stability factor per NDS 3.7.1.

        Args:
            le: Effective column length (Pint length quantity).
            axis: "strong" or "weak" buckling axis.
        """
        s = self.section
        d_dim = s.d.to("in").magnitude if axis == "strong" else s.b.to("in").magnitude
        le_in = le.to("in").magnitude
        slenderness = le_in / d_dim

        if slenderness > 50:
            raise ValueError(f"le/d = {slenderness:.1f} > 50 limit per NDS 3.7.1.4.")

        Emin_val = s.Emin.to("lbf/in^2").magnitude
        FcE = euler_critical_buckling_stress_val(Emin_val, le_in, d_dim)

        Fc_star = s.Fc.to("lbf/in^2").magnitude
        c = 0.9 if s.member_type == "glulam" else 0.8

        return column_stability_factor(FcE, Fc_star, c)

    def Cb(self, bearing_length):
        """Bearing area factor per NDS 3.10.4.

        Args:
            bearing_length: Length of bearing along grain (Pint length).
        """
        lb = bearing_length.to("in").magnitude
        if lb >= 6.0:
            return 1.0
        if lb < 0.5:
            lb = 0.5
        return (lb + 0.375) / lb

    def CV(self, L=None):
        """Volume factor for glulam per NDS 5.3.6.

        CV = (21/L)^(1/x) * (12/d)^(1/x) * (5.125/b)^(1/x)
        where x = 10 for Western Species, x = 10 for Southern Pine.

        Args:
            L: Span length in feet (Pint length). Required for glulam.
        """
        s = self.section
        if s.member_type != "glulam":
            return 1.0
        if L is None:
            return 1.0
        L_ft = L.to("ft").magnitude
        d_in = s.d.to("in").magnitude
        b_in = s.b.to("in").magnitude
        x = 10
        cv = (21.0 / L_ft) ** (1.0 / x) * (12.0 / d_in) ** (1.0 / x) * (5.125 / b_in) ** (1.0 / x)
        return min(cv, 1.0)

    def Cfu(self, flat_use=False):
        """Flat use factor per NDS Table 4.3.7."""
        if not flat_use:
            return 1.0
        s = self.section
        if s.member_type == "glulam":
            return 1.0  # Glulam flat use handled differently
        key = s._cf_size_class()
        if key is None:
            return 1.0
        return _FLAT_USE_FACTORS.get(key, 1.0)

    def KF(self, prop):
        """Format conversion factor (LRFD) per NDS Table N1."""
        if self.method != "LRFD":
            return 1.0
        return _KF.get(prop, 1.0)

    def phi(self, prop):
        """Resistance factor (LRFD) per NDS Table N2."""
        if self.method != "LRFD":
            return 1.0
        return _PHI.get(prop, 1.0)

    def lam(self, load_duration="normal"):
        """Time effect factor (LRFD) per NDS Table N3."""
        if self.method != "LRFD":
            return 1.0
        return _LAMBDA.get(load_duration, 0.80)

    def adjusted_value(self, prop, load_duration="normal", wet_service=False,
                       temperature_f=100.0, incised=False, repetitive=False,
                       lu=None, le_col=None, bearing_length=None,
                       flat_use=False, span_length=None, load_type="uniform"):
        """Compute the fully adjusted design value F' for a given property.

        Args:
            prop: Property name ("Fb", "Ft", "Fv", "Fc_perp", "Fc", "E", "Emin").
            load_duration: Load duration case name.
            wet_service: True if MC > 19%.
            temperature_f: Max sustained temperature (deg F).
            incised: True if incised for treatment.
            repetitive: True if repetitive member.
            lu: Unbraced length for CL (bending only).
            le_col: Effective column length for Cp (compression only).
            bearing_length: Bearing length for Cb (Fc_perp only).
            flat_use: True if loaded on flat face.
            span_length: Span length for CV (glulam bending only).
            load_type: Loading type for CL calculation.

        Returns:
            dict: {"value": adjusted Pint quantity, "factors": dict of factor names->values}
        """
        ref_val = getattr(self.section, prop)
        factors = {}

        # CD -- applies to all except E, Emin, Fc_perp
        if prop not in ("E", "Emin", "Fc_perp"):
            factors["CD"] = self.CD(load_duration)
        # CM
        factors["CM"] = self.CM(prop, wet_service)
        # Ct
        factors["Ct"] = self.Ct(temperature_f, prop, wet_service)
        # Ci
        factors["Ci"] = self.Ci(prop, incised)

        # Property-specific factors
        if prop == "Fb":
            factors["CF"] = self.CF("Fb")
            if repetitive:
                factors["Cr"] = self.Cr(True)
            if flat_use:
                factors["Cfu"] = self.Cfu(True)
            # CL and CV -- for glulam, use lesser of CL and CV (not both)
            if self.section.member_type == "glulam":
                cl = self.CL(lu or 0 * units("in"), load_type) if lu else 1.0
                cv = self.CV(span_length)
                # NDS 5.3.6: use lesser of CL and CV, not both
                if cl < cv:
                    factors["CL"] = cl
                else:
                    factors["CV"] = cv
            else:
                if lu is not None:
                    factors["CL"] = self.CL(lu, load_type)

        elif prop == "Ft":
            factors["CF"] = self.CF("Ft")

        elif prop == "Fc":
            factors["CF"] = self.CF("Fc")
            if le_col is not None:
                # For Cp, Fc* = Fc * all factors except Cp
                factors["Cp"] = self.Cp(le_col)

        elif prop == "Fc_perp":
            if bearing_length is not None:
                factors["Cb"] = self.Cb(bearing_length)

        # LRFD factors
        if self.method == "LRFD":
            factors["KF"] = self.KF(prop)
            factors["phi"] = self.phi(prop)
            if prop not in ("E", "Emin", "Fc_perp"):
                factors["lambda"] = self.lam(load_duration)

        # Compute product
        product = 1.0
        for v in factors.values():
            product *= v

        adjusted = ref_val * product
        return {"value": adjusted, "factors": factors}


# ===================================================================
# Standalone Helper Functions
# ===================================================================

def euler_critical_buckling_stress_val(Emin_prime, le_in, d_in):
    """FcE = 0.822 * E'min / (le/d)^2 per NDS 3.7.1.5.

    All arguments are raw numeric values in psi / inches.
    """
    ratio = le_in / d_in
    if ratio == 0:
        return float("inf")
    return 0.822 * Emin_prime / ratio**2


def euler_critical_buckling_stress(Emin_prime, le, d):
    """FcE per NDS 3.7.1.5 with Pint quantities.

    Args:
        Emin_prime: Adjusted minimum modulus of elasticity (Pint stress).
        le: Effective column length (Pint length).
        d: Member dimension in buckling plane (Pint length).

    Returns:
        Pint stress quantity.
    """
    Emin_val = Emin_prime.to("lbf/in^2").magnitude
    le_val = le.to("in").magnitude
    d_val = d.to("in").magnitude
    return euler_critical_buckling_stress_val(Emin_val, le_val, d_val) * units("lbf/in^2")


def column_stability_factor(FcE, Fc_star, c=0.8):
    """Cp per NDS Eq. 3.7-1.

    Args:
        FcE: Euler critical buckling stress (numeric, psi).
        Fc_star: Fc multiplied by all adjustment factors except Cp (numeric, psi).
        c: 0.8 for sawn lumber, 0.9 for glulam, 0.85 for round timber.

    Returns:
        float: Column stability factor Cp.
    """
    if Fc_star == 0:
        return 0.0
    ratio = FcE / Fc_star
    a = (1 + ratio) / (2 * c)
    return a - math.sqrt(a**2 - ratio / c)


def effective_beam_length(lu, load_type="uniform"):
    """Effective unbraced length le for lateral-torsional buckling.

    Per NDS Table 3.3.3.

    Args:
        lu: Unbraced length (Pint length quantity).
        load_type: One of "uniform", "concentrated_center",
            "concentrated_quarter", "equal_end_moments",
            "cantilever_uniform", "cantilever_point".

    Returns:
        Pint length quantity.
    """
    coeff = _EFFECTIVE_LENGTH_COEFF.get(load_type, 1.63)
    return coeff * lu


def beam_stability_factor_from_ratio(FbE, Fb_star):
    """CL per NDS 3.3.3.8.

    Same form as Cp but with c=0.95 for beams.

    Args:
        FbE: Critical buckling stress (numeric, psi).
        Fb_star: Fb times all factors except CL and CV (numeric, psi).

    Returns:
        float: Beam stability factor CL.
    """
    if Fb_star == 0:
        return 0.0
    ratio = FbE / Fb_star
    a = (1 + ratio) / 1.9  # 2*c where c=0.95
    return a - math.sqrt(a**2 - ratio / 0.95)


def beam_stability_factor(Emin_prime, Fb_star, le, d, b):
    """CL per NDS 3.3.3 with Pint quantities.

    Args:
        Emin_prime: Adjusted E'min (Pint stress).
        Fb_star: Fb * (all factors except CL and CV) (Pint stress).
        le: Effective unbraced length (Pint length).
        d: Depth (Pint length).
        b: Width (Pint length).

    Returns:
        float: CL.
    """
    le_in = le.to("in").magnitude
    d_in = d.to("in").magnitude
    b_in = b.to("in").magnitude
    Emin_val = Emin_prime.to("lbf/in^2").magnitude
    Fb_val = Fb_star.to("lbf/in^2").magnitude

    RB = math.sqrt(le_in * d_in / b_in**2)
    if RB > 50:
        raise ValueError(f"RB = {RB:.1f} exceeds 50 limit.")
    FbE = 1.20 * Emin_val / RB**2
    return beam_stability_factor_from_ratio(FbE, Fb_val)


# ===================================================================
# Member Design Check
# ===================================================================

class WoodMemberCheck:
    """Complete NDS member design check with calc-sheet output.

    Orchestrates adjustment factor computation and demand/capacity checks
    for all stress types. Each check returns a dict of intermediate values
    suitable for display in a Jupyter notebook.

    Args:
        section: LumberSection or GlulamSection.
        method: "ASD" or "LRFD".
        wet_service: True if in-service MC > 19%.
        temperature_f: Maximum sustained temperature (deg F).
        incised: True if incised for preservative treatment.
        repetitive: True if repetitive member conditions apply.
        load_duration: Governing load duration case.
    """

    def __init__(self, section, method="ASD", wet_service=False,
                 temperature_f=100.0, incised=False, repetitive=False,
                 load_duration="normal"):
        self.section = section
        self.af = AdjustmentFactors(section, method)
        self.method = method.upper()
        self.wet_service = wet_service
        self.temperature_f = temperature_f
        self.incised = incised
        self.repetitive = repetitive
        self.load_duration = load_duration
        self._results = {}

    def check_bending(self, M, lu=None, load_type="uniform", span_length=None):
        """Bending stress check.

        Args:
            M: Applied moment (Pint moment quantity, e.g. ft*lbf or in*lbf).
            lu: Unbraced length (Pint length). 0 or None = fully braced.
            load_type: Loading type for effective length.
            span_length: Span for CV (glulam only).

        Returns:
            dict with fb, Fb_prime, ratio, status, factors.
        """
        s = self.section
        M_in = M.to("lbf*in")
        fb = (M_in / s.Sx).to("lbf/in^2")

        adj = self.af.adjusted_value(
            "Fb", self.load_duration, self.wet_service,
            self.temperature_f, self.incised, self.repetitive,
            lu=lu, load_type=load_type, span_length=span_length,
        )
        Fb_prime = adj["value"].to("lbf/in^2")

        ratio = fb.magnitude / Fb_prime.magnitude
        result = {
            "fb": fb, "Fb_prime": Fb_prime, "ratio": round(ratio, 3),
            "status": "OK" if ratio <= 1.0 else "NG",
            "factors": adj["factors"],
        }
        self._results["bending"] = result
        return result

    def check_shear(self, V):
        """Shear stress check (fv = 3V/2A per NDS 3.4.2).

        Args:
            V: Applied shear force (Pint force quantity).

        Returns:
            dict with fv, Fv_prime, ratio, status, factors.
        """
        s = self.section
        fv = (1.5 * V / s.A).to("lbf/in^2")

        adj = self.af.adjusted_value(
            "Fv", self.load_duration, self.wet_service,
            self.temperature_f, self.incised,
        )
        Fv_prime = adj["value"].to("lbf/in^2")

        ratio = fv.magnitude / Fv_prime.magnitude
        result = {
            "fv": fv, "Fv_prime": Fv_prime, "ratio": round(ratio, 3),
            "status": "OK" if ratio <= 1.0 else "NG",
            "factors": adj["factors"],
        }
        self._results["shear"] = result
        return result

    def check_compression(self, P, le_strong, le_weak=None):
        """Compression parallel to grain check.

        Args:
            P: Applied axial compression (Pint force).
            le_strong: Effective length about strong axis (Pint length).
            le_weak: Effective length about weak axis (defaults to le_strong).

        Returns:
            dict with fc, Fc_prime, ratio, status, Cp, le_d, factors.
        """
        s = self.section
        if le_weak is None:
            le_weak = le_strong

        fc = (P / s.A).to("lbf/in^2")

        # Check both axes and use the governing (lower Cp)
        le_d_strong = le_strong.to("in").magnitude / s.d.to("in").magnitude
        le_d_weak = le_weak.to("in").magnitude / s.b.to("in").magnitude
        governing_le = le_strong if le_d_strong >= le_d_weak else le_weak

        adj = self.af.adjusted_value(
            "Fc", self.load_duration, self.wet_service,
            self.temperature_f, self.incised,
            le_col=governing_le,
        )
        Fc_prime = adj["value"].to("lbf/in^2")

        ratio = fc.magnitude / Fc_prime.magnitude
        result = {
            "fc": fc, "Fc_prime": Fc_prime, "ratio": round(ratio, 3),
            "status": "OK" if ratio <= 1.0 else "NG",
            "le_d_strong": round(le_d_strong, 1),
            "le_d_weak": round(le_d_weak, 1),
            "Cp": adj["factors"].get("Cp", 1.0),
            "factors": adj["factors"],
        }
        self._results["compression"] = result
        return result

    def check_bearing(self, R, bearing_length, bearing_width=None):
        """Compression perpendicular to grain (bearing) check.

        Args:
            R: Applied bearing reaction (Pint force).
            bearing_length: Length of bearing along grain (Pint length).
            bearing_width: Width of bearing (Pint length). Defaults to section width.

        Returns:
            dict with fc_perp, Fc_perp_prime, ratio, status, factors.
        """
        s = self.section
        if bearing_width is None:
            bearing_width = s.b

        bearing_area = (bearing_length * bearing_width).to("in^2")
        fc_perp = (R / bearing_area).to("lbf/in^2")

        adj = self.af.adjusted_value(
            "Fc_perp", self.load_duration, self.wet_service,
            self.temperature_f, self.incised,
            bearing_length=bearing_length,
        )
        Fc_perp_prime = adj["value"].to("lbf/in^2")

        ratio = fc_perp.magnitude / Fc_perp_prime.magnitude
        result = {
            "fc_perp": fc_perp, "Fc_perp_prime": Fc_perp_prime,
            "ratio": round(ratio, 3),
            "status": "OK" if ratio <= 1.0 else "NG",
            "factors": adj["factors"],
        }
        self._results["bearing"] = result
        return result

    def check_tension(self, T):
        """Tension parallel to grain check.

        Args:
            T: Applied tension force (Pint force).

        Returns:
            dict with ft, Ft_prime, ratio, status, factors.
        """
        s = self.section
        ft = (T / s.A).to("lbf/in^2")

        adj = self.af.adjusted_value(
            "Ft", self.load_duration, self.wet_service,
            self.temperature_f, self.incised,
        )
        Ft_prime = adj["value"].to("lbf/in^2")

        ratio = ft.magnitude / Ft_prime.magnitude
        result = {
            "ft": ft, "Ft_prime": Ft_prime, "ratio": round(ratio, 3),
            "status": "OK" if ratio <= 1.0 else "NG",
            "factors": adj["factors"],
        }
        self._results["tension"] = result
        return result

    def check_deflection(self, w, L, limit="L/360", I_eff=None):
        """Deflection check for uniform load on simple span.

        delta = 5*w*L^4 / (384*E'*I)

        Args:
            w: Uniform load (Pint force/length, e.g. lbf/ft).
            L: Span length (Pint length).
            limit: Deflection limit as string (e.g. "L/360", "L/240", "L/425").
            I_eff: Override moment of inertia. Defaults to section Ix.

        Returns:
            dict with delta, delta_limit, ratio, status.
        """
        s = self.section
        I = I_eff if I_eff is not None else s.Ix

        # Adjusted E
        adj_E = self.af.adjusted_value(
            "E", self.load_duration, self.wet_service,
            self.temperature_f, self.incised,
        )
        E_prime = adj_E["value"]

        w_in = w.to("lbf/in")
        L_in = L.to("in")
        I_in = I.to("in^4")

        delta = (5.0 * w_in * L_in**4 / (384.0 * E_prime * I_in)).to("in")

        # Parse limit
        parts = limit.split("/")
        denom = float(parts[1])
        delta_limit = (L_in / denom).to("in")

        ratio = abs(delta.magnitude) / delta_limit.magnitude
        result = {
            "delta": delta, "delta_limit": delta_limit,
            "ratio": round(ratio, 3),
            "status": "OK" if ratio <= 1.0 else "NG",
            "E_prime": E_prime,
        }
        self._results["deflection"] = result
        return result

    def check_combined_bending_compression(self, P, M, le_strong, le_weak=None,
                                           lu=None, load_type="uniform"):
        """Combined bending and axial compression per NDS Eq. 3.9-3.

        (fc/Fc')^2 + fb / (Fb' * (1 - fc/FcE)) <= 1.0

        Args:
            P: Axial compression (Pint force).
            M: Bending moment (Pint moment).
            le_strong: Effective column length, strong axis.
            le_weak: Effective column length, weak axis.
            lu: Unbraced length for bending.
            load_type: Loading type for CL.

        Returns:
            dict with interaction ratio and components.
        """
        comp = self.check_compression(P, le_strong, le_weak)
        bend = self.check_bending(M, lu, load_type)

        fc = comp["fc"].to("lbf/in^2").magnitude
        Fc_prime = comp["Fc_prime"].to("lbf/in^2").magnitude
        fb = bend["fb"].to("lbf/in^2").magnitude
        Fb_prime = bend["Fb_prime"].to("lbf/in^2").magnitude

        # FcE for the bending plane
        d_in = self.section.d.to("in").magnitude
        le_in = le_strong.to("in").magnitude
        Emin_val = self.section.Emin.to("lbf/in^2").magnitude
        FcE1 = euler_critical_buckling_stress_val(Emin_val, le_in, d_in)

        denom = 1 - fc / FcE1 if FcE1 != 0 else 1.0
        if denom <= 0:
            denom = 0.001  # Buckling failure

        interaction = (fc / Fc_prime) ** 2 + fb / (Fb_prime * denom)

        result = {
            "interaction_ratio": round(interaction, 3),
            "status": "OK" if interaction <= 1.0 else "NG",
            "compression_term": round((fc / Fc_prime) ** 2, 3),
            "bending_term": round(fb / (Fb_prime * denom), 3),
            "FcE1": FcE1 * units("lbf/in^2"),
        }
        self._results["combined"] = result
        return result

    def summary(self):
        """Return a DataFrame summarizing all checks performed.

        Returns:
            pd.DataFrame with columns: Check, Demand, Capacity, Ratio, Status.
        """
        rows = []
        for check_name, result in self._results.items():
            if check_name == "bending":
                rows.append({
                    "Check": "Bending",
                    "Demand": f"{result['fb']:.1f}",
                    "Capacity": f"{result['Fb_prime']:.1f}",
                    "D/C Ratio": result["ratio"],
                    "Status": result["status"],
                })
            elif check_name == "shear":
                rows.append({
                    "Check": "Shear",
                    "Demand": f"{result['fv']:.1f}",
                    "Capacity": f"{result['Fv_prime']:.1f}",
                    "D/C Ratio": result["ratio"],
                    "Status": result["status"],
                })
            elif check_name == "compression":
                rows.append({
                    "Check": "Compression",
                    "Demand": f"{result['fc']:.1f}",
                    "Capacity": f"{result['Fc_prime']:.1f}",
                    "D/C Ratio": result["ratio"],
                    "Status": result["status"],
                })
            elif check_name == "bearing":
                rows.append({
                    "Check": "Bearing",
                    "Demand": f"{result['fc_perp']:.1f}",
                    "Capacity": f"{result['Fc_perp_prime']:.1f}",
                    "D/C Ratio": result["ratio"],
                    "Status": result["status"],
                })
            elif check_name == "tension":
                rows.append({
                    "Check": "Tension",
                    "Demand": f"{result['ft']:.1f}",
                    "Capacity": f"{result['Ft_prime']:.1f}",
                    "D/C Ratio": result["ratio"],
                    "Status": result["status"],
                })
            elif check_name == "deflection":
                rows.append({
                    "Check": "Deflection",
                    "Demand": f"{result['delta']:.3f}",
                    "Capacity": f"{result['delta_limit']:.3f}",
                    "D/C Ratio": result["ratio"],
                    "Status": result["status"],
                })
            elif check_name == "combined":
                rows.append({
                    "Check": "Combined Bending+Compression",
                    "Demand": f"{result['interaction_ratio']:.3f}",
                    "Capacity": "1.000",
                    "D/C Ratio": result["interaction_ratio"],
                    "Status": result["status"],
                })
        return pd.DataFrame(rows)


# ===================================================================
# Timber Bridge Design (AASHTO LRFD)
# ===================================================================

class TimberBridgeDeck:
    """Timber bridge deck design per AASHTO LRFD Section 9.9.

    Args:
        deck_type: "nail_laminated", "spike_laminated", "glulam",
            "stress_laminated", or "plank".
        span: Clear span of deck panel (Pint length).
        thickness: Deck lamination depth (Pint length).
        species: Wood species group.
        grade: Lumber grade.
        wearing_surface: Key from WEARING_SURFACE_WEIGHTS or "none".
    """

    def __init__(self, deck_type, span, thickness, species, grade,
                 wearing_surface="none"):
        self.deck_type = deck_type
        self.span = span
        self.thickness = thickness
        self.species = species
        self.grade = grade
        self.wearing_surface = wearing_surface

        # Build a 1-ft-wide strip section for deck analysis
        # For nail-laminated decks, the laminations are on edge so
        # depth = lamination width, width = 12 in. (1 ft strip)
        t_in = thickness.to("in").magnitude
        self.strip_width = 12.0 * units("in")
        self.strip_A = 12.0 * t_in * units("in^2")
        self.strip_Sx = 12.0 * t_in**2 / 6.0 * units("in^3")
        self.strip_Ix = 12.0 * t_in**3 / 12.0 * units("in^4")

        # Look up reference values using a dummy section
        # Use the smallest dimension class for lookup
        nw = max(2, int(round(t_in)))
        if nw in (2, 3, 4):
            nom_w = nw
        else:
            nom_w = int(round(t_in))
        # For deck laminations we just need the material properties
        self._ref_section = LumberSection(nom_w, max(nom_w + 2, 6), species, grade)

        if wearing_surface != "none" and wearing_surface in WEARING_SURFACE_WEIGHTS:
            self.ws_weight = WEARING_SURFACE_WEIGHTS[wearing_surface]
        else:
            self.ws_weight = 0.0 * units("lbf/ft^2")

    def wheel_load_distribution_width(self, tire_contact_width=None):
        """Effective width for wheel load distribution per AASHTO 4.6.2.1.3.

        For transverse nail-laminated decks:
            E = 2.0 * t + 40 (in.)  (approximate, perpendicular to span)

        Args:
            tire_contact_width: Tire contact length (Pint length).
                Defaults to 20 in. per AASHTO 3.6.1.2.5.

        Returns:
            Pint length quantity: Effective distribution width.
        """
        if tire_contact_width is None:
            tire_contact_width = 20.0 * units("in")

        t_in = self.thickness.to("in").magnitude
        S_ft = self.span.to("ft").magnitude

        if self.deck_type in ("nail_laminated", "spike_laminated"):
            # AASHTO Table 4.6.2.1.3-1 for transverse wood decks
            # Perpendicular to span: E = 15.0 + 2.0*S (inches), S in feet
            E = (15.0 + 2.0 * S_ft) * units("in")
            return min(E, self.span)
        elif self.deck_type == "glulam":
            E = (15.0 + 2.5 * S_ft) * units("in")
            return min(E, self.span)
        elif self.deck_type == "stress_laminated":
            E = (15.0 + 2.0 * S_ft) * units("in")
            return min(E, self.span)
        else:  # plank
            E = tire_contact_width + 2.0 * self.thickness
            return E

    def dead_load_per_ft(self):
        """Dead load on a 1-ft-wide strip (lbf/ft).

        Returns:
            Pint force/length quantity.
        """
        # Deck self-weight
        t_ft = self.thickness.to("ft").magnitude
        deck_weight = t_ft * 50.0 * units("lbf/ft^2")  # 50 pcf for treated timber
        # Wearing surface
        total = deck_weight + self.ws_weight
        # Convert to lbf/ft for a 1-ft strip
        return total.to("lbf/ft^2") * 1.0 * units("ft")

    def check_deck(self):
        """Full deck adequacy check under AASHTO HL-93 wheel load.

        Uses a 16-kip wheel load (half of 32-kip axle) distributed
        over the effective width.

        Returns:
            dict with bending, shear, and deflection check results.
        """
        S = self.span
        E_dist = self.wheel_load_distribution_width()

        # HL-93 design truck wheel load = 16 kips
        P_wheel = 16.0 * units("kip")
        IM = 0.33  # Dynamic load allowance

        # Wheel load per foot width of deck
        w_ll = P_wheel * (1 + IM) / E_dist.to("ft")

        # Dead load
        w_dl = self.dead_load_per_ft()

        # Moments (simple span)
        # For concentrated load at midspan: M = PL/4
        # Approximate as equivalent uniform for combined check
        M_dl = w_dl * S**2 / 8.0
        M_ll = P_wheel * (1 + IM) * S / (4.0 * E_dist.to("ft") / (1.0 * units("ft")))

        # Factored moment (Strength I)
        M_str1 = 1.25 * M_dl + 1.75 * M_ll

        # Shear
        V_dl = w_dl * S / 2.0
        V_ll = P_wheel * (1 + IM) / (2.0 * E_dist.to("ft") / (1.0 * units("ft")))
        V_str1 = 1.25 * V_dl + 1.75 * V_ll

        # Check stresses on 1-ft strip
        fb = (M_str1.to("lbf*in") / self.strip_Sx).to("lbf/in^2")
        fv = (1.5 * V_str1 / self.strip_A).to("lbf/in^2")

        # Adjusted capacities
        af = AdjustmentFactors(self._ref_section, self.method if hasattr(self, 'method') else "ASD")
        Fb_adj = af.adjusted_value("Fb", "normal", wet_service=True, incised=True)
        Fv_adj = af.adjusted_value("Fv", "normal", wet_service=True, incised=True)
        E_adj = af.adjusted_value("E", "normal", wet_service=True, incised=True)

        Fb_prime = Fb_adj["value"].to("lbf/in^2")
        Fv_prime = Fv_adj["value"].to("lbf/in^2")
        E_prime = E_adj["value"]

        # Deflection (Service I, LL only)
        # Approximate: delta = PL^3/(48*E*I) for midspan point load
        L_in = S.to("in")
        delta = (P_wheel * (1 + IM) * L_in**3 / (
            48.0 * E_prime * self.strip_Ix * E_dist.to("in") / (1.0 * units("in"))
        )).to("in")
        delta_limit = L_in / 425.0

        return {
            "bending": {
                "fb": fb, "Fb_prime": Fb_prime,
                "ratio": round(fb.magnitude / Fb_prime.magnitude, 3),
                "status": "OK" if fb.magnitude <= Fb_prime.magnitude else "NG",
            },
            "shear": {
                "fv": fv, "Fv_prime": Fv_prime,
                "ratio": round(fv.magnitude / Fv_prime.magnitude, 3),
                "status": "OK" if fv.magnitude <= Fv_prime.magnitude else "NG",
            },
            "deflection": {
                "delta": delta, "delta_limit": delta_limit,
                "ratio": round(abs(delta.magnitude) / delta_limit.magnitude, 3),
                "status": "OK" if abs(delta.magnitude) <= delta_limit.magnitude else "NG",
            },
            "distribution_width": E_dist,
            "M_strength_I": M_str1,
            "V_strength_I": V_str1,
        }


class TimberStringer:
    """Timber bridge stringer design per AASHTO LRFD.

    Args:
        section: LumberSection or GlulamSection for the stringer.
        span: Stringer span (Pint length).
        spacing: Stringer center-to-center spacing (Pint length).
        num_lanes: Number of design lanes.
        deck_type: Type of deck supported.
    """

    def __init__(self, section, span, spacing, num_lanes=1,
                 deck_type="nail_laminated"):
        self.section = section
        self.span = span
        self.spacing = spacing
        self.num_lanes = num_lanes
        self.deck_type = deck_type

    def live_load_distribution_factor(self, num_stringers=5):
        """Live load distribution factor for moment per AASHTO Table 4.6.2.2.2a-1.

        Simplified method for timber beam/slab bridges.
        For one design lane loaded: g = S/D
        where S = spacing (ft), D depends on bridge type.

        Args:
            num_stringers: Total number of stringers.

        Returns:
            float: Distribution factor (lanes per beam).
        """
        S_ft = self.spacing.to("ft").magnitude

        if self.deck_type in ("nail_laminated", "spike_laminated"):
            # AASHTO Table 4.6.2.2.2a-1
            # Wood beams with transverse nail-laminated deck
            # One lane loaded: g = S/6.0 (ft)
            # Two+ lanes loaded: g = S/5.0 (ft)
            if self.num_lanes == 1:
                g = S_ft / 6.0
            else:
                g = S_ft / 5.0
        elif self.deck_type == "glulam":
            if self.num_lanes == 1:
                g = S_ft / 6.5
            else:
                g = S_ft / 5.5
        elif self.deck_type == "stress_laminated":
            if self.num_lanes == 1:
                g = S_ft / 7.0
            else:
                g = S_ft / 5.5
        elif self.deck_type == "plank":
            if self.num_lanes == 1:
                g = S_ft / 4.0
            else:
                g = S_ft / 3.5
        else:
            g = S_ft / 5.0

        # Apply multiple presence factor limits
        return round(g, 3)

    def live_load_distribution_factor_shear(self, num_stringers=5):
        """Live load distribution factor for shear.

        Conservatively uses the moment distribution factor (AASHTO allows
        this simplification for timber bridges).
        """
        return self.live_load_distribution_factor(num_stringers)

    def dynamic_load_allowance(self):
        """Dynamic load allowance (IM) per AASHTO 3.6.2.3.

        Returns 0.33 for timber bridges (same as other materials).
        Note: Some agencies reduce IM for timber. AASHTO does not
        distinguish by material.
        """
        return 0.33

    def rating_factor(self, DC_moment, DW_moment, LL_moment,
                      capacity_moment, gamma_DC=1.25, gamma_DW=1.50,
                      gamma_LL=1.75, phi_c=1.0, phi_s=1.0):
        """Load rating factor per AASHTO MBE Eq. 6A.4.2.1-1.

        RF = (phi_c * phi_s * C - gamma_DC * DC - gamma_DW * DW) /
             (gamma_LL * LL * (1 + IM))

        Args:
            DC_moment: Dead load moment (Pint moment).
            DW_moment: Wearing surface moment (Pint moment).
            LL_moment: Live load moment per stringer (Pint moment, without IM).
            capacity_moment: Member capacity M = Fb' * Sx (Pint moment).
            gamma_DC: DC load factor.
            gamma_DW: DW load factor.
            gamma_LL: LL load factor.
            phi_c: Condition factor (1.0, 0.85, or 0.65).
            phi_s: System factor (1.0 for most timber).

        Returns:
            dict with RF, numerator, denominator, and status.
        """
        IM = self.dynamic_load_allowance()

        C = capacity_moment.to("lbf*in").magnitude
        DC = DC_moment.to("lbf*in").magnitude
        DW = DW_moment.to("lbf*in").magnitude
        LL = LL_moment.to("lbf*in").magnitude

        numerator = phi_c * phi_s * C - gamma_DC * DC - gamma_DW * DW
        denominator = gamma_LL * LL * (1 + IM)

        if denominator == 0:
            RF = float("inf")
        else:
            RF = numerator / denominator

        return {
            "RF": round(RF, 3),
            "numerator": numerator * units("lbf*in"),
            "denominator": denominator * units("lbf*in"),
            "status": "ADEQUATE" if RF >= 1.0 else "INADEQUATE",
            "IM": IM,
        }


# ===================================================================
# Connection Design (NDS Chapter 12)
# ===================================================================

class BoltConnection:
    """Bolted connection design per NDS Chapter 12.

    Computes reference lateral design values using the yield mode
    equations and applies NDS adjustment factors.

    Args:
        bolt_diameter: Bolt diameter (Pint length, e.g. 0.75*units("in")).
        main_thickness: Main member thickness (Pint length).
        side_thickness: Side member thickness (Pint length).
        main_species_gravity: Specific gravity of main member.
        side_species_gravity: Specific gravity of side member (use 1.0 for steel).
        side_material: "wood" or "steel".
        loading: "single_shear" or "double_shear".
        angle_to_grain: Angle between force and grain direction (degrees).
            0 = parallel, 90 = perpendicular.
    """

    def __init__(self, bolt_diameter, main_thickness, side_thickness,
                 main_species_gravity, side_species_gravity=None,
                 side_material="wood", loading="single_shear",
                 angle_to_grain=0):
        self.D = bolt_diameter.to("in").magnitude
        self.lm = main_thickness.to("in").magnitude
        self.ls = side_thickness.to("in").magnitude
        self.Gm = main_species_gravity
        self.Gs = side_species_gravity or main_species_gravity
        self.side_material = side_material
        self.loading = loading
        self.theta = angle_to_grain

        # Dowel bearing strengths per NDS 12.3.3
        self.Fem = self._dowel_bearing_strength(self.Gm)
        self.Fes = self._dowel_bearing_strength(self.Gs) if side_material == "wood" else self._steel_bearing()

    def _dowel_bearing_strength(self, G):
        """Dowel bearing strength Fe per NDS Table 12.3.3.

        For parallel to grain: Fe_par = 11200 * G (psi)
        For perpendicular to grain: Fe_perp = 6100 * G^1.45 / sqrt(D) (psi)
        For angle theta: Fe_theta = Fe_par * Fe_perp / (Fe_par*sin^2(theta) + Fe_perp*cos^2(theta))
        """
        Fe_par = 11200.0 * G
        Fe_perp = 6100.0 * G**1.45 / math.sqrt(self.D)

        if self.theta == 0:
            return Fe_par
        elif self.theta == 90:
            return Fe_perp
        else:
            theta_rad = math.radians(self.theta)
            return (Fe_par * Fe_perp /
                    (Fe_par * math.sin(theta_rad)**2 + Fe_perp * math.cos(theta_rad)**2))

    def _steel_bearing(self):
        """Steel side plate bearing strength = 1.5 * Fu = 1.5 * 58000 = 87000 psi."""
        return 87000.0

    def Z_reference(self):
        """Reference single-bolt lateral design value Z per NDS 12.3.1.

        Uses the European Yield Model (EYM) equations for the six
        yield modes (Im, Is, II, IIIm, IIIs, IV).

        Returns:
            dict: {"Z": value in lbs, "governing_mode": mode name, "all_modes": dict}
        """
        D = self.D
        lm = self.lm
        ls = self.ls
        Fem = self.Fem
        Fes = self.Fes
        Fyb = 45000.0  # A307 bolt bending yield strength, psi

        Rd = {
            "Im": 4.0, "Is": 4.0, "II": 3.6, "IIIm": 3.2, "IIIs": 3.2, "IV": 3.2
        }

        Re = Fem / Fes if Fes != 0 else 1.0
        Rt = lm / ls if ls != 0 else 1.0

        # Mode Im
        Z_Im = D * lm * Fem / Rd["Im"]

        # Mode Is
        Z_Is = D * ls * Fes / Rd["Is"]

        # Mode II (single shear only)
        k1_num = math.sqrt(Re + 2 * Re**2 * (1 + Rt + Rt**2) + Rt**2 * Re**3) - Re * (1 + Rt)
        k1_den = (1 + Re)
        k1 = k1_num / k1_den if k1_den != 0 else 0
        Z_II = k1 * D * ls * Fes / Rd["II"] if self.loading == "single_shear" else float("inf")

        # Mode IIIm
        k2_num = -1 + math.sqrt(2 * (1 + Re) + 2 * Fyb * (1 + 2 * Re) * D**2 / (3 * Fem * lm**2))
        k2 = k2_num / (1 + Re) if (1 + Re) != 0 else 0
        Z_IIIm = k2 * D * lm * Fem / Rd["IIIm"]

        # Mode IIIs
        k3_num = -1 + math.sqrt(2 * (1 + Re) / Re + 2 * Fyb * (2 + Re) * D**2 / (3 * Fem * ls**2))
        k3 = k3_num / (1 + Re) if (1 + Re) != 0 else 0
        Z_IIIs = k3 * D * ls * Fes / Rd["IIIs"]

        # Mode IV
        Z_IV = D**2 / Rd["IV"] * math.sqrt(2 * Fem * Fyb / (3 * (1 + Re)))

        modes = {
            "Im": Z_Im, "Is": Z_Is, "II": Z_II,
            "IIIm": Z_IIIm, "IIIs": Z_IIIs, "IV": Z_IV,
        }

        # Filter out non-positive and inf values for governing
        valid_modes = {k: v for k, v in modes.items() if 0 < v < float("inf")}
        if not valid_modes:
            return {"Z": 0.0, "governing_mode": "none", "all_modes": modes}

        governing = min(valid_modes, key=valid_modes.get)
        Z = valid_modes[governing]

        # Double shear: multiply by 2 for modes Im, Is, IV
        # (but modes II, IIIm, IIIs don't apply in double shear)
        if self.loading == "double_shear":
            ds_modes = {"Im": Z_Im * 2, "Is": Z_Is, "IV": Z_IV * 2}
            # Mode Is uses smaller of 2*Z_Is and Z_Im for double shear
            governing = min(ds_modes, key=ds_modes.get)
            Z = ds_modes[governing]
            modes = ds_modes

        return {
            "Z": round(Z, 1),
            "Z_units": Z * units("lbf"),
            "governing_mode": governing,
            "all_modes": {k: round(v, 1) for k, v in modes.items()},
        }

    def Cg(self, num_bolts_in_row, Am=None, As=None):
        """Group action factor per NDS 10.3.6 Table 10.3.6A.

        Simplified approach: for 2 bolts in a row, Cg ~ 1.0.
        For more bolts, Cg decreases.

        Args:
            num_bolts_in_row: Number of fasteners in a row.
            Am: Area of main member (in^2). Defaults from section.
            As: Area of side member (in^2). Defaults to Am/2.

        Returns:
            float: Group action factor.
        """
        n = num_bolts_in_row
        if n <= 1:
            return 1.0

        # Simplified NDS Table 10.3.6A approximation
        # For wood-to-wood, Am/As = 1 to 5
        if Am is None:
            Am = self.lm * 3.5  # approximate
        if As is None:
            As = self.ls * 3.5

        ratio = Am / As if As != 0 else 1.0

        # Approximate Cg values from NDS Table 10.3.6A
        # These are for Em*Am / Es*As = 1.0 (wood-to-wood same species)
        _cg_table = {
            2: 1.00, 3: 0.98, 4: 0.96, 5: 0.93,
            6: 0.90, 7: 0.87, 8: 0.85, 9: 0.82,
            10: 0.80, 11: 0.78, 12: 0.76,
        }
        n_clamped = min(n, 12)
        return _cg_table.get(n_clamped, 0.75)

    def C_delta(self, end_distance, edge_distance, bolt_spacing, row_spacing=None):
        """Geometry factor per NDS 12.5.

        Checks minimum end distance, edge distance, and spacing
        requirements. Returns 1.0 if all minimums met, reduced value
        if distances are between minimum and full.

        Args:
            end_distance: Distance from bolt center to end of member (Pint length).
            edge_distance: Distance from bolt center to edge (Pint length).
            bolt_spacing: Center-to-center spacing between bolts in a row (Pint length).
            row_spacing: Spacing between rows (Pint length). Optional.

        Returns:
            float: Geometry factor (0 to 1.0).
        """
        D = self.D
        end_d = end_distance.to("in").magnitude
        edge_d = edge_distance.to("in").magnitude
        spacing = bolt_spacing.to("in").magnitude

        # NDS Table 12.5.1A - Minimum end distance
        # Parallel to grain, tension: 7D (full), 3.5D (reduced)
        # Parallel to grain, compression: 4D (full), 2D (reduced)
        min_end_full = 7.0 * D  # tension case (conservative)
        min_end_reduced = 3.5 * D

        # Minimum edge distance: 1.5D (NDS 12.5.4)
        min_edge = 1.5 * D

        # Minimum spacing: 4D (NDS 12.5.2)
        min_spacing = 4.0 * D

        factors = []

        if end_d < min_end_reduced:
            return 0.0  # Below absolute minimum
        elif end_d < min_end_full:
            factors.append(end_d / min_end_full)
        else:
            factors.append(1.0)

        if edge_d < min_edge:
            return 0.0
        factors.append(1.0)  # Edge distance is pass/fail

        if spacing < min_spacing * 0.75:
            return 0.0
        elif spacing < min_spacing:
            factors.append(spacing / min_spacing)
        else:
            factors.append(1.0)

        return round(min(factors), 3)

    def Z_prime(self, num_bolts=1, num_bolts_in_row=1,
                load_duration="normal", wet_service=False,
                temperature_f=100.0, end_distance=None,
                edge_distance=None, bolt_spacing=None):
        """Adjusted total connection design value Z'.

        Z' = Z * n * CD * CM * Ct * Cg * C_delta

        Args:
            num_bolts: Total number of bolts.
            num_bolts_in_row: Bolts per row (for Cg).
            load_duration: Load duration case.
            wet_service: True if wet service.
            temperature_f: Max sustained temperature.
            end_distance: End distance (Pint length).
            edge_distance: Edge distance (Pint length).
            bolt_spacing: In-row spacing (Pint length).

        Returns:
            dict with Z_prime, Z_ref, factors.
        """
        z_ref = self.Z_reference()
        Z = z_ref["Z"]

        factors = {}
        factors["CD"] = LOAD_DURATION_FACTORS.get(load_duration, 1.0)

        if wet_service:
            factors["CM"] = 0.70  # NDS Table 10.3.3
        else:
            factors["CM"] = 1.0

        if temperature_f <= 100:
            factors["Ct"] = 1.0
        elif temperature_f <= 125:
            factors["Ct"] = 0.80
        else:
            factors["Ct"] = 0.70

        factors["Cg"] = self.Cg(num_bolts_in_row)

        if end_distance and edge_distance and bolt_spacing:
            factors["C_delta"] = self.C_delta(end_distance, edge_distance, bolt_spacing)
        else:
            factors["C_delta"] = 1.0

        product = Z * num_bolts
        for v in factors.values():
            product *= v

        return {
            "Z_prime": round(product, 1) * units("lbf"),
            "Z_ref": z_ref,
            "num_bolts": num_bolts,
            "factors": factors,
        }


# ===================================================================
# Utility Functions
# ===================================================================

def list_available_species():
    """Return a list of available wood species in the reference database."""
    return sorted(_wood_ref["Species"].unique().tolist())


def list_available_grades(species=None):
    """Return available grades, optionally filtered by species."""
    if species:
        return sorted(_wood_ref[_wood_ref["Species"] == species]["Grade"].unique().tolist())
    return sorted(_wood_ref["Grade"].unique().tolist())


def list_available_glulam():
    """Return available glulam combinations."""
    return _glulam_ref[["Combination", "Species"]].drop_duplicates().to_string(index=False)


def list_lumber_sizes():
    """Return the lumber sizes table as a DataFrame."""
    return _lumber_sizes.copy()
