# WP1 Gate Memo — Project ECHO-FRB

**Work package:** WP1 — literal and clean-room reproduction of the reported FRB lensing candidates.
**Date:** 2026-07-23. **Status:** complete. **Recommendation:** **GATE PASS → proceed to WP2
(Authorization B).** The final authorization decision rests with the PI; this memo is a recommendation.

---

## 1. Gate criterion (proposal §8, WP1 row)
> *"Reported candidates and intermediate statistics are reproduced, or discrepancies are fully explained."*

## 2. Verdict against the criterion — **MET**
- **Literal reproduction is EXACT.** The authors' pipeline, run unmodified on our sealed Tier A data
  (byte-identical to the CANFAR release) in a reconstructed pinned environment, reproduces the committed
  outputs **value-for-value across all three** smoothing configurations (G_3=11, SG_20=16, SG_100=12).
  Every reproducible reported statistic in the reproducibility matrix is EXACT on the literal track
  (12/12; the remainder are out-of-scope or a subjective step).
- **Every independent-analysis discrepancy is fully explained.** The blind clean-room recovers 1 of 11
  G_3 candidates; the divergence is traced to a specific cause (W1.4 light-curve × ACF factorial:
  spike-detection algorithm/threshold-dominated) and quantified (W1.5 sweep: candidate count 22→3 across
  spike kσ∈[2,4]; only FRB 20190131D robust across all 20 configs).

Both limbs of the "reproduced **or** explained" criterion are satisfied.

## 3. §8.1 stop-condition assessment — **NOT triggered**
The §8.1 stop rule is *"stop/redesign if the public data cannot reproduce the claimed signal because
essential inputs are unavailable or undocumented."* None applies:
- The public data **did** reproduce the claim (literal EXACT).
- Essential inputs **were available** — Tier A verified byte-identical to CANFAR (W1.1); the authors'
  code and catalog tables are public.
- The remaining discrepancies are **explained**, not "cannot reproduce."

→ This is a *reproduced* outcome, not a stop condition.

## 4. Named-candidate verdicts (reproduction, not §7 discovery grades)
| Candidate | Verdict | Basis |
|---|---|---|
| **FRB 20190131D** | **REPRODUCED-ROBUST** | Recovered by the authors' code and a fully independent blind implementation (same Δt≈8.82 ms, same pair [76,85]); survives all 20 swept configs; factorial AGREE. |
| **FRB 20211115A** | **FRAGILE (explained)** | Reproducible only with the authors' exact code + preprocessing + a permissive spike threshold; no independent ACF spike at any threshold; drops under the authors' own SG_100 config. |

Catalog-global false-alarm probability is **not** computed here (that is WP4); these are reproduction
verdicts, not discovery grades (§7).

## 5. Reproducibility hazards found in the target (for the record)
Undeclared dependencies (`colossus`, `statsmodels`); no license / no `requirements.txt` / no pinned
versions; smoothing method switched by a **source comment-toggle**, not a parameter, yet it changes the
candidate count; hard-coded parameters/paths and no `__main__` guard; **headline results hard-coded**
(`fpbh.py`, `Hardness_test.py`) rather than regenerated; candidate list is smoothing-config-dependent.

## 6. Decision & recommendation
**GATE PASS.** Recommend **Authorization B** (WP2 development + initial simulations), carrying forward:
1. **FRB 20211115A fragility** as a documented finding — it should not be treated as a robust candidate
   on catalog data alone.
2. The **under-determined spike-detection step** as direct motivation for WP2's primary statistic — a
   masked, noise-weighted **two-dimensional** copy test, which replaces the frequency-integrated
   autocorrelation trigger whose fragility WP1 quantified.
3. FRB 20190131D as a **robust** reproduction worth revisiting in later WPs (baseband follow-up in WP5).

Preprocessing/threshold freezing and the empirical-null work proceed under WP2; no compute beyond the
existing workstation is requested at this gate.

## 7. Deliverables & provenance
| Deliverable | Location |
|---|---|
| Reproducibility matrix | `docs/reproducibility_matrix.md` (+ `.parquet` on popos) |
| Technical reproduction note | `docs/WP1_reproduction_note.md` |
| Candidate reproduction report (Appendix B) | `docs/candidate_reproduction_report.md` |
| W1.4 / W1.5 findings | `docs/WP1_W1.4_findings.md`, `docs/WP1_W1.5_findings.md` |
| Ground truth (authors' reported values) | `src/echo_frb/repro/target/authors_reported_values.yaml` |
| Code | `src/echo_frb/repro/{target,ingest,literal,cleanroom,selection,sensitivity,matrix}/` |
| Env locks | `env/microfrb_repro.lock` (literal), `env/requirements.lock` (clean-room), `env/README.md` |
| Tests | `tests/test_{cleanroom,selection,sensitivity,matrix,wp1_golden}.py` — 71 pass / 6 skip; golden 5/5 with `ECHO_FRB_WP1_ARTIFACTS` |

**Reproduction target:** arXiv:2605.19653, MICRO-FRB @ `c4fbfca` (sealed, `repro_target_manifest.parquet`).
**Data/artifacts:** popos `~/frb_catalog2_prep/wp1_repro/` (Tier A/B on the same host; nothing in git).
**Code provenance (git):** `66effaa` (W1.0–1.2), `91a2460` (W1.3), `17bb12b` (W1.4–1.5), plus this
closeout commit (W1.6–1.7).
