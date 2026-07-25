# W3b.7 Plan — Make the Round-2 Harness Actually Run v2

**Opened:** 2026-07-25. **Predecessor:** `docs/WP3b_dry_run_findings.md` (dry run = GO, α = 0.05).
**Goal:** close the six gaps between "v2 is validated" and "v2 can be blind-tested on pool 1".
**Constraint:** pool 1 is the last sealed pool. Nothing in this plan touches it — W3b.8 does, once.

---

## Dependency order

```
  A  calibration persistence + commitment        (issue 2)  ── foundational
     │
     ├── B  blind evaluator runs v2              (issue 1)
     ├── C  predicted-efficiency surface under v2 (issue 5)
     │
  D  controller guards + resized mixture         (issue 4)  ── independent
  E  G1 coverage metric -> two-sample CI overlap (issue 6)  ── independent
     │
     └── F  round-2 harness config + freeze contract (issue 3) ── last; needs the
            v2 analysis-config hash, which needs `frozen_date`, which needs the PI
     │
  G  DRESS REHEARSAL on a decoy set from dev     (new)  ── before pool 1, not on it
```

A–E can proceed now. F is gated on the PI's two target decisions and the freeze signature.
G is the last thing before W3b.8 and is the cheapest insurance available.

---

## A. Freeze the calibration as a committed artifact (issue 2)

**The gap.** `Calibration.fit()` is currently called on the fly. The calibration is now *part of the
analysis* — it decides candidacy — so if it can be refit between the dry run and the gate, the freeze
contract does not cover the thing being tested. Round 1's discipline (hash-commit before scoring) has to
extend to it.

**Design.** `Calibration.save(dir)` / `Calibration.load(dir)`, writing three files:

| file | contents |
|---|---|
| `calibration_values.parquet` | one row per null realization: `cell_id`, `M` — the empirical sample itself |
| `calibration_cells.parquet` | one row per cell: `cell_id`, family, stratum, level, `n`, GPD `u`/`shape`/`scale`, `n_exceedances`, `empirical_floor` |
| `calibration_manifest.json` | conditioning + tail spec, family list, **excluded families and why**, source-ensemble sha256, analysis-config sha16, `min_resolvable_alpha`, UTC build time |

`load()` **reconstructs, never refits** — the stored GPD parameters and M arrays are used as-is, so a
later code change cannot silently alter a committed calibration. It verifies both parquet hashes against
the manifest and raises on mismatch.

`calibration_commitment.json` (sha256 of all three + timestamp) is git-committed **before** the round-2
controller draws, exactly like `hidden_commitment.json`.

**Tests.** fit → save → load → byte-identical cell metadata; identical p-values across a grid of
(M, n_proposals, peak_snr) spanning every stratum and both sides of every GPD threshold; load fails loudly
on a tampered value file; `min_resolvable_alpha` survives the round trip; a loaded calibration refuses to
be refit.

**Files:** `src/echo_frb/search/margin/calibrate.py`, new `scripts/wp3b_freeze_calibration.py`,
`tests/test_wp3b_calibrate.py`.

---

## B. Blind evaluator runs v2 (issue 1)

**The gap.** `blind/evaluate.py:27` calls `run_frozen_chain` and records `is_candidate`. It computes no
`M` and no `p_robust`, so round 2 would re-measure v1.

**Design.** Make the evaluator **version-aware off the analysis config**, one code path per version, no
silent fallback:

- config has no `margin` block → v1 path (unchanged; preserves round-1 reproducibility)
- config has a `margin` block → v2 path: `margin.chain.run_margin_chain` → load the committed calibration
  → `p_robust` → `is_candidate = (M > 0) AND (p_robust <= alpha)`

The v2 path **asserts `margin.alpha` is not null** and that the calibration hash matches the commitment,
refusing to score otherwise. Per-item output gains `M`, `M_all`, `p_robust`, `worst_family`,
`p_robust_at_floor`, `cell_level` and the per-gate `z_*` margins, so the round-2 report can attribute
every decision.

**Blindness is preserved by construction** — the calibration is built from dev, contains no test data, and
`tests/test_wp3_blind.py` already scans this module's source to prove it opens no withheld artifact. That
scan must be extended to cover the calibration directory too.

**Files:** `src/echo_frb/search/blind/evaluate.py`, `tests/test_wp3_blind.py`.

---

## C. Predicted-efficiency surface under v2 (issue 5)

**The gap.** `predict.py:57` calls `run_frozen_chain`, so it predicts *v1* recovery. G1 would compare
observed-v2 against predicted-v1 and mis-fire — a repeat of round 1's metric failure in a new place.

**Design.** Rebuild the prediction from the artifact we already have. The dev null ensemble contains
**2,372 `injection` realizations** with `M` and covariates — a broader base than round 1's 150 hosts and,
crucially, produced by the same generator and the same chain the evaluator runs. So `predict.py` becomes
a transform, not a fresh campaign:

1. take `family == "injection"` from `null_ensemble_development.parquet`
2. apply the frozen calibration → `recovered = (M > 0) AND (p_robust <= alpha)`
3. join `tns_name` → manifest `catalog_snr` (dev is not scrubbed) and bin into S/N quartiles

Using `catalog_snr` — not the spectrum-derived `peak_snr` — keeps the predicted and observed sides on the
same axis, since the sealed labels carry `host_snr` from the manifest.

**Cross-check before committing:** the surface's marginal must reproduce the dry-run efficiency
(0.2995 all-μ / 0.4442 dev at μ≥0.5). A mismatch means the transform disagrees with the curve script and
one of them is wrong.

**Files:** `src/echo_frb/search/blind/predict.py`, `tests/test_wp3_blind.py`.

---

## D. Controller guards + resized mixture (issue 4)

**The gap.** `_select_roles` slices (`multi[:n]`, `single_left[:n]`) and never checks. Measured against
pool 1, the round-1 recipe yields **62 injection hosts instead of 300 and zero adverse hosts** — the class
that failed round 1 — with no error raised.

**Design.**
1. `_select_roles` raises a named, actionable error when any role is short: which role, requested vs
   available, which pool. A blind round drawn from a silently truncated mixture is worse than no round.
2. Round-2 mixture in the harness config: `n_real_null: 180`, `n_injections: 140`,
   `n_per_adverse_kind: 40` → 600 items over 360 of pool 1's 362 bursts (verified to fit exactly).
3. Record `n_multicomponent_drawn` (= 17, all of them) in `hidden_commitment.json`, so the report states
   the hard-null stratum's size pre-scoring rather than discovering it after.

**Tests.** A synthetic pool too small for the recipe raises; pool 1 + the round-2 recipe does not; the
commitment carries the multi-component count.

**Files:** `src/echo_frb/search/blind/controller.py`, `config/wp3_blind_config_v2.yaml`,
`tests/test_wp3_blind.py`.

---

## E. G1 coverage metric → two-sample CI overlap (issue 6)

**The gap.** Gate-memo item 2. Round 1's metric asked "is the observed cell rate inside the *predicted*
95% CI?", which compares a noisy observed cell against a tight predicted interval and mis-fired at 0.21
while the underlying agreement was fine (0.457 vs 0.474).

**Design.** A cell agrees iff its observed and predicted Wilson CIs **overlap** — a symmetric two-sample
test that accounts for uncertainty on both sides. Coverage = fraction of populated cells
(`n >= min_cell_n`) that agree. The marginal-tolerance and signed-bias checks are unchanged.

**Tests.** Two cells with identical rates and honest CIs agree regardless of n; a genuinely displaced cell
fails; the round-1 numbers (obs 0.457 / pred 0.474) now pass, which is the specific regression this fixes.

**Files:** `src/echo_frb/search/blind/unblind.py`, `config/wp3_blind_config_v2.yaml`,
`tests/test_wp3_blind.py`.

Same pass, since it is the same file and the same config: move scintillation from monitored to **gated**
in `unblind`'s G2 arithmetic, and mark the hard-null stratum **report-only** (n=17 cannot resolve 1%).
Both need the PI's numbers (§F).

---

## F. Round-2 harness config + freeze contract (issue 3) — LAST

**The gap.** `foundation.assert_freeze_contract` pins `3712e96faa969fcc` (v1).

**Design.** New `config/wp3_blind_config_v2.yaml`: pins the v2 analysis version + hash, pool 1, the
resized mixture, the round-2 targets, and the calibration commitment hash. `assert_freeze_contract` gains
a calibration-hash assertion alongside the config-hash one.

**Blocked on, in order:**
1. PI sets the **scintillation gate target** (≤ 0.10 proposed) and the **point-estimate vs CI convention**
   for the ≤ 0.01 deterministic target.
2. Targets land in the harness config; `frozen_date` is set in `config/wp2_analysis_config_v2.yaml`.
3. *Only then* is the v2 config hash stable and can be pinned. Any earlier and the pin is stale on the
   next edit — the exact failure mode that left the v1 docs quoting `e614642f` when the truth was
   `3712e96faa969fcc`.
4. PI signs `docs/WP3b_preregistration_addendum.md`; it and every commitment file are git-committed.

`tests/test_wp3b_freeze.py::test_freeze_date_is_set_at_pi_signoff` is written to fail at this point, on
purpose, so cutting the freeze is a visible reviewed edit.

---

## G. Dress rehearsal on a decoy set — before pool 1, not on it

The full controller → evaluator → unblind chain has never been run under v2. Debugging it against the
sealed pool would burn the one remaining draw on a plumbing bug.

**Design.** Draw a decoy round from **development sources** using the round-2 recipe and run the complete
chain end to end: sealed seed, labels hash-committed, scores committed, unblind guardrails, G1/G2 gate
arithmetic, report generation. Dev is already fully used in design, so a decoy round costs nothing and
reveals nothing.

**What it must demonstrate:** commitments verify and the ordering guard fires on a deliberately
out-of-order run; the evaluator emits `M`/`p_robust` for every item; G1 and G2 produce numbers consistent
with the dry run; the report renders. Because dev is the calibration set, its FP will be optimistic —
**the decoy validates the machinery, not the science.** That distinction goes in the output header so no
one later mistakes a rehearsal for a result.

**Files:** `scripts/wp3b_rehearsal.sh`, `docs/WP3b_rehearsal_notes.md`.

---

## Sequencing

| step | issue | blocked by | scope |
|---|---|---|---|
| A calibration persistence | 2 | — | new save/load + commitment, ~6 tests |
| B evaluator v2 | 1 | A | version-aware path, extend blindness scan |
| C predicted surface v2 | 5 | A | transform over the dev ensemble + cross-check |
| D controller guards | 4 | — | assertions + resized mixture |
| E G1 metric + G2 arithmetic | 6 | PI targets (partial) | CI-overlap test; scintillation gated |
| F harness config + freeze | 3 | A, D, E, **PI** | pin hashes; sign addendum |
| G dress rehearsal | — | A–F | decoy round on dev |
| **W3b.8** | — | **G + signature** | **one shot on pool 1** |

A–D and the metric half of E carry no dependency on the PI and can be built immediately. E's gate
arithmetic, F and G need the two target decisions.

**Invariant for the whole plan:** nothing reads pool 1. The only command that does is W3b.8, and it runs
after the rehearsal passes and the addendum is signed.
