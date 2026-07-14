# CivilPy MCP Bridge: Shadow MCP Orchestrator

This project implements a **Shadow MCP Orchestrator** using the Model Context Protocol (MCP) to turn the "hub-and-spoke" contract of `civilpy` into a real-time, agent-driven design loop.

**Note:** This is a separate project that uses `civilpy` as a dependency.

## The Strategy: Shadow MCP
Since MIDAS and AssetWise lack native MCP servers, this bridge acts as the **Orchestration Layer**. We treat existing APIs (MAPI, REST) as "tools" and expose them via a unified MCP interface.

- **Rhino Spoke:** Use official `RhinoMCP` (McNeel) to read/write the active `.3dm` document.
- **MIDAS Spoke:** Wraps `civilpy.structural.midas` MAPI as a set of MCP tools (e.g., `run_analysis`, `get_beam_forces`).
- **AssetWise Spoke:** Wraps AssetWise REST as a data resource (e.g., `fetch_bridge_inventory`).
- **Hub:** `civilpy.structural.structural_model.StructuralModel` remains the canonical translator between these agents.

---

## Phase 1: Native Object Agent (Foundation)
AI agents cannot design without a spatial source of truth.

**1.1 `Alignment` Agent Tools**
- **Dependency:** `civilpy.transportation.alignment`.
- **Goal:** Enable an agent to "trace" a curve in Rhino via `RhinoMCP` and immediately instantiate a `civilpy.Alignment` object.
- **Contract:** `point_at(station, offset)` → Global 3D Point.

**1.2 `Terrain` Resource Tools**
- **Dependency:** `civilpy.transportation.terrain`.
- **Goal:** Expose `Terrain.from_ogrip(bbox)` as a prompt-able tool.
- **Agent Workflow:** "AI, fetch the LiDAR for the 500ft corridor around the current alignment."

---

## Phase 2: The "Hub" as an MCP Host
Wiring the representations together so an AI can "see" and "act".

**2.1 Multi-Representation Contract (A3)**
- **Dependency:** `civilpy.structural.placement`.
- **Shadow MCP Workflow:**
  1. **User:** "Place a 30ft slab bridge at Station 10+00."
  2. **Agent:** Calls `civilpy` to create `SlabBridgeComponent`.
  3. **Output A (Rhino):** Agent sends BREP commands to `RhinoMCP`.
  4. **Output B (MIDAS):** Agent sends `midas_payloads()` to `MidasCivil` via `civilpy` tools.

**2.2 Analysis Reconciliation (The Validation Gate)**
- **Goal:** Automate the "Track B" reconciliation.
- **Agent Tool:** `reconcile_analysis(civilpy_results, midas_results)`.
- **Success Metric:** AI confirms L1 (civilpy) matches L2 (MIDAS) within 5% before proceeding to detailing.

---

## Phase 3: Vertically Sliced "Agent-First" Roadmaps
Each bridge type is carried through the full Shadow MCP loop.

1. **Single-span slab:** Prove the "Rhino ↔ Agent ↔ MIDAS" loop using equivalent-strip.
2. **Continuous slab:** Multi-span logic and negative moment reconciliation.
3. **Precast box beams:** Adjacent-box distribution factors and transverse PT.
4. **Precast I-girders:** Composite deck action and prestress modeling.
5. **Steel:** Field splices and plate girder optimization.

---

## Phase 4: AssetWise Integration (The Lifecycle Loop)
Closing the loop between design and management.

- **Inventory Search:** Tool to search AssetWise via SFN or bridge number.
- **Condition-Driven Design:** Agent reads "spalled deck" from AssetWise and automatically adds dead load for a future overlay in the MIDAS model.

---

## Implementation Status

- [ ] **Rhino MCP Integration:** wiring `civilpy` commands to the `RhinoMCP` server.
- [ ] **Shadow MCP Wrapper:** Create `mcp_server.py` to expose `civilpy` tools to MCP clients.

---

## Next Steps
1. **Initialize the Shadow MCP Server:** Build a FastAPI-based MCP server that imports `civilpy.structural`.
2. **Rhino-to-Midas Live Link:** Use the MCP agent to move a bridge abutment in Rhino and watch the MIDAS support node update in real-time.
