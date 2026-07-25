# Project ECHO-FRB — Statistical Approach, Data, and the Core Obstacle

*A self-contained explainer: what we are trying to detect, what our data looks like, the statistical
method we have built, and the problem that is currently blocking us. Written for a statistically-literate
reader who has not followed the work-package history.*

---

## 1. What we are trying to detect

A gravitational lens between us and a fast radio burst (FRB) source can produce **two images of the same
burst arriving at slightly different times**. In the ideal geometric-optics limit the second image is a
**delayed, scalar-magnified, otherwise-identical copy** of the first, across the whole observing band:

```
D(t, ν)  =  S(t, ν)  +  μ · S(t − Δt, ν)  +  N(t, ν)
```

where `S` is the intrinsic burst, `Δt` the lensing delay (one value for all frequencies — **achromatic**),
`μ ∈ (0, 1]` the relative magnification of the fainter second image, and `N` measurement noise. Detecting
this is a **needle-in-haystack** problem with a sharp prediction: the second component is not merely
"another peak," it is an *achromatic copy* of the first. That specificity is our main lever — and the
entire difficulty is that **naturally complex bursts and plasma propagation routinely imitate it.**

The competing explanations we must reject for any candidate:

| Hypothesis | Signature | Role |
|---|---|---|
| **H-L** strict lens | one achromatic delay, one scalar magnification, shared morphology | the target |
| **H-I** intrinsic complexity | two components with independent widths/spectra/drifts | main astrophysical false positive |
| **H-P** plasma propagation | chromatic delays, scintillation (frequency-dependent amplitude), fringes | adverse; not decisively rejectable on this data |
| **H-N** instrument/analysis | RFI remnants, mask edges, dedispersion/baseline artifacts | quality-control false positive |

The scientific claim we can support from this data is an **observable-space rate or upper limit** on
detectable lensing-like echoes — *not*, by itself, a lens or dark-matter detection.

---

## 2. What the data is like

**Source.** Public CHIME/FRB Catalog 2: **4,539 bursts from 3,641 sources**, total-intensity dynamic
spectra spanning **400–800 MHz** in **16,384 frequency channels**, at **0.983 ms** time resolution. Each
burst is a 2-D time–frequency array (`≈ 16384 × ~160` time samples; ~8 MB compressed after our
standardization).

**Standardized product (our "Tier B").** Per burst we store: the baseline-subtracted spectrum, a
per-channel robust noise estimate `σ(ν)`, a project mask (RFI + unusable channels), and an off-pulse time
window for noise estimation. This is the frozen input to all statistics.

Four features of the data dominate the statistical design:

1. **High but finite time resolution.** 0.983 ms means only **resolved** echoes are accessible — delays
   below ~2 ms blur into a single component. Our search domain is **Δt ∈ [2, 50] ms**. Short-delay and
   overlapping-image regimes are effectively out of reach.
2. **Rich intrinsic structure.** FRBs are genuinely complex — sub-bursts, drift, scattering tails. A large
   fraction of bursts have *some* second-peak-like feature that is **not** a copy. This is the enemy.
3. **Source-level dependence.** Many bursts come from **repeaters** (same source). Morphology learned from
   one burst of a source leaks into another, so *every* split, null, and resample must be done at the
   **source** level, never the burst level.
4. **Scarcity of the hard nulls.** The "hard" false-positive population — genuinely multi-component bursts
   (H-I) — is **rare**. In our sealed test split there are only **96 multi-component bursts out of 1,133**.
   This starves the false-positive tail of samples and limits how tightly we can bound rare-FP rates.

**Eligibility / holdouts.** 3,874 bursts pass eligibility (readable, valid axes, usable off-pulse). Two
previously-reported candidates (FRB 20190131D, FRB 20211115A) plus published intermediates are
**quarantined** — excluded from all method design. Sources are split **60/20/20 (dev/validation/test)** at
the source level; the test split is **sealed** for blind validation.

---

## 3. The statistical approach we have tried

### 3.1 Baseline (and why we left it): a 1-D autocorrelation trigger
The prior published method screens the **frequency-integrated** light curve with an autocorrelation
function and flags spikes above a smoothed baseline. We reproduced it exactly. Its verdict is
**under-determined**: the candidate list swings with smoothing/threshold choices (one of the two reported
candidates survives only under specific settings). Collapsing to 1-D throws away the achromaticity
information that most distinguishes a lens from intrinsic structure. This motivated a 2-D test.

### 3.2 Primary statistic: a masked, noise-weighted 2-D copy test
For a proposed pair of component windows `A` and `B`, fit `B` as a delayed, scaled copy of `A` over the
common set of valid (unmasked, usable) pixels `V`, minimizing a noise-weighted residual:

```
χ²_copy(Δt, a)  =  Σ_V  [ B(t,ν) − a · A(t − Δt, ν) ]²  /  [ σ_B²(t,ν) + a² σ_A²(t,ν) ]
```

The engineering that makes this work on real data:
- **Mask-aware inverse-variance rebin** 16,384 → 256 channels (the native resolution is noise-dominated).
- **On-burst support:** compare only where the reference component `A` actually has power.
- **Closed-form magnification** `a = Σ(AB/σ_B²) / Σ(A²/σ_B²)` — no `a`↔variance degeneracy.
- **Δχ²** = the matched-filter detection statistic (∝ SNR²); **reduced-χ²** whitened by the *full* noise
  `σ_B² + a²σ_A²` (≈ 1 for a true copy at any magnification); **NCC** = on-burst normalized correlation.

Δχ² measures *detectability*; NCC and reduced-χ² measure *copy-quality*; neither alone separates lenses
from complex bursts (bright complex bursts have high Δχ²; some real bursts are perfectly self-correlated,
saturating NCC). So the statistic is deliberately **multi-dimensional**.

### 3.3 The candidate criterion (frozen before validation)
A component pair is a **candidate** only if it is simultaneously:

```
detectable   Δχ² > 100
copy-like    NCC > 0.40   AND   reduced-χ² < 1.5
achromatic   per-band delay + magnification + spectral-flatness + DM/scattering ALL consistent  (mandatory)
robust       ≥ 7 of 9 diagnostics pass (leave-band-out, window/resolution stability, residual structure, …)
```

Achromaticity is a **hard gate**, not a vote — a single frequency-dependent delay or magnification
disqualifies. This is what rejects chromatic propagation and drift.

### 3.4 Empirically-calibrated nulls (not Gaussian noise)
The false-positive distribution is built from the phenomena that actually imitate lensing:
- **real** complex bursts (the dominant, realistic null),
- **matched cross-event pseudo-pairs** (components from *different* bursts — accidental agreement),
- **structure-preserving surrogates** (block bootstrap / phase randomization / time–frequency permutation
  — keep the envelope, destroy any true copy relation),
- **adverse simulations** — eight physically-motivated imitators injected into real bursts: drift,
  differential DM, differential scattering, chromatic echo, **scintillation**, overlapping, RFI remnant,
  plus an achromatic-copy positive control.

### 3.5 Where this stood after development
On the **development** split, the full criterion looked strong: real-complex-burst false positives driven
from ~8% (copy-quality alone) to **~0%**, detection efficiency **~79%**, deterministic artifacts rejected.
The one acknowledged residual: **scintillation** (a propagation effect) suppressed only 80% → 36% — plasma
is too flexible to rule out decisively on this data.

We then **froze** everything (statistic, thresholds, nulls, robustness tolerances) and moved to a **blind
injection test** on the sealed test split: hide a mixture of injected copies + real nulls + adverse cases,
run the frozen pipeline, and check that recovery and false-positive rate match what was predicted.

---

## 4. The core problem

### 4.1 The blind test broke on false-positive control — and located exactly why
Detection efficiency generalized fine out-of-sample (observed ≈ predicted). **False-positive control did
not.** Run *end-to-end* on the hidden test set, the adverse imitators passed the frozen criterion far above
target:

| adverse imitator | dev benchmark (single window) | **blind test (end-to-end)** |
|---|---:|---:|
| scintillation | 0.36 | **0.70** |
| overlapping | — | **0.60** |
| differential scattering | 0.08 | **0.25** |

Real complex nulls (0.3%) and deterministic artifacts (0%) stayed rejected — the failure is specifically
the **propagation-like and short-delay imitators**.

### 4.2 The mechanism: within-burst multiple comparisons (look-elsewhere)
The development benchmark scored **one oracle window** per burst — the location where we knew we had
injected. The real search cannot do that: a lightweight first stage proposes **candidate component windows**
(on average **~8 per burst**, across a delay grid), and the burst is flagged if **any one** of them passes
the criterion. A controlled rerun isolates the effect — the *same* adverse injections, scored single-window
vs. end-to-end, on the same bursts:

| imitator | single oracle window | **any of ~8 proposals** |
|---|---:|---:|
| scintillation | 0.28 | **0.55** |
| overlapping | 0.00 | **0.70** |
| differential scattering | 0.08 | **0.13** |
| drift / diff-DM / chromatic / RFI | 0.00 | 0.03–0.08 |

**The per-window false-positive rate was never the operative quantity.** Every burst gets ~8 independent
chances to produce a copy-like window, and a complex or scintillating burst usually has *some* window that
survives the criterion. Our benchmark measured the per-window rate; the search pays the **per-burst
maximum** over ~8 windows. That gap is the obstacle.

### 4.3 Why this is genuinely hard, not just a tuning bug
1. **Multiplicity is intrinsic to the search.** We deliberately do not require a pre-existing multi-peak
   label (that is the scientific novelty — catalog-wide sensitivity). So we *must* propose windows blindly,
   and multiplicity is unavoidable. Tightening thresholds to kill the adverse tail also kills genuine faint
   echoes (the efficiency we need).
2. **The nulls are the signal's twin.** A scintillating burst genuinely contains a frequency-modulated
   near-copy; a complex burst genuinely contains repeated-looking sub-structure. We are not separating
   signal from noise — we are separating a copy from *near-copies produced by different physics*, and the
   achromaticity test that is supposed to do this is only partially effective against scintillation.
3. **Propagation is not a finite model.** No finite set of plasma simulations exhausts H-P, so we can bound
   the scintillation false positive but not eliminate it — and it **worsened out-of-sample** (36% → 70%).
4. **The hard nulls are scarce.** With only ~96 genuinely multi-component test bursts, the rare-FP tail is
   under-sampled: bounding a 1% false-positive rate to a tight confidence interval needs more hard nulls
   than the catalog cheaply provides.
5. **Two nested look-elsewhere problems.** *Within* a burst (~8 windows) — the one that just broke us — and
   *across* the catalog (~4,500 bursts × delay grid). We had machinery for the catalog-wide family-wise
   error; we under-modeled the within-burst multiplicity in the development benchmark.

### 4.4 Where the definitions themselves bite
One "failure," **overlapping** (60%), is partly a definitional artifact: we injected it at Δt ≈ 3 ms, which
sits *inside* our declared search domain (Δt ≥ 2 ms), so the pipeline is arguably *correctly* detecting a
real short-delay copy rather than a false positive. It highlights that the boundary between "resolved echo"
and "adverse overlap" is set by the 0.983 ms resolution and our 2 ms floor — a data-imposed, somewhat
arbitrary line.

---

## 5. Statement of the problem, precisely

> We are testing, for every component pair the search proposes, whether one component is an **achromatic,
> scalar-magnified, delayed copy** of the other at a level not produced by intrinsic FRB morphology,
> plasma propagation, or instrumental artifacts. Our 2-D copy statistic plus mandatory-achromaticity and
> robustness criterion controls the **per-window** false-positive rate on real and deterministic-artifact
> nulls to ~0%. But the search evaluates **~8 proposed windows per burst and flags the burst if any one
> passes**, so the operative quantity is the **per-burst maximum** over those windows — and under that
> multiplicity the propagation-like imitators (scintillation, differential scattering) and short-delay
> copies pass at 25–70%, far above the rate a single-window benchmark showed. The open problem is to
> control the **within-burst multiple-comparison false-positive rate for delayed-copy structure against a
> null population of naturally complex and scintillating bursts**, without sacrificing the detection
> efficiency for genuine faint echoes, on data whose hard-null population is small and whose time
> resolution fixes the resolvable-delay floor.**

### Candidate directions (unresolved)
- **Reduce the multiplicity:** carry only the single best-triage window per burst into the full criterion,
  trading a little efficiency for a large false-positive reduction — the simplest lever.
- **Pay for the multiplicity explicitly:** a per-burst trials penalty / max-statistic calibration, so the
  reported significance already accounts for the ~8 within-burst looks.
- **Strengthen the achromaticity test against scintillation** specifically (it is the dominant residual),
  e.g. a stronger spectral-magnification-flatness or frequency-coherence constraint — while honestly
  conceding plasma cannot be fully excluded on catalog data.
- **Accept a higher resolved-delay floor** so "overlapping" cases fall cleanly outside the domain.

Any of these changes the frozen analysis, so it requires re-freezing and a **fresh** blind validation on a
still-untouched slice of the data — the discipline that surfaced the problem in the first place.
