# Bridge Analysis Work Plan (reprioritized)

Priority order set by the design goal, not by SCD backlog: **native objects and the
Rhino↔MIDAS analysis contract come first**, then bridge types are carried one at a time
from faithful Rhino geometry all the way through analysis and substructure design, easiest
type first.

## What already exists (don't rebuild)

The hub-and-spoke contract is largely built — it was just wired to the STM/truss front-end,
not to the bridge/SCD objects:

- **`StructuralModel`** (`structural_model.py`) — solver-agnostic analysis hub (Node/Element/
  Restraint/Load/Result), documented as mapping to `IfcStructuralAnalysisModel`.
- **Rhino → hub:** `rhino_stm.read_structural_model` reads a tagged `.3dm` into `StructuralModel`.
- **hub → MIDAS:** `midas_models.midas_payloads()` / `push_midas()` serialize the hub to MAPI
  `PUT /db/*` bodies. `MidasCivil` (`midas.py`) is a working MAPI client: nodes, elements,
  materials, sections, supports, static loads, load combos, `analyze()`, `result_table()`,
  `beam_forces()`.
- **L1 line-girder analysis:** `girder_pipeline.py` — `girder_line_envelope` (DC1/DC2/DW),
  `hl93_pos_neg` (HL-93 + IM + lane load via influence lines), splice placement.
- **Live-load distribution (all types):** `aashto/lrfd/distribution.py` already implements
  `slab_equivalent_strip` (4.6.2.3), beam `moment_df`/`shear_df` interior+exterior with skew
  corrections (4.6.2.2), box/multicell/spread-box factors, `multiple_presence_factor`,
  `lever_rule_exterior`, `effective_flange_width`, `dynamic_load_allowance`. L1 is mostly
  assembly, not new derivation.
- **Alignment primitives:** `transportation/curves.py` — `HorizontalCurve`, `VerticalCurve`
  (both station-based, `elevation_at`, `grade_at`, PC/PT/BVC/EVC).
- **Substructure/foundations:** `structural/abutment.py`, `structural/pier.py`, geotech
  `deep_foundation.py`, `lateral_pile.py`, `lpile.py`, `shallow_foundation.py`.

**Genuinely missing:** a composed `Alignment` (station+offset→3D), a `Terrain` object, and the
wiring that makes each bridge object emit *both* Rhino geometry *and* a `StructuralModel` spoke.

---

## Track A — Native object contract (foundation, blocks everything)

Nothing downstream is right until placement is defined by station/offset/elevation instead of
raw floats.

**A1. `Alignment`** — compose the existing curve primitives into a single object:
- Chain horizontal elements (tangent → `HorizontalCurve` → tangent, spirals later) with a
  vertical profile of `VerticalCurve`s; carry cross-slope/superelevation.
- Core contract methods: `point_at(station, offset)` → 3D point (incl. profile elevation +
  superelevation), `frame_at(station)` (tangent/normal for sweeping templates), and the inverse
  `station_offset_of(point)`.
- **Generators (decided): parametric PI/curve constructor first** (no external data — fastest
  to test the single-span-slab slice), **then ORD/LandXML import**, Rhino-curve tracing last.
- Rhino spoke: alignment centerline on an `Alignment` layer, typed so MIDAS/tools can consume it.

**A2. `Terrain`** — net-new, **source-agnostic** surface (decided: support both early-design
LiDAR and Stage-3 survey):
- One `Terrain` interface (TIN/mesh) with `elevation_at(x, y)` and, via A1,
  `elevation_at(station, offset)` — independent of how the surface was produced.
- **Generator 1 (demo):** Ohio **OGRIP LiDAR** — take GPS coordinates for the project extents,
  clip the point cloud/DEM to that corridor, build the TIN. No civilpy OGRIP *download* module
  exists yet (the OGRIP web portal is external, still net-new), but the **`.las`/`.laz` → mesh
  backbone now exists**: `Notebooks/Point_Clouds.ipynb` (copied from civilpy_private) does laspy
  read, bbox extraction, and BPA/Poisson/Delaunay meshing via open3d. Productionize that into the
  `Terrain` generator; add the GPS-extent → OGRIP-tile fetch/clip in front of it.
- **Generator 2 (production):** import a **survey-shot TIN** (LandXML/DTM from a licensed
  surveyor), which Stage-3 design plans ultimately rely on.
- Consumers: abutment/wingwall heights & foreslopes, approach grades, footing cutoff elevations.
- Rhino spoke: mesh on a `Terrain` layer.

**A3. Placement + multi-representation contract** — extend the existing hub rather than invent:
- Define the base a bridge component adopts: constructed from `(alignment, station, offset,
  terrain)`, exposing `.geometry()` → Rhino BREP/curves **and** `.structural_model()` →
  `StructuralModel` (which already reaches MIDAS via `midas_payloads`/`push_midas`).
- This is the "contract established" milestone the whole roadmap depends on.

**CDE export targets** (all spokes off the one `StructuralModel`/component hub):
- **Rhino** — geometry (BIM/quantity/clash).
- **MIDAS** — analysis/FEA. **This is priority #1**; the Rhino→MIDAS pipeline drives the whole
  near-term roadmap.
- **AASHTOWare BrR** — load rating. **Longer-term, not a short-term goal.** Add a BrR/AASHTOWare
  export spoke (alongside `midas_payloads`) once Rhino→MIDAS is working end-to-end; `aashtoware/
  brr.py` is the starting point. Do not let it pull focus from the MIDAS pipeline.

## Track B — Analysis contract & the three levels (primary use case)

Every faithfully-represented object must produce a faithful MIDAS analysis model. Wire the three
levels onto the A3 contract:

- **L1 — Fundamental (decided: mirror in both civilpy AND MIDAS as a validation gate).** Dead +
  live with AASHTO distribution → shear/moment/deflection diagrams. Assemble from the existing
  `distribution.py` factors + `girder_pipeline` + `influence_lines`; the slab equivalent-strip
  method (`slab_equivalent_strip`, 4.6.2.3) already exists for slab bridges, and beam bridges use
  the 4.6.2.2 g-factors — the distribution mechanism differs by type, which is part of what makes
  each slice distinct. Compute L1 in pure-Python civilpy (fast, offline baseline) **and** in MIDAS
  via `StructuralModel`→MAPI, then reconcile the two as the per-slice validation gate.
- **L2 — "MDX level."** Refined line-girder / grillage in MIDAS via `StructuralModel` → MAPI;
  composite section properties, staged construction, refined distribution, detailing checks.
- **L3 — Full FEA.** Plate/shell (and solid where warranted) models in MIDAS.
- **Cross-cutting analysis features:** lane-line definition → live-load application; bearing
  reaction extraction (`result_table`/`beam_forces`); load combinations.

## Track C — Substructure load path (completes the design workflow)

Follow the load down in the traditional workflow, per vertical slice:
- Superstructure analysis → **bearing reactions** → feed `abutment.py` / `pier.py` and geotech
  foundation modules (`deep_foundation`, `lateral_pile`/`lpile`, `shallow_foundation`) to size
  and design the substructure and its foundations.

---

## Vertical slices (the roadmap)

Carry each type end-to-end — **faithful Rhino geometry → L1 → L2 → L3 → substructure** — and
prove the analysis works before starting the next. Easiest/most abundant first.

1. **Single-span slab** (`slab_bridge` / SB-1-24). Simplest: equivalent-strip design, no girder
   distribution. Pair with its abutments (`capped_pile_abutment` CPA-1-08 / `capped_pile_pier`
   CPP-1-08), approach slab (`approach_slab` AS-1-15), sleeper slab (AS-2-15). **First target.**
2. **Continuous slab** (`continuous_slab_bridge` / CS-1-24). Adds continuity and negative moment
   over piers; exercises multi-span L1 and pier reactions.
3. **Precast box beams** (`box_beam` / PSBD, EXJ-5-93 joint). Adjacent-box LLDF, transverse
   post-tensioning, shear key.
4. **Precast I-girders** (`ps_i_beam` / PSID-1-13). `girder_pipeline` L1 is already strongest
   here; composite deck action, prestress/strand modeling, diaphragms.
5. **Steel** (`steel.py`, composite/plate girders, `rocker_bolster` RB-1-55, `fixed_bearing`
   FB-1-82). Composite section, field splices (`girder_pipeline.place_splices` exists).
6. **Advanced** — trusses (the STM/truss hub path already exists — good validation case),
   post-tensioned concrete, arches.

## Background tracks (parallel, non-blocking)

- **Per-SCD faithful geometry** (old Phase 2 gripes — orientation swap, `# r: civilpy`,
  human-readable layers, user-text attrs, materials, preview, rebar). These now fold into each
  vertical slice as the "faithful Rhino representation" step, done per type, not as a global sweep.
- **Pure-Python AASHTO checks** (no Rhino/MIDAS dependency): `stm.py` (tie anchorage, strut
  bursting, 25° angle), `timber.py` (shear, axial+bending interaction, Hankinson, deflection).
- **Missing-SCD backlog** — build on demand as each vertical slice needs a component
  (e.g. `EAB-1-22` bearings when bearings are needed for reactions; `PSBD-1-25` for slice 3).

---

## Decisions (resolved)

1. **Alignment source** — parametric PI/curve constructor first, ORD/LandXML import next,
   Rhino-curve tracing last.
2. **L1 home** — computed in both civilpy and MIDAS and reconciled as a per-slice validation gate.
3. **Terrain source** — one source-agnostic `Terrain`; build OGRIP-LiDAR-from-GPS-extents for the
   demo, and survey-TIN (LandXML) import for production/Stage-3.

## Progress

- **A1 — parametric `Alignment`: DONE.** `src/civilpy/transportation/alignment.py` composes the
  `HorizontalCurve`/`VerticalCurve` primitives into an `Alignment` (`Tangent`/`Curve` elements +
  `VerticalProfile`) exposing the placement contract: `point_at(station, offset)`,
  `elevation_at`, `bearing_at`, `frame_at`, and the inverse `station_offset_of`. Convention:
  azimuth cw from North, positive offset to the right. 16 pure-Python tests + doctests pass
  (`tests/transportation/test_alignment.py`). Superelevation on offset elevations is the one
  deferred piece (offsets currently sit at centerline profile elevation).
- **A2 — `Terrain`: DONE.** Productionized `Point_Clouds.ipynb` into
  `src/civilpy/transportation/terrain.py`. Supports `elevation_at(x, y)` via TIN, `from_las`
  with `open3d` preprocessing (downsampling/outliers), and `to_open3d_mesh` with Poisson
  reconstruction. Added `civilpy.state.ohio.ogrip` for automated tile discovery and
  `Terrain.from_ogrip(bbox)` for GPS-based ingestion.
- **A3 — Placement + multi-representation contract: DONE.** Established the
  `BridgeComponent` / `Placement` / `Bridge` contract in
  `src/civilpy/structural/placement.py`. Implemented `SlabBridgeComponent` as the first
  faithful representation of the A3 contract: it emits Rhino layout primitives and a
  `StructuralModel` hub spoke for MIDAS. Created `VALIDATION_TESTING.md` for reviewers.
- **B1 — Slab Analysis Vertical Slice (L1): DONE.** Implemented `calculate_l1_envelope()`
  and `reconcile_analysis()` in `SlabBridgeComponent`. This enables pure-Python AASHTO
  distribution and analysis (DC1/DC2/DW/HL-93) and established the reconciliation
  bridge to MIDAS results. Verified with `tests/structural/test_slab_bridge_analysis_l1.py`.
- **Terrain backbone copied:** `Notebooks/Point_Clouds.ipynb` (see A2).
- **Slice 5 (steel) carried through OUT OF ORDER as the BrIM proof-of-concept — superstructure
  DONE.** `bridge_layout.py` (crowned deck, BDM 309-4 overhang, haunches, rebar mats),
  `rhino_bim.py` emit layer + `draw_bim_emit.py` driver, MIDAS via
  `structural_model_from_layout`/`grillage_model_from_layout`, quantities read-back
  (`read_bim_quantities`), and the substructure *design* notebook
  (`Substructure Design from Preliminary Reactions.ipynb`: reactions → STM pier/abutment
  caps → bent P-M → wall stability). Substructure *geometry/BrIM components* are NOT yet
  emitted — the model stops at the bearings.
- **Substructure BrIM components DONE (Phase 4, except the 4.8 terrain hook).**
  `substructure_layout.py` places caps/seats/columns/footings/piles/backwalls/wingwalls
  from the executed design objects; `rhino_bim.substructure_emit`/`add_substructure`/
  `stm_overlay_emit` merge the tagged geometry, the rebar cage, and the in-place STM
  overlay into the superstructure emit; rollup/read-back cover the 511/507/509
  substructure items; demonstrated in the substructure notebook §7.

## Next steps

Task breakdowns in `docs/BrIM_Work_Plan.md`:

1. **Slice 3 — prestressed box beams (BrIM Phase 5).** Adjacent-box layout + shear keys/tie
   rods, strands from the `box_beam_design.py` PSBD tables, adjacent-box LLDF into the L1
   envelope, MIDAS spoke, emit-layer port of `rhino_box_beam.py`, walkthrough notebook;
   substructure path reused from the steel slice.
2. **Track B (background).** Drive the single-span-slab slice through the MIDAS pipeline
   (L1/L2/L3) and reconcile results with the civilpy baseline.
3. **Phase 4 leftovers.** The 4.8 terrain hook (footing/pile cutoff elevations from
   `Terrain.elevation_at`) and superstructure 3.1 authentic render materials.
