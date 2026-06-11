# Data Sources and Attribution

This document records the origins of reference data and third-party code used
in CivilPy.  It is intended to help users and contributors understand where
data comes from and what licensing constraints may apply.

## Steel Shape Properties

| File | Source | Notes |
|------|--------|-------|
| `src/civilpy/structural/res/steel_shapes.csv` | AISC Steel Construction Manual | Section properties for current standard shapes. |
| `src/civilpy/structural/res/aisc_shapes_historic.csv` | AISC Steel Construction Manual (historic editions) | Section properties for shapes from earlier AISC Manual editions. |

AISC shape data is widely used in the structural engineering community.
Users should verify values against the current edition of the AISC Steel
Construction Manual for design purposes.

## AASHTO LRFD Bridge Design Specifications

The following modules contain design values derived from the AASHTO LRFD
Bridge Design Specifications.  These are standard reference values used
throughout the bridge engineering profession.

| Module | AASHTO Reference |
|--------|-----------------|
| `structural/aashto/load_definitions.py` | Table 3.4.1-1 (Load Combinations), Table 3.4.1-2 (Permanent Load Factors) |
| `structural/aashto/bearings.py` | Table 14.6.2-1 (Bearing Suitability), Section 14.7.5 (Method A), Section 14.7.6 (Method B) |
| `structural/aashto/durometer.py` | Section 14.7.6 stress-strain relationships for steel-reinforced elastomeric bearings |
| `structural/aashto/vehicles.py` | Table 3.6.1.2.2-1 (HL-93 Design Truck) |

## AREMA Manual for Railway Engineering

| Module | AREMA Reference |
|--------|----------------|
| `structural/arema/steel.py` | Chapter 15 — Steel Structures (Cooper E80 loading) |
| `structural/arema/rail_tpg_design.py` | Through Plate Girder design provisions |

## Government / Public Data

| File | Source | Notes |
|------|--------|-------|
| `data/snbi/state_fips_master.csv` | U.S. Census Bureau | State FIPS codes and geographic regions. Public domain federal data. |
| `data/snbi/fish_names.csv` | Various public sources | Aquatic species names for SNBI water-crossing identification. |
| `state/ohio/DOT/TIMS.py` | ODOT TIMS ArcGIS REST API | Queries public endpoints at `gis.dot.state.oh.us`. |
| `res/Ohio_NBI.txt` | FHWA National Bridge Inventory | Public domain federal data. |
| `res/ohio_fips.csv` | U.S. Census Bureau | Ohio county FIPS codes. Public domain federal data. |

## Third-Party Code

| Function | Source | License |
|----------|--------|---------|
| `general/photos.py:slugify()` | [Django](https://github.com/django/django) `django.utils.text` | BSD 3-Clause. Full license text included inline above the function. |
