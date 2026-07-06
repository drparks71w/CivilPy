# SCD build questions & assumptions

Running record of judgment calls made while building the SCD components.
Format: SCD — question — what was assumed — what to revisit if wrong.

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
