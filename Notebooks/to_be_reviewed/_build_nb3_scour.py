"""Build Notebook 3: ODOT Hydraulic & Scour Analysis (BDM 201 / HEC-18)"""
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

# ---------------------------------------------------------------------------
# Cell 1: Title markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """# ODOT Hydraulic & Scour Analysis
**BDM 201 / HEC-18 5th Edition**

This notebook computes hydraulic scour depths for an ODOT bridge crossing
using the FHWA HEC-18 methodology. Results feed into the Structure Type
Study and scour criticality evaluation per BDM 305.1.6.

Scour components computed:
- **Contraction scour** (live-bed or clear-water)
- **Pier scour** (CSU / HEC-18 equation)
- **Abutment scour** (Froehlich equation)
- **Long-term degradation** (HEC-20 geomorphic assessment)
- **Total scour** vs. foundation depth"""))

# ---------------------------------------------------------------------------
# Cell 2: References markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## References
- ODOT Bridge Design Manual (BDM), Section 201 -- Hydraulic Design
- ODOT Location & Design Manual, Vol. 2 -- Drainage Design
- HEC-18, 5th Edition: Evaluating Scour at Bridges (FHWA-HIF-12-003)
- HEC-20, 4th Edition: Stream Stability at Highway Structures (FHWA-HIF-12-004)
- AASHTO LRFD Bridge Design Specifications, 9th Edition, Section 2.6"""))

# ---------------------------------------------------------------------------
# Cell 3: Imports code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Imports
# ============================================================
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from typing import Optional, List
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

# ODOT systems (optional)
try:
    from ODOT import USGSStreamStats, TIMSBridge, NHDFlowline
    ODOT_AVAILABLE = True
except ImportError:
    ODOT_AVAILABLE = False
    print("ODOT.py not available. Manual data entry required.")

print("Imports loaded.")"""))

# ---------------------------------------------------------------------------
# Cell 4: Section 1 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 1. Project Location & Hydrology"""))

# ---------------------------------------------------------------------------
# Cell 5: HydraulicInput code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# USER INPUT: Hydraulic Site Data
# ============================================================

class HydraulicInput(BaseModel):
    \"\"\"Site hydraulic and geomorphic parameters.\"\"\"
    sfn: str = ""                           # Structure File Number
    lat: Optional[float] = None             # Latitude (decimal degrees)
    lon: Optional[float] = None             # Longitude (decimal degrees)
    drainage_area_sqmi: Optional[float] = None  # Drainage area (sq mi)
    channel_slope: float = 0.0              # Channel slope (ft/ft)
    bed_material: str = "sand"              # sand / gravel / clay / rock
    D50_mm: float = 1.0                     # Median grain size (mm)
    D90_mm: float = 10.0                    # 90th percentile grain size (mm)

# USER INPUT
site = HydraulicInput(
    sfn="",
    lat=None,           # e.g. 39.9612
    lon=None,           # e.g. -82.9988
    drainage_area_sqmi=None,
    channel_slope=0.002,
    bed_material="sand",
    D50_mm=1.0,
    D90_mm=10.0,
)

print(f"SFN: {site.sfn or '(not set)'}")
print(f"Location: ({site.lat}, {site.lon})")
print(f"Bed material: {site.bed_material}, D50={site.D50_mm} mm, D90={site.D90_mm} mm")"""))

# ---------------------------------------------------------------------------
# Cell 6: StreamStats code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# StreamStats: Drainage Area & Peak Flows
# ============================================================

streamstats_result = None

if site.lat and site.lon and ODOT_AVAILABLE:
    try:
        streamstats_result = USGSStreamStats.delineate(site.lat, site.lon)
        da = streamstats_result.get("drainage_area_sqmi", None)
        if da:
            site.drainage_area_sqmi = da
        print(f"StreamStats drainage area: {site.drainage_area_sqmi} sq mi")
        peak_flows = streamstats_result.get("peak_flows", {})
        if peak_flows:
            print("\\nPeak flow estimates:")
            for ri, q in sorted(peak_flows.items()):
                print(f"  Q{ri}: {q:.0f} cfs")
    except Exception as e:
        print(f"StreamStats delineation failed: {e}")
        print("Enter drainage area and peak flows manually below.")
else:
    print("Provide lat/lon and ODOT.py to auto-delineate, or enter data manually below.")

# Manual override
if site.drainage_area_sqmi is None:
    site.drainage_area_sqmi = 0.0  # USER INPUT
    print(f"Manual drainage area: {site.drainage_area_sqmi} sq mi")"""))

# ---------------------------------------------------------------------------
# Cell 7: Section 2 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 2. Design Flows

Per BDM 201 and L&D Vol. 2:
- **Non-NHS bridges**: Q10 design, Q100 check
- **NHS bridges**: Q50 design, Q500 check (scour)
- **Scour analysis**: Q100 design, Q500 check per HEC-18"""))

# ---------------------------------------------------------------------------
# Cell 8: Design flows code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Design Flow Selection
# ============================================================

# USER INPUT: Peak flows (cfs) -- fill from StreamStats or manual analysis
peak_flows = {
    "Q10": 0.0,
    "Q25": 0.0,
    "Q50": 0.0,
    "Q100": 0.0,
    "Q500": 0.0,
}

# Overwrite from StreamStats if available
if streamstats_result and "peak_flows" in streamstats_result:
    for ri, q in streamstats_result["peak_flows"].items():
        key = f"Q{ri}"
        if key in peak_flows:
            peak_flows[key] = q

# Select design frequency
is_nhs = True  # USER INPUT: Set to False for non-NHS routes
design_freq = "Q50" if is_nhs else "Q10"
check_freq = "Q500"

Q_design = peak_flows[design_freq]
Q_check = peak_flows[check_freq]

flow_df = pd.DataFrame([
    {"Recurrence": k, "Flow (cfs)": f"{v:.0f}",
     "Use": "DESIGN" if k == design_freq else ("CHECK" if k == check_freq else "")}
    for k, v in peak_flows.items()
])

display(Markdown("### Peak Flow Summary"))
display(flow_df)
print(f"\\nDesign flow ({design_freq}): {Q_design:.0f} cfs")
print(f"Check flow ({check_freq}): {Q_check:.0f} cfs")"""))

# ---------------------------------------------------------------------------
# Cell 9: Section 3 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 3. HEC-RAS Results Input

Enter cross-section hydraulic results from HEC-RAS output tables.
Four sections are needed:
1. **Approach** -- upstream section (1 bridge length upstream)
2. **Bridge upstream** -- just upstream of bridge opening
3. **Bridge downstream** -- just downstream of bridge opening
4. **Exit** -- downstream section (1 bridge length downstream)"""))

# ---------------------------------------------------------------------------
# Cell 10: HECRASSection code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# HEC-RAS Cross-Section Data Model
# ============================================================

class HECRASSection(BaseModel):
    \"\"\"Hydraulic results at a single cross-section from HEC-RAS.\"\"\"
    station: str = ""               # HEC-RAS station label
    wse: float = 0.0                # Water surface elevation (ft)
    velocity: float = 0.0           # Average velocity (fps)
    flow_area: float = 0.0          # Flow area (sq ft)
    top_width: float = 0.0          # Top width (ft)
    hydraulic_depth: float = 0.0    # Hydraulic depth = area / top_width (ft)
    froude_number: float = 0.0      # Froude number
    energy_slope: float = 0.0       # Energy grade line slope (ft/ft)

# Create list of sections
sections = {
    "approach": HECRASSection(station="Approach"),
    "bridge_us": HECRASSection(station="Bridge US"),
    "bridge_ds": HECRASSection(station="Bridge DS"),
    "exit": HECRASSection(station="Exit"),
}

print("HECRASSection model defined. Fill in values below.")"""))

# ---------------------------------------------------------------------------
# Cell 11: HEC-RAS entry code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# USER INPUT: HEC-RAS Results (Q100 event)
# ============================================================
# Fill from HEC-RAS output tables or HDF5 extraction

sections["approach"] = HECRASSection(
    station="Approach",
    wse=0.0,            # ft
    velocity=0.0,       # fps
    flow_area=0.0,      # sq ft
    top_width=0.0,      # ft
    energy_slope=0.0,   # ft/ft
)

sections["bridge_us"] = HECRASSection(
    station="Bridge US",
    wse=0.0,
    velocity=0.0,
    flow_area=0.0,
    top_width=0.0,
    energy_slope=0.0,
)

sections["bridge_ds"] = HECRASSection(
    station="Bridge DS",
    wse=0.0,
    velocity=0.0,
    flow_area=0.0,
    top_width=0.0,
    energy_slope=0.0,
)

sections["exit"] = HECRASSection(
    station="Exit",
    wse=0.0,
    velocity=0.0,
    flow_area=0.0,
    top_width=0.0,
    energy_slope=0.0,
)

# Compute derived quantities
for name, sec in sections.items():
    if sec.top_width > 0:
        sec.hydraulic_depth = sec.flow_area / sec.top_width
    if sec.hydraulic_depth > 0:
        sec.froude_number = sec.velocity / np.sqrt(32.2 * sec.hydraulic_depth)

# Display
hecras_df = pd.DataFrame([
    {"Section": s.station, "WSE (ft)": s.wse, "V (fps)": s.velocity,
     "Area (sqft)": s.flow_area, "Width (ft)": s.top_width,
     "Hyd Depth (ft)": f"{s.hydraulic_depth:.2f}", "Fr": f"{s.froude_number:.3f}"}
    for s in sections.values()
])
display(Markdown("### HEC-RAS Results (Q100)"))
display(hecras_df)"""))

# ---------------------------------------------------------------------------
# Cell 12: Section 4 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 4. Contraction Scour: Live-Bed (HEC-18 Eq. 6.1-6.2)

Live-bed contraction scour occurs when upstream velocity exceeds the critical
velocity for sediment transport. The approach:

$$y_2 = y_1 \\left(\\frac{Q_2}{Q_1}\\right)^{6/7} \\left(\\frac{W_1}{W_2}\\right)^{K_1}$$

$$y_s = y_2 - y_0$$

Where $K_1$ depends on the ratio of shear velocity ($V_*$) to fall velocity ($\\omega$)."""))

# ---------------------------------------------------------------------------
# Cell 13: Live-bed scour code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Live-Bed Contraction Scour (HEC-18 Eq. 6.1-6.2)
# ============================================================

def fall_velocity(D50_mm, water_temp_F=60.0):
    \"\"\"Approximate fall velocity (fps) from D50 and water temperature.

    Uses simplified Rubey equation. For detailed analysis, refer to
    HEC-18 Table 6.1 or compute from Dietrich (1982).
    \"\"\"
    # Convert mm to ft
    d_ft = D50_mm / 304.8
    # Simplified -- for sand-size particles
    # More accurate lookup tables exist in HEC-18 Figure 6.8
    if D50_mm < 0.1:
        omega = 0.01  # very fine silt
    elif D50_mm < 0.25:
        omega = 0.07
    elif D50_mm < 0.5:
        omega = 0.15
    elif D50_mm < 1.0:
        omega = 0.30
    elif D50_mm < 2.0:
        omega = 0.50
    elif D50_mm < 4.0:
        omega = 0.75
    else:
        omega = 1.00
    return omega


def live_bed_contraction_scour(y1, Q1, Q2, W1, W2, V_star, omega):
    \"\"\"Live-bed contraction scour per HEC-18 Eq. 6.1-6.2.

    Args:
        y1: Average depth in upstream approach section (ft)
        Q1: Flow in upstream approach (cfs)
        Q2: Flow in contracted (bridge) section (cfs)
        W1: Bottom width of approach section (ft)
        W2: Bottom width of contracted section (ft)
        V_star: Shear velocity = sqrt(g * y1 * S1) (fps)
        omega: Fall velocity of D50 bed material (fps)

    Returns:
        dict with y2 (equilibrium depth), ys (scour depth), K1
    \"\"\"
    # K1 from V_star / omega ratio (HEC-18 Table 6.1)
    ratio = V_star / omega if omega > 0 else 999
    if ratio < 0.5:
        K1 = 0.59
    elif ratio <= 2.0:
        K1 = 0.64
    else:
        K1 = 0.69

    y2 = y1 * (Q2 / Q1) ** (6.0 / 7.0) * (W1 / W2) ** K1
    return {"y2": y2, "K1": K1, "V_star_omega_ratio": ratio}


# Compute shear velocity at approach section
g = 32.2  # ft/s^2
y1 = sections["approach"].hydraulic_depth
S1 = sections["approach"].energy_slope
V_star = np.sqrt(g * y1 * S1) if y1 > 0 and S1 > 0 else 0.0

omega = fall_velocity(site.D50_mm)
print(f"Shear velocity V*: {V_star:.3f} fps")
print(f"Fall velocity omega: {omega:.3f} fps")
if omega > 0:
    print(f"V*/omega ratio: {V_star / omega:.2f}")

# Compute live-bed scour
Q1 = peak_flows["Q100"]
Q2 = peak_flows["Q100"]  # Adjust if overbank flow is excluded from bridge
W1 = sections["approach"].top_width
W2 = sections["bridge_us"].top_width
y0_bridge = sections["bridge_us"].hydraulic_depth  # Existing depth in contracted section

if y1 > 0 and W1 > 0 and W2 > 0:
    lb_result = live_bed_contraction_scour(y1, Q1, Q2, W1, W2, V_star, omega)
    ys_live_bed = lb_result["y2"] - y0_bridge
    ys_live_bed = max(ys_live_bed, 0.0)
    print(f"\\nLive-bed contraction scour:")
    print(f"  K1: {lb_result['K1']}")
    print(f"  y2 (equilibrium depth): {lb_result['y2']:.2f} ft")
    print(f"  y0 (existing depth): {y0_bridge:.2f} ft")
    print(f"  ys (scour depth): {ys_live_bed:.2f} ft")
else:
    ys_live_bed = 0.0
    print("Insufficient HEC-RAS data for live-bed scour. Fill in Section 3.")"""))

# ---------------------------------------------------------------------------
# Cell 14: Section 5 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 5. Contraction Scour: Clear-Water (HEC-18 Eq. 6.3-6.4)

Clear-water scour applies when mean velocity is less than the critical
velocity for sediment transport:

$$y_2 = \\left(\\frac{K_u \\cdot Q^2}{D_m^{2/3} \\cdot W^2}\\right)^{3/7}$$

$$y_s = y_2 - y_0$$

Critical velocity: $V_c = 10.95 \\cdot y^{1/6} \\cdot D_{50}^{1/3}$ (US customary, $D_{50}$ in ft)"""))

# ---------------------------------------------------------------------------
# Cell 15: Clear-water scour code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Clear-Water Contraction Scour (HEC-18 Eq. 6.3-6.4)
# ============================================================

def critical_velocity(y, D50_ft):
    \"\"\"Critical velocity for sediment motion per HEC-18 Eq. 6.5.

    Args:
        y: Flow depth (ft)
        D50_ft: Median grain size (ft)

    Returns:
        Vc: Critical velocity (fps)
    \"\"\"
    if y <= 0 or D50_ft <= 0:
        return 0.0
    return 10.95 * y ** (1.0 / 6.0) * D50_ft ** (1.0 / 3.0)


def clear_water_contraction_scour(Q2, Dm_ft, W2, y0):
    \"\"\"Clear-water contraction scour per HEC-18 Eq. 6.3-6.4.

    Args:
        Q2: Flow through the bridge opening (cfs)
        Dm_ft: Effective grain size = 1.25 * D50 (ft)
        W2: Bottom width of contracted section (ft)
        y0: Existing average depth in contracted section (ft)

    Returns:
        dict with y2 (equilibrium depth), ys (scour depth)
    \"\"\"
    Ku = 0.0077  # US customary units
    if Dm_ft <= 0 or W2 <= 0:
        return {"y2": 0.0, "ys": 0.0}
    y2 = (Ku * Q2 ** 2 / (Dm_ft ** (2.0 / 3.0) * W2 ** 2)) ** (3.0 / 7.0)
    ys = max(y2 - y0, 0.0)
    return {"y2": y2, "ys": ys}


# Compute critical velocity
D50_ft = site.D50_mm / 304.8
Dm_ft = 1.25 * D50_ft  # Effective grain size
V_approach = sections["approach"].velocity
Vc = critical_velocity(y1, D50_ft)

print(f"D50: {site.D50_mm} mm = {D50_ft:.5f} ft")
print(f"Dm (1.25 * D50): {Dm_ft:.5f} ft")
print(f"Critical velocity Vc: {Vc:.2f} fps")
print(f"Approach velocity V: {V_approach:.2f} fps")

# Compute clear-water scour
if W2 > 0 and Q2 > 0:
    cw_result = clear_water_contraction_scour(Q2, Dm_ft, W2, y0_bridge)
    ys_clear_water = cw_result["ys"]
    print(f"\\nClear-water contraction scour:")
    print(f"  y2 (equilibrium depth): {cw_result['y2']:.2f} ft")
    print(f"  y0 (existing depth): {y0_bridge:.2f} ft")
    print(f"  ys (scour depth): {ys_clear_water:.2f} ft")
else:
    ys_clear_water = 0.0
    print("Insufficient data for clear-water scour. Fill in Section 3.")"""))

# ---------------------------------------------------------------------------
# Cell 16: Contraction scour selection code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Contraction Scour: Live-Bed vs. Clear-Water Selection
# ============================================================

if V_approach > Vc and Vc > 0:
    scour_type = "Live-Bed"
    ys_contraction = ys_live_bed
    print(f"V ({V_approach:.2f} fps) > Vc ({Vc:.2f} fps)")
    print(f"==> LIVE-BED contraction scour applies.")
else:
    scour_type = "Clear-Water"
    ys_contraction = ys_clear_water
    print(f"V ({V_approach:.2f} fps) <= Vc ({Vc:.2f} fps)")
    print(f"==> CLEAR-WATER contraction scour applies.")

print(f"\\nContraction scour depth: {ys_contraction:.2f} ft ({scour_type})")"""))

# ---------------------------------------------------------------------------
# Cell 17: Section 6 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 6. Pier Scour: CSU Equation (HEC-18 Eq. 7.1-7.3)

$$y_s = 2.0 \\cdot K_1 \\cdot K_2 \\cdot K_3 \\cdot K_4 \\cdot a^{0.65} \\cdot y_1^{0.35} \\cdot Fr_1^{0.43}$$

Where:
- $K_1$ = pier shape correction factor
- $K_2$ = angle of attack correction factor
- $K_3$ = bed condition correction factor
- $K_4$ = armoring factor (use 1.0 per HEC-18 5th ed. recommendation)
- $a$ = pier width (ft)
- $y_1$ = flow depth upstream of pier (ft)
- $Fr_1$ = Froude number upstream of pier"""))

# ---------------------------------------------------------------------------
# Cell 18: PierInput code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Pier Data Model
# ============================================================

class PierInput(BaseModel):
    \"\"\"Pier geometry and site conditions for scour calculation.\"\"\"
    pier_id: str = "Pier 1"
    width_a: float = 0.0            # Pier width (ft)
    length_L: float = 0.0           # Pier length (ft)
    shape: str = "round"            # round / square / sharp / group
    angle_of_attack: float = 0.0    # Skew angle to flow (degrees)
    bed_condition: str = "clear-water"  # clear-water / small_dunes / medium_dunes / large_dunes

# USER INPUT: Enter pier data for each pier
piers = [
    PierInput(
        pier_id="Pier 1",
        width_a=3.0,        # ft
        length_L=30.0,      # ft
        shape="round",      # round-nosed
        angle_of_attack=0.0,
        bed_condition="clear-water",
    ),
]

for p in piers:
    print(f"{p.pier_id}: a={p.width_a} ft, L={p.length_L} ft, shape={p.shape}, "
          f"angle={p.angle_of_attack} deg")"""))

# ---------------------------------------------------------------------------
# Cell 19: CSU pier scour code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# CSU Pier Scour (HEC-18 Eq. 7.1-7.3)
# ============================================================

def csu_pier_scour(a, y1, V1, Fr1, K1, K2, K3, K4=1.0):
    \"\"\"CSU pier scour equation per HEC-18 Eq. 7.1.

    Args:
        a: Pier width (ft)
        y1: Flow depth directly upstream of pier (ft)
        V1: Mean velocity upstream of pier (fps)
        Fr1: Froude number upstream of pier
        K1: Pier nose shape factor
        K2: Angle of attack factor
        K3: Bed condition factor
        K4: Armoring factor (default 1.0)

    Returns:
        ys: Pier scour depth (ft)
    \"\"\"
    if a <= 0 or y1 <= 0:
        return 0.0
    ys = 2.0 * K1 * K2 * K3 * K4 * (a ** 0.65) * (y1 ** 0.35) * (Fr1 ** 0.43)
    return ys


def get_K1(shape):
    \"\"\"Pier nose shape factor (HEC-18 Table 7.1).\"\"\"
    table = {"square": 1.1, "round": 1.0, "sharp": 0.9, "group": 1.0}
    return table.get(shape, 1.0)


def get_K2(angle_deg, L, a):
    \"\"\"Angle of attack factor (HEC-18 Table 7.2).\"\"\"
    if a <= 0:
        return 1.0
    theta = np.radians(angle_deg)
    K2 = (np.cos(theta) + (L / a) * np.sin(theta)) ** 0.65
    return K2


def get_K3(bed_condition):
    \"\"\"Bed condition factor (HEC-18 Table 7.3).\"\"\"
    table = {
        "clear-water": 1.1,
        "small_dunes": 1.1,
        "medium_dunes": 1.1,
        "large_dunes": 1.3,
    }
    return table.get(bed_condition, 1.1)


# Compute pier scour for each pier
pier_scour_results = []
for p in piers:
    K1 = get_K1(p.shape)
    K2 = get_K2(p.angle_of_attack, p.length_L, p.width_a)
    K3 = get_K3(p.bed_condition)
    K4 = 1.0  # HEC-18 5th edition recommendation

    # Use bridge upstream section hydraulics
    y1_pier = sections["bridge_us"].hydraulic_depth
    V1_pier = sections["bridge_us"].velocity
    Fr1_pier = sections["bridge_us"].froude_number

    ys_pier = csu_pier_scour(p.width_a, y1_pier, V1_pier, Fr1_pier, K1, K2, K3, K4)

    # Apply upper limit per HEC-18
    if p.shape == "round" and p.width_a > 0:
        ys_pier = min(ys_pier, 2.4 * p.width_a)
    elif p.width_a > 0:
        ys_pier = min(ys_pier, 3.0 * p.width_a)

    pier_scour_results.append({
        "pier_id": p.pier_id,
        "K1": K1, "K2": round(K2, 3), "K3": K3, "K4": K4,
        "ys": round(ys_pier, 2),
    })

    print(f"{p.pier_id}: K1={K1}, K2={K2:.3f}, K3={K3}, K4={K4}")
    print(f"  Pier scour depth: {ys_pier:.2f} ft")

# Maximum pier scour
ys_pier_max = max((r["ys"] for r in pier_scour_results), default=0.0)
print(f"\\nMax pier scour: {ys_pier_max:.2f} ft")"""))

# ---------------------------------------------------------------------------
# Cell 20: Section 7 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 7. Abutment Scour: Froehlich Equation (HEC-18 Eq. 8.1)

$$y_s = y_a \\left(2.27 \\cdot K_1 \\cdot K_2 \\cdot \\left(\\frac{a'}{y_a}\\right)^{0.43} \\cdot Fr_1^{0.61} + 1\\right) - y_a$$

Where:
- $K_1$ = abutment shape factor (vertical = 1.0, spill-through = 0.82)
- $K_2$ = skew correction = $(\\theta / 90)^{0.13}$
- $a'$ = projected abutment length perpendicular to flow (ft)
- $y_a$ = average depth of flow at the abutment (ft)
- $Fr_1$ = Froude number at the abutment"""))

# ---------------------------------------------------------------------------
# Cell 21: Abutment scour code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Abutment Scour: Froehlich Equation (HEC-18 Eq. 8.1)
# ============================================================

def froehlich_abutment_scour(a_prime, ya, Fr1, K1, K2):
    \"\"\"Froehlich abutment scour per HEC-18 Eq. 8.1.

    Args:
        a_prime: Projected abutment length perpendicular to flow (ft)
        ya: Average depth of flow at the abutment (ft)
        Fr1: Froude number at the abutment
        K1: Abutment shape factor (vertical=1.0, spill_through=0.82)
        K2: Skew correction factor

    Returns:
        ys: Abutment scour depth (ft)
    \"\"\"
    if ya <= 0 or a_prime <= 0:
        return 0.0
    ys = ya * (2.27 * K1 * K2 * (a_prime / ya) ** 0.43 * Fr1 ** 0.61 + 1) - ya
    return max(ys, 0.0)


# USER INPUT: Abutment parameters
abutment_type = "spill_through"  # "vertical" or "spill_through"
abutment_skew_deg = 90.0         # Angle of embankment to flow (90 = perpendicular)
a_prime_left = 0.0               # Projected abutment length, left (ft)
a_prime_right = 0.0              # Projected abutment length, right (ft)

# K factors
K1_abt = 1.0 if abutment_type == "vertical" else 0.82
K2_abt = (abutment_skew_deg / 90.0) ** 0.13 if abutment_skew_deg > 0 else 1.0

ya = sections["approach"].hydraulic_depth
Fr1_abt = sections["approach"].froude_number

# Left abutment
ys_abt_left = froehlich_abutment_scour(a_prime_left, ya, Fr1_abt, K1_abt, K2_abt)
# Right abutment
ys_abt_right = froehlich_abutment_scour(a_prime_right, ya, Fr1_abt, K1_abt, K2_abt)

ys_abutment = max(ys_abt_left, ys_abt_right)

print(f"Abutment type: {abutment_type}, K1={K1_abt}, K2={K2_abt:.3f}")
print(f"Left abutment scour: {ys_abt_left:.2f} ft")
print(f"Right abutment scour: {ys_abt_right:.2f} ft")
print(f"Controlling abutment scour: {ys_abutment:.2f} ft")"""))

# ---------------------------------------------------------------------------
# Cell 22: Section 8 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 8. Long-Term Degradation

Long-term channel degradation is estimated from geomorphic assessment
per HEC-20 procedures. This value should be obtained from the L&D Vol. 2
drainage study or a site-specific geomorphic analysis."""))

# ---------------------------------------------------------------------------
# Cell 23: Degradation code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Long-Term Degradation (HEC-20)
# ============================================================

# USER INPUT: Estimated long-term degradation from geomorphic assessment
# Refer to L&D Vol. 2 or HEC-20 geomorphic study
degradation_ft = 0.0  # TODO: Enter value from geomorphic study

print("Long-term degradation estimated from geomorphic assessment per HEC-20.")
print("Enter value from L&D Vol. 2 or geomorphic study.")
print(f"Long-term degradation: {degradation_ft:.2f} ft")"""))

# ---------------------------------------------------------------------------
# Cell 24: Section 9 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 9. Total Scour

Total scour is the sum of contraction scour, local scour (pier or abutment),
and long-term degradation:

$$\\text{Total Scour (pier)} = y_{s,contraction} + y_{s,pier} + y_{s,degradation}$$
$$\\text{Total Scour (abutment)} = y_{s,contraction} + y_{s,abutment} + y_{s,degradation}$$"""))

# ---------------------------------------------------------------------------
# Cell 25: Total scour code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Total Scour Calculation
# ============================================================

total_scour_pier = ys_contraction + ys_pier_max + degradation_ft
total_scour_abt = ys_contraction + ys_abutment + degradation_ft

# USER INPUT: Foundation depths (ft below channel bed)
foundation_depth_pier = 0.0   # ft below channel bed -- from boring logs
foundation_depth_abt = 0.0    # ft below channel bed -- from boring logs

# Comparison
scour_table = pd.DataFrame([
    {"Component": "Contraction Scour", "Pier (ft)": f"{ys_contraction:.2f}",
     "Abutment (ft)": f"{ys_contraction:.2f}"},
    {"Component": "Local Scour", "Pier (ft)": f"{ys_pier_max:.2f}",
     "Abutment (ft)": f"{ys_abutment:.2f}"},
    {"Component": "Long-Term Degradation", "Pier (ft)": f"{degradation_ft:.2f}",
     "Abutment (ft)": f"{degradation_ft:.2f}"},
    {"Component": "TOTAL SCOUR", "Pier (ft)": f"{total_scour_pier:.2f}",
     "Abutment (ft)": f"{total_scour_abt:.2f}"},
    {"Component": "Foundation Depth", "Pier (ft)": f"{foundation_depth_pier:.2f}",
     "Abutment (ft)": f"{foundation_depth_abt:.2f}"},
    {"Component": "Remaining Embedment", "Pier (ft)": f"{foundation_depth_pier - total_scour_pier:.2f}",
     "Abutment (ft)": f"{foundation_depth_abt - total_scour_abt:.2f}"},
])

display(Markdown("### Total Scour Summary"))
display(scour_table)

pier_ok = foundation_depth_pier >= total_scour_pier
abt_ok = foundation_depth_abt >= total_scour_abt
print(f"\\nPier: {'ADEQUATE' if pier_ok else 'INADEQUATE'} "
      f"(embedment {foundation_depth_pier:.1f} ft vs scour {total_scour_pier:.1f} ft)")
print(f"Abutment: {'ADEQUATE' if abt_ok else 'INADEQUATE'} "
      f"(embedment {foundation_depth_abt:.1f} ft vs scour {total_scour_abt:.1f} ft)")"""))

# ---------------------------------------------------------------------------
# Cell 26: Section 10 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 10. Scour Criticality Check (BDM 305.1.6)

Scour criticality codes per FHWA Coding Guide Item 113:
| Code | Description |
|------|-------------|
| **U** | Unknown foundations, scour not determined |
| **T** | Over tidal waters, scour not determined |
| **9** | Bridge foundations on dry land, well above flood water |
| **8** | Stable, foundations on rock or well below scour depth |
| **7** | Countermeasures installed, scour within tolerable limits |
| **5** | Stable, countermeasures installed and functional |
| **4** | Action required to protect exposed foundations |
| **3** | Unstable, scour critical; bridge closed to traffic |
| **2** | Unstable, scour critical; immediate action required |"""))

# ---------------------------------------------------------------------------
# Cell 27: Scour criticality code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Scour Criticality Evaluation (BDM 305.1.6 / FHWA Item 113)
# ============================================================

def evaluate_scour_code(total_scour, foundation_depth, on_rock=False,
                        countermeasures=False):
    \"\"\"Determine scour criticality code per FHWA Coding Guide Item 113.

    Args:
        total_scour: Total computed scour depth (ft)
        foundation_depth: Foundation depth below channel bed (ft)
        on_rock: True if founded on competent rock
        countermeasures: True if scour countermeasures are installed

    Returns:
        code: Scour criticality code (str)
        description: Code description
    \"\"\"
    if on_rock:
        return "8", "Stable -- foundations on rock or well below scour depth"
    if countermeasures and foundation_depth >= total_scour:
        return "5", "Stable -- countermeasures installed and functional"
    if foundation_depth >= total_scour * 1.5:
        return "8", "Stable -- foundations well below scour depth"
    if foundation_depth >= total_scour:
        if countermeasures:
            return "5", "Stable -- countermeasures installed and functional"
        else:
            return "7", "Countermeasures installed, scour within tolerable limits"
    if foundation_depth >= total_scour * 0.75:
        return "4", "Action required to protect exposed foundations"
    return "3", "Unstable -- scour critical"


# Evaluate
on_rock = site.bed_material == "rock"
countermeasures_installed = False  # USER INPUT

scour_code_pier, desc_pier = evaluate_scour_code(
    total_scour_pier, foundation_depth_pier, on_rock, countermeasures_installed)
scour_code_abt, desc_abt = evaluate_scour_code(
    total_scour_abt, foundation_depth_abt, on_rock, countermeasures_installed)

# Controlling code (lower is worse)
code_map = {"U": 0, "T": 0, "2": 2, "3": 3, "4": 4, "5": 5, "7": 7, "8": 8, "9": 9}
controlling_code = scour_code_pier if code_map.get(scour_code_pier, 0) <= code_map.get(scour_code_abt, 0) else scour_code_abt

print(f"Pier scour code: {scour_code_pier} -- {desc_pier}")
print(f"Abutment scour code: {scour_code_abt} -- {desc_abt}")
print(f"Controlling scour code: {controlling_code}")

# Compare with TIMS if available
if ODOT_AVAILABLE and site.sfn:
    try:
        bridge_tims = TIMSBridge(site.sfn)
        tims_scour = getattr(bridge_tims, "scour_critical", None)
        if tims_scour is not None:
            print(f"\\nTIMS Item 113 (scour_critical): {tims_scour}")
            print(f"Computed controlling code: {controlling_code}")
            if str(tims_scour) != str(controlling_code):
                print("NOTE: Computed code differs from TIMS. Review and update as needed.")
    except Exception:
        pass"""))

# ---------------------------------------------------------------------------
# Cell 28: Section 11 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 11. Riprap Sizing

Riprap sizing using the Isbash equation per HEC-11 / HEC-23:

$$D_{50} = 0.692 \\cdot \\frac{V^2}{2g} \\cdot \\frac{S_s}{S_s - 1}$$

Where $S_s$ = 2.65 (specific gravity of stone), $g$ = 32.2 ft/s$^2$."""))

# ---------------------------------------------------------------------------
# Cell 29: Riprap code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Riprap Sizing: Isbash Equation
# ============================================================

def isbash_riprap_d50(V, Ss=2.65, g=32.2):
    \"\"\"Compute riprap D50 using Isbash equation.

    Args:
        V: Design velocity (fps)
        Ss: Specific gravity of stone (default 2.65)
        g: Gravitational acceleration (ft/s^2)

    Returns:
        D50_ft: Required D50 in feet
    \"\"\"
    return 0.692 * (V ** 2 / (2 * g)) * (Ss / (Ss - 1))


# ODOT Riprap Classes (approximate D50 ranges)
ODOT_RIPRAP_CLASSES = {
    "Class 1": (4, 6),      # D50 4-6 inches
    "Class 2": (6, 9),      # D50 6-9 inches
    "Class 3": (9, 12),     # D50 9-12 inches
    "Class 4": (12, 18),    # D50 12-18 inches
    "Class 5": (18, 24),    # D50 18-24 inches
    "Class 6": (24, 36),    # D50 24-36 inches
}


def lookup_riprap_class(D50_inches):
    \"\"\"Look up ODOT riprap class from required D50.\"\"\"
    for cls, (lo, hi) in ODOT_RIPRAP_CLASSES.items():
        if D50_inches <= hi:
            return cls
    return "Class 6+"


# Design velocity for riprap
V_design = sections["bridge_us"].velocity
D50_riprap_ft = isbash_riprap_d50(V_design)
D50_riprap_in = D50_riprap_ft * 12.0

riprap_class = lookup_riprap_class(D50_riprap_in)

print(f"Design velocity: {V_design:.2f} fps")
print(f"Required riprap D50: {D50_riprap_ft:.3f} ft = {D50_riprap_in:.1f} in")
print(f"ODOT Riprap Class: {riprap_class}")"""))

# ---------------------------------------------------------------------------
# Cell 30: Section 12 markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## 12. Results Summary"""))

# ---------------------------------------------------------------------------
# Cell 31: Summary code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# Complete Scour Analysis Summary
# ============================================================

display(Markdown("### Scour Analysis Summary"))
display(Markdown(f"**SFN:** {site.sfn or '(not set)'}"))
display(Markdown(f"**Design Flow ({design_freq}):** {Q_design:.0f} cfs"))
display(Markdown(f"**Check Flow ({check_freq}):** {Q_check:.0f} cfs"))

summary_data = [
    {"Component": "Contraction Scour", "Q100 Depth (ft)": f"{ys_contraction:.2f}",
     "Q500 Depth (ft)": "--", "Foundation (ft)": "--", "Status": scour_type},
    {"Component": f"Pier Scour (max)", "Q100 Depth (ft)": f"{ys_pier_max:.2f}",
     "Q500 Depth (ft)": "--", "Foundation (ft)": f"{foundation_depth_pier:.1f}",
     "Status": ""},
    {"Component": "Abutment Scour (max)", "Q100 Depth (ft)": f"{ys_abutment:.2f}",
     "Q500 Depth (ft)": "--", "Foundation (ft)": f"{foundation_depth_abt:.1f}",
     "Status": ""},
    {"Component": "Long-Term Degradation", "Q100 Depth (ft)": f"{degradation_ft:.2f}",
     "Q500 Depth (ft)": "--", "Foundation (ft)": "--", "Status": ""},
    {"Component": "TOTAL (Pier)", "Q100 Depth (ft)": f"{total_scour_pier:.2f}",
     "Q500 Depth (ft)": "--", "Foundation (ft)": f"{foundation_depth_pier:.1f}",
     "Status": "ADEQUATE" if pier_ok else "INADEQUATE"},
    {"Component": "TOTAL (Abutment)", "Q100 Depth (ft)": f"{total_scour_abt:.2f}",
     "Q500 Depth (ft)": "--", "Foundation (ft)": f"{foundation_depth_abt:.1f}",
     "Status": "ADEQUATE" if abt_ok else "INADEQUATE"},
]

summary_df = pd.DataFrame(summary_data)
display(summary_df)

print(f"\\nRiprap Class: {riprap_class} (D50 = {D50_riprap_in:.1f} in)")
print(f"Scour Criticality Code: {controlling_code}")"""))

# ---------------------------------------------------------------------------
# Cell 32: Appendix markdown
# ---------------------------------------------------------------------------
cells.append(mk("markdown", """---
## Appendix: HEC-18 K-Factor Tables"""))

# ---------------------------------------------------------------------------
# Cell 33: K-factor code
# ---------------------------------------------------------------------------
cells.append(mk("code", """# ============================================================
# HEC-18 K-Factor Reference Tables
# ============================================================

# K1: Pier Shape Factor (HEC-18 Table 7.1)
k1_df = pd.DataFrame({
    "Pier Shape": ["Square nose", "Round nose", "Sharp nose (triangular)", "Group of cylinders"],
    "K1": [1.1, 1.0, 0.9, 1.0],
})
display(Markdown("### K1: Pier Nose Shape Factor"))
display(k1_df)

# K2: Angle of Attack Factor (HEC-18 Table 7.2)
angles = [0, 15, 30, 45, 90]
L_a_ratios = [4, 8, 12]
k2_rows = []
for angle in angles:
    row = {"Angle (deg)": angle}
    for la in L_a_ratios:
        theta = np.radians(angle)
        k2 = (np.cos(theta) + la * np.sin(theta)) ** 0.65
        row[f"L/a = {la}"] = round(k2, 2)
    k2_rows.append(row)

k2_df = pd.DataFrame(k2_rows)
display(Markdown("### K2: Angle of Attack Factor"))
display(k2_df)

# K3: Bed Condition Factor (HEC-18 Table 7.3)
k3_df = pd.DataFrame({
    "Bed Condition": ["Clear-water scour", "Plane bed / antidunes",
                      "Small dunes (2-10 ft)", "Medium dunes (10-30 ft)",
                      "Large dunes (> 30 ft)"],
    "Dune Height (ft)": ["N/A", "N/A", "2-10", "10-30", "> 30"],
    "K3": [1.1, 1.1, 1.1, 1.1, 1.3],
})
display(Markdown("### K3: Bed Condition Factor"))
display(k3_df)"""))

# ---------------------------------------------------------------------------
# Build notebook JSON
# ---------------------------------------------------------------------------
nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10.0"},
    },
    "cells": cells,
}

with open("Notebooks/ODOT Hydraulic Scour Analysis.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Built ODOT Hydraulic Scour Analysis.ipynb with {len(cells)} cells")
