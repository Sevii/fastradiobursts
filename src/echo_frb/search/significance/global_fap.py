#!/usr/bin/env python3
"""W2.8 — local -> global significance via the max-statistic (proposal §6.1).

A local copy score is not a catalog-level significance: the look-elsewhere effect
spans every burst, source, delay, and proposal. The global family-wise false-alarm
probability is the tail of the MAXIMUM score produced by catalog-equivalent null
searches. Resampling is at the SOURCE level (repeaters share a source) to preserve
source-level dependence. Direct Monte Carlo gives the empirical FAP down to its
resolution 1/B; a Generalized-Pareto tail model (fit on one null half, validated
out-of-sample) extrapolates further. WP2 builds + null-calibrates this; the real
catalog-global evaluation is WP4.
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def catalog_max_bootstrap(scores, sources, n_boot=20000, seed=42):
    """Source-level cluster bootstrap of the catalog-max score.

    scores, sources: equal-length arrays (one row per null proposal). Each
    realization resamples n_sources sources WITH replacement, pools their proposal
    scores, and takes the max -> distribution of the catalog-max under the null.
    """
    scores = np.asarray(scores, float)
    sources = np.asarray(sources)
    uniq = np.unique(sources)
    by_src = {s: scores[sources == s] for s in uniq}
    n_src = len(uniq)
    rng = np.random.default_rng(seed)
    maxima = np.empty(n_boot)
    for b in range(n_boot):
        pick = uniq[rng.integers(0, n_src, size=n_src)]
        m = -np.inf
        for s in pick:
            arr = by_src[s]
            if arr.size:
                mx = arr.max()
                if mx > m:
                    m = mx
        maxima[b] = m
    return maxima


def global_fap(observed, maxima):
    """Conservative (add-one) empirical global FAP = P(catalog-max >= observed)."""
    maxima = np.asarray(maxima, float)
    return (1 + int(np.sum(maxima >= observed))) / (1 + len(maxima))


def empirical_resolution(n_boot):
    return 1.0 / n_boot


def gpd_tail_fit_validate(maxima, q=0.90, seed=0):
    """Fit a GPD to exceedances over the q-quantile on one half, validate on the
    other. Returns (params, validation) where validation compares predicted vs
    empirical exceedance probabilities at high quantiles (out-of-sample)."""
    maxima = np.asarray(maxima, float)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(maxima))
    tr, te = maxima[idx[::2]], maxima[idx[1::2]]
    u = np.quantile(tr, q)
    exc = tr[tr > u] - u
    if exc.size < 20:
        return None, None
    c, loc, scale = stats.genpareto.fit(exc, floc=0.0)
    p_u = float(np.mean(tr > u))                       # base-rate above threshold
    val = []
    for qq in (0.95, 0.99, 0.999):
        x = np.quantile(tr, qq)
        pred = p_u * float(stats.genpareto.sf(x - u, c, loc=0.0, scale=scale))
        emp = float(np.mean(te > x))                   # out-of-sample empirical
        val.append(dict(quantile=qq, x=round(x, 1), pred_fap=pred, emp_fap=emp))
    return dict(shape_c=c, scale=scale, threshold_u=u, p_above_u=p_u), val
