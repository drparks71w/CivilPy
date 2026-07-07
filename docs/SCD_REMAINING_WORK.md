# SCD program — remaining work

Snapshot at commit `88e961b` (2026-07-07), pushed to `origin/development`.
This is a checkpoint for validation: everything listed as done below has
a green `pytest tests/structural` run (1503 passed, 6 skipped as of this
commit) and a docstring citing its source SCD + revision date. Everything
listed below as *remaining* has not been started.

See `docs/ODOT_SCD_Feasibility.md` for the full rating rationale of every
SCD (done and not-done), `docs/SCD_BUILD_LOG.md` for the one-line-per-SCD
module/test index, and `docs/SCD_BUILD_QUESTIONS.md` for the judgment
calls behind each done item (unit conventions, what's approximated vs.
exact, refusals where a sheet doesn't dimension something).

## Done (Waves 1-8, partial)

Waves 1-7 are fully closed. Wave 8 is partially closed:

- **Done**: RM-4.3, RM-4.5, RM-4.8 (`odot.roadway_barrier`, Types B/B1/C/C1/D/N),
  RM-4.9 (Type E, catalog only — layout refuses, concrete face undimensioned
  on the sheet), RM-4.2 + RM-4.1 (`odot.roadway_portable_barrier`, 32 in
  and 50 in portable barriers + the 50"->32" transition), BP-5.1
  (`odot.concrete_curb`, 13 catalog entries / 19 sheet labels).
- **Remaining in Wave 8** (below).

## Remaining: Wave 8 (roadway concrete barriers & curbs)

| SCD | Title | Rating | Scope note |
|---|---|---|---|
| RM-2.1 | Concrete Steps | 2 | Small parametric stair — new module, full build expected. |
| RM-5.2 | Bikeway Railing | 2 | Post-and-rail on structures; pairs with BR-2-15 (Wave 3) — check whether it can reuse `bridge_railing`/`rhino_barrier` or needs its own family. |
| RM-4.6 | Concrete Barrier End Sections | 2 | Lofted end tapers of the RM-4.x profiles already in `roadway_barrier.py` — extends that module rather than starting fresh. |
| RM-4.4 | Single Slope Barrier Transitions | 3 | Lofts between different RM-4.x barrier profiles (e.g. Type B <-> Type D) — geometry-only extension of the same engine. |
| RM-4.7 | Thrie-Beam Transition for PCB | 3 | Steel transition hardware bridging the barrier engine to guardrail steel — likely a lighter, catalog-heavy build (rated 3, proportional effort). |

## Remaining: Wave 9 (guardrail systems, extends `odot.guardrail`)

`odot.guardrail` already exists with some cataloged data (see current
module before starting — MGS-3.x may already have partial coverage).

| SCD | Title | Rating |
|---|---|---|
| MGS-3.1 | Bridge Terminal Assembly, Type 1 | 2 |
| MGS-3.2 | Bridge Terminal Assembly, Type 2 | 2 |
| MGS-3.3 | Bridge Terminal Assembly, Type TST-2 | 2 |
| MGS-2.1 | Midwest Guardrail System, standard run | 2 |
| MGS-2.2 | MGS with Rub Rail | 3 |
| MGS-2.3 | Long Span Guardrail | 3 |
| MGS-2.4 | Socketed Weak Post on Headwall | 3 |
| MGS-4.1 | Type A Anchor Assembly | 3 |
| MGS-4.2 | Type T Anchor Assembly | 3 |
| MGS-4.3 | Guardrail Transitions | 3 |
| MGS-6.1 | Guardrail at Bridges | 3 |
| MGS-4.5 | Buried-in-Backslope Terminal | 4 |
| MGS-6.2 | MGS at Piers | 4 |
| MGS-6.3 | Thrie Beam Bullnose | 4 |
| F-3.1 | Fence Details at Bridges | 5 |

Suggested order: MGS-3.1/3.2/3.3 and MGS-2.1 first (rated 2, standalone
value), then the rated-3 run/transition variants, then the rated 4-5
items get catalog/notes-only treatment per the established
proportional-effort convention.

## Remaining: Wave 10 (drainage structures)

| SCD | Title | Rating |
|---|---|---|
| I-3B / I-3C / I-3D / I-3N | Inlet No. 3 for Single Slope Barrier B/B1, C/C1, D, N | 2 |
| I-4B | Inlet No. 4 for Single Slope Barrier B/B1 | 2 |
| CB-3 / CB-3A | Catch Basin No. 3 / 3A | 2 |
| CB-2 series | Catch Basins 2-2A...2-6 | 2 |
| DM-2.1 | Paved Gutters | 2 |
| CB-4/4A/5/5A/6/8/8A/9 | Catch Basins | 3 |
| MH-2 / MH-4 | Manholes No. 2 / 4 | 3 |
| MH-1 / MH-3 / MH-5 | Manholes No. 1 / 3 / 5 | 3 |
| I-2 / I-2A | Median / Pavement Inlet No. 2 | 3 |
| CB-1 / CB-7 | Side Ditch Inlets / CB No. 7 | 3 |

The I-3x/I-4B inlets are formed INTO the RM-4.x barrier profiles — build
on `roadway_barrier.py`, likely after RM-4.6/RM-4.4 (Wave 8) since those
touch the same profile geometry. DM-2.1 is a trivial profile sweep, good
first item. The CB/MH families each want one parametric module per
family with per-number data tables (same pattern as `headwall.py`'s
HW-2.1/HW-2.2 or `box_beam.py`'s section tables).

## Other open items (not tied to a specific wave)

- `docs/CIVILPY_SCOPE.md`'s SCD-program status snapshot has not been
  updated since early waves — flagged as pending in an earlier session,
  still outstanding. Update once Wave 8 is fully closed (or now, if
  useful for validation context).
- The "new jersey" shape family in `rhino_barrier.py::barrier_profile`
  has the same latent `s = side or 1` bug as the single-slope family did
  before the RM-4.x fix (freestanding `side=0` calls would draw an
  asymmetric one-sided trapezoid instead of a symmetric one). Not fixed
  because no current catalog entry exercises `side=0` on a New Jersey
  shape — worth a defensive fix or at least a guard if a freestanding NJ
  barrier is cataloged later (e.g. if RM-4.6/RM-4.4 ever need one).
- No PSIDD (PS I-Beam design-data) companion sheet is archived yet for
  PSID-1-13 (Wave 6) — noted in that SCD's feasibility row, not blocking.

## Validation notes

- Full suite: `python -m pytest tests/structural -q` — 1503 passed, 6
  skipped at this checkpoint (skips are pre-existing, gated on
  `rhino3dm`/other optional imports, not new).
- Every completed module's docstring cites its SCD number + revision
  date; cross-check against the live sheet in `res/odot_scds/` (git-
  ignored — re-download from the ODOT SCD index if missing) rather than
  trusting the transcription blind, especially anywhere
  `SCD_BUILD_QUESTIONS.md` notes an approximation or a derived (not
  directly read) dimension.
- `git log origin/development..HEAD` should be empty as of this
  checkpoint (commit `88e961b` pushed) — if you find local commits ahead
  again later, that's new work done after this doc was written, not a
  push that was missed.
