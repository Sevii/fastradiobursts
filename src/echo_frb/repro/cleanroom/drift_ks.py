#!/usr/bin/env python3
"""Step 7 — achromaticity / drift test via a two-sample K-S statistic.

Clean-room implementation from PAPER_SPEC.md (Zhou et al. 2026).

A genuine lensed copy shows the SAME frequency spectrum in both images; an
intrinsic multi-component burst drifts in frequency. For a matched component
pair we extract each component's per-channel spectrum, rebin 16384 -> n_f=512
(mask-aware), and compare them:

    D_max = sup_f | CDF( Ibar_i(f) ) - CDF( Ibar_j(f) ) |               (Eq. 6)
    D_crit = 1.36 * sqrt(2 / n_f) ~ 0.1  @ alpha = 0.05                 (paper)

D_{n,upp} is a noise-only upper bound on D under the null of identical spectra,
built by bootstrap (~1e3 iters): take the mean of the two spectra as the shared
truth, add independent per-rebinned-channel Gaussian noise to two realizations,
and record D. D_{n,upp} = the upp_percentile of that null D distribution.

Drift (i.e. NOT a copy) is declared iff  D_max > D_crit  AND  D_max > D_{n,upp}.

Implementation choices (paper silent): (a) a component's spectrum is the
time-integral of the standardized dynamic spectrum over its +/- halfwidth window;
(b) spectra are turned into distributions for the CDF by clipping negatives to 0
then normalizing to unit sum; (c) the per-rebinned-channel noise for the null is
propagated from robust_std over the integration window and the mask-aware rebin;
(d) the bootstrap RNG is seeded (config) so the test is deterministic.
"""
from __future__ import annotations

import numpy as np


def d_crit(n_f, coeff=1.36):
    """K-S critical value at alpha=0.05 for two equal-size samples of n_f."""
    return float(coeff) * np.sqrt(2.0 / float(n_f))


def _rebin(vec, valid, nbin):
    """Mask-aware block average of a (nf,) vector -> (nbin,); NaN empty blocks."""
    nf = vec.size
    edges = np.linspace(0, nf, nbin + 1).astype(int)
    out = np.full(nbin, np.nan)
    cnt = np.zeros(nbin)
    for i in range(nbin):
        a, b = edges[i], edges[i + 1]
        if b <= a:
            continue
        m = valid[a:b]
        c = int(m.sum())
        cnt[i] = c
        if c:
            out[i] = np.sum(np.where(m, vec[a:b], 0.0)) / c
    return out, cnt


def component_spectrum(standardized, robust_std, valid_chan, center, halfwidth,
                       n_f):
    """Integrated + rebinned spectrum and its per-rebinned-channel noise sigma.

    Returns (spec[n_f], sigma[n_f], ok[n_f]) where ok marks non-empty rebin bins
    with a finite spectrum and positive noise.
    """
    nt = standardized.shape[1]
    a = max(0, center - halfwidth)
    b = min(nt, center + halfwidth + 1)
    nw = max(1, b - a)
    spec_full = standardized[:, a:b].astype(np.float64).sum(axis=1)   # (nf,)

    rs = np.asarray(robust_std, dtype=np.float64)
    var_full = np.where(np.isfinite(rs), nw * rs * rs, np.nan)         # integ. var

    spec, cnt = _rebin(spec_full, valid_chan, n_f)
    # noise of a block mean over M valid channels: var_reb = (1/M^2) sum var_c
    sig = np.full(n_f, np.nan)
    edges = np.linspace(0, spec_full.size, n_f + 1).astype(int)
    for i in range(n_f):
        lo, hi = edges[i], edges[i + 1]
        m = valid_chan[lo:hi]
        M = int(m.sum())
        if M:
            vv = np.where(m, var_full[lo:hi], 0.0)
            sig[i] = np.sqrt(np.nansum(vv)) / M
    ok = np.isfinite(spec) & np.isfinite(sig) & (sig > 0)
    return spec, sig, ok


def _as_distribution(spec):
    """Clip negatives to 0 and normalize to unit sum; uniform if all <= 0."""
    p = np.clip(np.asarray(spec, dtype=np.float64), 0.0, None)
    s = p.sum()
    if s <= 0:
        return np.full(p.size, 1.0 / p.size)
    return p / s


def ks_distance(spec_i, spec_j):
    """D_max between two binned spectra via their normalized cumulative CDFs."""
    pi = _as_distribution(spec_i)
    pj = _as_distribution(spec_j)
    return float(np.max(np.abs(np.cumsum(pi) - np.cumsum(pj))))


def drift_test(spec_i, sig_i, spec_j, sig_j, ok, n_f, cfg_ks, rng):
    """Run the K-S drift test on a matched pair over the shared-usable channels.

    Returns dict(d_max, d_crit, d_upp, has_drift, n_used).
    """
    dc = d_crit(n_f)
    use = np.asarray(ok, dtype=bool)
    n_used = int(use.sum())
    if n_used < 8:
        # too few usable channels to judge; do not declare drift
        return dict(d_max=float("nan"), d_crit=dc, d_upp=float("nan"),
                    has_drift=False, n_used=n_used)

    si = spec_i[use]
    sj = spec_j[use]
    d_max = ks_distance(si, sj)

    # bootstrap null: identical (mean) spectrum + independent noise realizations
    truth = 0.5 * (si + sj)
    ni = sig_i[use]
    nj = sig_j[use]
    iters = int(cfg_ks["bootstrap_iters"])
    ds = np.empty(iters)
    for t in range(iters):
        ri = truth + rng.standard_normal(truth.size) * ni
        rj = truth + rng.standard_normal(truth.size) * nj
        ds[t] = ks_distance(ri, rj)
    d_upp = float(np.percentile(ds, float(cfg_ks["upp_percentile"])))

    has_drift = bool((d_max > dc) and (d_max > d_upp))
    return dict(d_max=float(d_max), d_crit=float(dc), d_upp=d_upp,
                has_drift=has_drift, n_used=n_used)
