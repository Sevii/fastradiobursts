# WP1 · W1.3 — Blind Clean-Room Reimplementation — Plan

## Context

The literal leg (W1.2) is a clean **exact** reproduction of the authors' G_3 result on our Tier A
data. W1.3 is the second, independent leg: reimplement the paper's *detection + selection* method
**from the paper alone**, blind to the MICRO-FRB code, and run it on **our Tier B** products. The
scientific value is the comparison — a literal-vs-clean-room **agreement** corroborates the signal;
a **divergence** localizes it to a preprocessing/algorithmic choice. Either outcome is a WP1 result.

**Locked decisions (this session):**
- **Primary input = our Tier B** (max independence — uses *none* of the authors' preprocessing), plus
  a **Tier A diagnostic variant** (clean-room's own preprocessing on raw) so W1.4/W1.6 can decompose
  "preprocessing vs algorithm" when divergences appear.
- **Blindness via a fresh subagent** with a clean context, paper-only inputs, and hard-barred paths.
- **Scope = detection + Δt/μ** (per WP1): implement through the drift/K-S copy test; hardness only as
  a selection cut; **no lens masses / f_PBH**.

---

## Blindness governance (the core mechanism)

A fresh **clean-room implementer subagent** is spawned with a clean context and given ONLY:
1. **The paper** as authoritative source — instructed to read `arxiv.org/abs/2605.19653` (abs/html) itself,
   supplemented by `PAPER_SPEC.md` (below). The arXiv text contains no repo code.
2. `docs/standardized_data_schema.md` (Tier B schema) + how to reach Tier B on popos.
3. A **names-and-signatures** list of reusable WP0 utilities (no target-specific semantics).
4. The **neutral output schema** (below) it must emit.
5. The 340-set `tns_name` list (a public-catalog fact — the multi-peak subset — not their algorithm).

**Hard-barred** (explicitly instructed not to open, fetch, or `ssh cat`): the MICRO-FRB repo/GitHub
(`.../wp1_repro/microfrb_repo`, `microfrb_run`, scratchpad `microfrb_src`, `github.com/Huan-Zhou-spec/*`),
`src/echo_frb/repro/target/authors_reported_values.yaml`, `src/echo_frb/repro/literal/**`, and memory
`wp1-reproduction-target.md`.

**Orchestrator (me):** I run the clean-room and compare vs literal in W1.4/W1.6 — I never feed literal
outputs or their code back in. Any debugging guidance to the subagent is phrased in
paper/first-principles terms, **never "match their number."** Honest limitation recorded: this is
*context-level* blindness (one implementer that never saw their code), not a separate research team.

---

## Paper-derived specification → `src/echo_frb/repro/cleanroom/PAPER_SPEC.md`

Strictly from arXiv:2605.19653 (no repo). The blind agent may refine wording from the paper directly.
1. **Light curve** `I(t)`: masked, noise-weighted frequency-integration of the dynamic spectrum.
2. **Normalized ACF**: `C(δt) = Σ_t Ĩ(t)Ĩ(t−δt) / (N_δt · σ_I²)`, `Ĩ` demeaned.
3. **Lensing signature**: symmetric spikes at `δt = ±Δt` with amplitude ratio `R_f/(R_f²+1)` vs the
   zero-lag peak.
4. **Spike significance**: `σ_δt = √[(1/N_δt) Σ (C(δt) − G(δt))²]`, `G` = Gaussian-smoothed `C`
   (kernel σ=3); flag lags where `C` exceeds `G` by **>3σ_δt**.
5. **Peak matching**: detect burst components in `I(t)`; accept a spike if some component-pair
   separation matches `δt` within **±2 ms**.
6. **Cuts**: temporal ordering (leading component S/N ≥ trailing); **secondary PSNR > 10**; matched
   pairs must include the **global-max-PSNR** peak.
7. **Copy / drift K-S test**: per-component spectra at **n_f=512**; two-sample K-S between paired
   components; reject as drifting if `D_max > D_crit (≈0.1 @ α=0.05)` **AND** `D_max > D_{n,upp}`,
   the upper bootstrap bound from **O(10³)** noise resamples.
8. **Hardness (cut only)**: 3 bands `[L,M,H]`, hardness ratios consistent within **1σ**.
9. **Per-FRB verdict**: candidate iff a matched, ordered, cut-passing, non-drifting pair exists;
   report its `Δt` and magnification-ratio estimate.

**Under-specified in the paper** (peak-finder settings, exact light-curve weighting, noise-sample
selection, ACF edge handling) → the implementer makes **independent, documented** choices. Divergences
traceable to these are *findings*, not bugs.

---

## Deliverables

**`src/echo_frb/repro/cleanroom/`** (built by the blind subagent):
- `PAPER_SPEC.md` — the blind spec above.
- `lightcurve.py`, `acf.py` (ACF + spike detection), `peaks.py`, `drift_ks.py`, `hardness.py`,
  `pipeline.py` (per-FRB orchestration), `run.py` (CLI over the 340-set), `cleanroom_config.yaml`
  (all thresholds; hashed via the `_config_hash` convention).
- Emits `cleanroom_scores.parquet` (neutral schema) + per-FRB audit records, provenance-stamped.

**On popos:** `~/frb_catalog2_prep/wp1_repro/cleanroom_run/` (Tier B primary) and
`cleanroom_run_tierA/` (diagnostic variant).

**Tests:** `tests/test_cleanroom.py` — synthetic injected-copy recovery + determinism.

### Neutral output schema (both tracks map onto this in W1.4)
`frb_name, spike_delays_ms[], matched_pairs[], best_delay_ms, mag_ratio, is_candidate, has_drift,
n_components, config_hash, content_sha256, code_commit`.

---

## Reused WP0 infra (names/signatures given to the subagent)
| Need | Reuse | Path |
|---|---|---|
| Load Tier B (extend to also read `coords/freqs`, `coords/times`) | `load_tier_b` | `src/echo_frb/reference/make_plots.py` |
| 16384→512 freq rebin for K-S spectra | `rebin_freq(arr, valid, 512)` | `src/echo_frb/reference/make_plots.py` |
| Provenance + determinism hash | `content_sha256`, `sha256_of` | `src/echo_frb/preprocess/standardize.py` |
| Config-hash convention | `sha256(yaml_bytes)[:16]` | `preprocess/standardize.py` |
| Candidate quarantine (eval-but-quarantine) | `CANDIDATES` | `config/preprocessing_config.yaml` |
| 340-set tns list | `microfrb_input_manifest.parquet` (public-catalog-derived) | popos workspace |

**Environment:** clean-room uses **our WP0 `.venv`** (our stack, deliberately — code is the
independence axis, not libraries). Quarantine: WP1 is the sanctioned place to score the two named
candidates; write their clean-room scores to a quarantined path so nothing leaks to WP2.

---

## Verification (end-to-end)
1. **Unit** (`tests/test_cleanroom.py`): inject a delayed, scaled copy of a real single-component burst
   into real off-pulse noise → clean-room recovers `Δt` (±1 bin) and `R_f`; a no-copy control yields no
   candidate; determinism → identical `content_sha256` on re-run.
2. **Run** over the 340-set on Tier B → `cleanroom_scores.parquet`; then the Tier A diagnostic variant.
3. **Orchestrator-only sanity** (NOT fed back to the subagent, recorded as a W1.3 outcome): whether the
   clean-room independently flags FRB 20190131D / FRB 20211115A near 8.82 / 6.86 ms.
4. The **full literal-vs-clean-room reconciliation + reproducibility matrix is W1.4/W1.6**, not W1.3.

## Risks / open items
- Light-curve weighting + noise-sample selection are under-specified → independent choices, documented.
- Blindness is context-level, not organizational — stated honestly in the note.
- Clean-room may yield **more or fewer** candidates than the literal run; that delta is the scientific
  result, not a defect.
