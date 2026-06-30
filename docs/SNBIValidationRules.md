# SNBI Validation — FHWA gap closure roadmap

Tracks bringing `civilpy.state.ohio.snbi` into agreement with FHWA's own SNBI
processing report. Baseline = FHWA `FinalProcessingReport_OH_JSON_…` (report
date **5/6/2026**), *Validation Summary* sheet: **68 distinct items / 8,301
findings**, typed Safety / Error / Flag.

## Why we currently disagree

A 6-30-2026 `validate_snbi` run (post-0.3.1) agrees with FHWA on only **~8 of 68
items (~12%)**. Two root causes, in order of impact:

1. **Requiredness.** The model makes nearly every item `Optional`, and every
   helper (`_require_in`, `_require_code`, …) returns early on `None`. So
   FHWA's "*X is null or not valid*" Errors — the majority of findings — never
   raise. The module docstring already states the *intent* that
   "must be reported for all bridges" items are required; the implementation
   just didn't carry it through. Closing this is the single biggest lever.
2. **Dead enum tables.** `_SNBI_CODES` / `_PATTERN_CODES` (added on this branch)
   are defined but **never wired to a field**, so coded-value checks for ~20
   items don't run. Wiring them is safe and is this branch's stated purpose.

> Headline caveat: the single largest line (BIR02, 2085) is a **Flag** advisory
> ("don't report Fatigue Details on non-steel bridges"), not an Error — low
> priority despite the count.

## Action categories

Legend: ☐ todo · ☑ done · `freq` = FHWA finding count · `T` = Safety/Error/Flag

### A. Wire existing enum / pattern tables — ✅ DONE (this branch)
Catches *invalid present* values. Tables already existed on this branch but
were never wired to a field; now connected via `_require_code` /
`_require_pattern_code` / `_require_multi_code`. (Still skips `None` — null
flagging is section B.) Fixtures using lenient shorthand (`BF01="H"`,
`BSP01="M"`, `BCL01="1"`, `BPS01="A"`, `BSB01="A1"`) updated to real codes.

- ☑ BSP12 (390, E) Deck Reinforcing Protective System
- ☑ BSP09 (58, E)  Deck Material and Type
- ☑ BSP06 (17, E)  Span Type
- ☑ BSP04 (12, E)  Span Material
- ☑ BRT03 (71, E)  Route Direction
- ☑ BAP05 (111, E) Seismic Vulnerability
- ☑ BAP03 (22, E)  Scour Vulnerability
- ☑ BLR04 (13, E)  Load Rating Method
- ☑ BF02 (7, E)    Feature Location
- ☑ BIR01 (159, E) NSTM Inspection Required — added to Y/N set
- ☑ BIR03 (65, E)  Underwater Inspection Required — added to Y/N set
- ☑ BCL03 (28, E)  Federal/Tribal Land Access — `_require_multi_code`
- ☑ (no FHWA hits, wired for completeness) BSP07/08/10/11/13, BSB03-07,
  BG12, BH01, BRR01, BLR01/02, BIE01, BEP03, BPS01, BCL01/02, and patterns
  BF01 / BSP01 / BSB01

> ⚠️ Verification owed: a fresh `validate_snbi` run + re-compare vs FHWA, to
> confirm wiring closes the targeted "not valid" findings **without** adding
> false positives on items FHWA passed (e.g. if `_AGENCY`/span tables are
> narrower than FHWA's). Couldn't run here (needs warehouse DB access).

### B. Make required ("must be reported for all bridges" → flag null)
**Decision: Option A** — make unconditional items required in the base model.

**B1 — Unconditional, Bridge-level — ✅ DONE** (flipped Optional→required):
- ☑ BG06 (1232, E) Curb-to-Curb width — required **and** `> 0`
- ☑ BG07 (63) / BG08 (62) curb/sidewalk width
- ☑ BG03 (5, `>0`) Max Span Length
- ☑ BG10 (4) Median · BG11 (8) Skew · BG14 (19) Sidehill
- ☑ BAP01 (71) · BAP02 (63) · BAP03 (22) · BAP05 (111) appraisal
- ☑ BCL03 (28) Land Access · BCL04 (9) Historic · BCL05 (33) Toll
- ☑ BIR01 (159) NSTM req'd · BIR03 (65) Underwater req'd

**B2 — Conditional (need model_validators, NOT plain required) — ☐ TODO.**
These live on child models / apply only in context; forcing them required
would reject inapplicable records (e.g. a waterway feature has no `BH*`):
- ☐ BH06 (147) LRS Route ID · BH09 (98) AADT · BH11 (95) AADT year ·
  BH13 (95) min vert clearance · BH17 (122) bypass detour — **highway
  features only** (BF01 starts "H") → conditional on `Feature`
- ☐ BRT02 (83) Route Number — required per `Route`
- ☐ BSP02 (67) Number of Spans — required per `SpanSet`
- ☐ BLR05 (26) / BLR06 (26) rating factors — when load-rated
- ☐ BF03 (80) Feature Name · BE03 (3) Element total · BIE05 (1) interval ·
  BL03 (2) Place · BL07 (25) border (conditional)

### C. Numeric format (one decimal place)
- ☐ BG15 (358, E) Irregular Deck Area
- ☐ BH16 (346, E) Highway Maximum Usable Surface Width

### D. Cross-field / conditional rules
- ☐ BSP01 (211, E)  Culvert-definition consistency (coding vs. SNBI culvert def)
- ☐ BEP04 (197, E)  Do not report when BEP03 ∈ {C,S,L,V}
- ☐ BC09 (86, E)     Channel rating: N when no waterway feature, else 0-9
- ☐ BG05 (21, E)     Out-to-out must exceed curb-to-curb (unless sidehill)
- ☐ BW03 (50, F)     Work-performed code consistency
- ☐ BH18 (29, E)     Crossing bridge number ≠ BID01
- ☐ BSP03 (8)        Beam-line count vs. span type P01/P02
- ☐ BN02/04/06/03    Navigation sub-items (conditional on waterway + movable)
- ☐ BW02 (11, F)     Year work performed ≥ year built
- ☐ BE01 (10, F) · BC02/03/04 flags (no super/sub/culvert present)
- ☐ Border-bridge "do not report" flags (BH01/04/05/08/10/12/13/16/17, low)

### E. New enum table needed
- ☐ BH02 (899, E) Urban Code — 5-digit Census UACE or 99999 (no table yet)

### F. Done already (FHWA-calculated, must-not-report)
- ☑ BG16, BC12, BC13, BIE06

## Open design decision (blocks section B)
How to enforce "must report for all bridges":
- **A — make fields required in the base model** (matches FHWA; rejects any
  submission missing them; changes the library's lenient contract).
- **B — add a separate "completeness" pass / strict flag** that flags nulls
  without making the base model reject (preserves generic use).
- **C — enum-only now**, defer requiredness.
