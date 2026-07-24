# WP3 Gate Memo — Project ECHO-FRB

**Work package:** WP3 — blind-injection validation. **Date:** 2026-07-23. **Status:** complete (round 1).
**Recommendation:** **GATE FAIL → do NOT grant Authorization C; do NOT run the WP4 catalog search
(§8.1).** Revise the pipeline, cut a new analysis version, and re-validate on a fresh hidden set. The
final authorization is the PI's; this is a recommendation.

## 1. Gate criterion (proposal §8, WP3 row)
> *"Recovery agrees with predicted efficiency and predetermined false-positive targets."*
> Deliverable: a blind-validation report.

## 2. Verdict — NOT MET
Blind evaluation of the frozen `wp2-frozen-v1` pipeline on a hidden mixture (880 items, sealed test-split
pool 0, controller seed 8675309; full report `docs/WP3_blind_validation_report.md`):

- **G1 efficiency agreement — MET.** Observed full-criterion recovery 0.457 vs predicted 0.474 (|Δ|=0.017);
  per-cell two-sample consistency 0.958. (The pre-registered coverage metric mis-fired at 0.21 — a
  tight-predicted-CI vs noisy-observed-cell artifact, not a disagreement; fix noted for the revision.)
- **G2 false-positive targets — FAILED (decisive).** End-to-end, the adverse imitators pass the full
  criterion far above target: **differential_scattering 25%** (≤10%), **overlapping 60%** (≤1%),
  **scintillation 70%** (monitored ≤45%, escalated >60%). Real complex nulls (0.3%) and every
  deterministic artifact (0%) are still rejected.

## 3. Root cause (diagnosed, not guessed)
WP2's null benchmark scored a **single oracle window**; the real pipeline flags a burst if **any** of its
~8 Tier-1 proposals passes. A controlled end-to-end-vs-oracle rerun on development hosts confirms the
**multi-proposal "any-passes" search inflates the adverse FP** (scintillation 0.28→0.55, overlapping
0.00→0.70, every deterministic kind 0%→2.5–7.5%). WP2's benchmark was optimistic: it did not model the
per-burst look-elsewhere within the proposal set. This is exactly the failure a blind end-to-end gate
exists to catch.

## 4. §8.1 stop condition — TRIGGERED
> *"Do not run the catalog-wide search if WP3 fails the hidden-injection gate."*

WP4 is **blocked**. No named-candidate unblinding, no catalog scan, until a revised pipeline passes a
fresh blind gate.

## 5. Required before re-validation (proposal §5.8 step 5, step 7)
1. **Control the per-burst multi-proposal look-elsewhere** (single-best-proposal to Tier-2, a per-burst
   trials penalty, or stricter per-proposal robustness) — an **analysis change** → new version
   `wp2-frozen-v2` / `wp3-blind-v2`, which forfeits the WP2 calibration.
2. Fix the G1 coverage metric to a two-sample CI-overlap test.
3. Fix the `overlapping` adverse generator to inject below Δt_min (clean unresolved-echo control).
4. Re-freeze; draw a **fresh, source-disjoint** hidden set from **pool 1** (pool 0 is burned). A 2nd
   failure ⇒ redesign, not another draw (finite catalog; §8.1/§11).

## 6. What worked (carry forward)
Blind machinery, freeze contract, sealed-seed + hash-commitment discipline (labels-before-scores verified),
efficiency-agreement (G1), and deterministic-artifact + real-null rejection. Deliverables:
`docs/WP3_blind_validation_report.md`, `docs/WP3_preregistration_addendum.md`, audit trail
`docs/wp3_round1_artifacts/`, code `src/echo_frb/search/blind/`, tests `tests/test_wp3_blind.py` (22 pass).

## 7. Decision & recommendation
**GATE FAIL (round 1).** Recommend **withholding Authorization C** and returning to WP2-level method
development to control the multi-proposal adverse false-positive rate, then a fresh WP3 blind round on
pool 1. The result is scientifically valuable: the pipeline's true catalog-search false-positive behavior
is now measured out-of-sample, and the discipline that produced it is fully auditable.

**Provenance:** frozen analysis `wp2-frozen-v1` (`3712e96faa969fcc`, untouched); WP3 harness `wp3-blind-v1`;
hidden set + scores + validation on popos `~/frb_catalog2_prep/wp3/round1/`; blind order verified
(labels 05:40:00Z < scores 05:40:26Z). Quarantine held; named candidates NOT evaluated.
