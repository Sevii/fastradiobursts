# Project ECHO-FRB — WP0 Data-Preparation Plan

**Scope:** Prepare the public CHIME/FRB Catalog 2 data (downloading to `popos`) so every later
analysis is reproducible from the original files. This document covers **WP0 — the data-audit /
data-preparation phase** only. WP1 (candidate reproduction) and beyond begin only after the WP0
exit gate passes.

**Source documents:** `Project_ECHO-FRB_Updated_Research_Proposal.pdf` (v2.0),
`datacleaninginstructions.txt`.

---

## 1. What the two documents jointly require

- **Dataset:** Public CHIME/FRB Catalog 2 — 4,539 bursts from 3,641 sources, total-intensity
  dynamic spectra, 400–800 MHz, 0.983 ms native time resolution.
- **Prime directive — two immutable layers:**
  - **Tier A** = untouched source files + checksums (never altered, resaved, normalized, or cleaned).
  - **Tier B** = standardized spectra/masks, *reproducibly regenerated* from Tier A by one
    versioned command.
- **Reproducibility is non-negotiable:** every generated file traces to
  source checksum → git commit → config hash → env lock → timestamp → responsible job →
  output checksum.
- **Two quarantined candidates:** FRB 20190131D and FRB 20211115A must **not** influence any
  preprocessing choice or threshold. They are processed only by the *frozen* pipeline, and their
  outputs stay quarantined.
- **15 required deliverables** and a **14-point exit gate**, realized through **10 sequential tasks**.
- **Hardware:** the existing 16-core / 64 GB RAM / 16 GB GPU workstation (`popos`) — where the
  download is landing and where compute runs.

---

## 2. Locked-in decisions

- **Repo here, runs on popos.** Code is developed in
  `/Users/nicholassledgianowski/Projects/fastradiobursts` and synced to `popos` for execution
  against the data. Compute-heavy steps (full-archive checksums, preprocessing, benchmarking) run
  via `ssh popos`.
- **Hands off until the download completes.** No inspecting, moving, or checksumming anything
  mid-download — reading a partially-written file yields a false checksum and could race the other
  agent. **Download completion is the trigger to start.**
- **Clean handoff interface.** When the download tab finishes, this phase needs two things from it:
  the **landing path** and any **download log** (source URLs + retrieval timestamps). Those seed
  Task 1 (inventory) and Task 2 (Tier A sealing).

---

## 3. Coordination boundary with the download tab

The other Claude tab performs Task 2's *fetch* on `popos`. To keep two agents from touching the
same files:

- **Download tab owns:** pulling raw files into the landing/staging directory + recording source
  URLs and retrieval timestamps.
- **This phase owns:** everything from ingest-verification onward — sealing Tier A (checksums +
  read-only) and all of Tasks 3–10.

The only interface is **the landing path + a download log**.

---

## 4. Repository & data layout

Repo (initialized fresh — no git history exists yet; step 1 of build is `git init` for provenance):

```
echo-frb/
├── config/            preprocessing_config.yaml, exclusion_reason_dictionary.yaml
├── env/               lockfile (conda/uv), Dockerfile
├── src/echo_frb/
│   ├── ingest/        seal Tier A, checksums, read-only      (Task 2)
│   ├── schema/        format decode + loud schema tests      (Task 4)
│   ├── manifest/      master manifest builder                (Task 3)
│   ├── preprocess/    baseline / noise / off-pulse / masks   (Task 6)
│   ├── eligibility/   status + exclusion engine              (Task 7)
│   ├── qc/            per-file + distribution QC             (Task 8)
│   ├── reference/     20–50 event plot generator             (Task 5)
│   └── bench/         storage + throughput benchmark         (Task 9)
├── tests/             automated schema + QC tests
├── docs/              standardized_data_schema.md, WP0_data_audit_report.md
└── data/  (on popos, NOT in git)
    ├── tier_a_raw/            IMMUTABLE + checksummed
    │   ├── catalog_metadata/  dynamic_spectra/  masks/
    │   ├── documentation/     external_candidate_material/
    ├── tier_b_standardized/
    ├── manifests/  quality_control/  logs/
```

---

## 5. Sequencing — what happens once the download is done

1. **Inspect reality first (read-only).** `ssh popos`, examine the actual file format(s) — CHIME/FRB
   waterfall files (`.h5`/`.npz`), catalog metadata table (CSV/Parquet), masks, docs. Confirm array
   orientation, units, and whether dedispersion is pre-applied. **No writes.**
2. **Seal Tier A (Task 2).** SHA-256 every file, verify each opens, set the archive read-only. A
   second-analyst re-verification script proves the local copy matches the download. Tier A is never
   modified again.
3. **Source inventory (Task 1)** → `raw_archive_manifest.parquet`: expected vs. retrieved, sizes,
   versions, access status; any missing/unavailable products documented.
4. **Tasks 3–10** proceed in the dependency order below.

### Task pipeline (dependency-ordered)

```
Task 2  Seal Tier A ─┬─► Task 1  Inventory
                     ├─► Task 4  Schema decode + loud tests ──► standardized_data_schema.md
                     │                                          │
                     ├─► Task 3  Master manifest ◄──────────────┘
                     │        (identity·integrity·coords·masks·catalog·provenance)
                     ▼
             Task 5  Reference set (20–50 events, 2-analyst inspection)
                     ▼   validates our interpretation before we trust the pipeline
             Task 6  Standardized preprocessing → Tier B
                     (baseline · channel noise · off-pulse · original+project masks ·
                      catalog dedispersion · frozen config · deterministic re-run)
                     ▼
             Task 7  Eligibility / exclusion engine (E001–E099 codes, nothing deleted)
                     ▼
             Task 8  QC: per-file checks + catalog-wide distributions
                     ▼
             Task 9  Benchmark storage + throughput (measure, don't estimate)
                     ▼
             Task 10 WP0_data_audit_report.md + env lock + automated tests
```

---

## 6. Task → deliverable → gate mapping

| Task | Produces | Gate contribution |
|---|---|---|
| 1 Source inventory | `raw_archive_manifest.parquet` | All public products accounted for / documented unavailable |
| 2 Immutable Tier A | checksums, read-only archive | Every file has a verified SHA-256 |
| 3 Master manifest | `observation_manifest.parquet`, `catalog_metadata_normalized.parquet` | One authoritative record per observation |
| 4 Schema validation | schema tests, `standardized_data_schema.md` | Time/freq axes validated; malformed files caught |
| 5 Reference set | `reference_event_index.csv`, `reference_event_qc_plots/` | Manual inspection confirms interpretation |
| 6 Standardized preproc | `preprocessing_config.yaml`, Tier B products | Tier B regenerates from Tier A, identical checksums |
| 7 Eligibility/exclusion | `eligibility_table.parquet`, `exclusion_reason_dictionary.yaml` | Every obs has a status + machine-readable reason |
| 8 QC | `catalog_qc_summary.html/pdf` | QC passes or documented exceptions |
| 9 Benchmark | `archive_storage_benchmark.md`, `preprocessing_throughput_report.md` | Storage/runtime benchmarked before purchases |
| 10 Report | `WP0_data_audit_report.md` + env lock + tests | Full audit assembled |

**Full deliverable list (instructions §4):**

```
1.  raw_archive_manifest.parquet
2.  observation_manifest.parquet
3.  catalog_metadata_normalized.parquet
4.  eligibility_table.parquet
5.  exclusion_reason_dictionary.yaml
6.  preprocessing_config.yaml
7.  standardized_data_schema.md
8.  reference_event_index.csv
9.  reference_event_qc_plots/
10. catalog_qc_summary.html or .pdf
11. archive_storage_benchmark.md
12. preprocessing_throughput_report.md
13. reproducible environment lock file
14. automated schema and QC tests
15. WP0_data_audit_report.md
```

---

## 7. Design guarantees enforced in code

1. **Tier A immutable / Tier B regenerable** from Tier A by one versioned command, byte-identical on
   re-run (Task 6 completion condition, enforced by a CI checksum test on the reference set).
2. **Candidate quarantine in code** — `FRB 20190131D` and `FRB 20211115A` are a hard holdout list;
   preprocessing/threshold code refuses to read them until a `--frozen` flag is set, and their
   outputs write to a quarantined path. Makes "no candidate tuning leaked in" mechanically true.
3. **Full provenance stamp** on every generated file:
   `source_sha256 · git_commit · config_hash · env_id · timestamp · output_sha256`.
4. **xarray + HDF5/Zarr for Tier B** (labeled time/freq dims eliminate axis-orientation bugs — the
   central Task 4 failure mode); **Parquet** for manifests/tables. Matches the proposal stack
   (NumPy / SciPy / Astropy / h5py / xarray; Dask / Ray for burst-level parallelism).
5. **No per-burst tuning** — one frozen config; DM-perturbation and rebinning are labeled *diagnostic*
   variants that never overwrite the primary product. Nothing is ever deleted; exclusions keep a full
   audit record and a reversibility flag.

---

## 8. Preprocessing specifics (Task 6)

Standardized Tier B product retains: intensity dynamic spectrum; time & frequency coordinates;
original mask; a **separate** project mask; baseline estimates; channel-dependent noise estimates;
off-pulse-region definitions; processing metadata; source-file checksum; config hash.

- **Baseline:** robust statistics from off-pulse regions, per-channel where data permit; records which
  samples were used; reports failure when off-pulse data are insufficient; must not subtract burst
  structure.
- **Noise:** channel-dependent σ from off-pulse data; store sample counts, robust + conventional
  estimates, evidence of correlated noise, unstable channels, quality flags. Do **not** normalize
  every channel to the same burst amplitude (would destroy the true spectral envelope).
- **Dedispersion:** use the catalog DM as baseline. No per-event DM optimization during preparation;
  any DM perturbation is a predefined robustness test only.
- **Smoothing/rebinning:** one fixed primary configuration; alternates labeled diagnostic; original
  resolution retained; every operation recorded.

---

## 9. Eligibility & exclusion (Task 7)

Every observation gets exactly one status: `eligible`, `provisionally eligible`, `excluded`,
`processing failure`, or `pending manual review`. Eligible requires: readable spectrum; validated
time/freq coordinates; usable off-pulse interval; enough unmasked bandwidth; enough time coverage for
at least one allowed delay; no unrecoverable saturation / truncation / corruption.

Primary reason codes: `E001_UNREADABLE_FILE`, `E002_CHECKSUM_FAILURE`, `E003_MISSING_TIME_AXIS`,
`E004_MISSING_FREQUENCY_AXIS`, `E005_AXIS_DIMENSION_MISMATCH`, `E006_INSUFFICIENT_OFF_PULSE`,
`E007_INSUFFICIENT_USABLE_BANDWIDTH`, `E008_INSUFFICIENT_TIME_COVERAGE`, `E009_UNRECOVERABLE_SATURATION`,
`E010_UNRECOVERABLE_TRUNCATION`, `E011_CORRUPT_ARRAY`, `E012_MASK_UNINTERPRETABLE`,
`E013_METADATA_MISMATCH`, `E014_NOISE_ESTIMATION_FAILURE`, `E015_UNSUPPORTED_FORMAT`,
`E099_OTHER_REQUIRES_REVIEW`. Each exclusion stores: primary code, optional secondaries, human-readable
explanation, responsible code version, decision date, reversibility flag. **Excluded observations are
never deleted.**

---

## 10. Exit gate — definition of "done"

WP0 passes only when all 15 deliverables exist and every gate condition holds:

- All required public products downloaded or formally documented as unavailable.
- Every source file has a verified checksum.
- Every observation has an authoritative manifest record; every record resolves to a verified file.
- Time and frequency axes validated.
- Original masks preserved; project masks stored separately.
- Baseline and noise estimates reproducible.
- Off-pulse intervals explicitly recorded.
- Every observation has an eligibility status; every exclusion has a machine-readable primary reason.
- A representative reference set has passed manual inspection.
- Automated QC tests pass or produce documented exceptions.
- Full-catalog storage and runtime benchmarked.
- Tier B regenerable from Tier A by one versioned command.
- No candidate-specific tuning has entered the general preprocessing pipeline.

**Once this gate passes, WP1 — literal and clean-room reproduction of the two reported FRB lensing
candidates — may begin.**

---

## 11. Open items before / at start of build

- **Confirm the actual Catalog 2 file format** — h5 waterfalls vs. bulk archive vs. per-burst files
  change ingest and manifest design. This is the first read-only step post-download.
- **Obtain the landing path + download log** from the download tab.
- **Status:** plan approved; implementation on hold until the download finishes.
