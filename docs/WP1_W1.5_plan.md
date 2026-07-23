# WP1 · W1.5 — Controlled Sensitivity Analysis — Plan

## Context

W1.4 localized the literal-vs-clean-room divergence to the **spike-detection / smoothing** stage and
showed the reported candidate list is highly sensitive to it. W1.5 maps that sensitivity
**systematically**: vary one axis at a time off the frozen G_3 literal config and record which
candidates survive, appear, or vanish — quantifying which reported results (especially the two named
candidates and the 11 G_3 candidates) are robust vs artifacts of a single choice. **Comprehensive
breadth** (user-selected): the W1.4-motivated priority axes plus the full proposal §5.1 preprocessing
list. Output feeds the W1.6 reproducibility matrix.

**Key enabler / finding:** the authors' smoothing *method* is a **hard-coded source toggle**, not a
parameter — `detect_autocorr_spikes` (analysis_data.py:931) runs `gaussian_filter1d`, with
`savgol_filter(window_length=20, polyorder=3, mode='interp')` sitting **commented out** on the next
line. Their three committed configs (G_3/SG_20/SG_100) are three source states. This is itself a W1.5
result and makes SG reproduction a documented one-line edit.

---

## Axes (comprehensive)

**Priority (W1.4-motivated):**
- **Smoothing method** (source-edit variants): G_3 (done) · **SG_20** · **SG_100** — reproduce, verify
  vs the authors' committed CSVs, and compute cross-config candidate stability.
- **Spike threshold kσ** (literal `threshold`): {2, 2.5, 3, 3.5, 4}.
- **Clean-room `spike_nsigma`**: {2, 2.5, 3} — how many literal candidates our detector recovers as its
  threshold loosens (closes the W1.4 loop).
- **Gaussian `smooth_sigma`**: {2, 3, 5} (authors claim negligible effect — test it).

**Secondary (proposal-complete, one-at-a-time off G_3):**
- `rfi_factor` {2,3,4} · `f_down` {16,32,64} · `n_noise` {20,30,40} · `min_diff_threshold` (drift) {0.05,0.1,0.2}.

All literal runs: seed=42 fixed, `save_figure=False`, pinned `venv_microfrb`. Clean-room: our `.venv`.

---

## Mechanics

- **Parametric axes** (`threshold, smooth_sigma, rfi_factor, f_down, n_noise, min_diff_threshold`) are
  all `process_frb_catalog_lens` function params → **no source edit**. But importing `SearchLensedFRB.py`
  triggers its module-level `N=340` run (no `__main__` guard). So make a documented importable copy
  `SearchLensedFRB_lib.py` in the working copy with the bottom `results = process_frb_catalog_lens(...)`
  call removed (analysis logic untouched); the sweep runner imports `process_frb_catalog_lens` and calls
  it per config into a unique out-dir, then reads `lens_catalog_summary.csv`.
- **Smoothing method — clean parameterization (NO comment-toggle).** We do **not** switch smoothing by
  commenting/uncommenting source lines. Instead `sensitivity/smoothing.py` provides a single, faithful
  re-implementation of the authors' `detect_autocorr_spikes` whose smoothing line is chosen by a
  parameter (`method='gaussian'|'savgol'`, with `smooth_sigma` or `window_length`/`polyorder`), and
  monkeypatches it into `modules.analysis_data.detect_autocorr_spikes` at runtime. The Gaussian path is
  numerically identical to theirs; the savgol path (`window_length=20|100, polyorder=3, mode='interp'`)
  reproduces SG_20/SG_100. **Verify our SG output == the committed
  `FRB_lensing_results_SG_20/100/lens_catalog_summary.csv`** (extends the W1.2 exact-repro to all three
  configs) — one code path, selected by config, not by editing source.
- **Clean-room sweep**: `cleanroom/run.py` with `spike_nsigma` overridden in a copied config → 3 Tier B runs.

---

## Deliverables
- Code `src/echo_frb/repro/sensitivity/`: `make_lib.py` (the guard transform), `sg_variant.py` (the
  documented smoothing edit), `sweep_literal.py`, `sweep_cleanroom.py`, `aggregate.py`, `run.py`.
- Data (popos `~/frb_catalog2_prep/wp1_repro/sensitivity/`): per-run `*_summary.csv`,
  `sensitivity_matrix.parquet` (FRB × run-config → is_candidate / terminal stage),
  `candidate_stability.parquet` (per-candidate survival fraction across runs).
- `docs/WP1_W1.5_findings.md` + a compact stability table / text heatmap.
- `tests/test_sensitivity.py`: aggregation logic + SG-variant edit verification on a code snippet.

### `sensitivity_matrix` schema
Rows = union of all FRBs flagged candidate in any run; columns = each run config (method/param=value);
cells = `is_candidate`. Plus per-candidate `n_present / n_runs` and a `robust` flag. Highlighted rows:
FRB 20190131D, FRB 20211115A.

---

## Verification
1. **SG exact-repro:** our SG_20 / SG_100 runs reproduce the authors' committed CSVs value-for-value
   (like G_3) — or the discrepancy is traced (e.g., a different `window_length`/`polyorder`).
2. **Harness self-consistency:** the sweep's baseline G_3-params run reproduces the 11 candidates; the
   clean-room `spike_nsigma=3` run reproduces the committed single candidate (determinism).
3. **Stability readout:** FRB 20190131D survives across (nearly) all runs (robust); FRB 20211115A drops
   under threshold tightening / SG_100 / other axes (fragile) — quantified as a survival fraction.
4. Every run's config + candidate list is recorded in `sensitivity_matrix.parquet` (auditable).

## Risks / open items
- The library-guard transform must not change analysis → guarded by verification #2 (baseline = 11).
- The SG edit must match the authors' exact commented parameters; verify against committed outputs — a
  mismatch is a finding, not a failure.
- Runtime ~1.5–2 h (~22 literal runs + 3 clean-room); run in the background and checkpoint.
- Some axes push more bursts into the K-S stage (extra bootstrap) → slower but bounded.
- Sensitivity is about the candidate **list**; per-candidate Δt/μ stability is a secondary readout where
  a candidate persists across runs.
