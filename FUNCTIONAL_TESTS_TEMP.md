# Girder → Field-Splice Pipeline — Functional-Test Walkthrough (TEMPORARY)

> **Scratch doc, `development` branch.** Delete or fold into `docs/` once the
> pipeline stabilizes. It walks a user through every functional test to run, in
> order: the **Rhino authoring** front end first, then the **Python engine**,
> then the **round-trip** back to Rhino. The last section captures the
> **Grasshopper framing-plan authoring** we want to build next (the planning-
> stage, precast-box-or-steel, quick-cost-estimate front end).

---

## 0. The picture — where the tests live

Two codebases, one contract. They never call each other; they share a **tagged
`.3dm` file** (the `gdr.*` user-text schema in
`docs/Rhino Design Philosophy.md`).

```
  RHINO / C# plugin  (authoring)          PYTHON / civilpy  (engine)
  ───────────────────────────             ──────────────────────────
  GirderLines  ┐                          read_girder_model  (G4)
  GirderShape  ├─ writes gdr.* ─► .3dm ─► girder_line_envelope + place_splices
  (bearings)   ┘                          design_rolled_splice   (G6/G7/B4)
  GirderSplice ◄──── reads gdr.checks ◄── write_splice_results   (G8)
                                          optimize_splice_shape  (B5)
```

Everything on the Python side runs **offline today** (no live MIDAS): the
continuous-beam solver stands in for the moving-load analysis. The live-MIDAS
leg (G5 moving load + `analyze()`) and the MIDAS-vs-MDX benchmark (B1/B2) are
the only pieces that still need Civil NX.

**Environment for all Python commands below:** the civilpy source is exercised
through the snbi_ui virtualenv.

```bash
cd /home/dane/projects/civilpy
PY=/home/dane/projects/snbi_ui/.venv/bin/python
```

---

## 1. RHINO AUTHORING — manual functional tests (do these in one Rhino 8 session)

The full step list lives in the **C# repo**:
`/home/dane/projects/odotrhinoplugin/docs/VERIFICATION-TODO.md`. Summary of what
to verify (commands autocomplete: `GirderLines`, `GirderShape`, `GirderSplice`):

1. **`GirderLines` — generated framing.** No selection → set `Girders=5`,
   `Spacing=8`, enter span lengths (e.g. `70`, `90`, `70`) → **5 lines** on
   `Girders::Lines` along +X, **bearing points** on `Girders::Bearings` at each
   substructure station. Confirm via *Properties → Attribute User Text*:
   - girder lines carry `gdr.kind=girder`, `gdr.line=1..5`, `gdr.id=<GUID>`;
   - bearing points carry `gdr.kind=support` + `gdr.fixity=fixed|expansion`
     (continuous default: one fixed line at the interior pier, rest expansion).
2. **`GirderLines` — traced mode.** Pre-select existing curves → they get
   tagged as girder lines, no new geometry.
3. **`GirderShape`.** Select the 5 lines → pick `W24X104` (grade dropdown) →
   `gdr.shape`/`gdr.grade` stamped; optional cosmetic extrusion on
   `Girders::Display` (that extrusion has **no** `gdr.kind` — Python ignores it).
4. **Bridge parameters.** `GirderLines` currently writes `gdr.deck_t`,
   `gdr.deck_weff`, `gdr.deck_fc`, `gdr.ship_max`, `gdr.bolt_*` to
   **document** user text.
   > ⚠️ **Known gap (blocks the Python read of bridge params).** `rhino3dm`
   > cannot read `RhinoDoc.Strings`, so these document-level tags are invisible
   > to the Python reader. **Fix:** author them as object user text on a
   > `gdr.kind=bridge` marker point (see §"Grasshopper authoring" and the G1
   > sign-off item #0 in the design doc). Until the C# side moves them, the
   > Python reader falls back to BDM defaults and warns loudly — which is fine
   > for a first pass but must be closed for real deck geometry.
5. Save as `framing.3dm`.

**Pass criteria:** every authored object has the tags above; the extrusion is
cosmetic-only; `Save` produces a `.3dm` the Python reader opens without error.

---

## 2. PYTHON ENGINE — automated functional tests (the required suite)

Run the whole girder-pipeline suite. All should pass (≈75 tests; the
influence-line envelope makes `test_girder_pipeline` take ~30 s).

```bash
$PY -m pytest \
  tests/structural/test_rhino_gdr.py \
  tests/structural/test_bolted_field_splice.py \
  tests/structural/test_composite_section.py \
  tests/structural/test_continuous_beam.py \
  tests/structural/test_girder_pipeline.py \
  tests/structural/test_girder_midas.py \
  tests/structural/test_girder_optimizer.py \
  -v
```

What each proves:

| Test file | Stage | Proves |
|---|---|---|
| `test_rhino_gdr.py` | G4, G8 | reads a tagged `.3dm` → hub; writes/reads splice `gdr.status/summary/checks` |
| `test_bolted_field_splice.py` | G7 | reproduces **REF-DESIGN Splice #1** exactly (332.53 k, 10 bolts/flange, all OK); `girder_side_from_w`; the two legacy plate-girder designs still pass |
| `test_composite_section.py` | B4 | composite `n`/`3n`/cracked section props + `fcf` validated ±1% vs the MDX tables; `design_rolled_splice` needs no MDX-supplied stress |
| `test_continuous_beam.py` | analysis | slope-deflection solver vs closed form (`wL²/8`, `R=[15,50,15]`, 3-span symmetry) |
| `test_girder_pipeline.py` | G6 + E2E | splice placement in low-moment windows; **full offline pipeline** on the 60-80-60 benchmark |
| `test_girder_midas.py` | G5 | real per-shape `SECT` + per-grade `MATL` payloads from the hub |
| `test_girder_optimizer.py` | B5 | shape sweep + girder plastic-moment gate + cost ranking; beats the as-built |

**Full-repo regression** (optional, ~2 min): `$PY -m pytest tests/structural/ -q`.

---

## 3. PYTHON ENGINE — manual end-to-end functional test (offline, copy-paste)

This exercises the whole engine without Rhino or MIDAS. Save as `e2e.py`, run
`$PY e2e.py`.

```python
from civilpy.structural.girder_pipeline import girder_line_envelope, place_splices
from civilpy.structural.aashto.lrfd.composite import design_rolled_splice
from civilpy.structural.aashto.lrfd import BoltSpec, PlatePair, WebPlate
from civilpy.structural.girder_optimizer import optimize_splice_shape, cheapest_feasible

# 1) OFFLINE ENVELOPE for one interior girder line (placeholder 60-80-60 span,
#    loads in klf, distribution factor ~0.65). Replace with MIDAS output later.
stations, M = girder_line_envelope([0, 60, 140, 200],
    dc1_klf=0.85, dc2_klf=0.15, dw_klf=0.14, n_sections=21, gdf=0.65)

# 2) PLACE splices (shipping-limited, low-moment windows)
picks = place_splices(stations, M, ship_max_ft=130.0)
print(f"{len(picks)} splice(s):")
for p in picks:
    print(f"  x={p.station:.1f} ft  |Mu|={p.factored_moment:.0f} k-ft")

    # 3) DESIGN each splice (composite fcf computed internally — no MDX needed)
    plates = PlatePair("Grade 50", 0.375, 5.5, 0.375, 12.75, 2)
    d = design_rolled_splice("W24X131", "W24X104", p.loads,
        deck_thickness=7.5, deck_eff_width=84.0, rebar_area=7.46,
        bolts=BoltSpec("A325", 0.875, flange_threads_excluded=False,
                       web_threads_excluded=False, surface_class="C",
                       hole_type="oversize"),
        top_plates=plates, bottom_plates=plates,
        web_plate=WebPlate("Grade 50", 0.4375, 2),
        top_flange_rows=2, bottom_flange_rows=2, web_rows=4,
        bolt_spacing=3.0, flange_edge=1.5, flange_end=1.5,
        web_edge=1.5, web_end=1.5, design_year=2016)
    print(f"    design ok={d.ok}  {d.top_flange.total_bolts} bolts/flange  web {d.web.total_bolts}")

# 4) OPTIMIZE — cheapest feasible rolled shape vs the as-built (B5)
opts = optimize_splice_shape(picks[0].loads,
    ["W24X84", "W24X104", "W24X131", "W27X102"],
    length_ft=90.0, max_factored_moment=900.0,
    deck_thickness=7.5, deck_eff_width=84.0, rebar_area=7.46)
best = cheapest_feasible(opts)
print(f"cheapest feasible: {best.shape}  ${best.total_cost:,.0f}  {best.total_bolts} bolts")
```

**To run against a real Rhino-authored `.3dm`** (from §1), read it into the hub
first:

```python
from civilpy.structural.rhino_gdr import read_girder_model
bridge = read_girder_model("framing.3dm")     # GirderBridge (hub + deck/bolt params)
print(bridge.girder_lines)                    # {"1": [elem ids], ...}
print(bridge.deck_t, bridge.deck_weff, bridge.ship_max)
# then build the envelope from the geometry + loads and continue as above
```

**Pass criteria:** the reader loads the model and warns only about missing deck
params; the envelope is hogging over piers / sagging mid-span; a splice is placed
near a contraflexure and designs `ok=True`; the optimizer returns a feasible
shape.

---

## 4. ROUND-TRIP — Python write-back → Rhino review

1. Python authors the results file:

   ```python
   from civilpy.structural.rhino_gdr import write_splice_results, SpliceMarker
   write_splice_results("splice_results.3dm",
       [SpliceMarker(point=(71.8, 8.0, 0.0), design=d, line="2")])
   ```
2. In Rhino, run **`GirderSplice`** → import `splice_results.3dm`. Verify the
   check table renders and **NG rows show red** (`gdr.status=NG`). The C# repo's
   `VERIFICATION-TODO.md` §4 has a `rhinoscriptsyntax` snippet to fabricate an
   NG marker to exercise the dialog before a real design exists.

**Pass criteria:** the `article|check|actual|allowable|verdict` rows round-trip;
NG rows are visually flagged.

---

## 5. Status — what's verified vs. what still needs a live session / data

| Area | State |
|---|---|
| Rhino authoring (`GirderLines`/`GirderShape`/`GirderSplice`) | ✅ shipped C#; manual checks in §1 |
| Python read → hub (G4) | ✅ automated |
| Splice design, Splice #1 reproduction (G7/B4) | ✅ automated |
| Offline envelope + placement + end-to-end (G6) | ✅ automated |
| Write-back round-trip (G8 tags) | ✅ automated; ⏳ 3D plate/bolt geometry |
| Shape/cost optimizer (B5) | ✅ automated (splice-region); ⏳ full limit states |
| **Bridge params visible to Python** | ⚠️ needs `gdr.kind=bridge` marker (see §1.4) |
| **Live MIDAS** (moving load, `analyze()`, real SECT JSON — G5) | ⏳ needs Civil NX |
| **B1/B2** MIDAS-vs-MDX + deflection | ⏳ needs real span arrangement (Mon) + Civil NX |
| **Precast box girders** | ❌ not built — pipeline is steel W-shapes only |

---

## 6. NEXT FOCUS — Grasshopper framing-plan authoring (planning-stage cost)

**Goal (Dane):** a Grasshopper definition that lets a planner *quickly* lay out a
bridge — span lengths, girder spacing, girder count, **girder type (precast box
vs. steel)**, materials, fixity at every substructure unit, stiffener details/
locations — and pushes it to MIDAS with everything the analysis needs, so we can
get **preliminary cost estimates in the planning stage**.

This is an authoring layer on top of the same `gdr.*` contract. What it must
produce, and what the engine needs from it:

### 6a. What the authoring must stamp (extends today's contract)
- **Span layout:** girder lines in plan (X = stations, Y = spacing) — already
  `gdr.kind=girder`. Add a document/marker field for the **substructure
  stations** so bearings and pier locations are explicit, not inferred.
- **Girder type + section:** today `gdr.shape` assumes an **AISC W** label.
  Add `gdr.type=steel_i|precast_box|steel_box` and let `gdr.shape` carry the
  right vocabulary per type (AISC label for steel; a box designation for
  precast). **This is the key new tag** — the engine currently only resolves
  steel via `steel.W`.
- **Materials:** `gdr.grade` (steel) is done; for precast box add
  `gdr.fc_beam`, `gdr.strand`… — a materials dropdown per girder type.
- **Fixity at substructure units:** `gdr.fixity=fixed|expansion` on bearing
  points is done — the dropdown should set it **per substructure line**, which
  is exactly what a framing plan wants.
- **Stiffeners:** reserve/author `gdr.kind=stiffener` + `gdr.stiff=bearing|
  transverse` markers at their stations (reserved in the contract, **not yet
  authored** by C# or read by Python — a clean next tag).
- **Bridge params on a marker:** stamp deck/bolt params on a `gdr.kind=bridge`
  point (fixes §1.4 so Python actually reads them).

### 6b. What's needed on the engine side to close the loop
- **Precast-box design path.** The steel splice/optimizer path does not apply.
  civilpy already has box-beam / soil-interaction pieces
  (`structural.odot.box_beam_design`, `structural.cande`) — a parallel
  `girder_type="precast_box"` path should route there for capacity + quantities.
- **Preliminary cost hook.** `girder_optimizer` already has a steel weight +
  splice cost model; generalize it to a **quantity-takeoff → unit-price**
  estimate per girder type (steel lb, deck CY, precast box each, bearings,
  stiffeners) so the planner gets a number. This is where the ODOT
  warehouse / estimator price data plugs in.
- **Grasshopper → MIDAS.** Same `gdr.*` file the Python `midas_models`
  builders consume (`hub_section_material_blocks` for steel today); add the box
  and moving-load builders as G5's live leg lands.

### 6c. Suggested build order for the authoring focus
1. Add `gdr.type` + the `gdr.kind=bridge` marker to the C# / Grasshopper
   authoring and to the Python reader (small, unblocks real deck params).
2. Grasshopper framing-plan definition: span/spacing/count/type dropdowns →
   girder lines + bearings + bridge marker, fixity per substructure line.
3. `gdr.kind=stiffener` authoring + reader.
4. Precast-box girder-type branch in the reader + a first quantity/cost takeoff
   for planning-stage estimates (steel vs. box side-by-side).
5. Wire MIDAS push for the chosen type; validate against a live Civil NX run.

> The steel splice pipeline (this branch) is the proof that the
> author-in-Rhino → analyze → design → cost round-trip works end to end. The
> Grasshopper framing-plan authoring generalizes the *front* of it for planning,
> and the precast-box + cost-takeoff work generalizes the *engine* for the
> girder types a planner actually chooses between.
