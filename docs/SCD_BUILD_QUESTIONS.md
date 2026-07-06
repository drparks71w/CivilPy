# SCD build questions & assumptions

Running record of judgment calls made while building the SCD components.
Format: SCD — question — what was assumed — what to revisit if wrong.

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
