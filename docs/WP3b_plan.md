# WP3b Plan — End-to-End Per-Burst Max-Statistic Calibration (`wp2-frozen-v2` / `wp3-blind-v2`)

**Status:** planning → implementation. **Opened:** 2026-07-24.
**Predecessor:** WP3 round 1 — **GATE FAIL** (`docs/WP3_gate_memo.md`). WP4 remains blocked (§8.1).
**Source design:** `docs/SecondWP3Approach.md`, Approach 1 (the recommended baseline).

---

## 1. What failed and what this fixes

WP3 round 1 failed G2: run end-to-end on the hidden set, the adverse imitators passed the frozen
criterion at 25–70% against targets of 1–10%. The cause is diagnosed, not guessed
(`docs/WP3_gate_memo.md` §3): WP2's benchmark scored **one oracle window per burst**, while the search
flags a burst if **any** of its ~8 Tier-1 proposals passes. The per-window false-positive rate was never
the operative quantity.

Approach 1 does not remove that multiplicity — **it prices it.** The reported quantity becomes the
per-burst maximum over the proposal set, calibrated against null realizations that went through the
*entire* search, proposal selection included:

```
  M_i = max_{j=1..m_i} T_ij            T_ij = the weakest standardized gate margin of proposal j
  p_i = (1 + #{ M_b^(0) >= M_i }) / (B + 1)     per null family h, conditioned on covariates Z_i
  p_i^robust = max_h p_ih                       the most adverse family sets the threshold
```

This answers the question the pipeline actually asks — *how exceptional is the best candidate found
after conducting the entire search?* — and it changes neither the physical signal model nor the window
proposer.

**Expected cost.** Paying the true multiplicity penalty will lower sensitivity, possibly a lot. That is
an honest scientific result, not a method failure — but it must be measured **before** the last sealed
pool is spent. Hence §4.

---

## 2. The binding resource constraint (measured 2026-07-24)

The sealed test split was pre-partitioned into K=2 source-disjoint pools. Round 1 burned pool 0. What
remains:

| | pool 0 (burned) | **pool 1 (remaining)** |
|---|---:|---:|
| sources | 374 | 359 |
| bursts | 771 | **362** |
| multi-component (hard nulls) | 79 | **17** |
| repeater bursts | 409 | 5 |

Two consequences, both structural:

1. **The round-1 mixture recipe does not fit.** 300 real-null + 300 injection hosts + 40 adverse hosts =
   640 distinct bursts, against 362 available. Round 2 must be resized (§6).
2. **Pool 1 can only be the gate, never the calibration.** With 17 hard nulls, pool 1 cannot estimate a
   1% false-positive tail; it can only *test* a calibration built elsewhere. Every threshold, scale
   constant, stratum boundary and α must be frozen before the controller draws.

Per §8.1 / §11, a second failure means **redesign, not another draw**. This is the last blind round the
catalog supports.

### 2.1 Where the calibration comes from instead

| split | sources | bursts | multi | status |
|---|---:|---:|---:|---|
| development | 2176 | 2541 | 174 | used throughout WP2 — the design set |
| **validation** | **710** | **835** | **46** | **untouched by WP2** (nulls, injections and the W2.7 benchmark all ran on `split == "development"`) |
| test pool 1 | 359 | 362 | 17 | sealed — the round-2 gate |

The validation split is not a blind set — it sits on the "we may look" side of the wall, and the WP3
round-1 plan correctly excluded it from the *hidden* mixture on those grounds. But it was never used to
choose a threshold, so it is a legitimate **held-out dry run**: build on dev, dry-run on validation,
gate on pool 1.

**Compute is not a constraint.** `run_frozen_chain` measures at ~0.08 s/burst on popos (32 cores);
a 10^5-realization null ensemble is well under an hour. The limit is the supply of *real hard nulls*,
exactly as `SecondWP3Approach.md` §"Handling the limited hard-null sample" anticipates.

---

## 3. The statistic

### 3.1 Per-proposal margin `T_ij`

For diagnostic `k` with frozen threshold `c_k` and prespecified scale `s_k`:

```
  z_k =  (x_k - c_k) / s_k     for gates where LARGER passes
  z_k =  (c_k - x_k) / s_k     for gates where SMALLER passes
  T   =  min_k z_k
```

The terms are exactly the frozen v1 **mandatory** gates, plus the robustness vote as a count margin:

| # | quantity | gate | direction |
|---|---|---|---|
| 1 | `log10 Δχ²` | > log10 100 | larger |
| 2 | `ncc` | > 0.40 | larger |
| 3 | `reduced_chi2` | < 1.5 | smaller |
| 4 | `delay_spread_bins` | ≤ 1.5 | smaller |
| 5 | `mag_rel_spread` | ≤ 0.6 | smaller |
| 6 | `spectral_mag_reduced` | < 2.0 | smaller |
| 7 | `n_pass` | ≥ 7 | larger (`(n_pass − 7 + 0.5)/1`) |

Term 4 covers both `achromatic_delay_pass` and `dm_scattering_pass` (same underlying quantity in
`robustness/diagnostics.py`); term 3 covers both `copy_reduced_chi2` and `residual_structure_pass`;
term 2 covers both `copy_ncc` and `fine_structure_pass`.

`leave_band_out_min_frac`, `resolution_ncc_spread` and `window_ncc_spread` are **not** mandatory in v1 —
they are votes. They therefore enter `T` only through term 7, and are recorded separately as covariates
and as a secondary statistic `T_all` (min over *all* gates) for sensitivity reporting.

**Exact-equivalence property (unit-tested):** `T_ij > 0` ⟺ proposal `j` passes the frozen v1 full
criterion, and `sign(max_j T_ij)` ⟺ v1 `is_candidate`. So v2 preserves v1's interpretation rather than
replacing it.

`Δχ²` is taken on a log scale because it spans orders of magnitude. Scales `s_k` are frozen from the
robust (MAD) spread of each diagnostic across dev real-null proposals (W3b.2) — prespecified constants
written into the v2 config, never re-tuned after the dry run.

**NaN handling.** A diagnostic that is NaN *and* whose v1 pass flag is `False` (e.g. `delay_spread_bins`
when fewer than 2 bands are usable) contributes `−inf` — a hard fail. A diagnostic that is NaN and
whose v1 flag defaults to `True` (e.g. `spectral_mag_reduced` with fewer than 6 usable channels) is
uninformative and is **omitted from the min**. Both are recorded so the frequency of each is auditable.

**Cost note.** As in v1, robustness diagnostics run only on proposals that clear the copy gates. For a
proposal that fails a copy gate, `T` is computed from the copy margins alone and is therefore an *upper
bound* on the true margin. This is safe in the only direction that matters: such a proposal has `T < 0`,
can never produce a candidate, and can only push a null `M` upward, which makes p-values larger and the
decision more conservative. A computed `M > 0` always comes from a proposal whose robustness was fully
evaluated, so it is exact.

### 3.2 The decision rule

```
  candidate(burst i)  ⟺  M_i > 0        (all frozen v1 gates pass on some proposal)
                    AND  p_i^robust ≤ α  (that best proposal survives the multiplicity penalty)
```

Both conditions, deliberately. `M_i > 0` alone is v1. `p ≤ α` alone could admit a burst that fails a
frozen gate but happens to look unexceptional against a badly-behaved null family. Requiring both makes
v2 a **strict subset** of v1 — a tightening with a calibrated size, which is the whole point.

### 3.3 Null families

Every realization runs the complete chain: proposal → delay search → copy fit → achromaticity →
robustness → best-proposal selection.

| family `h` | construction | role |
|---|---|---|
| `real` | dev bursts, no injection | catalog-representative FP |
| `real_multicomponent` | the 174 dev multi-component bursts | the hard null (H-I) |
| `surrogate_block_bootstrap` / `_phase_randomization` / `_tf_permutation` | structure-preserving surrogates | envelope kept, copy relation destroyed |
| `adverse:drift` / `:differential_dm` / `:chromatic_echo` / `:rfi_remnant` / `:overlapping` | deterministic imitators | H-N / H-I controls |
| `adverse:differential_scattering` | near-deterministic propagation | H-P |
| `adverse:scintillation` | frequency-modulated near-copy | H-P — **GATED in v2** (PI decision, 2026-07-24) |

`p^robust = max_h p_h` — equivalently, the threshold is set by the most adverse family rather than by a
pooled average null that would dilute scintillation.

**Scintillation is promoted from monitored residual to gated family.** This is the substantive
strengthening over v1, and it is the term expected to dominate `max_h`: dev scintillation passes the v1
criterion at 55% end-to-end, so demanding `p_scint ≤ α` forces `M` above the far tail of the
scintillated-burst distribution. §11's caveat still stands — plasma is not a finite model, so this
bounds the scintillation false positive, it does not eliminate it.

Cross-event pairs (`xpair`) splice components from two different bursts and so have no whole-burst
end-to-end analogue; they are retained as a per-proposal supplementary null, not as an `M` family.

### 3.4 Conditional calibration

`P0(M ≥ m | Z)` is estimated per family, conditioned on `Z`: proposal count `m_i` (the direct
multiplicity driver — dev bursts range 1–10 proposals, median 3), burst SNR, effective bandwidth,
masked-channel fraction, temporal width, multi-component flag, repeater flag, minimum proposed delay.

Method: **stratified empirical distributions on (m_i, SNR) bins, plus a generalized Pareto tail above a
prespecified high quantile** within each stratum, with **source-cluster bootstrap** confidence intervals
(repeaters contribute dependent bursts). Conditioning matters because otherwise high-SNR, proposal-rich
bursts dominate the extreme tail and force an unnecessarily severe threshold on clean bursts.

**Tail honesty rule (non-negotiable, from `SecondWP3Approach.md`):** every quoted tail probability
reports what fraction is empirical and what fraction is GPD extrapolation. No 10^-4 claim is made
because a fitted curve reaches there. The GPD threshold is prespecified, not chosen by fit quality.

---

## 4. The pre-registered go/no-go (PI decision, 2026-07-24)

The dry run on validation produces an operating curve: false-positive rate per family versus α, and
detection efficiency versus (μ, Δt, SNR) at each α. α is then chosen as the largest value meeting **all**
pre-registered FP targets simultaneously.

> **GO/NO-GO:** if, at that α, end-to-end detection efficiency for **μ ≥ 0.5** injections is **< 30%**,
> pool 1 is **not** spent. The result is reported as an observable-space upper limit, and the project
> pivots to Approach 2/3 or to a redesign.

Round 1 measured 45.7% overall efficiency under v1 without paying any multiplicity penalty, so 30% for
bright copies is a meaningful but not vacuous floor. This threshold is fixed now, before any v2 number
exists, and is not revisable after the dry run.

---

## 5. Phase sequence

```
   dev split (2541 bursts)          validation split (835)         test pool 1 (362) — SEALED
  ┌────────────────────────┐      ┌────────────────────────┐     ┌─────────────────────────┐
  │ W3b.1 margin statistic │      │ W3b.6 DRY RUN          │     │ W3b.8 BLIND ROUND 2     │
  │ W3b.2 freeze scales    │ ───► │  FP vs alpha per family│ ──► │  controller (sealed seed)│
  │ W3b.4 null M ensembles │      │  efficiency vs (mu,dt) │     │  analyst (blind)        │
  │ W3b.5 conditional cal. │      │  pick alpha, GO/NO-GO  │     │  unblind vs targets     │
  └────────────────────────┘      └───────────┬────────────┘     └─────────────────────────┘
                                              │ NO-GO ⇒ upper limit / Approach 2-3, pool 1 preserved
                                   W3b.7 freeze wp2-frozen-v2, PI signs addendum
```

| task | deliverable |
|---|---|
| W3b.0 | this plan |
| W3b.1 | `src/echo_frb/search/margin/` — `T_ij`, `M_i`, equivalence test |
| W3b.2 | frozen `s_k` constants → `config/wp2_analysis_config_v2.yaml` |
| W3b.3 | `overlapping` generator fixed to inject **below** Δt_min (gate-memo item 3) |
| W3b.4 | per-family end-to-end null `M` ensembles + covariates `Z` on dev |
| W3b.5 | conditional calibration (stratified empirical + GPD tail + cluster bootstrap) |
| W3b.6 | validation dry run, operating curve, **go/no-go verdict** |
| W3b.7 | `wp2-frozen-v2` freeze, G1 coverage metric fix, resized round-2 mixture, preregistration addendum for PI signature |
| W3b.8 | blind round 2 on pool 1 — one shot |

---

## 6. Round-2 mixture (resized for pool 1)

Proposed, subject to the addendum signature. 362 bursts available; roles stay disjoint at the burst
level, sources already disjoint from pool 0 by construction.

| class | items | distinct bursts | note |
|---|---:|---:|---|
| `real_null` | 180 | 180 | all 17 multi-component + 163 single |
| `injection` | 140 | 140 | one host each, frozen (Δt, μ) grid, near-threshold oversampled |
| `adverse` | 280 | 40 | 7 kinds × 40 hosts (hosts reused across kinds, as in round 1) |
| **total** | **600** | **360** | |

The gate-critical measurement — adverse FP, the class that failed round 1 — remains well powered at
n=40 per kind. The scarce class is real multi-component nulls at n=17; that stratum will be **reported
with its Wilson interval, not gated**, and the honest statement is that pool 1 cannot resolve a 1%
hard-null FP. This limitation is recorded now, pre-scoring, not discovered afterwards.

---

## 7. Carried-forward fixes from the round-1 gate memo

1. **Multiplicity control** — this plan (Approach 1). Gate-memo item 1.
2. **G1 coverage metric** → two-sample CI-overlap test. The round-1 metric mis-fired at 0.21 as a
   tight-predicted-CI vs noisy-observed-cell artifact while the underlying agreement was fine
   (obs 0.457 vs pred 0.474). Gate-memo item 2. → W3b.7.
3. **`overlapping` generator** injects at 3 bins ≈ 2.95 ms, *inside* the Δt ≥ 2 ms search domain, so the
   pipeline was arguably detecting a real short-delay copy rather than producing a false positive. Fix:
   derive `dt_small` from the burst's ms/bin so `dt · mpb < dt_min_ms` (2 bins at 0.983 ms/bin). Gate-memo
   item 3. → W3b.3.

## 8. Governance

- Any change to the analysis config creates a new version and **forfeits the WP2 calibration** (§5.8
  step 7). v2 is exactly that: `wp2-frozen-v2`, new hash, freeze contract updated, WP2 numbers not
  inherited.
- Quarantine holds (23 TNS). The named candidates are **not** evaluated — that is WP4, after this gate.
- Source-level everything: strata, bootstrap clusters, pools, host draws.
- Blind discipline unchanged from round 1: sealed seed, labels hash-committed before scores committed
  before unblind, enforced by `unblind`'s tamper + ordering + freeze guards.
- α, the `s_k` constants, the stratum boundaries, the GPD threshold and the go/no-go floor are all
  frozen and git-committed **before** the W3b.8 controller runs.
