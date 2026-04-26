"""Build Notebook 2: ODOT Deck Edge / Overhang Design (BDM 309 / AASHTO A13)"""
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

# ---------- Cell 1: Title / Intro ----------
cells.append(mk("markdown", """# ODOT Deck Edge / Overhang Design
**BDM 309 / AASHTO LRFD A13**

This notebook designs the deck overhang and verifies the integrated concrete
parapet (railing) anchorage for an ODOT bridge per:

- AASHTO LRFD A13.2 through A13.4 (deck overhang design for railing loads)
- ODOT BDM Section 309 (TST railing, anchor rod design)
- AASHTO LRFD Section 5.6 (concrete flexural design)

Three load cases are evaluated at three design sections:

| Case | Load Combination | Reference |
|------|-----------------|-----------|
| 1 | Extreme Event II (vehicular collision) | AASHTO A13.4.1 |
| 2 | Extreme Event II (vertical collision force) | AASHTO A13.2 |
| 3 | Strength I (DL + LL) | AASHTO Table 3.4.1-1 |

The overhang must be designed so the **parapet fails before the deck**
(capacity-protection philosophy)."""))

# ---------- Cell 2: References ----------
cells.append(mk("markdown", """---
## References
- ODOT Bridge Design Manual (BDM), Section 309
- AASHTO LRFD Bridge Design Specifications, 9th Edition, Appendix A13.2 - A13.4
- AASHTO LRFD Section 5.6 (Flexural Design of Concrete Members)
- AASHTO LRFD Section 5.7.5 (Anchorage to Concrete)
- ODOT TST (Tall Solid Type) TL-4 Railing Standard Drawings"""))

# ---------- Cell 3: Imports ----------
cells.append(mk("code", """# ============================================================
# Imports
# ============================================================
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from IPython.display import display, Markdown

# Civilpy load factors (optional)
try:
    from civilpy.structural.aashto.load_definitions import load_combinations
    CIVILPY_AVAILABLE = True
except ImportError:
    CIVILPY_AVAILABLE = False

print("Imports loaded.")"""))

# ---------- Cell 4: Section 1 Markdown ----------
cells.append(mk("markdown", """---
## 1. Geometry & Material Properties"""))

# ---------- Cell 5: OverhangInput ----------
cells.append(mk("code", """# ============================================================
# Overhang Input Parameters
# ============================================================

class OverhangInput(BaseModel):
    \"\"\"Deck overhang geometry and material properties.\"\"\"
    overhang_length: float = Field(..., description="Overhang from CL exterior girder to edge of deck (ft)")
    slab_thickness: float = Field(..., description="Structural slab thickness (in)")
    slab_fc: float = Field(default=4.5, description="Concrete compressive strength (ksi)")
    rebar_fy: float = Field(default=60.0, description="Reinforcing steel yield strength (ksi)")
    cover_top: float = Field(default=2.5, description="Top cover to center of top mat rebar (in)")
    cover_bot: float = Field(default=1.0, description="Bottom cover to center of bottom mat rebar (in)")
    fws_thickness: float = Field(default=0.0, description="Future wearing surface thickness (in)")
    girder_spacing: float = Field(..., description="Interior girder spacing (ft)")
    parapet_type: str = Field(default="TST TL-4", description="Parapet type designation")

# USER INPUT
overhang = OverhangInput(
    overhang_length=3.25,   # ft
    slab_thickness=8.5,     # in
    slab_fc=4.5,            # ksi
    rebar_fy=60.0,          # ksi
    cover_top=2.5,          # in
    cover_bot=1.0,          # in
    fws_thickness=0.5,      # in
    girder_spacing=8.0,     # ft
    parapet_type="TST TL-4",
)

print(f"Overhang length: {overhang.overhang_length} ft")
print(f"Slab thickness: {overhang.slab_thickness} in")
print(f"f'c = {overhang.slab_fc} ksi, fy = {overhang.rebar_fy} ksi")
print(f"Girder spacing: {overhang.girder_spacing} ft")"""))

# ---------- Cell 6: ParapetProperties ----------
cells.append(mk("code", """# ============================================================
# Parapet Properties (ODOT 42-in TST TL-4 Railing)
# ============================================================

class ParapetProperties(BaseModel):
    \"\"\"Concrete parapet / railing properties per crash-test analysis.\"\"\"
    height: float = Field(default=42.0, description="Parapet height (in)")
    weight: float = Field(default=505.0, description="Parapet weight (plf)")
    Mc: float = Field(default=17.83, description="Flexural resistance about vertical axis (kip-ft/ft)")
    Lc: float = Field(default=11.86, description="Critical yield line length (ft)")
    Rw: float = Field(default=117.4, description="Transverse resistance of railing (kips)")

# Default values for ODOT 42-in TST TL-4 railing
parapet = ParapetProperties()

print(f"Parapet type: {overhang.parapet_type}")
print(f"Height: {parapet.height} in, Weight: {parapet.weight} plf")
print(f"Mc = {parapet.Mc} kip-ft/ft, Lc = {parapet.Lc} ft, Rw = {parapet.Rw} kips")"""))

# ---------- Cell 7: Section 2 Markdown ----------
cells.append(mk("markdown", """---
## 2. Design Sections

Per AASHTO A13.4.1, the overhang is checked at three sections:

- **Section 1A** - Inside face of parapet (at root of parapet)
- **Section 1B** - At exterior girder centerline
- **Section 1C** - At first interior girder (optional; used for negative moment check)"""))

# ---------- Cell 8: Design Sections Code ----------
cells.append(mk("code", """# ============================================================
# Design Sections & Effective Depths
# ============================================================

# Parapet base width (approximate for TST railing)
parapet_base_width = 15.0  # in (1.25 ft)

# Distance from deck edge to inside face of parapet
dist_edge_to_parapet_inside = parapet_base_width / 12.0  # ft

# Design section distances from deck edge
x_1A = dist_edge_to_parapet_inside  # Inside face of parapet
x_1B = overhang.overhang_length     # CL exterior girder
x_1C = overhang.overhang_length + overhang.girder_spacing  # CL first interior girder

# Assume #5 bars (0.625 in diameter) for top mat
bar_dia = 0.625  # in (#5 bar)

# Effective depth at each section (assuming uniform slab thickness in overhang)
d_1A = overhang.slab_thickness - overhang.cover_top - bar_dia / 2
d_1B = overhang.slab_thickness - overhang.cover_top - bar_dia / 2
d_1C = overhang.slab_thickness - overhang.cover_top - bar_dia / 2

print(f"Section 1A: x = {x_1A:.2f} ft from deck edge, d = {d_1A:.3f} in")
print(f"Section 1B: x = {x_1B:.2f} ft from deck edge, d = {d_1B:.3f} in")
print(f"Section 1C: x = {x_1C:.2f} ft from deck edge, d = {d_1C:.3f} in")
print(f"Bar size: #{int(bar_dia / 0.125)} (dia = {bar_dia} in)")"""))

# ---------- Cell 9: Section 3 Markdown ----------
cells.append(mk("markdown", """---
## 3. Dead Loads (DC, DW)

Dead loads on the overhang include:
- **DC**: Self-weight of slab, weight of parapet
- **DW**: Future wearing surface (applied only to roadway, not under parapet)"""))

# ---------- Cell 10: Dead Load Code ----------
cells.append(mk("code", """# ============================================================
# Dead Load Calculations
# ============================================================

gamma_conc = 0.150  # kcf (normal weight concrete)

# Slab self-weight per foot of bridge length
w_slab = (overhang.slab_thickness / 12.0) * gamma_conc  # ksf

# Parapet weight as line load (per foot of bridge length)
w_parapet = parapet.weight / 1000.0  # kips/ft (klf)

# Future wearing surface
w_fws = (overhang.fws_thickness / 12.0) * gamma_conc  # ksf

# Moment at each section from cantilever action (per foot of bridge length)
# DC moments (slab + parapet)
# Slab moment = w_slab * cantilever_arm^2 / 2
# Parapet moment = w_parapet * distance_from_parapet_CL_to_section

# Parapet CL distance from deck edge
parapet_cg = parapet_base_width / 12.0 / 2.0  # ft from deck edge (approx CG)

# --- Section 1A ---
arm_slab_1A = x_1A  # cantilever arm for slab
M_DC_1A = w_slab * arm_slab_1A**2 / 2.0  # slab self-weight
# Parapet is outboard of 1A, so parapet contributes no moment at 1A
# (parapet is on the other side of this section)
M_DC_1A += 0.0  # parapet load is on the free side
M_DW_1A = 0.0   # No FWS under parapet

# --- Section 1B ---
arm_slab_1B = x_1B
M_DC_1B = w_slab * arm_slab_1B**2 / 2.0
# Parapet moment at 1B
M_DC_1B += w_parapet * (x_1B - parapet_cg)
# FWS from parapet inside face to exterior girder
fws_arm = x_1B - x_1A
M_DW_1B = w_fws * fws_arm**2 / 2.0 + w_fws * fws_arm * (x_1A)
# Simplified: FWS moment = w_fws * (x_1B - x_1A) * ((x_1B - x_1A)/2 + 0)
# More precisely, FWS acts from x_1A to x_1B measured from deck edge
# Moment at 1B = w_fws * (x_1B - x_1A)^2 / 2
M_DW_1B = w_fws * fws_arm**2 / 2.0

# --- Section 1C ---
# For Section 1C (interior girder), use AASHTO approximate strip method
# Overhang moment at 1C is typically checked using interior strip design
# For this check, compute cantilever moment at exterior girder including
# both overhang and interior span effects
arm_slab_1C = x_1B  # cantilever portion only
M_DC_1C = M_DC_1B  # Same overhang DC as 1B (conservative)
M_DW_1C = M_DW_1B  # Same overhang DW as 1B (conservative)

print("Dead Load Moments (unfactored, per foot of bridge):")
print(f"  Section 1A: M_DC = {M_DC_1A:.3f} kip-ft/ft, M_DW = {M_DW_1A:.3f} kip-ft/ft")
print(f"  Section 1B: M_DC = {M_DC_1B:.3f} kip-ft/ft, M_DW = {M_DW_1B:.3f} kip-ft/ft")
print(f"  Section 1C: M_DC = {M_DC_1C:.3f} kip-ft/ft, M_DW = {M_DW_1C:.3f} kip-ft/ft")"""))

# ---------- Cell 11: Section 4 Markdown ----------
cells.append(mk("markdown", """---
## 4. Live Load

Per AASHTO A13.4.1, the design wheel load is 16 kips placed:
- **Design truck**: 1 ft from face of barrier (for Strength I)
- **At barrier face**: (for Extreme Event)

The effective strip width for overhang is:
$$E = 26.0 + 6.6 \\cdot S \\quad \\text{(in)}$$
where S = distance from load to support point (ft)."""))

# ---------- Cell 12: Live Load Code ----------
cells.append(mk("code", """# ============================================================
# Live Load on Overhang
# ============================================================

P_wheel = 16.0  # kips (design truck wheel)
IM = 0.33       # Dynamic load allowance for Strength

# Wheel position for Strength I: 1 ft from barrier face
# Barrier face is at x = 0 (deck edge) for exterior face
# Wheel at 1 ft from barrier face = parapet_base_width/12 + 1.0 ft from deck edge
x_wheel_strength = parapet_base_width / 12.0 + 1.0  # ft from deck edge

# Wheel position for Extreme Event: at barrier face
x_wheel_extreme = 0.0  # ft from deck edge (at face of barrier)

# Effective strip width for overhang (AASHTO Table 4.6.2.1.3-1)
# E = 26.0 + 6.6*S (in), where S = distance from wheel to section (ft)

# --- Section 1A (Strength I) ---
S_1A_str = abs(x_1A - x_wheel_strength)
E_1A_str = (26.0 + 6.6 * S_1A_str * 12.0) / 12.0 if S_1A_str > 0 else 26.0 / 12.0  # ft
# Note: S should be in feet for the formula with inches result
E_1A_str = (26.0 + 6.6 * S_1A_str) / 12.0  # ft
M_LL_1A_str = P_wheel * (x_1A - x_wheel_strength) / max(E_1A_str, 1.0) if x_wheel_strength < x_1A else 0.0

# --- Section 1B (Strength I) ---
S_1B_str = abs(x_1B - x_wheel_strength)
E_1B_str = (26.0 + 6.6 * S_1B_str) / 12.0  # ft
M_LL_1B_str = P_wheel * (x_1B - x_wheel_strength) / max(E_1B_str, 1.0)

# --- Section 1C (Strength I) ---
# At interior girder, use interior strip width
E_1C_str = E_1B_str  # Conservative: use same strip width
M_LL_1C_str = M_LL_1B_str  # Conservative

print("Live Load Moments (unfactored, per foot of bridge, without IM):")
print(f"  Wheel position (Strength I): {x_wheel_strength:.2f} ft from deck edge")
print(f"  Section 1A: E = {E_1A_str:.2f} ft, M_LL = {M_LL_1A_str:.3f} kip-ft/ft")
print(f"  Section 1B: E = {E_1B_str:.2f} ft, M_LL = {M_LL_1B_str:.3f} kip-ft/ft")
print(f"  Section 1C: E = {E_1C_str:.2f} ft, M_LL = {M_LL_1C_str:.3f} kip-ft/ft")"""))

# ---------- Cell 13: Section 5 Markdown ----------
cells.append(mk("markdown", """---
## 5. Case 1: Extreme Event II - Vehicular Collision (AASHTO A13.4.1)

The railing capacity is distributed into the deck over the yield line length.
The overhang must resist the bending moment and axial tension from the railing
failure mechanism.

$$M_{collision} = M_c + \\frac{R_w \\cdot (H + h_{parapet}/12)}{L_c + 2H}$$

$$T = \\frac{R_w}{L_c + 2H}$$

where H = height of wall above deck surface (ft)."""))

# ---------- Cell 14: Case 1 Code ----------
cells.append(mk("code", """# ============================================================
# Case 1: Extreme Event II (Vehicular Collision)
# ============================================================

# Load factors for Extreme Event II
gamma_DC_ee = 1.00
gamma_DW_ee = 1.00
gamma_LL_ee = 0.50  # LL factor for Extreme Event II

H = parapet.height / 12.0  # Parapet height in ft

# Collision force distributed over yield line length
# Moment at base of parapet per unit length
M_collision = parapet.Mc + (parapet.Rw * H) / (parapet.Lc + 2 * H)

# Axial tension per unit length at base of parapet
T_collision = parapet.Rw / (parapet.Lc + 2 * H)

print(f"Parapet height H = {H:.2f} ft")
print(f"Yield line length Lc = {parapet.Lc:.2f} ft")
print(f"M_collision = {M_collision:.3f} kip-ft/ft")
print(f"T_collision = {T_collision:.3f} kips/ft")

# --- Section 1A (inside face of parapet) ---
# Extreme Event: gamma_DC=1.00, gamma_LL=0.50
Mu_case1_1A = gamma_DC_ee * M_DC_1A + M_collision
Tu_case1_1A = T_collision

# --- Section 1B (at exterior girder CL) ---
Mu_case1_1B = gamma_DC_ee * M_DC_1B + M_collision
Tu_case1_1B = T_collision

# --- Section 1C (at first interior girder) ---
Mu_case1_1C = gamma_DC_ee * M_DC_1C + M_collision
Tu_case1_1C = T_collision

print(f"\\nCase 1 Factored Moments (Extreme Event II):")
print(f"  Section 1A: Mu = {Mu_case1_1A:.3f} kip-ft/ft, Tu = {Tu_case1_1A:.3f} kips/ft")
print(f"  Section 1B: Mu = {Mu_case1_1B:.3f} kip-ft/ft, Tu = {Tu_case1_1B:.3f} kips/ft")
print(f"  Section 1C: Mu = {Mu_case1_1C:.3f} kip-ft/ft, Tu = {Tu_case1_1C:.3f} kips/ft")"""))

# ---------- Cell 15: Section 6 Markdown ----------
cells.append(mk("markdown", """---
## 6. Case 2: Vertical Collision Force (AASHTO A13.2)

For TL-4 railing, the vertical design force is:
$$F_v = 18 \\text{ kips (downward)}$$

This force is distributed over the yield line length $L_c$ and applied at the
top of the parapet. For concrete parapets integral with the deck, **Case 2
rarely controls** over Case 1."""))

# ---------- Cell 16: Case 2 Code ----------
cells.append(mk("code", """# ============================================================
# Case 2: Vertical Collision Force (AASHTO A13.2, Table A13.2-1)
# ============================================================

# TL-4 vertical force
Fv = 18.0  # kips (downward, per AASHTO Table A13.2-1 for TL-4)

# Distributed over yield line length Lc
Fv_per_ft = Fv / parapet.Lc  # kips/ft

# Moment at each section = Fv_per_ft * cantilever arm
# Applied at edge of deck (conservative)

# --- Section 1A ---
Mu_case2_1A = gamma_DC_ee * M_DC_1A + Fv_per_ft * x_1A

# --- Section 1B ---
Mu_case2_1B = gamma_DC_ee * M_DC_1B + Fv_per_ft * x_1B

# --- Section 1C ---
Mu_case2_1C = gamma_DC_ee * M_DC_1C + Fv_per_ft * x_1B  # conservative

print(f"Fv = {Fv} kips, distributed over Lc = {parapet.Lc} ft")
print(f"Fv per ft = {Fv_per_ft:.3f} kips/ft")
print(f"\\nCase 2 Factored Moments (Vertical Collision Force):")
print(f"  Section 1A: Mu = {Mu_case2_1A:.3f} kip-ft/ft")
print(f"  Section 1B: Mu = {Mu_case2_1B:.3f} kip-ft/ft")
print(f"  Section 1C: Mu = {Mu_case2_1C:.3f} kip-ft/ft")
print(f"\\nNote: For concrete parapets, Case 2 rarely controls.")"""))

# ---------- Cell 17: Section 7 Markdown ----------
cells.append(mk("markdown", """---
## 7. Case 3: Strength I (DL + LL)

Standard Strength I load combination:
$$M_u = 1.25 \\cdot M_{DC} + 1.50 \\cdot M_{DW} + 1.75 \\cdot M_{LL} \\cdot (1 + IM)$$"""))

# ---------- Cell 18: Case 3 Code ----------
cells.append(mk("code", """# ============================================================
# Case 3: Strength I (DL + LL)
# ============================================================

gamma_DC_str = 1.25
gamma_DW_str = 1.50
gamma_LL_str = 1.75
IM_str = 0.33

# --- Section 1A ---
Mu_case3_1A = (gamma_DC_str * M_DC_1A
               + gamma_DW_str * M_DW_1A
               + gamma_LL_str * M_LL_1A_str * (1 + IM_str))

# --- Section 1B ---
Mu_case3_1B = (gamma_DC_str * M_DC_1B
               + gamma_DW_str * M_DW_1B
               + gamma_LL_str * M_LL_1B_str * (1 + IM_str))

# --- Section 1C ---
Mu_case3_1C = (gamma_DC_str * M_DC_1C
               + gamma_DW_str * M_DW_1C
               + gamma_LL_str * M_LL_1C_str * (1 + IM_str))

print("Case 3 Factored Moments (Strength I):")
print(f"  Section 1A: Mu = {Mu_case3_1A:.3f} kip-ft/ft")
print(f"  Section 1B: Mu = {Mu_case3_1B:.3f} kip-ft/ft")
print(f"  Section 1C: Mu = {Mu_case3_1C:.3f} kip-ft/ft")"""))

# ---------- Cell 19: Section 8 Markdown ----------
cells.append(mk("markdown", """---
## 8. Governing Moment at Each Section

Compare all three cases at each design section to determine the governing
demand."""))

# ---------- Cell 20: Governing Code ----------
cells.append(mk("code", """# ============================================================
# Governing Moment Summary
# ============================================================

# Build comparison table
gov_data = []
for section, cases in [
    ("1A", {
        "Case 1 (Collision)": (Mu_case1_1A, Tu_case1_1A),
        "Case 2 (Vert. Force)": (Mu_case2_1A, 0.0),
        "Case 3 (Strength I)": (Mu_case3_1A, 0.0),
    }),
    ("1B", {
        "Case 1 (Collision)": (Mu_case1_1B, Tu_case1_1B),
        "Case 2 (Vert. Force)": (Mu_case2_1B, 0.0),
        "Case 3 (Strength I)": (Mu_case3_1B, 0.0),
    }),
    ("1C", {
        "Case 1 (Collision)": (Mu_case1_1C, Tu_case1_1C),
        "Case 2 (Vert. Force)": (Mu_case2_1C, 0.0),
        "Case 3 (Strength I)": (Mu_case3_1C, 0.0),
    }),
]:
    for case_name, (mu, tu) in cases.items():
        gov_data.append({
            "Section": section,
            "Case": case_name,
            "Mu (kip-ft/ft)": f"{mu:.3f}",
            "Tu (kips/ft)": f"{tu:.3f}",
        })

gov_df = pd.DataFrame(gov_data)
display(Markdown("### Moment Comparison at All Sections"))
display(gov_df)

# Determine governing case at each section
gov_results = {}
for section, cases in [
    ("1A", [("Case 1", Mu_case1_1A, Tu_case1_1A),
            ("Case 2", Mu_case2_1A, 0.0),
            ("Case 3", Mu_case3_1A, 0.0)]),
    ("1B", [("Case 1", Mu_case1_1B, Tu_case1_1B),
            ("Case 2", Mu_case2_1B, 0.0),
            ("Case 3", Mu_case3_1B, 0.0)]),
    ("1C", [("Case 1", Mu_case1_1C, Tu_case1_1C),
            ("Case 2", Mu_case2_1C, 0.0),
            ("Case 3", Mu_case3_1C, 0.0)]),
]:
    governing = max(cases, key=lambda c: c[1])
    gov_results[section] = {"case": governing[0], "Mu": governing[1], "Tu": governing[2]}
    print(f"Section {section}: Governing = {governing[0]}, Mu = {governing[1]:.3f} kip-ft/ft")"""))

# ---------- Cell 21: Section 9 Markdown ----------
cells.append(mk("markdown", """---
## 9. Reinforcement Design (AASHTO 5.6)

Design top mat transverse reinforcement in the overhang for the governing
moment (and axial tension for Case 1).

For combined bending + tension (Case 1), the net moment approach is used:
$$M_{u,net} = M_u - T_u \\cdot (d - h/2)$$

Then design for $M_{u,net}$ as pure flexure and add tension reinforcement."""))

# ---------- Cell 22: Rebar Design Code ----------
cells.append(mk("code", """# ============================================================
# Reinforcement Design Function
# ============================================================

def design_rebar(Mu, b, d, fc, fy, Tu=0.0, h=None, phi=0.90):
    \"\"\"Design flexural reinforcement per AASHTO 5.6.

    Args:
        Mu: Factored moment (kip-ft/ft)
        b: Design width (in), typically 12 in for per-foot design
        d: Effective depth (in)
        fc: Concrete compressive strength (ksi)
        fy: Steel yield strength (ksi)
        Tu: Factored axial tension (kips/ft), default 0
        h: Total slab thickness (in), needed if Tu > 0
        phi: Resistance factor (1.0 for Extreme Event, 0.90 for Strength)

    Returns:
        dict with As_required, bar_spacing, a, c_over_de, status
    \"\"\"
    Mu_ft = abs(Mu)  # kip-ft/ft
    Mu_in = Mu_ft * 12.0  # kip-in per ft width

    if Tu > 0 and h is not None:
        # Combined bending + tension: net moment approach
        Mu_net = Mu_in - Tu * (d - h / 2.0)
        Mu_net = max(Mu_net, 0.0)
    else:
        Mu_net = Mu_in

    # Iterative solution for As
    # Initial guess: assume a = 0.1*d
    a = 0.1 * d
    for _ in range(20):
        As = Mu_net / (phi * fy * (d - a / 2.0))
        a_new = As * fy / (0.85 * fc * b)
        if abs(a_new - a) < 0.001:
            break
        a = a_new

    # Add tension steel if applicable
    if Tu > 0:
        As_tension = Tu / (phi * fy)
        As = As + As_tension

    # Check c/de ratio (AASHTO 5.6.2.1)
    beta1 = max(0.65, 0.85 - 0.05 * (fc - 4.0))
    c = a / beta1
    c_over_de = c / d

    # Net tensile strain check
    epsilon_t = 0.003 * (d - c) / c if c > 0 else float("inf")

    status = "OK"
    if c_over_de > 0.42:
        status = "FAIL: c/de > 0.42"
    if epsilon_t < 0.004:
        status = "FAIL: net tensile strain < 0.004"

    # Bar spacing for #5 bars (As_bar = 0.31 in2)
    As_bar = 0.31  # #5 bar
    spacing = As_bar / As * b if As > 0 else 0.0

    return {
        "As_required": round(As, 4),
        "a": round(a, 3),
        "c_over_de": round(c_over_de, 4),
        "epsilon_t": round(epsilon_t, 5),
        "bar_spacing": round(spacing, 2),
        "status": status,
    }

print("design_rebar() function defined.")"""))

# ---------- Cell 23: Rebar Results Code ----------
cells.append(mk("code", """# ============================================================
# Reinforcement Design Results
# ============================================================

b = 12.0  # in (per-foot design width)
h = overhang.slab_thickness

rebar_results = []
for section, d_eff, gov in [
    ("1A", d_1A, gov_results["1A"]),
    ("1B", d_1B, gov_results["1B"]),
    ("1C", d_1C, gov_results["1C"]),
]:
    case = gov["case"]
    Mu = gov["Mu"]
    Tu = gov["Tu"]

    # phi = 1.0 for Extreme Event (Cases 1, 2), 0.90 for Strength (Case 3)
    if "Case 3" in case:
        phi = 0.90
    else:
        phi = 1.00

    result = design_rebar(Mu, b, d_eff, overhang.slab_fc, overhang.rebar_fy,
                          Tu=Tu, h=h, phi=phi)
    result["Section"] = section
    result["Gov. Case"] = case
    result["Mu (kip-ft/ft)"] = f"{Mu:.3f}"
    result["Tu (kips/ft)"] = f"{Tu:.3f}"
    result["phi"] = phi
    rebar_results.append(result)

rebar_df = pd.DataFrame(rebar_results)
display_cols = ["Section", "Gov. Case", "Mu (kip-ft/ft)", "Tu (kips/ft)", "phi",
                "As_required", "bar_spacing", "c_over_de", "status"]
display(Markdown("### Reinforcement Design Summary"))
display(rebar_df[display_cols])

# Maximum required As controls the design
max_As = max(r["As_required"] for r in rebar_results)
max_section = [r["Section"] for r in rebar_results if r["As_required"] == max_As][0]
print(f"\\nControlling section: {max_section}")
print(f"Maximum required As = {max_As:.4f} in2/ft")
print(f"Use #5 bars @ {min(r['bar_spacing'] for r in rebar_results):.1f} in o.c.")"""))

# ---------- Cell 24: Section 10 Markdown ----------
cells.append(mk("markdown", """---
## 10. Capacity Protection Check (AASHTO A13.4.1)

The overhang must be stronger than the parapet to ensure the parapet fails
first (ductile failure mode / capacity protection):

$$\\phi M_n^{overhang} \\geq M_c^{parapet}$$

where $M_c$ is the parapet flexural resistance about the vertical axis."""))

# ---------- Cell 25: Capacity Protection Code ----------
cells.append(mk("code", """# ============================================================
# Capacity Protection Check
# ============================================================

# Compute provided moment capacity at Section 1A (inside face of parapet)
# Use the controlling As from the design
As_provided = max_As  # Use the design As (at minimum)

# Provided capacity
a_prov = As_provided * overhang.rebar_fy / (0.85 * overhang.slab_fc * b)
phi_Mn = 1.0 * As_provided * overhang.rebar_fy * (d_1A - a_prov / 2.0) / 12.0  # kip-ft/ft

# Check
cap_protect_pass = phi_Mn >= parapet.Mc

print("Capacity Protection Check (AASHTO A13.4.1):")
print(f"  phi*Mn (overhang) = {phi_Mn:.3f} kip-ft/ft")
print(f"  Mc (parapet)      = {parapet.Mc:.3f} kip-ft/ft")
print(f"  phi*Mn >= Mc?     {'PASS' if cap_protect_pass else 'FAIL'}")

if not cap_protect_pass:
    # Compute required As for capacity protection
    result_cp = design_rebar(parapet.Mc, b, d_1A, overhang.slab_fc,
                             overhang.rebar_fy, phi=1.0)
    print(f"  Required As for capacity protection: {result_cp['As_required']:.4f} in2/ft")
    print(f"  Use #5 @ {result_cp['bar_spacing']:.1f} in o.c.")"""))

# ---------- Cell 26: Section 11 Markdown ----------
cells.append(mk("markdown", """---
## 11. TST Railing Anchor Rod Design (BDM 309)

Verify the railing anchor rods per AASHTO LRFD Section 5.7.5 / ACI 318
Appendix D provisions. Three failure modes are checked:

1. **Steel failure** of anchor rod
2. **Concrete breakout** failure
3. **Concrete pullout** failure"""))

# ---------- Cell 27: AnchorInput Code ----------
cells.append(mk("code", """# ============================================================
# Anchor Rod Input
# ============================================================

class AnchorInput(BaseModel):
    \"\"\"TST railing anchor rod properties.\"\"\"
    bolt_diameter: float = Field(default=0.75, description="Bolt diameter (in)")
    embed_depth: float = Field(default=8.0, description="Effective embedment depth hef (in)")
    edge_distance: float = Field(default=4.0, description="Edge distance ca1 (in)")
    bolt_spacing: float = Field(default=12.0, description="Bolt spacing (in)")
    fc: float = Field(default=4.5, description="Concrete compressive strength (ksi)")
    fut: float = Field(default=60.0, description="Bolt ultimate tensile strength (ksi)")
    n_bolts: int = Field(default=2, description="Number of bolts per connection")

# Default: 3/4" A307 bolts
anchor = AnchorInput()

print(f"Bolt: {anchor.bolt_diameter} in dia., A307 (fut = {anchor.fut} ksi)")
print(f"Embedment hef = {anchor.embed_depth} in")
print(f"Edge distance ca1 = {anchor.edge_distance} in")
print(f"Spacing = {anchor.bolt_spacing} in, n = {anchor.n_bolts} bolts")"""))

# ---------- Cell 28: Anchor Design Code ----------
cells.append(mk("code", """# ============================================================
# Anchor Rod Design (Three Failure Modes)
# ============================================================

# ----- 1. Steel Failure -----
# Ase for 3/4" bolt (tensile stress area)
Ase = 0.334  # in2 (for 3/4" bolt)
Ns = anchor.n_bolts * Ase * anchor.fut  # kips
phi_steel = 0.75
phi_Ns = phi_steel * Ns

print("1. Steel Failure:")
print(f"   Ase = {Ase} in2, Ns = {Ns:.2f} kips, phi*Ns = {phi_Ns:.2f} kips")

# ----- 2. Concrete Breakout -----
hef = anchor.embed_depth
ca1 = anchor.edge_distance

# Basic breakout strength
# Nb = k * sqrt(fc_psi) * hef^1.5 (ACI 318 / AASHTO)
fc_psi = anchor.fc * 1000.0  # convert ksi to psi
Nb = 24.0 * np.sqrt(fc_psi) * hef**1.5 / 1000.0  # kips

# Projected area ratio
ANco = 9.0 * hef**2  # in2 (single anchor, no edge effects)

# Actual projected area (accounting for edge distance)
# For a row of bolts near an edge:
c_a_min = min(ca1, 1.5 * hef)
ANc = min(ANco, (c_a_min + 1.5 * hef) * min(anchor.bolt_spacing + 3.0 * hef, 2.0 * 1.5 * hef))
# Simplified for single anchor near edge:
ANc_single = (c_a_min + 1.5 * hef) * (2.0 * 1.5 * hef)
ANc = min(ANc_single * anchor.n_bolts / anchor.n_bolts, ANco)  # Simplified

# Edge effect factor
psi_ed = min(1.0, 0.7 + 0.3 * ca1 / (1.5 * hef))

# Cracked concrete factor
psi_c = 1.0  # Assume cracked concrete (conservative)

Ncb = (ANc / ANco) * psi_ed * psi_c * Nb * anchor.n_bolts
phi_concrete = 0.65  # CCD method
phi_Ncb = phi_concrete * Ncb

print(f"\\n2. Concrete Breakout:")
print(f"   Nb = {Nb:.2f} kips, ANc/ANco = {ANc/ANco:.3f}")
print(f"   psi_ed = {psi_ed:.3f}, psi_c = {psi_c:.1f}")
print(f"   Ncb = {Ncb:.2f} kips, phi*Ncb = {phi_Ncb:.2f} kips")

# ----- 3. Concrete Pullout -----
# Np = 8 * Abrg * fc (ksi)
# Bearing area for 3/4" hex bolt head
# Head across flats = 1.125 in for 3/4" bolt -> Abrg ~ 0.60 in2
Abrg = 0.60  # in2 (bearing area of bolt head minus shaft area)
Np_single = 8.0 * Abrg * anchor.fc  # kips per bolt
Np = anchor.n_bolts * Np_single
phi_pullout = 0.65
phi_Np = phi_pullout * Np

print(f"\\n3. Concrete Pullout:")
print(f"   Abrg = {Abrg} in2, Np = {Np:.2f} kips, phi*Np = {phi_Np:.2f} kips")

# ----- Governing Anchor Capacity -----
phi_Nn_gov = min(phi_Ns, phi_Ncb, phi_Np)
gov_mode = ["Steel", "Breakout", "Pullout"][[phi_Ns, phi_Ncb, phi_Np].index(phi_Nn_gov)]

# Factored demand from Case 1
T_demand = T_collision * anchor.bolt_spacing / 12.0  # Convert from per-ft to per connection

anchor_pass = phi_Nn_gov >= T_demand

print(f"\\nGoverning anchor capacity: phi*Nn = {phi_Nn_gov:.2f} kips ({gov_mode})")
print(f"Factored tension demand: Tu = {T_demand:.2f} kips")
print(f"Anchor check: {'PASS' if anchor_pass else 'FAIL'}")"""))

# ---------- Cell 29: Section 12 Markdown ----------
cells.append(mk("markdown", """---
## 12. Results Summary"""))

# ---------- Cell 30: Summary Code ----------
cells.append(mk("code", """# ============================================================
# Complete Results Summary
# ============================================================

display(Markdown("### Deck Edge / Overhang Design Summary"))
display(Markdown(f"**Parapet:** {overhang.parapet_type}, H = {parapet.height} in"))
display(Markdown(f"**Overhang:** {overhang.overhang_length} ft, "
                 f"slab = {overhang.slab_thickness} in, "
                 f"f'c = {overhang.slab_fc} ksi"))

# Reinforcement summary
summary_data = []
for r in rebar_results:
    summary_data.append({
        "Section": r["Section"],
        "Gov. Case": r["Gov. Case"],
        "Mu (kip-ft/ft)": r["Mu (kip-ft/ft)"],
        "Tu (kips/ft)": r["Tu (kips/ft)"],
        "As Req'd (in2/ft)": f"{r['As_required']:.4f}",
        "Provided (#5 @ in)": f"{r['bar_spacing']:.1f}",
        "c/de": f"{r['c_over_de']:.4f}",
        "Status": r["status"],
    })

display(Markdown("### Overhang Reinforcement"))
display(pd.DataFrame(summary_data))

# Capacity protection
display(Markdown("### Capacity Protection (AASHTO A13.4.1)"))
cp_df = pd.DataFrame([{
    "Check": "phi*Mn >= Mc",
    "phi*Mn (kip-ft/ft)": f"{phi_Mn:.3f}",
    "Mc (kip-ft/ft)": f"{parapet.Mc:.3f}",
    "Status": "PASS" if cap_protect_pass else "FAIL",
}])
display(cp_df)

# Anchor rod summary
display(Markdown("### Anchor Rod Design (BDM 309)"))
anchor_df = pd.DataFrame([{
    "Failure Mode": "Steel",
    "phi*Nn (kips)": f"{phi_Ns:.2f}",
    "Status": "PASS" if phi_Ns >= T_demand else "FAIL",
}, {
    "Failure Mode": "Breakout",
    "phi*Nn (kips)": f"{phi_Ncb:.2f}",
    "Status": "PASS" if phi_Ncb >= T_demand else "FAIL",
}, {
    "Failure Mode": "Pullout",
    "phi*Nn (kips)": f"{phi_Np:.2f}",
    "Status": "PASS" if phi_Np >= T_demand else "FAIL",
}, {
    "Failure Mode": f"GOVERNING ({gov_mode})",
    "phi*Nn (kips)": f"{phi_Nn_gov:.2f}",
    "Status": "PASS" if anchor_pass else "FAIL",
}])
display(anchor_df)

# Overall pass/fail
all_rebar_ok = all(r["status"] == "OK" for r in rebar_results)
overall_pass = all_rebar_ok and cap_protect_pass and anchor_pass

display(Markdown(f"### Overall Design Status: **{'PASS' if overall_pass else 'FAIL'}**"))

if not overall_pass:
    if not all_rebar_ok:
        print("ISSUE: Reinforcement design does not satisfy c/de or strain limits.")
    if not cap_protect_pass:
        print("ISSUE: Capacity protection check failed. Increase overhang reinforcement.")
    if not anchor_pass:
        print("ISSUE: Anchor rod capacity insufficient. Increase embedment or bolt size.")"""))

# ============================================================
# Build notebook
# ============================================================
nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10.0"},
    },
    "cells": cells,
}

with open("Notebooks/ODOT Deck Edge Overhang Design.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Built ODOT Deck Edge Overhang Design.ipynb with {len(cells)} cells")
