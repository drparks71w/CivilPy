# CivilPy

![PyPI - License](https://img.shields.io/pypi/l/civilpy)
<img alt="Pipeline" src="https://daneparks.com/Dane/civilpy/badges/master/pipeline.svg">
<img alt="Coverage" src="https://daneparks.com/Dane/civilpy/badges/master/coverage.svg">
<img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/civilpy">
[![PyPI Downloads](https://static.pepy.tech/badge/civilpy/month)](https://pepy.tech/projects/civilpy)

Python tools for civil and structural engineering — every AISC steel shape as a Python object
with Pint units, built-up section properties, AASHTO/AREMA design references, Midas Civil API
integration, and ODOT/SNBI bridge asset management tools.

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
