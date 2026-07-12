# BrIM Source-of-Truth Work Plan

Goal: make the **Rhino model the full BrIM "source of truth"** for a bridge —
faithful geometry **and** a complete, per-object BIM attribute record (pay items,
SCD/year, material properties) — from which the MIDAS analysis model, quantity
estimates, and other downstream models are generated.

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` needs review

---

## Phase 0 — Foundation (do first; everything else builds on these)

- [x] **0.1 Units.** The emit layer and driver are feet-native:
  `rhino_bim.girder_bridge_emit` emits feet, `draw_bim_emit.py` scales into the
  document's unit system. Keep new documents on the **Large Objects – Feet +
  Inches** template (`ModelUnitSystem = Feet`).
- [x] **0.2 BIM attribute schema (`civilpy.structural.bim`).** Typed tag
  builders per component (`girder_tags` … `rebar_tags`) with shared `bim.*`,
  `pay.*`, `mat.*` blocks; consumed by `rhino_bim` so every drawn object
  carries `bim.type` + unique `bim.id`, SCD keys where standard.
- [x] **0.3 Pay-item catalog.** Seed `PAY_ITEMS` in `civilpy.structural.bim`
  (`513E10220`, `513E20000` confirmed; concrete/reinforcing/bearing numbers
  flagged `[CONFIRM]` until checked against the CMS item master).

## Phase 1 — Geometry correctness (the visible bugs)

- [x] **1.1 Deck as a solid box.** `BridgeLayout.deck_profile_yz()` gives the
  closed crowned cross-section (top + parallel soffit + overhang taper starting
  at the outboard flange edge); the generator lofts it between the skewed ends
  and caps it — one closed solid.
- [x] **1.2 Haunches.** `layout.haunches` hang from the local soffit
  (crown-aware). Sides stay vertical and flange-aligned per BDM 309.3.5
  (verified against the 2020 Ed./Jan 2026 text: vertical sides required at any
  depth, 2 in minimum design haunch — no sloped-forming rule in the ODOT BDM).
- [x] **1.3 Deck rebar — slope + containment.** `deck_rebar_segments` places
  every bar `depth_in` below the *local* deck surface: both mats follow the
  crown/cross-slope (transverse bars crank at the crown as 3-vertex polylines)
  and stay inside the slab; edge clipping unchanged.
- [x] **1.4 Girder fillets (no square corners).** `rhino_bim.i_profile_wh`
  tessellates the k-region fillets into the girder prism outline.
- [x] **1.5 Shear studs.** `rhino_bim` emits stud cylinders (7/8 in × 6 in,
  rows of 3 at 24 in pitch, composite layouts only) each tagged `513E20000`.
- [x] **1.6 Parapet rebar per SCD.** `rhino_bim._sbr1_cage` follows the
  SBR-1-20 schedule: #6 Y601/Y602 verticals at 12 in embedding
  `overhang t − 1.5 in` into the deck (the SCD's `X − 1½"`, = the 9 in
  minimum for the standard deck) with 12 in legs lapping the bottom
  transverse steel, plus #4 GFRP horizontals (5 per face @ 7 in + 2-X401).
  The parapet solid itself is the true single-slope section (18/10 × 42 in,
  588 in² per the SCD design data). The 14 ft guardrail transitions are not
  modeled.
- [x] **1.7 Overhang per BDM Figure 309-4.** Deck overhang soffit runs
  parallel to the top at `t + 2 in` from the edge to the outboard flange tip,
  stepping to the uniform slab there (flush with the 2 in haunch bottom).

## Phase 2 — BIM attributes populated (per object)

All populated by `rhino_bim.girder_bridge_emit` through the `bim` tag
builders; verified in `tests/structural/test_rhino_bim.py`.

- [x] **2.1 Girders.** `girder.shape`, `mat.spec/grade/type/treatment`,
  `513E10220` (lb) with weight from the AISC plf × length.
- [x] **2.2 Shear studs.** dia, length, `513E20000` (ea, one per stud).
- [x] **2.3 Deck.** thickness, `deck.slope_pct`, `deck.crown_offset_ft`,
  `mat.fc_psi`/class, concrete item (cy) with the true crowned-profile volume.
- [x] **2.4 Parapets.** `bim.scd`/`bim.scd_year`, height, `mat.fc_psi`, pay
  item (cy) + length/volume.
- [x] **2.5 Bearings.** elastomeric, plies × ply thickness, total thickness,
  fixity, pay item (ea).
- [x] **2.6 Load plates.** thickness, `mat.spec`/grade 50, computed weight,
  `513E10220`.
- [x] **2.7 Rebar.** size/diameter/weight-per-foot, coating, bend
  (straight / crown-crank), length, weight into the reinforcing item (lb).
- [x] **2.8 Concrete (deck/parapet/haunch).** `mat.*` blocks on all three;
  haunch volume rolls into the superstructure concrete item per convention.

## Phase 3 — Presentation & round-trip

- [ ] **3.1 Authentic materials.** Assign render materials/colors so steel,
  concrete, and reinforcing read realistically in Shaded/Rendered.
- [x] **3.2 Read-back.** `rhino_bim.read_bim_tags` / `read_bim_quantities`
  read every `bim.*`-tagged object (plus the bridge marker) back from a saved
  `.3dm`; verified the live document round-trips to the identical rollup. The
  `gdr.*` tags stay on centerlines/bearings for the analysis reader.
- [x] **3.3 Estimating hook.** `pay_item_quantities(emit)` +
  `read_bim_quantities(path)` group by pay item; demonstrated in Steel Girder
  Bridge Walkthrough §8 (steel lb, studs ea, concrete cy, rebar lb).

## Phase 4 — Substructure components (model stops at the bearings today)

The analysis/design side exists (`Notebooks/Substructure Design from
Preliminary Reactions.ipynb`: reactions → `optimize_pier_cap` STM →
`MultiColumnBent` → `RetainingWall`), but nothing emits substructure
*geometry* — the BrIM record ends at the bearing pads. Close the loop so the
executed design drives the drawn substructure.

- [x] **4.1 Substructure layout.** `substructure_from_layout(layout, ...)`
  (`civilpy.structural.substructure_layout`) places a skew-aligned local
  frame at each support station; the cap top hangs one minimum seat below
  the lowest bearing stack and every girder gets a stepped beam seat
  following the cross slope, so the pads land exactly.
- [x] **4.2 Design → geometry round trip.** Emit dimensions come from the
  executed design objects (`PierCapDesign` span/thickness/depth + tie
  schedule, `MultiColumnBent` column sections/heights/steel area,
  `RetainingWall` stem/footing dims), not free parameters. The only
  explicit inputs are what no civilpy designer sizes yet: pile length,
  footing plan (`FootingSpec`), wingwall run length (`AbutmentSpec`).
- [x] **4.3 Pier emit.** Cap prism, column cylinders (or rectangular
  prisms), footings on `Substructure::*` layers with `bim.*`/`mat.*` tags;
  all CIP concrete measures into `511E40000` Class QC1 substructure (cy)
  `[CONFIRM]` against the CMS item master.
- [x] **4.4 Abutment emit.** Cap beam on HP piles (true I-profiles from the
  steel DB, web along the roadway), backwall, beam seats, and wingwall
  stem+footing panels from the `RetainingWall` dims; steel-pile pay item
  `507E10000` (ft) `[CONFIRM]`. The `odot/capped_pile_abutment.py`
  rebar-mark machinery stays the reference for CPA-1-08 standard details
  (this emit is the general capped-pile case).
- [x] **4.5 Substructure rebar.** Cap main steel straight from the STM ties
  (`PierCapDesign.report.ties` governing bar schedule), stirrups from the
  shear-check parameters, column verticals broken out of the `RebarLayer`
  area with hoops, nominal two-face backwall/wingwall mats (`SubRebarSpec`);
  weights roll into the 509 reinforcing items like the deck mats.
- [x] **4.6 STM results overlay.** `rhino_bim.stm_overlay_emit` draws the
  solved cap STM in place on `Substructure::STM::Ties`/`::Struts` (red /
  blue) in the main document, tagged `bim.analysis` with no pay item —
  excluded from every estimate rollup.
- [x] **4.7 Read-back + estimate.** `pay_item_quantities` /
  `read_bim_quantities` cover the substructure items automatically (tag
  driven); regression tests in `test_rhino_bim.py` +
  `test_substructure_layout.py`; demonstrated end-to-end in the
  substructure notebook §7 (1,310 tagged objects, 511/507/509 items next
  to the superstructure rollup).
- [ ] **4.8 Terrain hook (later).** Footing/pile cutoff elevations from
  `Terrain.elevation_at` once a surface is attached; nominal fixed
  elevations until then.

## Phase 4v — Substructure type variants

Phase 4 built one pier type (multi-column bent) and one abutment type
(capped-pile seat). Cover the rest of the ODOT substructure vocabulary,
one type at a time, each carried through placement → emit → tests the
same way. Per-unit assignment through typed specs so a bridge can mix
types (e.g. integral abutments with a hammerhead center pier).

- [x] **4v.1 Capped-pile pier (pile bent).** `PileBentSpec` /
  `pile_bent_geometry`: cap directly on driven piles — the CPP-1-08
  pattern generalized off the slab-bridge sheet
  (`odot/capped_pile_pier.py` keeps the SCD limits; the HP12X53 default
  carries over). Cap STM from `optimize_pier_cap` with the piles as
  supports, like the abutment cap.
- [x] **4v.2 Hammerhead pier.** `HammerheadSpec` /
  `hammerhead_geometry`: single column with cantilevered cap, soffit
  tapered from the column faces to `tip_depth_ft` at the tips via the
  generic `CapBeam.soffit_profile` (still one prism — the elevation
  profile extrudes across the width). The rebar emit reads the governing
  tie's height out of the STM, so the cantilever main steel lands in the
  **top** chord and the stirrups follow the taper.
- [x] **4v.3 Semi-integral abutment.** `SemiIntegralAbutmentSpec`: the
  seat abutment with the backwall replaced by an end diaphragm that
  moves with the superstructure — drawn on `Superstructure::Diaphragms`,
  concrete measured with the superstructure item (511E12100), back face
  over the cap back edge, encasing the girder ends.
- [x] **4v.4 Integral abutment.** `IntegralAbutmentSpec`: single row of
  HP piles embedded 2 ft into a full-height end diaphragm; **no
  bearings** at that support (`girder_bridge_emit(...,
  integral_supports=...)` skips the pad/plate stack, keeps the `gdr.*`
  support point tagged `gdr.integral`). Diaphragm depth derived from the
  layout (high deck edge to `embed_below_girder_ft` under the girder
  bottom), not a free parameter.
- [x] **4v.5 Type gallery.** Mixed-type regression tests
  (`assemble_substructure` by index/role) in
  `test_substructure_layout.py` / `test_rhino_bim.py`; per-unit specs
  make any combination placeable on one bridge.

## Phase 5 — Second vertical slice: prestressed box beams

Roadmap slice 3 (`Notebooks/Rhino Components/Work Plan.md`) carried through
the same BrIM architecture. Existing assets to build on, not rebuild:
`odot/box_beam_design.py` (PSBD standard-design + rating tables, strand
patterns per box/span), `odot/box_beam.py`, `rhino_box_beam.py` (legacy
direct writer), adjacent-box factors in `aashto/lrfd/distribution.py`,
`strip_seal_joint_box_beam.py`.

- [ ] **5.1 `BoxBeamBridgeInput` / layout.** Adjacent boxes across the width
  (box size from the PSBD tables), shear keys, transverse tie rods per the
  SCD, skew; composite topping (6 in min) vs non-composite with waterproofing
  + asphalt wearing surface as the two deck options.
- [ ] **5.2 Prestress from the standard designs.** Strand pattern/count from
  `box_beam_design(box, span)`; verify release + final stresses, approximate
  losses (LRFD 5.9.3), camber, and flexural/shear capacity as the pure-Python
  L1 gate.
- [ ] **5.3 Live-load distribution.** Wire the adjacent-box `moment_df` /
  `shear_df` (4.6.2.2.2b/3c) into the `girder_pipeline` envelope the way the
  steel slice used the beam factors.
- [ ] **5.4 MIDAS spoke.** `structural_model_from_layout` analog for the box
  layout (line beams per box minimum; grillage with transverse ties as the
  refinement); reconcile with the L1 baseline per the roadmap validation
  gate.
- [ ] **5.5 BrIM emit.** Port `rhino_box_beam.py` to the `rhino_bim` emit
  architecture: box prisms with voids, strands as tagged polylines, tie
  rods, shear keys, bearing pads, railing per SCD on the boxes/topping;
  prestressed member pay item (515E, ea/ft) `[CONFIRM]`.
- [ ] **5.6 Substructure reuse.** Same reactions → `optimize_pier_cap` /
  abutment path as the steel slice; Phase 4 emit applies unchanged.
- [ ] **5.7 Walkthrough notebook.** Box-beam analog of the Steel Girder
  Bridge Walkthrough, ending in the same quantities read-back.

---

## Notes / decisions
- Attribute values live in **civilpy** (source of truth), written to Rhino user
  text on the geometry; the Rhino model is the record other models regenerate
  from.
- SCD + year are the priority BIM keys (they imply most standard attributes);
  record them on every standard-detail component (parapet, deck, railing).
