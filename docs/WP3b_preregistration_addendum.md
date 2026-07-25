# WP3b Preregistration Addendum — Blind Round 2 (`wp3-blind-v2` / `wp2-frozen-v2`)

**Status: targets SET, hashes PINNED — awaiting the PI's signature line in §7 and a git commit.**
All three target decisions were taken 2026-07-25 and are recorded in §3. `frozen_date` is set in both
configs and `frozen.analysis_config_sha16` = `a24f285e569e211e` is pinned, so the freeze contract now
passes. **Nothing has been drawn from pool 1.** W3b.8 is a separate, explicit act.

---

## 1. What is being tested, and why there is a round 2

Round 1 failed G2 (`docs/WP3_gate_memo.md`): the frozen v1 pipeline calibrated the candidate criterion
per **window** while the search reports a per-**burst** maximum over ~8 Tier-1 proposals, so the adverse
imitators passed at 25–70% against 1–10% targets. `wp2-frozen-v2` prices that multiplicity:

```
  candidate  ⟺  M_i > 0  AND  p_i^robust ≤ α        M_i = max_j T_ij,  α = 0.05
```

`M_i > 0` is **exactly** v1's criterion — verified on all 2,541 dev bursts with zero disagreements
(`scripts/wp3b_check_equivalence.py`) — so v2 is a strict tightening of v1, not a different analysis.
Cutting v2 nonetheless forfeits the v1 calibration (proposal §5.8 step 7); no WP2 number is inherited.

Round 2 asks one question: **does a calibration built on development, and shown to transfer to
validation, still hold on a genuinely untouched, source-disjoint set?**

## 2. Substrate — the last draw

Pool 0 is burned. Pool 1 is the final source-disjoint pool the catalog supports: **359 sources / 362
bursts / 17 multi-component**. Per §8.1 and §11, a second failure means **redesign at the methodology
level, not another draw**.

Mixture (verified to fit exactly; the controller now raises rather than truncating silently):

| class | items | distinct bursts |
|---|---:|---:|
| real_null | 180 | 180 (all 17 multi-component + 163 single) |
| injection | 140 | 140 |
| adverse | 280 | 40 (7 kinds × 40 hosts) |
| **total** | **600** | **360 of 362** |

## 3. Predetermined targets

Frozen before the controller draws. Derived from the validation dry run
(`docs/WP3b_dry_run_findings.md`), not chosen to pass.

### G1 — efficiency agreement
Observed v2 recovery on the hidden injections vs the predicted surface
(`wp3b_predicted_efficiency.parquet`, generated under v2 from the dev ensemble).

| check | target |
|---|---|
| marginal | \|obs − pred\| ≤ 0.07, and the observed 95% CI contains the prediction |
| cell agreement | ≥ 90% of cells with n ≥ 5 agree by **two-sample Wilson CI overlap** |
| signed bias | \|mean(obs − pred)\| ≤ 0.05 |
| μ-shape | **diagnostic, not gated** — the end-to-end criterion is legitimately non-monotonic in μ |

### G2 — false positives (gate on the point estimate; CI reported as resolution)

| class | n | target | validation dry run |
|---|---:|---:|---:|
| real_null | 180 | ≤ 0.01 | 0.0024 [0.0000, 0.0062] |
| deterministic (drift, diff-DM, chromatic echo, RFI remnant, overlapping) | 40/kind | **≤ 0.025** | max 0.0068 |
| differential_scattering | 40 | ≤ 0.10 | 0.0102 [0.0044, 0.0167] |
| **scintillation — GATED** | 40 | **≤ 0.10** | 0.0388 [0.0280, 0.0503] |
| real_null_multicomponent | 17 | **report-only** | 0.0000 (n=46) |

**Decisions taken 2026-07-25.** All three turn on the same fact: at n=40 per adverse kind the achievable
rates are 0, 0.025, 0.05, …, so a target below 1/n cannot be distinguished from zero and any single
false positive fails it. A gate set below its own resolution tests sampling noise, not the analysis —
and a second failure means redesign, not another draw.

> **Decision 1 — scintillation gated at ≤ 0.10.** Promoted from round 1's monitored ≤0.45. At the
> validated rate of 0.039 the expected count is ~1.6 of 40, so P(fail | analysis correct) ≈ **2%** at
> ≤0.10 versus ≈ **20%** at ≤0.05. §11's caveat stands: this *bounds* the plasma false positive, it does
> not claim H-P is excluded.

> **Decision 2 — gate on the point estimate**, CI reported as resolution. At n=40 the 95% Wilson upper
> bound is ~8.8% even with **zero** false positives, so gating on the interval would make a ≤1% target
> unattainable by construction — a perfect 0-for-40 result would fail. That is a broken gate, not a
> strict one. Round 1 reached the same conclusion at the same n.

> **Decision 3 — deterministic target relaxed 0.01 → 0.025.** At 0.01 the class is zero-tolerance, and
> across the five deterministic kinds the chance of tripping it on sampling noise alone — with an
> analysis behaving exactly as validated — is ≈ **33%** (`overlapping` contributes ~24% by itself at its
> validated 0.0068). 0.025 is "at most one of forty", the tightest statement n=40 can express, and keeps
> the class at effectively zero tolerance.

A machine-checked consequence: `test_every_gated_target_is_expressible_at_its_sample_size` asserts every
target is ≥ 1/n for its class, so a future edit cannot silently reintroduce a sub-resolution gate.

**Report-only, stated pre-scoring:** pool 1 holds **17** multi-component bursts. That stratum cannot
resolve a 1% rate, so it is reported with its interval and does not gate. The controller records the
drawn count in `hidden_commitment.json` so this is committed before anything is scored.

**PASS = G1(all) AND G2(all hard classes).**

## 4. What is frozen, and what selecting α did and did not use

| artifact | frozen how |
|---|---|
| analysis config `wp2-frozen-v2` | `frozen_date: 2026-07-25`; sha16 **`a24f285e569e211e`** pinned in the harness |
| margin scales `s_k` | measured on 6,749 dev proposals, in the config |
| α = 0.05 | in the config; the largest value meeting every target above on validation |
| calibration | 3-file artifact + `calibration_commitment.json`; the evaluator verifies the hash and **reconstructs, never refits** |
| predicted surface | generated under v2, committed before scoring |
| seed | sealed; recorded inside the labels, revealed only post-unblind |

**α was selected on the validation split.** That is legitimate — validation is design-side and was never
used for WP2 threshold selection — but it means the *choice* of α is not itself blind. Pool 1 tests it
out-of-sample, once. This is stated here rather than discovered later.

**Calibration fit on dev only.** Refitting on dev+validation would lower the resolvable-α floor from
0.023 to ~0.018, but would replace a calibration whose out-of-sample transfer was demonstrated with one
that has not been tested. Not done.

## 5. Known limits, recorded before scoring

1. **17 hard nulls in pool 1** — the multi-component FP cannot be resolved at the 1% level. Reported only.
2. **α ≥ 0.023** — `p = max(p_empirical, p_gpd)` cannot beat a cell's empirical floor `1/(n+1)`, and the
   174 dev multi-component nulls set that bound. α = 0.05 sits clear of it, so the operating point rests
   on the null sample rather than GPD extrapolation.
3. **`block_bootstrap` excluded** as an invalid null — it resamples blocks with replacement and so
   manufactures exact achromatic copies. Its rate is reported, not calibrated against.
4. **Scintillation is bounded, not excluded.** Plasma is not a finite model (§11).

## 6. Blind protocol (unchanged from round 1)

Sealed seed → labels hash-committed → scores hash-committed → unblind. `unblind` refuses unless both
commitments exist, the labels still hash to their commitment, and `labels_ts < scores_ts`. Quarantine
holds (23 TNS); the named candidates are **not** evaluated — that is WP4, after this gate.

## 7. Signature

Decisions 1–3 are fixed (§3) and both configs are frozen and pinned. What remains is the PI's signature
and a git commit of `config/wp2_analysis_config_v2.yaml`, `config/wp3_blind_config_v2.yaml`, this
addendum, and `calibration_commitment.json` — the commit is what makes the preregistration a
pre-commitment rather than a description. Only then run W3b.8.

```
PI: Nicholas Sledgianowski    Date: July 25, 2026
```

**Pinned at sign-off:**

| | |
|---|---|
| analysis config | `wp2-frozen-v2`, sha16 `a24f285e569e211e` |
| calibration manifest | sha256 `070b1900b4ce0579…` (75 cells, 26,962 null realizations) |
| α | 0.05 (resolvable floor 0.0229) |
| pool | 1 — 359 sources / 362 bursts / 17 multi-component. **The last draw.** |
