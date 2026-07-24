#!/usr/bin/env python3
"""W2.1 — classical Tier-1 candidate generation (segmentation + matched filter).

Over any eligible burst (regardless of morphology label): detect component peaks
in the noise-weighted profile, then propose (A, B, Δt) pairs whose separation
falls in the delay domain — plus a delayed-energy scan so single-peaked bursts
can still surface a faint second image. Each proposal carries a cheap 1-D triage
score (normalized cross-correlation of the two component windows). PURE TRIAGE —
the evidence is the 2-D χ²_copy (W2.2), applied to these proposals downstream.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from .profile import build_profile


def _delay_bounds_bins(tb, cfg, nt):
    mpb = float(tb["res_time"]) * 1e3
    dd = cfg["delay_domain"]
    # ceil the lower bound so every proposed delay is >= dt_min_ms; floor the
    # upper so none exceeds dt_max_ms or the per-burst window cap.
    lo = max(1, int(np.ceil(dd["dt_min_ms"] / mpb)))
    span_cap = int(np.floor(dd["per_burst_window_fraction"] * nt))
    hi = int(min(np.floor(dd["dt_max_ms"] / mpb), span_cap))
    return lo, max(lo, hi), mpb


def _ncc(I, ca, cb, hw):
    nt = I.size
    a0, a1 = max(0, ca - hw), min(nt, ca + hw + 1)
    b0, b1 = max(0, cb - hw), min(nt, cb + hw + 1)
    n = min(a1 - a0, b1 - b0)
    if n < 3:
        return 0.0
    x, y = I[a0:a0 + n].copy(), I[b0:b0 + n].copy()
    x -= x.mean(); y -= y.mean()
    d = np.sqrt(np.sum(x * x) * np.sum(y * y))
    return float(np.sum(x * y) / d) if d > 0 else 0.0


def scan_burst(tb, cfg, peak_nsigma=4.0, second_nsigma=3.0, max_proposals=10,
               window_hw_bins=None):
    prof = build_profile(tb)
    I, mu, sig = prof["I"], prof["mu_off"], prof["sigma_off"]
    nt = I.size
    lo, hi, mpb = _delay_bounds_bins(tb, cfg, nt)
    hw = int(window_hw_bins) if window_hw_bins else max(2, lo)

    # 1. primary component peaks (permissive)
    peaks, props = find_peaks(I, height=mu + peak_nsigma * sig, distance=max(1, lo // 2))
    peaks = list(peaks)
    proposals = []

    # 2. pair existing peaks within the delay domain
    for i in range(len(peaks)):
        for j in range(i + 1, len(peaks)):
            ca, cb = peaks[i], peaks[j]
            sep = cb - ca
            if lo <= sep <= hi:
                proposals.append((ca, cb, sep, _ncc(I, ca, cb, hw), "peak_pair"))

    # 3. delayed-energy scan off the brightest peak (catch faint 2nd images)
    if peaks:
        main = int(peaks[int(np.argmax(I[peaks]))])
        for d in range(lo, hi + 1):
            cb = main + d
            if cb < nt and I[cb] > mu + second_nsigma * sig:
                if not any(p[0] == main and p[1] == cb for p in proposals):
                    proposals.append((main, cb, d, _ncc(I, main, cb, hw), "delayed_energy"))

    # rank by triage score, cap
    proposals.sort(key=lambda p: p[3], reverse=True)
    proposals = proposals[:max_proposals]

    rows = []
    for ca, cb, sep, ncc, kind in proposals:
        rows.append(dict(
            tns_name=tb["tns_name"], center_a=int(ca), center_b=int(cb),
            delay_bins=int(sep), delay_ms=float(sep * mpb), triage_ncc=float(ncc),
            kind=kind, n_peaks=len(peaks),
            peak_a_snr=float((I[ca] - mu) / sig), peak_b_snr=float((I[cb] - mu) / sig),
        ))
    return rows, prof
