# ODOT Structural SCDs — Grasshopper Component Feasibility Review

Reviewed 2026-07-05 from the ODOT Office of Structural Engineering SCD
index (https://www.dot.state.oh.us/SCDs/Pages/structural.aspx). All 41
current drawings are archived in `res/odot_scds/` (git-ignored; ~190 MB —
re-run the index download if missing). Ratings were assigned after
profiling every PDF (page count, text density, table content) and
rendering the ambiguous ones.

**Rating scale:** 1 = very feasible as a parametric Grasshopper component
(dimensioned, table-driven geometry) … 10 = not feasible (guidance text,
pay items, site-specific work with no parametric geometry).

**Conventions for implementation:** each component ships as a GHPython
source named exactly after its SCD (e.g. `Notebooks/res/AS-1-15.py`),
backed by a pure-Python catalog/layout module in `civilpy.structural.odot`
(the `deck_design` / `bridge_layout` pattern: engineering data + geometry
math testable outside Rhino, thin Rhino emission in the script, `gdr.*`
tagging where the MIDAS pipeline consumes the result). Several SCDs have
companion **Design Data (DD) sheets** published separately (PSBDD-1-25 is
already encoded as `odot.box_beam_design`; HWDD-1, PCBDD, SICDD-2-14,
NBSDD-1-09, TVPFDD-1-18, DBP-1-92 are in `~/Downloads`) — where a DD sheet
exists, the catalog module should encode it alongside the drawing.

## Wave 1 — approach slabs & simple details

| SCD | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| AS-1-15 | Reinforced Concrete Approach Slab | 2023-01 | **1** | ✅ DONE — `odot.approach_slab` + `Notebooks/res/AS-1-15.py`, 21 tests. Replaces the lost AS-1-15.3dm. |
| DS-1-92 | Drip Strip (over-the-side drainage) | 2022-07 | **1** | ✅ DONE — `odot.drip_strip` + `Notebooks/res/DS-1-92.py`, 10 tests. Plugs the "drainage" gap in the bridge generator. |
| PCB-91 | Portable Concrete Barrier | 2020-07 | **1** | ✅ DONE — `odot.portable_barrier` + `Notebooks/res/PCB-91.py`, 9 tests; TL data stays in `bridge_railing`. |
| AS-2-15 | Approach Slab Installation | 2023-07 | **4** | 14 sheets, mostly installation configurations and pressure-relief joints; implement the drawable subset (joint sections), catalog the rest. |

## Wave 2 — headwalls

| SCD | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| HW-2.1 | Half-Height Headwalls, CMP/plastic | 2022-07 | **1** | Dimension tables already encoded (`odot.headwall`); geometry is a straightforward parametric solid per pipe size. |
| HW-2.2 | Half-Height Headwalls, concrete pipe | 2018-07 | **1** | Same pattern as HW-2.1. |
| HW-1.1 | Full Height Headwalls | 2025-07 | **2** | Bigger dimension table (198 numeric entries), wingwall geometry adds work. |

## Wave 3 — bridge railings (replaces the generator's placeholder boxes)

| SCD | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| SBR-1-20 | Single Slope Railing 42" | 2024-07 | **1** | Profile sweep + bars; section data already in `bridge_railing`. |
| SBR-3-20 | Single Slope Railing 36" | 2024-07 | **1** | Same family. |
| BR-1-13 | New Jersey Shape Railing | 2014-01 | **1** | Profile + reinforcing tables (521 numeric entries). |
| SBR-2-20 | 57" Single Slope Median | 2024-07 | **2** | Median variants (Type B1 / back-to-back). |
| BR-2-15 | Sidewalk Railing w/ Concrete Barrier | 2024-07 | **2** | Barrier + steel tube on sidewalk; two materials. |
| TST-1-99 | Twin Steel Tube Railing | 2021-01 | **2** | Posts/tubes/anchorages fully dimensioned. |
| TST-2-21 | Three Steel Tube Railing | 2025-01 | **3** | 15 sheets, many mounting configurations. |
| DBR-2-73 | Deep Beam Bridge Guardrail | 2002-07 | **3** | Post + W-beam on deck edge; links to `odot.guardrail`. |
| DBR-3-11 | Deep Beam Retrofit Railing | 2011-07 | **3** | Retrofit mounting variants. |
| TBR-1-11 | Thrie Beam Retrofit Railing | 2013-01 | **3** | Same pattern. |

## Wave 4 — slab bridges & substructure

| SCD | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| SB-1-24 | Single Span Slab Bridges | 2026-01 | **1** | Verified by render: complete SLAB DATA table (spans 11–38 ft → thickness + A/B/M/N bar schedules), skew math on the sheet. The single highest-value component after the girder bridge. |
| CS-1-24 | Continuous Slab Bridge | 2026-01 | **2** | Same family + continuity/haunches; largest embedded tables of the set (779 numeric entries). |
| CPA-1-08 | Capped Pile Abutment (slab bridges) | 2024-01 | **2** | Cap + pile rows + wingwalls; SB-1-24's companion (referenced from its elevation). |
| CPP-1-08 | Capped Pile Pier (continuous slabs) | 2017-07 | **2** | One sheet, clean parametric cap/pile layout. |
| A-1-20 | Typical Abutment Details (expansion joints) | 2024-01 | **3** | Parametric by beam depth/seat/skew; more project-specific inputs than CPA. |

## Wave 5 — bearings & expansion joints

| SCD | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| RB-1-55 | Rockers and Bolsters | 2024-07 | **2** | Dimension catalog already encoded (`odot.rocker_bolster`); solids from the table. |
| FB-1-82 | Fixed Bearings, steel bridges | 2024-07 | **3** | Small shoe assemblies; limited table. |
| BD-1-11 | Bearing Details, box beams | 2018-07 | **3** | Elastomeric pad + dowels per beam depth (`odot.box_beam` has the pads). |
| EXJ-4-87 | Strip Seal EXJ, steel stringers | 2024-01 | **4** | Joint cross-section placed along a skewed joint line; gland/extrusion shapes are manufacturer-generic. |
| EXJ-5-93 | Strip Seal EXJ, box beams | 2024-01 | **4** | Same pattern. |
| EXJ-6-17 | Strip Seal EXJ, I-beams | 2024-01 | **4** | Same pattern. |
| EXJ-2-81 | Compression Seal EXJ, steel | 2022-07 | **4** | Aging detail, still standard. |
| EXJ-3-82 | Compression Seal EXJ, box beams | 2013-01 | **4** | Same pattern. |

## Wave 6 — prestressed & integral construction

| SCD | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| PSBD-1-25 | PS Box Beam Details | 2026-01 | **2** | Sections/strands/ties already encoded (`odot.box_beam`, `box_beam_design`); component is mostly geometry emission. |
| PSID-1-13 | PS I-Beam Details | 2025-07 | **3** | I-beam sections + strand patterns; encode like the box beams first. |
| ICD-1-20 | Integral details, steel on flexible abutments | 2024-01 | **4** | End-condition add-on to the girder generator, not standalone. |
| ICD-2-18 | Integral details, PS I-beams | 2024-01 | **4** | Same. |
| SICD-1-21 | Semi-integral details, steel on rigid abutments | 2024-01 | **4** | Same. |
| SICD-2-14 | Semi-Integral Abutment Diaphragm Guide | 2021-01 | **5** | "Guide" sheet — half guidance; DD sheet exists (SICDD-2-14). |

## Wave 7 — fencing & guidance-heavy sheets

| SCD | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| VPF-1-24 | Vandal Protection Fencing | 2025-01 | **5** | Posts/fabric/curved tops parametric in principle; many mounting cases. |
| TVPF-1-18 | Temporary Vandal Protection Fencing | 2025-01 | **6** | Temporary variant; DD sheet exists. |
| GSD-1-19 | General Steel Details | 2024-07 | **7** | A library of unrelated details (stiffeners, cross-frames, welds) — encode as a reference catalog, not one component. |
| NBS-1-09 | Noise Barrier Specifications | 2025-01 | **8** | Verified by profile: 13.6k words of specification text; only generic post/panel geometry. Catalog data only. |
| WU-1-26 | Wildlife Underpass | 2026-01 | **8** | Verified by render: site grading/aggregate path guidance + pay items under an existing bridge; no parametric structure. Notes module at most. |

## Not applicable

- **2026-01-16 Full Set** — concatenation of the above; not downloaded.

---

# Roadway, Hydraulic & Plan-Insert SCDs — structural-library subset

Reviewed 2026-07-05 from the roadway index
(https://www.dot.state.oh.us/SCDs/Pages/roadway.aspx), the hydraulic index
(https://www.dot.state.oh.us/SCDs/Pages/hydraulic.aspx), and the
structures Plan Insert Sheets page.  Only drawings with structural
content were archived (`res/odot_scds/roadway|hydraulic|plan_inserts/`);
purely roadway/landscape/erosion sheets (BP-4/7/9, LA, RM-1/3/6/7, DM-1.x,
DM-3/4, WQ, F-1/2, MGS-5.x layout sheets) were reviewed on the index and
excluded.

## Wave 8 — roadway concrete barriers & curbs (same profile engine as Wave 3)

| SCD | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| RM-4.3 | Single Slope Barrier, Types B, C, B1, C1 | 2025-07 | **1** | Roadway counterparts of the SBR bridge railings; identical profile-sweep engine. |
| RM-4.5 | Single Slope Barrier, Type D | 2026-01 | **1** | Same family. |
| RM-4.8 | Single Slope Barrier, Type N | 2026-01 | **1** | Same family (largest table of the group). |
| RM-4.9 | Single Slope Barrier, Type E | 2025-07 | **1** | Same family. |
| RM-4.2 | 32" Portable Concrete Barrier | 2026-01 | **2** | Segment + connection hardware; successor family to PCB-91. |
| RM-4.1 | 50" Portable Concrete Barrier | 2020-01 | **2** | Same pattern, taller. |
| BP-5.1 | Concrete Curbs and Curb & Gutter | 2026-01 | **1** | Simple profile sweeps (all curb types); interfaces with approach slabs. |
| RM-2.1 | Concrete Steps | 2013-07 | **2** | Small parametric stair. |
| RM-5.2 | Bikeway Railing | 2023-07 | **2** | Post-and-rail on structures; pairs with BR-2-15. |
| RM-4.6 | Concrete Barrier End Sections | 2025-07 | **2** | Lofted end tapers of the RM-4.x profiles. |
| RM-4.4 | Single Slope Barrier Transitions | 2025-01 | **3** | Lofts between barrier profiles. |
| RM-4.7 | Thrie-Beam Transition for PCB | 2025-01 | **3** | Steel transition hardware on the barrier engine. |

## Wave 9 — guardrail systems (extends `odot.guardrail`)

| SCD | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| MGS-3.1 | Bridge Terminal Assembly, Type 1 | 2026-01 | **2** | Already cataloged in `odot.guardrail`; connects guardrail runs to the Wave 3 railings. |
| MGS-3.2 | Bridge Terminal Assembly, Type 2 | 2025-07 | **2** | Same. |
| MGS-3.3 | Bridge Terminal Assembly, Type TST-2 | 2026-01 | **2** | Mates with TST-2-21. |
| MGS-2.1 | Midwest Guardrail System, standard run | 2026-01 | **2** | Posts/blockouts/W-beam as a linear assembly along an alignment. |
| MGS-2.2 | MGS with Rub Rail | 2026-01 | **3** | Run variant. |
| MGS-2.3 | Long Span Guardrail | 2025-07 | **3** | Run variant (unposted span over culverts — pairs with BCHW/HW). |
| MGS-2.4 | Socketed Weak Post on Headwall | 2026-01 | **3** | Directly ties guardrail to the HW-series headwalls. |
| MGS-4.1 | Type A Anchor Assembly | 2025-07 | **3** | End anchorage hardware. |
| MGS-4.2 | Type T Anchor Assembly | 2025-07 | **3** | 7 sheets of anchor hardware. |
| MGS-4.3 | Guardrail Transitions | 2025-07 | **3** | Height/stiffness transitions. |
| MGS-6.1 | Guardrail at Bridges | 2018-01 | **3** | Arrangement of runs + terminals at structures. |
| MGS-4.5 | Buried-in-Backslope Terminal | 2025-07 | **4** | Earthwork-dependent geometry. |
| MGS-6.2 | MGS at Piers | 2025-07 | **4** | Pier-protection arrangement. |
| MGS-6.3 | Thrie Beam Bullnose | 2025-07 | **4** | Median-nose layout, 8 sheets. |
| F-3.1 | Fence Details at Bridges | 2013-07 | **5** | Bridge fence mounting; pairs with VPF-1-24. |

## Wave 10 — drainage structures (hydraulic SCDs with structural content)

| SCD | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| I-3B / I-3C / I-3D / I-3N | Inlet No. 3 for Single Slope Barrier B/B1, C/C1, D, N | 2024–26 | **2** | Inlets formed INTO the RM-4.x barrier profiles — build on the Wave 8 engine. |
| I-4B | Inlet No. 4 for Single Slope Barrier B/B1 | 2025-01 | **2** | Same. |
| CB-3 / CB-3A | Catch Basin No. 3 / 3A | 2026-01 | **2** | Reinforced concrete boxes, depth-tabled walls, grate castings. |
| CB-2 series | Catch Basins 2-2A…2-6 | 2024-07 | **2** | Family of RC boxes; one parametric module, per-number data. |
| CB-4/4A/5/5A/6/8/8A/9 | Catch Basins | 2024–26 | **3** | Smaller variants; grate/casting geometry dominates. |
| MH-2 / MH-4 | Manholes No. 2 / 4 | 2021–24 | **3** | Tabled riser/base dimensions. |
| MH-1 / MH-3 / MH-5 | Manholes No. 1 / 3 / 5 | 2022–24 | **3** | Same family. |
| I-2 / I-2A | Median / Pavement Inlet No. 2 | 2024-07 | **3** | Frame-and-grate inlets. |
| CB-1 / CB-7 | Side Ditch Inlets / CB No. 7 | 2024-07 | **3** | Sloped-apron inlets. |
| DM-2.1 | Paved Gutters | 2013-01 | **2** | Trivial profile sweeps. |

Excluded from the archive (reviewed on the index): DM-1.1/1.2/1.3
(outlets/underdrains/slotted drains — product-driven), DM-3.1, DM-4.x
(erosion control), WQ-1.x (site basins).

## Plan Insert Sheets (Office of Structural Engineering)

| Sheet | Title | Rev | Rating | Notes |
|---|---|---|---|---|
| BCHW | Precast Concrete Box Culverts | 2022-01 | **3** | THE culvert entry point: pairs the ASTM C1577 standard precast sections (span x rise catalog to encode) with ODOT headwall/wingwall details and notes. High structural value; goes with Wave 2 headwalls. |
| AJBCBBB | Abutment Joints in Bit. Concrete Box Beam Bridges | 2022-01 | **8** | Notes-dominated single sheet; catalog note on the box-beam modules at most. |
| BC | Bridge Cleaning | 2022-01 | **10** | Pure notes; not archived. |
| CRHS | Collision Repair & Heat Straightening Notes | 2022-01 | **10** | Pure notes; not archived. |
