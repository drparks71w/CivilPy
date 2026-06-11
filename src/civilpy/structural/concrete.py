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
ACI 318-19 Chapter 17 - Anchoring to Concrete

All lengths in inches, forces in pounds (lb), stresses in psi.
"""

import functools
import math
from dataclasses import dataclass, field
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Anchor-rod thread lookup: UNC threads per inch → effective stress area (in²)
# Formula: A_se = π/4 * (d_a - 0.9743/n_t)²
# ──────────────────────────────────────────────────────────────────────────────
_UNC_TPI = {
    0.50: 13, 0.625: 11, 0.75: 10, 0.875: 9,
    1.00: 8,  1.25: 7,  1.50: 6,  1.75: 5,
    2.00: 4.5, 2.50: 4, 3.00: 4,
}


def _unc_stress_area(d_a: float) -> float:
    """Effective tensile stress area from UNC thread formula (in²)."""
    # Find nearest nominal diameter
    candidates = sorted(_UNC_TPI.keys(), key=lambda d: abs(d - d_a))
    n_t = _UNC_TPI[candidates[0]]
    return math.pi / 4 * (d_a - 0.9743 / n_t) ** 2


# ──────────────────────────────────────────────────────────────────────────────
# Results dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AnchorCheckResult:
    """Result for a single limit-state check."""
    label: str          # human-readable name
    reference: str      # ACI 318 section or equation number
    N_n: float          # nominal strength (lb), 0 if not a tension check
    V_n: float          # nominal strength (lb), 0 if not a shear check
    phi: float          # strength reduction factor
    phi_Sn: float       # design strength = phi * nominal (lb), or unitless limit if is_ratio
    demand: float       # factored demand (lb), or unitless ratio if is_ratio
    is_ratio: bool = False  # True for unitless interaction checks (don't divide by 1000)

    @property
    def dcr(self) -> float:
        """Demand-to-capacity ratio."""
        if self.phi_Sn <= 0:
            return float("inf")
        return self.demand / self.phi_Sn

    @property
    def ok(self) -> bool:
        return self.dcr <= 1.0

    def __repr__(self) -> str:
        status = "OK" if self.ok else "NG"
        if self.is_ratio:
            return (
                f"{self.label} [{self.reference}]: "
                f"limit={self.phi_Sn:.2f}, "
                f"demand={self.demand:.3f}, "
                f"DCR={self.dcr:.3f} [{status}]"
            )
        return (
            f"{self.label} [{self.reference}]: "
            f"φSn={self.phi_Sn/1000:.2f} kips, "
            f"demand={self.demand/1000:.2f} kips, "
            f"DCR={self.dcr:.3f} [{status}]"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────────────

class AnchorBolts:
    """
    ACI 318-19 Chapter 17 anchor design checks for cast-in and post-installed anchors.

    All inputs in US customary units (inches, pounds, psi).

    Parameters
    ----------
    f_c : float
        Specified concrete compressive strength (psi). Capped at 10,000 psi
        for cast-in anchors per ACI 318 Section 17.3.1.
    h_a : float
        Thickness of concrete member measured parallel to anchor axis (in).
    d_a : float
        Nominal anchor diameter (in).
    h_ef : float
        Effective embedment depth (in).
    f_ya : float
        Anchor yield strength (psi). e.g. ASTM F1554 Gr 36 → 36,000.
    f_uta : float
        Anchor tensile strength (psi). e.g. ASTM F1554 Gr 36 → 58,000.
        Used value is capped at min(1.9*f_ya, 125,000) per ACI 318-19 17.6.1.2.
    n_x : int
        Number of anchors in the x-direction (direction of applied shear).
    n_y : int
        Number of anchors in the y-direction.
    s_x : float
        Anchor spacing in x-direction (in). Use 0 if n_x == 1.
    s_y : float
        Anchor spacing in y-direction (in). Use 0 if n_y == 1.
    c_a1 : float
        Edge distance from anchor to free edge in direction of applied shear (in).
        Use a large value (e.g. 100) if no near edge in shear direction.
    c_a2 : float
        Edge distance from anchor to free edge perpendicular to shear (in).
        Use a large value if no near edge perpendicular to shear.
    c_a_min : float, optional
        Minimum edge distance in any direction (in). Defaults to min(c_a1, c_a2).
    A_se_N : float, optional
        Effective cross-sectional area of anchor in tension (in²). Computed
        from UNC thread formula if not provided.
    A_se_V : float, optional
        Effective cross-sectional area in shear (in²). Defaults to A_se_N.
    A_brg : float, optional
        Net bearing area of anchor head (in²). Required for headed-bolt pullout
        per 17.6.3.2.2a. If None, pullout check uses the hooked-bolt formula
        with e_h, or is skipped.
    e_h : float, optional
        Hook length (in) for J- or L-bolts; from inside of hook to bearing
        surface. Required for hooked-bolt pullout per 17.6.3.2.2b.
    lambda_a : float
        Lightweight concrete modification factor per ACI 318 Table 17.2.4.1.
        Use 1.0 for normalweight concrete (default).
    is_cracked : bool
        True if concrete is assumed cracked at service load levels (conservative
        default). False for uncracked.
    has_supp_reinf : bool
        True if supplementary reinforcement conforming to ACI 318 17.5.2.1
        is provided (Condition A → higher φ for concrete limit states).
    is_ductile : bool
        True if anchor material meets ductility requirements (elongation ≥ 14%,
        reduction ≥ 30%). ASTM F1554 Gr 36 and Gr 55 qualify.
    grout_pad : bool
        True if anchor is used with a built-up grout pad. Reduces V_sa by 0.80
        per ACI 318 Section 17.7.1.2.1.
    e_N_prime : float
        Eccentricity of resultant tensile force from centroid of anchor group (in).
        Use 0 for concentric loading.
    e_V_prime : float
        Eccentricity of shear force from centroid of anchor group (in).
        Use 0 for concentric shear.
    A_Nc : float, optional
        Projected concrete failure area for tension (in²). Computed automatically
        if not provided.
    A_Vc : float, optional
        Projected concrete failure area for shear (in²). Computed automatically
        if not provided.
    N_ua : float
        Total factored tensile demand on the anchor group (lb).
    V_ua : float
        Total factored shear demand on the anchor group (lb).
    shear_direction : str
        Direction of applied shear relative to the nearest edge: "perpendicular"
        (default), "parallel" (ACI 17.7.2.1(c) — doubles V_cb, sets psi_ed=1.0),
        or "away" (shear directed away from edge — no edge breakout check).
    anchor_type : str
        "cast_in" (default), "post_installed", or "adhesive".
        Affects k_c in basic breakout (24 vs 17) and enables bond check.
    tau_uncr : float, optional
        Characteristic bond stress in uncracked concrete (psi), from ACI 355.4
        evaluation report. Required for adhesive bond strength check.
    tau_cr : float, optional
        Characteristic bond stress in cracked concrete (psi). Required for
        adhesive bond strength check when is_cracked=True.
    sdc : str
        Seismic Design Category ("A"–"F"). For SDC C–F, concrete failure mode
        design strengths are multiplied by 0.75 per ACI 318-19 Section 17.10.5.3.
    anchor_reinf_tension : float, optional
        Design strength (φ*Rn, lb) of properly developed anchor reinforcement
        in tension per ACI 17.5.2.1. When provided, replaces concrete breakout
        in the tension limit-state check.
    anchor_reinf_shear : float, optional
        Design strength (φ*Rn, lb) of anchor reinforcement in shear per
        ACI 17.5.2.1. When provided, replaces concrete breakout in the shear
        limit-state check.
    bolt_circle_radius : float, optional
        Radius of the bolt circle (in) for circular anchor patterns (e.g. highway
        poles, luminaires, sign structures). When provided, `_A_Nc` and `_A_Vc`
        use annular/circular geometry instead of the rectangular array formulas.
        Use `from_circular()` to construct typical highway pole base patterns.
    shaft_radius : float, optional
        Outer radius of a drilled shaft (in). When provided together with
        `bolt_circle_radius`, automatically sets c_a1 = shaft_radius −
        bolt_circle_radius (edge distance from bolt to shaft perimeter).
    coupler_depth : float, optional
        Depth (in) of a heavy-hex coupling nut used to extend a damaged anchor rod
        via field repour. Per AISC Design Guide 1 and ACI 318-19 Section 17.10.5.3,
        the coupler must be frictionally isolated from the new concrete (e.g., with
        polyethylene tape or PVC sleeving) to preserve the anchor's stretch length
        and maintain ductile behavior. If the coupler is NOT isolated, it acts as
        the bearing surface, reducing effective embedment: h_ef_eff = h_ef − coupler_depth.
    c_ac : float, optional
        Critical edge distance for post-installed anchors (in). Used in the splitting
        factor ψ_cp,N per ACI 318-19 Eq. 17.6.2.6.1b. Defaults to 2.5·h_ef per
        ACI Table 17.9.5 if not provided. Only used when anchor_type='post_installed'
        and is_cracked=False.
    """

    def __init__(
        self,
        # Concrete
        f_c: float,
        h_a: float,
        # Anchor geometry
        d_a: float,
        h_ef: float,
        # Anchor material
        f_ya: float,
        f_uta: float,
        # Group layout
        n_x: int = 1,
        n_y: int = 1,
        s_x: float = 0.0,
        s_y: float = 0.0,
        # Edge distances
        c_a1: float = float("inf"),
        c_a2: float = float("inf"),
        c_a_min: Optional[float] = None,
        # Anchor cross-sections
        A_se_N: Optional[float] = None,
        A_se_V: Optional[float] = None,
        A_brg: Optional[float] = None,
        e_h: Optional[float] = None,
        # Concrete & reinforcement modifiers
        lambda_a: float = 1.0,
        is_cracked: bool = True,
        has_supp_reinf: bool = False,
        is_ductile: bool = True,
        grout_pad: bool = False,
        # Eccentricities
        e_N_prime: float = 0.0,
        e_V_prime: float = 0.0,
        # Override projected areas
        A_Nc: Optional[float] = None,
        A_Vc: Optional[float] = None,
        # Applied demands
        N_ua: float = 0.0,
        V_ua: float = 0.0,
        # Shear direction
        shear_direction: str = "perpendicular",
        # Anchor type & adhesive bond
        anchor_type: str = "cast_in",
        tau_uncr: Optional[float] = None,
        tau_cr: Optional[float] = None,
        # Seismic
        sdc: str = "A",
        # Anchor reinforcement overrides
        anchor_reinf_tension: Optional[float] = None,
        anchor_reinf_shear: Optional[float] = None,
        # AASHTO / highway structures
        bolt_circle_radius: Optional[float] = None,
        shaft_radius: Optional[float] = None,
        coupler_depth: Optional[float] = None,
        c_ac: Optional[float] = None,
    ):
        # ── Material limits ─────────────────────────────────────────────────
        self.f_c = min(f_c, 10_000)          # ACI 318 17.3.1
        self.h_a = h_a
        self.d_a = d_a
        self.f_ya = f_ya
        self.f_uta = min(f_uta, min(1.9 * f_ya, 125_000))  # 17.6.1.2 cap

        # ── Coupler / cold-joint depth ───────────────────────────────────────
        self.coupler_depth = coupler_depth
        if coupler_depth is not None:
            if coupler_depth <= 0 or coupler_depth >= h_ef:
                raise ValueError(
                    f"coupler_depth={coupler_depth} must be between 0 and h_ef={h_ef}"
                )
            self.h_ef = h_ef - coupler_depth
        else:
            self.h_ef = h_ef

        # c_ac stored after h_ef is set so default can reference it
        self._c_ac_input = c_ac

        # ── Group geometry ───────────────────────────────────────────────────
        self.n_x = max(1, n_x)
        self.n_y = max(1, n_y)
        self.n = self.n_x * self.n_y
        self.s_x = s_x
        self.s_y = s_y

        # ── Circular pattern / drilled shaft geometry ────────────────────────
        self._bolt_circle_radius = bolt_circle_radius
        self.shaft_radius = shaft_radius
        # If shaft geometry is provided and c_a1 wasn't explicitly set, derive it.
        if shaft_radius is not None and bolt_circle_radius is not None:
            derived = shaft_radius - bolt_circle_radius
            if derived <= 0:
                raise ValueError(
                    f"shaft_radius={shaft_radius} must be > bolt_circle_radius={bolt_circle_radius}"
                )
            if c_a1 == float("inf"):
                c_a1 = derived
            if c_a2 == float("inf"):
                c_a2 = derived  # round shaft: same edge distance on all sides

        # ── Edge distances ───────────────────────────────────────────────────
        self.c_a1 = c_a1
        self.c_a2 = c_a2
        self.c_a_min = c_a_min if c_a_min is not None else min(c_a1, c_a2)

        # ── Cross-sectional areas ────────────────────────────────────────────
        self.A_se_N = A_se_N if A_se_N is not None else _unc_stress_area(d_a)
        self.A_se_V = A_se_V if A_se_V is not None else self.A_se_N
        self.A_brg = A_brg
        self.e_h = e_h

        # ── Modifiers ────────────────────────────────────────────────────────
        self.lambda_a = lambda_a
        self.is_cracked = is_cracked
        self.has_supp_reinf = has_supp_reinf
        self.is_ductile = is_ductile
        self.grout_pad = grout_pad

        # ── Eccentricities ───────────────────────────────────────────────────
        self.e_N_prime = e_N_prime
        self.e_V_prime = e_V_prime

        # ── Projected areas (computed or user-supplied) ──────────────────────
        self._A_Nc_override = A_Nc
        self._A_Vc_override = A_Vc

        # ── Demands ─────────────────────────────────────────────────────────
        self.N_ua = N_ua
        self.V_ua = V_ua

        # ── Shear direction & anchor type ────────────────────────────────────
        if shear_direction not in ("perpendicular", "parallel", "away"):
            raise ValueError(f"shear_direction must be 'perpendicular', 'parallel', or 'away', got {shear_direction!r}")
        self.shear_direction = shear_direction
        if anchor_type not in ("cast_in", "post_installed", "adhesive"):
            raise ValueError(f"anchor_type must be 'cast_in', 'post_installed', or 'adhesive', got {anchor_type!r}")
        self.anchor_type = anchor_type
        self.tau_uncr = tau_uncr
        self.tau_cr = tau_cr

        # ── Seismic & anchor reinforcement ───────────────────────────────────
        self.sdc = sdc.upper()
        self.anchor_reinf_tension = anchor_reinf_tension
        self.anchor_reinf_shear = anchor_reinf_shear

        # ── Phi factors ─────────────────────────────────────────────────────
        # Table 17.5.3(a) - steel
        if is_ductile:
            self.phi_steel_tension = 0.75
            self.phi_steel_shear   = 0.65
        else:
            self.phi_steel_tension = 0.65
            self.phi_steel_shear   = 0.60

        # Table 17.5.3(b) - concrete breakout, bond, side-face blowout
        if has_supp_reinf:
            self.phi_concrete = 0.75   # Condition A
        else:
            self.phi_concrete = 0.70   # Condition B

        # Table 17.5.3(c) - pullout and pryout (cast-in anchors: fixed at 0.70)
        self.phi_pullout = 0.70

    # ─────────────────────────────────────────────────────────────────────────
    # Seismic reduction (17.10.5.3)
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def _phi_seismic(self) -> float:
        """0.75 reduction on concrete failure modes for SDC C–F (ACI 17.10.5.3)."""
        return 0.75 if self.sdc in ("C", "D", "E", "F") else 1.0

    @property
    def c_ac(self) -> float:
        """Critical edge distance for post-installed anchors (in) — ACI Table 17.9.5."""
        if self._c_ac_input is not None:
            return self._c_ac_input
        return 2.5 * self.h_ef

    # ─────────────────────────────────────────────────────────────────────────
    # Projected failure areas (17.6.2.1, 17.7.2.1)
    # ─────────────────────────────────────────────────────────────────────────

    def _A_Nco(self) -> float:
        """A_Nco: projected area of single anchor far from edges (17.6.2.1.4)."""
        return 9.0 * self.h_ef ** 2

    @functools.cached_property
    def _A_Nc(self) -> float:
        """
        A_Nc: projected concrete failure area for tension (17.6.2.1.1).

        Rectangular group: rectangle from projecting 1.5*h_ef from outermost anchors.
        Circular group: annular ring — π*(R_out² − R_in²) where
          R_out = r_bc + min(c_a_min, 1.5*h_ef),
          R_in  = max(0, r_bc − 1.5*h_ef)  (non-zero when bolts are far apart).
        """
        if self._A_Nc_override is not None:
            return self._A_Nc_override
        cone = 1.5 * self.h_ef
        if self._bolt_circle_radius is not None:
            r_bc = self._bolt_circle_radius
            R_out = r_bc + min(self.c_a_min, cone)
            R_in  = max(0.0, r_bc - cone)
            return math.pi * (R_out ** 2 - R_in ** 2)
        # Rectangular group
        x_extent = min(self.c_a_min, cone) + (self.n_x - 1) * self.s_x + min(self.c_a_min, cone)
        y_extent = min(self.c_a_min, cone) + (self.n_y - 1) * self.s_y + min(self.c_a_min, cone)
        return x_extent * y_extent

    def _A_Vco(self) -> float:
        """A_Vco: projected area of single anchor in deep member (17.7.2.1.3)."""
        return 4.5 * self.c_a1 ** 2

    def _a_vc_for(self, c_a1: float, c_a2: float, n_perp: int, s_perp: float) -> float:
        """A_Vc for arbitrary edge distances and group layout — used for corner checks."""
        height = min(1.5 * c_a1, self.h_a)
        c_a2_eff = min(c_a2, 1.5 * c_a1)
        return height * (c_a2_eff + (n_perp - 1) * s_perp + c_a2_eff)

    @functools.cached_property
    def _A_Vc(self) -> float:
        """
        A_Vc: projected concrete failure area for shear (17.7.2.1.1).

        Rectangular group: height × (c_a2_eff + group_width + c_a2_eff).
        Circular group: height × (c_a2_eff + 2*r_bc + c_a2_eff), where the
          bolt circle diameter replaces the rectangular group extent.
        """
        if self._A_Vc_override is not None:
            return self._A_Vc_override
        if self._bolt_circle_radius is not None:
            r_bc = self._bolt_circle_radius
            height = min(1.5 * self.c_a1, self.h_a)
            c_a2_eff = min(self.c_a2, 1.5 * self.c_a1)
            return height * (c_a2_eff + 2.0 * r_bc + c_a2_eff)
        return self._a_vc_for(self.c_a1, self.c_a2, self.n_y, self.s_y)

    # ─────────────────────────────────────────────────────────────────────────
    # 17.6 - Tensile strength
    # ─────────────────────────────────────────────────────────────────────────

    def steel_tension_strength(self) -> AnchorCheckResult:
        """
        Steel strength of anchors in tension — ACI 318-19 Eq. 17.6.1.2.

        N_sa = A_se,N * f_uta  (per anchor)
        Total group design strength = n * phi * N_sa
        """
        N_sa_each = self.A_se_N * self.f_uta
        N_sa_total = self.n * N_sa_each
        phi_Nn = self.phi_steel_tension * N_sa_total
        return AnchorCheckResult(
            label="Steel strength (tension)",
            reference="ACI 318-19 Eq. 17.6.1.2",
            N_n=N_sa_total,
            V_n=0.0,
            phi=self.phi_steel_tension,
            phi_Sn=phi_Nn,
            demand=self.N_ua,
        )

    def _psi_ec_N(self) -> float:
        """Eccentricity factor for tension — ACI 318-19 Eq. 17.6.2.3.1."""
        return min(1.0, 1.0 / (1.0 + self.e_N_prime / (1.5 * self.h_ef)))

    def _psi_ed_N(self) -> float:
        """Edge effect factor for tension — ACI 318-19 Eq. 17.6.2.4.1."""
        if self.c_a_min >= 1.5 * self.h_ef:
            return 1.0
        return 0.7 + 0.3 * self.c_a_min / (1.5 * self.h_ef)

    def _psi_c_N(self) -> float:
        """Cracking factor for tension — ACI 318-19 Section 17.6.2.5.1."""
        if self.is_cracked:
            return 1.0
        # Uncracked concrete: 1.25 for cast-in, 1.40 for post-installed or adhesive (17.6.2.5.1)
        return 1.40 if self.anchor_type in ("post_installed", "adhesive") else 1.25

    def _psi_cp_N(self) -> float:
        """Splitting factor for tension — ACI 318-19 Eq. 17.6.2.6.1."""
        # Cast-in anchors: always 1.0 per 17.6.2.6.2
        if self.anchor_type != "post_installed":
            return 1.0
        # Post-installed in cracked concrete: 1.0 per 17.6.2.6.1a
        if self.is_cracked:
            return 1.0
        # Post-installed in uncracked concrete: Eq. 17.6.2.6.1b
        ratio = self.c_a_min / self.c_ac
        return min(1.0, max(ratio, 1.0 / 1.5))

    def _N_b(self) -> float:
        """
        Basic concrete breakout strength of a single anchor in tension (lb).

        Cast-in: Eq. 17.6.2.2.3 (11 ≤ h_ef ≤ 25) else Eq. 17.6.2.2.1 (k_c=24).
        Post-installed: Eq. 17.6.2.2.1 with k_c=17 per 17.6.2.2.2.
        """
        if self.anchor_type == "cast_in" and 11.0 <= self.h_ef <= 25.0:
            return 16.0 * self.lambda_a * math.sqrt(self.f_c) * self.h_ef ** (5.0 / 3.0)
        k_c = 24.0 if self.anchor_type == "cast_in" else 17.0
        return k_c * self.lambda_a * math.sqrt(self.f_c) * self.h_ef ** 1.5

    def breakout_strength_tension(self) -> AnchorCheckResult:
        """
        Concrete breakout strength of anchor group in tension.

        Single anchor: Eq. 17.6.2.1a
        Anchor group:  Eq. 17.6.2.1b  (includes psi_ec_N)
        """
        A_Nc  = self._A_Nc
        A_Nco = self._A_Nco()
        N_b   = self._N_b()

        psi_ec  = self._psi_ec_N()
        psi_ed  = self._psi_ed_N()
        psi_c   = self._psi_c_N()
        psi_cp  = self._psi_cp_N()

        if self.n == 1:
            # Eq. 17.6.2.1a — single anchor
            N_cb = (A_Nc / A_Nco) * psi_ed * psi_c * psi_cp * N_b
            ref = "ACI 318-19 Eq. 17.6.2.1a"
        else:
            # Eq. 17.6.2.1b — anchor group
            N_cb = (A_Nc / A_Nco) * psi_ec * psi_ed * psi_c * psi_cp * N_b
            ref = "ACI 318-19 Eq. 17.6.2.1b"

        phi_Nn = self.phi_concrete * self._phi_seismic * N_cb
        return AnchorCheckResult(
            label="Concrete breakout (tension)",
            reference=ref,
            N_n=N_cb,
            V_n=0.0,
            phi=self.phi_concrete,
            phi_Sn=phi_Nn,
            demand=self.N_ua,
        )

    def _psi_c_P(self) -> float:
        """Pullout cracking factor — ACI 318-19 Section 17.6.3.3.1."""
        return 1.0 if self.is_cracked else 1.4

    def pullout_strength(self) -> Optional[AnchorCheckResult]:
        """
        Pullout strength of cast-in anchors — ACI 318-19 Section 17.6.3.

        Returns None if insufficient geometry is provided (no A_brg or e_h).

        For headed studs/bolts: N_p = 8 * A_brg * f_c'  (Eq. 17.6.3.2.2a)
        For J- or L-bolts:      N_p = 0.9 * f_c' * e_h * d_a  (Eq. 17.6.3.2.2b)
        N_pn = psi_c,P * N_p  (Eq. 17.6.3.1)

        Note: Pullout is evaluated per anchor; total = n * phi * N_pn.
        """
        if self.A_brg is not None:
            # Eq. 17.6.3.2.2a — headed studs and headed bolts
            N_p = 8.0 * self.A_brg * self.f_c
            ref = "ACI 318-19 Eq. 17.6.3.2.2a (headed)"
        elif self.e_h is not None:
            # Eq. 17.6.3.2.2b — J- or L-bolts
            if not (3.0 * self.d_a <= self.e_h <= 4.5 * self.d_a):
                raise ValueError(
                    f"Hook length e_h={self.e_h:.3f} must satisfy "
                    f"3*d_a={3*self.d_a:.3f} ≤ e_h ≤ 4.5*d_a={4.5*self.d_a:.3f}"
                )
            N_p = 0.9 * self.f_c * self.e_h * self.d_a
            ref = "ACI 318-19 Eq. 17.6.3.2.2b (hooked)"
        else:
            return None

        N_pn_each  = self._psi_c_P() * N_p
        N_pn_total = self.n * N_pn_each
        phi_Nn     = self.phi_pullout * self._phi_seismic * N_pn_total
        return AnchorCheckResult(
            label="Pullout (tension)",
            reference=ref,
            N_n=N_pn_total,
            V_n=0.0,
            phi=self.phi_pullout,
            phi_Sn=phi_Nn,
            demand=self.N_ua,
        )

    def side_face_blowout(self) -> Optional[AnchorCheckResult]:
        """
        Side-face blowout strength of headed anchors — ACI 318-19 Section 17.6.4.

        Applicable only when h_ef > 2.5 * c_a1 (deep anchor near edge).
        Returns None if condition not met or A_brg not provided.

        N_sb = 160 * c_a1 * sqrt(A_brg) * lambda_a * sqrt(f_c')  (Eq. 17.6.4.1)
        Group: N_sbg = (1 + s/6/c_a1) * N_sb  (Eq. 17.6.4.2, simplified)
        """
        if self.A_brg is None:
            return None
        if self.h_ef <= 2.5 * self.c_a1:
            return None   # condition not triggered

        N_sb = 160.0 * self.c_a1 * math.sqrt(self.A_brg) * self.lambda_a * math.sqrt(self.f_c)

        # Perpendicular edge modifier (17.6.4.1.1)
        if self.c_a2 < 3.0 * self.c_a1:
            ratio = max(1.0, min(3.0, self.c_a2 / self.c_a1))
            N_sb *= (1.0 + ratio) / 4.0

        # Group effect (17.6.4.2): if spacing < 6*c_a1, average per anchor
        if self.n > 1 and self.s_x < 6.0 * self.c_a1:
            N_sbg = N_sb * (1.0 + self.s_x / (6.0 * self.c_a1))
        else:
            N_sbg = self.n * N_sb

        phi_Nn = self.phi_concrete * self._phi_seismic * N_sbg
        return AnchorCheckResult(
            label="Side-face blowout",
            reference="ACI 318-19 Eq. 17.6.4.1",
            N_n=N_sbg,
            V_n=0.0,
            phi=self.phi_concrete,
            phi_Sn=phi_Nn,
            demand=self.N_ua,
        )

    def bond_strength_tension(self) -> Optional[AnchorCheckResult]:
        """
        Bond strength of adhesive anchors in tension — ACI 318-19 Section 17.6.5.

        Requires anchor_type="adhesive" and tau_uncr (or tau_cr when is_cracked).
        Returns None for non-adhesive anchors or missing bond stress data.

        N_ba = tau * π * d_a * h_ef   (Eq. 17.6.5.2.1)
        c_Na = 10 * d_a * sqrt(tau / 1100)  (Eq. 17.6.5.1.5, influence distance)
        """
        if self.anchor_type != "adhesive":
            return None
        tau = self.tau_cr if self.is_cracked else self.tau_uncr
        if tau is None:
            return None

        # Characteristic influence distance
        c_Na = 10.0 * self.d_a * math.sqrt(tau / 1100.0)

        # Reference influence area (single anchor, free of edges)
        A_Nao = (2.0 * c_Na) ** 2

        # Group influence area (bounded by edges)
        x_ext = min(self.c_a_min, c_Na) + (self.n_x - 1) * self.s_x + min(self.c_a_min, c_Na)
        y_ext = min(self.c_a_min, c_Na) + (self.n_y - 1) * self.s_y + min(self.c_a_min, c_Na)
        A_Na = x_ext * y_ext

        # Basic bond strength per anchor
        N_ba = tau * math.pi * self.d_a * self.h_ef

        # Edge and eccentricity factors
        psi_ed_Na = 1.0 if self.c_a_min >= c_Na else (0.7 + 0.3 * self.c_a_min / c_Na)
        psi_ec_Na = min(1.0, 1.0 / (1.0 + self.e_N_prime / c_Na))

        if self.n == 1:
            N_ag = (A_Na / A_Nao) * psi_ed_Na * N_ba
            ref = "ACI 318-19 Eq. 17.6.5.1.1a"
        else:
            N_ag = (A_Na / A_Nao) * psi_ec_Na * psi_ed_Na * N_ba
            ref = "ACI 318-19 Eq. 17.6.5.1.1b"

        phi_Nn = self.phi_concrete * self._phi_seismic * N_ag
        return AnchorCheckResult(
            label="Bond strength (tension)",
            reference=ref,
            N_n=N_ag,
            V_n=0.0,
            phi=self.phi_concrete,
            phi_Sn=phi_Nn,
            demand=self.N_ua,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 17.7 - Shear strength
    # ─────────────────────────────────────────────────────────────────────────

    def steel_shear_strength(self) -> AnchorCheckResult:
        """
        Steel strength of anchors in shear — ACI 318-19 Eq. 17.7.1.2b.

        For cast-in headed bolts (threads may be in shear plane):
            V_sa = 0.6 * A_se,V * f_uta  per anchor
        Grout pad reduces by 0.80 (Section 17.7.1.2.1).
        """
        V_sa_each = 0.6 * self.A_se_V * self.f_uta
        if self.grout_pad:
            V_sa_each *= 0.80   # 17.7.1.2.1

        V_sa_total = self.n * V_sa_each
        phi_Vn = self.phi_steel_shear * V_sa_total
        return AnchorCheckResult(
            label="Steel strength (shear)",
            reference="ACI 318-19 Eq. 17.7.1.2b",
            N_n=0.0,
            V_n=V_sa_total,
            phi=self.phi_steel_shear,
            phi_Sn=phi_Vn,
            demand=self.V_ua,
        )

    def _psi_ec_V(self) -> float:
        """Eccentricity factor for shear — ACI 318-19 Eq. 17.7.2.3.1."""
        return min(1.0, 1.0 / (1.0 + self.e_V_prime / (1.5 * self.c_a1)))

    def _psi_ed_V(self) -> float:
        """Edge effect factor for shear — ACI 318-19 Eq. 17.7.2.4.1."""
        if self.c_a2 >= 1.5 * self.c_a1:
            return 1.0
        return 0.7 + 0.3 * self.c_a2 / (1.5 * self.c_a1)

    def _psi_c_V(self) -> float:
        """
        Cracking factor for shear — ACI 318-19 Table 17.7.2.5.1.

        1.4 if uncracked and no supplementary reinforcement
        1.2 if cracked with supplementary reinforcement ≥ No. 4 bar
        1.0 if cracked with no adequate supplementary reinforcement
        """
        if not self.is_cracked:
            return 1.4
        if self.has_supp_reinf:
            return 1.2
        return 1.0

    def _psi_h_V(self) -> float:
        """
        Member thickness factor for shear — ACI 318-19 Eq. 17.7.2.6.1.

        Applied when h_a < 1.5 * c_a1.
        """
        if self.h_a >= 1.5 * self.c_a1:
            return 1.0
        return math.sqrt(1.5 * self.c_a1 / self.h_a)

    def _v_b_for(self, c_a1: float) -> float:
        """V_b for arbitrary c_a1 — used for corner checks and parallel shear."""
        l_e = min(self.h_ef, 8.0 * self.d_a)
        V_b_a = (7.0 * (l_e / self.d_a) ** 0.2 * math.sqrt(self.d_a)) * \
                self.lambda_a * math.sqrt(self.f_c) * c_a1 ** 1.5
        V_b_b = 9.0 * self.lambda_a * math.sqrt(self.f_c) * c_a1 ** 1.5
        return min(V_b_a, V_b_b)

    @functools.cached_property
    def _V_b(self) -> float:
        """
        Basic concrete breakout strength of a single anchor in shear (lb).

        V_b per Eq. 17.7.2.2.1a (geometry-based), capped by Eq. 17.7.2.2.1b.
        l_e = h_ef for anchors with constant stiffness (headed rods).
        """
        return self._v_b_for(self.c_a1)

    def _vcb_perp(self, c_a1: float, c_a2: float, n_perp: int, s_perp: float,
                  override_psi_ed: Optional[float] = None) -> float:
        """
        V_cb for shear perpendicular to an edge — parametric helper for corner/parallel.

        n_perp / s_perp are the anchor count and spacing in the direction
        *perpendicular* to shear (i.e. parallel to the edge being checked).
        """
        A_Vc  = self._a_vc_for(c_a1, c_a2, n_perp, s_perp)
        A_Vco = 4.5 * c_a1 ** 2
        V_b   = self._v_b_for(c_a1)

        psi_ec = min(1.0, 1.0 / (1.0 + self.e_V_prime / (1.5 * c_a1)))
        if override_psi_ed is not None:
            psi_ed = override_psi_ed
        elif c_a2 >= 1.5 * c_a1:
            psi_ed = 1.0
        else:
            psi_ed = 0.7 + 0.3 * c_a2 / (1.5 * c_a1)
        psi_c = self._psi_c_V()
        psi_h = 1.0 if self.h_a >= 1.5 * c_a1 else math.sqrt(1.5 * c_a1 / self.h_a)

        if self.n == 1:
            return (A_Vc / A_Vco) * psi_ed * psi_c * psi_h * V_b
        return (A_Vc / A_Vco) * psi_ec * psi_ed * psi_c * psi_h * V_b

    def breakout_strength_shear(self) -> Optional[AnchorCheckResult]:
        """
        Concrete breakout strength of anchor group in shear — ACI 318-19 17.7.2.

        shear_direction="perpendicular": standard edge breakout (17.7.2.1a/b).
          Corner condition (both c_a1 and c_a2 finite): automatically computes
          both edges and uses the minimum per ACI 17.7.2.1(d).
        shear_direction="parallel": doubles V_cb with psi_ed=1.0 (17.7.2.1(c)).
        shear_direction="away": returns None (no edge breakout).

        Returns None when c_a1 is infinite (no near edge in shear direction).
        """
        if self.shear_direction == "away" or not math.isfinite(self.c_a1):
            return None

        psi_c = self._psi_c_V()

        if self.shear_direction == "parallel":
            # ACI 17.7.2.1(c): double the perpendicular result, psi_ed = 1.0
            V_cb = 2.0 * self._vcb_perp(self.c_a1, self.c_a2, self.n_y, self.s_y,
                                         override_psi_ed=1.0)
            ref_suffix = " (parallel×2)"
        else:
            # "perpendicular"
            V_cb = self._vcb_perp(self.c_a1, self.c_a2, self.n_y, self.s_y)

            # Corner check — ACI 17.7.2.1(d): when c_a2 < 1.5*c_a1 the second
            # edge can produce a lower breakout capacity; check both and use min.
            if math.isfinite(self.c_a2) and self.c_a2 < 1.5 * self.c_a1:
                V_cb_2 = self._vcb_perp(self.c_a2, self.c_a1, self.n_x, self.s_x)
                if V_cb_2 < V_cb:
                    V_cb = V_cb_2
                    ref_suffix = " (corner, edge 2 governs)"
                else:
                    ref_suffix = " (corner, edge 1 governs)"
            else:
                ref_suffix = ""

        eq = "17.7.2.1a" if self.n == 1 else "17.7.2.1b"
        ref = f"ACI 318-19 Eq. {eq}{ref_suffix}"
        phi_Vn = self.phi_concrete * self._phi_seismic * V_cb
        return AnchorCheckResult(
            label="Concrete breakout (shear)",
            reference=ref,
            N_n=0.0,
            V_n=V_cb,
            phi=self.phi_concrete,
            phi_Sn=phi_Vn,
            demand=self.V_ua,
        )

    def pryout_strength(self) -> AnchorCheckResult:
        """
        Concrete pryout strength of anchors in shear — ACI 318-19 Eq. 17.7.3.1.

        V_cp  = k_cp * N_cp   (single anchor)
        V_cpg = k_cp * N_cpg  (group)

        k_cp = 1.0 for h_ef < 2.5 in, else 2.0.
        N_cp / N_cpg taken as concrete breakout strength in tension.
        """
        k_cp = 1.0 if self.h_ef < 2.5 else 2.0

        # Use nominal tension breakout (no phi) as N_cp
        result_N = self.breakout_strength_tension()
        N_cp = result_N.N_n   # nominal (unfactored)

        V_cp = k_cp * N_cp
        phi_Vn = self.phi_pullout * self._phi_seismic * V_cp

        return AnchorCheckResult(
            label="Pryout (shear)",
            reference="ACI 318-19 Eq. 17.7.3.1",
            N_n=0.0,
            V_n=V_cp,
            phi=self.phi_pullout,
            phi_Sn=phi_Vn,
            demand=self.V_ua,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 17.8 - Tension-shear interaction
    # ─────────────────────────────────────────────────────────────────────────

    def tension_shear_interaction(self) -> AnchorCheckResult:
        """
        Tension-shear interaction — ACI 318-19 Section 17.8.

        If N_ua/(φN_n) ≤ 0.2:  shear governs, full shear capacity available.
        If V_ua/(φV_n) ≤ 0.2:  tension governs, full tension capacity available.
        Otherwise:
            N_ua/(φN_n) + V_ua/(φV_n) ≤ 1.2  (Eq. 17.8.3)
        """
        phi_Nn = min(r.phi_Sn for r in self._tension_results() if r is not None)
        phi_Vn = min(r.phi_Sn for r in self._shear_results() if r is not None)

        ratio_N = self.N_ua / phi_Nn if phi_Nn > 0 else float("inf")
        ratio_V = self.V_ua / phi_Vn if phi_Vn > 0 else float("inf")

        if ratio_N <= 0.2:
            # Only shear: demand = 0 equivalent (tension neglected)
            interaction = ratio_V
        elif ratio_V <= 0.2:
            # Only tension
            interaction = ratio_N
        else:
            interaction = ratio_N + ratio_V

        return AnchorCheckResult(
            label="Tension-shear interaction",
            reference="ACI 318-19 Eq. 17.8.3",
            N_n=0.0,
            V_n=0.0,
            phi=1.0,
            phi_Sn=1.2,
            demand=interaction,
            is_ratio=True,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers & summary
    # ─────────────────────────────────────────────────────────────────────────

    def _tension_results(self) -> list:
        results = [self.steel_tension_strength()]

        # Anchor reinforcement replaces concrete breakout in tension (17.5.2.1)
        if self.anchor_reinf_tension is not None:
            results.append(AnchorCheckResult(
                label="Anchor reinforcement (tension)",
                reference="ACI 318-19 Section 17.5.2.1",
                N_n=self.anchor_reinf_tension,
                V_n=0.0,
                phi=1.0,
                phi_Sn=self.anchor_reinf_tension,
                demand=self.N_ua,
            ))
        else:
            results.append(self.breakout_strength_tension())

        pu = self.pullout_strength()
        if pu is not None:
            results.append(pu)
        sb = self.side_face_blowout()
        if sb is not None:
            results.append(sb)
        bond = self.bond_strength_tension()
        if bond is not None:
            results.append(bond)
        return results

    def _shear_results(self) -> list:
        results = [self.steel_shear_strength()]

        # Anchor reinforcement replaces concrete breakout in shear (17.5.2.1)
        if self.anchor_reinf_shear is not None:
            results.append(AnchorCheckResult(
                label="Anchor reinforcement (shear)",
                reference="ACI 318-19 Section 17.5.2.1",
                N_n=0.0,
                V_n=self.anchor_reinf_shear,
                phi=1.0,
                phi_Sn=self.anchor_reinf_shear,
                demand=self.V_ua,
            ))
        else:
            cb = self.breakout_strength_shear()
            if cb is not None:
                results.append(cb)

        results.append(self.pryout_strength())
        return results

    def governing_tension_strength(self) -> AnchorCheckResult:
        """Return the governing (minimum φSn) tension limit state."""
        return min(self._tension_results(), key=lambda r: r.phi_Sn)

    def governing_shear_strength(self) -> AnchorCheckResult:
        """Return the governing (minimum φSn) shear limit state."""
        return min(self._shear_results(), key=lambda r: r.phi_Sn)

    def stretch_length_check(self) -> Optional[AnchorCheckResult]:
        """
        Stretch length adequacy for seismic ductile designs — ACI 318-19 Section 17.10.5.3.

        For SDC C–F where anchor yielding is relied upon for ductility, the
        frictionally isolated length must be ≥ 8·d_a.  Returns None if not in
        seismic SDC C–F.  coupler_depth is used as the isolated stretch length when
        provided; otherwise h_ef is used as a conservative proxy.
        """
        if self.sdc not in ("C", "D", "E", "F"):
            return None
        L_stretch = self.coupler_depth if self.coupler_depth is not None else self.h_ef
        L_min = 8.0 * self.d_a
        # phi_Sn = available length (capacity), demand = required minimum
        # OK when L_stretch >= L_min (DCR = L_min/L_stretch <= 1.0)
        return AnchorCheckResult(
            label="Stretch length (seismic)",
            reference="ACI 318-19 Section 17.10.5.3",
            N_n=0.0,
            V_n=0.0,
            phi=1.0,
            phi_Sn=L_stretch,
            demand=L_min,
            is_ratio=True,
        )

    def check_all(self) -> dict:
        """
        Run all applicable limit-state checks.

        Returns a dict mapping check label to AnchorCheckResult.
        Interaction check is included only when both N_ua and V_ua are nonzero.
        Stretch length check is included for SDC C–F.
        """
        results = {}
        for r in self._tension_results():
            results[r.label] = r
        for r in self._shear_results():
            results[r.label] = r
        if self.N_ua > 0 and self.V_ua > 0:
            r = self.tension_shear_interaction()
            results[r.label] = r
        sl = self.stretch_length_check()
        if sl is not None:
            results[sl.label] = sl
        return results

    def summary(self) -> str:
        """Print a formatted table of all limit-state checks."""
        header = f"{'Limit State':<35} {'Ref':<28} {'φSn (kip)':>10} {'Demand':>10} {'DCR':>7} {'Status':>6}"
        separator = "-" * len(header)
        lines = [separator, header, separator]
        for r in self.check_all().values():
            if r.is_ratio:
                phi_str   = f"{'≤1.20':>10}"
                dem_str   = f"{r.demand:>10.3f}"
            else:
                phi_str   = f"{r.phi_Sn/1000:>10.2f}"
                dem_str   = f"{r.demand/1000:>10.2f}"
            lines.append(
                f"{r.label:<35} {r.reference:<28} "
                f"{phi_str} {dem_str} "
                f"{r.dcr:>7.3f} {'OK' if r.ok else 'NG':>6}"
            )
        lines.append(separator)
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # AASHTO / highway structure helpers
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_circular(
        cls,
        n_bolts: int,
        bolt_circle_radius: float,
        f_c: float,
        h_a: float,
        d_a: float,
        h_ef: float,
        f_ya: float,
        f_uta: float,
        M_u: Optional[float] = None,
        P_u: float = 0.0,
        V_u: Optional[float] = None,
        T_u: float = 0.0,
        **kwargs,
    ) -> "AnchorBolts":
        """
        Constructor for circular bolt patterns — highway poles, luminaires, signs.

        Parameters
        ----------
        n_bolts : int
            Total number of anchor rods on the bolt circle.
        bolt_circle_radius : float
            Radius of the bolt circle (in), measured to bolt centerlines.
        M_u : float, optional
            Factored overturning moment at pole base (lb·in). When provided,
            bolt demands are computed automatically via bolt_demands_from_pole().
        P_u : float, optional
            Factored axial load; positive = uplift/tension (lb). Used with M_u.
        V_u : float, optional
            Factored base shear at pole base (lb). When provided, shear demands
            are computed automatically via bolt_demands_from_pole().
        T_u : float, optional
            Factored torsional moment at pole base (lb·in). Used with V_u.
        **kwargs
            Any additional AnchorBolts parameters (shaft_radius, sdc, N_ua, …).
            Explicit N_ua/V_ua in kwargs take precedence over computed values.

        Notes
        -----
        `n` is stored as n_y=n_bolts, n_x=1.  Projected areas _A_Nc and _A_Vc
        use annular/circular geometry automatically when bolt_circle_radius is set.
        Supply shaft_radius to auto-derive c_a1 for drilled shaft applications.
        """
        if M_u is not None or V_u is not None:
            n_ua_auto, v_ua_auto = cls.bolt_demands_from_pole(
                n_bolts=n_bolts,
                bolt_circle_radius=bolt_circle_radius,
                M_u=M_u or 0.0,
                P_u=P_u,
                V_u=V_u or 0.0,
                T_u=T_u,
            )
            kwargs.setdefault("N_ua", n_ua_auto)
            kwargs.setdefault("V_ua", v_ua_auto)

        return cls(
            f_c=f_c,
            h_a=h_a,
            d_a=d_a,
            h_ef=h_ef,
            f_ya=f_ya,
            f_uta=f_uta,
            n_x=1,
            n_y=n_bolts,
            bolt_circle_radius=bolt_circle_radius,
            **kwargs,
        )

    @staticmethod
    def bolt_demands_from_pole(
        n_bolts: int,
        bolt_circle_radius: float,
        M_u: float,
        P_u: float = 0.0,
        V_u: float = 0.0,
        T_u: float = 0.0,
    ) -> tuple:
        """
        Max individual bolt demands from global AASHTO pole reactions.

        Uses the elastic circular bolt group method (AASHTO LTS-1 / AISC Design
        Guide 1).  All inputs in consistent units (lb and in).

        Parameters
        ----------
        n_bolts : int
            Number of anchor rods on the bolt circle.
        bolt_circle_radius : float
            Radius from pole centroid to bolt centerlines (in).
        M_u : float
            Factored overturning moment at base (lb·in).
        P_u : float
            Factored axial load; positive = uplift/tension (lb).
        V_u : float
            Factored in-plane shear at base (lb).
        T_u : float
            Factored torsional moment at base (lb·in).

        Returns
        -------
        (N_ua_max, V_ua_max) : tuple[float, float]
            Maximum tension demand (lb) and shear demand (lb) on a single bolt.

        Notes
        -----
        Tension from moment: N_M = 2·M_u / (n·r)  [elastic, Σy² = n·r²/2]
        Axial share:         N_P = P_u / n
        Shear from V_u:      V_v = V_u / n
        Shear from torsion:  V_t = T_u / (n·r)  [all bolts at equal radius]
        Final:               N_ua_max = max(0, N_M + N_P)
                             V_ua_max = V_v + V_t  (conservative, additive)
        """
        r = bolt_circle_radius
        n = n_bolts
        N_moment = 2.0 * M_u / (n * r)
        N_axial  = P_u / n
        N_ua_max = max(0.0, N_moment + N_axial)
        V_direct  = V_u / n
        V_torsion = T_u / (n * r)
        V_ua_max  = V_direct + V_torsion
        return N_ua_max, V_ua_max

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 4 — Visualisation & digital inputs
    # ─────────────────────────────────────────────────────────────────────────

    def plot(self, title: str = "", figsize: tuple = (8, 7)):
        """
        2D plan-view diagram of the anchor group.

        Draws the concrete boundary, bolt locations, the 1.5·h_ef tension breakout
        zone (dashed red), and demand arrows for V_ua and N_ua.

        Parameters
        ----------
        title : str
            Optional plot title; defaults to repr(self).
        figsize : tuple
            Matplotlib figure size in inches, default (8, 7).

        Returns
        -------
        (fig, ax) : tuple
            Matplotlib Figure and Axes objects for further customisation or saving.
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
        except ImportError:
            raise ImportError(
                "matplotlib is required for plot(). Install with: pip install matplotlib"
            )

        fig, ax = plt.subplots(figsize=figsize)

        cone = 1.5 * self.h_ef
        r_bc = self._bolt_circle_radius

        # ── Display extents ──────────────────────────────────────────────────
        base = r_bc + cone if r_bc else max(
            cone,
            (self.n_x - 1) * self.s_x / 2 + cone,
            (self.n_y - 1) * self.s_y / 2 + cone,
        )
        c1  = self.c_a1 if math.isfinite(self.c_a1) else base
        c2  = self.c_a2 if math.isfinite(self.c_a2) else base
        far = max(base, c1)  # extent on the "far" (non-edge) side of the group

        # ── Concrete boundary ────────────────────────────────────────────────
        conc = mpatches.Rectangle(
            (-c1, -c2), c1 + far, 2 * c2,
            linewidth=2, edgecolor="#555555", facecolor="#e8e8e8", zorder=1,
        )
        ax.add_patch(conc)

        # ── Bolt locations ───────────────────────────────────────────────────
        bolt_r = max(self.d_a / 2, cone * 0.03)  # visible even for tiny diameters
        if r_bc is not None:
            for k in range(self.n):
                theta = 2 * math.pi * k / self.n
                bx, by = r_bc * math.cos(theta), r_bc * math.sin(theta)
                ax.add_patch(mpatches.Circle((bx, by), bolt_r,
                                             color="steelblue", zorder=5))
            # Bolt circle reference (thin dashed)
            ax.add_patch(mpatches.Circle((0, 0), r_bc, fill=False,
                                         linestyle=":", edgecolor="steelblue",
                                         linewidth=0.8, zorder=2))
        else:
            for i in range(self.n_x):
                for j in range(self.n_y):
                    bx = (i - (self.n_x - 1) / 2.0) * self.s_x
                    by = (j - (self.n_y - 1) / 2.0) * self.s_y
                    ax.add_patch(mpatches.Circle((bx, by), bolt_r,
                                                 color="steelblue", zorder=5))

        # ── Tension breakout zone (1.5·h_ef) ────────────────────────────────
        if r_bc is not None:
            ext  = min(self.c_a_min if math.isfinite(self.c_a_min) else cone, cone)
            R_out = r_bc + ext
            R_in  = max(0.0, r_bc - cone)
            ax.add_patch(mpatches.Circle((0, 0), R_out, fill=False,
                                         linestyle="--", edgecolor="crimson",
                                         linewidth=1.5, zorder=3))
            if R_in > 0:
                ax.add_patch(mpatches.Circle((0, 0), R_in, fill=False,
                                             linestyle="--", edgecolor="crimson",
                                             linewidth=1.5, zorder=3))
        else:
            ext  = min(self.c_a_min if math.isfinite(self.c_a_min) else cone, cone)
            xh   = (self.n_x - 1) * self.s_x / 2.0 + ext
            yh   = (self.n_y - 1) * self.s_y / 2.0 + ext
            ax.add_patch(mpatches.Rectangle(
                (-xh, -yh), 2 * xh, 2 * yh,
                fill=False, linestyle="--", edgecolor="crimson",
                linewidth=1.5, zorder=3,
            ))

        # ── Near-edge lines and labels ───────────────────────────────────────
        if math.isfinite(self.c_a1):
            ax.axvline(x=-c1, color="#333333", linewidth=2.0, zorder=4)
            ax.text(-c1 - cone * 0.05, -c2 * 0.85,
                    f'c_a1 = {self.c_a1:.1f}"',
                    ha="right", fontsize=8, color="#333333")
        if math.isfinite(self.c_a2):
            for sign in (+1, -1):
                ax.axhline(y=sign * c2, color="#333333", linewidth=2.0, zorder=4)
            ax.text(far * 0.7, c2 + cone * 0.05,
                    f'c_a2 = {self.c_a2:.1f}"', fontsize=8, color="#333333")

        # ── Shear demand arrow (→) ───────────────────────────────────────────
        if self.V_ua > 0:
            arrow_len = far * 0.35
            ax.annotate(
                "", xy=(arrow_len, 0), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="darkorange",
                                lw=2.2, mutation_scale=16),
                zorder=6,
            )
            ax.text(arrow_len + cone * 0.05, bolt_r * 2.5,
                    f"Vu = {self.V_ua / 1000:.1f} k",
                    color="darkorange", fontsize=8)

        # ── Tension demand arrow (↑ out of plane, shown as ⊕ label) ─────────
        if self.N_ua > 0:
            ax.text(0, 0, "⊕", ha="center", va="center",
                    fontsize=14, color="green", fontweight="bold", zorder=7)
            ax.text(bolt_r * 3, c2 * 0.5,
                    f"Nu = {self.N_ua / 1000:.1f} k",
                    color="green", fontsize=8)

        # ── Axis / legend ────────────────────────────────────────────────────
        pad = cone * 0.25
        ax.set_xlim(-c1 - pad, far + pad)
        ax.set_ylim(-c2 - pad, c2 + pad)
        ax.set_aspect("equal")
        ax.set_xlabel('x — shear direction (in)')
        ax.set_ylabel('y — perpendicular (in)')
        ax.set_title(title or repr(self))
        ax.grid(True, alpha=0.3)

        legend_handles = [
            mpatches.Patch(facecolor="#e8e8e8", edgecolor="#555555", label="Concrete"),
            mpatches.Patch(facecolor="steelblue", label="Anchor rod"),
            mpatches.Patch(fill=False, edgecolor="crimson", linestyle="--",
                           label=f'1.5·h_ef = {cone:.1f}"'),
        ]
        ax.legend(handles=legend_handles, loc="upper left", fontsize=8)
        fig.tight_layout()
        return fig, ax

    @classmethod
    def from_dxf(
        cls,
        path: str,
        f_c: float,
        h_a: float,
        h_ef: float,
        f_ya: float,
        f_uta: float,
        bolts_layer: str = "BOLTS",
        concrete_layer: str = "CONCRETE",
        **kwargs,
    ) -> "AnchorBolts":
        """
        Build an AnchorBolts instance by parsing geometry from a DXF file.

        Reads two layers from the DXF modelspace:

        * ``bolts_layer`` (default ``"BOLTS"``) — CIRCLE entities whose centres
          define bolt locations and whose radius gives anchor_radius = d_a / 2.
        * ``concrete_layer`` (default ``"CONCRETE"``) — one LWPOLYLINE (or
          POLYLINE) whose vertices define the concrete boundary.  Edge distances
          c_a1 (shear direction) and c_a2 (perpendicular) are derived from the
          minimum distances from the bolt-group centroid to the boundary edges,
          classified by edge orientation.

        Bolt pattern detection:

        * **Circular** — all bolts lie within 10 % of the same radius from the
          centroid.  Delegates to ``from_circular()``.
        * **Rectangular** — grid spacing is inferred from the sorted unique
          x/y coordinates of the bolt positions.

        Parameters
        ----------
        path : str
            Absolute or relative path to the ``.dxf`` file.
        f_c, h_a, h_ef, f_ya, f_uta : float
            Material and geometry properties not derivable from CAD.
        bolts_layer, concrete_layer : str
            Layer names to query (case-sensitive, DXF convention is UPPERCASE).
        **kwargs
            Additional ``AnchorBolts`` keyword arguments (N_ua, V_ua, sdc, …).

        Returns
        -------
        AnchorBolts
        """
        try:
            import ezdxf
        except ImportError:
            raise ImportError(
                "ezdxf is required for from_dxf(). Install with: pip install ezdxf"
            )

        doc = ezdxf.readfile(path)
        msp = doc.modelspace()

        # ── Extract bolt positions (CIRCLE entities) ─────────────────────────
        bolt_centers: list = []
        bolt_radius: Optional[float] = None
        for ent in msp.query(f'CIRCLE[layer=="{bolts_layer}"]'):
            bolt_centers.append((ent.dxf.center.x, ent.dxf.center.y))
            if bolt_radius is None:
                bolt_radius = ent.dxf.radius

        if not bolt_centers:
            raise ValueError(
                f"No CIRCLE entities found on layer '{bolts_layer}' in {path!r}"
            )

        n = len(bolt_centers)
        d_a = (bolt_radius or 0.5) * 2.0

        # Centroid of bolt group
        cx = sum(p[0] for p in bolt_centers) / n
        cy = sum(p[1] for p in bolt_centers) / n
        rel = [(x - cx, y - cy) for x, y in bolt_centers]

        # ── Detect circular vs rectangular ───────────────────────────────────
        radii = [math.hypot(x, y) for x, y in rel]
        r_mean = sum(radii) / len(radii) if radii else 0.0
        r_std  = math.sqrt(sum((r - r_mean) ** 2 for r in radii) / len(radii)) \
                 if len(radii) > 1 else 0.0
        is_circular = (r_mean > 1e-6) and (r_std < 0.10 * r_mean)

        # ── Extract concrete boundary (LWPOLYLINE) ───────────────────────────
        c_a1 = float("inf")
        c_a2 = float("inf")
        for ent in msp.query(f'LWPOLYLINE[layer=="{concrete_layer}"]'):
            pts = [(v[0], v[1]) for v in ent.get_points()]
            if len(pts) < 3:
                continue
            for i in range(len(pts)):
                p1 = pts[i]
                p2 = pts[(i + 1) % len(pts)]
                dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                seg_len = math.hypot(dx, dy)
                if seg_len < 1e-9:
                    continue
                t = max(0.0, min(1.0, ((cx - p1[0]) * dx + (cy - p1[1]) * dy)
                                 / seg_len ** 2))
                px, py = p1[0] + t * dx, p1[1] + t * dy
                dist = math.hypot(cx - px, cy - py)
                # Classify by edge orientation: horizontal edge → c_a2 (y-normal)
                #                              vertical edge   → c_a1 (x-normal)
                if abs(dx) > abs(dy):
                    c_a2 = min(c_a2, dist)
                else:
                    c_a1 = min(c_a1, dist)

        # ── Build instance ───────────────────────────────────────────────────
        if is_circular:
            return cls.from_circular(
                n_bolts=n,
                bolt_circle_radius=r_mean,
                f_c=f_c, h_a=h_a, d_a=d_a,
                h_ef=h_ef, f_ya=f_ya, f_uta=f_uta,
                c_a1=c_a1, c_a2=c_a2,
                **kwargs,
            )

        # Rectangular: reconstruct grid from sorted unique positions
        ROUND = 2  # decimal places for deduplication
        xs = sorted({round(x, ROUND) for x, _ in rel})
        ys = sorted({round(y, ROUND) for _, y in rel})
        n_x = len(xs)
        n_y = len(ys)
        s_x = (xs[-1] - xs[0]) / (n_x - 1) if n_x > 1 else 0.0
        s_y = (ys[-1] - ys[0]) / (n_y - 1) if n_y > 1 else 0.0
        return cls(
            f_c=f_c, h_a=h_a, d_a=d_a, h_ef=h_ef,
            f_ya=f_ya, f_uta=f_uta,
            n_x=n_x, n_y=n_y, s_x=s_x, s_y=s_y,
            c_a1=c_a1, c_a2=c_a2,
            **kwargs,
        )

    def __repr__(self) -> str:
        return (
            f"AnchorBolts(n={self.n}, d_a={self.d_a}in, h_ef={self.h_ef}in, "
            f"f_c={self.f_c:.0f}psi, f_uta={self.f_uta:.0f}psi)"
        )


# ──────────────────────────────────────────────────────────────────────────────
# ACI 318-19 Section 17.11 — Shear Lug Checks
# ──────────────────────────────────────────────────────────────────────────────

class ShearLugCheck:
    """
    ACI 318-19 Section 17.11 shear lug design checks.

    Shear lugs transfer in-plane shear by bearing against concrete rather than
    through anchor rod bending.  Two limit states are checked:

    1. Bearing strength of lug (17.11.2.1):
       V_brg,sl = n_sl × 1.7 × λ_a × f_c × A_ef,sl

    2. Concrete breakout of lug (17.11.3.2.1):
       V_b,sl = 3.5 × λ_a × √f_c × A_ef,sl^0.5 × h_sl^1.5
       Full breakout: V_cb,sl = (A_Vc,sl / A_Vco,sl) × psi_ed × V_b,sl

    All lengths in inches, forces in pounds (lb), stresses in psi.

    Parameters
    ----------
    f_c : float
        Specified concrete compressive strength (psi), capped at 10,000 psi.
    h_a : float
        Member thickness in the direction of applied shear (in).
    n_sl : int
        Number of shear lugs.
    A_ef_sl : float
        Effective bearing area of a single shear lug (in²). This is the
        projected bearing face area perpendicular to applied shear, excluding
        any grout pocket area.
    h_sl : float
        Height of shear lug above the concrete or grout surface (in).
    c_a1 : float
        Edge distance from the lug to the nearest free edge in the direction
        of applied shear (in). Use float('inf') if no near edge.
    c_a2 : float
        Edge distance perpendicular to applied shear (in).
        Use float('inf') if no near edge.
    lambda_a : float
        Lightweight concrete factor (1.0 for normalweight).
    has_supp_reinf : bool
        True if supplementary reinforcement is provided (Condition A, φ=0.75).
    V_ua : float
        Factored shear demand on the lug group (lb).
    sdc : str
        Seismic Design Category; applies 0.75 seismic reduction for SDC C–F.
    """

    def __init__(
        self,
        f_c: float,
        h_a: float,
        n_sl: int,
        A_ef_sl: float,
        h_sl: float,
        c_a1: float = float("inf"),
        c_a2: float = float("inf"),
        lambda_a: float = 1.0,
        has_supp_reinf: bool = False,
        V_ua: float = 0.0,
        sdc: str = "A",
    ):
        self.f_c = min(f_c, 10_000)
        self.h_a = h_a
        self.n_sl = max(1, n_sl)
        self.A_ef_sl = A_ef_sl
        self.h_sl = h_sl
        self.c_a1 = c_a1
        self.c_a2 = c_a2
        self.lambda_a = lambda_a
        self.has_supp_reinf = has_supp_reinf
        self.V_ua = V_ua
        self.sdc = sdc.upper()

        self.phi = 0.75 if has_supp_reinf else 0.70

    @property
    def _phi_seismic(self) -> float:
        return 0.75 if self.sdc in ("C", "D", "E", "F") else 1.0

    def bearing_strength(self) -> AnchorCheckResult:
        """
        Bearing strength of shear lugs — ACI 318-19 Eq. 17.11.2.1.

        V_brg,sl = n_sl × 1.7 × λ_a × f_c × A_ef,sl
        """
        V_brg = self.n_sl * 1.7 * self.lambda_a * self.f_c * self.A_ef_sl
        phi_Vn = self.phi * self._phi_seismic * V_brg
        return AnchorCheckResult(
            label="Shear lug bearing",
            reference="ACI 318-19 Eq. 17.11.2.1",
            N_n=0.0,
            V_n=V_brg,
            phi=self.phi,
            phi_Sn=phi_Vn,
            demand=self.V_ua,
        )

    def breakout_strength(self) -> Optional[AnchorCheckResult]:
        """
        Concrete breakout strength of shear lug — ACI 318-19 Section 17.11.3.

        V_b,sl = 3.5 × λ_a × √f_c × A_ef,sl^0.5 × h_sl^1.5  (Eq. 17.11.3.2.1)
        Returns None when c_a1 is infinite (no near edge).
        """
        if not math.isfinite(self.c_a1):
            return None

        # Basic breakout strength (Eq. 17.11.3.2.1)
        V_b_sl = (3.5 * self.lambda_a * math.sqrt(self.f_c)
                  * math.sqrt(self.A_ef_sl) * self.h_sl ** 1.5)

        # Reference area (single lug, deep member) — same form as anchor
        A_Vco_sl = 4.5 * self.c_a1 ** 2

        # Projected area
        height = min(1.5 * self.c_a1, self.h_a)
        c_a2_eff = min(self.c_a2, 1.5 * self.c_a1) if math.isfinite(self.c_a2) else 1.5 * self.c_a1
        A_Vc_sl = height * 2.0 * c_a2_eff

        # Edge factor
        if math.isfinite(self.c_a2) and self.c_a2 < 1.5 * self.c_a1:
            psi_ed = 0.7 + 0.3 * self.c_a2 / (1.5 * self.c_a1)
        else:
            psi_ed = 1.0

        V_cb_sl = (A_Vc_sl / A_Vco_sl) * psi_ed * V_b_sl
        phi_Vn = self.phi * self._phi_seismic * V_cb_sl
        return AnchorCheckResult(
            label="Shear lug breakout",
            reference="ACI 318-19 Eq. 17.11.3.2.1",
            N_n=0.0,
            V_n=V_cb_sl,
            phi=self.phi,
            phi_Sn=phi_Vn,
            demand=self.V_ua,
        )

    def check_all(self) -> dict:
        """Run bearing and breakout checks; return dict of label → AnchorCheckResult."""
        results = {}
        for r in [self.bearing_strength(), self.breakout_strength()]:
            if r is not None:
                results[r.label] = r
        return results

    def summary(self) -> str:
        """Formatted table of shear lug limit-state checks."""
        header = f"{'Limit State':<25} {'Ref':<32} {'φVn (kip)':>10} {'Demand':>10} {'DCR':>7} {'Status':>6}"
        sep = "-" * len(header)
        lines = [sep, header, sep]
        for r in self.check_all().values():
            lines.append(
                f"{r.label:<25} {r.reference:<32} "
                f"{r.phi_Sn/1000:>10.2f} {r.demand/1000:>10.2f} "
                f"{r.dcr:>7.3f} {'OK' if r.ok else 'NG':>6}"
            )
        lines.append(sep)
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"ShearLugCheck(n_sl={self.n_sl}, A_ef={self.A_ef_sl}in², "
            f"h_sl={self.h_sl}in, f_c={self.f_c:.0f}psi)"
        )
