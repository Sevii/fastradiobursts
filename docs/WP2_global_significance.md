# WP2 Global Significance — machinery + null calibration (W2.8)

**Goal (proposal §6.1):** convert a local copy score to a catalog-global family-wise false-alarm
probability via the maximum statistic of catalog-equivalent null searches, with source-level resampling.
WP2 builds and null-calibrates the machinery; the real catalog-global evaluation is WP4.

## What was built
`src/echo_frb/search/significance/global_fap.py` (+ `run.py`, `tests/test_significance.py` 4/4):
- **Source-level cluster bootstrap** of the catalog-max statistic (repeaters share a source, so
  realizations resample SOURCES with replacement, preserving source-level dependence).
- **Empirical global FAP** = P(catalog-max ≥ observed), with add-one conservatism; resolution = 1/B.
- **Generalized-Pareto tail model** fit on one null half and validated out-of-sample (predicted vs
  empirical tail FAP within an order of magnitude on synthetic extreme-value data — unit-tested).

## Null-calibration finding (the important result)
Null-calibrating on the real-null catalog (6749 proposals, 640 copy-quality, 1236 sources, B=20000)
showed that **no single continuous statistic is a valid global ranking on its own**:
- **Δχ² (∝ SNR²) is brightness-dominated** — the catalog-max collapses to the single brightest null
  burst (Δχ²≈1.7e5) as a point mass; the GPD tail is degenerate. Unusable.
- **NCC saturates at 1.0** — some real complex bursts are *perfectly* on-burst-correlated, so the
  catalog-max NCC pins at 1.0 and every sub-unity candidate has FAP≈1. Unusable alone.

**Therefore the global significance must be computed on the FULL candidate criterion** (copy-quality +
mandatory achromaticity + robustness), not on Δχ² or NCC alone — consistent with the proposal's insistence
that the evidence is a 2-D copy test plus robustness, never a single number. Under the full criterion the
real null produces ~0 candidates (W2.7: 0/500 sampled), so a surviving candidate is globally rare; the
max-statistic FWER over the full criterion is therefore resolution-limited small and requires the larger
WP4 null run to pin its tail (rule-of-three on 0/500 gives a per-copy-quality-proposal upper bound
≈0.6%, i.e. an O(few) catalog-wide upper bound at 95% CL with the current sample — to be tightened in WP4).

## Status / handoff
- The FWER machinery (source-level max-statistic bootstrap + GPD tail + out-of-sample validation +
  empirical resolution) is implemented and unit-tested, ready for the WP4 catalog-global run.
- **Frozen in W2.9:** the final ranking statistic must be a brightness-fair *local significance* (e.g. a
  local p-value of the full-criterion score within S/N-matched nulls), not raw Δχ²/NCC — this choice and
  its null are part of the preregistration.
- Artifacts: `~/frb_catalog2_prep/wp2/significance/{null_catalog_max.parquet,global_significance_report.md}`.
