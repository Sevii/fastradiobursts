#!/usr/bin/env python3
"""Steps 2-4 — normalized ACF, Gaussian-smoothed baseline, 3-sigma spike search.

Clean-room implementation from PAPER_SPEC.md (Zhou et al. 2026).

    C(dt) = (1 / (N_dt * sigma_I^2)) * sum_t Ihat(t) Ihat(t - dt)      (Eq. 2)
    G(dt) = Gaussian_smooth(C, sigma = 3)                              (paper)
    sigma_dt = sqrt( (1/N) sum ( C - G )^2 )                           (Eq. 4)
    spike where  C(dt) > G(dt) + 3 * sigma_dt                          (paper)

The zero-lag core (|dt| < min_lag_bins) is excluded from BOTH the sigma_dt
scatter estimate and the spike search, because C(0)=1 by construction and its
smoothed shoulder would otherwise dominate the scatter (our documented choice).
A lensed (delayed scalar copy) burst produces a spike whose amplitude relative
to the zero-lag peak is R_f/(R_f^2+1); we invert this to cross-check R_f.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d


def normalized_acf(I, max_lag):
    """One-sided normalized ACF C(k) for k = 0..max_lag (Eq. 2). C(0) == 1."""
    x = np.asarray(I, dtype=np.float64)
    n = x.size
    max_lag = int(min(max_lag, n - 1))
    xhat = x - x.mean()
    var = np.mean(xhat * xhat)
    C = np.zeros(max_lag + 1, dtype=np.float64)
    if var <= 0:
        return C  # flat signal -> no correlation structure
    for k in range(max_lag + 1):
        N_k = n - k
        C[k] = np.dot(xhat[k:], xhat[: n - k]) / (N_k * var)
    return C


def smoothed_baseline(C, sigma):
    """G(dt): Gaussian-smoothed ACF baseline (kernel std = sigma)."""
    return gaussian_filter1d(np.asarray(C, dtype=np.float64), sigma=float(sigma),
                             mode="nearest")


def find_spikes(C, sigma_smooth, spike_nsigma, min_lag_bins):
    """Return dict with G, sigma_dt, threshold curve and detected spike lags.

    Spikes are contiguous runs of lags exceeding G + n*sigma_dt (outside the
    zero-lag core); each run is reduced to its peak lag. Amplitude reported is
    C at the peak lag.
    """
    C = np.asarray(C, dtype=np.float64)
    G = smoothed_baseline(C, sigma_smooth)
    resid = C - G
    lags = np.arange(C.size)
    search = lags >= int(min_lag_bins)

    if search.sum() >= 2:
        sigma_dt = float(np.sqrt(np.mean(resid[search] ** 2)))
    else:
        sigma_dt = float(np.sqrt(np.mean(resid ** 2))) if resid.size else 0.0
    thr = G + spike_nsigma * sigma_dt

    above = (C > thr) & search
    spikes = []
    k = 0
    n = C.size
    while k < n:
        if above[k]:
            j = k
            while j + 1 < n and above[j + 1]:
                j += 1
            seg = np.arange(k, j + 1)
            pk = int(seg[np.argmax(C[seg])])
            spikes.append(dict(lag_bins=pk, amplitude=float(C[pk]),
                               excess=float(C[pk] - thr[pk])))
            k = j + 1
        else:
            k += 1
    return dict(G=G, sigma_dt=sigma_dt, threshold=thr, spikes=spikes)


def rf_from_acf_amplitude(amp):
    """Invert amp = R_f/(R_f^2+1) for R_f >= 1; NaN if amp not in (0, 0.5]."""
    a = float(amp)
    if not (0.0 < a <= 0.5):
        return float("nan")
    disc = 1.0 - 4.0 * a * a
    if disc < 0:
        return float("nan")
    r = (1.0 + np.sqrt(disc)) / (2.0 * a)  # >= 1 root
    return float(r)
