# WP1 · W1.5 — Controlled Sensitivity Analysis (findings)

**Input to the W1.6 reproducibility matrix.** Comprehensive one-axis-at-a-time sweep of the literal
pipeline off the frozen G_3 config (17 literal runs) plus a clean-room spike-threshold sweep (3 runs),
over the 340 multi-peak FRBs. Smoothing method is switched by a **clean parameter** (a faithful
single-source re-implementation of the authors' detector), **never** by editing/commenting source.

## 1. All three committed smoothing configs reproduce EXACTLY
Via the parameterized detector (`sensitivity/smoothing.py`):

| Config | Ours | Authors' committed | Match |
|---|---:|---:|:--:|
| G_3 (Gaussian σ=3) | 11 | 11 | ✅ |
| SG_20 (Sav-Golay w=20) | 16 | 16 | ✅ |
| SG_100 (Sav-Golay w=100) | 12 | 12 | ✅ |

Extends the W1.2 exact-reproduction from G_3 to **all three** configs. (Reproducibility note: the
authors switch these by commenting/uncommenting one line in `detect_autocorr_spikes`; we replaced that
with a parameter and confirmed identical results.)

## 2. The candidate list is dominated by the spike threshold and smoothing

| Axis | Values → candidate count |
|---|---|
| **spike threshold kσ** | 2→**22**, 2.5→16, **3→11**, 3.5→6, 4→**3** |
| **smoothing method** | G_3→11, SG_20→16, SG_100→12 |
| drift cut `min_diff_threshold` | 0.05→11, 0.1→11, 0.2→16 |
| Gaussian σ | 2→12, 3→11, 5→13 |
| rfi_factor | 2→12, 3→11, 4→10 |
| f_down | 16→11, 32→11, 64→12 |
| n_noise | 20→11, 30→11, 40→11 |

The reported candidate count swings from **22 to 3** across a plausible spike-threshold range and
**11↔16** across smoothing/drift choices — confirming the W1.4 diagnosis that the result is governed by
the under-specified spike-detection step. `n_noise` and `f_down` are nearly inert.

## 3. Per-candidate stability — only ONE named candidate is robust

Across the 17 literal configs, **22 distinct FRBs** appear as a candidate in ≥1 run; 13 of them in only
a single (permissive-threshold) run. Survival fraction (fraction of literal runs in which an FRB is a
candidate):

| FRB | survival | note |
|---|---:|---|
| **FRB20190131D** | **1.00 (17/17)** | named candidate — robust |
| FRB20220424C | 1.00 (17/17) | robust in literal, but NOT found by the clean-room |
| FRB20190915E | 0.94 | |
| FRB20210130C / **FRB20211115A** / FRB20220225C / FRB20221129B | 0.88 | **20211115A drops in SG_100 & kσ=4** |
| …down to… | 0.06 | 13 FRBs candidate in exactly one run |

Only **FRB20190131D** and FRB20220424C survive **all** literal configs. Of the two, only
**FRB20190131D** is also recovered by the fully independent clean-room.

## 4. Clean-room spike-threshold sweep (closes the W1.4 loop)
Loosening the clean-room `spike_nsigma` 3.0→2.5→2.0 keeps the clean-room candidate count at **1**
(FRB20190131D) throughout. At the loosest (2.0) it *surfaces* an ACF spike for **6 of the 11** G_3
candidates, but **none** convert to a candidate (they fail the downstream match/cut/copy tests). The
remaining **5 of 11 — including FRB20211115A — have zero ACF spikes at any threshold** on our Tier B
light curve: a genuine preprocessing-level absence, not a threshold effect. This confirms the W1.4
attribution (algorithm-dominated, with FRB20211115A additionally preprocessing-suppressed).

## 5. Bottom line for the two named candidates (feeds W1.6)
- **FRB 20190131D — robust.** Candidate in **all 20** configurations swept (17 literal axes + 3
  clean-room thresholds): every smoothing method, spike threshold kσ∈[2,4], preprocessing variant, and
  the independent implementation. The one result that survives everything.
- **FRB 20211115A — fragile.** Drops under SG_100 and kσ=4; never recovered by the clean-room at any
  threshold (no ACF spike on our Tier B). Its candidacy is contingent on the authors' specific
  smoothing + preprocessing + a permissive threshold.

Artifacts (popos `~/frb_catalog2_prep/wp1_repro/sensitivity/`): `sensitivity_matrix.parquet`
(FRB × 20 configs → is_candidate), `candidate_stability.parquet`, `sweep_literal_long.parquet`,
`sweep_cleanroom_long.parquet`, `sensitivity_summary.md`. Harness/tests: `src/echo_frb/repro/sensitivity/`,
`tests/test_sensitivity.py` (5/5).
