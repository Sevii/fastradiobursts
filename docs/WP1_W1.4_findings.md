# WP1 · W1.4 — Selection-Chain Reconciliation & Causal Decomposition (findings)

**Input to the W1.6 reproducibility matrix — not the final matrix.** Compares the two frozen W1
detection tracks over the same 340 multi-peak FRBs: the **literal** run (authors' code on Tier A) and
the **blind clean-room** (our code on our Tier B).

## 1. Per-stage selection funnels

Canonical funnel: `PROCESSED → SPIKE (ACF spike >3σ) → MATCH (pair ±2 ms) → CUTS (order / secondary
PSNR>10 / global-max) → DRIFT (K-S) → CANDIDATE`.

| Terminal stage | Literal (Tier A, their code) | Clean-room (Tier B, our code) |
|---|---:|---:|
| NO_SPIKE | 235 | 331 |
| NO_MATCH | 23 | 0 |
| CUTS | 60 | 1 |
| DRIFT | 11 | 6 |
| HARDNESS | 0 | 0 |
| CANDIDATE | **11** | **1** |
| EXCLUDED (noise_failed) | 0 | 1 |
| **spikes detected (≥1)** | **105 / 340** | **8 / 340** |

The literal funnel reproduces the authors' committed G_3 exactly (11 candidates = their list). The
clean-room detects an ACF spike in only **8** of 340 bursts vs the literal **105** — the funnels part
almost entirely at the very first stage.

## 2. Reconciliation

- Tracks agree on terminal stage for **235/340** (all mutual NO_SPIKE).
- Of the divergences, **102 are at the SPIKE stage**, only 3 at CUTS.
- Candidate overlap: **11 literal ∩ 1 clean-room = {FRB20190131D}**. 10 literal-only, 0 clean-room-only.
- All 10 literal-only candidates (incl. **FRB20211115A**) drop out in the clean-room at **NO_SPIKE** —
  they never reach the copy/drift test. The copy test is therefore *not* where the tracks disagree.

Artifacts: `candidate_selection_chain.parquet` (all 340, both tracks), `reconciliation_matrix.parquet`
(the 107 reaching ≥SPIKE in either track), `reconciliation_matrix.md`.

## 3. Causal decomposition — light-curve × ACF factorial

For each of the 11 flagged-in-either FRBs we crossed the two light curves (`LC_lit`=authors'
`process_data_ts`; `LC_cr`=our Tier B inverse-variance) with the two spike detectors
(`ACF_lit`=authors' `compute_autocorr_with_spikes`; `ACF_cr`=our normalized-ACF+3σ). Cell value =
a spike detected within ±2 ms of the expected delay.

| Cause | FRBs | Reading |
|---|---|---|
| **AGREE** (all 4 cells detect) | FRB20190131D | robust to both factors → the sole cross-track candidate |
| **ALGORITHM** (detector flips, LC doesn't) | FRB20190915E, 20200603B, 20210117D, 20210130C, 20220424C, 20221129B, 20221216A, 20230402B (8) | authors' detector finds the spike **even on our Tier B light curve**; our stricter detector does not |
| **MIXED** (both factors matter) | **FRB20211115A**, FRB20220225C (2) | spike survives **only** under authors' LC *and* authors' detector; our preprocessing *also* suppresses it |

**Attribution:** the literal-vs-clean-room divergence is **dominated by the spike-detection
algorithm/threshold**, not preprocessing. For 8 of 10 vanished candidates, the authors'
`compute_autocorr_with_spikes` (threshold=3 on its own ACF/smoothing) flags a spike that our
paper-faithful normalized-ACF-vs-Gaussian-baseline 3σ criterion does not — on the *same* light curve.
The paper's spike criterion is thus **under-determined**: the reported candidate list is highly
sensitive to the exact spike-detection implementation, a detail the paper does not fully pin down.

**FRB 20211115A** is additionally **preprocessing-sensitive** (MIXED): its 6.86 ms spike vanishes under
our Tier B light curve even with the authors' own detector. Combined with its absence under the authors'
**own SG_100** smoothing config (W1.0), it is fragile from three independent directions.

**FRB 20190131D** is detected in all four factorial cells → genuinely robust to both preprocessing and
detector choice; this is the one candidate that reproduces across fully independent implementations.

Artifacts: `decomposition_factorial.parquet` (per-cell), `decomposition_attribution.parquet` (2×2 grid).

## 4. Bottom line for the two named candidates (feeds W1.6)
- **FRB 20190131D — reproduces robustly.** Recovered by both tracks (same Δt≈8.82 ms, same peak pair
  [76,85]) and in all four factorial cells. Not sensitive to the identified degrees of freedom.
- **FRB 20211115A — fragile / not independently reproduced.** No significant ACF spike under the
  independent path; divergence attributed to *both* the spike-detection algorithm and our preprocessing;
  also absent under the authors' own SG_100 config. Its candidacy depends on specific, under-documented
  choices rather than on a robust achromatic-copy signal.

*Caveat:* this does not declare the clean-room "correct" and the authors "wrong." It quantifies that the
paper's spike-detection step is under-specified and that the candidate list — FRB 20211115A especially —
is sensitive to it. The full smoothing-config + version sweep is W1.5; the assembled matrix is W1.6.
