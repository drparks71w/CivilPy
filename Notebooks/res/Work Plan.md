# CivilPy: Bridge Engineering Hub (2026 Roadmap)

This roadmap outlines the development of `civilpy` as a central hub for bridge engineering, focusing on native object contracts, multi-representation modeling (A3), and automated analysis reconciliation.

## The Strategy: Hub-and-Spoke Orchestration
`civilpy` acts as the **Canonical Hub** between various engineering "spokes" (Rhino, MIDAS, AssetWise). We leverage standardized data models (IFC 4.3 aligned) to ensure interoperability.

- **Rhino Spoke:** Read/write active `.3dm` documents via `rhino3dm` and custom RhinoCommon plugins.
- **MIDAS Spoke:** Direct integration with MIDAS MAPI for automated FEA modeling and results extraction.
- **AssetWise Spoke:** Integration with AssetWise REST APIs for inventory and condition data.
- **Hub:** `StructuralModel` remains the canonical translator and source of truth.

---

## Phase 1: Native Object Contracts (Foundation)
Establishing the spatial source of truth for all bridge components.

**1.1 `Alignment` Engine**
- **Status:** DONE.
- **Scope:** Parametric PI/curve logic, station/offset conversions.
- **Contract:** `point_at(station, offset)` → Global 3D Point.

**1.2 `Terrain` & Site Ingestion**
- **Status:** DONE.
- **Scope:** LiDAR ingestion from OGRIP, TIN mesh backbone.
- **Workflow:** Fetch terrain data for defined corridors and project geometry onto it.

---

## Phase 2: Multi-Representation Modeling (A3)
Wiring the representations together for seamless design-to-analysis workflows.

**2.1 Placement Contract**
- **Status:** DONE.
- **Source of Truth:** `src/civilpy/structural/placement.py`.
- **Workflow:**
  1. Define `BridgeComponent` (geometry + structural model).
  2. Place components on `Alignment` via `Placement` objects.
  3. Emit Rhino BREPs for detailing.
  4. Emit MIDAS MAPI payloads for analysis.

**2.2 Analysis Reconciliation (Track B)**
- **Goal:** Automate the comparison between simplified L1 (civilpy) and refined L2 (MIDAS) analysis.
- **Tool:** `reconcile_analysis(civilpy_results, midas_results)`.
- **Success Metric:** Verified matching results within engineering tolerances (e.g., 5%) before final design.

---

## Phase 3: Vertically Sliced Component Roadmaps
Applying the hub-and-spoke loop to specific bridge types.

1. **Single-span slab:** **Target #1.** End-to-end equivalent-strip analysis and detailing.
2. **Continuous slab:** Multi-span logic and negative moment distribution.
3. **Precast box beams:** Adjacent-box distribution factors and transverse post-tensioning.
4. **Precast I-girders:** Composite deck action and prestress losses.
5. **Steel Plate Girders:** Field splices, flange transitions, and plate optimization.

---

## Phase 4: AssetWise & Lifecycle Integration
Closing the loop between design, management, and inspection.

- **Inventory Integration:** Search and pull AssetWise data via SFN or bridge number.
- **Condition-Aware Modeling:** Use inspection data (e.g., section loss, spalling) to automatically adjust analysis models.

---

## Progress Tracking

- [x] **Core Alignment Engine:** DONE.
- [x] **Terrain Backbone:** DONE.
- [x] **Placement Contract:** DONE.
- [x] **Midas MAPI Client:** DONE.
- [ ] **Rhino Bridge Enhancements:** *In Progress.* improving `rhino_stm` and C# plugin features.
- [ ] **Automated Reconciliation Suite:** *Planned.* Building the Track B comparison engine.

---

## Next Steps
1. **Refine `StructuralModel` Hub:** Complete the migration of all component types to the canonical hub.
2. **Rhino-to-Midas Live Link:** Enable real-time updates of MIDAS models based on Rhino geometry changes.
