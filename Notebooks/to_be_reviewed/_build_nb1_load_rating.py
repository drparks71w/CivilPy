"""Build Notebook 1: ODOT Bridge Load Rating (MBE 6A / BDM 400)"""
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

cells.append(mk("markdown", """# ODOT Bridge Load Rating
**MBE 6A.4.2 / BDM Section 400**

This notebook computes load rating factors for an ODOT bridge using the
AASHTO Manual for Bridge Evaluation (MBE) General Load-Rating Equation:

$$RF = \\frac{C - \\gamma_{DC} \\cdot DC - \\gamma_{DW} \\cdot DW}{\\gamma_{LL} \\cdot LL \\cdot (1 + IM)}$$

Where $C = \\phi_c \\cdot \\phi_s \\cdot \\phi \\cdot R_n$ (factored member capacity).

Ratings are computed for Inventory, Operating, Legal, and Permit levels
using all 16 ODOT standard vehicles."""))

cells.append(mk("markdown", """---
## References
- AASHTO MBE 3rd Edition, Section 6A.4.2
- AASHTO LRFD Bridge Design Specifications, 9th Edition
- ODOT Bridge Design Manual (BDM), Section 400
- ODOT Bridge Load Rating Guidelines"""))

cells.append(mk("code", """# ============================================================
# Imports
# ============================================================
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from IPython.display import display, Markdown

# ODOT systems (optional — wrap in try/except)
try:
    from ODOT import (
        BrRBridge, TIMSBridge, MidasBridge,
        BRR_VEHICLE_MAP, OHIO_STANDARD_VEHICLES,
        ControllingRating, MemberCapacity,
    )
    ODOT_AVAILABLE = True
except ImportError:
    ODOT_AVAILABLE = False
    print("ODOT.py not available. Manual data entry required.")

# Civilpy load factors
try:
    from civilpy.structural.aashto.load_definitions import load_combinations
    CIVILPY_AVAILABLE = True
except ImportError:
    CIVILPY_AVAILABLE = False

print("Imports loaded.")"""))

cells.append(mk("markdown", """---
## 1. Bridge Identification & Data Pull"""))

cells.append(mk("code", """# ============================================================
# USER INPUT: Bridge Identification
# ============================================================
SFN = ""  # e.g. "2102226"

# Optional: Pull data from ODOT systems
bridge_tims = None
bridge_brr = None

if SFN and ODOT_AVAILABLE:
    try:
        bridge_tims = TIMSBridge(SFN)
        print(f"TIMS: {bridge_tims}")
    except Exception as e:
        print(f"TIMS lookup failed: {e}")

    try:
        bridge_brr = BrRBridge(SFN)
        print(f"BrR: {bridge_brr}")
    except Exception as e:
        print(f"BrR lookup failed: {e}")
elif not SFN:
    print("Enter SFN above to pull data from TIMS/BrR, or enter data manually below.")"""))

cells.append(mk("markdown", """---
## 2. Member Properties

Enter the controlling member properties. For steel girders, enter section properties.
For prestressed beams, enter nominal moment/shear capacity directly."""))

cells.append(mk("code", """# ============================================================
# Member Input
# ============================================================

class MemberInput(BaseModel):
    \"\"\"Structural member properties for load rating.\"\"\"
    member_id: str = "Girder 1"
    member_type: str = "steel_girder"  # steel_girder, prestressed_beam, concrete_slab
    span_length: float = 0.0  # ft
    girder_spacing: float = 0.0  # ft
    num_girders: int = 0

    # Capacity (enter one set)
    Mn_pos: float = 0.0   # Nominal positive moment capacity (kip-ft)
    Mn_neg: float = 0.0   # Nominal negative moment capacity (kip-ft)
    Vn: float = 0.0       # Nominal shear capacity (kips)
    phi_moment: float = 1.0   # Resistance factor for flexure
    phi_shear: float = 1.0    # Resistance factor for shear

# USER INPUT
member = MemberInput(
    member_id="Girder 1",
    member_type="steel_girder",
    span_length=80.0,      # ft
    girder_spacing=8.0,     # ft
    num_girders=5,
    Mn_pos=3500.0,          # kip-ft
    Mn_neg=0.0,             # kip-ft (simple span)
    Vn=450.0,               # kips
    phi_moment=1.0,         # 1.0 for steel flexure
    phi_shear=1.0,          # 1.0 for steel shear
)

print(f"Member: {member.member_id}")
print(f"Type: {member.member_type}")
print(f"Span: {member.span_length} ft, Spacing: {member.girder_spacing} ft")
print(f"Mn+: {member.Mn_pos} kip-ft, Vn: {member.Vn} kips")"""))

cells.append(mk("markdown", """---
## 3. Dead Load Effects (DC, DW)

Enter the unfactored dead load effects at the controlling section (typically midspan
for moment, near supports for shear)."""))

cells.append(mk("code", """# ============================================================
# Dead Load Effects (unfactored)
# ============================================================

class DeadLoadEffects(BaseModel):
    \"\"\"Unfactored dead load effects at the controlling section.\"\"\"
    # Moment (kip-ft)
    M_DC: float = 0.0   # Component dead load moment (self-weight, slab, haunch, diaphragms)
    M_DW: float = 0.0   # Wearing surface + utilities moment

    # Shear (kips)
    V_DC: float = 0.0
    V_DW: float = 0.0

# USER INPUT
dead = DeadLoadEffects(
    M_DC=800.0,    # kip-ft
    M_DW=120.0,    # kip-ft
    V_DC=80.0,     # kips
    V_DW=12.0,     # kips
)

# TODO: Pull from Midas or BrR if available
# if bridge_brr:
#     dead.M_DC = bridge_brr.nbi_info.get("dead_load_moment", 0)

print(f"DC Moment: {dead.M_DC} kip-ft, DC Shear: {dead.V_DC} kips")
print(f"DW Moment: {dead.M_DW} kip-ft, DW Shear: {dead.V_DW} kips")"""))

cells.append(mk("markdown", """---
## 4. Live Load Effects (LL + IM)

Enter the unfactored live load effects per vehicle. The impact factor (IM) is applied
within the rating equation. IM = 33% for Strength, 15% for Fatigue."""))

cells.append(mk("code", """# ============================================================
# Live Load Effects (unfactored, WITHOUT impact)
# ============================================================

class LiveLoadEffect(BaseModel):
    \"\"\"Live load effect for a single vehicle at controlling section.\"\"\"
    vehicle_name: str
    M_LL: float = 0.0   # Unfactored moment (kip-ft) WITHOUT IM
    V_LL: float = 0.0   # Unfactored shear (kips) WITHOUT IM

# USER INPUT: Enter live load effects for each vehicle
# These typically come from influence line analysis or Midas moving load results
live_loads = [
    LiveLoadEffect(vehicle_name="HL-93",           M_LL=1200.0, V_LL=110.0),
    LiveLoadEffect(vehicle_name="Type 3",          M_LL=650.0,  V_LL=62.0),
    LiveLoadEffect(vehicle_name="Type 3S2",        M_LL=780.0,  V_LL=72.0),
    LiveLoadEffect(vehicle_name="Type 3-3",        M_LL=820.0,  V_LL=75.0),
    LiveLoadEffect(vehicle_name="SU4",             M_LL=540.0,  V_LL=52.0),
    LiveLoadEffect(vehicle_name="SU5",             M_LL=600.0,  V_LL=56.0),
    LiveLoadEffect(vehicle_name="SU6",             M_LL=650.0,  V_LL=60.0),
    LiveLoadEffect(vehicle_name="SU7",             M_LL=680.0,  V_LL=63.0),
    LiveLoadEffect(vehicle_name="EV2",             M_LL=720.0,  V_LL=65.0),
    LiveLoadEffect(vehicle_name="EV3",             M_LL=760.0,  V_LL=68.0),
    LiveLoadEffect(vehicle_name="OH 2F1",          M_LL=500.0,  V_LL=48.0),
    LiveLoadEffect(vehicle_name="OH 3F1",          M_LL=580.0,  V_LL=55.0),
    LiveLoadEffect(vehicle_name="OH 5C1",          M_LL=700.0,  V_LL=64.0),
    LiveLoadEffect(vehicle_name="PL 60T",          M_LL=900.0,  V_LL=85.0),
    LiveLoadEffect(vehicle_name="PL 65T",          M_LL=950.0,  V_LL=90.0),
]

print(f"Loaded {len(live_loads)} vehicle effects")
for ll in live_loads[:5]:
    print(f"  {ll.vehicle_name}: M={ll.M_LL} kip-ft, V={ll.V_LL} kips")
print("  ...")"""))

cells.append(mk("markdown", """---
## 5. Condition and System Factors (MBE 6A.4.2.3-4)

| Condition (NBI) | phi_c |
|-----------------|-------|
| Good/Satisfactory (>= 6) | 1.00 |
| Fair (5) | 0.95 |
| Poor (<= 4) | 0.85 |

| System | phi_s |
|--------|-------|
| Multi-girder (>= 4 girders) | 1.00 |
| 3-girder system | 0.85 |
| 2-girder / 2-truss | 0.85 |
| Floor beam with 2 or fewer girders | 0.85 |"""))

cells.append(mk("code", """# ============================================================
# Condition & System Factors
# ============================================================

def get_condition_factor(nbi_rating):
    \"\"\"MBE Table 6A.4.2.3-1: Condition factor phi_c.\"\"\"
    if nbi_rating is None:
        return 1.00
    try:
        r = int(nbi_rating)
    except (ValueError, TypeError):
        return 1.00
    if r >= 6:
        return 1.00
    elif r == 5:
        return 0.95
    else:
        return 0.85

def get_system_factor(member_type, num_girders):
    \"\"\"MBE Table 6A.4.2.4-1: System factor phi_s.\"\"\"
    if member_type in ("steel_girder", "prestressed_beam"):
        if num_girders >= 4:
            return 1.00
        elif num_girders == 3:
            return 0.85
        else:
            return 0.85
    elif member_type == "concrete_slab":
        return 1.00  # Slab bridges
    return 1.00

# Auto-pull from TIMS if available
if bridge_tims:
    # Use the lowest of deck/super/sub ratings
    nbi_ratings = [bridge_tims.deck_rating, bridge_tims.superstructure_rating,
                   bridge_tims.substructure_rating]
    nbi_min = min((int(r) for r in nbi_ratings if r is not None), default=6)
    phi_c = get_condition_factor(nbi_min)
    print(f"Condition ratings (D/S/S): {'/'.join(str(r) for r in nbi_ratings)}")
    print(f"Controlling NBI rating: {nbi_min}")
else:
    # USER INPUT
    phi_c = 1.00  # Adjust based on inspection

phi_s = get_system_factor(member.member_type, member.num_girders)

print(f"phi_c (condition factor): {phi_c}")
print(f"phi_s (system factor): {phi_s}")"""))

cells.append(mk("markdown", """---
## 6. Rating Factor Calculation

The general load rating equation per MBE Eq. 6A.4.2.1-1:

$$RF = \\frac{C - \\gamma_{DC} \\cdot DC - \\gamma_{DW} \\cdot DW}{\\gamma_{LL} \\cdot LL \\cdot (1 + IM)}$$

### Live Load Factors (gamma_LL)

| Rating Level | gamma_LL | IM |
|---|---|---|
| Inventory (HL-93) | 1.75 | 0.33 |
| Operating (HL-93) | 1.35 | 0.33 |
| Legal (ADTT unknown) | 1.45 | 0.33 |
| Legal (ADTT <= 1000) | 1.40 | 0.33 |
| Legal (ADTT 1001-5000) | 1.35 | 0.33 |
| Legal (ADTT > 5000) | 1.30 | 0.33 |
| Permit - Routine | 1.20 | 0.33 |
| Permit - Special | 1.10 | 0.33 |"""))

cells.append(mk("code", """# ============================================================
# Rating Factor Functions
# ============================================================

# Load factors (MBE Table 6A.4.2.2-1)
GAMMA_DC = 1.25
GAMMA_DW = 1.50
IM_STRENGTH = 0.33
IM_FATIGUE = 0.15

GAMMA_LL_TABLE = {
    "Inventory": 1.75,
    "Operating": 1.35,
    "Legal_unknown": 1.45,
    "Legal_le1000": 1.40,
    "Legal_1001_5000": 1.35,
    "Legal_gt5000": 1.30,
    "Permit_routine": 1.20,
    "Permit_special": 1.10,
}


def compute_rf(C, DC, DW, LL, gamma_DC=1.25, gamma_DW=1.50, gamma_LL=1.75, IM=0.33):
    \"\"\"Compute rating factor per MBE Eq. 6A.4.2.1-1.

    Args:
        C: Factored capacity (phi_c * phi_s * phi * Rn)
        DC: Unfactored component dead load effect
        DW: Unfactored wearing surface dead load effect
        LL: Unfactored live load effect (WITHOUT IM)
        gamma_DC, gamma_DW, gamma_LL: Load factors
        IM: Dynamic load allowance (decimal, e.g. 0.33)

    Returns:
        Rating factor (float). RF >= 1.0 means adequate.
    \"\"\"
    numerator = C - gamma_DC * DC - gamma_DW * DW
    denominator = gamma_LL * LL * (1 + IM)
    if denominator == 0:
        return float("inf")
    return numerator / denominator


def get_legal_gamma_ll(adtt):
    \"\"\"Get legal load gamma_LL based on ADTT per MBE Table 6A.4.4.2.3a-1.\"\"\"
    if adtt is None:
        return 1.45
    elif adtt <= 1000:
        return 1.40
    elif adtt <= 5000:
        return 1.35
    else:
        return 1.30


print("Rating functions defined.")"""))

cells.append(mk("markdown", """---
## 7. Inventory & Operating Rating (HL-93)"""))

cells.append(mk("code", """# ============================================================
# Inventory & Operating Rating (HL-93)
# ============================================================

# Factored capacity
C_moment = phi_c * phi_s * member.phi_moment * member.Mn_pos
C_shear = phi_c * phi_s * member.phi_shear * member.Vn

# Find HL-93 live load
hl93 = next((ll for ll in live_loads if "HL-93" in ll.vehicle_name), None)

if hl93:
    rf_inv_moment = compute_rf(C_moment, dead.M_DC, dead.M_DW, hl93.M_LL,
                               gamma_LL=GAMMA_LL_TABLE["Inventory"])
    rf_inv_shear = compute_rf(C_shear, dead.V_DC, dead.V_DW, hl93.V_LL,
                              gamma_LL=GAMMA_LL_TABLE["Inventory"])
    rf_opr_moment = compute_rf(C_moment, dead.M_DC, dead.M_DW, hl93.M_LL,
                               gamma_LL=GAMMA_LL_TABLE["Operating"])
    rf_opr_shear = compute_rf(C_shear, dead.V_DC, dead.V_DW, hl93.V_LL,
                              gamma_LL=GAMMA_LL_TABLE["Operating"])

    inv_results = pd.DataFrame({
        "Check": ["Moment", "Shear"],
        "C (capacity)": [f"{C_moment:.1f} kip-ft", f"{C_shear:.1f} kips"],
        "Inventory RF": [f"{rf_inv_moment:.3f}", f"{rf_inv_shear:.3f}"],
        "Operating RF": [f"{rf_opr_moment:.3f}", f"{rf_opr_shear:.3f}"],
        "Inv Status": ["PASS" if rf_inv_moment >= 1.0 else "FAIL",
                        "PASS" if rf_inv_shear >= 1.0 else "FAIL"],
    })
    display(Markdown("### HL-93 Rating Results"))
    display(inv_results)

    rf_inv_controlling = min(rf_inv_moment, rf_inv_shear)
    rf_opr_controlling = min(rf_opr_moment, rf_opr_shear)
    print(f"\\nControlling Inventory RF: {rf_inv_controlling:.3f}")
    print(f"Controlling Operating RF: {rf_opr_controlling:.3f}")
else:
    print("No HL-93 vehicle found in live_loads. Add it to compute Inv/Opr ratings.")"""))

cells.append(mk("markdown", """---
## 8. Legal Load Rating

Legal vehicles per MBE 6A.4.4.2.1: AASHTO Type 3, 3S2, 3-3; Posting loads SU4-SU7;
Emergency vehicles EV2, EV3; Ohio Legal loads OH 2F1, 3F1, 5C1."""))

cells.append(mk("code", """# ============================================================
# Legal Load Rating
# ============================================================

# ADT/ADTT for gamma_LL selection
adtt = None
if bridge_tims:
    adt = bridge_tims.adt
    # Approximate ADTT as 10% of ADT if no truck percentage available
    adtt = int(adt * 0.10) if adt else None
    print(f"ADT from TIMS: {adt}, Estimated ADTT: {adtt}")

gamma_ll_legal = get_legal_gamma_ll(adtt)
print(f"Legal gamma_LL: {gamma_ll_legal} (ADTT = {adtt or 'unknown'})")

# Legal vehicles
LEGAL_VEHICLES = ["Type 3", "Type 3S2", "Type 3-3", "SU4", "SU5", "SU6", "SU7",
                  "EV2", "EV3", "OH 2F1", "OH 3F1", "OH 5C1"]

legal_results = []
for ll in live_loads:
    if any(lv in ll.vehicle_name for lv in LEGAL_VEHICLES):
        rf_m = compute_rf(C_moment, dead.M_DC, dead.M_DW, ll.M_LL,
                          gamma_LL=gamma_ll_legal)
        rf_v = compute_rf(C_shear, dead.V_DC, dead.V_DW, ll.V_LL,
                          gamma_LL=gamma_ll_legal)
        rf_ctrl = min(rf_m, rf_v)
        legal_results.append({
            "Vehicle": ll.vehicle_name,
            "RF (Moment)": f"{rf_m:.3f}",
            "RF (Shear)": f"{rf_v:.3f}",
            "RF (Controlling)": f"{rf_ctrl:.3f}",
            "Controls": "Moment" if rf_m < rf_v else "Shear",
            "Status": "PASS" if rf_ctrl >= 1.0 else "FAIL",
        })

if legal_results:
    legal_df = pd.DataFrame(legal_results)
    display(Markdown("### Legal Load Rating Results"))
    display(legal_df)
else:
    print("No legal vehicles found in live_loads list.")"""))

cells.append(mk("markdown", """---
## 9. Permit Load Rating

ODOT permit vehicles: OH 2F1, OH 3F1, OH 5C1, PL 60T, PL 65T."""))

cells.append(mk("code", """# ============================================================
# Permit Load Rating
# ============================================================

PERMIT_VEHICLES = ["OH 2F1", "OH 3F1", "OH 5C1", "PL 60T", "PL 65T"]

permit_results = []
for ll in live_loads:
    if any(pv in ll.vehicle_name for pv in PERMIT_VEHICLES):
        rf_routine = compute_rf(C_moment, dead.M_DC, dead.M_DW, ll.M_LL,
                                gamma_LL=GAMMA_LL_TABLE["Permit_routine"])
        rf_special = compute_rf(C_moment, dead.M_DC, dead.M_DW, ll.M_LL,
                                gamma_LL=GAMMA_LL_TABLE["Permit_special"])
        permit_results.append({
            "Vehicle": ll.vehicle_name,
            "RF Routine (gamma=1.20)": f"{rf_routine:.3f}",
            "RF Special (gamma=1.10)": f"{rf_special:.3f}",
            "Routine Status": "PASS" if rf_routine >= 1.0 else "FAIL",
        })

if permit_results:
    permit_df = pd.DataFrame(permit_results)
    display(Markdown("### Permit Load Rating Results"))
    display(permit_df)
else:
    print("No permit vehicles found in live_loads list.")"""))

cells.append(mk("markdown", """---
## 10. Posting Analysis (MBE 6A.8)

If any legal load RF < 1.0, the bridge requires load posting.
Posted weight = RF x Gross Vehicle Weight (GVW)."""))

cells.append(mk("code", """# ============================================================
# Posting Analysis
# ============================================================

# Approximate GVW for each vehicle (kips)
VEHICLE_GVW = {
    "Type 3": 25.0, "Type 3S2": 36.0, "Type 3-3": 40.0,
    "SU4": 27.0, "SU5": 31.0, "SU6": 34.0, "SU7": 38.0,
    "EV2": 33.0, "EV3": 42.0,
    "OH 2F1": 20.0, "OH 3F1": 25.0, "OH 5C1": 40.0,
}

posting_required = False
posting_results = []

for ll in live_loads:
    if any(lv in ll.vehicle_name for lv in LEGAL_VEHICLES):
        rf_m = compute_rf(C_moment, dead.M_DC, dead.M_DW, ll.M_LL,
                          gamma_LL=gamma_ll_legal)
        rf_v = compute_rf(C_shear, dead.V_DC, dead.V_DW, ll.V_LL,
                          gamma_LL=gamma_ll_legal)
        rf_ctrl = min(rf_m, rf_v)

        if rf_ctrl < 1.0:
            posting_required = True
            gvw = VEHICLE_GVW.get(ll.vehicle_name, 0)
            posted_weight = rf_ctrl * gvw if gvw > 0 else 0
            posting_results.append({
                "Vehicle": ll.vehicle_name,
                "RF": f"{rf_ctrl:.3f}",
                "GVW (tons)": f"{gvw:.1f}",
                "Posted Weight (tons)": f"{posted_weight:.1f}",
            })

if posting_required:
    display(Markdown("### POSTING REQUIRED"))
    display(pd.DataFrame(posting_results))
else:
    print("No posting required. All legal load RFs >= 1.0.")"""))

cells.append(mk("markdown", """---
## 11. Results Summary"""))

cells.append(mk("code", """# ============================================================
# Complete Rating Summary
# ============================================================

display(Markdown("### Bridge Load Rating Summary"))
display(Markdown(f"**SFN:** {SFN or '(not set)'}"))
display(Markdown(f"**Member:** {member.member_id} ({member.member_type})"))
display(Markdown(f"**Span:** {member.span_length} ft"))
display(Markdown(f"**phi_c:** {phi_c}, **phi_s:** {phi_s}"))

# Build comprehensive summary table
all_results = []

# HL-93
if hl93:
    all_results.append({"Vehicle": "HL-93", "Level": "Inventory",
                        "RF": f"{rf_inv_controlling:.3f}",
                        "Status": "PASS" if rf_inv_controlling >= 1.0 else "FAIL"})
    all_results.append({"Vehicle": "HL-93", "Level": "Operating",
                        "RF": f"{rf_opr_controlling:.3f}",
                        "Status": "PASS" if rf_opr_controlling >= 1.0 else "FAIL"})

# Legal
for ll in live_loads:
    if any(lv in ll.vehicle_name for lv in LEGAL_VEHICLES):
        rf_m = compute_rf(C_moment, dead.M_DC, dead.M_DW, ll.M_LL, gamma_LL=gamma_ll_legal)
        rf_v = compute_rf(C_shear, dead.V_DC, dead.V_DW, ll.V_LL, gamma_LL=gamma_ll_legal)
        rf_ctrl = min(rf_m, rf_v)
        all_results.append({"Vehicle": ll.vehicle_name, "Level": "Legal",
                            "RF": f"{rf_ctrl:.3f}",
                            "Status": "PASS" if rf_ctrl >= 1.0 else "FAIL"})

# Permit
for ll in live_loads:
    if any(pv in ll.vehicle_name for pv in PERMIT_VEHICLES):
        rf = compute_rf(C_moment, dead.M_DC, dead.M_DW, ll.M_LL,
                        gamma_LL=GAMMA_LL_TABLE["Permit_routine"])
        all_results.append({"Vehicle": ll.vehicle_name, "Level": "Permit (routine)",
                            "RF": f"{rf:.3f}",
                            "Status": "PASS" if rf >= 1.0 else "FAIL"})

summary_df = pd.DataFrame(all_results)
display(summary_df)

print(f"\\nPosting Required: {'YES' if posting_required else 'No'}")"""))

cells.append(mk("markdown", """---
## 12. BrR Comparison (Optional)

If BrR data was loaded, compare computed RFs against the database values."""))

cells.append(mk("code", """# ============================================================
# BrR Database Comparison
# ============================================================

if bridge_brr and bridge_brr.controlling_rating.inventory_rf is not None:
    cr = bridge_brr.controlling_rating
    display(Markdown("### BrR Database vs. Computed"))
    comparison = pd.DataFrame({
        "Source": ["BrR Database", "This Notebook"],
        "Inventory RF": [cr.inventory_rf, rf_inv_controlling if hl93 else "N/A"],
        "Operating RF": [cr.operating_rf, rf_opr_controlling if hl93 else "N/A"],
        "Controlling Vehicle": [cr.controlling_vehicle, "HL-93"],
        "Rating Method": [str(cr.rating_method), "LRFR"],
    })
    display(comparison)
else:
    print("No BrR data available for comparison.")
    print("Connect to BrR by setting SFN above.")"""))

cells.append(mk("markdown", """---
## Appendix: Load Factor Reference

### MBE Table 6A.4.2.2-1 (Strength I)
| Load | gamma_max | gamma_min |
|------|-----------|-----------|
| DC | 1.25 | 0.90 |
| DW | 1.50 | 0.65 |
| LL (Inventory) | 1.75 | -- |
| LL (Operating) | 1.35 | -- |
| LL (Legal) | 1.30-1.45 | -- |
| IM | 0.33 | -- |"""))

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

with open("Notebooks/ODOT Bridge Load Rating.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Built ODOT Bridge Load Rating.ipynb with {len(cells)} cells")
