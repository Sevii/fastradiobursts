#!/usr/bin/env python3
"""W2.4 — adverse-simulation generators (proposal §5.6 control 4, §2.3 H-P/H-I/H-N).

Inject a SECOND component that imitates a lensed copy but breaks the strict
achromatic-scalar-copy model, into a real single-component burst. The copy
statistic must score these LESS copy-like than a true achromatic copy (higher
reduced χ², lower NCC) — that is the "known artifacts are rejected" half of the
W2.7 gate. `achromatic_copy` is the positive control (a genuine copy).

All operate on the Tier B `standardized` spectrum; return a modified tb.
"""
from __future__ import annotations

import numpy as np

from ..copy.statistic import time_shift

HW = 8                                   # component half-width (bins)
K_DM = 4.148808                          # ms, DM in pc/cm^3, freq in GHz


def overlapping_dt_bins(tb, dt_min_ms=2.0):
    """Largest whole-bin delay that is strictly SHORTER than the search floor.

    W3b.3 / WP3 gate-memo item 3. The `overlapping` control is meant to be an
    UNRESOLVED second image — a delay the pipeline must not be able to claim. It
    was hardcoded at 3 bins ≈ 2.95 ms, which is INSIDE the declared Δt ≥ 2 ms
    domain, so a "false positive" there was arguably the pipeline correctly
    detecting a real short-delay copy (round-1 overlapping FP 60%, docs/
    WP3_blind_validation_report.md). Deriving it from the burst's own ms/bin puts
    the control back below the floor: 2 bins ≈ 1.97 ms at CHIME's 0.983 ms.
    """
    mpb = float(tb["res_time"]) * 1e3
    if not np.isfinite(mpb) or mpb <= 0:
        return 1
    return int(max(1, np.floor((float(dt_min_ms) - 1e-9) / mpb)))


def _component(std, c, hw=HW):
    comp = np.zeros_like(std)
    lo, hi = max(0, c - hw), min(std.shape[1], c + hw + 1)
    comp[:, lo:hi] = std[:, lo:hi]
    return comp


def per_channel_time_shift(patch, shifts_bins):
    """Shift each channel along time by its own (fractional) bin amount."""
    out = np.zeros_like(patch)
    r = np.round(shifts_bins).astype(int)
    for s in np.unique(r):
        rows = np.where(r == s)[0]
        out[rows] = time_shift(patch[rows], s) if s != 0 else patch[rows]
    return out


def _second_image(std, tb, c, dt, mu, kind, rng, **p):
    T = _component(std, c)
    nf, nw = std.shape
    if kind == "achromatic_copy":                         # positive control
        return mu * time_shift(T, dt)
    if kind == "overlapping":                             # UNRESOLVED echo: dt < dt_min
        return mu * time_shift(T, overlapping_dt_bins(tb, p.get("dt_min_ms", 2.0))
                               if p.get("dt_small") is None else max(1, p["dt_small"]))
    if kind == "drift":                                   # chromatic freq offset
        return mu * np.roll(time_shift(T, dt), p.get("drift_channels", 600), axis=0)
    if kind == "scintillation":                           # freq-dependent amplitude
        scale = p.get("scale", 120.0)
        m = 1.0 + 0.9 * np.sin(2 * np.pi * np.arange(nf) / scale + rng.uniform(0, 6))
        return mu * time_shift(T, dt) * m[:, None]
    if kind == "differential_scattering":                 # one-sided exp tail
        tau = float(p.get("tau_bins", 4.0))
        k = np.exp(-np.arange(0, 6 * tau) / tau); k /= k.sum()
        sec = mu * time_shift(T, dt)
        from scipy.ndimage import convolve1d
        return convolve1d(sec, k, axis=1, mode="constant", origin=-(len(k) // 2))
    if kind in ("differential_dm", "chromatic_echo"):     # per-channel time delay
        freqs = np.asarray(tb["freqs"], float)
        mpb = float(tb["res_time"]) * 1e3
        if kind == "differential_dm":
            g = (freqs / 1e3); fref = g.max()
            dshift = K_DM * p.get("dm_extra", 0.3) * (g ** -2 - fref ** -2) / mpb
        else:                                             # linear chromatic echo
            dshift = p.get("slope_bins", 8.0) * (np.arange(nf) - nf / 2) / nf
        return mu * per_channel_time_shift(time_shift(T, dt), dt * 0 + dshift)
    if kind == "rfi_remnant":                             # narrowband stripe, not a burst
        sec = np.zeros_like(std)
        ch0 = rng.integers(0, nf - 200); tcen = c + dt
        lo, hi = max(0, tcen - 1), min(nw, tcen + 2)
        sec[ch0:ch0 + 200, lo:hi] = mu * np.abs(std).max()
        return sec
    raise ValueError(kind)


KINDS = ["achromatic_copy", "drift", "differential_dm", "differential_scattering",
         "chromatic_echo", "scintillation", "overlapping", "rfi_remnant"]


def inject(tb, c, dt, mu, kind, rng, **params):
    std = np.asarray(tb["standardized"], float).copy()
    std = std + _second_image(std, tb, c, dt, mu, kind, rng, **params)
    out = dict(tb); out["standardized"] = std.astype(np.float32)
    return out
