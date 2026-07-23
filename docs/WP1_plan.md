# Project ECHO-FRB — WP1 Reproduction Plan

## Context

WP0 (data audit) is complete: the public CHIME/FRB Catalog 2 archive is downloaded, sealed as
immutable **Tier A** (22,755 files / 64.3 GB, checksummed) and standardized into **Tier B**
(4,532 `<TNS>_tierb.h5` products) on the `popos` workstation, with manifests, an eligibility table,
QC, and benchmarks. All approvals are in; **Authorization A/B** (WP0–WP1 on existing hardware) is granted.

**WP1's job** (proposal §5.1, §8): *literal and clean-room reproduction of the previously reported FRB
lensing candidates* — Zhou et al. 2026, "Evidence for Intermediate-Mass Black Holes From Microlensing
Signatures in CHIME/FRB Catalog 2" (arXiv:2605.19653; code: `github.com/Huan-Zhou-spec/MICRO-FRB`).
We reproduce their pipeline **as literally as possible**, then **independently (blind)** reimplement it
from the paper, and determine which reported statistics reproduce, approximately reproduce, or fail —
tracing every discrepancy to a cause. The outcome is the **reproducibility matrix + technical note**, and
it feeds the WP1 gate and the §8.1 stop-condition (redesign if the public data cannot reproduce the claim
because essential inputs are unavailable/undocumented).

**Scope decisions (confirmed with user):**
- **Stop at detection + Δt/μ.** Reproduce the ACF/KS/morphology screening down to the intermediate
  candidate list and the two named candidates, incl. their measured **time delays and flux ratios**.
  Do **not** reproduce redshifted lens masses or f_PBH in WP1 (those belong to WP5; hardness-ratio
  *consistency* is still run where it acts as a **selection cut**, but derived masses are not reported).
- **Blind clean-room.** The clean-room track is implemented from the paper's equations/thresholds + our
  Tier B schema only, by an implementer **blind to the MICRO-FRB repo**, so a literal-vs-clean-room
  discrepancy is a genuine independent-reproduction signal.

---

## The reproduction target (what we must match)

**Method (paper):** normalized light-curve autocorrelation `C(δt)`; a lensed copy produces spikes at
`δt = ±Δt` with amplitude ratio `R_f/(R_f²+1)`. A spike is significant if it exceeds **3σ** relative to a
Gaussian-smoothed `C` (kernel σ=3). Screening chain: peak-match within **±2 ms**, temporal ordering
(main before secondary), secondary **PSNR > 10**, pair includes the global-max peak, **K-S** frequency-drift
test (n_f=512, D_crit≈0.1 @ α=0.05, D_n,upp from 1000 bootstraps), then a 3-band **hardness-ratio**
consistency check (1σ).

**Selection funnel to reproduce:** 340 multi-peak FRBs → ACF/KS → **11** candidates → **9** (after subjective
morphology reassessment) → **2** final. Repo's `SG_20/lens_catalog_summary.csv` actually lists **16**
initial candidates, and results differ across three smoothing configs (`G_3`, `SG_20`, `SG_100`) — these
inconsistencies are precisely what the reproduction must surface.

**Named candidates (reference values):** FRB 20190131D Δt=8.82 ms, R_f≈0.35(ep1)/0.55(ep2); FRB 20211115A
Δt=6.86 ms, R_f≈0.37/0.38. (Abstract lens-mass mapping 20190131D→[539–609] M☉, 20211115A→[1544–2571] M☉
appears internally swapped vs. the body — a to-resolve item, but out of WP1's reporting scope.)

**Repo facts / repro risks:** Python; **no requirements.txt, no license**; `random_seed=42`; hard-coded
`__main__` params & relative paths; only 1 of ~340 `.h5` bundled (rest from CANFAR
`CISTI.CANFAR/25.0066/data/dynamic_spectra/`); `fpbh.py` and `Hardness_test.py` **hard-code** headline
results rather than regenerating them. Full detail in memory `wp1-reproduction-target.md`.

---

## Locked-in decisions

- **Runs on `popos`, code in this repo** (same as WP0): develop in `~/Projects/fastradiobursts`, execute via
  `ssh popos` against the data using the project `.venv/bin/python`.
- **Reuse Tier A as their input if byte-equivalent to CANFAR** (verified in W1.1); this ties both provenance
  chains and avoids a 60 GB re-download. Fall back to CANFAR only for files that differ or are missing.
- **Two isolated environments.** The MICRO-FRB repo runs in its own reconstructed/pinned env
  (`env/microfrb_repro.lock`); the clean-room track uses our WP0 env. Never mix.
- **Quarantine still governs downstream.** WP1 is the *only* sanctioned place to evaluate the two named
  candidates (proposal §3.2). We run and record them here, but their scores are written to a quarantined
  path and must not influence WP2+ thresholds. Reuse the existing quarantine mechanism.
- **New code is additive** under `src/echo_frb/repro/`; nothing in WP0's Tier A/Tier B/manifests is modified.

---

## Layout

```
src/echo_frb/repro/
├── target/       W1.0  clone-seal MICRO-FRB, extract authors' reported values
├── ingest/       W1.1  CANFAR↔Tier A equivalence, reconstruct the 340-set
├── literal/      W1.2  thin runners around their scripts (their env)
├── cleanroom/    W1.3  BLIND reimplementation from the paper (our env)
├── selection/    W1.4  per-stage candidate-selection reconstruction
├── sensitivity/  W1.5  one-axis-at-a-time robustness sweeps
└── matrix/       W1.6  reproducibility matrix + note assembly
tests/            W1.7  determinism + golden-value + selection-invariant tests
docs/             WP1_plan.md, WP1_reproduction_note.md, candidate_reproduction_report.md
```
On popos (generated, not in git): `~/frb_catalog2_prep/wp1_repro/` →
`microfrb_repo/` (sealed) · `authors_reported_values.yaml` · input manifests · `literal_run/` ·
`cleanroom_run/` · `sensitivity/` · `reports/`.

---

## Task pipeline (dependency-ordered)

```
W1.0 Seal target ──┬─► W1.1 Input equivalence + reconstruct the 340-set
                   │
                   ├─► W1.2 LITERAL run (their repo, their env, 3 smoothing configs)
                   │            │
   (paper only) ───┴─► W1.3 BLIND clean-room reimplementation ─┐
                                                               ▼
                          W1.4 Candidate-selection chain (both tracks, per stage)
                                                               ▼
                          W1.5 Sensitivity matrix (one axis at a time)
                                                               ▼
                          W1.6 Reproducibility matrix + technical note
                                                               ▼
                          W1.7 Tests + env locks + gate memo
```

### W1.0 — Seal the reproduction target & extract its claims
- Clone MICRO-FRB at a **pinned commit**; SHA-256 every file (reuse `ingest/checksums.py:sha256_file` +
  `find_files`), seal read-only → `repro_target_manifest.parquet` (mirrors Tier A sealing).
- Reconstruct their environment: infer deps (numpy, scipy, pandas, matplotlib, h5py) from imports, pin a
  plausible 2026 version set, lock → `env/microfrb_repro.lock` (+ optional container).
- **Extract `authors_reported_values.yaml`** — the machine-readable ground truth: per-candidate Δt & R_f
  (per episode), spike significances, the intermediate candidate lists **per smoothing config** (parse the
  committed `Figures/*/lens_catalog_summary.csv`), and the selection counts (340/16/11/9/2) + all thresholds.
  This is what the reproducibility matrix compares against.

### W1.1 — Input equivalence + reconstruct the 340 multi-peak set
- **Equivalence:** compare the one bundled repo `.h5` (`FRB20181028A`) and a sample of CANFAR downloads
  against our Tier A copies (array-level + byte-level). If identical → **use Tier A as their input**; else
  document the delta and fetch differing/missing files from CANFAR into a hashed `tier_a_canfar/` area.
- **Reconstruct the 340-set:** derive their "multi-peak" selection from the bundled cat2 `.npy` +
  our manifest (`morphology_label`, `n_subbursts` from `normalize_catalog.py`); reconcile the count and
  emit `microfrb_input_manifest.parquet` (TNS → Tier A path + hash, in/out of the 340).
- Deliverable: `input_equivalence_report.md`.

### W1.2 — Literal reproduction (run their workflow as-is)
- Drive `SearchLensedFRB.py` with their exact `__main__` params (f_down=32, t_down=1, rfi_factor=3,
  smooth_sigma=3, threshold=3, n_noise=30, n_bootstrap=1000, seed=42) over the 340 `.h5`, for **all three**
  smoothing configs. Capture per-FRB ACF spikes, matched peak indices, Δt, R_f, and candidate flags.
- **Diff against their committed outputs** (`Figures/*/lens_catalog_summary.csv`, `_report.txt`) →
  `literal_vs_committed_diff.md`. Byte/value agreement = literal reproduction confirmed.
- Resolve where the hardness-consistency and morphology-reassessment steps live (in-script vs. manual);
  run the hardness step only as a **selection cut** (masses not reported).

### W1.3 — Blind clean-room reimplementation
- A **fresh implementer blind to the repo** (spawned with only paper-derived equations/thresholds + our
  Tier B schema) builds `cleanroom/`: ACF copy statistic, 3σ spike detection, peak-match/ordering/PSNR
  cuts, K-S drift test, morphology cuts. Runs on Tier B (Tier A + documented preprocessing as a variant).
- **Reuse WP0 infra:** `reference/make_plots.py:rebin_freq(arr, valid, 512)` (16384→512), `load_tier_b`,
  `preprocess/standardize.py:content_sha256`/`sha256_of` (provenance), the `_config_hash` YAML-bytes
  convention, and the `CANDIDATES` quarantine constant/flag. Emits the **same score schema** as W1.2.

### W1.4 — Candidate-selection path reconstruction
- For **both tracks**, record every FRB entering each stage and every filter removing it
  (340 → ACF>3σ → peak-match/ordering/PSNR/global-max → K-S → morphology → hardness) →
  `candidate_selection_chain.parquet` (per-FRB, per-stage pass/fail + reason, per smoothing config).
- **Reconcile 16 vs 11 vs 9 vs 2** and characterize the subjective 11→9 morphology reassessment.

### W1.5 — Controlled sensitivity analysis
- One axis at a time off the frozen literal config: RFI mask (`rfi_factor`), smoothing (G vs SG, σ/window),
  rebinning (`f_down` 16/32/64, `t_down`), time-window/episode split, background/noise regions
  (`n_noise`, `quantile_threshold`), frequency-band definitions (hardness bands, KS n_f). Record which
  candidates survive / appear / vanish → `sensitivity_matrix.parquet` + a heatmap summary. Answers which
  reported statistics are robust vs. artifacts of one preprocessing choice.

### W1.6 — Reproducibility matrix + technical note
- Assemble `reproducibility_matrix.parquet/.md`: each reported statistic (per-candidate Δt, R_f ep1/ep2,
  spike significance, intermediate-candidate membership, selection counts) × {literal, clean-room} →
  **exact / approximate / not reproduced**, with tolerance and, for discrepancies, a traced cause
  (data version · preprocessing · software · numerical tolerance · undocumented choice).
- Write `WP1_reproduction_note.md` + `candidate_reproduction_report.md` (independent evaluation of
  FRB 20190131D, FRB 20211115A, and the full published selection chain — proposal §12.2 deliverable).

### W1.7 — Tests, env locks, gate memo
- pytest mirroring WP0 conventions (`tests/test_*`, determinism idiom from `test_preprocess.py`):
  determinism of both tracks; clean-room vs golden reported values within stated tolerance;
  selection-chain invariant (every 340-set FRB has a disposition at every stage).
- Finalize `env/microfrb_repro.lock` + record clean-room env.
- **Gate memo:** reproduced OR every discrepancy explained; explicit §8.1 stop/redesign recommendation.

---

## Deliverables → gate mapping

| WP1 deliverable (proposal §8, §12.2) | Produced by |
|---|---|
| Reproducibility matrix (exact/approx/not, per statistic × track) | W1.6 |
| Technical note + candidate reproduction report (both candidates + selection chain) | W1.6 |
| Intermediate candidate table (340→…→2, per stage, per config) | W1.4 |
| Sensitivity matrix (masks, smoothing, rebinning, windows, backgrounds, bands) | W1.5 |
| Reconstructed target env lock + sealed repo manifest | W1.0, W1.7 |
| Input-equivalence report (CANFAR ↔ Tier A) | W1.1 |
| Automated reproduction tests | W1.7 |

**Gate (WP1 → Authorization B/WP2):** *"Reported candidates and intermediate statistics are reproduced, or
discrepancies are fully explained."* Plus the §8.1 stop rule: if essential inputs are unavailable/undocumented
such that the claim cannot be reproduced, publish the technical reproducibility result and **redesign** rather
than proceed.

---

## Reused WP0 utilities (do not reinvent)

| Need | Reuse | Path |
|---|---|---|
| File hashing / seal repo | `sha256_file`, `find_files` | `src/echo_frb/ingest/checksums.py` |
| Content/determinism hash, output hash | `content_sha256`, `sha256_of` | `src/echo_frb/preprocess/standardize.py` |
| Load Tier A / Tier B | `load_tier_a` (dict), `load_tier_b` | `src/echo_frb/reference/make_plots.py` |
| 16384→512 freq rebin | `rebin_freq(arr, valid, 512)` | `src/echo_frb/reference/make_plots.py` |
| Config-hash convention | `_config_hash` = SHA-256(YAML bytes)[:16] | `preprocess/standardize.py`, `eligibility/engine.py` |
| Quarantine list + gate | `CANDIDATES`, `--process-candidates` | `config/preprocessing_config.yaml`, `standardize.py` |
| Eligible list, DM/SNR/morphology, TNS→paths | eligibility + manifest parquet (join on `tns_name`) | `manifest/`, `eligibility/` |
| Test conventions (determinism, golden, skipif real-data) | `test_preprocess.py`, `test_schema_contract.py` | `tests/` |

*Caveats surfaced by exploration:* `CANDIDATES` is duplicated in 3 places (single-source from config);
implemented quarantine flag is `--process-candidates` (docs say `--frozen`); Tier B provenance omits
`env_id`/`timestamp` by design; no time-rebin helper exists (write one for `t_down`); two `load_tier_a`
signatures exist (use the dict one that pairs with `load_tier_b`).

---

## Verification (how we'll know it works)

1. **Literal:** our W1.2 run reproduces the repo's committed `lens_catalog_summary.csv` / `_report.txt`
   for all three smoothing configs (value-for-value, seed=42) → `literal_vs_committed_diff.md` shows zero
   or fully-explained deltas.
2. **Clean-room:** `cleanroom_run` recovers the two named candidates' Δt (within ±1 time bin ≈ ±0.98 ms)
   and R_f (within reported uncertainty), and its intermediate candidate set overlaps the literal set;
   divergences are logged as findings, not silently reconciled.
3. **Determinism:** re-running either track yields identical `content_sha256` (pytest, WP0 idiom).
4. **Selection invariant:** every FRB in the 340-set has a recorded disposition at every stage (pytest).
5. **End-to-end audit:** `reproducibility_matrix.md` classifies every reported statistic and the
   `candidate_reproduction_report.md` renders per-candidate audit records (proposal Appendix B schema).

---

## Open items / risks

- **340-set definition** is not explicitly pinned in the paper — reconstructed from catalog morphology in
  W1.1; a mismatch in membership is itself a reproducibility finding.
- **Morphology reassessment (11→9)** is subjective/manual — we reproduce the *inputs* and document that the
  step is not algorithmically specified.
- **Hard-coded headline results** (`fpbh.py`, `Hardness_test.py`) can't regenerate end-to-end — out of WP1
  reporting scope, noted as a target limitation.
- **Env reconstruction** (no pinned deps) may cause small numerical drift (scipy KS / Savitzky–Golay);
  W1.5 treats software version as one sensitivity axis so drift is measured, not assumed away.
- **Blind-clean-room hygiene:** the implementing agent for W1.3 must receive only paper-derived material +
  Tier B schema; keep repo details (incl. memory `wp1-reproduction-target.md`) out of its context.
