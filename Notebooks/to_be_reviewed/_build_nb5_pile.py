"""Build Notebook 5: ODOT Pile Foundation Design (BDM 305)"""
import json
import uuid


def mk(cell_type, source):
    lines = source.split("\n")
    src = [l + "\n" for l in lines[:-1]] + [lines[-1]]
    cell = {"cell_type": cell_type, "metadata": {}, "source": src, "id": str(uuid.uuid4())[:8]}
    if cell_type == "code":
        cell["outputs"] = []
        cell["execution_count"] = None
    return cell


cells = []

# Cell 1: Title
cells.append(mk("markdown", """# ODOT Pile Foundation Design
**BDM Section 305**

This notebook computes driven pile foundation design per the ODOT Bridge
Design Manual (BDM) Section 305 and AASHTO LRFD Section 10.7. It covers:

- Factored axial load computation (Strength I)
- Pile bearing resistance and Ultimate Bearing Value (UBV)
- Pile length estimation from SPT borings (Meyerhof method)
- Downdrag / negative skin friction (BDM 305.3.2.2)
- Structural capacity check for HP piles
- Settlement check (elastic shortening + group settlement)
- Plan note generation per BDM 600"""))

# Cell 2: References
cells.append(mk("markdown", """---
## References
- ODOT Bridge Design Manual (BDM), Section 305 - Pile Foundations
- AASHTO LRFD Bridge Design Specifications, 9th Edition, Section 10.7
- FHWA-NHI-16-009: Design and Construction of Driven Pile Foundations
- FHWA-SA-97-070: Design and Construction of Driven Pile Foundations (Vol. I & II)"""))

# Cell 3: Imports
cells.append(mk("code", """# ============================================================
# Imports
# ============================================================
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

# Civilpy load factors (optional)
try:
    from civilpy.structural.aashto.load_definitions import load_combinations
    CIVILPY_AVAILABLE = True
except ImportError:
    CIVILPY_AVAILABLE = False

# ODOT systems (optional)
try:
    from ODOT import BrRBridge, MidasBridge
    ODOT_AVAILABLE = True
except ImportError:
    ODOT_AVAILABLE = False
    print("ODOT.py not available. Manual data entry required.")

print("Imports loaded.")"""))

# Cell 4: Section 1 heading
cells.append(mk("markdown", """---
## 1. Project & Substructure Input

Define the pile design input parameters. Pile types follow ODOT standard
designations. Unfactored loads at the substructure can be entered manually
or pulled from Midas/BrR if available."""))

# Cell 5: Section 1 code
cells.append(mk("code", """# ============================================================
# USER INPUT: Pile Design Parameters
# ============================================================

class PileDesignInput(BaseModel):
    \"\"\"Input parameters for pile foundation design per BDM 305.\"\"\"
    sfn: str = ""                          # Structure File Number
    substructure_id: str = "Pier 1"        # Abutment or pier ID
    pile_type: str = "HP14x73"             # HP10x42, HP12x53, HP14x73, pipe12, pipe14, concrete12, concrete14
    fy: float = 50.0                       # Yield strength (ksi), 50 ksi for HP piles
    num_piles: int = 8                     # Number of piles in the group
    pile_spacing: float = 3.0              # Center-to-center spacing (ft)
    axial_DL: float = 0.0                  # Unfactored dead load reaction (kips)
    axial_LL: float = 0.0                  # Unfactored live load reaction (kips)
    lateral_load: float = 0.0              # Lateral load at pile cap (kips)
    moment: float = 0.0                    # Moment at pile cap (kip-ft)
    scour_depth: float = 0.0              # Design scour depth (ft)

# USER INPUT
pile_input = PileDesignInput(
    sfn="",
    substructure_id="Pier 1",
    pile_type="HP14x73",
    fy=50.0,
    num_piles=8,
    pile_spacing=3.0,
    axial_DL=600.0,    # kips (unfactored DC + DW)
    axial_LL=250.0,    # kips (unfactored LL without IM)
    lateral_load=30.0,
    moment=150.0,
    scour_depth=0.0,
)

# Optional: Pull reactions from Midas or BrR
if pile_input.sfn and ODOT_AVAILABLE:
    try:
        midas_bridge = MidasBridge(pile_input.sfn)
        print(f"Midas reactions available for SFN {pile_input.sfn}")
    except Exception as e:
        print(f"Midas lookup failed: {e}")
    try:
        brr_bridge = BrRBridge(pile_input.sfn)
        print(f"BrR data available for SFN {pile_input.sfn}")
    except Exception as e:
        print(f"BrR lookup failed: {e}")
else:
    if not pile_input.sfn:
        print("Enter SFN above to pull reactions from Midas/BrR, or use manual input.")

print(f"Pile type: {pile_input.pile_type}")
print(f"Number of piles: {pile_input.num_piles}")
print(f"Unfactored DL: {pile_input.axial_DL} kips, LL: {pile_input.axial_LL} kips")"""))

# Cell 6: Section 2 heading
cells.append(mk("markdown", """---
## 2. Soil Profile

Define the soil boring log with SPT N-values. Each layer includes depth,
description, N-value, unit weight, and strength parameters. The soil profile
drives the pile length estimation and capacity calculation."""))

# Cell 7: Section 2 code
cells.append(mk("code", """# ============================================================
# Soil Profile Input
# ============================================================

class SoilLayer(BaseModel):
    \"\"\"Single soil layer from boring log.\"\"\"
    depth_top: float             # Top of layer (ft below ground)
    depth_bot: float             # Bottom of layer (ft below ground)
    description: str             # e.g. "Medium dense sand", "Stiff clay"
    N_value: int                 # SPT blow count (N60)
    unit_weight: float           # Total unit weight (pcf)
    friction_angle: Optional[float] = None   # Drained friction angle (degrees)
    cohesion: Optional[float] = None         # Undrained cohesion Su (psf)
    is_cohesive: bool = False                # True for clay/silt, False for sand/gravel

# USER INPUT: Soil boring log
soil_profile: List[SoilLayer] = [
    SoilLayer(depth_top=0,  depth_bot=5,  description="Loose fill",          N_value=4,  unit_weight=110, friction_angle=28, is_cohesive=False),
    SoilLayer(depth_top=5,  depth_bot=12, description="Soft clay",           N_value=3,  unit_weight=105, cohesion=300,      is_cohesive=True),
    SoilLayer(depth_top=12, depth_bot=20, description="Medium dense sand",   N_value=15, unit_weight=120, friction_angle=32, is_cohesive=False),
    SoilLayer(depth_top=20, depth_bot=30, description="Stiff clay",          N_value=12, unit_weight=118, cohesion=1200,     is_cohesive=True),
    SoilLayer(depth_top=30, depth_bot=45, description="Dense sand",          N_value=30, unit_weight=125, friction_angle=36, is_cohesive=False),
    SoilLayer(depth_top=45, depth_bot=60, description="Very dense sand/gravel", N_value=50, unit_weight=130, friction_angle=40, is_cohesive=False),
]

print(f"Soil profile: {len(soil_profile)} layers, total depth {soil_profile[-1].depth_bot} ft")
for layer in soil_profile:
    print(f"  {layer.depth_top:5.1f} - {layer.depth_bot:5.1f} ft: {layer.description:25s} N={layer.N_value}")"""))

# Cell 8: SPT plot
cells.append(mk("code", """# ============================================================
# Plot SPT N-value vs Depth
# ============================================================

fig, ax = plt.subplots(figsize=(5, 8))

for layer in soil_profile:
    depth_mid = (layer.depth_top + layer.depth_bot) / 2
    thickness = layer.depth_bot - layer.depth_top
    ax.barh(depth_mid, layer.N_value, height=thickness * 0.8, color="steelblue", edgecolor="black")
    ax.text(layer.N_value + 1, depth_mid, f"{layer.description}", va="center", fontsize=8)

ax.set_xlabel("SPT N-value (blows/ft)")
ax.set_ylabel("Depth (ft)")
ax.set_title("SPT Boring Log")
ax.invert_yaxis()
ax.set_xlim(0, max(l.N_value for l in soil_profile) + 15)
ax.grid(axis="x", alpha=0.3)
plt.tight_layout()
plt.show()"""))

# Cell 9: Section 3 heading
cells.append(mk("markdown", """---
## 3. Factored Axial Load (BDM 305.3)

Strength I load combination per AASHTO LRFD Table 3.4.1-1:

$$P_u = 1.25 \\cdot DC + 1.50 \\cdot DW + 1.75 \\cdot LL \\cdot (1 + IM)$$

Per-pile factored load:

$$Q_{p} = \\frac{P_u}{n_{piles}}$$"""))

# Cell 10: Section 3 code
cells.append(mk("code", """# ============================================================
# Factored Axial Load (Strength I)
# ============================================================

# Load factors (AASHTO LRFD Table 3.4.1-1, Strength I)
GAMMA_DC = 1.25
GAMMA_DW = 1.50
GAMMA_LL = 1.75
IM = 0.33  # Dynamic load allowance

# For simplicity, treat axial_DL as combined DC + DW with gamma_DC
# In practice, separate DC and DW components
Pu = GAMMA_DC * pile_input.axial_DL + GAMMA_LL * pile_input.axial_LL * (1 + IM)

# Per-pile factored load
Qp_factored = Pu / pile_input.num_piles

print(f"Factored total load Pu = {Pu:.1f} kips")
print(f"Number of piles: {pile_input.num_piles}")
print(f"Factored load per pile Qp = {Qp_factored:.1f} kips")
print(f"Factored load per pile = {Qp_factored / 2:.1f} tons")"""))

# Cell 11: Section 4 heading
cells.append(mk("markdown", """---
## 4. Pile Bearing Resistance (BDM Table 305.3.2-1)

Resistance factors for driven piles per BDM Table 305.3.2-1:

| Resistance Determination Method | Resistance Factor (phi) |
|---|---|
| Static analysis (alpha/beta method) | 0.45 |
| Dynamic analysis (WEAP) | 0.65 |
| Dynamic testing (PDA + CAPWAP) | 0.75 |
| Static load test | 0.80 |

The Ultimate Bearing Value (UBV) is the nominal resistance required at the
pile tip to achieve the factored design load:

$$Q_n = \\frac{Q_p}{\\phi_{stat}}$$"""))

# Cell 12: Section 4 code
cells.append(mk("code", """# ============================================================
# Pile Bearing Resistance & UBV
# ============================================================

# BDM Table 305.3.2-1 resistance factors
PHI_RESISTANCE = {
    "static_analysis": 0.45,
    "WEAP": 0.65,
    "PDA_CAPWAP": 0.75,
    "static_load_test": 0.80,
}


def compute_ubv(Qp_factored, phi_stat):
    \"\"\"Compute Ultimate Bearing Value (nominal resistance required).

    Args:
        Qp_factored: Factored load per pile (kips)
        phi_stat: Resistance factor from BDM Table 305.3.2-1

    Returns:
        Qn_required: Nominal resistance required (kips) = UBV
    \"\"\"
    Qn_required = Qp_factored / phi_stat
    return Qn_required


# Compute UBV for each verification method
print("Ultimate Bearing Value (UBV) for each resistance method:")
print(f"  Factored load per pile: {Qp_factored:.1f} kips ({Qp_factored/2:.1f} tons)")
print()
ubv_results = {}
for method, phi in PHI_RESISTANCE.items():
    ubv = compute_ubv(Qp_factored, phi)
    ubv_results[method] = ubv
    print(f"  {method:25s}: phi = {phi:.2f}, UBV = {ubv:.1f} kips ({ubv/2:.1f} tons)")

# Select the resistance method for design
# Default to WEAP (most common for ODOT projects)
design_method = "WEAP"
phi_design = PHI_RESISTANCE[design_method]
UBV = ubv_results[design_method]

print(f"\\nDesign method: {design_method} (phi = {phi_design})")
print(f"Design UBV = {UBV:.1f} kips ({UBV/2:.1f} tons)")"""))

# Cell 13: Section 5 heading
cells.append(mk("markdown", """---
## 5. Pile Length Estimation from SPT (Meyerhof Method)

Estimate pile capacity vs. depth using the Meyerhof (1976) SPT-based method:

**End bearing (sand):**
$$q_p = 0.8 \\cdot N_{avg} \\cdot A_p \\text{ (tsf)}, \\quad \\leq 4N \\text{ (tsf)}$$

**End bearing (clay):**
$$q_p = 9 \\cdot S_u, \\quad S_u \\approx N/4 \\text{ (ksf, soft)}, \\quad N/8 \\text{ (ksf, stiff)}$$

**Skin friction (sand):**
$$f_s = \\frac{N}{50} \\text{ (tsf per unit area)}$$

**Skin friction (clay):**
$$f_s = \\alpha \\cdot S_u$$

where alpha is the adhesion factor from AASHTO Fig 10.7.3.8.6b-1.

Total nominal resistance: $Q_n = Q_p + Q_s$

The estimated pile length is where the capacity curve intersects the UBV line."""))

# Cell 14: Section 5 code - HP section properties
cells.append(mk("code", """# ============================================================
# HP Pile Section Properties
# ============================================================

HP_SECTIONS = {
    # pile_type: {A (in2), d (in), bf (in), tf (in), Ix (in4), Sx (in3), Zx (in3), perimeter (in)}
    "HP10x42": {"A": 12.4, "d": 9.70, "bf": 10.075, "tf": 0.420, "Ix": 210, "Sx": 43.4, "Zx": 48.3, "perimeter": 39.55},
    "HP12x53": {"A": 15.5, "d": 11.78, "bf": 12.045, "tf": 0.435, "Ix": 393, "Sx": 66.8, "Zx": 74.0, "perimeter": 47.65},
    "HP14x73": {"A": 21.4, "d": 13.61, "bf": 14.585, "tf": 0.505, "Ix": 729, "Sx": 107.0, "Zx": 118.0, "perimeter": 56.39},
    "pipe12":  {"A": 11.91, "d": 12.75, "bf": 12.75, "tf": 0.375, "Ix": 191.9, "Sx": 30.1, "Zx": 39.4, "perimeter": 40.05},
    "pipe14":  {"A": 16.05, "d": 14.00, "bf": 14.00, "tf": 0.375, "Ix": 372.8, "Sx": 53.3, "Zx": 69.1, "perimeter": 43.98},
    "concrete12": {"A": 144.0, "d": 12.0, "bf": 12.0, "tf": 12.0, "Ix": 1728, "Sx": 288, "Zx": 432, "perimeter": 48.0},
    "concrete14": {"A": 196.0, "d": 14.0, "bf": 14.0, "tf": 14.0, "Ix": 3201, "Sx": 457, "Zx": 686, "perimeter": 56.0},
}

# Get selected pile properties
pile_props = HP_SECTIONS[pile_input.pile_type]
A_pile = pile_props["A"]           # in^2
perimeter_pile = pile_props["perimeter"]  # in

print(f"Pile: {pile_input.pile_type}")
print(f"  Area A = {A_pile} in^2 ({A_pile/144:.3f} ft^2)")
print(f"  Perimeter = {perimeter_pile} in ({perimeter_pile/12:.2f} ft)")"""))

# Cell 15: Section 5 code - capacity calculation
cells.append(mk("code", """# ============================================================
# Pile Capacity vs Depth (Meyerhof Method)
# ============================================================

def estimate_pile_capacity(soil_profile, A_pile_ft2, perimeter_ft, depth_increment=1.0):
    \"\"\"Estimate pile capacity vs depth using Meyerhof SPT method.

    Args:
        soil_profile: List of SoilLayer objects
        A_pile_ft2: Pile tip area (ft^2)
        perimeter_ft: Pile perimeter (ft)
        depth_increment: Depth step for computation (ft)

    Returns:
        depths: array of depths (ft)
        Qp_array: end bearing capacity at each depth (kips)
        Qs_array: cumulative skin friction at each depth (kips)
        Qn_array: total nominal capacity at each depth (kips)
    \"\"\"
    max_depth = soil_profile[-1].depth_bot
    depths = np.arange(depth_increment, max_depth + depth_increment, depth_increment)

    Qp_array = np.zeros_like(depths)
    Qs_array = np.zeros_like(depths)

    Qs_cumulative = 0.0

    for i, depth in enumerate(depths):
        # Find the soil layer at this depth
        layer = None
        for sl in soil_profile:
            if sl.depth_top <= depth < sl.depth_bot:
                layer = sl
                break
        if layer is None:
            layer = soil_profile[-1]

        N = layer.N_value

        # End bearing at current depth
        if not layer.is_cohesive:
            # Sand: Meyerhof end bearing
            qp_tsf = 0.8 * N  # tsf (per unit area)
            qp_tsf = min(qp_tsf, 4.0 * N)  # upper limit
            Qp = qp_tsf * A_pile_ft2  # tons
            Qp = Qp * 2.0  # convert to kips
        else:
            # Clay: end bearing = 9 * Su
            if layer.cohesion is not None:
                Su_psf = layer.cohesion
            else:
                # Estimate Su from SPT: Su ~ N/8 ksf for stiff, N/4 for soft
                if N <= 8:
                    Su_psf = N * 250  # ~N/4 ksf = N*250 psf
                else:
                    Su_psf = N * 125  # ~N/8 ksf = N*125 psf
            Qp = 9.0 * (Su_psf / 1000.0) * A_pile_ft2  # kips (Su in ksf * ft2)

        Qp_array[i] = Qp

        # Skin friction for this depth increment
        if not layer.is_cohesive:
            # Sand: fs = N/50 tsf
            fs_tsf = N / 50.0
            dQs = fs_tsf * perimeter_ft * depth_increment * 2.0  # kips (tsf->kips: *2)
        else:
            # Clay: fs = alpha * Su
            if layer.cohesion is not None:
                Su_psf = layer.cohesion
            else:
                Su_psf = N * 250 if N <= 8 else N * 125
            Su_ksf = Su_psf / 1000.0
            # Alpha factor (simplified from AASHTO Fig 10.7.3.8.6b-1)
            if Su_ksf <= 0.5:
                alpha = 1.0
            elif Su_ksf <= 1.5:
                alpha = 1.0 - 0.5 * (Su_ksf - 0.5)
            else:
                alpha = 0.5
            dQs = alpha * Su_ksf * perimeter_ft * depth_increment  # kips

        Qs_cumulative += dQs
        Qs_array[i] = Qs_cumulative

    Qn_array = Qp_array + Qs_array
    return depths, Qp_array, Qs_array, Qn_array


# Compute capacity vs depth
A_pile_ft2 = A_pile / 144.0  # in^2 to ft^2
perimeter_ft = perimeter_pile / 12.0  # in to ft

depths, Qp_arr, Qs_arr, Qn_arr = estimate_pile_capacity(
    soil_profile, A_pile_ft2, perimeter_ft, depth_increment=1.0
)

print(f"Capacity computed from 1 ft to {depths[-1]:.0f} ft")
print(f"Max end bearing: {max(Qp_arr):.1f} kips")
print(f"Max skin friction: {max(Qs_arr):.1f} kips")
print(f"Max total capacity: {max(Qn_arr):.1f} kips")"""))

# Cell 16: Capacity vs depth plot
cells.append(mk("code", """# ============================================================
# Plot: Pile Capacity vs Depth with UBV Line
# ============================================================

fig, ax = plt.subplots(figsize=(8, 8))

ax.plot(Qn_arr, depths, "b-", linewidth=2, label="Total Capacity $Q_n$")
ax.plot(Qp_arr, depths, "r--", linewidth=1.5, label="End Bearing $Q_p$")
ax.plot(Qs_arr, depths, "g--", linewidth=1.5, label="Skin Friction $Q_s$")
ax.axvline(x=UBV, color="k", linewidth=2, linestyle="-.", label=f"UBV = {UBV:.0f} kips")

# Find intersection (estimated pile length)
est_length = None
for i in range(len(Qn_arr) - 1):
    if Qn_arr[i] < UBV <= Qn_arr[i + 1]:
        # Linear interpolation
        frac = (UBV - Qn_arr[i]) / (Qn_arr[i + 1] - Qn_arr[i])
        est_length = depths[i] + frac * (depths[i + 1] - depths[i])
        break

if est_length is not None:
    ax.plot(UBV, est_length, "ko", markersize=10, zorder=5)
    ax.annotate(f"Est. length = {est_length:.1f} ft",
                xy=(UBV, est_length), xytext=(UBV + 20, est_length - 3),
                arrowprops=dict(arrowstyle="->"), fontsize=10, fontweight="bold")
    print(f"Estimated pile length: {est_length:.1f} ft")
else:
    print("WARNING: Pile capacity does not reach UBV within the boring depth.")
    print("Extend the soil profile or select a different pile type.")

ax.set_xlabel("Capacity (kips)")
ax.set_ylabel("Depth (ft)")
ax.set_title("Pile Capacity vs Depth (Meyerhof SPT Method)")
ax.invert_yaxis()
ax.legend(loc="lower right")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()"""))

# Cell 17: Section 6 heading
cells.append(mk("markdown", """---
## 6. Downdrag / Negative Skin Friction (BDM 305.3.2.2)

Downdrag applies when:
- Fill placed > 5 ft above original ground
- Consolidating clay layers present
- Water table has been lowered

The beta method computes downdrag as:

$$DD = \\sum \\beta_z \\cdot \\sigma'_{v,z} \\cdot \\text{perimeter} \\cdot \\Delta L$$

for layers above the neutral plane.

| Soil Type | Beta Range |
|---|---|
| Soft clay | 0.20 - 0.25 |
| Medium clay | 0.25 - 0.35 |
| Stiff clay/sand | 0.35 - 0.50 |

The neutral plane is where pile settlement equals soil settlement.
Simplified: neutral plane at bottom of compressible layer.

Modified UBV per BDM C305.3.2-1:
$$Q_{p,total} = Q_{p,structural} + \\gamma_p \\cdot DD$$"""))

# Cell 18: Section 6 code
cells.append(mk("code", """# ============================================================
# Downdrag / Negative Skin Friction
# ============================================================

def compute_downdrag(soil_profile, perimeter_ft, neutral_plane_depth=None):
    \"\"\"Compute downdrag load using beta method (BDM 305.3.2.2).

    Args:
        soil_profile: List of SoilLayer objects
        perimeter_ft: Pile perimeter (ft)
        neutral_plane_depth: Depth of neutral plane (ft).
            If None, uses bottom of deepest compressible (cohesive) layer.

    Returns:
        DD: Downdrag force (kips)
        neutral_depth: Neutral plane depth used (ft)
    \"\"\"
    # Determine neutral plane (simplified: bottom of deepest cohesive layer)
    if neutral_plane_depth is None:
        neutral_plane_depth = 0.0
        for layer in soil_profile:
            if layer.is_cohesive:
                neutral_plane_depth = layer.depth_bot
    if neutral_plane_depth == 0:
        return 0.0, 0.0  # No downdrag

    # Beta values by soil type
    def get_beta(layer):
        if not layer.is_cohesive:
            return 0.40  # Sand/gravel
        else:
            if layer.N_value <= 4:
                return 0.22  # Soft clay
            elif layer.N_value <= 8:
                return 0.30  # Medium clay
            else:
                return 0.42  # Stiff clay

    DD = 0.0
    sigma_v = 0.0  # Running effective vertical stress

    for layer in soil_profile:
        if layer.depth_top >= neutral_plane_depth:
            break
        depth_top = layer.depth_top
        depth_bot = min(layer.depth_bot, neutral_plane_depth)
        thickness = depth_bot - depth_top
        if thickness <= 0:
            continue

        beta = get_beta(layer)
        gamma = layer.unit_weight / 1000.0  # pcf to kcf

        # Compute at midpoint of layer
        sigma_v_mid = sigma_v + gamma * thickness / 2.0  # ksf
        dDD = beta * sigma_v_mid * perimeter_ft * thickness  # kips

        DD += dDD
        sigma_v += gamma * thickness

    return DD, neutral_plane_depth


DD, neutral_depth = compute_downdrag(soil_profile, perimeter_ft)

print(f"Neutral plane depth: {neutral_depth:.1f} ft")
print(f"Downdrag force DD = {DD:.1f} kips per pile")

if DD > 0:
    # Modify UBV for downdrag (BDM C305.3.2-1)
    gamma_p_dd = 1.0  # Load factor for downdrag (typically 1.0 per BDM)
    Qp_total = Qp_factored + gamma_p_dd * DD
    UBV_with_DD = compute_ubv(Qp_total, phi_design)
    print(f"\\nModified factored load per pile: {Qp_total:.1f} kips")
    print(f"Modified UBV (with downdrag): {UBV_with_DD:.1f} kips ({UBV_with_DD/2:.1f} tons)")
else:
    UBV_with_DD = UBV
    print("No downdrag applicable.")"""))

# Cell 19: Section 7 heading
cells.append(mk("markdown", """---
## 7. Structural Capacity Check

For HP piles (fully embedded, no buckling):

$$P_{n,axial} = F_y \\cdot A_g$$
$$P_u \\leq \\phi_c \\cdot P_n, \\quad \\phi_c = 0.70$$

Combined axial + bending interaction (when $P_u / (\\phi P_n) < 0.20$):

$$\\frac{P_u}{2 \\phi P_n} + \\frac{M_u}{\\phi M_n} \\leq 1.0$$

When $P_u / (\\phi P_n) \\geq 0.20$:

$$\\frac{P_u}{\\phi P_n} + \\frac{8}{9} \\cdot \\frac{M_u}{\\phi M_n} \\leq 1.0$$"""))

# Cell 20: Section 7 code
cells.append(mk("code", """# ============================================================
# Structural Capacity Check
# ============================================================

phi_c = 0.70  # Resistance factor for axial compression (driven piles)
phi_f = 1.00  # Resistance factor for flexure

# Axial capacity
Pn = pile_input.fy * A_pile  # kips (nominal)
Pr = phi_c * Pn              # kips (factored resistance)

print(f"Structural Capacity Check ({pile_input.pile_type}):")
print(f"  Fy = {pile_input.fy} ksi, Ag = {A_pile} in^2")
print(f"  Pn = Fy * Ag = {Pn:.1f} kips")
print(f"  Pr = phi_c * Pn = {phi_c} x {Pn:.1f} = {Pr:.1f} kips")
print(f"  Pu per pile = {Qp_factored:.1f} kips")

# Axial check
axial_ratio = Qp_factored / Pr
axial_status = "PASS" if Qp_factored <= Pr else "FAIL"
print(f"  Pu/Pr = {axial_ratio:.3f} --> {axial_status}")

# Combined axial + bending (if moment is present)
Mu_per_pile = pile_input.moment / pile_input.num_piles  # kip-ft per pile (simplified)
if Mu_per_pile > 0:
    Sx = pile_props["Sx"]
    Zx = pile_props["Zx"]
    Mn = pile_input.fy * Zx / 12.0  # kip-ft
    Mr = phi_f * Mn

    if axial_ratio < 0.20:
        interaction = Qp_factored / (2 * Pr) + Mu_per_pile / Mr
        eq_label = "Pu/(2*phi*Pn) + Mu/(phi*Mn)"
    else:
        interaction = Qp_factored / Pr + (8.0 / 9.0) * Mu_per_pile / Mr
        eq_label = "Pu/(phi*Pn) + 8/9*Mu/(phi*Mn)"

    interaction_status = "PASS" if interaction <= 1.0 else "FAIL"
    print(f"\\n  Moment per pile Mu = {Mu_per_pile:.1f} kip-ft")
    print(f"  Mn = Fy * Zx = {Mn:.1f} kip-ft")
    print(f"  {eq_label} = {interaction:.3f} --> {interaction_status}")
else:
    interaction = 0.0
    interaction_status = "N/A"
    print("\\n  No moment applied -- interaction check not needed.")"""))

# Cell 21: Section 8 heading
cells.append(mk("markdown", """---
## 8. Settlement Check

**Elastic shortening:**
$$\\delta_e = \\frac{Q \\cdot L}{A \\cdot E}$$

**Pile group settlement (Equivalent Footing Method):**
$$\\Delta = \\frac{C_c}{1 + e_0} \\cdot H \\cdot \\log_{10}\\left(\\frac{\\sigma'_0 + \\Delta\\sigma}{\\sigma'_0}\\right)$$

ODOT limits (BDM 305.1.3):
- Total settlement: 1.5 inches
- Differential settlement: 0.75 inches"""))

# Cell 22: Section 8 code
cells.append(mk("code", """# ============================================================
# Settlement Check
# ============================================================

# Material properties
if pile_input.pile_type.startswith("HP"):
    E_pile = 29000.0  # ksi (steel)
elif pile_input.pile_type.startswith("pipe"):
    E_pile = 29000.0  # ksi (steel pipe)
else:
    E_pile = 4000.0   # ksi (concrete, approximate)

# Estimated pile length (use computed value or manual override)
L_pile = est_length if est_length is not None else 40.0  # ft

# 1. Elastic shortening
Q_service = pile_input.axial_DL / pile_input.num_piles + pile_input.axial_LL / pile_input.num_piles  # service load per pile (kips)
delta_e = Q_service * (L_pile * 12.0) / (A_pile * E_pile)  # inches

print("Settlement Check:")
print(f"  Service load per pile: {Q_service:.1f} kips")
print(f"  Pile length: {L_pile:.1f} ft")
print(f"  E = {E_pile} ksi, A = {A_pile} in^2")
print(f"  Elastic shortening: delta_e = {delta_e:.3f} in")

# 2. Group settlement (equivalent footing method, simplified)
# Assume group dimensions
n_rows = int(np.ceil(np.sqrt(pile_input.num_piles)))
n_cols = int(np.ceil(pile_input.num_piles / n_rows))
B_group = (n_cols - 1) * pile_input.pile_spacing + 1.0  # ft (group width)
L_group = (n_rows - 1) * pile_input.pile_spacing + 1.0  # ft (group length)

# Equivalent footing at 2/3 pile length
z_footing = L_pile * 2.0 / 3.0  # ft
B_eff = B_group + z_footing  # ft (spread at 1H:1V)
L_eff = L_group + z_footing  # ft

# Consolidation settlement (for cohesive soils below pile tips)
Cc = 0.20       # Compression index (typical, USER SHOULD VERIFY)
e0 = 0.80       # Initial void ratio (typical)
H_compress = 10.0  # Thickness of compressible layer below tips (ft)
gamma_soil = 0.120  # Average unit weight (kcf)
sigma_0 = gamma_soil * (z_footing + H_compress / 2.0)  # ksf
Q_total_service = Q_service * pile_input.num_piles
delta_sigma = Q_total_service / (B_eff * L_eff)  # ksf (stress increase)

if sigma_0 > 0 and delta_sigma > 0:
    delta_consol = (Cc / (1 + e0)) * H_compress * 12.0 * np.log10((sigma_0 + delta_sigma) / sigma_0)  # inches
else:
    delta_consol = 0.0

delta_total = delta_e + delta_consol

# ODOT limits
SETTLE_LIMIT_TOTAL = 1.5    # inches
SETTLE_LIMIT_DIFF = 0.75    # inches

settle_status = "PASS" if delta_total <= SETTLE_LIMIT_TOTAL else "FAIL"

print(f"\\n  Group dimensions: {B_group:.1f} x {L_group:.1f} ft")
print(f"  Equivalent footing depth: {z_footing:.1f} ft")
print(f"  Consolidation settlement: {delta_consol:.3f} in")
print(f"  Total settlement: {delta_total:.3f} in")
print(f"  ODOT limit: {SETTLE_LIMIT_TOTAL} in --> {settle_status}")"""))

# Cell 23: Section 9 heading
cells.append(mk("markdown", """---
## 9. Results Summary

Comprehensive summary of all pile design checks."""))

# Cell 24: Section 9 code
cells.append(mk("code", """# ============================================================
# Results Summary
# ============================================================

summary_data = {
    "Check": [
        "Factored Load per Pile (Pu)",
        "UBV (without downdrag)",
        "Downdrag Force (DD)",
        "UBV (with downdrag)",
        "Estimated Pile Length",
        "Structural Capacity (Axial)",
        "Interaction Equation",
        "Total Settlement",
    ],
    "Value": [
        f"{Qp_factored:.1f} kips",
        f"{UBV:.1f} kips ({UBV/2:.1f} tons)",
        f"{DD:.1f} kips",
        f"{UBV_with_DD:.1f} kips ({UBV_with_DD/2:.1f} tons)",
        f"{est_length:.1f} ft" if est_length else "N/A",
        f"Pu/Pr = {axial_ratio:.3f}",
        f"{interaction:.3f}" if Mu_per_pile > 0 else "N/A",
        f"{delta_total:.3f} in",
    ],
    "Limit": [
        "--",
        "--",
        "--",
        "--",
        "--",
        "<= 1.0",
        "<= 1.0",
        f"<= {SETTLE_LIMIT_TOTAL} in",
    ],
    "Status": [
        "--",
        "--",
        "Yes" if DD > 0 else "No",
        "--",
        "OK" if est_length else "EXTEND BORING",
        axial_status,
        interaction_status,
        settle_status,
    ],
}

summary_df = pd.DataFrame(summary_data)
display(Markdown("### Pile Foundation Design Summary"))
display(Markdown(f"**SFN:** {pile_input.sfn or '(not set)'}"))
display(Markdown(f"**Substructure:** {pile_input.substructure_id}"))
display(Markdown(f"**Pile:** {pile_input.num_piles} - {pile_input.pile_type}"))
display(Markdown(f"**Design Method:** {design_method} (phi = {phi_design})"))
display(summary_df)"""))

# Cell 25: Section 10 heading
cells.append(mk("markdown", """---
## 10. Plan Note Generation (BDM 600)

Generate standard pile foundation plan notes per ODOT BDM Section 600
requirements. These notes are placed on the foundation plan sheets."""))

# Cell 26: Section 10 code
cells.append(mk("code", """# ============================================================
# Plan Note Generation (BDM 600)
# ============================================================

# Compute tip elevation (user must provide ground elevation)
ground_elev = 800.0  # ft (USER INPUT: ground surface elevation)
tip_elev = ground_elev - (est_length if est_length else 40.0)

plan_note = (
    f"Piles: {pile_input.num_piles} - {pile_input.pile_type}. "
    f"Minimum tip elevation: {tip_elev:.1f} ft. "
    f"Ultimate Bearing Value: {UBV_with_DD / 2:.1f} tons. "
    f"Estimated pile length: {est_length:.1f} ft. " if est_length else
    f"Piles: {pile_input.num_piles} - {pile_input.pile_type}. "
    f"Minimum tip elevation: {tip_elev:.1f} ft. "
    f"Ultimate Bearing Value: {UBV_with_DD / 2:.1f} tons. "
    f"Estimated pile length: N/A. "
)
plan_note += (
    f"Downdrag load: {DD:.1f} kips. "
    f"Scour depth: {pile_input.scour_depth:.1f} ft."
)

display(Markdown("### Foundation Plan Note"))
display(Markdown(f"```\\n{plan_note}\\n```"))
print(plan_note)"""))

# Cell 27: Additional notes
cells.append(mk("markdown", """---
## Notes & Limitations

1. Pile capacity estimates from SPT are approximate. Field verification with
   dynamic testing (PDA/CAPWAP) or static load test is required.
2. Lateral pile capacity analysis (p-y curves) is beyond the scope of this
   notebook. Use LPILE or similar software for lateral design.
3. Scour effects should be evaluated per BDM 305.3.2.3. Skin friction in the
   scour zone must be deducted from the capacity.
4. Group effects (efficiency) should be checked when pile spacing < 3D.
5. Consult the geotechnical engineer for site-specific soil parameters.
6. Settlement parameters (Cc, e0) should be obtained from consolidation tests."""))

# Cell 28: Version info
cells.append(mk("code", """# ============================================================
# Version Info
# ============================================================
print("ODOT Pile Foundation Design Notebook")
print(f"Total cells: 28")
print(f"Design reference: ODOT BDM 305, AASHTO LRFD 10.7")
print(f"Resistance method: {design_method}")
print(f"Pile: {pile_input.num_piles} - {pile_input.pile_type}")
print(f"UBV: {UBV_with_DD/2:.1f} tons")
if est_length:
    print(f"Estimated length: {est_length:.1f} ft")"""))

# Build notebook
nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10.0"},
    },
    "cells": cells,
}

with open("Notebooks/ODOT Pile Foundation Design.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Built ODOT Pile Foundation Design.ipynb with {len(cells)} cells")
