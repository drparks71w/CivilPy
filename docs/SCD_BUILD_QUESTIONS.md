# SCD build questions & assumptions

Running record of judgment calls made while building the SCD components.
Format: SCD — question — what was assumed — what to revisit if wrong.

## Cross-cutting: module-name/function-name collisions in `odot/__init__.py`

- **Pitfall found while testing FB-1-82.** Several submodules define a
  guarded-lookup function with the *same name* as the module itself
  (`rocker_bolster.py` has `def rocker_bolster(...)`, `fixed_bearing.py`
  has `def fixed_bearing(...)`). `odot/__init__.py` re-exports that
  function into the package namespace, which — because Python sets the
  package's submodule attribute as an import side effect and then the
  `from .foo import foo` statement rebinds that same attribute name to
  the function — silently shadows the submodule. `from
  civilpy.structural.odot import fixed_bearing as fb` (or `import
  civilpy.structural.odot.fixed_bearing as fb`) then binds `fb` to the
  *function*, not the module, and `fb.SCD` etc. raise `AttributeError`.
  Only affects code that wants the *module itself* aliased through the
  package (GH scripts and `__init__.py` are unaffected — they use `from
  civilpy.structural.odot.fixed_bearing import NAME`, the direct
  dotted-submodule form, which always resolves correctly). Fix in test
  code: import the specific names you need directly from the dotted
  submodule path instead of aliasing the module through the package
  (see `test_odot_fixed_bearing.py`'s top-of-file comment for the
  worked example). Worth remembering before adding any new
  `<name>.py` module whose primary lookup function is also called
  `<name>`.

## Cross-cutting: Rhino layer taxonomy (2026-07-06)

- **Culvert vs. Site assignment.** Every SCD component's GH script bakes
  display-only, untagged geometry (no `gdr.kind`), so none of them are
  touched by a C# import command's per-kind routing. Assumed: headwalls/
  box culverts go under `Culvert::<SCD>` (HW-1.1, HW-2.1/2.2, BCHW);
  everything else at grade goes under `Site::<SCD>` (AS-1-15, AS-2-15,
  DS-1-92, PCB-91), including DS-1-92 even though a drip strip physically
  mounts on the deck fascia. Revisit — and move DS-1-92 to `Deck::` — if
  the SCD components ever get real `gdr.kind` tags and start participating
  in the girder/deck import pipeline. See `docs/Rhino Design
  Philosophy.md`'s "Rhino layer taxonomy" section for the full rationale
  and the authoritative Deck/Superstructure/Substructure paths this
  extends.

## AS-1-15 (rev. 01-20-2023)

- **Bar stacking at the covers.** Section B-B dimensions "3 in clear" to
  the A bars (bottom) and to the C bars (top), while section A-A
  dimensions "3 in CL." to the B501 at both faces — they cannot all sit
  at exactly 3 in. Assumed: A bars (primary #10) on the bottom cover with
  B501 stacked above them; B501 on the top cover with C bars stacked
  below. Revisit if a bar list / project plan shows the opposite top
  stack (would shift C and top-B501 centerlines by one #5 diameter).
- **Bracketed count formulas** (`[12(W-0.5)/K] + 1` etc.). Interpreted the
  bracket as "round the number of spaces up" so the placed spacing never
  exceeds the tabulated value, and the layout distributes bars evenly
  between the 3 in edge clearances. Exact-multiple widths give the exact
  tabulated spacing.
- **B501 bottom spacing does not close exactly.** 3 in + 5 spaces @ 6 in +
  (count − 6) spaces @ N + 3 in ≠ L for L = 20 ft (4 in short) and
  L = 30 ft (1 in long). The sheet writes "@ N c/c" without ±, but the
  counts govern; the layout anchors the first/last bars at the 3 in
  clearances and spreads the interior spaces evenly (≈N). Revisit only if
  exact N spacing with a variable end space is preferred.
- **D801/D802 secant terms vs. drawn geometry.** The tabulated lengths
  carry sec(θ) on the diagonal term although the bars are placed parallel
  to the roadway CL (plan) where the longitudinal seat profile is
  skew-independent. Schedule lengths use the sheet formulas verbatim;
  the drawn polyline is the profile-true 45° bar (leg 1'-0", diagonal to
  the top-cover plane, low end embedded below the seat). At skew the
  drawn length therefore differs from the schedule length — schedule
  governs quantities.
- **D-bar vertical placement.** The sheet fixes the 2½ in offset at the
  slab bottom and the bar shape, but not the exact top/bottom termination
  elevations. Assumed the diagonal stops at the top-cover plane (3 in
  below the surface) and extends below the slab bottom by the remainder
  of the 45° diagonal; the D801 terminal hook is not drawn (noted in the
  component report).
- **Not modeled** (reported by the component): A-bar end bends (1'-5"
  total extra length is in the schedule), the optional widened edge
  portion for integral curb/barrier, curb-height transitions, deck
  crown/cross slope, sheet-2 joint grooves/seals (cataloged as data in
  `JOINT_DETAILS` / `JOINT_NOTES` / `SEAT_CONFIGURATIONS`).

## PSID-1-13 (rev. 07-18-2025) -- Wave 6

- **Top/bottom flange widths for Type 3/4 are published AASHTO standard
  values, not individually re-measured from the rendered sheet.** Type 2's
  12/18 in flanges were confirmed directly against this sheet's own
  dimensions; Type 3 (16/22) and Type 4 (20/26, shared by all three
  Modified Type 4 depths) are the well-known standard AASHTO I-girder
  values. Revisit with a closer render if a project needs an exact
  flange-width citation from this specific sheet.
- **No PSIDD-1-xx design-data companion sheet is archived** (unlike
  PSBD-1-25/PSBDD-1-25), so strand patterns, camber, and load ratings
  have no source to encode yet — only section geometry and the general
  bar-mark/bend-type legend are cataloged.
- **ICD-1-20/ICD-2-18/SICD-1-21/SICD-2-14 intentionally not built.** All
  four are end-condition add-ons to an existing girder line (integral or
  semi-integral abutment details) rather than standalone structures with
  their own geometry to generate; SICD-2-14 is additionally a half-
  guidance "guide" sheet with a full companion (SICDD-2-14) to build
  against instead if this becomes worth doing later.

## EXJ-4-87 / EXJ-5-93 (rev. 01-19-2024) -- Wave 5 complete

- **Both sheets are detailing templates for a manufacturer-generic strip
  seal gland** -- the gland/extrusion cross-section itself is never
  drawn on either SCD (it's a proprietary product), so neither module
  attempts to model it; only the skewed joint line and the steel
  hardware that varies by structure type (support angles for steel
  stringers, plate spacing for box beams) are cataloged/drawn.
- **EXJ-4-87's a1-a4 formulas assume a uniform stringer top flange
  width** across all stringers (a single `top_flange_width_in` input);
  the real structure could have different flange widths at different
  stringer lines (e.g. near a haunch), which would need a per-stringer
  input — not implemented, since the sheet itself computes one length
  per stringer from one flange width.
- **EXJ-5-93's beam-gap stations assume uniform beam width** (`n_beams *
  beam_width_in` evenly spaced) — real adjacent box-beam layouts are
  built this way by design (edge-to-edge, no gap per PSBD-1-25), so this
  is a faithful simplification, not an assumption to revisit.
- **Not modeled** (both): the strip seal gland, retainer angles/plates,
  anchor bars/threaded rods, abutment backwall armor, stainless steel
  deflector (EXJ-3-82, box beam sheet's own cross-reference), end
  cross-frames (GSD-1-19, steel stringer sheet's own cross-reference).

This closes Wave 5 (bearings & expansion joints): RB-1-55, FB-1-82,
BD-1-11, EXJ-4-87, EXJ-5-93 all done.

## BD-1-11 (rev. 07-20-2018)

- **Catalog was already done, layout was the gap.** `BeveledLoadPlate`,
  `BEVELED_LOAD_PLATE`, and `load_plate_bevel` already existed in
  `odot/box_beam.py` from earlier box-beam work but had zero test
  coverage and no drawable geometry — same "catalog done, add the
  layout" pattern as RB-1-55. Added `layout_load_plate` there (not a new
  module) since BD-1-11's only content is this one plate detail, already
  living alongside PSBD-1-25's bearing pad catalog it's sized from.
- **Anchor-hole spacing (varies by 36 in vs. 48 in box width, PLAN view)
  not transcribed.** The dimension strings for the two box widths were
  not cleanly separable in the rendered sheet without a much closer
  read, and this is a hardware/layout detail, not the plate itself; left
  as "not modeled" rather than guessing.
- **Not modeled**: anchor rods/recesses, plate washers, the preformed
  bearing pad, permanent bearing markings, box-beam anchor hole spacing.

## FB-1-82 (rev. 07-19-2024)

- **E used as masonry plate thickness, H as pin clearance above it** --
  neither is explicitly labeled "plate thickness" on the sheet, but a
  literal read of H as "overall height" (mirroring RB-1-55's H) placed
  the pin partially below the base plate for several rows (checked and
  rejected during development, not shipped). E is the smallest tabulated
  dimension across every row, consistent with a base-plate thickness;
  the stack (base + pin + top plate, all self-consistent) is verified in
  `test_layout_stack_is_self_consistent`. Revisit if a clean render of
  the ELEVATIONS OF FIXED BEARINGS view clarifies H/E's true roles.
- **Anchor rod count and bearing-stiffener requirements are per-row
  booleans** (notes 1 and 2 on the sheet), not geometry -- cataloged on
  `FixedBearing` (`two_anchor_rods`, `stiffeners_required`) and reported,
  not drawn.
- **Not modeled**: anchor rods (1-1/4" dia x 1'-7", 2 or 4 depending on
  the row), welds, bearing seat reinforcing, 1/8" preformed bearing pad,
  the roadway-grade bevel (note: upper plate bevels to match grade over
  2%, keeping dimension C at plate center).

## RB-1-55 (rev. 07-19-2024) -- Wave 5 begins

- **Dimension-letter roles inferred from the 1955 sheet's four sub-views**
  (bolster front/side, rocker front/side) plus the existing catalog's own
  test comment ("H ... 13-3/8 in overall height"). Confirmed: H = overall
  height, T = base/masonry plate thickness (labeled "T MIN." on both
  elevations), A = top bearing width (also the input to the TOP BEARING
  DETAIL's r1/r2 formulas), B = base plate width in the front-view
  (span) direction, L = base plate length in the side-view (transverse)
  direction (shared by both bolster and rocker — same base footprint).
  C is used as the tapered body height for both bolster and rocker (no
  separate rocker-body-height letter exists on the sheet). D, F, G, K, M,
  R, Y are cataloged but not incorporated into the drawn solid — their
  precise roles (K = flange plate width; F = flange plate edge offset; G,
  M = secondary/inner dimensions visible in the drawing but not
  cross-verified against a clean render) are less certain and not needed
  for a proportioned visual check.
- **Rocker curved top uses a half-cylinder sweep** at radius r2 = A/2 +
  3/32" (the sheet's own "TOP PLATE" formula), not the true rocker
  contact geometry (which is a compound curve per the TOP BEARING DETAIL's
  r1-vs-r2 relationship, r1 being the tighter web curve). Good enough for
  a proportioned visual check, not for contact-stress verification.
- **Not modeled**: flange plate + fillet weld, anchor bolts (2 x 1-1/4"
  swedge bolts per bolster), 1-1/2" dowels (rocker), bearing seat
  reinforcing steel, 1/8" preformed bearing pad.

## A-1-20 (rev. 01-19-2024) -- Wave 4 complete

- **Strongest "not a standalone standard" disclaimer of any SCD so far.**
  Sheet 1's General note explicitly says to treat every dimension as a
  minimum and perform a complete design; do not reference this drawing in
  contract plans. Scope kept correspondingly light: only two literal
  formulas (`bearing_seat_dim_a_ft` = 2'-0"/cos(skew); the 8'-0" wingwall
  unsupported-length limit) plus section minimums (cover, bar spacing,
  bar size default) are cataloged; `layout_typical_abutment` takes every
  overall dimension as project-supplied and is explicitly framed (in its
  own docstring and the GH report) as a visual check, not a design
  artifact.
- **Backwall/footing width and wingwall flare angle assumed**, same
  posture as `capped_pile_abutment`: `BACKWALL_TOP_WIDTH_FT` (1'-8", from
  SECTION A-A "with piles") is used regardless of the with/without-piles
  variant shown on the sheet, and the wingwall flare is assumed 45 deg
  (not dimensioned on this sheet either). Revisit if a specific project's
  variant matters for the visual check.
- **Not modeled**: reinforcing (bars are #5 unless noted, max 1'-6"
  spacing — no bend/placement generator, unlike BCHW/CPA-1-08's
  `bend_shape()`), drainage (PGD/NPCPP/PCPP), PEJF joints, beam-seat bars,
  rock channel protection, and the with-piles vs. without-piles footing
  variants (one generic footing prism drawn for both).

This closes Wave 4 (slab bridges & substructure): SB-1-24, CS-1-24,
CPA-1-08, CPP-1-08, A-1-20 all done.

## CS-1-24 (rev. 01-16-2026)

- **Transcription methodology for the 779-entry table.** Given the size
  (33 spans x ~20 fields), the SLAB DATA table was transcribed by
  rendering the sheet at high DPI *and* independently extracting
  PyMuPDF's word-position text, then cross-checking every column
  (B/C/D/E-bar lengths, N/M-bar counts, U-bar counts — every field except
  A-bar, which the render alone made unambiguous) programmatically
  against the raw extracted strings. Zero mismatches on the second pass.
- **Caught and fixed two real bugs during that verification, not just
  documenting assumptions:**
  1. D-bar SIZE was initially inferred from slab thickness the same way
     A/B-bar size is (a threshold on `T`) — but D-bar steps 8->9 at span
     30 and 9->10 at span 38, which do **not** align with the A/B
     thickness thresholds (span 35, 45). Fixed by transcribing D-bar
     SIZE explicitly per row instead of deriving it.
  2. The E-bar tuple was built as (size, spacing, length) matching the
     sheet's own SIZE/SPA/LENGTH column order, but passed positionally
     into `LenBarSpec(spacing_in, size, length_ft)` — silently swapping
     size and spacing for every E-bar row. Fixed by swapping the tuple
     indices at the construction site with a comment explaining why.

  Both were caught by writing tests that check specific rows against the
  sheet rather than only checking a formula's output against itself —
  worth remembering as a general lesson for any future large-table SCD.
- **Interior span is a fixed ratio (1.25x end span), not tabulated
  separately** — the sheet's own "SPANS (FEET)" column bakes this in
  (e.g. "14 - 17.50 - 14"). Additional interior spans (same length as the
  middle span) may be added per the sheet's own General note without
  changing thickness or reinforcing — not modeled as a >3-span option
  here, but the same `CSSlabDesign` row would still apply.
- **A/B-bar size inferred from thickness, verified exact.** Unlike D-bar,
  A/B-bar size genuinely does correlate 1:1 with slab thickness
  (threshold at T=21.5 and T=26.5) across all 33 rows — verified, kept as
  a formula for readability rather than 33 explicit values.
- **Not modeled**: haunches / thickness transition over the piers
  (uniform T assumed across the whole 3-span length — the real elevation
  tapers), edge beam, bent A/B-bar ends, transverse N/M bars (cataloged
  by count only, not drawn), camber, and the companion abutment/pier
  (CPA-1-08/CPP-1-08).

## CPP-1-08 (rev. 07-21-2017)

- **Genuinely parametric, unlike BCHW/CPA-1-08.** The pier cap length is
  a literal sheet formula (`3'-0" + (slab width - 4'-4")/cos(skew)`), and
  cap width/end-radius are fixed constants regardless of span — only pile
  count/spacing are project-supplied (with a stated 7'-6" max spacing,
  same "not a table, just a limit" pattern as the abutment sheets).
- **Cap depth (2'-0") read off the HALF ELEVATION's overall dimension
  bracket**, not a separately labeled "T" or "D" callout on this sheet
  (unlike SB-1-24/HW-1.1's explicit depth columns) — treated as a fixed
  default (`CAP_DEPTH_FT`) but exposed as a `PierInput` override since
  it's the least certain of the fixed dimensions transcribed here.
- **Rebar bend shapes not fully modeled.** `pier_bar()` catalogs the
  P501-P504 leg dimensions and the `Q = T + 1'-4"` formula (T = the
  companion CS-1-24 slab thickness) but does not generate bend polylines
  the way `box_culvert_headwall.bend_shape()` /
  `capped_pile_abutment.bend_shape()` do — P501/P502/P503 are closed
  U-shapes and P504 is a diagonal corner bar with an inside radius;
  revisit if a drawn bar cage becomes valuable.
- **Not modeled**: reinforcing bar layout/placement, pile encasement
  (Item Special, for steel piles only), pile sections themselves, shear
  keys, and the slab edge beam (shared detail with SB-1-24).

## CPA-1-08 (rev. 01-19-2024)

- **Detailing template, like BCHW.** Only a handful of dimensions are
  fixed on this sheet (cap width 3'-0", the 1'-6"/1'-6" pile-zone split,
  max bar spacings); wingwall length, pile count/spacing, and footing
  depth are project design outputs, and the S501/S502/S503 bar lengths
  carry a literal ``base/COS(theta)`` skew term rather than a tabulated
  number. `layout_capped_pile_abutment` takes all of these as required
  inputs, same posture as `box_culvert_headwall`.
- **Wingwall flare angle assumed 45 deg.** Unlike HW-1.1 (which tabulates
  a skew-dependent flare split) or BCHW (which labels one angle
  explicitly), CPA-1-08's part-plan views don't dimension the wingwall
  flare angle at all — the "PART PLAN AT ABUTMENT" sheets show it
  schematically. Assumed a fixed 45 deg flare regardless of skew (a
  common default for this style of abutment wingwall). Revisit if a
  project plan shows a skew-dependent flare like HW-1.1's.
- **Cap/footing modeled as one prism** at the project-supplied
  `footing_depth_ft`; the true Section C-C/D-D profile (bridge-seat
  construction joint, battered wingwall-side face, separate cap vs.
  footing steps) is not distinguished.
- **layer group: `Substructure::CPA-1-08`.** This is a true NBIS
  substructure element (an abutment), unlike the SCD accessories that
  land in the civilpy-proposed `Culvert::`/`Site::` groups — it uses the
  C#-authoritative `Substructure` group directly (currently empty/reserved
  on the C# side; this is the first thing to populate it).
- **Not modeled**: reinforcing bar layout (only `rebar_mark()`/
  `bend_shape()` catalog the bar list, not a full placed schedule),
  drainage pipes, neoprene sheeting/PEJF joints, and the three
  railing-transition detail sheets (deflector parapet / three-tube /
  twin-tube).

## SB-1-24 (rev. 01-16-2026)

- **M/N-bar orientation assumed longitudinal.** The SLAB PLAN view only
  draws A-bars (bottom) and B-bars (top) as the many parallel longitudinal
  lines across the full plan; M-bars and N-bars only appear in the SLAB
  ELEVATION, dimensioned "@ 10\"/12\" SPA." along the span with "(2)
  ADDITIONAL N-BARS" called out near the abutment. Assumed M/N are
  additional longitudinal bars (modeled the same way as A/B, full-width,
  full-length) rather than transverse or abutment-zone-only bars. Revisit
  if a project bar list shows M/N confined to the end zones only.
- **Bottom/top cover assumed 2.5 in** (not explicitly re-dimensioned in
  the rendered crop used) to place the A/M (bottom) and B/N (top) bar
  elevations; the sheet's actual cover note should be confirmed against a
  full-resolution render of the SLAB ELEVATION detail bubble before using
  the bar elevations for anything beyond a visual check.
- **layer group: `Deck::SB-1-24`, not `Site::`/`Culvert::`.** Unlike the
  SCD plan-insert accessories (approach slabs, headwalls, barriers), the
  slab bridge SCD *is* the deck/superstructure itself for a slab-bridge
  structure type, so its GH component bakes to the `Deck::` group already
  defined by `Gdr.cs` rather than one of the two civilpy-proposed groups.
- **Not modeled**: the edge-beam taper solid (D/X detail — cataloged as
  data only), bent A/B-bar ends near the abutments, the U401/U402
  edge-beam lap bars, camber, and the abutment diaphragm (CPA-1-08,
  Wave 4's next item).

## Wave 3: bridge railings (SBR/BR/TST/DBR/TBR)

- **Already-done discovery.** `civilpy.structural.odot.bridge_railing`
  already cataloged full profile/reinforcement data for every Wave 3
  railing, and `civilpy.structural.rhino_barrier.build_barriers()` already
  draws any of them generically via `shape_family()` dispatch (concrete
  profile sweep + rebar cage, or steel curb + posts + rails) — there was no
  need for per-SCD standalone GH scripts like the other waves. Wave 3's
  work was auditing that existing pipeline against each drawing rather
  than building anew.
- **BR-2-15 bug found and fixed.** `shape_family()` matched the substring
  `"tube"` in BR-2-15's shape string ("combination (barrier + steel
  tube)") and misclassified it as a bare `"steel tube"` railing, so
  `barrier_profile()` drew only a 10 in curb instead of the actual 42 in
  tall x 12 in wide rectangular crashworthy concrete barrier (confirmed
  against SECTION A-A/B-B/C-C on the drawing) with a steel tube pedestrian
  rail on top. Fixed by adding a `"combination"` family (checked before
  the `"tube"` substring test) and a `rail_height_above_in` field (2'-0",
  from SECTION A-A's post height above the barrier) so the concrete body
  draws full height + gets its own rebar cage, and the steel rail mounts
  above that instead of replacing it. Also filled in the missing
  `base_width=12.0` (the sheet shows a straight rectangular section, not
  tapered — `top_width` was already correct at 12.0, `base_width` had
  been silently defaulting to the generic 18 in fallback).
- **DBR-2-73 / DBR-3-11 / TBR-1-11 use the generic "steel tube"
  approximation** (curb + HSS-tube posts/rails) rather than their true
  corrugated deep-beam / thrie-beam rail cross-sections — the same
  simplification already accepted for TST-1/TST-2. Revisit if a true
  corrugated-rail profile is ever wanted.
- **SBR-2-20 "back-to-back" median variant** is cataloged as its own
  `BridgeRailing` entry but is meant to be placed as two independent
  SBR-2 single-slope instances (mirrored, 6 in max gap apart), not drawn
  as one symmetric F-shape the way PCB's `side=0` placement works. Not
  verified against the drawing's exact median geometry; revisit if a
  true single symmetric back-to-back cross-section is needed.

## BCHW (rev. 01-21-2022)

- **This sheet has no dimension table.** Every geometric value (wall
  height, footing offsets a/b/c, foreslope/cutoff wall heights, footing
  width, box wall thickness, wingwall length, bar spacings) is drawn as
  `*` or a blank `@ _ c/c` for the project engineer to fill in, and the
  sheet explicitly instructs "INSERT ODOT BOX CULVERT REINFORCING DESIGN
  DESIGN HERE IF SPAN > 12'." — the box culvert's own reinforcing design
  is out of scope by the sheet's own admission, not an omission on
  civilpy's part. `layout_wingwall` therefore takes every dimension as a
  required input with no catalog/defaults, unlike every other SCD module.
- **Rebar bend-shape geometry (TYPE-1..TYPE-8) is a best-effort
  transcription of the legend art**, not a measured dimension. The bar
  list's actual leg lengths (A/B/C/D) are likewise always project-
  supplied. Types 2/3/4/8 involve a diagonal or angled segment whose
  exact vertex ordering was read off the rendered legend rather than
  extracted text; revisit against a project bar list if a bend looks
  wrong in Rhino.
- **ASTM C1577 precast box section catalog (span x rise) is a separate,
  not-yet-encoded sheet** — BCHW is the cast-in-place wingwall/foreslope-
  wall wrap-around only, referenced from (but not containing) the
  precast box culvert details ("FOR PRECAST BOX CULVERT DETAILS, SEE
  SHEET xx/xx").
- **Not modeled**: rebar placement (only the bend-shape generator is
  provided, not a full bar list/schedule), weepholes, porous backfill,
  PEJF, waterproofing (Type 2/3, payment-only), and the wingwall
  corner-configuration "SUBSET" sheets 3-8 (skew-dependent corner
  return details) — the drawable subset is one flared wingwall +
  foreslope wall + footing.

## HW-1.1 (rev. 07-18-2025)

- **Type A/B split pinned to the sheet's own 10 deg cutoff, not the
  table's halfway point.** The dimension/quantity table only tabulates
  quantities at skew ~= 0/15/30/45 deg, but the sheet separately states
  Type A (symmetric wingwall) applies at skew <= 10 deg and Type B
  (asymmetric) above it. Naive nearest-neighbor rounding would put an
  11 deg skew's *quantities* at bucket 15 while an 9 deg skew's would stay
  at bucket 0 — both correct — but a naive halfway split (7.5 deg) would
  put a 9 deg skew (Type A per the sheet) at bucket 15's asymmetric L1/h1
  data. `nearest_skew_bucket` special-cases the 0/15 boundary at 10 deg
  (matching the Type A/B cutoff exactly) and uses plain halfway points
  (22.5, 37.5) for the 15/30/45 buckets, which the sheet does not
  otherwise constrain.
- **Wingwall flare angle under skew is an assumption.** The plan view
  labels one wingwall's flare as "45 - theta/2" off the culvert
  centerline; the other wingwall's angle is not labeled. Assumed
  (45 + theta/2) for the L2/h2 wingwall by symmetry/complement — a common
  convention for these ODOT skewed flared-wingwall details — so the two
  wingwalls' flares sum to 90 deg regardless of skew. Revisit if a project
  plan shows a different obtuse-side angle.
- **No explicit headwall width (W) is tabulated** (unlike HW-2.1/2.2).
  The drawable center face uses the pipe diameter D directly as its width,
  with the wingwalls springing from its edges — the table's `a`/`b`/`c`
  corner-offset dimensions and the true battered wingwall cross-section
  (HALF SECTION A-A) are cataloged only, not incorporated into the width.
- **Not modeled** (reported by the component): wingwall batter/thickness
  (`a_ft`/`b_ft`/`c_ft`/`ts_ft` cataloged only), the footing, reinforcing
  bar layout, weepholes, porous backfill, chamfers, pipe-arch geometry,
  and the rigid-vs-corrugated-pipe end treatment details (sheet 2).

## HW-2.1 (rev. 07-15-2022) / HW-2.2 (rev. 07-20-2018)

- **Drawable subset = end treatment "A", circular pipe.** Only the
  rectangular cast-in-place headwall of the circular tables is generated:
  width W, height H, front face vertical, back face battered from 12 in
  (top, per the profile view) to the tabulated T at the base. The pipe-
  arch tables, the elliptical table (HW-2.2), the anchor bolt/cable/
  eyebolt options, and the 6 in inlet headwall extension are catalog/
  not-drawn.
- **Pipe elevation & the A/B boundary.** The flow line is taken at the
  wall base (z = 0), so the pipe centre sits D/2 above it and the cover
  over the crown is H − D. On the drawing this reaches its stated 6 in
  minimum exactly at D = 48 in (H = 54 in) — strong confirmation of the
  datum. Sizes with cover < 6 in are end treatment "B" (the wall top is
  bevel-cut by 2:1 slopes tangent to the pipe, per the sheet note "2:1
  slopes … tangent to pipe"); `layout_headwall` raises `ValueError` for
  them rather than emit a wrong top. Modeled range: HW-2.1 D = 12–48 in
  (12 sizes), HW-2.2 D = 12–60 in (13 sizes).
- **Battered back, not a prism.** The wall is swept from a Y-Z side
  profile (front vertical at y = 0; back at y = −12 in on top, y = −T at
  the base), so the solid volume tapers with height. The tabulated
  `concrete_cy` remains the controlling quantity; the swept solid is for
  display and is not reconciled to it (the battered form is close but the
  drawing's exact base fillet / footing below the flow line is not drawn).

## AS-2-15 (rev. 01-20-2023)

- **Only the sleeper slab is modeled.** AS-2-15 is 14 sheets of
  installation configurations (Types A/B/C, flexible/rigid pavement,
  MSE vs. turnback wingwalls). The parametric geometry is the reinforced
  concrete sleeper slab (Type A/C); the fourteen configurations are
  cataloged as data (`INSTALLATION_INDEX`). Type B has no sleeper slab
  (reinforced joint mesh, measured by SY) and raises `ValueError`.
- **Skew convention (Section A-A + Note 9).** The 8 ft sleeper width
  (4'-0" + 4'-0" in Section A-A) is the TRUE width perpendicular to the
  skewed centerline, so the slab's along-roadway (X) extent is 8/cos θ
  and the plan outline is a parallelogram sheared by y·tan θ. SS501 runs
  parallel to the skewed centerline, length A = (W − 0.5')/cos θ. SS502
  is placed **parallel to CL roadway** (Note 9), so its plan run in X
  equals the tabulated bar length B = 7.5'/cos θ; its spacing is measured
  perpendicular to CL roadway. (An earlier draft's test asserted a true
  4.0 ft half-width and a 7.5 ft SS502 plan run — both corrected to the
  sec θ forms above to match the bending table.)
- **Sleeper measured length** is W/cos θ (linear foot along the skew,
  per the measurement note), independent of the bar cover deductions.
- **Not modeled** (reported by the component): the 25 ft flexible
  pavement transition and its T2→T3 thickness tapers, bond breaker,
  aggregate-drain outlets (DM-4.1) and pipe outlet details (DM-1.1/1.2),
  the MSE-wall / turnback-wingwall variations, and the Type B reinforced
  joint mesh.

## DS-1-92 (rev. 07-15-22)

- **Sheet thickness for display.** The sheet specifies "minimum 22 gage"
  ASTM A167 Type 304 with no decimal thickness. Used 0.031 in (nominal
  22-gage stainless sheet) purely for solid display
  (`GAGE_THICKNESS_IN`); it is not an engineering value.
- **Root depth below deck surface.** Views A-A/C-C dimension 2-1/2 in
  (DBR-2-73, written "DRB-2-73" on the sheet — treated as a typo) and
  2 in (TST-1-99); view D-D shows 2 in for TST-2-21. Encoded those as the
  bend-line depth. The asphalt-overlay variants (views B-B/E-E, 3 in min
  overlay) shift the strip relative to the wearing surface — not encoded
  separately; the component takes the concrete-deck-surface datum.
- **Upper/lower strip separation.** The views draw the upper strip's
  embedded plate immediately above the lower strip's (they overlap in
  view G-G); the exact vertical gap between the two roots is not
  dimensioned legibly, so both strips are modeled from a common root
  line. Revisit if the ~1-3/4 in stagger dimensioned in views A-A/B-B
  should separate them vertically.
- **Perforations and field notching** are cataloged (`hole_centers_in`)
  but not cut from the display solids; box-beam spike fastening is data
  only.

## PCB-91 (rev. 07-17-2020)

- **Lifting-slot height.** Section B-B shows the drainage/lifting slot
  14 in wide (base 5" | 1'-2" | 5") with a 7 in vertical dimension at the
  slot; view A-A carries an unexplained 2 in dimension near the bottom
  centerline. Encoded the slot as 14 in wide x 7 in high x 4'-0" long
  (elevation: 3' | 4' | 3' on a 10 ft segment). Revisit if the slot is
  actually 2 in high with the 7 in belonging to something else.
- **Anchor-hole transverse position.** Detail C dimensions the anchor
  2" + 5" from the barrier face; the plan shows a row along each face.
  The GH component places hole markers 5 in from each base edge
  (y = +/-7 in). The sheet leaves the anchor count per segment to the
  project plans, so the component simply marks every tabulated station.
- **Revision date.** The revision block lists 1999/2002/2013 entries but
  the drawing file is `PCB-91_07-17-20.dgn`; cited 07-17-2020 (matching
  the feasibility review and the `bridge_railing` catalog).
- **Hinge-loop hardware** (loop projections, 18/15/12/8.5 in loop
  elevations in the hinged-connection detail) is cataloged as constants
  only where legible and is not drawn; the joint is represented by its
  gap.

## RM-4.3 / RM-4.5 / RM-4.8 / RM-4.9 (roadway single-slope barrier family)

- **Feasibility doc assumed "identical profile-sweep engine" as the SBR
  bridge parapets; mostly true, but the freestanding-symmetric case was
  actually broken.** `rhino_barrier.barrier_profile`'s single-slope
  fallback computed `s = side or 1`, so a `side=0` (freestanding) call —
  which a roadway median/at-grade barrier is, having no deck edge to back
  against — fell through to `s=1` and drew a one-sided trapezoid offset
  entirely to +Y instead of a symmetric section. Fixed by adding an
  explicit `fam == "single slope" and side == 0` branch that returns a
  centerline-symmetric trapezoid. This also silently fixes
  `SBR-2 (57 in median)`/`(back-to-back)` if ever placed via
  `build_barriers(..., placements="median")`, which nobody had exercised
  before (`test_rhino_barrier.py::test_single_slope_freestanding_profile_is_symmetric`
  added as a regression guard).
- **Types C/C1 (RM-4.3, sheet 2) are not fully dimensioned — they are
  project-variable-height siblings of B/B1.** The sheet shows a "Varies,
  24 in max. See Plans for dimensions." extension added above the fixed
  B/B1 body, giving overall height ranges of 42-66 in (C) / 57-81 in
  (C1) with no formula for how the extension's own taper is dimensioned.
  Cataloged C/C1 with the same height/top/base as their B/B1 base body
  (not the full variable range) and documented the extension as
  project-defined in `notes` — consistent with the "detailing template,
  don't invent a formula" precedent from BCHW/CPA-1-08/A-1-20.
- **Type D's (RM-4.5) concrete face was cross-checked against its slope,
  not read directly off a base-width dimension line.** The sheet
  dimensions the compacted-soil foundation detail (20 in min shoulder,
  20:1 batter, 2:1 max embankment, 6 in toe) more prominently than the
  barrier body itself, which shares Type B's 42 in / 12 in top / 5.25:1
  slope. Computed `base = top + 2*(height/slope) = 12 + 2*(42/5.25) =
  28 in`, matching Type B exactly (expected, since Type D differs from
  Type B only in foundation, not barrier cross-section).
- **Type N (RM-4.8) base width (42.875 in) likewise derived from
  height/slope** (`12 + 2*(81/5.25)`) rather than read off a single
  dimension line, since the sheet dimensions the top split
  (1'-3-7/16" + 1'-0" + 1'-3-7/16" = 42.875 in) across three segments at
  the *top* callout row, not a single base-width figure; confirmed the
  three segments sum to the same value the slope formula predicts.
- **Type E (RM-4.9) concrete face envelope is genuinely not on the
  sheet — not just hard to read.** RM-4.9 dimensions the rebar cage (Bar
  S/Bar U, #4/#5) and the moment-slab foundation in detail but never
  calls out the barrier's own top/base width; the "14 1/2", "7 1/2""
  etc. callouts at the top of the section view are rebar/cover
  dimensions, not the concrete edge. Rather than back-fill a guessed
  profile, `RoadwayBarrier("Type E").top_width`/`.base_width` are left
  `None` and `layout_roadway_barrier` raises `ValueError` if asked to
  build it — same "guarded lookup, never silently invent" discipline
  used for A-1-20 and CPA-1-08's Type 6 bend. Revisit if a cleaner sheet
  render turns up an explicit face dimension.
- **Joint spacing differs by sheet and was transcribed per-sheet, not
  assumed uniform across the family:** RM-4.3/RM-4.5 state 20 ft max
  unsealed-joint spacing, RM-4.8 states 10 ft, RM-4.9 states a 20 ft
  min/100 ft max *expansion*-joint (not contraction-joint) spacing —
  cataloged as `joint_spacing_ft` per entry rather than a shared module
  constant.

## BP-5.1 (concrete curbs and combined curb & gutter)

- **19 sheet-labeled curb types consolidated into 13 catalog entries.**
  Several labels differ only by the pavement/base course the same curb
  face sits on, not by the face geometry itself: Types 2/2-A/2-B,
  3/3-A/3-B, and 4/4-A/4-B each share one profile across their lettered
  substrate variants. Consolidated via a `CurbType.sheet_labels: tuple`
  field and a `CURB_TYPES` dict mapping every individual sheet name to
  the same shared object (`curb_type("Type 2-A") is curb_type("Type
  2-B")`), rather than duplicating near-identical dataclass instances —
  every sheet label still resolves, and `test_all_sheet_labels_present`
  guards that the full 19-name set stays resolvable if the catalog is
  ever refactored.
- **Rolled/mountable curbs (Type 3/3-A/3-B) and Type 11's compound-curve
  face are approximated as straight-line chamfers, not the true arcs.**
  Type 3 rounds flush with the pavement over a 10 in radius arc; Type
  11's face is a compound curve (18 in toe radius plus an X=4-3/4 in /
  Y=4-5/8 in offset break). Neither is dimensioned in a way that maps
  cleanly onto the module's 4-point trapezoid representation, so both
  are drawn as straight ramps/segmented trapezoids instead of true
  arcs — documented in both the module docstring and each entry's
  `notes` field, consistent with the "schematic profile, sheet remains
  controlling" precedent used for bridge-railing toe kicks.
- **Types 9, 10, and 11 have no fixed height** — the sheet's general
  note states the gutter-plate thickness `T` "shall be 9 in unless
  otherwise shown on the plans," and these three types key their curb
  height directly to `T`. Cataloged `height=None` for these three and
  added `DEFAULT_GUTTER_PLATE_T_IN = 9.0` plus a `curb_height_in(label,
  gutter_plate_t_in=None)` resolver that defaults to 9 in but accepts a
  project override — the same variable-dimension pattern used for
  `A-1-20` and `CPA-1-08`'s Type 6 bend.
- **Type 4's back width and Type 3's exact back-of-curb tie-in are
  project-specified ("as shown on Typical Sections in Plans")**, not
  given as a fixed sheet dimension; both are cataloged with the
  concrete-face-only trapezoid and documented as not modeling the
  variable tie-in width, rather than guessing a value.

## PSID-1-13 extension + Wave 8/9 railings (2026-07-12)

- **PSID-1-13 permissible strand grids were extracted from the PDF's
  vector marks, not read visually.** Each `+` mark is a distinctive
  drawing signature (a 7.5 pt horizontal+vertical stroked line pair);
  filled 4.2 pt circles turned out to be *rebar* section cuts, not
  strands. The per-row extraction reconciles exactly with each
  diagram's stated permissible count (26/40/52/62), which is the
  validation that made the transcription trustworthy.
- **Modified AASHTO Type 4 top-flange widths corrected.** The earlier
  catalog carried Type 4's 20 in flange for all three Modified
  sections with a "not re-verified" caveat; sheet 1's own dimension
  strings (3'-0" / 4'-0") and the shipping-strand offsets (+/-15.5 in
  and +/-21.5 in — impossible inside a 20 in flange) prove the wide
  thin flange: 36 in (60/66) and 48 in (72). `test_modified_type4_*`
  now locks the corrected values.
- **`ps_i_beam_profile` outlines are straight-line.** AASHTO 2/3/4
  close on the published areas to ~1 in^2; the Modified Type 4 / WF
  top-flange edge split between vertical edge and underside slope is
  read to the nearest inch, so those polygons run a few percent over
  the published areas — quantities must use the published area/weight
  (the emit does).
- **The strand designer models debonding, not draping.** Fill order is
  bottom-row-up / outside-in; when the fully-bonded end overstresses
  at transfer, outermost bottom-row strands are debonded in pairs up
  to the 5.9.4.3.3 cap (45 % default, the 8th-Edition limit; pass
  0.25 for pre-2018 designs). The WF web locations the sheet marks
  "must be draped if utilized" are simply never used. Staggered debond
  lengths and hold-down geometry are not modeled.
- **RM-4.4 is not what the remaining-work table guessed.** The sheet
  is *plan-width* transitions (40 ft tapers wrapping sign-support /
  light-tower foundations and pier columns) rather than profile-to-
  profile lofts; `layout_barrier_transition` returns width-vs-station
  accordingly.
- **RM-4.6 Type D's intermediate sections are approximated.** The
  sheet's M-M section shows a one-side-sloped 30 in-base body that
  doesn't match RM-4.5's symmetric catalog profile exactly; the layout
  lofts from the RM-4.5 profile to the 20 in vertical-faced end and
  the 4:1 plan end flare is note-only, not geometry.
- **RM-5.2 heights are derived, not dimensioned as one number.** The
  42 in `RAILING_HEIGHT_IN` composes the 3 ft post reveal plus the
  top-rail zone; the drawing dimensions the pieces (1'-0" face-rail
  moduli, 6 in bottom gap) rather than an overall height.
- **MGS-3.x layouts keep each sheet's own stationing direction**
  (`origin` field): Type 1 from the parapet end, TST-2 from the MGS
  end, Type 2 from the connector — flipping any of them to a common
  origin invited transcription errors for no modeling benefit.
