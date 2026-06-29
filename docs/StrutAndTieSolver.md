# Rhino-to-Python pier-cap optimizer — strut-and-tie solver

A roadmap, now with a **working end-to-end prototype**, for turning a drawn
concrete D-region (a rectangle or arbitrary polygon, with supports and loads)
into an *optimized* strut-and-tie truss, then sizing and costing it.

> **Status (2026-06-29): prototype of all five phases shipped** on branch
> `stm-topology-optimization`, in `src/civilpy/structural/stm_topology/` plus a
> direct-stiffness upgrade to `strut_and_tie.py`.  The single-load-path cases
> (deep beam, cantilever bent cap, region with a void) run cleanly with correct
> statics; complex multi-point-load caps are a documented limitation (below).

## Architecture decisions (as built)

- **One front end, two authors.** The optimizer consumes a
  `DRegionProblem` (boundary polygon + thickness + material + supports + loads).
  The manual workflow builds it in Python; the Rhino workflow reads the same
  object from a tagged `.3dm` via `rhino_stm.problem_from_3dm` (a
  `stm.kind=region` curve, per the frozen contract in
  `docs/Rhino Design Philosophy.md` §"Two front ends").  The optimizer never
  imports `rhino3dm`.
- **Structured quads on a fixed grid, not a body-fitted mesh.** Arbitrary
  polygons (and voids/solids) are handled by masking a bounding-box grid of
  square Q4 elements — elements whose centroid falls outside the polygon are
  passive. This keeps the regular grid that makes the density filter and the
  skeletonization trivial, and it means **no `gmsh`/`scikit-fem` dependency**.
- **NumPy/SciPy only.** The FEA uses the closed-form `top88` element stiffness;
  the skeletonization is a hand-rolled Zhang–Suen thinning; arbitrary-polygon
  point-in-polygon uses `matplotlib.path`. No `scikit-fem`, `scikit-image`,
  `networkx`, `pygmsh`, or `shapely` — the pipeline runs on civilpy's existing
  core deps.
- **The extracted truss is solved by the new indeterminate solver** (Phase 4),
  with an optional fully-stressed (area∝force) iteration to pick the load path.

---

### Phase 1 — Region front end & meshing ✅

* Manual: `DRegionProblem` / `DRegionProblem.rectangle(...)`.
* Rhino: `rhino_stm.problem_from_3dm(path)` → `DRegionProblem`
  (`stm.kind=region` + `stm.thickness`/`stm.fc`/… and `void`/`solid` curves;
  `stm.bearing` on supports/loads).
* Meshing: `stm_topology.mesh.GroundMesh` — structured Q4 grid, arbitrary
  polygon + void + solid masking, support/load → grid-node mapping with bearing
  spreading. **`top88` node/DOF numbering** so the element stiffness drops in.

### Phase 2 — SIMP topology optimization engine ✅

* `stm_topology.simp.optimize_density(mesh, vol_frac, penal, rmin, …)`.
* Linear plane-stress FEA (sparse assembly + `spsolve`), optimality-criteria
  update, cone density filter, passive solid/void elements. Returns a
  `(nely, nelx)` density field. Verified to drive a deep beam to the classic
  tied-arch pattern.

### Phase 3 — Truss extraction (density → strut-and-tie) ✅

* `stm_topology.extract.extract_truss(density_result, threshold, merge)`.
* Threshold → **Zhang–Suen thinning** → skeleton graph walk → straight members
  between real graph nodes (junctions + forced support/load anchors) → node
  merge → graph cleanup (prune degree-1 spurs, contract degree-2 chains, keep
  the anchored component). Anchors snap to their true BC coordinates.
* Key idealization: truss joints land **only at supports, loads, and genuine
  junctions** — a smooth arch becomes one straight strut, not a wobbly chain.

### Phase 4 — Indeterminate truss solver (DSM) ✅

* `StrutAndTieModel.solve(method="auto")` — method of joints when determinate,
  **direct stiffness** when indeterminate; `degree_of_indeterminacy()` dispatches.
* Member `area` (relative stiffness) sets the load path among redundants.
* `StrutAndTieModel.solve_fully_stressed()` — iterate area∝|force| to a
  uniform-stress load path (the natural STM idealization), exception-safe
  against members shrinking to a mechanism.
* The original determinate API and results are unchanged (doctest + tests green).

### Phase 5 — Code checks & ODOT cost ✅

* `stm_topology.cost` — `size_ties` (invert AASHTO 5.8.2.4: `Ast = Pu/(φ·fy)`,
  rounded to whole bars), `check_nodes` (5.8.2.5 bearing/nodal-zone, CCC/CCT/CTT
  classified from solved member signs), `material_takeoff`, `estimate_cost`
  (concrete by the cy, reinforcing by the lb, ODOT-style unit prices).

---

## The one call

```python
from civilpy.structural.stm_topology import DRegionProblem

p = DRegionProblem.rectangle(20, 10, thickness=2.0, vol_frac=0.35)
p.add_support(1, 0, bearing=1.5)
p.add_support(19, 0, fix_x=False, bearing=1.5)
p.add_load(10, 10, fy=-600, bearing=1.5)

result = p.solve()        # mesh → SIMP → extract → solve → size → cost
print(result.summary())
result.plot()             # density field + extracted truss overlay
```

`result.forces` feeds the AASHTO capacity checks; `result.model` is a normal
`StrutAndTieModel` (so `to_3dm`, `plot`, etc. all work).

## Validation

| Case | Result |
|---|---|
| Deep beam (20×10, central load) | Tied arch, DoI=0, tie = (P/2)(L/2)/d to <1%; struts/tie statics exact |
| Cantilever bent cap (12×6) | Stable 5-node/7-member truss, ΣRy = applied load, top tie sized |
| Rectangle with a duct void | Load path routes around the void, stable |

11 unit tests in `tests/structural/test_stm_topology.py` (solver determinacy,
DSM equilibrium, mesh masking, SIMP convergence, thinning, end-to-end statics,
tie sizing/cost). All green; existing `strut_and_tie`/`rhino_stm` tests unaffected.

## Known limitations / next steps

- **Multi-point-load caps** (several loads on a straight top chord) can extract
  as an under-triangulated mechanism; the pipeline degrades gracefully
  (`result.stable == False`, density + geometry still returned) instead of
  crashing. Next: a triangulation/stabilization pass that guarantees each load
  has a strut path to a support (e.g. add minimal bracing members, or solve as a
  ground-structure layout problem).
- **`scikit-image` skeletonize** could replace the hand-rolled thinning if the
  optional dep is acceptable — pluggable behind `extract`.
- **Volume-fraction sweep** (Phase 5 outer loop): wrap `optimize_to_stm` over a
  range of `vol_frac` and pick the minimum-cost valid design. Deferred.
- **Rhino round-trip** of the extracted truss + an `STMRegion` authoring command
  on the C# side (tracked in `docs/Rhino Design Philosophy.md`).
- **`problem_from_3dm`** is written against the frozen tag schema but untested
  live (needs `rhino3dm` + an authored region `.3dm` fixture).
