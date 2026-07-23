#!/usr/bin/env python3
"""Step 1 — frequency-integrated light curve I(t) from a Tier B dynamic spectrum.

Clean-room implementation from PAPER_SPEC.md (Zhou et al. 2026), Step 1.

Implementation choices (paper is silent on the exact weighting):
  * We form an inverse-variance-weighted channel mean:
        I(t) = sum_c w_c x_c(t) / sum_c w_c ,  w_c = 1 / robust_std_c^2
    over channels that are usable (project_mask AND channel_usable AND finite,
    positive robust_std). This is the minimum-variance linear estimator of the
    common burst profile and matches "valid channels + appropriate noise
    weighting" in the spec. A per-time-bin weight uses the pixel-level
    project_mask so masked pixels drop out bin-by-bin.
  * The light-curve noise sigma_noise and baseline mu_off are estimated from the
    off-pulse time bins (offpulse/time_mask) using a robust 1.4826*MAD.
"""
from __future__ import annotations

import h5py
import numpy as np


def load_tier_b(path):
    """Load the Tier B arrays this pipeline needs (incl. coords + attrs)."""
    with h5py.File(path, "r") as f:
        out = dict(
            standardized=f["standardized"][()].astype(np.float32),
            project_mask=f["mask/project_mask"][()],
            robust_std=f["noise/robust_std"][()],
            channel_usable=f["noise/channel_usable"][()],
            offpulse=f["offpulse/time_mask"][()],
            freqs=f["coords/freqs"][()],
            times=f["coords/times"][()],
            attrs=dict(f.attrs),
        )
    return out


def channel_weights(robust_std, channel_usable):
    """Inverse-variance channel weights; 0 where a channel is unusable."""
    rs = np.asarray(robust_std, dtype=np.float64)
    ok = np.asarray(channel_usable, dtype=bool) & np.isfinite(rs) & (rs > 0)
    w = np.zeros_like(rs)
    w[ok] = 1.0 / (rs[ok] ** 2)
    return w, ok


def build_lightcurve(tb):
    """Return (I(t), meta) where I is the inverse-variance-weighted light curve.

    meta holds res_time (s), the off-pulse mask, and robust off-pulse baseline
    mu_off and noise sigma_noise of I(t).
    """
    x = np.asarray(tb["standardized"], dtype=np.float64)          # (nf, nt)
    pmask = np.asarray(tb["project_mask"], dtype=bool)            # (nf, nt)
    w, chan_ok = channel_weights(tb["robust_std"], tb["channel_usable"])

    # per-pixel weight: channel weight, gated by the pixel-level project mask
    W = (w[:, None] * pmask)                                      # (nf, nt)
    num = (W * x).sum(axis=0)
    den = W.sum(axis=0)
    I = np.zeros_like(num)
    good = den > 0
    I[good] = num[good] / den[good]

    off = np.asarray(tb["offpulse"], dtype=bool)
    res_time = float(tb["attrs"].get("res_time", np.nan))
    if off.sum() >= 4:
        off_vals = I[off]
        mu_off = float(np.median(off_vals))
        mad = float(np.median(np.abs(off_vals - mu_off)))
        sigma_noise = 1.4826 * mad
    else:
        mu_off = float(np.median(I))
        sigma_noise = float(np.std(I))
    if not np.isfinite(sigma_noise) or sigma_noise <= 0:
        sigma_noise = float(np.std(I)) or 1.0

    meta = dict(
        res_time=res_time,
        offpulse=off,
        mu_off=mu_off,
        sigma_noise=sigma_noise,
        n_usable_channels=int(chan_ok.sum()),
        chan_weights=w,
        chan_ok=chan_ok,
    )
    return I, meta


def ms_per_bin(res_time):
    return float(res_time) * 1e3
