# WP1 Reproduction — Progress Tracker

Living status of the WP1 tasks (plan: `docs/WP1_plan.md`). Reproduction target:
Zhou et al. 2026 (arXiv:2605.19653) + `github.com/Huan-Zhou-spec/MICRO-FRB`.
Work runs on `popos` under `~/frb_catalog2_prep/wp1_repro/`; code in this repo
under `src/echo_frb/repro/`, synced to popos and run via its `.venv`.

## Scope (confirmed)
- **Detection + Δt/μ only** — reproduce screening + the two candidates' delays/flux
  ratios; NO lens-mass / f_PBH (those are WP5). Hardness runs only as a selection cut.
- **Blind clean-room** — W1.3 implementer sees only the paper + Tier B schema, never the repo.

## Task status

| Task | Status | Artifact |
|---|---|---|
| W1.0 Seal target + extract claims | 🟢 done | Repo cloned @ pinned `c4fbfca` (2026-05-18), **sealed read-only**, checksummed → `repro_target_manifest.parquet` (272 files, 0.15 GB, 0 err). Ground truth → `src/echo_frb/repro/target/authors_reported_values.yaml`. Env reconstructed + locked → `env/microfrb_repro.lock` (**found 2 UNDECLARED deps: `colossus`, `statsmodels`**). |
| W1.1 Input equivalence + 340-set | 🟢 done | Bundled repo `.h5` **byte-identical** to our Tier A (same sha256) → CANFAR release == Tier A, no re-download. 340-set = full `chimefrbcat2_first_duplicates.npy` (340 rows, sub_num≥1); **all 340 in Tier A**, both candidates present → `microfrb_input_manifest.parquet`. |
| W1.2 Literal run (G_3) | 🟢 done (G_3) | Ran `SearchLensedFRB.py` **unmodified** N=340 on Tier A via pinned env. **EXACT reproduction of committed G_3**: 11==11 candidates, 0 field mismatches, identical spike delays → `literal_vs_committed_diff.md`. SG_20/SG_100 variants deferred to W1.5 (smoothing axis). |
| W1.3 Blind clean-room | ⚪ not started | Fresh blind implementer from paper only. |
| W1.4 Selection chain | ⚪ not started | Per-stage disposition, both tracks. |
| W1.5 Sensitivity matrix | ⚪ not started | One axis at a time. |
| W1.6 Repro matrix + note | ⚪ not started | exact/approx/not + traced causes. |
| W1.7 Tests + env locks + gate | ⚪ not started | determinism + golden + invariant; gate memo. |

## Key W1.0 findings (ground truth)
- Repo pinned commit **c4fbfcabae551d933dbb24cd56bb11fa73b73419** ("2026.05.18").
- Bundled: 7 CHIME cat2 `.npy` classification tables + **only 1** of ~340 `.h5`
  (`FRB20181028A`, and it is NOT in any candidate list). The other ~339 must come
  from CANFAR or our Tier A (W1.1).
- **Candidate list is smoothing-config-dependent** (committed `lens_catalog_summary.csv`):
  - **G_3** (Gaussian σ=3): **11** candidates → this is the paper's headline funnel
    (`lens_analysis_summary.txt`: "总处理 FRB 数量: 340 … 透镜候选: 11").
  - **SG_20** (Savitzky-Golay w=20): **16** candidates.
  - **SG_100** (Savitzky-Golay w=100): **12** candidates — and **FRB20211115A, a final
    candidate, is ABSENT** from this list.
  - Common to all three: FRB20190131D, FRB20190915E, FRB20210130C, FRB20220225C, FRB20220424C.
- Named candidates (from G_3 reports): FRB20190131D Δt=**8.82 ms** peaks (76,85);
  FRB20211115A Δt=**6.86 ms** peaks (78,85). Both `has_drift=False`.
- Reports/summaries are in Chinese but numerically unambiguous.
- Hazards logged in `authors_reported_values.yaml:reproduction_hazards` (no deps pin,
  no license, config-dependent selection, subjective 11→9, hard-coded headline results).

## W1.1 / W1.2 findings
- **Input provenance closed:** repo's bundled `FRB20181028A.h5` sha256 == our Tier A copy →
  the CANFAR `CISTI.CANFAR/25.0066` release is the same bytes as Tier A. Literal run reuses Tier A
  via symlinks into `microfrb_run/FRB_data/canfar_downloads/` (working copy; sealed repo untouched).
- **Undeclared deps** (no requirements.txt): `colossus` (cosmology) + `statsmodels` — both required
  because `modules/__init__.py` eagerly imports `fpbh_data`/`hardness_data`. Reproducibility finding.
- **Literal G_3 = EXACT.** Deterministic value-for-value match to committed output (byte-identical
  inputs + seed=42 + numpy-2.6 repr). The paper's "340 → 11" funnel and both candidates' delays
  reproduce exactly from public data + their code.
- Their `read_frb_dynamic_spectrum` auto-detects the 2D `data` dataset (CHIME layout) — no code
  change needed to read Tier A. Script runs at import (no `__main__` guard); `MPLBACKEND=Agg` headless.

## Environment (literal track)
- Dedicated venv `~/frb_catalog2_prep/wp1_repro/venv_microfrb` (isolated from WP0 env).
- Pinned: numpy 2.2.6, scipy 1.15.3, pandas 2.3.3, matplotlib 3.10.9, h5py 3.16.0,
  statsmodels 0.14.6, colossus 1.4.0. Lock: `env/microfrb_repro.lock`.

## Notes / decisions
- `authors_reported_values.yaml` is version-controlled (published numbers only).
- Provenance/sealing reuses `echo_frb.ingest.checksums` (same as WP0 Tier A).
- Next concrete step: W1.3 blind clean-room (spawn implementer blind to the repo), then
  W1.4 selection-chain reconstruction; SG variants + version drift → W1.5 sensitivity.
