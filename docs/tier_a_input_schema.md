# Tier A Input Schema — CHIME/FRB Catalog 2 Stokes-I Dynamic Spectra

Empirically decoded from the downloaded `.h5` files (Task 4). This documents the
**source/input** format. The standardized Tier B **output** schema is a separate
document (`standardized_data_schema.md`).

- **Source:** The Second CHIME/FRB Catalog of Fast Radio Bursts (DOI 10.11570/25.0066)
- **Product:** `dynamic_spectra/data/FRB<TNS>_stokesi_dynamic_spectrum.h5`
- **Files on disk:** 4,536 `.h5` (science data). Format: HDF5.
- **Decoded from:** representative sample spanning the file-size range (3 MB – 155 MB).

## Array orientation & coordinates (CONSTANT — safe to assert)

| Property | Value |
|---|---|
| `data` axes | `(frequency, time)` — axis 0 = freq, axis 1 = time (`DIMENSION_LABELS=['freqs','times']`) |
| `num_freq` | 16384 (all files) |
| Channel width (`res_freq`) | 0.0244140625 MHz |
| Band | 400.20752 – 800.18311 MHz |
| Frequency ordering | **increasing** with channel index |
| Time resolution (`res_time`) | native 0.00098304 s (0.983 ms) **× 2ᵏ** — see cadence note |
| Dedispersion | already applied (`is_dedispersed=True`) at `dm_incoherent`, ref `ref_freq` |
| Intensity units | dimensionless (mean-subtracted, per-channel mean-normalized) |

**Normalization:** `data[f,t] = (data_full[f,t] - statistics.mean[f]) / statistics.mean[f]`.
This is a per-channel *gain* normalization by the full-timeseries mean (off-pulse dominated),
**not** normalization to burst amplitude — the true spectral envelope is preserved in
`statistics.mean` and `calibration.flux_conversion_factor`.
Physical flux: `data_jy[f,t] = calibration.flux_conversion_factor[f] * data[f,t]`.

## VARIABLE per burst (record in manifest, never assert equal)

- `num_time` — windowed time-bin count. Observed **20 → 2604+**. Drives off-pulse /
  time-coverage eligibility (Task 7).
- `unwindowed_num_time` — full timeseries length (7k – 33k+).
- `dm_incoherent`, `center_time`, `start_time_unix_nano`, `beam_number`, `event_id`.
- `pulse_emission_region` — `(n_components, 2)` int array: on-pulse time-bin span(s).
  **Absent in ~87 "un-modeled" bursts** (see optional datasets) → off-pulse must be
  derived another way at Task 7. Treated as optional, not a schema error.
- `repeater_name` — empty string for apparent non-repeaters, else source name.

### Time cadence (validated over all 4536 files)

`res_time` is native × 2ᵏ (time-downsampled products), not a single constant:

| res_time | factor | files |
|---|---|---|
| 983 µs | ×1 | 4496 |
| 1966 µs | ×2 | 34 |
| 3932 µs | ×4 | 6 |

Schema rule: `res_time` must be `native × 2ᵏ` **and** equal the actual
`index_map/times` spacing (internal-consistency check catches corruption).
`time_downsample_factor` (=2ᵏ) is recorded per file.

## Datasets

### Required (assert present; fail loudly if missing → E-code)

| Path | Shape | Dtype | Meaning |
|---|---|---|---|
| `data` | (16384, num_time) | float32 | Stokes-I dynamic spectrum (normalized, dedispersed) |
| `flag` | (16384, num_time) | bool | **Original mask**, True=valid, False=missing |
| `good_freq` | (16384,) | bool | Channel-level good/RFI mask (True=good) |
| `index_map/freqs` | (16384,) | float64 | Channel center frequencies (MHz), increasing |
| `index_map/times` | (num_time,) | float64 | Time-bin centers (s since instrument start) |
| `index_map/times_unix` | (num_time,) | float64 | Unix time per bin (UTC) |
| `times` | (16384, num_time) | float64 | Per-pixel time |
| `statistics/mean` | (16384,) | float64 | Per-channel mean over full timeseries |
| `statistics/central_moment_2` | (16384,) | float64 | Per-channel variance (→ noise) |
| `statistics/central_moment_3` | (16384,) | float64 | 3rd central moment (skewness diag) |
| `statistics/central_moment_4` | (16384,) | float64 | 4th central moment (kurtosis diag) |
| `statistics/nsample` | (16384,) | int64 | Valid-sample count per channel |

### Optional (record presence/absence; do NOT fail)

| Path | Notes | Missing in |
|---|---|---|
| `model` | Best-fit burst model. | 87 files ("un-modeled" class) |
| `pulse_emission_region` (attr) | On-pulse time-bin span. | same 87 files |
| `calibration/flux_conversion_factor` | (16384,) float64, Jy → not flux-calibratable, normalized-only. | 250 files |
| `calibration/spectrum` | (16384,) float64 | 250 files |
| `calibration/good_freq` | (16384,) bool | 250 files |

Structural variants (validated over all 4536): full schema (4449); **87 "un-modeled"
bursts** lack both `model` and `pulse_emission_region` (structurally valid — data,
flag, coords, statistics all present); **250** lack the `calibration` group
(normalized-only). Missing-calibration and un-modeled classes skew toward repeaters
but are not exclusively so.

## Root attributes (per-burst metadata → manifest)

`beam_number, burst_parameters_json, catalog, center_time, contact, creator,
datatype, dm_const, dm_incoherent, dm_index, doi, event_id, freqs_bin0, instrument,
is_dedispersed, num_freq, num_time, pipeline_parameters_json, pulse_emission_region,
ref_freq, repeater_name, res_freq, res_time, start_time_unix_nano, stokes, telescope,
times_bin0, tns_name, unwindowed_num_time, unwindowed_times_bin0`

`burst_parameters_json` fields: amplitude, arrival_time, burst_width, dm, dm_index,
scattering_timescale, scattering_index, spectral_index, spectral_running, ref_freq.

## Implications for downstream tasks

- **Task 3 (manifest):** extract identity, coords, and variable fields above; flag
  `has_model`, `has_calibration`.
- **Task 4 (schema tests):** assert constants + required datasets; tolerance-compare
  `res_time`; record (not assert) `num_time`; verify coord array lengths match `data` axes.
- **Task 6 (preprocess):** original mask = `flag` ∧ `good_freq` (broadcast); project mask
  separate. Baseline/noise seed from `statistics`. Off-pulse = complement of
  `pulse_emission_region` within the window; note limited off-pulse when `num_time` small.
- **Task 7 (eligibility):** small `num_time` → off-pulse / time-coverage exclusions;
  missing `calibration` → normalized-only flag (not necessarily an exclusion).
