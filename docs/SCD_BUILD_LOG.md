# ODOT SCD component build log

One line per SCD, updated as each lands. Status: done / parked /
skipped-by-rating. Companion decisions and open questions live in
`SCD_BUILD_QUESTIONS.md`.

| SCD | Status | Module | GH script | Tests |
|---|---|---|---|---|
| AS-1-15 | done | `structural/odot/approach_slab.py` | `Notebooks/res/AS-1-15.py` | 21 (`test_odot_approach_slab.py`) |
| DS-1-92 | done | `structural/odot/drip_strip.py` | `Notebooks/res/DS-1-92.py` | 10 (`test_odot_drip_strip.py`) |
| PCB-91 | done | `structural/odot/portable_barrier.py` | `Notebooks/res/PCB-91.py` | 9 (`test_odot_portable_barrier.py`) |
| AS-2-15 | done | `structural/odot/sleeper_slab.py` | `Notebooks/res/AS-2-15.py` | 9 (`test_odot_sleeper_slab.py`) |
| HW-2.1 | done | `structural/odot/headwall.py` | `Notebooks/res/HW-2.1.py` | 10 (`test_odot_headwall.py`) + table tests in `test_odot_rocker_headwall.py` |
| HW-2.2 | done (circular) | `structural/odot/headwall.py` (`concrete=True`) | `Notebooks/res/HW-2.1.py` (`concrete` toggle) | shared with HW-2.1; elliptical table cataloged, not drawn |
| HW-1.1 | done | `structural/odot/full_height_headwall.py` | `Notebooks/res/HW-1.1.py` | 11 (`test_odot_full_height_headwall.py`) |
| BCHW | done (wingwall/foreslope wall) | `structural/odot/box_culvert_headwall.py` | `Notebooks/res/BCHW.py` | 11 (`test_odot_box_culvert_headwall.py`) |
| SBR-1-20, SBR-3-20, BR-1-13, SBR-2-20, TST-1-99, TST-2-21, DBR-2-73, DBR-3-11, TBR-1-11 | done | `structural/odot/bridge_railing.py` (catalog, pre-existing) | `structural/rhino_barrier.py` `build_barriers()` (shared pipeline, not per-SCD scripts) | covered by `test_rhino_barrier.py` + `test_odot_bridge_railing.py` |
| BR-2-15 | done (bugfix) | `structural/odot/bridge_railing.py` (added `base_width`, `rail_height_above_in`) + `structural/rhino_barrier.py` (new `"combination"` shape family) | `build_barriers()` | `test_rhino_barrier.py::test_combination_*` (2 new tests) |
| SB-1-24 | done | `structural/odot/slab_bridge.py` | `Notebooks/res/SB-1-24.py` | 14 (`test_odot_slab_bridge.py`) |
| CPA-1-08 | done | `structural/odot/capped_pile_abutment.py` | `Notebooks/res/CPA-1-08.py` | 16 (`test_odot_capped_pile_abutment.py`) |
| CPP-1-08 | done | `structural/odot/capped_pile_pier.py` | `Notebooks/res/CPP-1-08.py` | 11 (`test_odot_capped_pile_pier.py`) |
| CS-1-24 | done | `structural/odot/continuous_slab_bridge.py` | `Notebooks/res/CS-1-24.py` | 17 (`test_odot_continuous_slab_bridge.py`) |
| A-1-20 | done (guidance only) | `structural/odot/typical_abutment.py` | `Notebooks/res/A-1-20.py` | 7 (`test_odot_typical_abutment.py`) |
