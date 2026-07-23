#!/usr/bin/env python3
"""Steps 5-6 — burst-peak detection, spike/peak matching, selection cuts.

Clean-room implementation from PAPER_SPEC.md (Zhou et al. 2026).

  * Peak detection (choice): scipy.signal.find_peaks on I(t), with a height of
    mu_off + detect_snr * sigma_noise and a minimum separation. PSNR of a peak
    is (I_peak - mu_off) / sigma_noise (Eq. 5 form).
  * Matching (paper): an ACF spike at lag L is accepted only if some ordered
    component pair (i earlier, j later) has |dt_ij - L| <= match_tol_ms.
  * Cuts on a matched pair (paper): temporal ordering (leading PSNR >= trailing
    PSNR), secondary PSNR > secondary_psnr_min, and the pair must include the
    global-max (highest-PSNR) peak.
  * Component flux (choice): integral of (I - mu_off) over a +/- halfwidth window
    around each peak; the half-width auto-shrinks so paired windows never overlap.
    R_f (magnification ratio) = F_leading / F_trailing (>= 1 under ordering).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks


def detect_peaks(I, meta, detect_snr, min_separation_bins):
    """Return a list of peak dicts sorted by time-bin index."""
    mu = meta["mu_off"]
    sig = meta["sigma_noise"]
    height = mu + detect_snr * sig
    idx, props = find_peaks(I, height=height,
                            distance=max(1, int(min_separation_bins)))
    peaks = []
    for p in idx:
        psnr = (float(I[p]) - mu) / sig if sig > 0 else 0.0
        peaks.append(dict(bin=int(p), psnr=float(psnr), amp=float(I[p] - mu)))
    peaks.sort(key=lambda d: d["bin"])
    return peaks


def component_flux(I, mu_off, center, halfwidth):
    """Integrate (I - mu_off) over [center-hw, center+hw] (clipped to array)."""
    n = I.size
    a = max(0, center - halfwidth)
    b = min(n, center + halfwidth + 1)
    return float(np.sum(I[a:b] - mu_off))


def match_spikes_to_peaks(spikes, peaks, ms_per_bin, match_tol_ms):
    """For each spike lag, list ordered peak pairs whose separation matches.

    Returns a list of matched-pair dicts (i<j by time), each carrying the spike
    it matched and the pair's measured delay.
    """
    matches = []
    for s in spikes:
        lag_ms = s["lag_bins"] * ms_per_bin
        for a in range(len(peaks)):
            for b in range(a + 1, len(peaks)):
                sep_bins = peaks[b]["bin"] - peaks[a]["bin"]
                sep_ms = sep_bins * ms_per_bin
                if abs(sep_ms - lag_ms) <= match_tol_ms:
                    matches.append(dict(
                        lead=peaks[a], trail=peaks[b],
                        lead_bin=peaks[a]["bin"], trail_bin=peaks[b]["bin"],
                        sep_bins=int(sep_bins), delay_ms=float(sep_ms),
                        spike=s, spike_lag_ms=float(lag_ms),
                    ))
    return matches


def apply_selection_cuts(match, peaks, secondary_psnr_min):
    """Evaluate the three paper cuts for one matched pair. Returns (ok, flags)."""
    lead, trail = match["lead"], match["trail"]
    global_max_bin = max(peaks, key=lambda d: d["psnr"])["bin"] if peaks else None
    ordering_ok = lead["psnr"] >= trail["psnr"]
    secondary_ok = trail["psnr"] > secondary_psnr_min
    global_ok = global_max_bin in (lead["bin"], trail["bin"])
    flags = dict(ordering_ok=bool(ordering_ok),
                 secondary_ok=bool(secondary_ok),
                 global_max_ok=bool(global_ok))
    return (ordering_ok and secondary_ok and global_ok), flags


def magnification_ratio(I, mu_off, match, halfwidth):
    """R_f = F_leading / F_trailing using non-overlapping component windows."""
    hw = int(halfwidth)
    hw = min(hw, max(1, match["sep_bins"] // 2))
    fl = component_flux(I, mu_off, match["lead_bin"], hw)
    ft = component_flux(I, mu_off, match["trail_bin"], hw)
    if ft == 0:
        return float("nan"), fl, ft
    r = fl / ft
    return float(r), float(fl), float(ft)
