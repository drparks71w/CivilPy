# Architecture TODOs

Items flagged during the 2026-07 documentation pass — files in odd spots,
redundant modules, and structural cleanups deferred for a later refactor.
Most also carry a `.. todo::` in their module docstring (rendered on the
Sphinx site via `sphinx.ext.todo`) or a `TODO(architecture)` comment at the
offending line.

## Redundant / duplicated modules

- [ ] `src/civilpy/transportation/FHWA/snbi.py` vs
  `src/civilpy/state/ohio/snbi.py` — the real (national, Pydantic) SNBI
  validation models live under `state.ohio`; the FHWA module is a plotting
  scratchpad with hard-coded demo data. Move the generic SNBI models to
  `transportation/FHWA/` (or a new `civilpy.fhwa`) and leave Ohio-specific
  extensions under `state.ohio`.
- [ ] `src/civilpy/state/ohio/DOT/boring_logs.py` — empty stub; working boring
  tools are `civilpy.geotech.boring` / `boring_io`. Implement ODOT wrappers or
  delete.
- [ ] `src/civilpy/state/ohio/DOT/legacy.py` — superseded in part by
  `DOT/TIMS.py`; fold the still-used pieces (label dictionaries, `TimsBridge`)
  into `TIMS.py` and retire the rest.
- [ ] `docs/civilpy.geotechnical.rst` — orphaned redirect page for the old
  `geotechnical` package name; drop once external links have had time to rot.

## Empty placeholder modules (implement or remove)

- [ ] `src/civilpy/construction/__init__.py`
- [ ] `src/civilpy/environmental/__init__.py`
- [ ] `src/civilpy/general/bentley/__init__.py` (generic Bentley API helpers
  should migrate here out of `state/ohio/DOT/AssetWise.py`)
- [ ] `src/civilpy/transportation/FHWA/nbi.py` (NBI code dictionaries
  currently live in `state/ohio/DOT/TIMS.py`; move the generic parts here)
- [ ] `src/civilpy/structural/arema/masonry.py`
- [ ] `src/civilpy/state/ohio/DOT/plan_splitter.py`

## Scripts masquerading as modules

These ran GUIs/network calls at import time; each is now wrapped in a
`main()` with a `__main__` guard, but they belong behind proper console
entry points (`pyproject.toml [project.scripts]`) or in a `tools/` dir:

- [ ] `src/civilpy/state/maryland/mdta_photo_editor.py` (also verify it still
  works against `civilpy.general.photos` — its old sibling-import was broken)
- [ ] `src/civilpy/state/ohio/DOT/D6_file_explorer.py`
- [ ] `src/civilpy/state/ohio/DOT/ODOT_Inspection_Photo_DL.py`
- [ ] `src/civilpy/state/ohio/DOT/gemini.py` — generalize beyond the one
  hard-coded extraction prompt.

## Misplaced files

- [ ] `docs/StrutAndTieSolver.md`, `docs/SNBIValidationRules.md`,
  `docs/Rhino Design Philosophy.md` — design notes sitting in `docs/` but not
  part of the Sphinx build; wire in with `myst-parser` or convert to reST.
- [ ] `docs/ifc_file_example_1.ifc` — test fixture in the docs folder; move to
  `tests/` or `res/ifc_examples/`.
- [ ] `res/` (repo root) — mixed sample data (PDF plan sets, FIPS tables, HY-8
  file). Decide what is test fixture (→ `tests/res/`) vs package data
  (→ `src/civilpy/data/`).
- [ ] `templates/STM_Template.3dm` — single Rhino template at repo root;
  probably belongs with `src/civilpy/structural/rhino_scripts/`.

## Naming / consistency

- [ ] `civilpy.state.ohio.DOT` — only uppercase package in the tree; rename to
  `dot` (breaking change, needs deprecation shim).
- [ ] Mixed module-name casing in `DOT/` (`AssetWise.py`, `OSE.py`, `TIMS.py`,
  `Rhino.py` vs snake_case elsewhere).
- [ ] `tests/geotechnical/` tests the `civilpy.geotech` package — rename the
  test dir to match.
