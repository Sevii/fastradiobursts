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
| 1 Source inventory | 🟡 partial | `.h5` set inventoried; see gaps below |
| 2 Immutable Tier A | 🟢 baseline done | `raw_archive_manifest_h5.parquet` + `.sha256` (4536 files, 0 err, 0 dup). Physical read-only lock DEFERRED until download completes. |
| 3 Master manifest | 🟢 done (h5) | `observation_manifest.parquet` (4536×69) |
| 4 Schema validation | 🟢 done | `contract.py` + 16-test pytest suite (all pass) + `validate_catalog.py` → `schema_validation.parquet` (**4536/4536 PASS**, 0 errors). Docs updated. |
| 5 Reference set | ⬜ not started | |
| 6 Standardized preprocessing | ⬜ not started | |
| 7 Eligibility/exclusion | ⬜ not started | (preview computed — see below) |
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

## Eligibility preview (rough, pre-Task-7)
- `num_time` < 40 (little off-pulse): **3**
- total off-pulse bins < 20: **3**
- usable bandwidth < 100 MHz: 0
- masked-channel frac > 0.5: **39**

## Open data gaps (Task 1)
1. **Download stalled** inside `localizations/` (`.h5.part` incomplete). Dynamic-spectrum
   `.h5` (4536) complete; plots + localizations partial. Other-tab job to resume/finish.
2. **No Catalog 2 metadata table on disk** → manifest fields `catalog_snr`,
   `morphology_label` null, flagged `pending_catalog_table=True`. Source: CADC VOSpace
   DOI 25.0066 (may be elsewhere in the tree, not yet fetched).
3. **4536 vs. catalog 4539** — 3-burst discrepancy to reconcile once the table exists.

## Next steps (proposed order)
1. Formal Task 4 pytest schema suite (`tests/`) — encode required/optional + tolerances.
2. Task 7 eligibility engine over the manifest (E001–E099).
3. Task 5 reference set (20–50 events) + inspection plots.
4. Task 6 standardized preprocessing → Tier B (baseline/noise/off-pulse/project mask).
5. Task 8 QC + distributions; Task 9 benchmark; Task 10 report.
6. Locate Catalog 2 metadata table (coordinate with download tab) to fill catalog fields.
