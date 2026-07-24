# Project ECHO-FRB — WP3 Blind-Validation Report (Round 1)

**Verdict: GATE FAIL.** Per proposal §8.1, **the WP4 catalog-wide search does not run.** The frozen
`wp2-frozen-v1` pipeline must be revised, a new analysis version cut, and a **fresh, source-disjoint**
hidden set (pool 1) evaluated before Authorization C can be recommended.

**The blind gate did its job:** it revealed that the pipeline's *real* end-to-end false-positive rate on
adverse imitators — as the catalog search will actually experience it — is far higher than WP2's
development benchmark implied. The failure is decisive and substantive (G2), not a metric artifact.

---

## 1. What was tested
The **frozen** analysis pipeline (`wp2-frozen-v1`, `sha256[:16]=3712e96faa969fcc`, unchanged) was run
**blind** on a hidden mixture drawn from the **sealed test-split pool 0** (source-disjoint from all WP2
design data). Decision per item = end-to-end **full criterion** (Tier-1 triage → χ²_copy → robustness →
candidate/not), exactly as WP4 would run. Predetermined targets: `docs/WP3_preregistration_addendum.md`.

## 2. Blind audit trail (discipline verified)
| Event | UTC | Hash |
|---|---|---|
| Labels sealed + committed | 2026-07-24T05:40:00Z | labels `c8066d2a…` |
| Scores committed | 2026-07-24T05:40:26Z | scores `5bdfcb91…` |
| Frozen analysis config (both commitments) | — | `3712e96faa969fcc` |

`unblind` verified: labels **untampered** (hash matches), **`labels_ts < scores_ts`** (no peeking), freeze
held. Artifacts: `docs/wp3_round1_artifacts/{hidden,scores}_commitment.json`. Controller seed `8675309`
(sealed; revealed here post-unblind).

## 3. Revealed mixture (880 items, pool 0)
| Class | n | Composition |
|---|---:|---|
| Lensed injections (+) | 300 | achromatic copies, frozen (Δt,μ) grid, μ oversampled low |
| Real nulls (−) | 300 | real test bursts, no injection (incl. all 79 multi-component of pool 0) |
| Adverse (−) | 280 | 7 imitator kinds × 40, μ=0.5 |

## 4. G1 — recovery vs predicted efficiency: **AGREES** (pre-registered metric mis-fired)
- **Marginal:** observed full-criterion efficiency **0.457** vs predicted **0.474** → |Δ|=0.017 ≤ 0.07,
  CIs overlap. **PASS.**
- **Per-cell agreement:** observed injection recovery tracks the predicted (non-monotonic) surface —
  by μ: 0.03 / 0.27 / 0.54 / 0.75 / 0.66 / 0.75 / 0.63 (μ=0.1…0.9), matching the prediction's shape.
- **Coverage metric caveat:** the *pre-registered* coverage metric (observed point inside the
  **predicted** 95% CI) read **0.21** and mechanically flagged G1 fail — but that is a **metric
  mis-specification**, not a disagreement: the predicted cell CIs are tight (~260 dev injections/cell)
  while observed cells are noisy (~10/cell), so a noisy observed point often falls outside a tight
  predicted CI even under true agreement. The correct **two-sample** test (observed CI overlaps predicted
  CI) gives **0.958** consistency over 24 populated cells (≥ 0.90). **Efficiency agreement is met.**
  → *Revision item:* the G1 coverage metric must be a two-sample CI-overlap (or combined-uncertainty)
  test. This does **not** change the verdict (G2 fails hard regardless).

## 5. G2 — false positives: **FAIL** (the decisive result)
Full-criterion FP (candidate flagged on a null item), end-to-end, on the hidden test set:

| Null class | FP (test) | target | role | result |
|---|---:|---:|---|---|
| real_null (all morphology) | 0.003 (1/300) | ≤0.01 | hard | ✅ pass |
| real_null multi-component | 0.000 | ≤0.05 | monitored | ✅ |
| drift | 0.000 | ≤0.01 | hard | ✅ |
| differential_dm | 0.000 | ≤0.01 | hard | ✅ |
| chromatic_echo | 0.000 | ≤0.01 | hard | ✅ |
| rfi_remnant | 0.000 | ≤0.01 | hard | ✅ |
| **differential_scattering** | **0.250 (10/40)** | ≤0.10 | hard | ❌ **over** |
| **overlapping** | **0.600 (24/40)** | ≤0.01 | hard | ❌ **over** |
| **scintillation** | **0.700 (28/40)** | ≤0.45 | monitored | ❌ **escalated (>0.60, §11)** |

**Real complex nulls and every deterministic artifact are still cleanly rejected** (≤0.3%). The failure
is concentrated in the **propagation-like** imitators (scintillation, differential scattering) and
**overlapping** short-delay copies.

## 6. Root cause — multi-proposal "any-passes" inflation (confirmed on dev)
WP2's W2.7 benchmark scored a **single oracle window** `(c, c+8)`. The real pipeline (and WP4) flags a
burst if **any** of its Tier-1 proposals (mean ≈ 8/burst here) passes the full criterion. Re-running the
identical adverse generation **end-to-end vs oracle on development hosts** isolates the effect:

| kind | oracle FP (≈ WP2 W2.7) | **end-to-end FP** | WP2 dev ref |
|---|---:|---:|---:|
| scintillation | 0.275 | **0.550** | 0.36 |
| overlapping | 0.000 | **0.700** | — |
| differential_scattering | 0.075 | **0.125** | 0.08 |
| drift / diff-DM / chromatic / RFI | 0.000 | 0.025–0.075 | 0.00 |

The oracle single-window FP reproduces WP2's benchmark; the **end-to-end multi-proposal search roughly
doubles-to-∞ the adverse FP** because ~8 windows each get a chance and the burst is flagged if any one
passes. WP2's benchmark was **optimistic** — it did not model the per-burst look-elsewhere within the
Tier-1 proposal set. On the test hosts the effect is at least as large (scintillation 0.55→0.70).

Two secondary contributors, both fixable:
- **overlapping** was injected at Δt=3 bins (≈2.95 ms), which is *inside* the frozen search domain
  (Δt_min=2 ms). So Tier-1 correctly finds a real short-delay copy and flags it — partly a **definitional
  artifact** of the adverse generator (it should inject *below* Δt_min to be a clean "unresolved" adverse
  case). *Revision item.*
- scintillation on the test hosts (0.70) exceeds even dev end-to-end (0.55) — a genuine dev→test worsening
  of the propagation residual, consistent with §11 (plasma propagation is not decisively rejectable on
  Catalog 2 alone).

## 7. Verdict and required revisions (before a fresh hidden set)
**GATE FAIL → WP4 blocked (§8.1).** The pipeline does not control the adverse false-positive rate that
the catalog-wide search will actually experience. Required before re-validation on **pool 1**:
1. **Control the per-burst multi-proposal look-elsewhere** — the substantive fix. Options: take only the
   single best-triage proposal to Tier-2; apply a per-burst trials penalty to the criterion; or tighten
   the per-proposal robustness so the adverse FP survives an ~8-proposal search. This is an analysis
   change → **new analysis version** (`wp2-frozen-v2` / `wp3-blind-v2`), forfeiting this calibration
   (§5.8 step 7).
2. **Fix the G1 coverage metric** to a two-sample CI-overlap test (efficiency agreement itself is fine).
3. **Fix the overlapping adverse generator** to inject below Δt_min (a clean unresolved-echo adverse case).
4. Re-freeze, then draw a **fresh, source-disjoint** hidden set from **pool 1** (pool 0 is now burned).
   A 2nd failure ⇒ redesign, not another draw.

**Positive findings carried forward:** the blind machinery, freeze contract, and commitment discipline
all worked; efficiency agreement (G1) is met; real complex nulls and deterministic artifacts are rejected
end-to-end. The gap is specifically the multi-proposal adverse-FP control — now measured, not guessed.
