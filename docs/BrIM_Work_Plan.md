# BrIM Source-of-Truth Work Plan

Goal: make the **Rhino model the full BrIM "source of truth"** for a bridge —
faithful geometry **and** a complete, per-object BIM attribute record (pay items,
SCD/year, material properties) — from which the MIDAS analysis model, quantity
estimates, and other downstream models are generated.

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` needs review

---

## Phase 0 — Foundation (do first; everything else builds on these)

- [ ] **0.1 Units.** Rhino must always be in the **Large Objects – Feet + Inches**
  template (Feet, not mm). Draw in feet directly (drop the ×304.8 scale). Set
  `ModelUnitSystem = Feet`, large-object tolerance.
- [ ] **0.2 BIM attribute schema (`civilpy.structural.bim`).** One typed
  attribute contract per component, replacing the blanket `gdr.*`. Every object
  carries `bim.type` + `bim.id` (unique) and, where relevant, **`bim.scd` +
  `bim.scd_year`** (the highest-value BIM keys), plus a **pay item** and
  **material** block. Source of truth = civilpy (testable), consumed by the
  Rhino draw, MIDAS, and estimating.
  - Namespaces: `girder.*`, `deck.*`, `parapet.*`, `bearing.*`, `load_plate.*`,
    `haunch.*`, `shear_stud.*`, `rebar.*`, `diaphragm.*`, plus shared
    `bim.*`, `pay.*`, `mat.*`.
- [ ] **0.3 Pay-item catalog (`civilpy.structural.pay_items`).** ODOT item
  numbers with description, unit, level. Seed: `513E10220` structural steel
  (per lb), `513E20000` welded shear studs (ea), deck/parapet concrete (cy),
  epoxy-coated reinforcing (lb), etc. Each component maps to its item.

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
- [ ] **1.4 Girder fillets (no square corners).** Model the web-to-flange
  fillet (k region) so haunch rebar and splice plates have realistic clearance
  — square re-entrant corners mislead detailing.
- [ ] **1.5 Shear studs.** Rows of welded studs on the top flange (composite).
  Own object + `513E20000` pay item (ea).
- [ ] **1.6 Parapet rebar per SCD.** Current cage is generic; ODOT SBR-1-20
  rebar **extends down into the deck** (dowels) and follows the barrier bar
  schedule. Match the SCD: vertical dowels lapping into the deck, longitudinal
  runners at the SCD spacing.

## Phase 2 — BIM attributes populated (per object)

- [ ] **2.1 Girders.** `girder.shape`, `mat.spec` (ASTM A709), `mat.grade`
  (36/50/50W/70), `mat.type` (weathering/carbon), `mat.treatment`
  (none/galvanized/painted), `pay.item` 513E10220 (lb) + computed weight.
- [ ] **2.2 Shear studs.** dia, length, count, `513E20000` (ea).
- [ ] **2.3 Deck.** thickness, **deck slope**, **crown offset**, `mat.fc_psi`,
  `mat.class` (Class S), concrete pay item (cy) + volume.
- [ ] **2.4 Parapets.** `bim.scd`/`bim.scd_year`, height, `mat.fc_psi`, pay
  item (ft or cy) + length/volume.
- [ ] **2.5 Bearings.** type (elastomeric), **plies/ply thickness**, total
  thickness, fixity, pay item.
- [ ] **2.6 Load plates.** thickness, `mat.spec`/`grade`, weight, pay item.
- [ ] **2.7 Rebar.** size, diameter, **coating** (epoxy/GFRP/stainless/black),
  **bend shape**, length, weight, pay item (e.g. epoxy-coated reinforcing, lb).
- [ ] **2.8 Concrete (deck/parapet/haunch).** material properties (f'c, unit
  wt, Ec) + concrete pay items.

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
