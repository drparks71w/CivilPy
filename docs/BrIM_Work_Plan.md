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

- [~] **5.1 `BoxBridgeInput` / layout.** Adjacent boxes across the width
  (box size + span from the PSBD tables), transverse tie rods and
  diaphragms per the SCD, composite topping vs non-composite from the
  design line (`rhino_box_bim.BoxBridgeInput`). Remaining: skew (sheet
  2/6 diaphragm/tie offset rules) and shear-key geometry.
- [x] **5.2 Prestress from the standard designs.** `box_beam_pipeline
  .box_beam_line_checks`: strand pattern from `box_beam_design(box,
  span)`, elastic shortening + approximate lump-sum losses (5.9.3),
  transfer stresses at the 60-diameter transfer length and service
  stresses (5.9.2.3), Strength I flexure (5.6.3), tabulated camber
  passed through. Fully-bonded transfer check is conservative at the
  longest catalog spans (the sheet debonds there — flagged, not
  modeled).
- [x] **5.3 Live-load distribution.** Adjacent-box `moment_df_interior_
  box` / `shear_df_interior_box` (4.6.2.2.2b/3c, thin-wall J) feed the
  same `girder_line_envelope` machinery the steel slice uses.
- [~] **5.4 MIDAS spoke.** `structural_model_from_box`: line beams per
  box broken at the diaphragm stations, transverse tie elements, loads
  matched to the L1 pipeline; PSBD section constants in element
  metadata for a value-type MAPI section. Remaining: the grillage
  refinement and a live-MIDAS reconciliation run.
- [x] **5.5 BrIM emit.** `rhino_box_bim.box_beam_bridge_emit`: hollow-
  tube members (four wall prisms), strand rows, tie rods, diaphragms,
  bearing pads, composite topping; one `515E10000` member count per
  beam `[CONFIRM]`; drawn by the same `draw_bim_emit.py`, read back by
  the same `read_bim_quantities`. Remaining: railing on the topping.
- [ ] **5.6 Substructure reuse.** Same reactions → `optimize_pier_cap` /
  abutment path as the steel slice; needs the support-station/bearing
  frame on the box layout so `assemble_substructure` can place under it.
- [x] **5.7 Walkthrough notebook.** `Notebooks/Box Beam Bridge
  Walkthrough.ipynb`: design line → L1 checks (all passing) → tagged
  emit + quantities → MIDAS hub model.

## Phase 6 — Third vertical slice: prestressed I-beams (PSID-1-13)

Unlike the box slice there is **no companion design-data sheet**
(PSIDD does not exist), so this slice *designs* the strand pattern on
the sheet's permissible grid instead of verifying a table.

- [x] **6.1 Catalog extension.** `odot/ps_i_beam.py` now carries all
  13 PSID-1-13 sections: the 7 WF sections (sheets 2-3 properties
  table) added; the Modified Type 4 top-flange widths corrected to the
  sheet (36/36/48 in wide thin flanges, not Type 4's 20 in); per-
  section permissible strand grids vector-extracted from the drawing
  (row totals reconcile with the stated 26/40/52/62 counts), WF
  draped-required web locations, MT4/WF shipping strands, true tapered
  outlines (`ps_i_beam_profile`), and the sheet 10 design constants
  (0.6 in Gr 270 low-lax strand @ 0.217 in^2, f'c 5.5-7.0 /
  f'ci 4.0-5.0 ksi, HL-93 + 60 psf FWS, S < 14 ft, skew < 45 deg).
- [x] **6.2 Strand designer + line checks.** `ps_i_beam_pipeline
  .ps_i_beam_line_checks`: smallest even straight pattern passing
  Service III + Strength I (composite section with the CIP deck), ES +
  approximate lump-sum losses, transfer checks at the 60-diameter
  transfer length with **end debonding designed in pairs** (5.9.4.3.3,
  45 % cap default) when the fully-bonded end overstresses; type-k
  LLDF (4.6.2.2.2b/3a with Kg); elastic release camber. Long spans at
  the 5.0 ksi f'ci ceiling correctly report the midspan release-
  compression limit.
- [x] **6.3 MIDAS spoke.** `structural_model_from_ps_i`: girder lines
  broken at the sheet 5 diaphragm stations (midspan <= 80 ft, quarter
  points beyond), transverse diaphragm elements, DC1/DC2/DW matching
  the line checks; published section constants in element metadata.
- [x] **6.4 BrIM emit.** `rhino_ps_i_bim.ps_i_bridge_emit`: true-
  profile I-prisms driven by the executed design (strand rows with
  debond counts in tags), 2 in haunches, flat CIP deck, CIP
  intermediate diaphragms (515E30000 `[CONFIRM]` each), bearing pads;
  `ps_i_beam` member item 515E20000 `[CONFIRM]`; drawn by the same
  `draw_bim_emit.py`, read back by `read_bim_quantities`.
- [ ] **6.5 Remaining.** Skew; crowned-deck/BridgeLayout integration
  (deck is flat like the box topping); railing on the deck; draped-
  strand modeling (only debonding is designed); substructure reuse
  (same gap as box 5.6); walkthrough notebook.

---

## Notes / decisions
- Attribute values live in **civilpy** (source of truth), written to Rhino user
  text on the geometry; the Rhino model is the record other models regenerate
  from.
- SCD + year are the priority BIM keys (they imply most standard attributes);
  record them on every standard-detail component (parapet, deck, railing).
