# WP3b — Validation Dry Run: Findings and Go/No-Go Verdict

**Date:** 2026-07-25. **Plan:** `docs/WP3b_plan.md`. **Analysis:** `wp2-frozen-v2` (draft).
**Verdict: GO** — efficiency at the operating point clears the pre-registered floor out-of-sample.
**Pool 1 is NOT yet spent.** W3b.8 requires the PI's signature on the round-2 addendum first.

---

## 1. What was run

| step | substrate | result |
|---|---|---|
| W3b.1 margin statistic `T_ij` / `M_i` | 2,541 dev bursts | `M_i > 0` == v1 `is_candidate` on **every** burst, 0 disagreements |
| W3b.2 scale constants `s_k` | 6,749 dev proposals | frozen into `config/wp2_analysis_config_v2.yaml` |
| W3b.3 `overlapping` generator fix | — | now injects at 2 bins ≈ 1.97 ms, **below** the Δt ≥ 2 ms floor |
| W3b.4 null ensembles | dev | **29,334** complete end-to-end realizations, 12 families, 0 errors |
| W3b.5 conditional calibration | dev | stratified empirical + GPD tail, source-cluster bootstrap |
| W3b.6 dry run | **validation (835 bursts / 46 multi)** | fit on dev, evaluated out-of-sample |

The equivalence check is the load-bearing one: v2 is a *calibrated tightening* of v1, not a different
analysis. `scripts/wp3b_check_equivalence.py` asserts it on real data; 29 unit tests assert it on
synthetic. Both the frozen v1 config and the v2 config produce identical v1 decisions (the scale
constants cannot move a sign).

---

## 2. The operating point

α is the largest value meeting every pre-registered false-positive target simultaneously. On the
validation dry run that is **α = 0.05**: at α = 0.10 the deterministic imitators reach 1.6%, breaching
their ≤ 1% target.

### Out-of-sample results at α = 0.05

Decision rule: `M_i > 0` **AND** `p_i^robust ≤ 0.05`.

| family | n | sources | v1 (round-1 rule) | **v2** | 95% cluster CI | target |
|---|---:|---:|---:|---:|---|---:|
| real | 835 | 710 | 0.0120 | **0.0024** | [0.0000, 0.0062] | ≤ 0.01 ✅ |
| real_multicomponent | 46 | 27 | 0.0000 | **0.0000** | [0.0000, 0.0000] | reported, not gated |
| adverse_drift | 1171 | 363 | 0.0009 | **0.0000** | [0.0000, 0.0000] | ≤ 0.01 ✅ |
| adverse_chromatic_echo | 1177 | 363 | 0.0042 | **0.0008** | [0.0000, 0.0026] | ≤ 0.01 ✅ |
| adverse_rfi_remnant | 1181 | 362 | 0.0034 | **0.0008** | [0.0000, 0.0026] | ≤ 0.01 ✅ |
| adverse_differential_dm | 1179 | 363 | 0.0059 | **0.0017** | [0.0000, 0.0053] | ≤ 0.01 ✅ |
| adverse_overlapping | 1181 | 363 | 0.1321 | **0.0068** | [0.0025, 0.0118] | ≤ 0.01 ✅ |
| adverse_differential_scattering | 1178 | 363 | 0.1350 | **0.0102** | [0.0044, 0.0167] | ≤ 0.10 ✅ |
| adverse_scintillation | 1185 | 363 | 0.2776 | **0.0388** | [0.0280, 0.0503] | now gated — §5 |
| **efficiency, μ ≥ 0.5** | 507 | 293 | 0.6982 | **0.4458** | **[0.3980, 0.4938]** | **≥ 0.30 ✅** |
| efficiency, all μ | 1182 | 363 | 0.5525 | **0.2995** | [0.2696, 0.3280] | — |

### The round-1 failure, measured against the fix

| imitator | WP3 round 1 (blind, end-to-end) | **WP3b validation @ α=0.05** |
|---|---:|---:|
| scintillation | 0.70 | **0.039** |
| overlapping | 0.60 | **0.007** |
| differential scattering | 0.25 | **0.010** |

Two mechanisms contribute, and they are separable. The `overlapping` collapse is largely W3b.3: at
Δt ≈ 2.95 ms the old control sat *inside* the search domain, so the pipeline was detecting a real
short-delay copy rather than producing a false positive. Scintillation and differential scattering are
the multiplicity penalty doing its job — those injections are unchanged.

### The price

The multiplicity penalty costs **69.8% → 44.6%** detection efficiency at μ ≥ 0.5. That is the honest
cost of pricing ~8 within-burst looks, and it was always the expected outcome (`SecondWP3Approach.md`,
"Main limitation"). Per-μ, out-of-sample:

| μ | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.7 | 0.9 |
|---|---:|---:|---:|---:|---:|---:|---:|
| v1 | 0.053 | 0.277 | 0.584 | 0.780 | 0.811 | 0.764 | 0.521 |
| **v2 @ α=0.05** | 0.020 | 0.069 | 0.224 | 0.403 | **0.524** | **0.506** | **0.308** |

The non-monotonic turnover at μ = 0.9 is the known v1 behaviour (robustness is stricter for
equal-brightness copies), not a v2 artifact.

### Dev vs validation agreement

Efficiency at μ ≥ 0.5: dev 0.4442, validation 0.4458. Scintillation FP: dev 0.0418, validation 0.0388.
The calibration transfers out-of-sample — which is what the dry run existed to test, and what round 1
failed to do.

---

## 3. Finding: `block_bootstrap` is not a valid null for a copy test

`nulls/surrogate.py:block_bootstrap` resamples contiguous time blocks **with replacement**, so it can
place the same block twice and thereby **manufacture an exact achromatic copy** — precisely the signal
under test. The evidence is unambiguous: among its 170 dev "false positives", the *median* per-band
delay spread is exactly 0 (the ceiling of the margin), and 45 are exact-copy detections on both delay
and magnification.

It is therefore **excluded from the calibrating families**. Under `p^robust = max_h p_h` a broken null
would silently set the threshold for every other family — the family with the most spurious passes wins
the max. Its rate is still reported (4.67% at α=0.05) for transparency.

`tf_permutation` (0.48%) and `phase_randomization` (0.00%) are unaffected: both permute rather than
resample with replacement, so neither can duplicate a block.

This does not affect any WP2 or WP3 round-1 conclusion — those used surrogates as a per-proposal null
where the effect is diluted, not as a max-statistic calibrator.

---

## 4. Finding: the hard-null supply, not the estimator, limits how small α can be

`p = max(p_empirical, p_gpd)` never returns less than a cell's empirical floor `1/(n+1)`. The
`real_multicomponent` family has **174 dev realizations** — every multi-component burst in the
development split — so its floor is 1/175 = 0.0057, and with the pre-registered 4× headroom the
**smallest α this calibration can evidence is 0.023**.

Rows below that in the operating curve are sample-size artifacts, not results: at α = 0.005 the
apparent 0% efficiency simply means no burst can clear a floor it is beneath. The curve labels them
`resolvable = False`.

The first attempt used `min_stratum_n = 50`, which produced cells with floors of 1/51 = 0.0196 and an
efficiency cliff at α = 0.01 that looked like a real collapse. It was not. `min_stratum_n` is now 200,
tied to α by `min_stratum_n ≥ factor/α − 1`, and `Calibration.min_resolvable_alpha()` reports the bound
so the artifact cannot be mistaken for a finding again.

**Consequence:** conditioning must stay coarse. We cannot both condition finely and resolve a small α on
174 hard nulls. The chosen α = 0.05 sits comfortably above the 0.023 bound, so the operating point is
supported by the null sample rather than by tail extrapolation — the GPD is not doing load-bearing work
at this α, which is the honest place to be.

---

## 5. Open items for the PI (both must be settled before W3b.8)

1. **A numeric target for scintillation.** It was promoted from monitored residual to gated family (PI
   decision, 2026-07-24), but no number was ever set — round 1 only *monitored* it at ≤0.45 / escalate
   >0.60. The dry run gives 0.0388 [0.0280, 0.0503]. A target of **≤ 0.10** is proposed: it is met with
   large margin out-of-sample, and it is a genuine strengthening over round 1. §11's caveat stands — this
   bounds the plasma false positive, it does not claim H-P is excluded.
2. **Whether the ≤ 0.01 deterministic target is gated on the point estimate or the CI.** Round 1 gated
   on the point estimate (Wilson upper was too strict at n=40/kind). `overlapping` gives 0.0068 with a
   cluster-CI upper of 0.0118, which passes on the point estimate and fails on the interval. Round 2's
   n per adverse kind is 40 — the same regime — so the round-1 convention (point estimate, CI reported)
   is proposed for consistency.

---

## 6. Recommendation

**GO.** Proceed to W3b.7 (freeze `wp2-frozen-v2` with α = 0.05, fix the G1 coverage metric, resize the
round-2 mixture for pool 1) and then W3b.8, the single blind round on pool 1.

Two limits must be carried into the round-2 report rather than discovered afterwards:

- **Pool 1 has 17 multi-component bursts.** The hard-null stratum cannot resolve a 1% FP; it will be
  reported with its interval and explicitly not gated. This is recorded now, pre-scoring.
- **α = 0.05 was selected on the validation split.** That is legitimate — validation is design-side —
  but it means the *choice* of α is not blind. Pool 1 tests whether an α chosen there holds out-of-sample
  on a genuinely untouched, source-disjoint set. That is the only remaining unblinded question, and it is
  a one-shot test: a second failure means redesign, not another draw (§8.1 / §11).

**Artifacts.** popos `~/frb_catalog2_prep/wp3b/`: `null_ensemble_{development,validation}.parquet`,
`curve_{dev,validation}/{scored,operating_curve,calibration_cells}.parquet`,
`equivalence_development{,_v2}.parquet`, `proposals_development.parquet`, `margin_scales.{parquet,yaml}`.
Code `src/echo_frb/search/margin/`, scripts `scripts/wp3b_*.py`, tests `tests/test_wp3b_*.py` (54 pass).
