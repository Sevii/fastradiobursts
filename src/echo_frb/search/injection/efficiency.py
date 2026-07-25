#!/usr/bin/env python3
"""W2.6 — recovery flag + binned detection efficiency with binomial CIs.

delta_chi2 is the matched-filter copy-detection statistic (≈ SNR²), so recovery
requires enough signal (delta_chi2 > τ) AND copy-like quality (high NCC, residual
noise-like). Injected copies are copy-like by construction, so ε is driven mainly
by detectability = f(μ, host S/N) — the efficiency surface the limits depend on.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Frozen candidate detectability + copy-quality (config: candidate_criterion).
RECOVERY = dict(delta_min=100.0, ncc_min=0.40, reduced_max=1.5)


def recovery_flag(df, delta_min=None, ncc_min=None, reduced_max=None):
    d = RECOVERY["delta_min"] if delta_min is None else delta_min
    n = RECOVERY["ncc_min"] if ncc_min is None else ncc_min
    r = RECOVERY["reduced_max"] if reduced_max is None else reduced_max
    return (df.delta_chi2 > d) & (df.ncc > n) & (df.reduced_chi2 < r)


def wilson(k, n, z=1.96):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return np.nan, np.nan, np.nan
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def efficiency_by(df, by, use_flag_column=False):
    """Binned efficiency with Wilson CIs.

    By default the recovery flag is RECOMPUTED from the copy criterion (Δχ², NCC,
    reduced χ²) — the W2.6 behaviour, kept so the injection campaign is unchanged.
    Pass `use_flag_column=True` when the caller's `recovered` column is the
    decision (e.g. the v2 rule `M > 0 AND p_robust <= alpha`), which the copy
    criterion alone cannot reproduce: silently overwriting it there reports a
    materially higher efficiency than the analysis actually achieves.
    """
    df = df if use_flag_column else df.assign(recovered=recovery_flag(df))
    rows = []
    for key, g in df.groupby(by):
        k, n = int(g.recovered.sum()), len(g)
        p, lo, hi = wilson(k, n)
        rec = {by if isinstance(by, str) else "_".join(by): key,
               "n": n, "recovered": k, "efficiency": round(p, 3),
               "ci_lo": round(lo, 3), "ci_hi": round(hi, 3)}
        rows.append(rec)
    return pd.DataFrame(rows)


def surface(df, mu_col="mu", snr_col="host_snr_bin"):
    """2-D ε(μ, host S/N) grid with counts + Wilson CIs."""
    df = df.assign(recovered=recovery_flag(df))
    g = df.groupby([mu_col, snr_col]).recovered.agg(["sum", "count"]).reset_index()
    g["efficiency"] = g["sum"] / g["count"]
    ci = g.apply(lambda r: wilson(r["sum"], r["count"]), axis=1, result_type="expand")
    g["ci_lo"], g["ci_hi"] = ci[1].round(3), ci[2].round(3)
    return g.rename(columns={"sum": "recovered", "count": "n"})
