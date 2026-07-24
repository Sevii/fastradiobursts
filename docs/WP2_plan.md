# Project ECHO-FRB — WP2 Plan: Copy Statistic, Empirical Nulls & Null Benchmark

## Context

WP1 passed its gate: the reported pipeline reproduces exactly, but its candidate list is governed by an
**under-determined, frequency-integrated autocorrelation spike step** — FRB 20211115A is fragile, only
FRB 20190131D is robust. WP2 is the proposal's answer to that fragility: replace the 1-D ACF trigger
with a **masked, noise-weighted two-dimensional copy statistic**, and build a **realistically calibrated
empirical null** so that "how copy-like is this component pair?" is measured against how often
*naturally complex FRBs, propagation, and artifacts* imitate a delayed copy — not against Gaussian noise.

**Authorization:** B (granted at the WP1 gate) — WP2 development + initial simulations on the existing
16-core workstation (`popos`). No cloud/hardware purchase (that is gated on WP3).
**Scope (confirmed):** full WP2 per proposal §5.3–5.7, §6, Objectives 2–4. **Tier-1 = classical**
(segmentation + matched filtering); ML stays out of the pipeline entirely.
**Runs on:** Tier B products (frozen WP0 preprocessing), project `.venv`, popos. Embarrassingly parallel
over bursts/injections.

**WP2 gate (proposal §8):** *false-positive behavior is stable across null constructions and known
artifacts are rejected.* **Deliverable:** a versioned analysis package + a null benchmark.

---

## Locked-in decisions
- **Preprocessing is frozen** = WP0 Tier B (`<TNS>_tierb.h5`); WP2 never re-derives it. Alternate
  resolutions/DM perturbations are *diagnostics only* (§5.5), never the primary product.
- **Primary evidence = χ²_copy** (2-D, masked, noise-weighted; §5.4). ML, if ever used, is triage-only
  and never the evidence score — and per the decision above, WP2 uses **no ML**.
- **Quarantine holds.** The two named candidates **and** the WP1 intermediate candidates are recorded
  but **excluded from all threshold/null design**; their scores are computed only after thresholds
  freeze. Reuse the `CANDIDATES` gate; extend it with the WP1 intermediate list.
- **Source-aware everything.** Development / validation / untouched-test splits and null resampling
  operate at the **source** level (repeaters share a source); repeater vs apparent-nonrepeater strata
  are checked separately before pooling.
- **Freeze before WP3.** WP2 ends by freezing preprocessing + statistic + nuisance params + robustness
  tests + thresholds + global-significance method into a **preregistration draft** (Appendix A). No
  named candidate or full-catalog evaluation happens in WP2.

## Primary statistic (§5.4) — the thing WP2 is built around
For proposed component windows A, B over the common valid pixel set V:
```
chi2_copy = min_{Δt, a}  Σ_V  [B(t,ν) − a·A(t−Δt,ν)]²  /  [σ_B²(t,ν) + a²·σ_A²(t,ν)]
```
- **V** = Tier B `project_mask` ∧ `channel_usable` (both components); **σ** = Tier B `robust_std`.
- **Δt** on a prespecified grid with fractional-bin interpolation; **a** = one achromatic scalar
  magnification (no per-frequency warping — that is the H-LP robustness extension, not primary).
- Final statistic (frozen pre-unblinding) may combine reduced χ²_copy, normalized cross-correlation, and
  posterior-predictive diagnostics, with **explicit complexity penalties** for any extra nuisance param.

---

## Task pipeline (dependency-ordered)

```
W2.0 Foundation ─┬─► W2.1 Tier-1 scan ─┐
                 ├─► W2.2 χ²_copy stat ─┼─► W2.3 Empirical nulls ─┐
                 │                      │   W2.4 Adverse sims ─────┤
                 │                      └─► W2.5 Robustness diag ──┤
                 │                                                 ▼
                 │                          W2.6 Dev injections (~10k) → efficiency ε
                 │                                                 ▼
                 │                          W2.7 NULL BENCHMARK  ◄── GATE
                 │                                                 ▼
                 └─────────────────────────► W2.8 Local→global significance (design + null-calibrate)
                                                                   ▼
                                            W2.9 Versioned package + preregistration draft + tests
```

### W2.0 — Foundation: scope freeze + experiment infrastructure
- **Experiment database** (§9.3): one record store binding data hashes · masks · preprocessing version ·
  parameter grids · seeds · scores · posteriors · significance. Parquet + a run manifest, provenance via
  the existing `content_sha256` / config-hash conventions.
- **Source-aware split**: assign every eligible source to development / validation / **untouched-test**
  (sealed) at the source level; persist the split + seed. Repeater/non-repeater strata labeled.
- **Quarantine list v2**: `{FRB20190131D, FRB20211115A}` ∪ WP1 intermediate candidates → excluded from
  design; enforced in code (extend the config `quarantine` block).
- **Delay domain**: set [Δt_min, Δt_max] from the WP0 audit — lower bound > effective temporal
  resolution (0.983 ms native; ×2ᵏ for the downsampled cadences) enough to resolve two components; upper
  bound from the saved time window + off-pulse availability. Recorded in the frozen config.

### W2.1 — Tier-1 catalog-wide candidate generation (classical; §5.3)
- Over **every eligible Tier B spectrum** (regardless of catalog morphology label): segment the
  noise-weighted profile into candidate component windows; matched-filter for delayed energy across the
  delay domain → `(A, B, Δt)` proposals. **Permissive threshold calibrated on null data**; pure triage.
- Output `tier1_proposals.parquet` (per burst: candidate windows + delays + a triage score). Runs
  CPU-parallel across the ~3.9k eligible bursts.

### W2.2 — Primary 2-D copy statistic χ²_copy (§5.4)
- Implement the masked, noise-weighted residual minimized over (Δt, a) with fractional-bin
  interpolation; add normalized cross-correlation + posterior-predictive checks. Emit a per-proposal
  score record (reduced χ²_copy, best Δt, best a, cross-corr, residual summary), provenance-stamped.
- Unit-tested on synthetic injected copies (recover Δt within ½-bin, a within noise) + null controls.

### W2.3 — Empirical null population (§5.6, controls 1–3)
- **Real complex-burst nulls** — all usable multi-component events (ex quarantine + validation reserve).
- **Matched cross-event pseudo-pairs** — components from *different* bursts matched on width / S-N /
  bandwidth / scattering / repeater status / masking (features from `observation_manifest`).
- **Structure-preserving surrogates** — block bootstrap · phase randomization · time-frequency
  permutation (retain spectral envelope + correlated background, destroy any true delayed-copy relation).
- All source-level; output `null_catalog_{real,xpair,surrogate}.parquet` with χ²_copy scores.

### W2.4 — Adverse simulations (§5.6 control 4; the artifacts the gate must reject)
- Physically-motivated imitators injected into real backgrounds: intrinsic drifting components,
  overlapping peaks, chromatic echoes, differential DM, differential scattering, scintillation-like
  modulation, RFI remnants, mask boundaries, baseline errors → `adverse_catalog.parquet`. These define
  the "known artifacts" for the gate.

### W2.5 — Mandatory robustness diagnostics (§5.5, all 8)
- Per candidate: achromatic-delay consistency (per-band delays agree within calibrated uncertainty) ·
  magnification stability (per-band ratio) · fine-structure ordering · residual structure (autocorr /
  drift / channel-edge) · resolution stability (rebin/smooth via `rebin_freq`) · leave-band-out ·
  window-boundary stability · DM/scattering consistency. Each returns a pass/flag + diagnostic values.

### W2.6 — Development injection campaign (~10k; §5.7, §6.2)
- Inject **achromatic delayed copies** into real single-component bursts + real off-pulse; sample
  Δt · μ · S-N · width · scattering · bandwidth · overlap · mask quality. Adaptive allocation (coarse →
  dense near the detection boundary). Also inject a limited set of differential-propagation variants for
  robustness. → detection efficiency `ε(Δt, μ, S/N, width, scattering, bandwidth, mask, overlap)` with
  binomial/hierarchical uncertainty. Output `injection_recovery.parquet` + an interpolated ε model.

### W2.7 — NULL BENCHMARK (the gate) (§8, §6.1)
- Show the χ²_copy **false-positive distribution is stable across** the null constructions (real complex ·
  cross-event pairs · surrogates) — report each FP tail + their disagreement as an explicit uncertainty.
- Show the **known artifacts (W2.4) are rejected** — do not produce copy-like extreme scores.
- Deliverable `null_benchmark_report.md` + `fp_distributions.parquet`. **This is the WP2 exit gate.**

### W2.8 — Local→global significance framework (design + null-calibrate; §6.1)
- Build the catalog-equivalent null-search **max-statistic → empirical family-wise false-alarm
  probability**; source-level cluster resampling / source-level null catalogs. Direct Monte Carlo where
  practical; any extreme-value tail model fitted on one null set, **validated out-of-sample**. (The full
  catalog-global evaluation is WP4; WP2 builds and null-calibrates the machinery + reports the empirical
  resolution.)

### W2.9 — Versioned analysis package + preregistration draft + tests
- Freeze: preprocessing version · Tier-1 config · χ²_copy definition · nuisance params + interpolation ·
  null constructions · robustness tests · thresholds · global-significance method → a timestamped
  **preregistration draft** (Appendix A checklist). Versioned analysis package + automated tests +
  `WP2_null_benchmark_report`. Thresholds freeze at the WP2→WP3 boundary; **no fresh hidden set is
  touched in WP2.**

---

## Deliverables → gate mapping
| Deliverable (proposal §8, §12) | Produced by |
|---|---|
| Versioned analysis package (statistic + config + tests) | W2.2, W2.5, W2.9 |
| Null benchmark (FP stability across constructions; artifacts rejected) | W2.7 |
| Empirical null catalogs (4 constructions) | W2.3, W2.4 |
| Detection-efficiency surface (development) | W2.6 |
| Global-significance machinery (null-calibrated) | W2.8 |
| Preregistration draft (Appendix A) + experiment DB | W2.0, W2.9 |

**Gate:** false-positive behavior **stable across null constructions** (W2.7) **and known artifacts
rejected** (W2.4→W2.7). Plus §8.1 stop-rule: don't spend compute widening simulations while null-model
**misspecification** remains the dominant uncertainty.

## Reused WP0/WP1 infrastructure (do not reinvent)
| Need | Reuse | Path |
|---|---|---|
| Load Tier B (std, mask, noise, offpulse, coords) | `load_tier_b` (+ coords reader) | `reference/make_plots.py`, `repro/cleanroom/lightcurve.py` |
| Freq rebin (resolution diag, band splits) | `rebin_freq(arr, valid, n)` | `reference/make_plots.py` |
| Provenance + determinism + config hash | `content_sha256`, `sha256_of`, `sha256(yaml)[:16]` | `preprocess/standardize.py` |
| Quarantine gate | `CANDIDATES` + config `quarantine` | `config/preprocessing_config.yaml` |
| Burst features (width, scattering, S/N, bandwidth, n_subbursts, repeater, source) | manifests | `manifest/`, `eligibility_table.parquet`, `catalog_metadata_normalized.parquet` |
| Test conventions (determinism, artifact-gated skipif) | `tests/test_*` patterns | `tests/` |

## Layout & compute
- Code namespace `src/echo_frb/search/`: `experiment/` (DB + splits + quarantine v2), `tier1/`,
  `copy/` (χ²_copy), `nulls/`, `adverse/`, `robustness/`, `injection/`, `significance/`, `benchmark/`.
- Frozen `config/wp2_analysis_config.yaml` (delay domain, statistic params, thresholds, grids) — hashed.
- Data on popos: **Tier C** (`tier1_proposals`, `copy_scores`, `null_catalog_*`) + **Tier D**
  (`injection_recovery`, posteriors, benchmark tables) — regenerable from Tier B + config + seeds.
- Compute: existing 16 cores / 64 GB / project `.venv`; parallel via multiprocessing/Dask. GPU not
  required. ~10k development injections; no cloud.

## Verification / exit gate
1. χ²_copy recovers injected copies (Δt within ½-bin, a within noise) and scores nulls low — unit tests.
2. `null_benchmark_report`: FP tails **agree across** real/xpair/surrogate constructions within stated
   tolerance; adverse artifacts sit in the null bulk (rejected), quantified.
3. Detection-efficiency surface has binomial CIs; adaptive stopping documented.
4. Global-significance tail model (if used) validated out-of-sample; empirical resolution reported.
5. Every figure/table regenerates from a versioned command; quarantine holds (no candidate/hidden-set
   evaluation in WP2); splits are source-level. Preregistration draft covers every Appendix-A item.

## Risks / open items
- **Null-model misspecification is the dominant risk** (§8.1) — lead with realistic real-burst nulls;
  treat construction disagreement as an uncertainty, not noise; don't over-simulate to hide it.
- Intrinsic complex morphology imitating copies — matched cross-event pairs + fine-structure/residual
  tests are the guard.
- Plasma propagation is too flexible to "rule out" — treat as adverse tests; require strict achromaticity
  for lens classification (do not claim plasma excluded).
- Catalog time resolution limits short delays / overlap — restrict primary claims to resolved echoes
  (delay domain lower bound); overlap is exploratory.
- Leakage of candidate knowledge into thresholds — quarantine v2 + source-level splits + freeze-before-WP3.
