# WP0 Data-Preparation — Progress Tracker

Living status of the 10 tasks in `datacleaninginstructions.txt`. Data + generated
products live on popos under `~/frb_catalog2/` (Tier A source) and
`~/frb_catalog2_prep/` (generated). Code in this repo, synced to
`~/Projects/fastradiobursts` on popos, run via its `.venv`.

## Environment
- popos: uv-managed `.venv` (Python 3.10) — h5py 3.16, numpy 2.2, scipy 1.15,
  astropy 6.1, xarray 2025.6, pyarrow, zarr, matplotlib. Lock: `env/requirements.lock`.

## Task status

| Task | Status | Artifact |
|---|---|---|
| 1 Source inventory | 🟢 done | `data_source_inventory.parquet` — 5 products, 22755 files, 64.3 GB (download complete). 3 events lack an `.h5` (documented). |
| 2 Immutable Tier A | 🟢 done | `raw_archive_manifest.parquet` + `.sha256` (**22755 files, 64.3 GB, 0 err**). Tier A **sealed read-only** (`chmod -R a-w`). |
| 3 Master manifest | 🟢 done | `observation_manifest.parquet` (4536×**90**), enriched with catalog table (S/N, DM, morphology, flags). `catalog_metadata_normalized.parquet` (4539 events, deliverable #3). |
| 4 Schema validation | 🟢 done | `contract.py` + 16-test pytest suite (all pass) + `validate_catalog.py` → `schema_validation.parquet` (**4536/4536 PASS**, 0 errors). Docs updated. |
| 5 Reference set | ⬜ not started | |
| 6 Standardized preprocessing | ⬜ not started | |
| 7 Eligibility/exclusion | 🟢 done | `engine.py` + `eligibility_config.yaml` + `exclusion_reason_dictionary.yaml` → `eligibility_table.parquet`. 10 unit tests. 4236 eligible / 298 provisional / **2 excluded** / 0 failures. Invariant: all 4536 have a status. |
| 8 QC | ⬜ not started | |
| 9 Benchmark | ⬜ not started | (checksum: 501 files/s; manifest read ~full 56GB) |
| 10 Report | ⬜ not started | |

## Key decoded facts
- `.h5` = Catalog 2 Stokes-I dynamic spectra. `data` shape `(16384 freq, num_time)`,
  freq **increasing** 400.2–800.2 MHz @ 0.0244 MHz, time res 0.983 ms,
  **already dedispersed** at catalog DM, per-channel mean-normalized.
- Original mask = `flag` (pixel) ∧ `good_freq` (channel). Off-pulse from
  `pulse_emission_region` attr. Per-channel noise/baseline seed = `statistics/*`.
- Optional datasets: `model` (missing in 87), `calibration/*` (missing in 250 →
  normalized-only, no Jy). All examples repeaters.

## Manifest distributions (4536 obs)
- `num_time`: 20 / 162 / 2604 (min/med/max). 981 repeaters.
- orig masked-pixel frac: med 0.14, max 0.96. masked-channel frac: med 0.28, max 0.68.
- usable bandwidth: all ≥126 MHz. NaN/Inf: none. All coord checks pass.

## Schema diversity found by full-catalog validation (Task 4)
- **87 "un-modeled" bursts** lack `model` + `pulse_emission_region` (structurally
  valid; off-pulse must be derived without the attr at Task 7). → W_NO_MODEL / W_NO_PULSE_REGION.
- **250** lack `calibration` group → normalized-only, no Jy. → W_NO_CALIBRATION.
- **3 time cadences**: 983 µs ×4496, 1966 µs ×34, 3932 µs ×6 (native × 2ᵏ).
  `time_downsample_factor` recorded per file; res_time cross-checked vs coord spacing.
- Contract violation codes map to Task 7 E-codes (E003/E004/E005/E011/E012/E013/E015).

## Eligibility results (Task 7, config_hash 44c5fb1f624f4ff3)
Preregistered thresholds: usable BW ≥100 MHz, time coverage ≥32 bins, off-pulse ≥16 bins,
soft masked-pixel flag >0.50. Set from band/cadence physics, independent of candidates.
- **eligible: 3876 | provisionally_eligible: 658 | excluded: 2 | processing_failure: 0**
- 2 excluded: `FRB20201014B` (E006, off-pulse 14<16), `FRB20210421D` (E008, num_time 20<32).
- provisional flags (files may carry >1): catalog_excluded 369, no_calibration 250,
  needs_offpulse_derivation 87, catalog_sidelobe 30, heavily_masked 16.
- Both candidates classified `eligible`, quarantined, did not influence thresholds.
- Invariant holds: every one of 4536 rows has a status + machine-readable reason.
- Decisions are deterministic given (manifest, schema, config); only the provenance
  timestamp varies run-to-run.

## Data gaps (Task 1) — RESOLVED
1. ✅ Download complete (22755/22755, 0 `.part`). All products present.
2. ✅ Catalog table found: `table/chimefrbcat2.{csv,fits,json,npy}` (4539 events, 60 cols).
   Manifest enriched; `pending_catalog_table=False`.
3. ✅ 4536 vs 4539 = **3 events with no dynamic spectrum**: FRB20190415C, FRB20190422B,
   FRB20190517D (in catalog, no `.h5`). All 4536 `.h5` events are in the catalog.
- Note: catalog marks **369** of our events `excluded_flag=1` + **30** `sidelobe_flag=1` →
  retained but surfaced as provisional soft flags (own eligibility decision, non-destructive).
- Not yet used: `localizations/`, `exposure/` (available for later WPs).

## Next steps (proposed order)
1. Formal Task 4 pytest schema suite (`tests/`) — encode required/optional + tolerances.
2. Task 7 eligibility engine over the manifest (E001–E099).
3. Task 5 reference set (20–50 events) + inspection plots.
4. Task 6 standardized preprocessing → Tier B (baseline/noise/off-pulse/project mask).
5. Task 8 QC + distributions; Task 9 benchmark; Task 10 report.
6. Locate Catalog 2 metadata table (coordinate with download tab) to fill catalog fields.
