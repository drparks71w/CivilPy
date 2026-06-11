# Changelog

All notable changes to CivilPy are documented here. Generated from git history.
Versions follow [Semantic Versioning](https://semver.org/) (major.minor.patch).

---

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
