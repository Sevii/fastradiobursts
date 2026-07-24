# WP2 — Statistic & Nulls — Progress Tracker

Living status of the WP2 tasks (plan: `docs/WP2_plan.md`). Builds the masked, noise-weighted 2-D copy
statistic + realistic empirical nulls that WP1 motivated. Runs on **Tier B** (frozen WP0 preprocessing),
popos, project `.venv`. Code namespace: `src/echo_frb/search/`. Data → Tier C/D on popos (regenerable).

## Scope (confirmed)
- **Full WP2** (proposal §5.3–5.7, §6, Objectives 2–4). **Tier-1 = classical** (segmentation + matched
  filter); **no ML** in the pipeline.
- **Gate:** false-positive behavior stable across null constructions **and** known artifacts rejected.

## Governance (standing)
- **Quarantine v2**: {FRB20190131D, FRB20211115A} ∪ WP1 intermediate candidates — excluded from all
  threshold/null design; scored only after freeze.
- **Source-aware** dev/validation/untouched-test splits; repeater vs non-repeater strata separate.
- **Freeze before WP3** — no named-candidate or full-catalog evaluation in WP2.

## Task status
| Task | Status | Artifact |
|---|---|---|
| W2.0 Foundation (experiment DB, source split, quarantine v2, delay domain) | 🟢 done | `config/wp2_analysis_config.yaml` (hash `e614642f`), `src/echo_frb/search/experiment/` (splits/quarantine/db/build_foundation) + `tests/test_wp2_foundation.py` **5/5**. On popos `~/frb_catalog2_prep/wp2/`: `source_split.parquet` (**dev 2186 src/2552 · val 713/840 · test 736/1140**, source-level, invariant holds), `quarantine_v2.csv` (**23 tns** = 2 named ∪ G_3∪SG_20∪SG_100), `experiment_db.parquet`. |
| W2.1 Tier-1 catalog scan (classical) | 🟢 done | `src/echo_frb/search/{tierb_io,tier1/{profile,scan,run}}` + `tests/test_tier1.py` **3/3**. Noise-weighted profile → peak segmentation + delayed-energy scan → (A,B,Δt) proposals in the delay domain + 1-D NCC triage. **Full scan: 4532 bursts, 0 fail, 12200 proposals over 2609 bursts** (5881 peak_pair / 6319 delayed_energy) → `tier1_proposals.parquet`. Δt 2.95–49.15 ms (domain respected), median 6.88 ms; quarantine flagged (146 props / 22 bursts). |
| W2.2 χ²_copy statistic | 🟢 done (v2) | `src/echo_frb/search/copy/` (`statistic.py`, `extract.py`, `score.py`) + `tests/test_copy_statistic.py` **4/4**. **v1 was noise-dominated on real data (NCC≈0, no separation) — v2 fixes it:** mask-aware inverse-variance freq rebin (16384→256), **on-burst support** (compare where A has power), **template amplitude fit** (closed-form a, matched-filter Δχ², no a↔variance degeneracy). **Validated on real data:** injected copy (NCC 0.48 / Δχ² 540) >> real-null (0.17 / 202) >> surrogate (0.12 / 26) — separates, surrogate correctly lowest. Tail overlap = the real FP problem (→ nulls + robustness). |
| W2.3 Empirical nulls (real / xpair / surrogate) | 🟢 done | `src/echo_frb/search/{copy/score,nulls/{surrogate,build,run}}` + `tests/test_nulls.py` **3/3**. Built on dev split (non-quarantined) → `nulls/null_catalog_{real,surrogate,xpair,all}.parquet` (**12,265 scores**: real 6749 / surrogate 4065 [3 methods] / xpair 1451). Δχ² median real **176** · xpair **166** · surrogate **38** (copy-destroyed → correctly lowest). Statistic validated: injected copy separates from all nulls. |
| W2.4 Adverse simulations | 🟢 done | `src/echo_frb/search/adverse/{generators,run}` + `tests/test_adverse.py` **2/2**. 8 imitators (drift, diff-DM, diff-scattering, chromatic-echo, scintillation, overlapping, RFI + achromatic control) injected into 150 real single-component dev bursts → `nulls/adverse_catalog.parquet` (1200 rows). **7/7 adverse kinds score less copy-like than achromatic** (NCC 0.60 ctrl vs ≤0.56; reduced-χ² flags scintillation/drift/RFI). Scintillation closest → W2.5 achromaticity diagnostics finish it. |
| W2.5 Robustness diagnostics (8) | 🟢 done | `src/echo_frb/search/robustness/{diagnostics,run}` + `tests/test_robustness.py` **3/3**. All 8 (§5.5): achromatic-delay, magnification-stability, leave-band-out, resolution-stability, window-stability, residual-structure, fine-structure, DM/scattering. **Validated on real bursts:** achromatic copy passes **7.8/8**; every adverse kind <7 — achromaticity checks kill drift/DM/chromatic (0.00–0.12), residual-structure catches **scintillation** (0.03, the copy-score borderline). Candidate bar ≥7/8 separates. |
| W2.6 Dev injection campaign (~10k) → ε | 🟢 done | `src/echo_frb/search/injection/{efficiency,run}` + `tests/test_injection.py` **3/3**. **11,305 injections** (11 Δt × 7 μ × 150 hosts) → `injection_recovery.parquet`. **ε(μ) monotonic**: 0.10/0.33/0.64/0.83/0.93/0.96/0.96 (μ=0.1→0.9), 50% near μ≈0.27; ε(μ,S/N) surface + Wilson CIs. **Caught + fixed a statistic artifact** (reduced-χ² whitened by template-only noise = 1+a² → high-μ copies wrongly cut; now full-noise whitening → ~1 at all μ, ε monotonic). |
| W2.7 **Null benchmark (GATE)** | 🟢 done — PASS (qualified) | `src/echo_frb/search/benchmark/{gate,full_criterion}` + `tests/test_benchmark.py` **2/2**. `docs/WP2_null_benchmark.md`. **Key finding:** copy-only FP is dominated by real intrinsic morphology (real 7.7% ≫ xpair 0.07% > surrogate 2.1%). **Full criterion (copy + MANDATORY achromaticity + robustness): real-null FP 7%→0%, efficiency 79%, deterministic artifacts→0%.** Added **spectral-magnification-flatness** diagnostic (9th) → scintillation 80%→36% (bounded propagation residual per §11, not eliminated). Thresholds provisional → freeze in W2.9. |
| W2.8 Local→global significance (design + null-calibrate) | 🟢 done | `src/echo_frb/search/significance/{global_fap,run}` + `tests/test_significance.py` **4/4**. `docs/WP2_global_significance.md`. Machinery: **source-level cluster bootstrap of catalog-max + GPD tail (out-of-sample validated) + empirical resolution 1/B**. **Null-calibration finding:** neither Δχ² (brightness-dominated → point mass) nor NCC (saturates at 1.0) is a valid standalone global statistic → global significance must use the **full candidate criterion** (real-null candidates ~0). Final ranking stat (brightness-fair local p-value) freezes in W2.9; catalog-global run = WP4. |
| W2.9 Versioned package + preregistration draft + tests | 🟢 done | **Frozen** `config/wp2_analysis_config.yaml` (`wp2-frozen-v1`, 2026-07-23) — candidate criterion, robustness tolerances, statistic params, global-sig method all sealed. `docs/WP2_preregistration.md` (Appendix A, all 17 items) + `docs/WP2_gate_memo.md`. `tests/test_wp2_frozen.py` asserts config==code constants. **Full suite 105 pass / 6 skip.** |

**✅ WP2 COMPLETE — gate PASS (qualified). Recommend Authorization C → WP3 (blind-injection validation). Frozen: `wp2-frozen-v1`.**

## Notes
- Prerequisite: WP1 gate PASS (`docs/WP1_gate_memo.md`) → Authorization B. ✅
- Not started — planning complete, awaiting go to execute W2.0.
