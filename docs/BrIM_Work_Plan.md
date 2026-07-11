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
- [ ] **1.6 Parapet rebar per SCD.** Current cage is generic; ODOT SBR-1-20
  rebar **extends down into the deck** (dowels) and follows the barrier bar
  schedule. Match the SCD: vertical dowels lapping into the deck, longitudinal
  runners at the SCD spacing.

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
- [ ] **3.2 Read-back.** Extend `rhino_gdr` (→ `rhino_bim`) to read the new
  per-type attributes back into the hub, so the Rhino model round-trips as the
  source of truth (BIM → MIDAS/estimate) without loss.
- [ ] **3.3 Estimating hook.** Notebook cell: walk the model, group by pay
  item, output quantities (steel lb, studs ea, concrete cy, rebar lb) → on-the-
  fly estimate.

---

## Notes / decisions
- Attribute values live in **civilpy** (source of truth), written to Rhino user
  text on the geometry; the Rhino model is the record other models regenerate
  from.
- SCD + year are the priority BIM keys (they imply most standard attributes);
  record them on every standard-detail component (parapet, deck, railing).
