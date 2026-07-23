# Standardized (Tier B) Data Schema

Deliverable #7. Documents the output of the Task 6 preprocessing pipeline
(`echo_frb.preprocess.standardize`). One HDF5 file per eligible observation,
`<TNS>_tierb.h5`, deterministically regenerable from the Tier A source + the
frozen `preprocessing_config.yaml`.

Format: HDF5 (gzip level 4, `shuffle=True`, `track_times=False` for byte-level
reproducibility). Frequency axis length is 16384; `T` = `num_time` (per event).

## Root attributes

### Provenance
| Attr | Meaning |
|---|---|
| `source_file` | Tier A filename |
| `source_sha256` | SHA-256 of the Tier A source (from the raw archive manifest) |
| `config_hash` | SHA-256 (16-hex) of `preprocessing_config.yaml` |
| `code_commit` | git commit of the pipeline |
| `preprocessing_version` | e.g. `wp0-preproc-v1` |
| `content_sha256` | hash over the logical arrays + metadata (determinism check) |
| `tns_name`, `event_id`, `dm_incoherent`, `res_time`, `res_freq`, `num_time` | copied Tier A identity/coords |

### Processing summary
| Attr | Meaning |
|---|---|
| `offpulse_method` | `pulse_emission_region` or `derived_profile` |
| `on_pulse_start`, `on_pulse_end` | on-pulse time-bin span (guard-expanded) |
| `n_offpulse_bins` | off-pulse time bins used |
| `n_usable_channels` | channels in the project mask with a valid noise estimate |
| `project_masked_pixel_frac` | fraction masked by the project mask |
| `corr_time_lag1`, `corr_freq_adj` | correlated-noise indicators (off-pulse) |
| `noise_failed` | True if off-pulse/usable-channel count too low to estimate noise |

## Datasets

| Path | Shape | Dtype | Meaning |
|---|---|---|---|
| `standardized` | (16384, T) | float32 | baseline-subtracted dynamic spectrum (`data - baseline[:,None]`) |
| `mask/original_flag` | (16384, T) | bool | **original** pixel mask from Tier A `flag` (True=valid) — preserved verbatim |
| `mask/original_good_freq` | (16384,) | bool | **original** channel mask from Tier A `good_freq` — preserved verbatim |
| `mask/project_mask` | (16384, T) | bool | **separate** project mask (True=use): original ∧ usable-noise-channel ∧ not-outlier |
| `baseline/per_channel` | (16384,) | float64 | robust per-channel baseline (median of off-pulse) subtracted from `standardized` |
| `noise/robust_std` | (16384,) | float64 | robust per-channel σ (1.4826·MAD of off-pulse); NaN where not usable |
| `noise/conventional_std` | (16384,) | float64 | conventional per-channel σ (std of off-pulse) |
| `noise/nsample` | (16384,) | int64 | off-pulse samples used per channel |
| `noise/channel_usable` | (16384,) | bool | channel has a valid, stable noise estimate |
| `offpulse/time_mask` | (T,) | bool | True = off-pulse time bin (complement of on-pulse) |
| `coords/freqs` | (16384,) | float64 | channel center frequencies (MHz), increasing |
| `coords/times` | (T,) | float64 | time-bin centers (s) |
| `coords/times_unix` | (T,) | float64 | Unix time per bin (UTC) |

## Interpretation notes

- **Original masks are never modified** — `mask/original_flag` and
  `mask/original_good_freq` reproduce Tier A. The project's own masking lives only
  in `mask/project_mask`.
- **Spectral envelope preserved**: `standardized` is baseline-*subtracted* only;
  channels are never renormalized to equal burst amplitude. Physical flux (Jy) is
  recoverable from Tier A `calibration.flux_conversion_factor` where present.
- **Dedispersion**: inherited from Tier A (catalog `dm_incoherent`); not re-optimized.
- **Determinism**: same (source, config, code) → identical `content_sha256` and
  identical file bytes. Verified on real data and by the QC determinism spot-check.
- **Noise weighting** for the downstream copy statistic uses `noise/robust_std`;
  masked/unstable channels are excluded via `mask/project_mask` ∧ `noise/channel_usable`.
