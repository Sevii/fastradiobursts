# WP1 · W1.4 — Selection-Chain Reconciliation & Causal Decomposition — Plan

## Context

Two independent detection runs now exist over the same 340 multi-peak FRBs:
- **Literal** (authors' code on Tier A) → **11** candidates, incl. both named ones (EXACT match to
  their committed G_3).
- **Blind clean-room** (our code on our Tier B) → **1** candidate (FRB 20190131D only); FRB 20211115A
  produces **0 significant ACF spikes**.

W1.4 turns that raw divergence into an auditable result: (1) reconstruct the **per-stage selection
funnel for both tracks**, (2) build a **reconciliation matrix** classifying every FRB by where the two
tracks agree/diverge, and (3) **causally attribute** the divergences — especially FRB 20211115A —
to *preprocessing* vs *algorithm* via a **light-curve × ACF factorial** (user-selected method).
Blindness is complete: the clean-room artifact is frozen; W1.4 is orchestrator-side analysis and may
use the authors' code as a *diagnostic probe* (not a blind build). Output feeds the W1.6 matrix + note.

---

## Tasks

### W1.4a — Per-stage selection funnel, both tracks → `candidate_selection_chain.parquet`
Canonical stages: `PROCESSED → SPIKE (≥1 ACF spike >3σ) → MATCH (pair within ±2 ms) → CUTS (ordering /
secondary PSNR>10 / global-max inclusion) → DRIFT (K-S) → CANDIDATE`. Record each FRB's terminal
disposition per track.
- **Literal:** parse `~/frb_catalog2_prep/wp1_repro/literal_G3_run.log` per `[i/340]` block into a
  terminal disposition (phrases confirmed present: `无自相关尖峰`=no-spike, `未匹配…峰对`=no-match,
  `没有包含最高SNR`=cut-maxSNR, `SNR 顺序错误`=cut-order, `后峰 SNR`=cut-PSNR, `严重频率漂移`=drift,
  `分析完成`=candidate). Tally: 340 → 105 spike → 59 matched → cuts → 11 candidates.
- **Clean-room:** add an additive `stage_dropped` output to `cleanroom/pipeline.py` (logging only —
  thresholds/logic **unchanged**) and re-run 340 → `cleanroom_scores_staged.parquet`; guard that
  `is_candidate` + `content_sha256` are identical to the committed run (determinism preserved). Existing
  columns (`n_spikes, n_matched, best_secondary_psnr, ks_d_max, has_drift, is_candidate`) seed the rest.

### W1.4b — Reconciliation matrix → `reconciliation_matrix.parquet` + `.md`
Union of all FRBs reaching ≥SPIKE in *either* track. Per FRB: `literal_disposition`,
`cleanroom_disposition`, `agree` (bool), `divergence_stage` (first stage where they differ),
`in_literal_candidates`, `in_cleanroom_candidates`. Summary counts + the agreement/confusion table.
Cross-reference (context only; full smoothing sweep = W1.5): the authors' committed **SG_20 (16)** /
**SG_100 (12)** lists and the paper's **11→9→2** funnel from `authors_reported_values.yaml` — noting
FRB 20211115A's absence under SG_100 corroborates the clean-room non-detection, and that 11→9→2 is a
**subjective, non-algorithmic** morphology reassessment we do not attempt to reproduce.

### W1.4c — Causal decomposition: light-curve × ACF factorial → `decomposition_factorial.parquet` + narrative
For the **divergent FRBs** (priority: FRB 20211115A + both named candidates + the union of
flagged-in-either), cross two light curves × two spike-detectors:
- `LC_lit` = authors' `process_data_ts` light curve (import from the working copy `microfrb_run/modules`;
  their code, used here strictly as an analysis probe).
- `LC_cr`  = clean-room light curve from Tier B (`cleanroom/lightcurve.py`).
- `ACF_lit` = authors' `compute_autocorr_with_spikes`; `ACF_cr` = `cleanroom/acf.py`.
- Both light curves share the native time axis (Tier B `t_down=1`, their `t_down=1`) → spikes in the
  same lag units, directly comparable.

Per FRB, record the 2×2 spike outcome (spike-near-expected-Δt? y/n) and attribute:
- differs **across rows** (LC factor) ⇒ **preprocessing**-driven;
- differs **across columns** (ACF factor) ⇒ **algorithm/threshold**-driven.
Resolve FRB 20211115A explicitly: does its 6.86 ms spike survive under `LC_lit+ACF_cr` and
`LC_cr+ACF_lit`, isolating whether our Tier B preprocessing or the clean-room ACF suppresses it.

### W1.4d — Findings note → `docs/WP1_W1.4_findings.md`
Both funnels (with a small ASCII/table waterfall), the reconciliation summary, the factorial attribution
per divergent FRB, and the bottom line for the two named candidates (FRB 20190131D = robust across
independent preproc+code; FRB 20211115A = fragile, with the attributed cause). Explicitly scopes this as
input to W1.6, not the final matrix.

---

## Deliverables
- Code: `src/echo_frb/repro/selection/` — `funnel_literal.py` (log parser), `funnel_cleanroom.py`,
  `reconcile.py`, `factorial.py`, `run.py`.
- Data (popos `~/frb_catalog2_prep/wp1_repro/selection/`): `candidate_selection_chain.parquet`,
  `reconciliation_matrix.parquet`, `decomposition_factorial.parquet`, `cleanroom_scores_staged.parquet`.
- `docs/WP1_W1.4_findings.md` + `reconciliation_matrix.md`.
- `tests/test_selection.py`: log-parser unit test (synthetic log block → expected disposition);
  reconciliation invariant (every FRB reaching ≥SPIKE in either track has a row + a divergence_stage);
  factorial determinism.

## Reused infra / inputs
| Need | Reuse | Path |
|---|---|---|
| Literal per-stage reasons | parse | `wp1_repro/literal_G3_run.log` |
| Clean-room stages | existing columns + additive `stage_dropped` | `cleanroom/pipeline.py`, `cleanroom_scores.parquet` |
| Factorial: their LC + ACF (probe) | `process_data_ts`, `compute_autocorr_with_spikes` | `wp1_repro/microfrb_run/modules` |
| Factorial: our LC + ACF | `lightcurve.py`, `acf.py` | `src/echo_frb/repro/cleanroom/` |
| Authors' SG/funnel context | `authors_reported_values.yaml` | `src/echo_frb/repro/target/` |
| 340-set | `microfrb_input_manifest.parquet` | popos workspace |

**Note on using authors' code (W1.4c):** the clean-room build (W1.3) stays frozen and blind; the
factorial imports `process_data_ts`/`compute_autocorr_with_spikes` only as post-hoc *measurement
instruments* to attribute an already-observed divergence. This is analysis, not (re)implementation.

## Verification
1. **Funnel closure:** literal funnel terminal counts sum to 340 and yield exactly **11** candidates
   (matches the committed G_3); clean-room funnel yields exactly **1** and `is_candidate`/`content_sha256`
   match the committed W1.3 run (determinism guard).
2. **Reconciliation invariant** (pytest): every ≥SPIKE FRB has a row with a valid `divergence_stage`;
   the candidate columns reproduce {11 literal, 1 clean-room}.
3. **Factorial sanity:** the `LC_cr+ACF_cr` cell reproduces the committed clean-room spike outcome, and
   `LC_lit+ACF_lit` reproduces the literal spike outcome, for every probed FRB (self-consistency).
4. **FRB 20211115A resolved:** its divergence is attributed to a specific factor (preproc vs algo),
   stated with the 2×2 evidence.

## Risks / open items
- Log parsing must be **per-`[i/340]` block** (phrase counts overlap across n_peaks loop iterations) —
  take the terminal disposition per block, not raw grep totals.
- Ordering/max-SNR cuts aren't distinct clean-room columns → the additive `stage_dropped` instrumentation
  supplies them; must not alter detection outcomes (guarded).
- Light-curve normalization conventions differ between tracks → feed each ACF the raw LC and let it apply
  its own demean/normalize (both demean); document this so the factorial compares like-for-like.
- Attribution may be **mixed** (both factors contribute) — report the 2×2 honestly rather than forcing a
  single cause.
