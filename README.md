# CivilPy

![PyPI - License](https://img.shields.io/pypi/l/civilpy)
<img alt="Pipeline" src="https://daneparks.com/Dane/civilpy/badges/master/pipeline.svg">
<img alt="Coverage" src="https://daneparks.com/Dane/civilpy/badges/master/coverage.svg">
<img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/civilpy">
[![PyPI Downloads](https://static.pepy.tech/badge/civilpy/month)](https://pepy.tech/projects/civilpy)

Python tools for civil and structural engineering — every AISC steel shape as a Python object
with Pint units, NDS wood design, ACI 318 anchor checks, beam shear/moment/deflection diagrams,
built-up section properties, AASHTO/AREMA design references, Midas Civil API integration, and
ODOT/SNBI bridge asset management tools.

**[Source](https://daneparks.com/Dane/civilpy) · [Docs](https://dane.daneparks.com/civilpy) · [PyPI](https://pypi.org/project/civilpy/)**

---

## Installation

```bash
pip install civilpy
```

Optional dependency groups for heavier tools:

| Extra | What it adds |
|-------|-------------|
| `civilpy[db]` | PostgreSQL / Oracle connectors, SSH tunnel |
| `civilpy[pdf]` | PDF extraction (PyMuPDF, Camelot, Tesseract OCR) |
| `civilpy[geo]` | Folium maps, GeoTIFF tools |
| `civilpy[web]` | Selenium, Plotly |
| `civilpy[jupyter]` | Notebook utilities, ipywidgets |
| `civilpy[validation]` | Pydantic models for SNBI data validation |
| `civilpy[full]` | All of the above |

---

## AISC Steel Shapes

Every shape in the AISC Steel Construction Manual is available as a Python class. Properties
carry [Pint](https://pint.readthedocs.io/) units so dimensional arithmetic is automatic.

```python
from civilpy.structural.steel import W, HSS, C, L, Pipe, HP, WT, TwoL

# Wide-flange beam — all standard AISC section properties
beam = W("W36X150")
print(beam.depth)               # 35.9 in
print(beam.flange_width)        # 16.2 in
print(beam.I_x)                 # 9040.0 in⁴
print(beam.Z_x)                 # 581.0 in³  (plastic section modulus)
print(beam.S_x)                 # 504.0 in³  (elastic section modulus)
print(beam.r_x)                 # radius of gyration
print(beam.J)                   # torsional constant
print(beam.Cw)                  # warping constant
print(beam.slenderness_ratio_web)   # h/tw
print(beam.slenderness_ratio_flange)  # bf/2tf

# HSS rectangular and round tube sections
col = HSS("HSS12X8X.500")
print(col.tdes)                 # design wall thickness

# Channel sections
ch = C("C15X50")

# Angle sections
ang = L("L4X4X1/2")

# Pipe sections
pipe = Pipe("Pipe6STD")
print(pipe.OD, pipe.ID)

# HP bearing piles
pile = HP("HP14X117")

# Tee sections (split from W shapes)
tee = WT("WT18X150")

# Double angles
dang = TwoL("2L6X4X7/16SLBB")
```

### Units and dimensional math

All section properties use [Pint](https://pint.readthedocs.io/) units. Unit conversion and
arithmetic just work:

```python
from civilpy.general import units
from civilpy.structural.steel import W

beam = W("W24X76")

# Applied moment in kip-ft, convert for stress calculation
M = 400 * units("kip*ft")
S_x = beam.S_x.to("in^3")
fb = (M.to("kip*in") / S_x).to("ksi")
print(f"Bending stress: {fb:.2f}")   # 14.93 ksi

# Deflection — mix of units resolves automatically
E = 29000 * units("ksi")
I = beam.I_x.to("in^4")
L = 30 * units("ft").to("in")
w = 2 * units("kip/ft").to("kip/in")
delta = (5 * w * L**4) / (384 * E * I)
print(delta.to("in"))
```

### Historic shapes

Pre-AISC standardization shapes used in older bridges are available via `HistoricSteelSection`:

```python
from civilpy.structural.steel import HistoricSteelSection, WF

# Look up a historic WF shape by edition
section = WF("WF36X150")
print(section.I_x)
```

### Bolt weights

```python
from civilpy.structural.steel import get_bolt_weights

# A325 bolt, 1.5" long, 0.75" diameter, 2 washers
weight_per_bolt = get_bolt_weights(length=1.5, diameter=0.75, no_of_washers=2)
print(f"{weight_per_bolt:.4f} lbs/bolt")
```

---

## Built-Up Section Properties

`CrossSection` assembles a built-up section by stacking rectangular plates from the bottom up.
Each call to the instance appends the next component. Can also accept rolled shapes directly.

```python
from civilpy.structural.section_properties import CrossSection
from civilpy.structural.steel import W

# Plate girder: bottom flange + web + top flange
section = CrossSection(label="bottom flange", dimensions=(16, 1.5))
section(label="web",           dimensions=(0.5625, 54))
section(label="top flange",    dimensions=(16, 1.5))

print(f"Area:         {section.area:.2f} in²")
print(f"Neutral axis: {section.n:.2f} in from bottom")
print(f"I (strong):   {section.I_n:.2f} in⁴")

# Cover-plated rolled beam: start from a W shape, then add plates
beam = W("W33X201")
comp = CrossSection(label="W33X201", shape=beam)
comp(label="top cover plate", dimensions=(12, 0.75))
print(f"Composite I: {comp.I_n:.2f} in⁴")
```

---

## Wood Design (NDS)

Sawn lumber and glulam sections with NDS reference design values, adjustment factors, and
ASD/LRFD member checks. Sections are created from a size label, mirroring the steel workflow:

```python
from civilpy.structural.wood import LumberSection, GlulamSection
from civilpy.general import units

# Sawn lumber — dressed dimensions, section properties, and NDS Supplement
# reference design values looked up automatically
beam = LumberSection("6x12", "Douglas Fir-Larch", "No. 1")
print(beam.b, beam.d)        # 5.5 inch, 11.25 inch (dressed)
print(beam.A, beam.Sx)       # 61.875 in², 116.0 in³
print(beam.Fb, beam.E)       # 1350 psi, 1.6e6 psi

# Glulam — combination symbol lookup (NDS Supplement Table 5A)
gl = GlulamSection("6.75x30", "24F-V4", "Douglas Fir")
print(gl.Fb_pos, gl.Fb_neg)  # 2400 psi positive face, 1850 psi negative
```

### Member design checks

`WoodMemberCheck` applies the full NDS adjustment factor chain
(C<sub>D</sub>, C<sub>M</sub>, C<sub>t</sub>, C<sub>L</sub>, C<sub>F</sub>, C<sub>i</sub>,
C<sub>r</sub>, C<sub>P</sub>, C<sub>b</sub>, C<sub>V</sub>) and reports demand/capacity per check:

```python
from civilpy.structural.wood import LumberSection, WoodMemberCheck
from civilpy.general import units

# Beam: bending, shear, deflection, bearing
beam = LumberSection("6x12", "Douglas Fir-Larch", "No. 1")
check = WoodMemberCheck(beam, method="ASD", wet_service=False, load_duration="normal")

bend = check.check_bending(9600 * units("lbf*ft"))
print(bend["ratio"], bend["status"])      # 0.736 OK

shear = check.check_shear(2400 * units("lbf"))
defl = check.check_deflection(200 * units("lbf/ft"), 16 * units("ft"), limit="L/360")
check.summary()                            # DataFrame of all checks run

# Column: stability factor Cp computed per NDS 3.7.1
col = LumberSection("6x6", "Douglas Fir-Larch", "No. 1")
comp = WoodMemberCheck(col).check_compression(15000 * units("lbf"), le_strong=10 * units("ft"))
print(comp["Cp"], comp["ratio"])           # 0.692, 0.717

# Combined bending + compression interaction per NDS Eq. 3.9-3
inter = WoodMemberCheck(LumberSection("6x8", "Douglas Fir-Larch", "No. 1")) \
    .check_combined_bending_compression(
        P=5000 * units("lbf"), M=8000 * units("lbf*ft"),
        le_strong=8 * units("ft"), lu=8 * units("ft"))
```

Also included: `TimberBridgeDeck` and `TimberStringer` for AASHTO LRFD timber bridge checks
and MBE load rating, and `BoltConnection` for NDS Chapter 12 bolted connections via the
European Yield Model.

---

## Beam Analysis

Shear, moment, and deflection diagrams for statically determinate beams, following AISC
Table 3-23 sign conventions. Supports may be placed anywhere in the span (overhanging beams).

```python
from civilpy.structural.beam_bending import Beam, PointLoadV, DistributedLoadV

# 30 ft simple span: 15 kip point load at 10 ft + 2 klf uniform
beam = Beam(span=30)
beam.pinned_support = 0
beam.rolling_support = 30
beam.add_loads([
    PointLoadV(15, 10),          # 15 kips down at x=10 ft
    DistributedLoadV(2, (0, 30)),  # 2 kips/ft over full span
])

axial, R1, R2 = beam.get_reaction_forces()
print(R1, R2)                    # 40.0, 35.0 kips

beam.plot_all()                  # beam diagram + V + M (+ deflection) figure

# Other support conditions
from civilpy.structural.beam_bending import (
    CantileverBeam, ProppedCantileverBeam, FixedFixedBeam, ContinuousBeam
)
```

---

## Concrete Anchor Design (ACI 318-19)

Chapter 17 anchor checks for cast-in anchors: steel strength, concrete breakout, pullout,
side-face blowout, shear, and interaction — with a calc-sheet style summary.

```python
from civilpy.structural.concrete import AnchorBolts

# 2x2 group of 3/4" F1554 Gr 36 headed anchors, 12" embedment,
# 4000 psi concrete, 6" edge distances
group = AnchorBolts(
    f_c=4000, h_a=24,
    d_a=0.75, h_ef=12,
    f_ya=36000, f_uta=58000,   # ASTM F1554 Gr 36
    n_x=2, n_y=2, s_x=6, s_y=6,
    c_a1=6, c_a2=6,
    A_brg=0.654,               # heavy hex head bearing area
    N_ua=5000, V_ua=3000,      # factored demands (lbs)
)

results = group.check_all()    # dict of every limit state
print(group.summary())         # formatted table: φSn, demand, DCR, OK/NG
```

`ShearLugCheck` covers shear lug design per ACI 318-19 17.11.

---

## Midas Civil API Integration

Connect directly to a running Midas Civil instance via the Open API (Midas Civil 2022+, REST
API enabled). Store your key in `~/secrets.json` as `{"MIDAS_API_KEY": "your-key-here"}`.

```python
from civilpy.structural.midas import (
    midas_api, get_api_key,
    get_elements, get_nodes, get_materials,
    get_sections, get_static_loads, get_units,
    get_supports, setup_output_directory,
)

get_api_key()   # Loads key from ~/secrets.json

# Read model geometry
elements  = get_elements()
nodes     = get_nodes()
materials = get_materials()
sections  = get_sections()
supports  = get_supports()
loads     = get_static_loads()
units_    = get_units()

# Direct API calls for anything not covered by the helpers
# method: 'GET', 'PUT', 'POST', or 'DELETE'
# command: Midas API endpoint path
response = midas_api("GET", "db/elem")
midas_api("PUT", "db/stld", body={"Assign": {"1": {"NAME": "Dead Load (DC)"}}})

# Set up a local output directory for exported results
output_path = setup_output_directory()
```

---

## AASHTO Reference

### Bearing suitability (AASHTO LRFD Table 14.6.2)

```python
from civilpy.structural.aashto.bearings import BearingSuitability, MethodABearing

# Print the full reference table
# S = Suitable, U = Unsuitable, R = Requires special consideration
print(BearingSuitability().table)

# Method A elastomeric bearing design checks
bearing = MethodABearing(
    length=12,                    # in
    width=18,                     # in
    total_elastomer_thickness=3.0, # in
    n_layers=3,
    layer_thickness=1.0,
)
bearing.run_checks()              # Prints pass/fail for each AASHTO article
print(bearing.get_shape_factors())
print(bearing.get_deflections())
```

### Load combinations and HL-93

```python
from civilpy.structural.aashto.load_definitions import load_combinations
from civilpy.structural.aashto.vehicles import HL93Load

# AASHTO LRFD limit state load factors
print(load_combinations["Strength I"])
print(load_combinations["Service II"])
gamma_ll = load_combinations["Strength I"]["LL"]["gamma"]  # 1.75

# HL-93 design truck: 8-kip front, two 32-kip rear axles
# Rear axle spacing governs between 14 ft and 30 ft
truck = HL93Load()
print(truck.axels)
```

---

## AREMA Railroad Bridge Design

```python
from civilpy.structural.arema.rail_tpg_design import (
    GlobalDefinitions, LoadDefinitions, ThroughPlateGirderFloorbeam
)

# Global material constants — defaults per AREMA Chapter 15
# Override any argument for project-specific conditions
g = GlobalDefinitions(
    f_y=50000,          # psi
    tie_spacing=1.5,    # ft
    future_ballast=12,  # in
)

# E80 Cooper loading definitions — override for alternate load rating
loads = LoadDefinitions(
    axel_load=100,      # kips
    wind_load=300,      # lbf/ft
)

# Floor beam design
fb = ThroughPlateGirderFloorbeam(globals=g, loads=loads)
```

---

## SNBI Bridge Inspection Data

Pydantic models for the FHWA Special Notice for Bridges and Inspection (SNBI) data standard.
Useful for validating inspection data before submission to national databases or for building
tools that read/write SNBI-formatted records.

```python
from civilpy.state.ohio.snbi import (
    Element, Route, Feature, Inspection,
    SpanSet, SubstructureSet, Bridge
)

# Validate an SNBI element record — Pydantic raises ValidationError on bad data
element = Element(
    BE01="0100",    # Element number (max 4 chars)
    BE02="0000",    # Parent element number
    BE03=1250,      # Total quantity
    BCS01=1000,     # Quantity in condition state 1
    BCS02=200,      # Condition state 2
    BCS03=50,       # Condition state 3
)

# Validate a span set configuration
span = SpanSet(
    BSP01="M",       # Main span designation
    BSP02=3,         # Number of spans
    BSP04="3",       # Span material (Steel)
    BSP06="02",      # Span type (Stringer/multi-beam)
    BSP09="1A",      # Deck material and type
)

# Validate inspection metadata
inspection = Inspection(
    BIE01="R",              # Routine inspection
    BIE02="20240801",       # Begin date YYYYMMDD
    BIE03="20240801",       # Completion date
    BIE05=24,               # Inspection interval (months)
)
```

---

## ODOT TIMS Bridge Data

Fetch live bridge records from the ODOT TIMS ArcGIS REST service. No credentials required.

```python
from civilpy.state.ohio.DOT.TIMS import TIMSBridge, get_tims_data

# Single bridge by SFN
bridge = TIMSBridge("2102374")
print(bridge)
# <TIMSBridge SFN: '2102374'>
#   Route Carried: SR 16
#   Location:      Coshocton County, District 5
#   Year Built:    1968
#   Material/Type: Steel / Stringer/Multi-beam (3/02)
#   Deck: 6  Superstructure: 6  Substructure: 7

# Any TIMS field is an attribute
print(bridge.deck_area)
print(bridge.suff_rating)
print(bridge.lanes_on)

# Bulk download — full statewide inventory as a DataFrame
df = get_tims_data("Bridge")
district_5 = df[df["district"] == 5]
poor_condition = df[df["deck_summary"] <= 4]
```

---

## Package Structure

```mermaid
graph TD
    A[Does the function relate to a specific state<br>requirement/system, or a branch of civil engineering?]
    A --> |State| B("Does it apply statewide<br>or to a specific department?")
    A --> |Branch| C("Which engineering branch?")
    C --> |structural| E(civilpy.structural)
    C --> |geotechnical| F(civilpy.geotech)
    C --> |transportation| H(civilpy.transportation)
    C --> |water_resources| I(civilpy.water_resources)
    A --> |Neither| P(civilpy.general)
    E --> K("Standard-specific?")
    K --> |AASHTO| N(civilpy.structural.aashto)
    K --> |AREMA| NA(civilpy.structural.arema)
    K --> |No| O(civilpy.structural)
    B --> |Statewide| L(civilpy.[state])
    B --> |Department| M(civilpy.[state].DOT)
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — includes setup instructions, the four-role QA/QC
review process, and the AI use policy.

Security issues: [SECURITY.md](SECURITY.md)

Bugs and feature requests: [issue tracker](https://daneparks.com/Dane/civilpy/issues)
