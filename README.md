# Project ECHO-FRB

**Searching CHIME/FRB Catalog 2 for gravitationally lensed echoes of fast radio bursts.**

> **Status (2026-07-25): WP4 blocked. The catalog-wide search was never authorized.**
> The blind validation gate failed twice, both sealed test pools are spent, and per the proposal's
> §8.1 stop rule the response is redesign at the methodology level rather than another draw. The
> deliverable from here is an observable-space measurement, not a candidate list —
> see [`docs/WP3b_gate_memo.md`](docs/WP3b_gate_memo.md).

---

## What this is

A gravitational lens between us and an FRB source can produce **two images of the same burst arriving a
few milliseconds apart**. In the geometric-optics limit the second image is a *delayed, scalar-magnified,
otherwise-identical copy* of the first, across the entire observing band:

```
D(t, ν)  =  S(t, ν)  +  μ · S(t − Δt, ν)  +  N(t, ν)
```

with `Δt` the lensing delay — **one value for all frequencies, i.e. achromatic** — and `μ ∈ (0,1]` the
relative magnification of the fainter image. Detecting these would probe compact-object dark matter.

This repository is the full analysis: data audit, a reproduction of two previously reported candidates, a
new detection statistic, and the blind validation that ultimately declined to authorize a catalog search.

## The signal, and why it is hard

The specificity of the prediction is the whole lever — the second component is not merely "another peak",
it is an *achromatic copy*. The difficulty is that nature imitates that constantly:

| hypothesis | signature | role |
|---|---|---|
| **H-L** strict lens | one achromatic delay, one scalar magnification, shared morphology | the target |
| **H-I** intrinsic complexity | two components, independent widths/spectra/drifts | main astrophysical false positive |
| **H-P** plasma propagation | chromatic delays, scintillation, fringes | adverse; not decisively rejectable on this data |
| **H-N** instrument/analysis | RFI remnants, mask edges, dedispersion artifacts | quality-control false positive |

Four properties of the data dominate every design decision:

1. **0.983 ms time resolution** → only *resolved* echoes are reachable. Search domain **Δt ∈ [2, 50] ms**.
2. **Rich intrinsic structure** → many bursts have *some* second-peak-like feature that is not a copy.
3. **Source-level dependence** → repeaters share morphology, so every split, null and resample is done at
   the **source** level, never the burst level.
4. **Scarce hard nulls** → only **340 of 4,539** bursts are multi-component, and those are exactly the
   population that starves the false-positive tail.

## The method

**Primary statistic — a masked, noise-weighted 2-D copy test.** For a proposed pair of component windows,
fit B as a delayed, scaled copy of A over the valid pixels:

```
χ²_copy(Δt, a) = Σ_V [ B(t,ν) − a·A(t−Δt, ν) ]² / [ σ_B²(t,ν) + a²σ_A²(t,ν) ]
```

with a closed-form magnification, a mask-aware inverse-variance rebin 16,384 → 256 channels, and an
on-burst support constraint. It yields Δχ² (detectability), NCC and reduced-χ² (copy quality).

**Candidate criterion (frozen before validation).** Detectable *and* copy-like *and* **achromatic**
(a hard gate — a single frequency-dependent delay or magnification disqualifies) *and* robust across 9
diagnostics.

**Empirically calibrated nulls**, not Gaussian noise: real complex bursts, cross-event pseudo-pairs,
structure-preserving surrogates, and eight physically-motivated adverse imitators (drift, differential
DM, differential scattering, chromatic echo, scintillation, overlapping, RFI remnant, plus an achromatic
positive control).

**The multiplicity correction (v2).** The search proposes ~8 candidate windows per burst and flags the
burst if *any* passes — so the operative quantity is a **per-burst maximum**, not a per-window rate.
v2 prices that explicitly:

```
candidate  ⟺  M_i > 0  AND  p_i^robust ≤ α        M_i = max_j T_ij ,  α = 0.05
```

where `T_ij` is the weakest standardized gate margin of proposal *j*, and `p^robust = max_h p_h` takes the
most adverse null family rather than a pooled average. `M_i > 0` is *exactly* the v1 criterion — verified
on all 2,541 development bursts with zero disagreements — so v2 is a strict tightening, not a different
analysis.

## Work packages

| WP | scope | gate |
|---|---|---|
| **WP0** | Data audit, standardization, eligibility, QC | ✅ 4,530/4,532 pass · 3,874 eligible |
| **WP1** | Literal + clean-room reproduction of the two reported candidates | ✅ **PASS** |
| **WP2** | Copy statistic, empirical nulls, frozen criterion (`wp2-frozen-v1`) | ✅ **PASS** (qualified) |
| **WP3** | Blind-injection validation, round 1 (test pool 0) | ❌ **FAIL** — multiplicity |
| **WP3b** | Max-statistic revision (`wp2-frozen-v2`) + round 2 (pool 1) | ❌ **FAIL** — `real_null` |
| **WP4** | Catalog-wide search | 🚫 **blocked** — never run |
| **WP5** | Baseband follow-up | not reached |

## Headline results

**WP1 — the published method is under-determined.** The literal reproduction is *exact*, value-for-value
across all three smoothing configurations. But an independent blind clean-room recovered only **1 of 11**
candidates, and sweeping the spike threshold moves the candidate count from **22 to 3**. Only
**FRB 20190131D** survives all 20 swept configurations; **FRB 20211115A** is reproducible only with the
authors' exact code plus a permissive threshold. This motivated replacing the 1-D autocorrelation trigger
with the 2-D copy test.

**WP3 round 1 — the per-window calibration was optimistic.** Run end-to-end on hidden data, the adverse
imitators passed far above target because the benchmark had scored a single oracle window while the real
search takes a maximum over ~8 proposals.

**WP3b round 2 — the multiplicity fix works; the gate still failed.** On a genuinely untouched,
source-disjoint pool:

| imitator | round 1 (v1) | **round 2 (v2)** |
|---|---:|---:|
| scintillation | 0.70 | **0.075** |
| overlapping | 0.60 | **0.000** |
| differential scattering | 0.25 | **0.000** |

Efficiency agreement (G1) **passed** — observed 0.200 vs predicted 0.228, full cell coverage, negligible
bias; efficiency at μ ≥ 0.5 was **0.486**. False positives (G2) **failed on one class**: `real_null` at
**2 of 180 = 0.0111** against a target permitting at most one. That outcome is statistically *consistent*
with the validated 0.0024 rate (P(X≥2) ≈ 7%), but the target was pre-registered and is not relitigated
after the fact.

## What the project concluded

The measured real-null false-positive rate of ~1% over 3,874 eligible bursts implies **tens of flagged
bursts by chance alone** in a catalog-wide run. A candidate list produced now would be dominated by false
positives with no principled way to separate them. That is why the gate exists and why it was respected.

The claim this data supports is an **observable-space rate or upper limit** on detectable lensing-like
echoes — not a lens detection and not a candidate list. Of the two previously reported candidates, only
FRB 20190131D is a robust reproduction, and it is the natural target for baseband follow-up.

## Repository layout

```
src/echo_frb/
  ingest/ manifest/ schema/ preprocess/ eligibility/ qc/   WP0 — audit → Tier B products
  repro/                                                   WP1 — literal + clean-room reproduction
  search/
    tier1/        candidate window proposal (triage)
    copy/         the χ²_copy statistic
    robustness/   the 9 mandatory diagnostics
    nulls/ adverse/ injection/                             empirical null + imitator generators
    benchmark/ significance/                               frozen criterion, global FAP
    margin/       WP3b — per-burst max statistic + conditional calibration
    blind/        the blind protocol: controller → evaluator → unblind
config/           frozen analysis configs (v1, v2) + blind harnesses
docs/             plans, findings, gate memos, preregistrations, audit artifacts
tests/            237 tests (7 skipped)
scripts/          operational entry points (wp3b_*, review tooling)
```

## Data and compute

Raw and processed data are held outside the repository — `.gitignore` excludes `*.h5`, `*.parquet` and
`data/`, so nothing bulk is ever committed. The analysis expects a prepared data root containing:

- the raw CHIME/FRB Catalog 2 dynamic spectra (~60 GB)
- `manifests/*.parquet` — observation manifest, eligibility table, normalized catalog metadata
- `tier_b_standardized/<TNS>_tierb.h5` — 4,532 standardized products, the frozen input to every statistic
- per-work-package outputs for the reproduction, the search, and the blind rounds

Every stage takes explicit `--manifests`, `--tier-b-dir` and `--split` arguments, so the data root is a
parameter rather than something baked into the code.

**The test suite needs none of it** — it runs entirely on synthetic spectra:

```bash
PYTHONPATH=src python -m pytest tests/ -q      # 237 passed, 7 skipped
```

The end-to-end stages are compute-intensive — the development null ensemble alone is ~29,000 complete
pipeline runs — and assume a multi-core workstation.

## Why the repository looks like this

This is a preregistered analysis, and much of the structure exists to make cheating difficult:

- **Frozen configs with pinned hashes.** The blind evaluator refuses to run if the analysis config has
  drifted by a byte. Any change cuts a new analysis version and forfeits the prior calibration.
- **Sealed test split.** Test sources were partitioned into source-disjoint pools before anything was
  scored. Round 1 used pool 0, round 2 pool 1. There is no pool 2.
- **Commitment ordering.** Labels are hash-committed before scores, which are hash-committed before
  unblinding. `unblind` verifies the hashes and the timestamp ordering and refuses otherwise. The git
  history preserves that chain — see commits `c64bee4` → `6a5d215` → `929b292` → `1780c3a`.
- **The calibration is part of the freeze.** It decides candidacy, so it is committed as a hashed
  artifact and *reconstructed, never refit*, at scoring time.

## Key documents

| document | what it is |
|---|---|
| [`Project_ECHO-FRB_Updated_Research_Proposal.md`](Project_ECHO-FRB_Updated_Research_Proposal.md) | the research proposal |
| [`obstacles.md`](obstacles.md) | self-contained explainer: data, method, and the core statistical obstacle |
| [`docs/WP1_gate_memo.md`](docs/WP1_gate_memo.md) | reproduction verdicts on the two reported candidates |
| [`docs/WP3_gate_memo.md`](docs/WP3_gate_memo.md) | round-1 failure and its diagnosis |
| [`docs/WP3b_plan.md`](docs/WP3b_plan.md) | the max-statistic design |
| [`docs/WP3b_dry_run_findings.md`](docs/WP3b_dry_run_findings.md) | validation dry run and the go/no-go |
| [`docs/WP3b_preregistration_addendum.md`](docs/WP3b_preregistration_addendum.md) | signed round-2 preregistration |
| [`docs/WP3b_gate_memo.md`](docs/WP3b_gate_memo.md) | **round-2 verdict and what it establishes** |
