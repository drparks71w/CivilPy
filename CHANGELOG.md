# Changelog

All notable changes to CivilPy are documented here. Generated from git history.
Versions follow [Semantic Versioning](https://semver.org/) (major.minor.patch).

---

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
