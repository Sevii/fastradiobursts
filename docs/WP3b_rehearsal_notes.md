# W3b.7-G — Dress Rehearsal Notes

**Date:** 2026-07-25. **Command:** `scripts/wp3b_rehearsal.py --seed 20260725 --full`.
**Artifacts:** popos `~/frb_catalog2_prep/wp3b/rehearsal/`.

> **This validated the machinery, not the science.** The decoy round is drawn from **development**
> sources, which are the calibration set — its false-positive rates are optimistic by construction and
> are *not* evidence about v2's out-of-sample behaviour. That is what pool 1 is for.

## Why it exists

The controller → evaluator → unblind chain had never been run under v2. Finding a plumbing bug against
the sealed pool would burn the last remaining draw on a missing column or a bad path. Dev is already
fully spent on design, so a decoy round costs nothing and reveals nothing.

It paid for itself immediately: **it found two bugs that would have broken the real round 2.**

## Bug 1 — G1's marginal compared different injections on each side

`g1_assess` weighted the *predicted* marginal over only cells with `n_obs >= min_cell_n` (5), while the
*observed* marginal was taken over **all** injections. Round 1's 300 injections filled most cells, so the
bias was small and invisible. The 60-injection rehearsal left just 2 sparse low-μ cells and reported
**pred 0.013 vs obs 0.217** on a set that actually agreed — a pure artifact, and it declared G1 FAIL.

Round 2 spreads **140 injections over 28 cells (~5 each)**, so roughly half would fall below the
threshold. This would have mis-fired G1 for real — the same failure mode as round 1's coverage metric, in
a different place, and it would have been indistinguishable from a genuine efficiency deficit.

**Fix:** `min_cell_n` now gates **coverage only**, where a per-cell comparison genuinely needs data. The
marginal spans every cell that has a prediction, and the observed marginal is computed over exactly those
same injections. `n_marginal` and `n_injections_without_prediction` are now reported so any residual
mismatch is visible rather than silent. Regression test:
`test_g1_marginal_compares_the_same_injections_on_both_sides`.

## Bug 2 — the hard-null count was always zero

`n_multicomponent_drawn` used `feat.loc[h].single is False`, an identity comparison against a
`numpy.bool_`, which is never true. The commitment would have recorded 0 multi-component bursts drawn
regardless of the truth — defeating the whole point of stating the hard-null stratum size pre-scoring.
Caught by `test_controller_reports_the_hard_null_count_pre_scoring`.

## What the rehearsal demonstrated

Full round-2 mixture (600 items, 360 distinct dev bursts, seed 20260725):

| property | result |
|---|---|
| all four stages ran | ✅ pools → controller → evaluator → unblind |
| items scored / errors | 600 / **0** |
| `p_robust` populated | 600/600 |
| v2 columns present | `M`, `p_robust`, `worst_family`, `cell_level`, per-gate `z_*` |
| commitment guardrails | labels untampered, `labels_ts < scores_ts`, freeze held |
| freeze contract | asserted against the live v2 hash + calibration hash |
| gate arithmetic | computed end to end; G1 PASS, G2 hard PASS |
| scintillation role | `hard` (gated), as configured |
| hard-null stratum role | `report_only` |

The verdict itself (PASS) is **meaningless as science** — dev is the calibration set. What matters is
that every step ran, every column arrived, and the gate arithmetic produced numbers rather than crashing
or silently comparing the wrong things.

## Re-run policy

The rehearsal generates its harness config from whatever `config/wp2_analysis_config_v2.yaml` currently
hashes to, so it is always self-consistent. **Re-run it after any change to the analysis config, the
calibration, or the blind chain** — a stale rehearsal is worth nothing, and it is cheap.
