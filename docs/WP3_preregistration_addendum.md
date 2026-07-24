# Project ECHO-FRB — WP3 Preregistration Addendum (predetermined blind-gate targets)

**Analysis version (frozen, unchanged):** `wp2-frozen-v1` · **config**
`config/wp2_analysis_config.yaml` · **sha256[:16]** `3712e96faa969fcc`.
**WP3 harness version:** `wp3-blind-v1` · **config** `config/wp3_blind_config.yaml`.
**Frozen:** 2026-07-23 — **before** any hidden item is drawn or scored.

This addendum extends the WP2 preregistration (`docs/WP2_preregistration.md`, item A10/A11)
with the **predetermined pass/fail arithmetic** for the WP3 blind-injection gate. It changes
**no** analysis code and **no** threshold in `wp2-frozen-v1` — it only records what "recovery
agrees with predicted efficiency and predetermined false-positive targets" (proposal §8, WP3
row) means, fixed in advance so the hidden results cannot shape the criterion (§5.8 step 4).
Any change to the numbers below after the hidden set is scored creates a new analysis version
and forfeits this calibration (§5.8 step 7).

> **Correction carried in:** the WP2 progress note labeled the frozen config hash `e614642f`;
> that was the W2.0-era hash recorded before `candidate_criterion`/`robustness_tolerances`
> were added in W2.7/W2.9. The config is **unchanged since commit `8c253b2` ("Completed WP2")**
> and its true `sha256[:16]` is `3712e96faa969fcc`. The freeze contract asserts the latter.

## 1. Substrate and blinding (fixed)
- **Data:** ONLY the sealed **test** split sources (736 sources / 1140 bursts;
  `source_split.parquet`, `split=="test"`), never used in WP2 threshold/null design. Quarantine v2
  (23 TNS) excluded. Development / validation are off-limits to the hidden mixture.
- **Blind-round pools:** test sources partitioned into **K=2** disjoint pools (salt
  `echo-frb-wp3-blind-v1`, source-level). Round 1 = pool 0 (the larger, multi-component-richer pool;
  ~771 bursts / 79 multi-component), a failed gate re-does on pool 1 (source-disjoint — §5.8 step 5).
  K=2 not 3: the whole test split holds only **96 multi-component bursts**, and repeaters make finer
  partitions too small/uneven. After **2** failures: redesign at the methodology level, not another
  draw (finite catalog; §8.1, §11).
- **Blind separation:** sealed controller seed; `hidden_labels.parquet` hash-committed
  (`hidden_commitment.json`) **before** scoring; `hidden_scores.parquet` hash-committed **before**
  unblinding. `unblind` refuses unless both commitments exist, labels are untampered, and
  `labels_ts < scores_ts`.

## 2. Hidden mixture (fixed recipe; counts revealed only post-unblind)
| Class | Truth | Count | Draw |
|---|---|---:|---|
| Lensed injections (achromatic delayed copies) | + | 300 | frozen `(Δt, μ)` grid, μ oversampled near threshold (weights `[.20,.20,.18,.15,.12,.09,.06]` over μ=`[.1,.2,.3,.4,.5,.7,.9]`) into real single-component test hosts (hosts reused across grid points) |
| Unlensed real nulls | − | 300 | real test bursts run end-to-end, NO injection = catalog-representative FP; draw prioritizes the scarce multi-component bursts (all ~79 in pool 0) then fills with single-component real bursts |
| Adverse imitators (7 kinds) | − | 7×40=280 | drift · differential_dm · differential_scattering · chromatic_echo · scintillation · overlapping · rfi_remnant, μ=0.5, into real test hosts (disjoint from the null & injection hosts) |

Total ≈ **880** items/round. Every item is materialized as an opaque Tier-B-shaped h5; the manifest
carries only `item_id` + host public features — no truth, no injection parameters. The three classes
use **disjoint** underlying bursts so item decisions are independent.

## 3. Predicted efficiency (the prediction G1 is judged against)
The prediction is the **full-criterion, END-TO-END** efficiency surface
`ε_pred(μ, host S/N)` produced by `blind/predict.py` on the **development** split with the SAME
`run_frozen_chain` the blind evaluator uses (Tier-1 triage included). It is generated and committed
**before** the hidden set is scored → `wp3_predicted_efficiency.parquet` (+ `_surface.parquet`).
Because it is end-to-end, its marginal may be ≤ the WP2 tier2-only figure (0.79) — that is the
honest prediction, not a regression.

## 4. G1 — recovery agrees with predicted efficiency (PASS conditions, ALL required)
Evaluated on the hidden **injections** only, decision = full-criterion `is_candidate`.
1. **Marginal:** `|ε_obs − ε_pred|` ≤ **0.07**, where `ε_pred` is the predicted surface
   marginalized over the hidden set's realized `(μ, S/N)` cell counts; **and** the observed and
   predicted 95% Wilson CIs overlap.
2. **Surface coverage:** in populated `(μ, S/N)` cells with ≥ **5** hidden injections, ≥ **90%**
   have `ε_obs` inside the predicted cell's 95% Wilson CI.
3. **No systematic bias:** mean signed `(ε_obs − ε_pred)` over scored cells within **±0.05**.

**μ-shape is a reported diagnostic, NOT a pass-condition.** The dev prediction (generated pre-unblind)
shows the frozen full end-to-end criterion is **non-monotonic in μ**: robustness legitimately rejects a
fraction of near-equal-brightness (μ→1) copies, so ε(μ) peaks near μ≈0.6–0.7 and dips at μ=0.9 (full
criterion: 0.04→0.55; the *copy*-criterion alone stays monotonic 0.18→0.95). An absolute-monotonicity
requirement would therefore fail a result that correctly *agrees* with the prediction. G1 tests
agreement (marginal + cell coverage + bias); we report `mu_shape_max_dev = max_μ|ε_obs(μ) − ε_pred(μ)|`
as a shape-agreement diagnostic. **Provenance:** this criterion was corrected on the **development**
prediction, before any hidden item was scored (permitted — §5.8 freezes before the *hidden* set; the
dev prediction is design-set use). The frozen analysis pipeline is untouched — only the WP3 gate
arithmetic was refined.

## 5. G2 — false positives meet predetermined targets (PASS conditions)
Evaluated on the hidden **null** classes, decision = full-criterion `is_candidate` (a candidate on
a null item = a false positive). The gate is on the **observed FP rate (point estimate) ≤ target**;
the 95% Wilson CI is **reported** as the statistical resolution, not used as the gate — with a finite
per-class item budget (e.g. 40 per adverse kind) the Wilson upper bound at 0 FP already exceeds a 1%
target, so gating on it would make even a perfect 0-FP result unpassable. A broken pipeline shows a
large point-estimate excess, which the point gate catches; tighter FP bounds come from the larger
WP4 null run (global significance). Targets:
| Null class | FP upper-bound target | WP2 (dev) reference | Gate role |
|---|---:|---:|---|
| Real nulls, ALL morphology | **≤ 1%** | 0% | **hard** (catalog-representative FP) |
| Real nulls, multi-component subset | ≤ 5% expected | 0% | **monitored** (H-I stress; small n → wide CI) |
| Deterministic adverse: drift, differential_dm, chromatic_echo, rfi_remnant, overlapping | **≤ 1%** each | 0% | **hard** |
| differential_scattering | **≤ 10%** | 8% | **hard** (near-deterministic) |
| scintillation | ≤ 45% expected | 36% | **monitored, NOT a gate fail**; > 60% escalated to PI (§11) |

## 6. Gate verdict (predetermined)
**PASS = G1 (all four) ∧ G2 (all hard classes),** with scintillation within its monitored bound.
**FAIL** on any hard condition → revise the pipeline → **new analysis version** → **new,
source-disjoint** hidden set from the next pool. **Per §8.1, WP4 (catalog search) does not run on a
failed gate.** Scintillation exceeding 45% (but ≤ 60%) widens the documented §11 limitation and is
reported, not failed; exceeding 60% is escalated as evidence the propagation residual is worse
out-of-sample than modeled.

## 7. What WP3 does NOT do
- Does not evaluate the named candidates (FRB 20190131D / 20211115A) — that is WP4, after this gate
  passes (§5.8 step 6).
- Does not tune, add, or remove any statistic, threshold, or robustness tolerance.
- Does not touch the development or validation splits for the hidden set (only for the frozen
  prediction, which is legitimate design-set use).

**Signed (PI):** _pending_ · **Timestamp of freeze:** 2026-07-23.
