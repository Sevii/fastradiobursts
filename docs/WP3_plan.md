# Project ECHO-FRB — WP3 Plan: Blind Injection Validation

## Context

WP1 passed its gate (the published ACF trigger is under-determined; only FRB 20190131D is robust). WP2
answered that fragility with a masked, noise-weighted 2-D copy statistic + a realistically calibrated
empirical null, and **froze the entire analysis** into `wp2-frozen-v1`
(`config/wp2_analysis_config.yaml`, hash `3712e96faa969fcc`; preregistration `docs/WP2_preregistration.md`). WP2
reported, **on the development split**, a full-criterion detection efficiency of **79%** with a
real-null false-positive rate driven to **~0%** and all deterministic artifacts rejected
(`docs/WP2_null_benchmark.md`).

WP3 is the proposal's **blind gate before any catalog search** (§5.8, §8 WP3 row, Authorization C). It
takes the **already-frozen** pipeline — *no new statistic, no new threshold, no tuning* — and asks a
single question on **untouched data**:

> **Gate (§8):** *does recovery agree with the predicted efficiency, and does the false-positive rate
> meet predetermined targets, on a hidden mixture the pipeline has never seen?*

WP2 measured efficiency and FP on the **development** split it was designed against. WP3 must show those
numbers **generalize out-of-sample** on the **sealed test split**, under a blind protocol that makes
it impossible to have tuned to the answer. **§8.1 stop condition: if WP3 fails, the catalog-wide search
(WP4) does not run.**

**Authorization:** C is *requested* at the WP2 gate and *granted* only if WP3 passes — WP3 itself runs on
the existing 16-core workstation (`popos`, project `.venv`), no cloud/hardware purchase. Embarrassingly
parallel over hidden items.

---

## What is fundamentally different about WP3 (vs WP2)

WP2 was *development*: build, measure, iterate, freeze. WP3 is *adjudication*: run once, blind, on data
reserved from all of that. Three properties define it and drive every decision below.

1. **The pipeline is frozen and read-only.** WP3 changes **zero** analysis code and **zero** thresholds.
   The config hash MUST equal `wp2-frozen-v1` at evaluation time (asserted in code). Any change — even a
   "harmless" one — creates a new analysis version and **forfeits this calibration** (§5.8 step 7). The
   only new code is the *harness* (controller + evaluator + unblinder), never the *analysis*.
2. **Targets are predetermined.** The pass/fail numbers are written down, timestamped, and committed
   **before the hidden set is scored** (§5.8 step 4). We do not get to look at the hidden results and
   then decide what "agreement" means. This plan proposes those targets (below); the PI signs them into
   `docs/WP3_preregistration_addendum.md` before W3.1 draws anything.
3. **One look, then a *fresh* set.** §5.8 step 5: a failed gate requires an **entirely new hidden set** —
   you may not tweak and re-score the same one (that is peeking). A finite catalog gives a finite number
   of independent hidden sets; we pre-partition the test sources so a re-do is genuinely source-disjoint,
   and we cap the number of rounds honestly.

---

## Locked-in decisions (governance carried from WP2, enforced in WP3)

- **Frozen pipeline.** `wp2-frozen-v1` only. `evaluate` asserts `sha256(config)[:16] == 3712e96faa969fcc` and
  that code constants == config (reuse `tests/test_wp2_frozen.py` machinery). No exceptions.
- **Sealed test split is the only substrate.** The hidden mixture is built **exclusively** from the
  `split == "test"` sources (**736 sources / 1140 bursts**) — never used in WP2 threshold/null design.
  Development and validation sources are off-limits to WP3 (they leaked into design).
- **Quarantine holds.** The 23 quarantined TNS (2 named ∪ published intermediates) are excluded from the
  hidden mixture. WP3 does **not** evaluate the named candidates — that is WP4, *after* this gate passes
  (§5.8 step 6).
- **Source-level everything.** Hidden-round pools, injection hosts, and null draws partition at the
  **source** level (repeaters share a source); no source appears in two blind-round pools.
- **Blind separation is code-enforced, timestamped, and auditable** even for a one-person team (see W3.1)
  — sealed controller seed, labels hash-committed before scoring, scores hash-committed before unblinding.
- **Scintillation is a declared, monitored residual — not a new gate.** WP2 bounded it at 36% (§11); WP3
  measures it out-of-sample against that bound but does **not** fail the gate on it (it is already an
  acknowledged limitation, not a copy-imitator the frozen criterion claims to reject).

---

## The blind protocol (architecture)

Three roles, code-separated, run strictly in order. Even as one operator, the *artifacts and their
commitment timestamps* enforce the discipline (§10.1: "hidden-test seeds remain inaccessible until the
blind gate is complete").

```
  ┌─ CONTROLLER (sealed seed) ─────────────────┐     ┌─ ANALYST (blind) ──────────────┐
  │ draw test-split hosts/nulls/adverse        │     │ run FROZEN pipeline per item   │
  │ build hidden items (spectra on disk)       │     │ tier1 → copy → robustness →    │
  │ write hidden_manifest.parquet  (NO labels) │──►  │        full-criterion decision │
  │ write hidden_labels.parquet    (SEALED)    │     │ write hidden_scores.parquet    │
  │ commit  SHA256(labels)+timestamp ──────────┼──┐  │ commit SHA256(scores)+ts ──────┼──┐
  └────────────────────────────────────────────┘  │  └────────────────────────────────┘  │
                                                   ▼                                       ▼
                            ┌─ UNBLIND (only after BOTH commitments exist) ────────────────┐
                            │ verify labels hash == commitment (untampered)                │
                            │ verify commit order: labels_ts < scores_ts (no peeking)      │
                            │ join scores↔labels → efficiency vs predicted, FP by class    │
                            │ evaluate PREDETERMINED gate → blind-validation report        │
                            └──────────────────────────────────────────────────────────────┘
```

- **Commitment mechanism.** The controller writes `hidden_labels.parquet` and records only its SHA256 +
  UTC timestamp in a git-committed `hidden_commitment.json`; the labels file itself stays out of the
  analyst's reach (separate popos dir; a test asserts `evaluate` never opens it). The analyst writes
  `hidden_scores.parquet`, and its SHA256 + timestamp are committed **before** `unblind` may read the
  labels. `unblind` refuses to run unless (a) both commitments exist, (b) the labels file still hashes to
  its committed value, and (c) `labels_ts < scores_ts`. This gives an auditable pre-commitment with one
  operator — the equivalent of the proposal's "blind controller or sealed script" (§5.8 step 3).
- **Controller seed is sealed:** provided at controller runtime, recorded *inside* the sealed labels
  (not in git, not in the manifest), revealed only in the post-unblind report. Determinism is preserved
  (re-running the controller with the same seed reproduces the set) without exposing it pre-unblind.

---

## The hidden mixture (§5.8 step 3)

A realistic blend the analyst cannot distinguish by eye or by metadata — three truth classes:

| Class | Truth | Built from | Reuses | Role at the gate |
|---|---|---|---|---|
| **Lensed injections** | positive | achromatic delayed copies into real single-component **test** hosts + real off-pulse, over the frozen `(Δt, μ)` grid, weighted **near threshold** (μ≈0.1–0.4) where efficiency turns over | `injection/run.py`, `adverse.generators.inject("achromatic_copy")` | **efficiency** — recovery must match W2.6 prediction |
| **Unlensed real nulls** | negative | real **test** bursts run end-to-end, NO injection = catalog-representative FP; draw prioritizes the scarce multi-component bursts (H-I stress) then fills with single-component | `blind/pipeline.run_frozen_chain` on real Tier B | **FP** — must stay rejected; multi-component subset reported stratified |
| **Adverse propagation/artifact** | negative | the 7 imitators (drift, diff-DM, diff-scattering, chromatic echo, scintillation, overlapping, RFI) into real **test** hosts | `adverse/generators.py` | **FP** — deterministic artifacts must stay rejected; scintillation monitored vs its 36% bound |

- **Mixing ratio is set by the controller and hidden from the analyst** (the analyst does not know how
  many of each, nor which item is which). Revealed only at unblind.
- **Blinding of injections:** injected items are written as ordinary Tier-B-shaped spectra indistinguishable
  in format/metadata from real nulls; the manifest carries only an opaque `item_id` and the host's public
  eligibility features (so Tier-1 can propose windows), never the truth or injection parameters.
- **Sizing (recommended, for power).** Enough items that the FP target has teeth and the efficiency
  surface is covered out-of-sample without exhausting the test split:
  - ~**300 lensed injections** spanning the `(Δt, μ, S/N)` cells, oversampling μ≤0.4 and the near-50%
    threshold region;
  - ~**300 unlensed real nulls** (real bursts, no injection — drives the catalog-representative FP; 300
    gives a 95% upper bound ~1% at 0 observed; multi-component subset reported stratified with its wider CI);
  - ~**7×40 = 280 adverse** (40 per imitator kind).
  - Total ≈ **880 items** from **one** round pool (pool 0 ≈ 771 bursts / 79 multi-component of the 733
    test sources), source-disjoint from the reserve pool. Final counts set in the addendum.

---

## Predetermined gate targets (RECOMMENDED — freeze in the addendum before W3.1)

These are the numbers the PI signs **before** any hidden item is scored. They are derived from the WP2
development results + their Wilson CIs, *not* chosen to pass. Two components, both must hold.

### G1 — Recovery agrees with predicted efficiency
The pipeline must recover injected copies **consistently with the W2.6 ε surface**, out-of-sample:
- **Marginal:** observed full-criterion efficiency `ε_obs` on lensed injections lies within the 95%
  Wilson CI implied by the W2.6 prediction (`ε_pred ≈ 0.79` marginal) for the round's N — i.e. no
  significant deficit **or** excess. Recommended acceptance band: **|ε_obs − ε_pred| ≤ 0.07** *and* CIs
  overlap.
- **Surface coverage:** in populated `(μ, S/N)` cells, **≥ 90%** have `ε_obs` inside the predicted cell's
  95% CI, with **no systematic signed bias** (mean deviation within ±0.05). This catches a pipeline that
  passes on average but is miscalibrated where it matters (near threshold).
- **Shape sanity:** `ε(μ)` monotonic non-decreasing; near-threshold 50% point reproduced within the
  grid step (W2.6: μ≈0.27).

### G2 — False positives meet predetermined targets
- **Real complex nulls (primary FP term):** full-criterion FP **≤ 1%** (point estimate consistent with
  the WP2 0%; the target is the 95% upper bound, so 0/300 → ≤1.0% passes).
- **Deterministic adverse (drift, diff-DM, chromatic echo, RFI, overlapping):** FP **≤ 1%** each — these
  are the artifacts the criterion claims to reject; WP2 had them at 0%.
- **Differential scattering:** FP **≤ 10%** (WP2: 8%) — near-deterministic, small allowance.
- **Scintillation (MONITORED, not a gate fail):** report FP; expected **≤ 45%** (WP2 36% + CI). Exceeding
  it is flagged as a widened known-limitation, **not** a WP3 failure — but a *gross* excess (e.g. >60%)
  is escalated to the PI as evidence the propagation residual is worse out-of-sample than modeled.

### Gate verdict
**PASS = G1 ∧ G2** (with scintillation within its monitored bound). **FAIL** on either → the pipeline is
revised, a **new** analysis version is cut, and an **entirely new, source-disjoint** hidden set is drawn
from a reserve pool (§5.8 step 5). WP4 does not run on a failed gate (§8.1).

---

## Task pipeline (dependency-ordered)

```
W3.0 Blind-test foundation ──► W3.1 Controller (sealed) ──► W3.2 Frozen evaluator (blind)
   (pools, addendum, freeze)      (hidden set + commit)        (scores + commit)
                                                                     │
                                                                     ▼
                                                     W3.3 Unblind + gate assessment
                                                                     │
                                                                     ▼
                                          W3.4 Blind-validation report + gate memo + tests
                                              PASS → Authorization C → WP4 · FAIL → new set
```

### W3.0 — Blind-test foundation: pools + predetermined targets + freeze contract
- **Partition the 733 non-quarantined test sources into K = 2 disjoint blind-round pools** at the
  source level, deterministically (hash split, salt `echo-frb-wp3-blind-v1`). Round 1 uses pool 0 (the
  larger, multi-component-richer pool: ~771 bursts / 79 multi-component); a re-do uses pool 1 — genuinely
  source-disjoint so the analyst never re-sees a source. **K=2 not 3** because the test split holds only
  **96 multi-component bursts total** (repeaters cluster them), and finer partitions leave a round too
  small. **Honest cap:** after 2 failed rounds we stop drawing and redesign at the methodology level
  (a finite catalog yields finitely many independent hidden sets — §8.1, §11 look-elsewhere depth).
- **Freeze the predetermined targets** (G1/G2 above, with final N-driven CIs) into
  `docs/WP3_preregistration_addendum.md`, timestamped. This is the only "preregistration" step in WP3 —
  it does **not** touch `wp2-frozen-v1`; it records the *gate arithmetic* the addendum commits us to.
- **Assert the freeze contract:** config hash == `3712e96faa969fcc`, code constants == config, quarantine v2 and
  the source split unchanged since WP2. A test fails loudly if any drifted.
- Artifacts: `config/wp3_blind_config.yaml` (pool salt, mixture recipe, target numbers — *harness* config,
  distinct from the frozen analysis config), `blind_round_pools.parquet`, the addendum.

### W3.1 — Blind controller: sealed hidden-mixture generator
- `src/echo_frb/search/blind/controller.py` — from a **sealed seed**, draw hosts/nulls/adverse from the
  active round pool, build the three-class mixture, and write hidden spectra to popos. Reuses
  `injection.run`, `adverse.generators`, `nulls.build` — **no new signal physics**, just orchestration +
  blinding.
- Emit **two** files: `hidden_manifest.parquet` (opaque `item_id` + host public features, **NO** truth)
  and `hidden_labels.parquet` (`item_id → {class, injection params, host tns, controller seed}`, SEALED
  to a popos dir the analyst code cannot read). Write `hidden_commitment.json` (SHA256(labels) + UTC
  timestamp) and **git-commit it**.
- Deterministic given the seed (re-derivable for audit). Tests: determinism, manifest carries no truth
  columns, commitment hash matches.

### W3.2 — Frozen-pipeline evaluator (analyst side, blind)
- `src/echo_frb/search/blind/evaluate.py` — for each `item_id` in the manifest, run the **frozen**
  chain end-to-end: `tier1.scan` → `copy.score` → `robustness.diagnostics` → `benchmark.full_criterion`
  → per-item **candidate / not-candidate** decision + all sub-scores. **Asserts config hash first**;
  refuses to run against a mutated config.
- Blind by construction: reads only `hidden_manifest.parquet` + the hidden spectra; a test asserts the
  module never opens the labels path. Emit `hidden_scores.parquet` (`item_id → decision + Δχ², NCC,
  reduced-χ², achromaticity pass, robustness n_pass, ...`). Commit SHA256(scores) + timestamp **after**
  scoring, **before** unblind is permitted.
- CPU-parallel across items (multiprocessing), same as the WP2 scans.

### W3.3 — Unblind + gate assessment
- `src/echo_frb/search/blind/unblind.py` — guardrails first: both commitments exist, labels untampered
  (hash matches), `labels_ts < scores_ts` (no peeking). Only then join scores↔labels.
- **G1:** compute `ε_obs` marginal + `(μ, S/N)` surface with Wilson CIs; compare cell-by-cell to the
  W2.6 prediction (`injection_recovery.parquet`); coverage %, signed bias, monotonicity, threshold point.
- **G2:** FP by null class (real complex, each adverse kind) with Wilson CIs vs the predetermined targets;
  scintillation reported against its monitored bound.
- Emit the gate verdict + every number the report needs; reuse `injection.efficiency` and
  `benchmark.gate` so the arithmetic is identical to WP2's, not a re-implementation.

### W3.4 — Blind-validation report + gate memo + tests
- `docs/WP3_blind_validation_report.md` (the proposal deliverable): predetermined targets (as committed),
  the **revealed** mixture recipe + controller seed, observed efficiency vs predicted (surface + marginals
  + CIs + coverage), FP by class vs target, the full audit trail (commitment hashes + timestamps proving
  the blind order), and **PASS/FAIL**.
- `docs/WP3_gate_memo.md`: recommendation — **PASS → Authorization C confirmed → proceed to WP4**
  (named-candidate unblinding, then frozen catalog scan); **FAIL → revise + new analysis version + fresh
  source-disjoint hidden set**, WP4 blocked (§8.1). The final authorization is the PI's.
- `tests/test_wp3_blind.py`: controller determinism + no-truth-leak, blindness enforcement (evaluate
  can't read labels), commitment/tamper detection, ordering guard, unblind arithmetic on a synthetic
  set, gate logic (a seeded pass-set passes, a seeded fail-set fails). Artifact-gated golden on the real
  hidden set (`ECHO_FRB_WP3_ARTIFACTS`), mirroring `test_wp1_golden.py`.

---

## Deliverables → gate mapping

| Deliverable (proposal §8, §12) | Produced by |
|---|---|
| Blind-validation report (efficiency agreement + FP vs targets + audit trail) | W3.3, W3.4 |
| Predetermined-target preregistration addendum (timestamped, pre-scoring) | W3.0 |
| Hidden mixture + sealed labels + commitment (auditable blind trail) | W3.1 |
| Frozen-pipeline scores on untouched test data | W3.2 |
| Gate memo (Authorization-C recommendation) | W3.4 |
| Automated tests (blindness, commitment, gate logic) | W3.4 |

**Gate (§8):** recovery **agrees with predicted efficiency** (G1) **and** false positives **meet
predetermined targets** (G2), on a hidden mixture the frozen pipeline never saw. §8.1: WP4 is blocked if
this fails.

---

## Reused WP2 infrastructure (do not reinvent — WP3 adds a *harness*, not analysis)

| Need | Reuse | Path |
|---|---|---|
| Inject achromatic copies / adverse imitators | `adverse.generators.inject`, `injection/run.py` | `src/echo_frb/search/{adverse,injection}/` |
| Real / complex null construction | `nulls/build.py` | `src/echo_frb/search/nulls/` |
| Frozen scoring chain (tier1 → copy → robustness → full criterion) | `tier1.scan`, `copy.score`, `robustness.diagnostics`, `benchmark.{full_criterion,gate}` | `src/echo_frb/search/` |
| Efficiency surface + Wilson CIs (predicted vs observed) | `injection.efficiency` | `src/echo_frb/search/injection/efficiency.py` |
| Sealed source split (test reserve) | `source_split.parquet` (`split=="test"`) | popos `~/frb_catalog2_prep/wp2/` |
| Quarantine v2 gate | `experiment.quarantine` + config `quarantine` | `src/echo_frb/search/experiment/` |
| Config-freeze assertion | `tests/test_wp2_frozen.py` machinery + `sha256(yaml)[:16]` | `config/`, `tests/` |
| Provenance / determinism | `content_sha256`, experiment DB | `src/echo_frb/preprocess/standardize.py`, `experiment/db.py` |

## Layout & compute

- New namespace `src/echo_frb/search/blind/`: `controller.py`, `evaluate.py`, `unblind.py`, `run.py`
  (orchestration + commitment guards). **No analysis code changes.**
- New **harness** config `config/wp3_blind_config.yaml` (pool salt, mixture recipe, gate targets) —
  hashed, distinct from and **not modifying** `wp2-frozen-v1`.
- Data on popos `~/frb_catalog2_prep/wp3/`: `blind_round_pools.parquet`, `hidden/round1/{hidden_manifest,
  hidden_labels,hidden_scores}.parquet` + hidden spectra, `hidden_commitment.json`,
  `scores_commitment.json`, `blind_validation.parquet`. Tier C/D, regenerable from Tier B + sealed seed.
- Compute: existing 16 cores / 64 GB / project `.venv`; parallel over ~920 items. No GPU, no cloud
  (cloud is what Authorization C *unlocks* for WP4, not what WP3 spends).

## Verification / exit gate

1. Freeze contract holds: config hash == `3712e96faa969fcc`, code == config, quarantine + split unchanged
   (asserted; loud failure otherwise).
2. Blind trail is auditable: labels committed before scoring, scores committed before unblind, labels
   untampered — all provable from `*_commitment.json` timestamps + hashes.
3. Analyst side is provably blind: `evaluate` never reads the labels path (test-enforced); manifest
   carries no truth columns.
4. G1: `ε_obs` matches the W2.6 prediction within the predetermined band, surface coverage ≥90%, no
   signed bias, monotonic, threshold reproduced.
5. G2: real-null and deterministic-adverse FP within predetermined targets; scintillation within its
   monitored bound (or escalated).
6. Every number in the report regenerates from a versioned command; the sealed seed is revealed only
   post-unblind; a re-do (if any) uses a source-disjoint reserve pool.

## Risks / open items

- **Unblinding discipline is the dominant risk.** Mitigation: code-enforced commitment ordering + tamper
  check + blindness test; the *arithmetic* of the gate is fixed in the addendum before scoring.
- **Dev→test population shift could look like a pipeline failure.** A ε deficit might be a genuine bug
  *or* a benign host-population difference (test hosts fainter/wider). Mitigation: G1 is evaluated on the
  `(μ, S/N)`-stratified surface, not just the marginal — a uniform stratified deficit implicates the
  pipeline; a shift concentrated in under-sampled cells is diagnosed as population, reported, not silently
  passed.
- **Test-set exhaustion + scarce hard nulls.** Finite sources ⇒ **2** independent hidden rounds
  (pre-partitioned K=2). A 2nd failure triggers redesign, not more draws — the honest §8.1/§11 limit. The
  test split holds only **96 multi-component bursts** (the hard H-I null); they cannot be fragmented, so
  the real-null FP is gated on all-morphology real bursts with the multi-component subset reported as a
  stratified stress statistic (small n → wide CI, honestly flagged).
- **Predetermined targets chosen too loose (rubber-stamp) or too tight (guaranteed fail).** Mitigation:
  targets derive from WP2 CIs and are PI-signed before W3.1; this plan states the recommended values
  openly for review.
- **Scintillation residual worse out-of-sample.** Monitored, not gated; a gross excess (>60%) is escalated
  as a widened §11 limitation feeding the H-LP extension — it does not silently sink or silently pass WP3.
- **Accidental peek / label leakage.** Sealed labels live in an analyst-inaccessible popos dir; the seed
  is inside the sealed file; a test asserts the evaluator's file access set excludes both.

## Decisions needed from the PI (before W3.1 draws the set)

1. **Sign off the predetermined targets** (G1 band, G2 FP bounds, scintillation monitored bound) — or
   amend. These freeze in the addendum and cannot change post-scoring without a new hidden set.
2. **Mixture sizes / ratios** (~300 inj / ~300 real-null / ~280 adverse) and **K=2** pools (1 primary +
   1 fresh re-do) — set as defaults; confirm or adjust.
3. **Blind-controller model:** the code-enforced sealed-seed + hash-commitment scheme described here
   (recommended for a one-person team), or a second person acting as an independent blind controller.
