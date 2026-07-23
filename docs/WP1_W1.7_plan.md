# WP1 · W1.7 — Tests, Env Locks & Gate Memo (WP1 closeout) — Plan

## Context

W1.0–W1.6 are complete: literal reproduction is exact across all three committed configs, the blind
clean-room independently confirms FRB 20190131D and flags FRB 20211115A as fragile, and the
reproducibility matrix + notes are assembled. **W1.7 formally closes WP1**: verify/consolidate the full
test suite, finalize the environment locks, and write the **WP1 gate memo** — the decision record that
feeds the Authorization-B call (proceed to WP2). Low compute; mostly verification + one decision doc.
This is the last WP1 task.

## Tasks

### W1.7a — Test suite consolidation & verification
- Run the **full `tests/` suite** (WP0 + WP1) on popos with the project `.venv`; confirm green. Document
  the suite and the run command in the gate memo.
- Add **artifact-gated golden/integration tests** (currently WP1 tests are unit-only) →
  `tests/test_wp1_golden.py`, guarded by `@pytest.mark.skipif(not os.environ.get("ECHO_FRB_WP1_ARTIFACTS"))`
  (mirrors WP0's `ECHO_FRB_DATA` opt-in in `tests/test_schema_contract.py`), asserting from the popos
  artifacts: literal **G_3 == 11** and membership == committed list; clean-room candidates == {FRB 20190131D};
  FRB 20190131D Δt within 1 bin of 8.82 ms; **FRB 20211115A n_spikes == 0**; every one of the 340 has a
  disposition in `candidate_selection_chain.parquet`. Guards against silent regressions in re-runs.

### W1.7b — Environment locks
- **Refresh `env/microfrb_repro.lock`** to reflect the env actually used (adds `pyarrow`, `pyyaml`
  pulled in for the W1.4/W1.5 harness), with a header comment splitting **"reproduction core"**
  (numpy 2.2.6 / scipy 1.15.3 / h5py / matplotlib / colossus / statsmodels — pinned, unchanged) from
  **"analysis harness"** (pyarrow/pyyaml). Do **not** alter the pinned reproduction versions.
- Add **`env/README.md`** mapping env → track: literal & sensitivity → `venv_microfrb`
  (`microfrb_repro.lock`); clean-room + selection + matrix → project `.venv` (`requirements.lock`).

### W1.7c — WP1 gate memo → `docs/WP1_gate_memo.md` (the key deliverable)
Formal decision record:
- **Gate criterion** (proposal §8, WP1 row): *reported candidates and intermediate statistics are
  reproduced, or discrepancies are fully explained.*
- **Evidence** (from the matrix): literal **EXACT** on all 12 reproducible statistics; independent
  reproduction partial but **every discrepancy traced and quantified** (W1.4 factorial + W1.5 sweep).
- **§8.1 stop-condition assessment:** **NOT triggered** — the public data *did* reproduce the claim
  (literal exact), essential inputs were available (Tier A == CANFAR, verified), and discrepancies are
  *explained*, not "cannot reproduce."
- **Named-candidate verdicts:** FRB 20190131D = REPRODUCED-ROBUST; FRB 20211115A = FRAGILE (explained).
- **Reproducibility hazards** logged (undeclared deps, no license, smoothing source-toggle, hard-coded
  headline results, config-dependent lists).
- **Decision & recommendation:** **GATE PASS → recommend Authorization B (proceed to WP2)**, carrying
  forward (i) FRB 20211115A fragility as a documented finding and (ii) the under-determined
  spike-detection step as direct motivation for WP2's 2-D noise-weighted copy statistic. Explicitly note
  the **PI holds the final authorization decision**; this memo is a recommendation.
- **Deliverables index + provenance:** links to the matrix / note / candidate report / W1.4–W1.5
  findings / plans, with commit hashes and popos artifact locations.

### W1.7d — Closeout
- Mark **WP1 complete** in `docs/WP1_progress.md` (gate outcome recorded); update memory.

## Deliverables
- **`docs/WP1_gate_memo.md`** (new — key artifact).
- **`env/microfrb_repro.lock`** (refreshed) + **`env/README.md`** (env map).
- **`tests/test_wp1_golden.py`** (artifact-gated golden tests) + full suite green.
- `docs/WP1_progress.md` closeout + memory update.

## Reused infra / inputs
- Artifacts (popos): `reproducibility_matrix.parquet`, `candidate_stability.parquet`,
  `cleanroom_scores.parquet`, `sweep_literal_long.parquet`, `candidate_selection_chain.parquet`,
  `authors_reported_values.yaml`.
- Test convention: the `skipif` opt-in from `tests/test_schema_contract.py`.
- Env locks: `env/requirements.lock` (project/clean-room), `env/microfrb_repro.lock` (literal).

## Verification
1. `pytest tests/ -q` green for the WP0+WP1 unit suite; the artifact-gated golden tests pass on popos
   with `ECHO_FRB_WP1_ARTIFACTS=1`.
2. `microfrb_repro.lock` imports resolve in a fresh venv (spot check); pinned reproduction versions
   unchanged.
3. Every numeric claim in `WP1_gate_memo.md` matches the matrix/artifacts exactly (no drift); each links
   to a source artifact.

## Risks / open items
- Golden tests must **skip cleanly** where popos artifacts are absent (keep the default suite hermetic).
- Env-lock refresh must **not** bump the pinned reproduction versions — only add harness deps.
- The gate memo is a **recommendation**; phrase the authorization as the PI's decision, not a foregone one.
- Keep reproduction-verdict vs discovery-grade separation consistent with W1.6.
