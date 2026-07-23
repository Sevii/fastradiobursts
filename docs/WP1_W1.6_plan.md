# WP1 · W1.6 — Reproducibility Matrix & Technical Note — Plan

## Context

W1.2–W1.5 are complete: literal reproduction is **exact** across all three committed smoothing configs;
the blind clean-room independently recovers only FRB 20190131D; W1.4 attributed the divergence to the
spike-detection stage; W1.5 showed only FRB 20190131D is robust across 20 configs. W1.6 **synthesizes**
these into the formal WP1 deliverables (proposal §8, §12.2, Appendix B): a **reproducibility matrix**
(each reported statistic × {literal, clean-room} → exact / approximate / not / n-a, with a traced
cause), a **technical reproduction note**, and **per-candidate audit records** for FRB 20190131D,
FRB 20211115A, and the published selection chain. It feeds the WP1 gate (formalized in W1.7). Low
compute — assembly + writing from existing artifacts. **Format: markdown + parquet** (no visual).

## Inputs (all existing — no new runs)
`authors_reported_values.yaml` (ground truth) · W1.2 literal exact-repro (+ W1.5 SG exact-repro) ·
`cleanroom_scores.parquet` · `candidate_selection_chain.parquet` · `decomposition_attribution.parquet` ·
`sensitivity_matrix.parquet` · `candidate_stability.parquet`.

## Deliverables
1. **`reproducibility_matrix.parquet` + `.md`** — built by `src/echo_frb/repro/matrix/build.py`.
2. **`docs/WP1_reproduction_note.md`** — the WP1 technical note (narrative synthesis).
3. **`docs/candidate_reproduction_report.md`** — per-candidate Appendix-B audit records.
4. **`tests/test_matrix.py`** — schema/enum + a couple of golden rows.

## Reproducibility-matrix schema
One row per reported statistic. Columns: `statistic, reported_value, literal_status, literal_value,
cleanroom_status, cleanroom_value, robust (W1.5), cause, notes`.
Status vocabulary: **EXACT / APPROX / NOT / N-A (out of WP1 scope) / SUBJECTIVE (non-algorithmic)**.

Rows to score:
- **Selection counts:** processed=340 · G_3=11 · SG_20=16 · SG_100=12 · 11→9 (morphology) · →2 final.
- **Per-config candidate membership** (G_3 / SG_20 / SG_100 lists).
- **Named-candidate detection:** FRB 20190131D {detected, Δt=8.82, has_drift=False, μ}; FRB 20211115A
  {detected, Δt=6.86, has_drift=False, μ}.
- **Spike delays** of the 11 G_3 candidates.
- **Out of scope → N-A:** lens masses, source z, f_PBH (detection+Δt/μ scope).

Scoring (from the artifacts):
- **Literal:** EXACT for all counts / lists / delays (byte/value-verified in W1.2 + W1.5).
- **Clean-room:** FRB 20190131D detection **EXACT** (Δt 8.847≈8.82, within 1 bin; achromatic K-S);
  FRB 20211115A **NOT** (no ACF spike); selection counts **NOT** (1 vs 11); μ **APPROX** (convention).
- **cause** (non-EXACT rows): from W1.4 factorial (ALGORITHM-dominated spike threshold; FRB 20211115A
  MIXED + preprocessing) and W1.5 (count 22→3 across kσ; only FRB 20190131D robust).
- **11→9 morphology reassessment:** SUBJECTIVE (not algorithmically specified).
- **μ / R_f:** reconcile conventions — authors report R_f<1 (weaker image); clean-room `mag_ratio`≈2.51
  ≈ 1/0.40 → magnitude-consistent, convention/episode difference noted (APPROX, not NOT).

## Per-candidate audit records (Appendix B schema)
For FRB 20190131D and FRB 20211115A, assemble: **Identity** · **Data integrity** (Tier A sha256 =
CANFAR; Tier B hash) · **Preprocessing** (config hashes, both tracks) · **Search** (Δt, μ, spikes,
matched pairs, per track) · **Significance** (LOCAL detection only — **catalog-global FAP is WP4, not
computed here**; mark explicitly) · **Robustness** (W1.5 survival fraction + W1.4 factorial cause) ·
**Model comparison** (N-A in WP1) · **External checks** (baseband availability — deferred to WP5) ·
**Decision**. Decision uses a **reproduction-verdict** vocabulary — **REPRODUCED-ROBUST**
(FRB 20190131D) vs **NOT-INDEPENDENTLY-REPRODUCED / FRAGILE** (FRB 20211115A) — explicitly *not* the
proposal §7 discovery grades (which require the WP4 global FAP).

## Technical note outline (`WP1_reproduction_note.md`)
1. Scope + method (literal · blind clean-room · selection reconstruction · sensitivity).
2. **Literal = EXACT** across all three committed configs (11/16/12) — table.
3. **Independent (clean-room) = 1/11**; FRB 20190131D robust, FRB 20211115A not.
4. Where/why they diverge — W1.4 funnel + factorial (spike stage, algorithm-dominated) + W1.5
   (count 22→3; smoothing method a source toggle; only FRB 20190131D robust across 20 configs).
5. **Reproducibility hazards found** — undeclared deps (colossus, statsmodels); no license; hard-coded
   params/paths; smoothing comment-toggle; config-dependent candidate lists; hard-coded fpbh/hardness
   headline numbers.
6. Bottom line on the two named candidates + the method.
7. **Gate readiness (preliminary; formal memo = W1.7):** reported candidates + intermediate statistics
   **are reproduced** (literal exact; every independent-analysis discrepancy fully explained and
   attributed) → supports passing the WP1 gate, with the explicit caveat that **FRB 20211115A is
   fragile** and depends on under-documented choices.

## Reused infra
`pandas`/`pyarrow` (parquet), `yaml` (ground truth); the W1.3–W1.5 output parquets; package already
scaffolded at `src/echo_frb/repro/matrix/`. Config-hash + provenance conventions as elsewhere.

## Verification
1. `reproducibility_matrix.parquet` has one row per reported statistic; every row carries a status in
   the vocabulary and, for non-EXACT rows, a non-empty `cause`.
2. Cross-check against artifacts: all literal statuses EXACT (consistent with W1.2/W1.5); clean-room
   FRB 20190131D EXACT and FRB 20211115A NOT (consistent with `cleanroom_scores`).
3. `tests/test_matrix.py`: enum/schema validation + 2 golden rows (a literal-EXACT and the
   FRB 20211115A NOT row with its cause).
4. Both notes render every Appendix-B field for both candidates; the reproduction-verdict vocabulary is
   used (no discovery-grade language).

## Risks / open items
- **μ/R_f convention** — score as APPROX with the convention explained, not NOT.
- Keep **reproduction verdict ≠ discovery grade** (§7) — no implied discovery claim either way.
- **Significance** rows are LOCAL only; catalog-global FAP is WP4 → N-A, never fabricated.
- Balance the framing: literal EXACT is a strong positive; independent reproduction is partial; state
  both plainly without over- or under-claiming.
