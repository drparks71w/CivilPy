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
