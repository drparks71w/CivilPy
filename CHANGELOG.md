# Changelog

All notable changes to CivilPy are documented here. Generated from git history.
Versions follow [Semantic Versioning](https://semver.org/) (major.minor.patch).

---

## [Unreleased]

## [0.4.0] - 2026-07-12

The BrIM "source of truth" release: the Rhino model now carries faithful
geometry **and** a complete per-object BIM attribute record (pay items,
SCD keys, materials) for three full bridge types — steel girder,
adjacent box beam, and prestressed I-beam — plus the substructure, all
regenerable into MIDAS models and quantity estimates. See
`docs/BrIM_Work_Plan.md` for the phase-by-phase record.

- **BrIM emit architecture (`structural.bim` + `structural.rhino_bim`).**
  Typed per-component tag builders (`bim.*` / `pay.*` / `mat.*`), a
  seeded ODOT pay-item catalog, and the transport-neutral
  `girder_bridge_emit` → `EmitObject` record drawn by the pure-Rhino
  `draw_bim_emit.py` driver. Deck as a crowned closed solid with BDM
  Figure 309-4 overhangs, vertical-sided haunches (BDM 309.3.5), girder
  k-fillets, shear studs, crown-following deck rebar mats, and the
  SBR-1-20 parapet with its true bar cage. `read_bim_tags` /
  `read_bim_quantities` / `pay_item_quantities` round-trip every tagged
  object back into a pay-item rollup.

- **Substructure (work-plan Phase 4/4v).** `substructure_layout` places
  skew-aligned units under the layout with stepped beam seats that land
  the bearing pads exactly; emit dimensions come from the executed
  design objects (`PierCapDesign` STM ties drive the cap steel). Five
  substructure types, mixable per support line via typed specs:
  multi-column bent, capped-pile bent, hammerhead (tapered cap,
  top-chord tie steel), seat / semi-integral / integral abutments (the
  integral type skips the bearing stack entirely). Cap STM results
  overlay in place; all concrete/pile/reinforcing quantities roll into
  the 511/507/509 items.

- **Adjacent box beams (Phase 5).** `box_beam_pipeline` re-derives the
  PSBDD-1-25 standard designs' governing checks (adjacent-box LLDF,
  elastic shortening + lump-sum losses, transfer/service stresses,
  Strength I flexure) and builds the MIDAS line-beam hub with tie
  elements; `rhino_box_bim` emits hollow members, strand rows, tie
  rods, diaphragms, pads, and the composite topping. Walkthrough
  notebook: design line → checks → tagged emit → MIDAS model.

- **Prestressed I-beams (Phase 6, PSID-1-13).** The catalog now carries
  all 13 sections — the seven WF36-49..WF72-49 wide-flange sections
  were added, and the Modified AASHTO Type 4 top-flange widths were
  **corrected** from Type 4's 20 in to the sheet's wide thin flanges
  (36 in for the 60/66 in beams, 48 in for the 72 in) — plus the
  permissible strand grids (vector-extracted from the drawing; row
  totals reconcile with the stated 26/40/52/62 counts), draped-required
  and shipping-strand locations, true tapered outlines, and the sheet
  10 design constants. With no PSIDD companion sheet, the new
  `ps_i_beam_pipeline` *designs* the strand pattern: smallest even
  straight count passing Service III + Strength I on the composite
  section, with end debonding designed in pairs (5.9.4.3.3, 45 % cap)
  when transfer overstresses the beam end. MIDAS spoke breaks lines at
  the sheet 5 diaphragm stations; `rhino_ps_i_bim` emits the slice with
  the designed strand rows (and debond counts) in the tags.

- **Railing program (SCD Waves 8-9).** RM-4.6 concrete barrier end
  sections (Type B/B1/D lofting stations down to the 32 in
  terminal-ready end), RM-4.4 single-slope barrier transitions
  (plan-width tapers at sign supports and pier protection), RM-5.2
  bikeway railing (new treated-wood post-and-rail module), RM-4.7
  thrie-beam transitions between 32 in PCB families (three connection
  pairs; the J-J Hook NJ shape correctly refuses). MGS bridge terminal
  assemblies Type 1 / Type 2 / TST-2 as post-by-post layouts joining
  guardrail runs to the bridge railings, plus `layout_mgs_run` and
  registry-note coverage of the remaining MGS sheets.

- **Roadway alignment + terrain.** New `transportation` alignment
  module (horizontal/vertical geometry) with terrain support and a
  point-cloud processing notebook — the first leg of the native
  Alignment/Terrain roadmap.

- **SCD review pass.** Every previously-built SCD component
  (A-1-20 through VPF-1-24) re-verified against its drawing; findings
  folded into the modules and `Validation TODOs.md`. The
  `tests/functional_tests/ODOT SCD Components Verification.ipynb`
  notebook now exercises all 33 component families end to end,
  including the three BrIM emits, the substructure type gallery, and
  every barrier shape family generated to a tagged `.3dm`.

### Breaking

- `odot.ps_i_beam`: the Modified AASHTO Type 4 sections'
  `top_flange_width_in` changed from the incorrect `20.0` to the
  drawing's `36.0` / `36.0` / `48.0`; anything consuming those values
  (haunch widths, emit geometry) gets different — now correct —
  dimensions.

## [0.3.9] - 2026-07-07

- **Python 3.9 support (Rhino compatibility).** Lowered `requires-python` to
  `>=3.9` so civilpy installs into Rhino's bundled Python 3.9 (`rhinoinside` /
  Rhino 8 CPython). Added `from __future__ import annotations` to the ~40
  modules that used PEP 604 `X | Y` union type hints, which only evaluate
  natively on 3.10+; deferred evaluation makes the same annotations safe on
  3.9 without changing any typing. `tox.ini` now runs the suite under `py39`
  in addition to `py311`.

- **Bolted field splice — plate sizing tools.** Added
  `size_flange_splice_plates` (C6.13.6.1.3b) and `size_web_splice_plate`
  (6.13.6.1.3c / seal spacing 6.13.2.6.2) to `aashto.lrfd.splices`, so the
  designer proportions the splice plates from the girder geometry instead of
  taking them as inputs: outer plate = narrowest connected flange, web
  clearance gap from `max(tw) + 2*(weld + 1/8)`, inner width `(b - clr)/2`,
  minimum thickness `t/2 + 1/16`, and inner thickness proportioned to the
  outer plate with the 10% double-shear band. The web tool returns the
  near-full-depth plate height, the 6.13.2.6.2 sealing pitch, the resulting
  minimum bolts per row, and whether a web filler is required. Validated
  against both NSBA plate-girder worked examples (`FlangeSplicePlates`,
  `WebSplicePlates`).

- **Documentation overhaul.**
  - Finished the MIT relicense in the source tree: replaced the AGPL notice in
    ~200 file headers with an SPDX MIT notice (`CONTRIBUTING.md` updated too);
    every module now carries the same header.
  - Added module docstrings to the 50+ modules that had none, and fixed
    docstring reST errors so autodoc renders them cleanly.
  - Sphinx site now covers the whole package: new/expanded `.rst` pages for
    `geotech`, `structural` (incl. new `aashto.lrfd`, `odot`, `stm_topology`
    pages), `state.maryland`, `state.ohio.snbi`, transportation and
    water-resources modules; rewrote `docs/index.rst` into a real landing page
    (install, quickstart, package overview, MIT license section); `conf.py`
    reads the release from package metadata instead of a stale hardcode.
  - Import-safety fixes so autodoc (and plain `import`) can't hang or crash:
    GUI scripts (`mdta_photo_editor`, `D6_file_explorer`,
    `ODOT_Inspection_Photo_DL`) no longer launch windows at import —
    wrapped in `main()`; `gemini.py` refactored into callable functions
    (no more API-key check at import); `transportation.FHWA.snbi` no longer
    plots at import; fixed `mdta_photo_editor`'s broken `photos` import;
    added `state/maryland/__init__.py`.
  - New demo notebooks: **Bridge Scour (HEC-18)**, **Geotech Foundations from
    a Boring Log**, and **Roadway Geometry — Curves and Sight Distance**,
    executed and matching the existing invented-problem house style.
  - Added `TODO.md` cataloguing architecture cleanups (redundant modules,
    placeholder stubs, misplaced files, naming inconsistencies).

## [0.3.8] - 2026-07-01

- **Relicensed to MIT.** Reverted from AGPL-3.0-or-later back to MIT (`LICENSE`,
  `pyproject.toml` license field and classifier).

## [0.3.7] - 2026-07-01

- **Bolted field splice — web horizontal force Hw** (`structural.aashto.lrfd`).
  The web bolt group is now sized for the AASHTO 6.13.6.1.3c moment couple: when
  the flanges cannot resist the full splice moment, the excess is delivered to
  the web as `Hw = (|Mu| - Mflange)/(D/4)` and the web bolts are designed for the
  resultant of Hw and the design shear. The controlling ± Hw combines with each
  composite service shear case; deck casting keeps its own. Reproduces the second
  worked example's 66-bolt web exactly (previously governed only by the
  maximum-pitch layout).
  - Fixed the Strength I permanent-load factor in `_factor_loads`: gamma_p is now
    chosen (max 1.25/1.50 vs min 0.90/0.65) to maximize the moment in the
    direction checked, per AASHTO 3.4.1 — required for splices whose dead-load
    moment is negative at the splice.
  - Web checks now include a Service II slip check and bearing against the
    shear-plus-Hw resultant.

## [0.3.6] - 2026-07-01

- **AASHTO 6.13.6.1 bolted field-splice designer** (`structural.aashto.lrfd`). New
  `bolted_field_splice` module: `design_splice(SpliceInput) -> SpliceDesign` sizes
  the flange and web bolt groups, lays out the bolt pattern (gage / pitch / edge /
  end), sizes the splice plates, and runs the limit-state checks by feeding the
  existing `steel`/`splices` primitives. Exported from the `lrfd` package.
  - Extended `splices.py` with the remaining article functions: splice-plate
    design-force apportioning (C6.13.6.1.3b), filler-plate reduction R
    (6.13.6.1.4), net-section limit An ≤ 0.85·Ag (6.13.5.2), composite slab
    crushing (D6.1), flange moment resistance, and bolt spacing/edge limits
    (6.13.2.6).
  - `steel.bolt_shear_resistance` gained a `design_year` switch selecting the
    0.56/0.45 shear coefficient (2017+) vs the legacy 0.48/0.38 (6.13.2.7); the
    default is unchanged.
  - Validated to the cent against two independently worked plate-girder splices
    (bolt counts, layout, plate sizes, block-shear modes, bearing, slab crushing);
    `tests/structural/test_bolted_field_splice.py`. Known limitation: the web
    moment-couple Huw for the inadequate-flange case (needs elastic flange
    stresses) is surfaced through the failing flange checks rather than by
    enlarging the web group.

## [0.3.5] - 2026-07-01

- **SNBI validation — B.RT.01 optional** (`state.ohio.snbi`). AssetWise reports a
  route's number/direction but omits the B.RT.01 Route Designation on many routes,
  and FHWA flags that omission 0 times. `Route.BRT01` is now optional (was
  required); when present it must still be a valid designation (begins with "R",
  ≤3 chars). This clears the residual BRT01 false errors that traced to a
  snbi_ui field-mapping bug (fixed there in parallel: routes were read at the
  feature stride of 31 instead of their own stride of 30, and absent designations
  were fabricated as the literal "Unknown").

## [0.3.4] - 2026-07-01

- **SNBI validation — calibration round 2** (`state.ohio.snbi`). First run against
  a full local AssetWise sync (46,355 bridges / 28,045 NBIS) cut the error count
  from 22,534 (5.5× FHWA's 8,301) to **5,929 (0.71×)** by removing over-reporters
  that FHWA's own report flags 0 times (our REST read omits data the "export FHWA
  data" feed carries). Principle: strip only rules FHWA does not enforce at all;
  keep the ones it does even when our pull over-triggers them on missing data.
  - Dropped the "highway feature must report a Route (BRT01)" requirement (7,358
    false errors); the BH02/06/09/11/13/16/17 requiredness is now gated on the
    feature actually having a Route, so it no longer re-reports the same
    incomplete-pull records thousands of times.
  - BAP03 Scour Vulnerability now accepts "N" (not applicable), matching BAP05.
  - BG05 Width Out-to-Out, BG02 Total Length, BG09 Approach Width, and BCL01/BCL02
    owner/maintenance are optional (FHWA flags none of their nulls); BG06
    curb-to-curb stays required (FHWA does flag its nulls).
  - See `docs/SNBIValidationRules.md` for the per-item table and the finding that
    the residual BRT01 errors are an `snbi_ui` field-mapping bug (route *number*
    loaded into Route *Designation*), to be fixed there, not by loosening the rule.

## [0.3.3] - 2026-06-30

- **SNBI validation — calibration against FHWA** (`state.ohio.snbi`). The first
  full NBIS run against FHWA's processing report showed 0.3.2 over-reported, so
  this release dials the rules back to match FHWA's actual finding rates:
  - Reverted to optional (FHWA tolerates the null far more than our data omits
    it): BG03, BG07, BG08, BG10, BG11, BIR01, BIR03, BAP01, BAP02, BAP03, Route
    BRT03/04/05; BSP12 no longer forced on decked spans. Kept the items that
    matched FHWA (BG06, BG14, BAP05, BCL03/04/05, the highway BH set, BN02/04/06,
    BSP02/04/05/06/09).
  - Removed enum checks that rejected valid codes FHWA accepts: BCL01/BCL02,
    BF01 pattern, BEP03, BSP07/08/10/11/13, BSB05/06/07.
  - Relaxed BG05 > BG06 to BG05 ≥ BG06 (equal widths allowed).

---

## [0.3.2] - 2026-06-30

- **SNBI validation — FHWA agreement build-out** (`state.ohio.snbi`). Closes
  most of the gap against FHWA's own SNBI processing report. See
  `docs/SNBIValidationRules.md` for the full per-item roadmap.
  - Wired the coded-value tables (`_SNBI_CODES` / `_PATTERN_CODES`, previously
    unused) to their fields, so invalid coded values now raise.
  - Made the unconditional "report for all bridges" items required: BG06 (`>0`),
    BG07, BG08, BG03 (`>0`), BG10, BG11, BG14, BAP01/02/03/05, BCL03/04/05,
    BIR01/03.
  - Conditional requiredness: highway features require BH02/06/09/11/13/16/17;
    routes require BRT02–05; span sets require BSP02/04/05/06 (plus BSP09/12 for
    decked, non-pipe-culvert spans); navigable waterways require BN02/04/06.
  - Cross-field rules: BG05 > BG06 (except sidehill), BC09 channel-vs-waterway,
    BH18 ≠ BID01, BW02 ≥ BW01, BEP04 not reported with BEP03 ∈ {C,S,L,V}, and
    one-decimal-place format for BG15/BH16.

---

## [0.3.1] - 2026-06-29

- **SNBI validation fix** — `state.ohio.snbi` `Element.BE02` (Element Parent
  Number) is now optional. It is only reported for child elements (defects,
  protective systems); top-level NBE elements have no parent, so requiring it
  raised a spurious "Field required" on every parentless element (the dominant
  share of validation errors on complete inventories).

---

## [0.3.0] - 2026-06-24

Final 0.3.0 release, promoting the tested 0.3.0rc1/rc2 candidates so a plain
`pip install civilpy` selects it by default.

- **SNBI validation** — `state.ohio.snbi` now enforces the FHWA SNBI Data
  Validation Rules as real Pydantic checks (state-code validation replacing
  the former `Field(eq=39)` no-op, do-not-report rejection, enumerations,
  date/charset/range rules, and cross-field critical/safety checks).
- Includes everything from 0.3.0rc1 and 0.3.0rc2 below.

---

## [0.3.0rc2] - 2026-06-16 (release candidate)

`MidasCivil` hardening from live batch load-rating runs:
- **Long-operation timeout** — `analyze()`, `open()`, and `result_table()` now
  use a 600 s read timeout (class attr `ANALYSIS_TIMEOUT`); the 30 s default cut
  off large finite-element solves mid-analysis. Default request timeout 30 → 60 s,
  and `request()` takes a per-call `timeout=`.
- **`beam_forces(elem_ids, load_case_names, …)`** — element-force extraction in
  the request shape confirmed against live Civil NX (integer `NODE_ELEMS` KEYS +
  `UNIT` + `STYLES` + `PARTS`); omitting any of those returns the
  `"second query is wrong"` HTTP 400.

---

## [0.3.0rc1] - 2026-06-16 (release candidate)

Pre-release for 0.3.0. A plain `pip install civilpy` will **not** select it;
install it explicitly with `pip install civilpy==0.3.0rc1`.

Highlights since 0.2.4:
- **Substructure design** — cantilever retaining wall / abutment
  (`structural.abutment`) and multi-column pier & bent (`structural.pier`).
- **Geotechnical** — laterally loaded piles with a p-y library + FE solver and
  Broms / subgrade methods (`geotech.lateral_pile`), LPILE integration
  (`geotech.lpile`), drilled-shaft & driven-pile axial capacity from boring
  logs (`geotech.deep_foundation`), shallow/spread foundations
  (`geotech.shallow_foundation`), DIGGS boring schema and SPT correlations.
- **MIDAS modeling** — `structural.midas_models` payload builders (curved
  girders, bifurcated girders, integral/semi-integral abutment connections,
  nodal soil-spring supports) and `geotech.axial_load_transfer` API RP 2A
  t-z / q-z axial pile load-transfer curves.
- **RC design** — `aashto.lrfd.concrete.size_flexural_rebar` selects flexural
  reinforcement from a factored moment.
- HEC-18 scour, ODOT standards (box beams, railings, guardrail), CANDE
  box-culvert integration, the truss-bridge builder, and AASHTO LRFD/LRFR
  check-suite expansions.

---

## [0.2.4] - 2026-06-11
- Added `MidasCivil` class to `civilpy.structural.midas` — object-oriented MIDAS API client
  covering the full API surface: generic `/db/*` access (`get_db`/`put_db`/`post_db`/`delete_db`),
  typed table helpers (nodes, elements, materials, sections, supports, static loads, groups,
  load combinations, units), document operations (`new`/`open`/`save`/`save_as`/`analyze`/
  `import_file`/`export_file`), and results extraction via `result_table` (`POST /post/TABLE`).
  Supports custom base URLs, request timeouts, and raises `MidasApiError` instead of printing.
- Fixed `convert_node_units` inverting the conversion factor (12 in → 144 instead of 1 ft)
  and crashing when `to_units` is None.
- Fixed `setup_output_directory` creating the parent directory instead of the `output/` subdirectory.
- Expanded `tests/structural/test_midas.py` with regression tests and full `MidasCivil` coverage.

## [0.2.3] - 2026-05-03
- Bumped version to 0.2.3 for next patch release.
- Updated `pyproject.toml` and synchronized `uv.lock`.
- Preparation for structural engineering TODO implementations.

## [0.1.40] - 2025

- Added extensive docstrings to structural, geotechnical, water resources, and transportation modules
- Migrated from `setup.py` to `pyproject.toml` (PEP 517/518)
- Added Sphinx autodoc documentation pipeline via GitLab Pages
- Fixed CI/CD pipeline: removed Windows/CUDA-only packages (`torch`, `torchvision`, `rhinoinside`) from requirements
- Added `[docs]` and `v*` git tag triggers to CI for selective deployments
- Updated `autodoc_mock_imports` for optional heavy dependencies

## [0.1.39] - 2025

- Added comprehensive Sphinx documentation for structural, geotech, transportation, and state modules
- Updated ReadTheDocs configuration and directory structure
- Improved legacy file handling in `state/ohio/DOT/legacy.py`
- Updated Python and OS version support in `.readthedocs.yaml`

## [0.1.38] - 2025

- Added `# pragma: no cover` annotations to improve coverage reporting accuracy
- Expanded unit tests for structural analysis, geotechnical calculations, and hydraulic designs

## [0.1.37] - 2024

- Added function to display Rhino BREP geometries in Jupyter notebooks

## [0.1.36] - 2024

- Updated licensing of all source files to reflect correct dates

## [0.1.35] - 2024

- Added generalized function for Pydantic models to be used by DBEs

## [0.1.34] - 2024

- Updated Pydantic Bridge Model to QC'd version

## [0.1.33] - 2024

- Updated AssetWise Data Extractor

## [0.1.32] - 2024

- Fixed CI/CD error caused by NumPy compatibility

## [0.1.31] - 2024

- Fixed CI/CD errors caused by NumPy compatibility

## [0.1.30] - 2024

- Fixed CI/CD errors caused by NumPy compatibility

## [0.1.29] - 2024

- Fixed CI/CD errors caused by Python 3.14 compatibility
- Refactored `simple_concrete_slab` for improved readability
- Added `odot_concrete_slab_generator.py` for parameterized bridge deck generation

## [0.1.28] - 2024

- Fixed missing files from previous versions

## [0.1.27] - 2024

- Further developed steel manual reference

## [0.1.26] - 2024

- Various updates and notebook restorations

## [0.1.25] - 2024

- Improvements to SNBI and ODOT tools

## [0.1.24] - 2024

- Improvements to SNBI and ODOT tools

## [0.1.23] - 2024

- Improvements to SNBI and ODOT tools

## [0.1.22] - 2024

- Improvements to SNBI fields and AssetWise data pulling

## [0.1.21] - 2024

- Focused on SNBI fields, AssetWise data, and QOL functions

## [0.1.20] - 2024

- Focused on SNBI fields, AssetWise data, and QOL functions

## [0.1.19] - 2024

- Added BRR functions, updated FEA tools
- Added new way to query and generate maps for ODOT bridges

## [0.1.18] - 2024

- Added BRR functions, updated FEA tools
- Added new way to query and generate maps for ODOT bridges

## [0.1.17] - 2024

- Moved modules; bearing design first draft complete

## [0.1.16] - 2024

- Moved modules; bearing module mostly complete (compressive stress pending)

## [0.1.15] - 2024

- Removed secondary function providing incorrect results

## [0.1.14] - 2024

- Removed secondary function providing incorrect results

## [0.1.13] - 2024

- Removed secondary function providing incorrect results

## [0.1.12] - 2024

- Updated bearing calculation code; ready for early review

## [0.1.11] - 2024

- Reorganized to separate AASHTO and AREMA tools into distinct subpackages

## [0.1.10] - 2024

- Added AASHTO load combinations

## [0.1.9] - 2024

- Added OSE tools; renamed `section` to `reference`

## [0.1.7] - 2024

- Added OSE tools

---

_This file is generated from git commit history. To regenerate:_

```bash
git log --oneline | grep "Release" | head -50
```
