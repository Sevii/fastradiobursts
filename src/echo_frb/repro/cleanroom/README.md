# Clean-room microlensed-FRB detection pipeline (WP1 reproduction)

Independent, clean-room implementation of the microlensing **detection** pipeline
described in Zhou et al. 2026 (*"Evidence for Intermediate-Mass Black Holes From
Microlensing Signatures in CHIME/FRB Catalog 2"*, arXiv:2605.19653), built
**strictly** from the paper and the paper-derived spec
[`PAPER_SPEC.md`](./PAPER_SPEC.md). No access to the authors' code was used. Lens
masses / f_PBH are intentionally **out of scope** — this package produces a
per-FRB detection verdict only.

## Pipeline (paper Steps 1–9)

| Step | Module | What it does |
|---|---|---|
| 1 Light curve | `lightcurve.py` | Frequency-integrated, noise-weighted intensity `I(t)`. |
| 2–4 ACF + spikes | `acf.py` | Normalized ACF `C(δt)` (Eq. 2), Gaussian-smoothed baseline `G` (σ=3), local scatter `σ_δt` (Eq. 4), 3σ spike flagging. |
| 5–6 Peaks + cuts | `peaks.py` | Peak detection, spike↔peak matching (±2 ms), ordering / secondary-PSNR>10 / global-max cuts. |
| 7 K-S drift | `drift_ks.py` | Per-component spectra rebinned to n_f=512, two-sample K-S `D_max` (Eq. 6), bootstrap null `D_{n,upp}`, drift decision. |
| 8 Hardness | `hardness.py` | 3-band [L,M,H] hardness-ratio consistency within 1σ (Eq. 8). |
| 9 Verdict | `pipeline.py` | Per-FRB orchestration → candidate verdict + content hash. |
| batch | `run.py` | CLI over the 340-set → `cleanroom_scores.parquet`. |

All thresholds live in [`cleanroom_config.yaml`]; the config hash follows the repo
convention `sha256(file_bytes)[:16]`.

## Running

```bash
# on popos, with the project venv (numpy/scipy/pandas/h5py/pyarrow):
python -m echo_frb.repro.cleanroom.run \
    --config     src/echo_frb/repro/cleanroom/cleanroom_config.yaml \
    --target     src/echo_frb/repro/cleanroom/target_340_set.csv \
    --tier-b-dir ~/frb_catalog2_prep/tier_b_standardized \
    --out        ~/frb_catalog2_prep/wp1_repro/cleanroom_run/cleanroom_scores.parquet
```

Output columns (neutral results schema): `frb_name, spike_delays_ms, matched_pairs,
best_delay_ms, mag_ratio, is_candidate, has_drift, n_components, config_hash,
content_sha256, code_commit` plus diagnostics (`n_spikes, n_matched,
best_secondary_psnr, ks_d_max, ks_d_upp, n_usable_channels, note`).

## Parameters the paper fixes (used verbatim)

`smoothing σ = 3` for `G`; spike threshold `3σ_δt`; peak-match tolerance `±2 ms`;
secondary PSNR `> 10`; K-S `n_f = 512`; `D_crit = 1.36·√(2/n_f) ≈ 0.1 @ α=0.05`;
bootstrap `~10³`; hardness bands `= 3`; hardness consistency `1σ`; ACF spike
amplitude relation `R_f/(R_f²+1)`.

## Implementation choices (where the paper is silent)

Each item is a documented, independent decision — **not** tuned to any external
number. All are exposed in `cleanroom_config.yaml`.

1. **Light-curve noise weighting** (`lightcurve.weighting: invvar`). `I(t)` is the
   inverse-variance-weighted channel mean, `w_c = 1/robust_std_c²`, over channels
   with `project_mask ∧ channel_usable ∧ finite,positive σ`. The pixel-level
   `project_mask` gates each time bin. This is the minimum-variance estimator of a
   common burst profile. The light-curve baseline `μ_off` and noise `σ_noise` are
   robust (median / 1.4826·MAD) statistics over the off-pulse bins.

2. **ACF lag range & edge handling.** One-sided ACF for lags `0…max_lag`, with
   `max_lag = round(max_lag_ms / bin_ms)` and `max_lag_ms = 50` (component
   separations of interest are at most tens of ms in one dynamic spectrum). Per-lag
   normalization uses `N_δt = N − k` overlapping samples and the full-series
   variance `σ_I²`, giving `C(0)=1`.

3. **Zero-lag exclusion** (`acf.min_lag_bins = 2`). The trivial zero-lag core is
   excluded from **both** the spike search and the `σ_δt` scatter estimate;
   otherwise the `C(0)=1` peak and its smoothed shoulder inflate `σ_δt` and mask
   real spikes. Contiguous supra-threshold lags are collapsed to their peak lag.

4. **Peak detection** (`peaks.detect_snr = 5`, `min_separation_bins = 2`).
   `scipy.signal.find_peaks` on `I(t)` with height `μ_off + 5·σ_noise`. The detect
   floor is kept **below** the secondary-PSNR>10 cut so genuine near-threshold
   secondaries are not lost before the cut is applied. `PSNR = (I_peak−μ_off)/σ_noise`.

5. **Component window** (`peaks.component_halfwidth_bins = 3`). A component's flux
   and spectrum are integrated over `±3` time bins around its peak, auto-shrunk to
   `min(3, ⌊Δt_bins/2⌋)` so paired windows never overlap.

6. **Magnification ratio** `R_f`. Primary estimate is the integrated-flux ratio
   `F_leading/F_trailing` (≥1 under the ordering cut). `acf.rf_from_acf_amplitude`
   additionally inverts the ACF-spike amplitude `A = R_f/(R_f²+1)` as an independent
   cross-check (used in tests).

7. **K-S spectra as distributions.** Per-component spectra are the time-integral of
   the standardized dynamic spectrum over the component window, mask-aware rebinned
   16384→512. To form CDFs for the two-sample statistic, spectra are clipped at 0
   and normalized to unit sum; `D_max = max|CDF_i − CDF_j|`.

8. **K-S bootstrap null** (`ks.bootstrap_iters = 1000`, `upp_percentile = 99.73`,
   `bootstrap_seed = 20260722`). The null "identical spectra + noise" uses the mean
   of the two spectra as the shared truth and adds independent per-rebinned-channel
   Gaussian noise (propagated from `robust_std` over the integration window and the
   rebin) to two realizations; `D_{n,upp}` is the 99.73rd percentile (~one-sided 3σ)
   of the resulting null `D` distribution. Drift is declared iff
   `D_max > D_crit AND D_max > D_{n,upp}`. Fewer than 8 shared-usable rebinned
   channels ⇒ inconclusive, drift **not** declared. The RNG is **seeded** so the
   whole pipeline is deterministic.

9. **Hardness bands.** Equal-width frequency thirds over the channel axis; band flux
   integrated over the component window (baseline already subtracted in Tier B);
   `σ_band = √(nw)·√(Σ σ_c²)`. Ratios `HR_HM = H/M`, `HR_ML = M/L` must each agree
   between the two components within 1σ (quadrature-combined). A non-positive
   denominator ⇒ failed (inconsistent) cut.

10. **Best-pair / verdict policy.** An FRB is a **candidate** iff ≥1 matched pair
    passes all cuts, is **not** flagged as drift by K-S, and is hardness-consistent;
    among such pairs the reported one maximizes trailing PSNR. If no candidate but
    some cut-passing pair was K-S-tested, that pair is reported with `is_candidate=
    False` and its `has_drift`. If only sub-cut matches exist, the strongest-spike
    pair is reported (`has_drift=False`, untested). No matches ⇒ `best_delay_ms/
    mag_ratio = NaN`.

11. **Unusable inputs.** `noise_failed=True` (e.g. FRB20201014B) or zero usable
    channels ⇒ a graceful non-candidate row with `note` set; never a crash. Missing
    Tier B files and per-FRB exceptions are likewise recorded in `note`, not raised.

12. **Determinism / provenance.** `content_sha256` hashes the light curve + the
    rounded numeric verdict + `config_hash`; identical inputs reproduce it exactly
    (verified in tests and on real data). Rows also carry `config_hash` and
    `code_commit`.

## Tests

`tests/test_cleanroom.py` (pytest): (a) recovery of an injected delayed, scaled
copy — Δt within ±1 bin and a sensible `R_f`, plus an ACF-amplitude cross-check;
(b) no-copy control yields no candidate; (b′) a spectrally-drifting copy is rejected
by the K-S test; (c) determinism of `content_sha256`; and graceful `noise_failed`
handling. All pass.

> A genuine point-mass echo is a *sharp* copy, so the ACF side-peak must be narrow
> relative to the σ=3 smoothing kernel; the recovery test therefore injects ~1-bin
> (≈1 ms) components, matching CHIME's 0.983 ms resolution. Intrinsically broad
> components (≳3 bins) are, by design, not flagged — the smoothing absorbs a broad
> side-peak into the baseline.
