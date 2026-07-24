# WP3 — Blind Injection Validation — Progress Tracker

Living status of the WP3 tasks (plan: `docs/WP3_plan.md`). WP3 evaluates the **frozen**
`wp2-frozen-v1` pipeline on a hidden mixture drawn from the **sealed test split**, and passes only
if recovery matches the predicted efficiency (G1) and false positives meet predetermined targets
(G2). Runs on **Tier B**, popos, project `.venv` with `PYTHONPATH=src`. Code namespace:
`src/echo_frb/search/blind/`. **§8.1: WP4 does not run on a failed gate.**

## Scope / governance (standing)
- **Frozen pipeline, zero tuning.** Analysis config pinned to `wp2-frozen-v1`
  (`sha256[:16] = 3712e96faa969fcc`); the evaluator asserts equality before scoring. WP3 adds a
  *harness*, never analysis. Any drift → new analysis version, calibration forfeited (§5.8 step 7).
- **Predetermined targets** frozen in `docs/WP3_preregistration_addendum.md` **before** scoring.
- **Blind separation** code-enforced: sealed seed, labels hash-committed before scoring, scores
  hash-committed before unblinding.
- **One look, then a fresh set.** Test sources → K=2 disjoint pools (only 96 multi-component bursts in
  the test split → can't fragment finer); round 1 = pool 0 (~771 bursts / 79 multi); a failed round
  re-does on pool 1; after 2 failures → redesign.
- **Quarantine holds**; named candidates are **not** evaluated in WP3 (that is WP4).

## Task status
| Task | Status | Artifact |
|---|---|---|
| W3.0 Foundation (pools, addendum, freeze contract, predicted-ε generator) | 🟡 in progress | `config/wp3_blind_config.yaml`, `docs/WP3_preregistration_addendum.md`, `src/echo_frb/search/blind/{foundation,pipeline,predict}.py`, `tests/test_wp3_blind.py` **8/8 (1 golden skip)**. **Freeze finding:** frozen-config true hash `3712e96faa969fcc` (docs' `e614642f` was a stale W2.0-era label; config unchanged since commit `8c253b2`). **Data finding:** test split = 733 non-quarantined sources / 1133 bursts, only **96 multi-component** → **K=2** pools (pool 0: 374 src/771 bursts/79 multi; pool 1: 359/362/17). `blind_round_pools.parquet` built. Pending: `wp3_predicted_efficiency.parquet` (dev, full-criterion end-to-end). |
| W3.1 Blind controller (sealed hidden mixture) | 🟢 code+tests done | `blind/controller.py` → `hidden_manifest.parquet` (no-truth, verified) + sealed `hidden_labels.parquet` + `hidden_commitment.json`. Smoke: 45 items rendered, h5 identity scrubbed (tns_name:=item_id, source_file/event_id removed). Roles disjoint. Awaiting full production render. |
| W3.2 Frozen-pipeline evaluator (blind) | 🟢 code+tests done | `blind/evaluate.py` + `blind/pipeline.run_frozen_chain` (shared end-to-end runner). Smoke: 45 items/3s (8 workers), blind by construction (source-scan test enforces no truth access). scores_commitment ts post-dates labels. Awaiting full run. |
| W3.3 Unblind + gate assessment | 🟢 code+tests done | `blind/unblind.py`: commitment guards (tamper + peeking + freeze), G1 (marginal+CI / cell-coverage / bias / monotonic), G2 (point-estimate FP ≤ target, Wilson CI reported). **Gate-arithmetic fix:** gate on FP point (not Wilson upper — at n=40/kind the 0-FP upper is ~8.8%, would make 0 FP unpassable). |
| W3.4 Report + gate memo + tests | 🟢 done | `tests/test_wp3_blind.py` **23 pass** (incl. golden on real artifacts). `docs/WP3_blind_validation_report.md`, `docs/WP3_gate_memo.md`, audit trail `docs/wp3_round1_artifacts/`. |
| Production round + unblind | 🟢 done — **GATE FAIL** | Predicted-ε (100 dev hosts, 7490 inj) → controller (seed 8675309, pool 0, **880 items**) → blind evaluate (200 flagged) → unblind. Blind order verified (labels 05:40:00Z < scores 05:40:26Z). |

## RESULT: GATE FAIL (round 1) → WP4 BLOCKED (§8.1)
- **G1 efficiency agreement — MET.** obs 0.457 vs pred 0.474; per-cell two-sample consistency 0.958.
  (Pre-registered coverage metric mis-fired at 0.21 = tight-pred-CI vs noisy-obs-cell artifact, not a
  disagreement; revision item — does not change verdict.)
- **G2 false positives — FAILED (decisive).** End-to-end adverse FP far over target: differential_scattering
  0.25 (≤0.10), overlapping 0.60 (≤0.01), scintillation 0.70 (monitored ≤0.45, escalated). Real nulls
  (0.3%) + all deterministic artifacts (0%) still rejected.
- **Root cause (confirmed on dev):** the catalog search flags a burst if **any** of ~8 Tier-1 proposals
  passes; WP2's benchmark scored a **single oracle window**. End-to-end-vs-oracle rerun on dev:
  scintillation 0.28→0.55, overlapping 0.00→0.70, deterministic 0%→2.5–7.5%. WP2's benchmark was
  optimistic (no per-burst multi-proposal look-elsewhere). The blind gate caught it.
- **Required before pool-1 re-validation:** (1) control the per-burst multi-proposal LEE (analysis change
  → new version, forfeits calibration); (2) G1 coverage → two-sample CI-overlap; (3) overlapping generator
  → inject below Δt_min. A 2nd failure ⇒ redesign.

## Predetermined gate (from the addendum)
- **G1 (efficiency agreement):** `|ε_obs − ε_pred| ≤ 0.07` (marginal, CIs overlap) ∧ ≥90% of
  populated `(μ, S/N)` cells within the predicted 95% CI ∧ signed bias ≤ ±0.05 ∧ `ε(μ)` monotonic.
  Prediction = full-criterion **end-to-end** ε surface on the dev split (`predict.py`).
- **G2 (FP targets):** real ≤1%, deterministic adverse ≤1%, differential_scattering ≤10% (all
  hard); scintillation monitored ≤45% (escalate >60%, not a gate fail).
- **PASS = G1 ∧ G2(hard).**

## Next step — PI decision (WP3 round 1 complete, gate FAIL)
WP3 round 1 is **done**; the gate **failed on G2** (multi-proposal adverse-FP inflation) → **WP4 is
blocked (§8.1)**. The next action is a genuine scope decision because it **forfeits the `wp2-frozen-v1`
calibration** (§5.8 step 7): revise the pipeline → cut a **new analysis version** (`wp2-frozen-v2` /
`wp3-blind-v2`) → re-validate on a **fresh, source-disjoint pool-1** hidden set. Pool 0 is now burned;
a 2nd failure ⇒ redesign, not another draw.

Highest-leverage fix (recommended first): **take only the single best-triage Tier-1 proposal to Tier-2**
(or add a per-burst trials penalty / tighten per-proposal robustness) so the adverse FP survives an
~8-proposal search. Also (2) G1 coverage → two-sample CI-overlap test; (3) `overlapping` generator →
inject below Δt_min. **Awaiting the PI's go before reopening the frozen analysis.** Full write-up:
`docs/WP3_blind_validation_report.md`, `docs/WP3_gate_memo.md`.

## Notes
- Prerequisite: WP2 gate PASS (`docs/WP2_gate_memo.md`) → Authorization C requested. ✅
- Efficiency is **end-to-end** (Tier-1 triage × Tier-2 full criterion), so it is comparable to the
  WP4 catalog scan and may sit ≤ the WP2 tier2-only 0.79 oracle figure — captured by regenerating
  the prediction on dev with the same `run_frozen_chain`.
- popos sync is rsync (no git on popos); run with `PYTHONPATH=src` under the project `.venv`.
- Uncommitted since WP1 (user commits explicitly; don't nag).
