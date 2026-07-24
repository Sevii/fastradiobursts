# WP2 Gate Memo — Project ECHO-FRB

**Work package:** WP2 — statistic + empirical nulls. **Date:** 2026-07-23. **Status:** complete.
**Recommendation:** **GATE PASS (qualified) → proceed to WP3 (Authorization C: blind-injection
validation).** The final authorization is the PI's; this is a recommendation.

## 1. Gate criterion (proposal §8, WP2 row)
> *"False-positive behavior is stable across null constructions and known artifacts are rejected."*
> Deliverable: a versioned analysis package + a null benchmark.

## 2. Verdict — MET (qualified)
- **FP characterized + consistent across constructions.** Copy-only FP is dominated by real intrinsic
  morphology (real 7.7% ≫ xpair 0.07% > surrogate 2.1%); surrogate lowest confirms structure matters.
  The real–xpair disagreement (0.077) is the reported null-model uncertainty (§6.5).
- **Under the full candidate criterion, FP is controlled to ~0%** (real-null 7%→0.0%) at **79% detection
  efficiency**, and **all deterministic artifacts are rejected** (drift/DM/chromatic/RFI → 0%).
- **One qualification:** scintillation (a propagation effect) is suppressed 80%→36% but not eliminated —
  a bounded residual, explicitly per §11 ("plasma is too flexible to rule out decisively; treat as an
  adverse test"). Carried forward to WP3/WP5 + the H-LP extension, not overclaimed.

## 3. Deliverables (proposal §8, §12)
| Deliverable | Location |
|---|---|
| Versioned analysis package (statistic + nulls + robustness + injections) | `src/echo_frb/search/`, frozen `config/wp2_analysis_config.yaml` (`wp2-frozen-v1`) |
| Null benchmark (FP stability + artifact rejection + ε-vs-FP) | `docs/WP2_null_benchmark.md`, popos `wp2/benchmark/` |
| Empirical null catalogs (4 constructions) | popos `wp2/nulls/null_catalog_{real,surrogate,xpair}.parquet`, `adverse_catalog.parquet` |
| Detection-efficiency surface + CIs | popos `wp2/injection_recovery.parquet` |
| Global-significance machinery (null-calibrated) | `docs/WP2_global_significance.md`, `significance/` |
| Preregistration draft (Appendix A) | `docs/WP2_preregistration.md` |
| Automated tests | `tests/test_{wp2_foundation,copy_statistic,tier1,nulls,adverse,robustness,injection,benchmark,significance}.py` — 30 pass |

## 4. Method integrity (validation-driven)
WP2 caught and fixed **four** methodological issues *before* they could bias a result, each via
validation-first design:
1. v1 copy statistic noise-dominated on real data (NCC≈0) → mask-aware rebin + on-burst support +
   template amplitude fit.
2. reduced-χ² = 1+a² inflated high-μ copies → whitened by full noise (efficiency now monotonic).
3. scintillation slipped the copy criterion → spectral-magnification-flatness diagnostic + mandatory
   achromaticity.
4. Δχ²/NCC unusable as standalone global statistics (brightness / saturation) → global significance rests
   on the full criterion (local p-value).

## 5. §8.1 stop-conditions — not triggered
Statistic + null are credible and calibrated; the dominant risk (null-model misspecification) is
addressed by leading with real-burst nulls and reporting construction disagreement as an uncertainty. No
compute was spent widening simulations while misspecification dominated.

## 6. Decision & recommendation
**GATE PASS (qualified).** Recommend **Authorization C** (WP3 hidden-injection validation), carrying:
1. the frozen preregistration (`wp2-frozen-v1`) — thresholds/statistic/nulls/robustness sealed before the
   hidden set;
2. the scintillation/plasma residual as a documented limitation;
3. the WP3 requirement that recovery match the W2.6 efficiency at the predetermined FP before any
   catalog-wide search (WP4).

**Provenance:** frozen config `wp2-frozen-v1` (2026-07-23); data/products on popos
`~/frb_catalog2_prep/wp2/`; code under `src/echo_frb/search/` (this commit). Quarantine v2 + source-level
splits + freeze-before-WP3 held throughout — no candidate/hidden-set evaluation occurred in WP2.
