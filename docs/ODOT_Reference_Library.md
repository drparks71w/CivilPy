# Local ODOT reference library

The source drawings live in `res/odot_scds/` (PDFs and the generated
`manifest.json` are git-ignored). The Python geometry/data catalogs live in
`src/civilpy/structural/odot/`; these are transcriptions, not replacements for
the drawings. A fresh checkout does not contain the PDF cache.

Restore missing individual structural, roadway, and hydraulic drawings from
the official ODOT indexes:

```powershell
.venv/Scripts/python.exe scripts/sync_odot_scds.py
```

Use `--refresh` to replace existing PDFs with the currently published files.
The default preserves existing files. The manifest records URLs, hashes,
and which files were fetched; it does not certify a retained file's revision.
Check the revision block before changing a catalog. Dated roadway filenames
may coexist with older undated copies.

## Box-beam bridge references

| Reference | Local PDF | Python catalog |
|---|---|---|
| Box-beam details and bearings | `PSBD-1-25.pdf` | `box_beam` |
| Box-beam design data | `standard-design-data/PSBDD-1-25_01-16-26.pdf` | `box_beam_design` |
| Open three-tube bridge railing | `TST-2-21.pdf` | `bridge_railing` |
| Existing deep-beam railing / retrofit | `DBR-2-73.pdf`, `DBR-3-11.pdf` | `bridge_railing` |
| Deep-beam Type 4 bridge transition | `plan_inserts/GR-3.4.pdf` | `box_bridge_railing` geometry |
| Roadside end treatments | `roadway/MGS-4.1.pdf`, `MGS-4.2_2026-07-17.pdf`, `MGS-4.5_2025-07-18.pdf` | `guardrail` / `box_bridge_railing` |
| Roadway-to-TST-2 transition | `roadway/MGS-3.3_2026-01-16.pdf` | `guardrail` |
| Approach slab reinforcement | `AS-1-15.pdf` | `approach_slab` |
| Approach installation, sleepers and drainage | `AS-2-15.pdf`, `AS-2-15-Sup.pdf` | `sleeper_slab` |
| Conventional abutment | `A-1-20.pdf` | `typical_abutment` |
| Capped pile abutment | `CPA-1-08.pdf` | `capped_pile_abutment` |
| Bearing beveled load plate | `BD-1-11.pdf` | Check drawing applicability |
| Drip strip | `DS-1-92.pdf` | `drip_strip` (do not cut box-beam drip grooves) |

The companion design-data PDF was copied from the existing Downloads copy on
2026-09-18; it is separately published and is not an SCD. The sync script only
downloads documents linked by the SCD indexes.

The 2026-09-18 sync indexed 127 individual drawings and supplements. The
published PSBD-1-25 revision is 2026-07-17; the previous PDF is retained as
`PSBD-1-25_01-16-26.pdf`. TST-2-21, AS-1-15, AS-2-15 and A-1-20 were byte-for-byte
identical to their published copies when checked. This audit does not claim
that every Python catalog has been updated to every newly downloaded revision.

GR-3.4 (2018-07-20) was subsequently retrieved from the official
[roadway plan-insert index](https://www.dot.state.oh.us/PIS/Pages/roadway.aspx)
for the deep-beam transition examples. The sync script also restores this
separately published plan insert.

`BDM-2026-01.pdf` is the January 2026 design basis used for the bridge-detail
work, copied into the cache from the [official archived BDM](https://dam.assets.ohio.gov/image/upload/transportation.ohio.gov/structural/bdm/archive/2026-01-BDM.pdf).
Figures 306-7 and 306-8 distinguish integral and semi-integral box-beam ends;
Sections 308.3 and 309.4 cover box beams and railing applicability. This is a
pinned reference, not a claim that January is the latest manual revision.

Official drawing indexes: [structural](https://www.dot.state.oh.us/SCDs/Pages/structural.aspx),
[roadway](https://www.dot.state.oh.us/SCDs/Pages/roadway.aspx),
[hydraulic](https://www.dot.state.oh.us/SCDs/Pages/hydraulic.aspx).
