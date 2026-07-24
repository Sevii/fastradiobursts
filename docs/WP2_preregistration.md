# Project ECHO-FRB — Preregistration (draft, frozen at WP2→WP3)

**Analysis version:** `wp2-frozen-v1` · **Frozen:** 2026-07-23 · **Config:**
`config/wp2_analysis_config.yaml` (hashed). This document freezes preprocessing, the copy statistic,
nuisance parameters, the empirical null, injections, thresholds, robustness tests, and the global-
significance method **before** the hidden-injection validation (WP3), the named candidates, and the
catalog-wide search (WP4). Any change after WP3 begins creates a new analysis version and forfeits this
significance calibration (proposal §5.8). Covers every Appendix A checklist item.

## A1. Data release, manifest, checksum policy
CHIME/FRB Catalog 2 dynamic spectra (CANFAR `CISTI.CANFAR/25.0066`). Immutable **Tier A** (sha256 per
file, read-only; `raw_archive_manifest.parquet`) → deterministic **Tier B** (`<TNS>_tierb.h5`, one
frozen command, `preprocessing_config.yaml`). Provenance stamp: source_sha256 · config_hash ·
code_commit · content_sha256. (WP0.)

## A2. Eligibility & exclusion rules (reason codes)
`eligibility_table.parquet` with primary reason codes E001–E099 (readable spectrum, validated
time/freq axes, usable off-pulse, sufficient unmasked bandwidth/time, no unrecoverable corruption).
3874 eligible / 658 provisional / 4 excluded; nothing deleted. (WP0.)

## A3. Source-level development / validation / test split
Source = repeater_name (repeaters) else tns_name. Deterministic hash split `bucket = hash(salt,
source_id)`, 60/20/20 at the **source** level (no source spans sets). dev 2186 sources / val 713 / test
736 (sealed). Salt `echo-frb-wp2-split-v1`. (W2.0, `source_split.parquet`.)

## A4. Named-candidate quarantine
Quarantine v2 = {FRB20190131D, FRB20211115A} ∪ published intermediates (G_3∪SG_20∪SG_100) = 23 TNS.
Excluded from ALL threshold/null design; scored only after this freeze. (W2.0, `quarantine_v2.csv`.)

## A5. Primary preprocessing + permitted robustness variants
Frozen = WP0 Tier B (baseline-subtracted, per-channel robust noise, project mask, off-pulse). Permitted
DIAGNOSTIC-ONLY variants: rebin resolution {128,256,512}, component-window ±2 bins, small DM
perturbation. Never re-derive the primary product.

## A6. Search delay domain + component-proposal procedure
Delay domain [2.0, 50.0] ms, per-burst cap 0.4×window, grid step 0.5 ms (fractional-bin interp).
Tier-1 = classical segmentation of the noise-weighted profile + delayed-energy matched filter → (A,B,Δt)
proposals; permissive triage only (peak 4σ, secondary 3σ, ≤10 proposals/burst). (W2.1.)

## A7. Primary copy statistic χ²_copy (§5.4)
`B(t,ν) ≈ a·A(t−Δt,ν)` over the common valid pixel set V. Mask-aware inverse-variance freq rebin
16384→256; on-burst support (|A|/σ>2); closed-form template amplitude `a=Σ(AB/σ_B²)/Σ(A²/σ_B²)`;
Δχ² = matched-filter detection; reduced-χ² whitened by the FULL noise σ_B²+a²σ_A² (~1 at any a); NCC =
on-burst correlation. (W2.2.) `src/echo_frb/search/copy/`.

## A8. Nuisance parameters, priors, interpolation
Magnification `a ∈ [0.02, 1.0]` (delayed image fainter); delay Δt on the frozen grid with linear
fractional-bin interpolation. No frequency-dependent warping in the primary model (that is the H-LP
robustness extension).

## A9. Empirical null construction + source dependence
Four constructions (§5.6): **real** complex-burst nulls, **matched cross-event** pseudo-pairs (matched
on width/S-N/bandwidth/scattering/repeater), **structure-preserving surrogates** (block bootstrap, phase
randomization, TF permutation), **adverse** simulations (8 kinds). All source-level; repeater vs
apparent-nonrepeater strata separate. (W2.3–W2.4.)

## A10. Injection distributions, allocation, hidden-set rule
Achromatic delayed copies into real single-component hosts + real off-pulse. Δt ∈ {3..40} bins,
μ ∈ {0.1..0.9}; ~10⁴ development. Stopping rule = efficiency precision (Wilson CIs), not a round count.
**Hidden validation set (WP3)** built by a blind controller/sealed seed; not touched in WP2.

## A11. Screening + candidate thresholds + mandatory robustness
**Candidate criterion (frozen):** detectability Δχ² > 100 AND copy-quality (NCC > 0.40, reduced-χ² <
1.5) AND **mandatory achromaticity** (per-band delay, magnification, spectral-magnification flatness,
DM/scattering ALL pass) AND robustness n_pass ≥ 7 of 9. The 9 diagnostics + tolerances are frozen in
`config/wp2_analysis_config.yaml:robustness_tolerances`. (W2.5, W2.7.)

## A12. Global false-alarm calculation + tail modeling
Max-statistic family-wise FAP over catalog-equivalent null searches; **source-level cluster bootstrap**
(B=20000; resolution 1/B); GPD tail fit on one null half, validated out-of-sample. **Ranking = local
p-value of the full criterion within S/N-matched nulls** — NOT raw Δχ² (brightness-dominated) or NCC
(saturates) (W2.8). Catalog-global evaluation = WP4.

## A13. Efficiency uncertainty target + simulation stopping rule
Binomial/Wilson CIs per (μ, S/N) cell; adaptive densification near the detection boundary until a
preregistered precision, else compute budget. (W2.6.)

## A14. Candidate-level generative models + prior sensitivity
Reserved for WP5 (nested sampling / SBI on top-ranked survivors; posterior-predictive + prior-sensitivity
reporting). Out of WP2 scope.

## A15. Observable-rate model + conditions for compact-object inference
Observable-space echo rate/limit over the declared (Δt, μ) domain using the W2.6 efficiency; compact-
object abundance only after a separate selection gate (WP5). Out of WP2 scope.

## A16. Post-unblinding modification rule
Any post-unblinding change → new analysis version + a fresh hidden set; cannot inherit this calibration.

## A17. Code, environment, audit, public-release
Git-versioned `src/echo_frb/search/`; env `env/requirements.lock`; experiment DB (`experiment_db.parquet`)
binds data hashes · config_hash · code_commit · seeds · outputs. 30 automated tests. Public release =
redistributable inputs/instructions only (no restricted telescope products).

---
**Known limitation carried forward:** scintillation/plasma propagation is suppressed (80%→36%) but not
eliminated — a bounded residual false positive (§11); decisive separation requires higher-resolution
data + the H-LP extension, not Catalog 2 alone.
