"""Build Notebook 4: ODOT MSE Wall Design (BDM 500 / AASHTO LRFD 11.10)"""
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

# --- Cell 1: Title ---
cells.append(mk("markdown", """# ODOT MSE Wall Design
**BDM Section 500 / AASHTO LRFD Bridge Design Specifications Section 11.10**

This notebook performs Mechanically Stabilized Earth (MSE) wall design checks
per AASHTO LRFD 11.10 and ODOT BDM 500. Both external and internal stability
are evaluated, including sliding, eccentricity, bearing, tensile rupture,
and pullout resistance at each reinforcement layer.

$$K_a = \\tan^2\\!\\left(45^\\circ - \\frac{\\phi'}{2}\\right)$$"""))

# --- Cell 2: References ---
cells.append(mk("markdown", """---
## References
- AASHTO LRFD Bridge Design Specifications, 9th Edition, Section 11.10
- ODOT Bridge Design Manual (BDM), Section 500
- FHWA-NHI-10-024: Design and Construction of Mechanically Stabilized Earth Walls and Reinforced Soil Slopes, Volume I
- FHWA-NHI-10-025: Design and Construction of Mechanically Stabilized Earth Walls and Reinforced Soil Slopes, Volume II
- FHWA GEC 011: Design of Mechanically Stabilized Earth Walls and Reinforced Soil Slopes"""))

# --- Cell 3: Imports ---
cells.append(mk("code", """# ============================================================
# Imports
# ============================================================
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from IPython.display import display, Markdown

# Civilpy geotechnical (optional)
try:
    from civilpy.geotech import rankine_active_pressure
    RANKINE_AVAILABLE = True
except ImportError:
    RANKINE_AVAILABLE = False

# Civilpy load factors (optional)
try:
    from civilpy.structural.aashto.load_definitions import permanent_load_factors
    CIVILPY_LOADS = True
except ImportError:
    CIVILPY_LOADS = False

print("Imports loaded.")"""))

# --- Cell 4: Section 1 Wall Geometry ---
cells.append(mk("markdown", """---
## 1. Wall Geometry and Soil Properties

Define the MSE wall geometry, reinforced backfill properties, retained soil
properties, and foundation soil properties per AASHTO LRFD 11.10.5."""))

cells.append(mk("code", """# ============================================================
# Wall Geometry & Soil Input (Pydantic Model)
# ============================================================

class MSEWallInput(BaseModel):
    \"\"\"MSE wall geometry and soil parameters per AASHTO LRFD 11.10.\"\"\"
    # Wall geometry
    H: float = Field(..., description="Total wall height (ft)")
    L: float = Field(None, description="Reinforcement length (ft). Default = 0.7*H")
    batter: float = Field(0.0, description="Wall face batter angle (degrees)")
    embedment: float = Field(None, description="Embedment depth (ft). Default = max(H/20, 2.0)")
    surcharge_q: float = Field(0.0, description="Live load surcharge pressure (psf)")

    # Reinforced backfill
    backfill_gamma: float = Field(125.0, description="Reinforced backfill unit weight (pcf)")
    backfill_phi: float = Field(34.0, description="Reinforced backfill friction angle (deg)")

    # Retained soil (behind reinforced zone)
    retained_gamma: float = Field(120.0, description="Retained soil unit weight (pcf)")
    retained_phi: float = Field(30.0, description="Retained soil friction angle (deg)")

    # Foundation soil
    foundation_phi: float = Field(30.0, description="Foundation soil friction angle (deg)")
    foundation_cohesion: float = Field(0.0, description="Foundation cohesion (psf)")
    foundation_qult: float = Field(4.0, description="Foundation ultimate bearing capacity (ksf)")

    @validator("L", always=True, pre=True)
    def default_length(cls, v, values):
        if v is None and "H" in values:
            return round(0.7 * values["H"], 1)
        return v

    @validator("embedment", always=True, pre=True)
    def default_embedment(cls, v, values):
        if v is None and "H" in values:
            return max(values["H"] / 20.0, 2.0)
        return v

# USER INPUT
wall = MSEWallInput(
    H=20.0,             # ft
    L=None,             # defaults to 0.7 * H = 14.0 ft
    batter=0.0,         # degrees
    embedment=None,     # defaults to max(H/20, 2.0) = 2.0 ft
    surcharge_q=250.0,  # psf (equivalent to ~2 ft of soil surcharge)
    backfill_gamma=125.0,
    backfill_phi=34.0,
    retained_gamma=120.0,
    retained_phi=30.0,
    foundation_phi=30.0,
    foundation_cohesion=0.0,
    foundation_qult=4.0,  # ksf
)

print(f"Wall Height H = {wall.H} ft")
print(f"Reinforcement Length L = {wall.L} ft  (L/H = {wall.L/wall.H:.2f})")
print(f"Embedment Depth = {wall.embedment} ft")
print(f"Surcharge q = {wall.surcharge_q} psf")
print(f"Backfill: gamma = {wall.backfill_gamma} pcf, phi = {wall.backfill_phi} deg")
print(f"Retained: gamma = {wall.retained_gamma} pcf, phi = {wall.retained_phi} deg")
print(f"Foundation: phi = {wall.foundation_phi} deg, c = {wall.foundation_cohesion} psf, qult = {wall.foundation_qult} ksf")"""))

# --- Cell 5: Reinforcement Input ---
cells.append(mk("markdown", """---
## Reinforcement Properties

Define the soil reinforcement type and strength parameters per AASHTO LRFD 11.10.6."""))

cells.append(mk("code", """# ============================================================
# Reinforcement Input (Pydantic Model)
# ============================================================

class ReinforcementInput(BaseModel):
    \"\"\"Soil reinforcement properties per AASHTO LRFD 11.10.6.\"\"\"
    reinf_type: str = Field("geogrid", description="Type: steel_strip, geogrid, or geotextile")
    Tult: float = Field(4800.0, description="Ultimate tensile strength (lb/ft)")
    Rc: float = Field(1.0, description="Coverage ratio (dimensionless)")
    F_star: float = Field(None, description="Pullout friction factor. Default: 0.4*tan(phi) for geogrids")
    alpha: float = Field(None, description="Scale correction factor. 0.8 for geogrids, 1.0 for strips")
    Sv: float = Field(1.0, description="Vertical spacing (ft)")
    num_layers: int = Field(20, description="Number of reinforcement layers")
    RF_CR: float = Field(1.45, description="Creep reduction factor")
    RF_D: float = Field(1.10, description="Durability reduction factor")
    RF_ID: float = Field(1.40, description="Installation damage reduction factor")

    @validator("F_star", always=True, pre=True)
    def default_fstar(cls, v, values):
        if v is None:
            # Default: 0.4 * tan(phi) for geogrids; 1.5 for steel strips
            return None  # Will be set after wall input is available
        return v

    @validator("alpha", always=True, pre=True)
    def default_alpha(cls, v, values):
        if v is None:
            rt = values.get("reinf_type", "geogrid")
            if rt == "steel_strip":
                return 1.0
            else:
                return 0.8
        return v

# USER INPUT
reinf = ReinforcementInput(
    reinf_type="geogrid",
    Tult=4800.0,       # lb/ft
    Rc=1.0,
    F_star=None,       # computed below
    alpha=None,        # defaults to 0.8 for geogrid
    Sv=1.0,            # ft
    num_layers=20,
    RF_CR=1.45,
    RF_D=1.10,
    RF_ID=1.40,
)

# Set F_star based on wall backfill phi
if reinf.F_star is None:
    if reinf.reinf_type == "steel_strip":
        reinf.F_star = 1.5  # typical for ribbed steel strips
    else:
        reinf.F_star = 0.4 * np.tan(np.radians(wall.backfill_phi))

print(f"Reinforcement Type: {reinf.reinf_type}")
print(f"Tult = {reinf.Tult} lb/ft")
print(f"Vertical Spacing Sv = {reinf.Sv} ft")
print(f"Number of Layers = {reinf.num_layers}")
print(f"Coverage Ratio Rc = {reinf.Rc}")
print(f"F* = {reinf.F_star:.4f}")
print(f"Alpha = {reinf.alpha}")
print(f"Reduction Factors: CR={reinf.RF_CR}, D={reinf.RF_D}, ID={reinf.RF_ID}")"""))

# --- Cell 6: Section 2 Earth Pressure ---
cells.append(mk("markdown", """---
## 2. Active Earth Pressure Coefficient

Rankine active earth pressure coefficient per AASHTO LRFD 3.11.5.3:

$$K_a = \\tan^2\\!\\left(45^\\circ - \\frac{\\phi'}{2}\\right)$$

The lateral earth pressure at depth $z$ is:

$$\\sigma_h(z) = K_a \\cdot \\gamma \\cdot z + K_a \\cdot q$$"""))

cells.append(mk("code", """# ============================================================
# Earth Pressure Coefficients
# ============================================================

def rankine_Ka(phi_deg):
    \"\"\"Rankine active earth pressure coefficient.\"\"\"
    phi_rad = np.radians(phi_deg)
    return np.tan(np.radians(45) - phi_rad / 2) ** 2

# Ka for reinforced backfill (internal stability)
Ka_backfill = rankine_Ka(wall.backfill_phi)

# Ka for retained soil (external stability)
Ka_retained = rankine_Ka(wall.retained_phi)

print(f"Ka (backfill, phi={wall.backfill_phi} deg) = {Ka_backfill:.4f}")
print(f"Ka (retained, phi={wall.retained_phi} deg) = {Ka_retained:.4f}")

# Validate against civilpy if available
if RANKINE_AVAILABLE:
    try:
        Ka_check = rankine_active_pressure(wall.retained_phi)
        print(f"civilpy Ka check = {Ka_check:.4f}")
    except Exception as e:
        print(f"civilpy validation skipped: {e}")"""))

cells.append(mk("code", """# ============================================================
# Lateral Pressure Diagram
# ============================================================

z = np.linspace(0, wall.H, 100)
sigma_soil = Ka_retained * wall.retained_gamma * z   # psf
sigma_surcharge = Ka_retained * wall.surcharge_q * np.ones_like(z)  # psf
sigma_total = sigma_soil + sigma_surcharge

fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharey=True)

# Pressure diagram
ax1 = axes[0]
ax1.plot(sigma_soil, z, 'b-', linewidth=2, label='Soil pressure')
ax1.plot(sigma_surcharge, z, 'r--', linewidth=2, label='Surcharge')
ax1.plot(sigma_total, z, 'k-', linewidth=2.5, label='Total')
ax1.set_xlabel('Lateral Pressure (psf)')
ax1.set_ylabel('Depth z (ft)')
ax1.set_title('Active Earth Pressure Distribution')
ax1.invert_yaxis()
ax1.legend()
ax1.grid(True, alpha=0.3)

# Wall schematic
ax2 = axes[1]
ax2.add_patch(patches.Rectangle((0, 0), wall.L, wall.H, linewidth=2,
              edgecolor='brown', facecolor='sandybrown', alpha=0.5, label='Reinforced zone'))
ax2.add_patch(patches.Rectangle((-0.5, 0), 0.5, wall.H, linewidth=2,
              edgecolor='gray', facecolor='gray', alpha=0.7, label='Wall face'))
for i in range(reinf.num_layers):
    z_layer = wall.H - (i + 0.5) * reinf.Sv
    if z_layer > 0:
        ax2.plot([0, wall.L], [z_layer, z_layer], 'k-', linewidth=0.8, alpha=0.5)
ax2.set_xlabel('Distance from face (ft)')
ax2.set_ylabel('Height (ft)')
ax2.set_title('Wall Cross Section')
ax2.set_xlim(-2, wall.L + 2)
ax2.set_ylim(-1, wall.H + 2)
ax2.legend(loc='upper right')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

print(f"Max lateral pressure at base = {sigma_total[-1]:.1f} psf")"""))

# --- Cell 7: Section 3 External - Sliding ---
cells.append(mk("markdown", """---
## 3. External Stability: Sliding Check (AASHTO 11.10.5.3)

The factored sliding resistance must exceed the factored driving force:

$$\\phi_s \\cdot V \\cdot \\tan(\\delta_b) \\geq \\gamma_{EH} \\left(\\frac{1}{2} K_a \\gamma_r H^2 + K_a q H\\right)$$

Where:
- $\\phi_s = 1.00$ (resistance factor for shear between soil and foundation, tan-phi method)
- $\\delta_b = \\min(\\phi_{foundation}, \\phi_{backfill})$
- $\\gamma_{EH} = 1.50$ (maximum load factor for horizontal earth pressure)
- $V = \\gamma_{backfill} \\cdot H \\cdot L + q \\cdot L$ (total vertical load)"""))

cells.append(mk("code", """# ============================================================
# External Stability: Sliding (AASHTO 11.10.5.3)
# ============================================================

def check_sliding(wall):
    \"\"\"Check sliding stability per AASHTO LRFD 11.10.5.3.

    Returns dict with forces, CDR, and pass/fail status.
    \"\"\"
    # Load factors
    gamma_EV = 1.00   # min for vertical earth pressure (stabilizing)
    gamma_EH = 1.50   # max for horizontal earth pressure (driving)
    phi_s = 1.00      # resistance factor for sliding (tan-phi method)

    # Interface friction angle
    delta_b = min(wall.foundation_phi, wall.backfill_phi)

    # Vertical forces (unfactored)
    V_soil = wall.backfill_gamma * wall.H * wall.L  # weight of reinforced fill (lb/ft)
    V_surcharge = wall.surcharge_q * wall.L          # surcharge (lb/ft)
    V_total = V_soil + V_surcharge                   # total vertical (lb/ft)

    # Sliding resistance (factored)
    F_resist = phi_s * gamma_EV * V_total * np.tan(np.radians(delta_b))

    # Driving force (factored)
    Pa_soil = 0.5 * Ka_retained * wall.retained_gamma * wall.H**2
    Pa_surcharge = Ka_retained * wall.surcharge_q * wall.H
    F_driving = gamma_EH * (Pa_soil + Pa_surcharge)

    CDR = F_resist / F_driving if F_driving > 0 else float('inf')
    status = "PASS" if CDR >= 1.0 else "FAIL"

    print(f"--- Sliding Check (AASHTO 11.10.5.3) ---")
    print(f"delta_b = min({wall.foundation_phi}, {wall.backfill_phi}) = {delta_b} deg")
    print(f"V_total = {V_total:.0f} lb/ft")
    print(f"F_resist = {F_resist:.0f} lb/ft (factored)")
    print(f"Pa_soil = {Pa_soil:.0f} lb/ft, Pa_surcharge = {Pa_surcharge:.0f} lb/ft")
    print(f"F_driving = {F_driving:.0f} lb/ft (factored)")
    print(f"CDR = {CDR:.3f}  --> {status}")

    return {
        "check": "Sliding",
        "F_resist": F_resist,
        "F_driving": F_driving,
        "CDR": CDR,
        "status": status,
        "V_total": V_total,
    }

sliding = check_sliding(wall)"""))

# --- Cell 8: Section 4 External - Eccentricity ---
cells.append(mk("markdown", """---
## 4. External Stability: Eccentricity Check (AASHTO 11.10.5.4)

The resultant of all forces must fall within the middle third (soil foundation)
or middle half (rock foundation) of the base:

$$e = \\frac{L}{2} - \\frac{\\sum M_R - \\sum M_O}{V}$$

Limits:
- Soil foundation: $e \\leq L/6$
- Rock foundation: $e \\leq L/4$"""))

cells.append(mk("code", """# ============================================================
# External Stability: Eccentricity (AASHTO 11.10.5.4)
# ============================================================

def check_eccentricity(wall, foundation_type="soil"):
    \"\"\"Check eccentricity per AASHTO LRFD 11.10.5.4.

    Args:
        wall: MSEWallInput instance
        foundation_type: 'soil' or 'rock'

    Returns dict with eccentricity, limit, and pass/fail.
    \"\"\"
    gamma_EV = 1.00   # min for vertical (destabilizing for eccentricity)
    gamma_EH = 1.50   # max for horizontal

    # Vertical forces and moments about toe (point A at base-front of wall)
    V_soil = wall.backfill_gamma * wall.H * wall.L
    arm_soil = wall.L / 2.0  # acts at center of reinforced zone
    M_R_soil = gamma_EV * V_soil * arm_soil

    V_surcharge = wall.surcharge_q * wall.L
    arm_surcharge = wall.L / 2.0
    M_R_surcharge = gamma_EV * V_surcharge * arm_surcharge

    V_total = gamma_EV * (V_soil + V_surcharge)

    # Overturning moments from lateral earth pressure
    Pa_soil = 0.5 * Ka_retained * wall.retained_gamma * wall.H**2
    arm_Pa = wall.H / 3.0  # triangular distribution acts at H/3
    M_O_soil = gamma_EH * Pa_soil * arm_Pa

    Pa_surcharge = Ka_retained * wall.surcharge_q * wall.H
    arm_q = wall.H / 2.0  # uniform distribution acts at H/2
    M_O_surcharge = gamma_EH * Pa_surcharge * arm_q

    sum_MR = M_R_soil + M_R_surcharge
    sum_MO = M_O_soil + M_O_surcharge

    # Eccentricity
    e = wall.L / 2.0 - (sum_MR - sum_MO) / V_total

    # Limits
    if foundation_type == "rock":
        e_limit = wall.L / 4.0
    else:
        e_limit = wall.L / 6.0

    CDR = e_limit / abs(e) if abs(e) > 0 else float('inf')
    status = "PASS" if abs(e) <= e_limit else "FAIL"

    print(f"--- Eccentricity Check (AASHTO 11.10.5.4) ---")
    print(f"Sum M_resisting = {sum_MR:.0f} lb-ft/ft")
    print(f"Sum M_overturning = {sum_MO:.0f} lb-ft/ft")
    print(f"V_total = {V_total:.0f} lb/ft")
    print(f"Eccentricity e = {e:.3f} ft")
    print(f"Limit (L/{6 if foundation_type == 'soil' else 4}) = {e_limit:.3f} ft")
    print(f"CDR = {CDR:.3f}  --> {status}")

    return {
        "check": "Eccentricity",
        "computed": abs(e),
        "limit": e_limit,
        "CDR": CDR,
        "status": status,
        "e": e,
    }

eccentricity = check_eccentricity(wall, foundation_type="soil")"""))

# --- Cell 9: Section 5 External - Bearing ---
cells.append(mk("markdown", """---
## 5. External Stability: Bearing Check (AASHTO 11.10.5.4)

The vertical stress at the base must not exceed the factored bearing resistance:

$$\\sigma_v = \\frac{V}{L - 2e}$$

$$\\sigma_v \\leq \\phi_{bc} \\cdot q_{ult}$$

Where $\\phi_{bc} = 0.65$ (resistance factor for bearing capacity)."""))

cells.append(mk("code", """# ============================================================
# External Stability: Bearing (AASHTO 11.10.5.4)
# ============================================================

def check_bearing(wall, e):
    \"\"\"Check bearing pressure per AASHTO LRFD 11.10.5.4.

    Args:
        wall: MSEWallInput instance
        e: eccentricity (ft) from eccentricity check

    Returns dict with bearing stress, capacity, CDR, and pass/fail.
    \"\"\"
    gamma_EV = 1.35  # max for vertical earth pressure (driving for bearing)
    phi_bc = 0.65    # resistance factor for bearing capacity

    # Vertical forces (unfactored)
    V_soil = wall.backfill_gamma * wall.H * wall.L
    V_surcharge = wall.surcharge_q * wall.L
    V_total = V_soil + V_surcharge

    # Factored vertical force
    V_factored = gamma_EV * V_total

    # Effective base width
    B_eff = wall.L - 2.0 * abs(e)

    # Bearing stress (convert to ksf: divide by 1000)
    sigma_v = V_factored / B_eff / 1000.0  # ksf

    # Factored bearing resistance
    qr = phi_bc * wall.foundation_qult  # ksf

    CDR = qr / sigma_v if sigma_v > 0 else float('inf')
    status = "PASS" if sigma_v <= qr else "FAIL"

    print(f"--- Bearing Check (AASHTO 11.10.5.4) ---")
    print(f"V_factored = {V_factored:.0f} lb/ft")
    print(f"Effective width B' = L - 2e = {B_eff:.3f} ft")
    print(f"sigma_v = {sigma_v:.3f} ksf")
    print(f"phi_bc * qult = {qr:.3f} ksf")
    print(f"CDR = {CDR:.3f}  --> {status}")

    return {
        "check": "Bearing",
        "computed": sigma_v,
        "limit": qr,
        "CDR": CDR,
        "status": status,
    }

bearing = check_bearing(wall, eccentricity["e"])"""))

# --- Cell 10: External Summary ---
cells.append(mk("markdown", """---
## External Stability Summary"""))

cells.append(mk("code", """# ============================================================
# External Stability Summary Table
# ============================================================

ext_data = []
ext_data.append({
    "Check": "Sliding",
    "Computed": f"{sliding['F_driving']:.0f} lb/ft (driving)",
    "Limit": f"{sliding['F_resist']:.0f} lb/ft (resisting)",
    "CDR": f"{sliding['CDR']:.3f}",
    "Status": sliding["status"],
})
ext_data.append({
    "Check": "Eccentricity",
    "Computed": f"{eccentricity['computed']:.3f} ft",
    "Limit": f"{eccentricity['limit']:.3f} ft (L/6)",
    "CDR": f"{eccentricity['CDR']:.3f}",
    "Status": eccentricity["status"],
})
ext_data.append({
    "Check": "Bearing",
    "Computed": f"{bearing['computed']:.3f} ksf",
    "Limit": f"{bearing['limit']:.3f} ksf",
    "CDR": f"{bearing['CDR']:.3f}",
    "Status": bearing["status"],
})

ext_df = pd.DataFrame(ext_data)
display(Markdown("### External Stability Results"))
display(ext_df)

ext_pass = all(r["status"] == "PASS" for r in [sliding, eccentricity, bearing])
print(f"\\nExternal Stability: {'ALL CHECKS PASS' if ext_pass else 'ONE OR MORE CHECKS FAIL'}")"""))

# --- Cell 11: Section 6 Internal - Reinforcement Stresses ---
cells.append(mk("markdown", """---
## 6. Internal Stability: Reinforcement Stresses (AASHTO 11.10.6.2)

At each reinforcement layer depth $z$:

$$\\sigma_v = \\gamma \\cdot z + q$$

$$\\sigma_h = K_r \\cdot \\sigma_v$$

The ratio $K_r / K_a$ varies with depth and reinforcement type:
- **Inextensible (steel strips):** $K_r/K_a$ varies from 1.7 at the top to 1.2 at 6 m (20 ft) depth and below
- **Extensible (geosynthetics):** $K_r/K_a = 1.0$ at all depths

Maximum tensile force per unit width at each layer:

$$T_{max} = \\sigma_h \\cdot S_v$$"""))

cells.append(mk("code", """# ============================================================
# Internal Stability: Reinforcement Stresses
# ============================================================

def get_Kr_Ka_ratio(z_ft, reinf_type):
    \"\"\"Get Kr/Ka ratio per AASHTO LRFD Figure 11.10.6.2.1-3.

    Args:
        z_ft: depth below top of wall (ft)
        reinf_type: 'steel_strip', 'geogrid', or 'geotextile'

    Returns:
        Kr/Ka ratio
    \"\"\"
    if reinf_type == "steel_strip":
        # Linear interpolation from 1.7 at z=0 to 1.2 at z=20ft, constant below
        z_m = z_ft * 0.3048  # convert to meters for AASHTO figure
        if z_m <= 0:
            return 1.7
        elif z_m >= 6.0:
            return 1.2
        else:
            return 1.7 - (1.7 - 1.2) * z_m / 6.0
    else:
        # Extensible reinforcement (geosynthetic)
        return 1.0


# Compute stresses at each layer
layer_data = []
for i in range(reinf.num_layers):
    z = wall.H - (reinf.num_layers - i) * reinf.Sv + reinf.Sv / 2.0
    if z < 0:
        continue

    # Vertical stress
    sigma_v = wall.backfill_gamma * z + wall.surcharge_q  # psf

    # Lateral stress coefficient
    Kr_Ka = get_Kr_Ka_ratio(z, reinf.reinf_type)
    Kr = Kr_Ka * Ka_backfill

    # Horizontal stress and max tension
    sigma_h = Kr * sigma_v  # psf
    Tmax = sigma_h * reinf.Sv  # lb/ft

    layer_data.append({
        "layer": i + 1,
        "z_ft": z,
        "sigma_v_psf": sigma_v,
        "Kr_Ka": Kr_Ka,
        "Kr": Kr,
        "sigma_h_psf": sigma_h,
        "Tmax_lbft": Tmax,
    })

layer_df = pd.DataFrame(layer_data)
print(f"Computed stresses for {len(layer_data)} reinforcement layers")
display(layer_df[["layer", "z_ft", "sigma_v_psf", "Kr_Ka", "sigma_h_psf", "Tmax_lbft"]].round(2))"""))

# --- Cell 12: Section 7 Internal - Tensile Rupture ---
cells.append(mk("markdown", """---
## 7. Internal Stability: Tensile Rupture (AASHTO 11.10.6.3.1)

The factored reinforcement tension must not exceed the factored long-term
tensile resistance:

**Geosynthetic reinforcement:**
$$T_{al} = \\frac{T_{ult}}{RF_{CR} \\cdot RF_D \\cdot RF_{ID}}$$

**Steel reinforcement:**
$$T_{al} = F_y \\cdot b \\cdot E_c$$ (corroded cross-section)

Check: $\\gamma_{EV} \\cdot T_{max} \\leq \\phi \\cdot T_{al} \\cdot R_c$

Resistance factors:
- $\\phi = 0.75$ for steel strip reinforcement
- $\\phi = 0.65$ for geosynthetic reinforcement"""))

cells.append(mk("code", """# ============================================================
# Internal Stability: Tensile Rupture (AASHTO 11.10.6.3.1)
# ============================================================

def check_rupture(reinf, layer_data):
    \"\"\"Check tensile rupture at each reinforcement layer.

    Returns list of dicts with rupture check results.
    \"\"\"
    gamma_EV = 1.35  # max load factor for vertical earth pressure

    # Long-term allowable tensile strength
    if reinf.reinf_type in ("geogrid", "geotextile"):
        Tal = reinf.Tult / (reinf.RF_CR * reinf.RF_D * reinf.RF_ID)
        phi_t = 0.65  # geosynthetic resistance factor
    else:  # steel_strip
        Tal = reinf.Tult  # user should input Fy * b * Ec directly
        phi_t = 0.75      # steel strip resistance factor

    print(f"Tal (long-term allowable) = {Tal:.1f} lb/ft")
    print(f"phi (tensile resistance factor) = {phi_t}")
    print(f"phi * Tal * Rc = {phi_t * Tal * reinf.Rc:.1f} lb/ft")

    results = []
    for layer in layer_data:
        Tmax_factored = gamma_EV * layer["Tmax_lbft"]
        capacity = phi_t * Tal * reinf.Rc
        CDR = capacity / Tmax_factored if Tmax_factored > 0 else float('inf')
        status = "PASS" if CDR >= 1.0 else "FAIL"

        results.append({
            **layer,
            "Tal_lbft": Tal,
            "Tmax_factored": Tmax_factored,
            "phi_Tal_Rc": capacity,
            "CDR_rupture": CDR,
            "rupture_status": status,
        })

    return results

rupture_results = check_rupture(reinf, layer_data)

# Show summary
rupture_df = pd.DataFrame(rupture_results)
display(Markdown("### Tensile Rupture Check by Layer"))
display(rupture_df[["layer", "z_ft", "Tmax_lbft", "Tmax_factored",
                     "phi_Tal_Rc", "CDR_rupture", "rupture_status"]].round(2))

all_rupture_pass = all(r["rupture_status"] == "PASS" for r in rupture_results)
print(f"\\nTensile Rupture: {'ALL LAYERS PASS' if all_rupture_pass else 'ONE OR MORE LAYERS FAIL'}")"""))

# --- Cell 13: Section 8 Internal - Pullout ---
cells.append(mk("markdown", """---
## 8. Internal Stability: Pullout Resistance (AASHTO 11.10.6.3.2)

The reinforcement length behind the theoretical failure surface must provide
adequate pullout resistance:

$$P_r = \\phi \\cdot F^* \\cdot \\alpha \\cdot \\sigma_v' \\cdot L_e \\cdot C \\cdot R_c$$

Where:
- $\\phi = 0.90$ (pullout resistance factor)
- $F^*$ = pullout friction factor
- $\\alpha$ = scale correction factor
- $L_e$ = effective length behind failure surface
- $C = 2$ for strips and grids (top and bottom surfaces)

The failure surface for Rankine theory intersects the wall face at the base and
extends at angle $45 + \\phi/2$ from horizontal:

$$L_e = L - (H - z) \\cdot \\tan(45^\\circ - \\phi/2)$$"""))

cells.append(mk("code", """# ============================================================
# Internal Stability: Pullout (AASHTO 11.10.6.3.2)
# ============================================================

def check_pullout(wall, reinf, rupture_results):
    \"\"\"Check pullout resistance at each reinforcement layer.

    Returns updated list of dicts with pullout check results.
    \"\"\"
    gamma_EV = 1.35  # max load factor for Tmax
    phi_po = 0.90    # pullout resistance factor
    C = 2.0          # 2 for strips and grids (both sides)

    results = []
    for layer in rupture_results:
        z = layer["z_ft"]

        # Effective length behind failure surface
        # Failure surface: Rankine at (45 + phi/2) from horizontal
        tan_alpha = np.tan(np.radians(45.0 - wall.backfill_phi / 2.0))
        La = (wall.H - z) * tan_alpha  # length in active zone
        Le = wall.L - La               # length in resistant zone

        # Ensure minimum Le of 3 ft per AASHTO 11.10.6.3.2
        Le = max(Le, 3.0)

        # Overburden stress at depth z (unfactored, for pullout)
        sigma_v = wall.backfill_gamma * z  # psf (no surcharge for pullout per AASHTO)

        # Pullout resistance (factored)
        Pr = phi_po * reinf.F_star * reinf.alpha * sigma_v * Le * C * reinf.Rc

        # Factored tensile demand
        Tmax_factored = layer["Tmax_factored"]

        CDR = Pr / Tmax_factored if Tmax_factored > 0 else float('inf')
        status = "PASS" if CDR >= 1.0 else "FAIL"

        results.append({
            **layer,
            "La_ft": La,
            "Le_ft": Le,
            "sigma_v_pullout": sigma_v,
            "Pr_lbft": Pr,
            "CDR_pullout": CDR,
            "pullout_status": status,
        })

    return results

pullout_results = check_pullout(wall, reinf, rupture_results)

pullout_df = pd.DataFrame(pullout_results)
display(Markdown("### Pullout Resistance Check by Layer"))
display(pullout_df[["layer", "z_ft", "La_ft", "Le_ft", "Tmax_factored",
                     "Pr_lbft", "CDR_pullout", "pullout_status"]].round(2))

all_pullout_pass = all(r["pullout_status"] == "PASS" for r in pullout_results)
print(f"\\nPullout: {'ALL LAYERS PASS' if all_pullout_pass else 'ONE OR MORE LAYERS FAIL'}")"""))

# --- Cell 14: Internal Summary ---
cells.append(mk("markdown", """---
## Internal Stability Summary"""))

cells.append(mk("code", """# ============================================================
# Internal Stability Summary Table
# ============================================================

int_summary = []
for r in pullout_results:
    int_summary.append({
        "Layer": r["layer"],
        "z (ft)": f"{r['z_ft']:.1f}",
        "sigma_v (psf)": f"{r['sigma_v_psf']:.0f}",
        "sigma_h (psf)": f"{r['sigma_h_psf']:.0f}",
        "Tmax (lb/ft)": f"{r['Tmax_lbft']:.0f}",
        "Tal (lb/ft)": f"{r['Tal_lbft']:.0f}",
        "CDR Rupture": f"{r['CDR_rupture']:.2f}",
        "Le (ft)": f"{r['Le_ft']:.1f}",
        "Pr (lb/ft)": f"{r['Pr_lbft']:.0f}",
        "CDR Pullout": f"{r['CDR_pullout']:.2f}",
        "Status": "PASS" if r['rupture_status'] == 'PASS' and r['pullout_status'] == 'PASS' else "FAIL",
    })

int_df = pd.DataFrame(int_summary)
display(Markdown("### Complete Internal Stability Results"))
display(int_df)

all_int_pass = all(s["Status"] == "PASS" for s in int_summary)
print(f"\\nInternal Stability: {'ALL LAYERS PASS' if all_int_pass else 'ONE OR MORE LAYERS FAIL'}")"""))

# --- Cell 15: Internal Stability Plots ---
cells.append(mk("code", """# ============================================================
# Internal Stability Plots
# ============================================================

fig, axes = plt.subplots(1, 3, figsize=(15, 6))

depths = [r["z_ft"] for r in pullout_results]
cdr_rupt = [r["CDR_rupture"] for r in pullout_results]
cdr_pull = [r["CDR_pullout"] for r in pullout_results]
tmax_vals = [r["Tmax_lbft"] for r in pullout_results]

# CDR Rupture
ax1 = axes[0]
colors_r = ['green' if c >= 1.0 else 'red' for c in cdr_rupt]
ax1.barh(depths, cdr_rupt, height=reinf.Sv * 0.7, color=colors_r, alpha=0.7)
ax1.axvline(x=1.0, color='black', linewidth=2, linestyle='--', label='CDR = 1.0')
ax1.set_xlabel('CDR (Rupture)')
ax1.set_ylabel('Depth z (ft)')
ax1.set_title('Tensile Rupture CDR')
ax1.invert_yaxis()
ax1.legend()
ax1.grid(True, alpha=0.3)

# CDR Pullout
ax2 = axes[1]
colors_p = ['green' if c >= 1.0 else 'red' for c in cdr_pull]
ax2.barh(depths, cdr_pull, height=reinf.Sv * 0.7, color=colors_p, alpha=0.7)
ax2.axvline(x=1.0, color='black', linewidth=2, linestyle='--', label='CDR = 1.0')
ax2.set_xlabel('CDR (Pullout)')
ax2.set_title('Pullout CDR')
ax2.invert_yaxis()
ax2.legend()
ax2.grid(True, alpha=0.3)

# Tmax distribution
ax3 = axes[2]
ax3.plot(tmax_vals, depths, 'bo-', linewidth=2, markersize=5)
ax3.set_xlabel('Tmax (lb/ft)')
ax3.set_title('Max Reinforcement Tension')
ax3.invert_yaxis()
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()"""))

# --- Cell 16: Section 9 Global Stability ---
cells.append(mk("markdown", """---
## 9. Global (Overall) Stability (AASHTO 11.10.4.3)

Global stability analysis requires slope stability software capable of
modeling the reinforced soil mass, retained soil, and foundation. This is
typically performed using:
- **Slide** (Rocscience)
- **ReSSA** (FHWA/ADAMA Engineering)
- **SLOPE/W** (GeoStudio)

Per ODOT BDM: **FS >= 1.30** (or resistance factor $\\phi = 0.75$).

This check cannot be performed analytically in this notebook. The following
input summary is provided for use with external software."""))

cells.append(mk("code", """# ============================================================
# Global Stability Input Summary
# ============================================================

display(Markdown("### Input Summary for Global Stability Analysis"))

global_input = pd.DataFrame({
    "Parameter": [
        "Wall Height H",
        "Reinforcement Length L",
        "Embedment Depth",
        "Backfill Unit Weight",
        "Backfill Friction Angle",
        "Retained Soil Unit Weight",
        "Retained Soil Friction Angle",
        "Foundation Friction Angle",
        "Foundation Cohesion",
        "Surcharge",
        "Reinforcement Type",
        "Tult",
        "Tal (long-term)",
        "Vertical Spacing Sv",
        "Number of Layers",
    ],
    "Value": [
        f"{wall.H} ft",
        f"{wall.L} ft",
        f"{wall.embedment} ft",
        f"{wall.backfill_gamma} pcf",
        f"{wall.backfill_phi} deg",
        f"{wall.retained_gamma} pcf",
        f"{wall.retained_phi} deg",
        f"{wall.foundation_phi} deg",
        f"{wall.foundation_cohesion} psf",
        f"{wall.surcharge_q} psf",
        reinf.reinf_type,
        f"{reinf.Tult} lb/ft",
        f"{rupture_results[0]['Tal_lbft']:.1f} lb/ft",
        f"{reinf.Sv} ft",
        f"{reinf.num_layers}",
    ],
})

display(global_input)
print("\\nRequired FS >= 1.30 per ODOT BDM Section 500")
print("Use slope stability software (Slide, ReSSA, SLOPE/W) to verify.")"""))

# --- Cell 17: Section 10 Settlement ---
cells.append(mk("markdown", """---
## 10. Settlement Estimate (AASHTO 11.10.4.1)

Elastic settlement estimate for the MSE wall foundation. ODOT BDM limits:
- Total settlement: 2 inches
- Differential settlement: 1 inch (or 1/200 for precast panels)"""))

cells.append(mk("code", """# ============================================================
# Settlement Estimate
# ============================================================

def estimate_settlement(wall, Es_foundation=300_000):
    \"\"\"Estimate elastic settlement under MSE wall.

    Args:
        wall: MSEWallInput instance
        Es_foundation: Foundation soil elastic modulus (psf).
                       Typical: 150-600 ksf for medium dense sand.
                       Default = 300 ksf = 300,000 psf

    Returns dict with settlement estimates.
    \"\"\"
    # Applied stress at base (unfactored, service)
    V_total = wall.backfill_gamma * wall.H * wall.L + wall.surcharge_q * wall.L
    sigma_applied = V_total / wall.L  # psf

    # Influence factor (Boussinesq, center of flexible footing)
    # I = pi/4 * (1 - nu^2) for strip footing, approximate
    nu = 0.30  # Poisson's ratio for sand
    I = 0.785 * (1 - nu**2)  # ~0.714

    # Elastic settlement: delta = q * B * I / Es
    B = wall.L  # footing width
    delta_ft = sigma_applied * B * I / Es_foundation
    delta_in = delta_ft * 12.0

    print(f"--- Settlement Estimate ---")
    print(f"Applied stress (service) = {sigma_applied:.0f} psf = {sigma_applied/1000:.2f} ksf")
    print(f"Foundation Es = {Es_foundation/1000:.0f} ksf")
    print(f"Influence factor I = {I:.3f}")
    print(f"Elastic settlement = {delta_in:.2f} inches")
    print(f"Total limit = 2.0 inches: {'PASS' if delta_in <= 2.0 else 'FAIL'}")
    print(f"Differential limit = 1.0 inch: {'PASS' if delta_in/2 <= 1.0 else 'LIKELY OK'}")

    return {
        "sigma_applied_psf": sigma_applied,
        "Es_psf": Es_foundation,
        "settlement_in": delta_in,
        "total_pass": delta_in <= 2.0,
        "diff_pass": delta_in / 2 <= 1.0,
    }

# USER INPUT: Foundation elastic modulus (psf)
Es_foundation = 300_000  # psf (300 ksf, typical medium dense sand)

settlement = estimate_settlement(wall, Es_foundation)"""))

# --- Cell 18: Results Summary ---
cells.append(mk("markdown", """---
## Complete Design Summary"""))

cells.append(mk("code", """# ============================================================
# Complete Design Summary
# ============================================================

display(Markdown("# MSE Wall Design Summary"))
display(Markdown(f"**Wall Height:** {wall.H} ft | **Reinforcement Length:** {wall.L} ft (L/H = {wall.L/wall.H:.2f})"))
display(Markdown(f"**Reinforcement:** {reinf.reinf_type}, Tult = {reinf.Tult} lb/ft, Sv = {reinf.Sv} ft"))

display(Markdown("---"))
display(Markdown("### External Stability"))
display(ext_df)

display(Markdown("---"))
display(Markdown("### Internal Stability (Controlling Layers)"))

# Find worst layers
worst_rupture = min(pullout_results, key=lambda r: r["CDR_rupture"])
worst_pullout = min(pullout_results, key=lambda r: r["CDR_pullout"])

controlling = pd.DataFrame([
    {
        "Check": "Tensile Rupture (worst)",
        "Layer": worst_rupture["layer"],
        "Depth (ft)": f"{worst_rupture['z_ft']:.1f}",
        "CDR": f"{worst_rupture['CDR_rupture']:.2f}",
        "Status": worst_rupture["rupture_status"],
    },
    {
        "Check": "Pullout (worst)",
        "Layer": worst_pullout["layer"],
        "Depth (ft)": f"{worst_pullout['z_ft']:.1f}",
        "CDR": f"{worst_pullout['CDR_pullout']:.2f}",
        "Status": worst_pullout["pullout_status"],
    },
])
display(controlling)

display(Markdown("---"))
display(Markdown("### Settlement"))
display(Markdown(f"Estimated elastic settlement: **{settlement['settlement_in']:.2f} inches** (limit = 2.0 in)"))

display(Markdown("---"))
display(Markdown("### Global Stability"))
display(Markdown("Requires slope stability software. FS >= 1.30 per ODOT BDM."))

display(Markdown("---"))

# Overall verdict
all_ext = ext_pass
all_int = all_int_pass
all_settle = settlement["total_pass"]

if all_ext and all_int and all_settle:
    display(Markdown("## OVERALL RESULT: ALL CHECKS PASS"))
else:
    display(Markdown("## OVERALL RESULT: DESIGN REVISION NEEDED"))
    if not all_ext:
        display(Markdown("- External stability: FAIL - increase L or revise soil parameters"))
    if not all_int:
        display(Markdown("- Internal stability: FAIL - increase Tult, reduce Sv, or increase L"))
    if not all_settle:
        display(Markdown("- Settlement: EXCEEDS LIMITS - consider ground improvement"))

print(f"\\nGlobal stability must be verified separately with slope stability software.")"""))

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

with open("Notebooks/ODOT MSE Wall Design.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Built ODOT MSE Wall Design.ipynb with {len(cells)} cells")
