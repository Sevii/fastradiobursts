# WP1 Reproduction Note — Project ECHO-FRB

**Reproduction target:** Zhou et al. 2026, "Evidence for Intermediate-Mass Black Holes From
Microlensing Signatures in CHIME/FRB Catalog 2" (arXiv:2605.19653); code
`github.com/Huan-Zhou-spec/MICRO-FRB` @ pinned commit `c4fbfca`.
**Scope (preregistered for WP1):** detection + selection reproduction, including the two named
candidates' delays and magnification — **not** lens masses, redshifts, or f_PBH (those are WP5).
**Deliverables:** `docs/reproducibility_matrix.md` (+ `.parquet`), this note, and
`docs/candidate_reproduction_report.md`.

## 1. Method
Three independent lines of evidence over the same 340 multi-peak Catalog 2 bursts:
1. **Literal** — the authors' pipeline run unmodified on our sealed Tier A data (byte-identical to the
   CANFAR release; verified W1.1) in a reconstructed, pinned environment.
2. **Blind clean-room** — an independent re-implementation from the paper's equations/thresholds only,
   built by an implementer kept blind to the authors' code, run on our standardized Tier B products.
3. **Reconciliation + sensitivity** — per-stage selection-funnel reconstruction, a light-curve × ACF
   causal decomposition, and a comprehensive one-axis-at-a-time sensitivity sweep.

## 2. Literal reproduction — EXACT
Running `SearchLensedFRB.py` unmodified (seed=42) reproduces the authors' committed outputs
**value-for-value** across **all three** of their smoothing configurations:

| Config | Authors' committed | Our literal run |
|---|---:|---:|
| G_3 (Gaussian σ=3) | 11 candidates | **11** (identical list, delays, drift flags) |
| SG_20 (Sav-Golay w=20) | 16 | **16** (identical) |
| SG_100 (Sav-Golay w=100) | 12 | **12** (identical) |

Every reproducible reported statistic in the matrix is **EXACT** on the literal track (12/12; the rest
are out-of-scope or a subjective step). **The published pipeline reproduces exactly from public data.**

## 3. Independent (clean-room) reproduction — partial
The blind clean-room, on our independent preprocessing, flags **1 candidate (FRB 20190131D)** vs the
literal 11. The two named candidates diverge sharply:
- **FRB 20190131D — reproduced.** Detected with Δt=8.847 ms (vs 8.82; within one 0.983 ms bin), the same
  matched peak pair [76,85], and an achromatic K-S result. **EXACT** on all four of its matrix rows.
- **FRB 20211115A — not reproduced.** No significant ACF spike arises on our Tier B at any threshold, so
  it never reaches the copy test. **NOT** on all four of its rows.

## 4. Where and why the tracks diverge (fully attributed)
- **Funnels:** literal 340→105 spikes→11 candidates; clean-room 340→8 spikes→1. **102 of 105
  divergences occur at the very first (SPIKE) stage** — the copy/drift test is never where they disagree.
- **Causal decomposition (light-curve × ACF factorial):** the divergence is **dominated by the
  spike-detection algorithm/threshold**. For 8 of the 10 vanished candidates the authors' detector finds
  the spike *even on our light curve*, while our paper-faithful 3σ criterion does not. FRB 20211115A is
  **MIXED** — our preprocessing *also* suppresses its spike.
- **Sensitivity sweep (20 configs):** the reported candidate count swings from **22 (kσ=2) to 3 (kσ=4)**
  and 11↔16 across smoothing/drift choices. **Only FRB 20190131D is robust across all 20 configurations;
  FRB 20211115A drops under SG_100 and kσ=4** and is never recovered by the clean-room.

**Interpretation:** the paper's spike-detection criterion is **under-determined** — the candidate list
is governed by one under-documented implementation choice. This is not a claim that either
implementation is "correct"; it quantifies the fragility of the reported selection.

## 5. Reproducibility hazards found in the target
- **Two undeclared dependencies** (`colossus`, `statsmodels`) — the package will not import without them.
- **No license**, no `requirements.txt`, no pinned versions.
- **Smoothing method is a hard-coded source toggle** (comment/uncomment inside `detect_autocorr_spikes`),
  not a parameter — yet it changes the candidate count (11/16/12).
- **Hard-coded parameters and relative paths** in `__main__`; script runs on import (no `__main__` guard).
- **Headline results are hard-coded, not regenerated** (`fpbh.py`, `Hardness_test.py` embed the lens
  masses / f_PBH and a non-final candidate's peak indices).
- **Candidate list is smoothing-config-dependent**, and FRB 20211115A is absent under the authors' own
  SG_100 config.

## 6. Bottom line
- **FRB 20190131D** is a robust reproduction: recovered by the authors' code and by a fully independent
  implementation, across every preprocessing/detection choice tested. It warrants continued attention.
- **FRB 20211115A** is fragile: its candidacy depends on the authors' specific smoothing + preprocessing
  + a permissive spike threshold, and it fails independent reproduction. It should **not** be treated as
  a robust candidate on catalog data alone.
- **Methodologically**, autocorrelation-spike screening is highly sensitive to an under-specified
  detection step — direct motivation for the two-dimensional, noise-weighted copy statistic ECHO-FRB
  develops in WP2.

## 7. Gate readiness (preliminary — formal memo in W1.7)
The WP1 gate asks that reported candidates and intermediate statistics be **reproduced or the
discrepancies fully explained**. Both hold: the literal reproduction is **exact**, and every
independent-analysis discrepancy is **traced to a specific cause** (spike-detection threshold /
preprocessing) and quantified. WP1 therefore **supports passing the gate**, with the explicit,
documented caveat that **FRB 20211115A is fragile**. Per proposal §8.1 this is a "reproduced" outcome,
not a stop condition. Formal gate memo, env locks, and test suite: W1.7.
