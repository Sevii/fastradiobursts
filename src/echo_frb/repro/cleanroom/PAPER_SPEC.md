# Clean-Room Specification — Microlensed-FRB Detection (paper-derived)

**Source:** Zhou et al. 2026, "Evidence for Intermediate-Mass Black Holes From Microlensing
Signatures in CHIME/FRB Catalog 2", arXiv:2605.19653. This file is derived **only** from the
published paper. It is the authoritative algorithmic reference for the clean-room implementation.
You (the implementer) should also read the paper itself (`arxiv.org/abs/2605.19653`, and the HTML
`arxiv.org/html/2605.19653`) as the primary authority and may refine the wording below from it.

> **BLINDNESS RULE (non-negotiable):** implement strictly from the paper. Do **not** read, fetch, or
> `cat` the authors' code (`github.com/Huan-Zhou-spec/MICRO-FRB` or any local copy under
> `.../wp1_repro/microfrb_repo`, `microfrb_run`, or any `microfrb_src`), the file
> `src/echo_frb/repro/target/authors_reported_values.yaml`, anything under
> `src/echo_frb/repro/literal/`, or the project memory about the reproduction target. Where the paper
> is silent on an implementation detail, make your **own** reasoned choice and **document it** — do
> not try to guess or match the authors' specific numbers.

---

## Goal
For each FRB dynamic spectrum, decide whether it contains a **resolved, achromatic, delayed scalar
copy** of the burst (a point-mass microlensing echo) — i.e. a second component that is a
time-shifted, magnitude-scaled copy of the first with the **same** frequency structure. Report the
delay Δt, a magnification ratio estimate, and a candidate/not-candidate verdict.

## Pipeline (as described in the paper)

**1. Light curve.** Form the frequency-integrated intensity light curve `I(t)` from the dynamic
spectrum, using valid (unmasked) channels and appropriate noise weighting.

**2. Normalized autocorrelation (ACF).**
```
C(δt) = (1 / (N_δt · σ_I²)) · Σ_t  Ĩ(t) · Ĩ(t − δt)
```
with `Ĩ(t)` the demeaned light curve and `σ_I²` its variance; `N_δt` = number of overlapping samples
at lag `δt`.

**3. Lensing signature.** A lensed (delayed scalar copy) burst produces **symmetric spikes** in the
ACF at `δt = ±Δt` (besides the zero-lag peak). Their amplitude relative to the zero-lag peak is
`R_f / (R_f² + 1)`, where `R_f` is the flux ratio (magnification ratio) of the two images.

**4. Spike significance.** Define a local scatter about a smooth ACF baseline:
```
σ_δt = sqrt( (1/N_δt) · Σ_δt ( C(δt) − G(δt) )² )
```
where `G(δt)` is a **Gaussian-smoothed** version of `C(δt)` with smoothing kernel `σ = 3`. Flag lags
where `C(δt)` exceeds `G(δt)` by more than **3·σ_δt** as candidate lensing spikes.

**5. Peak matching.** Detect the burst's temporal components (peaks) in `I(t)`. Accept a detected ACF
spike only if the separation of some pair of components matches the spike lag within **±2 ms**.

**6. Selection cuts on a matched pair.**
   - **Temporal ordering:** the leading (earlier) component must be at least as bright (S/N) as the
     trailing one (the magnified image is the weaker, later copy).
   - **Secondary-peak significance:** the trailing (secondary) component must have peak S/N **> 10**.
   - **Global-max inclusion:** the matched pair must include the burst's highest-S/N peak.

**7. Achromaticity / drift (copy) test — K-S.** For the two matched components, extract their
per-component **frequency spectra**, rebinned to **n_f = 512** channels. A true lensed copy has the
**same** spectrum in both images; intrinsic multi-component bursts drift in frequency. Use a
two-sample **Kolmogorov–Smirnov** test between the paired components' spectra:
   - Critical value `D_crit ≈ 0.1` at significance `α = 0.05`.
   - Establish an upper bound `D_{n,upp}` on the K-S statistic under the null (identical spectra plus
     noise) via **bootstrap resampling with O(10³) iterations**.
   - **Reject** the pair as *drifting* (i.e. NOT a copy) if `D_max > D_crit` **AND** `D_max > D_{n,upp}`.
     A pair that is not rejected is consistent with an achromatic copy.

**8. Hardness-ratio consistency (selection cut only).** As an additional check, split the band into
**three regions [L, M, H]** and compare the two components' hardness ratios; require consistency
within **1σ**. (Use only as a pass/fail cut. Do **not** compute lens masses or f_PBH — out of scope.)

**9. Verdict.** An FRB is a **lensing candidate** iff it has at least one matched, correctly-ordered,
S/N-passing, hardness-consistent component pair whose ACF spike is significant and whose K-S test does
**not** indicate drift. Report: the spike delay(s), the matched component pair(s), the best Δt (ms),
a magnification-ratio (`R_f`) estimate, and the candidate/drift booleans.

## Parameters the paper fixes
`smoothing kernel σ = 3` (for `G`), spike threshold `3σ`, peak-match tolerance `±2 ms`, secondary
PSNR `> 10`, K-S `n_f = 512`, `D_crit ≈ 0.1 @ α=0.05`, bootstrap `~10³`, hardness bands `= 3`,
hardness consistency `1σ`.

## Parameters the paper leaves to you (choose + document)
Peak-detection method/settings, exact light-curve noise weighting, ACF lag range and edge handling,
which off-pulse samples define the noise for the K-S bootstrap, magnification-ratio estimator, and the
episode/window definition for the two components. Put every such choice in a `## Implementation choices`
section of your code's README/config so divergences are auditable.
