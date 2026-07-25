"""WP3b — per-burst max-statistic calibration (docs/WP3b_plan.md, Approach 1).

The WP3 round-1 gate failed because the frozen criterion was calibrated per
WINDOW while the search reports a per-BURST maximum over ~8 Tier-1 proposals.
This package does not remove that multiplicity — it PRICES it:

    T_ij = the weakest standardized gate margin of proposal j in burst i
    M_i  = max_j T_ij                     (the quantity the pipeline reports)
    p_i  = empirical tail of M under complete null runs, conditioned on Z_i
    p_i^robust = max_h p_ih               (the most adverse null family)

`statistic` builds T_ij so that `T_ij > 0` is EXACTLY the frozen wp2-frozen-v1
full criterion; `chain` runs it end-to-end. No analysis threshold is changed —
v2's decision is `M_i > 0 AND p_i^robust <= alpha`, a strict subset of v1.
"""
