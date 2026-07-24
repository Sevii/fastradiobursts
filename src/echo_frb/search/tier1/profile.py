#!/usr/bin/env python3
"""W2.1 — noise-weighted frequency-integrated profile I(t) + off-pulse stats.

The inverse-variance channel mean (minimum-variance estimator of the common
burst profile), gated per-pixel by the project mask. Off-pulse baseline μ and
noise σ come from the Tier B off-pulse time mask (robust 1.4826·MAD).
"""
from __future__ import annotations

import numpy as np


def build_profile(tb):
    x = np.asarray(tb["standardized"], np.float64)          # (nf, nt)
    pmask = np.asarray(tb["project_mask"], bool)
    rs = np.asarray(tb["robust_std"], np.float64)
    chan_ok = np.asarray(tb["channel_usable"], bool) & np.isfinite(rs) & (rs > 0)
    w = np.zeros_like(rs)
    w[chan_ok] = 1.0 / rs[chan_ok] ** 2

    W = w[:, None] * pmask                                   # (nf, nt)
    num = np.nansum(W * x, axis=0)
    den = W.sum(axis=0)
    I = np.zeros_like(num)
    good = den > 0
    I[good] = num[good] / den[good]

    off = np.asarray(tb["offpulse"], bool)
    if off.sum() >= 4:
        v = I[off]
        mu = float(np.median(v))
        sigma = float(1.4826 * np.median(np.abs(v - mu)))
    else:
        mu, sigma = float(np.median(I)), float(np.std(I))
    if not np.isfinite(sigma) or sigma <= 0:
        sigma = float(np.std(I)) or 1.0
    return dict(I=I, mu_off=mu, sigma_off=sigma, n_valid_bins=int(good.sum()))
