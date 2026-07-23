#!/usr/bin/env python3
"""Step 8 — hardness-ratio consistency cut.

Clean-room implementation from PAPER_SPEC.md (Zhou et al. 2026).

Split the band into 3 regions [L, M, H]. For each component integrate its
band flux (baseline already subtracted in Tier B) over its time window, and
form the two independent hardness ratios HR_HM = H/M and HR_ML = M/L. A lensed
copy has the same intrinsic spectrum, so the two components must share hardness
ratios; require agreement within consistency_nsigma (paper: 1 sigma), with
uncertainties propagated from the per-band noise (Eq. 8 form).

Implementation choices (paper silent): equal-width frequency thirds over the
usable channels; band uncertainty sigma_band = sqrt(nw) * sqrt(sum_c sigma_c^2)
over that band's usable channels (nw = window length in time bins); ratios with
a non-positive denominator are treated as a failed (inconsistent) cut.
"""
from __future__ import annotations

import numpy as np


def _band_flux(standardized, robust_std, valid_chan, chan_slice, center,
               halfwidth):
    """Return (flux, sigma) integrated over a band x its time window."""
    nt = standardized.shape[1]
    a = max(0, center - halfwidth)
    b = min(nt, center + halfwidth + 1)
    nw = max(1, b - a)
    lo, hi = chan_slice
    m = valid_chan[lo:hi]
    if not m.any():
        return float("nan"), float("nan")
    block = standardized[lo:hi, a:b].astype(np.float64)
    flux = float(np.sum(block[m]))
    rs = np.asarray(robust_std[lo:hi], dtype=np.float64)
    var = float(np.nansum(np.where(m, rs * rs, 0.0)) * nw)
    return flux, float(np.sqrt(var))


def _ratio(num, dnum, den, dden):
    """Ratio and 1-sigma error via standard propagation; NaN if den<=0."""
    if not np.isfinite(num) or not np.isfinite(den) or den <= 0:
        return float("nan"), float("nan")
    r = num / den
    rel = 0.0
    if num != 0:
        rel += (dnum / num) ** 2
    if den != 0:
        rel += (dden / den) ** 2
    return float(r), float(abs(r) * np.sqrt(rel))


def hardness_consistent(standardized, robust_std, valid_chan, lead_bin,
                        trail_bin, halfwidth, n_bands, consistency_nsigma):
    """Return (ok, detail). ok=True iff both HR ratios agree within nsigma."""
    nf = standardized.shape[0]
    edges = np.linspace(0, nf, n_bands + 1).astype(int)
    # band slices low->high frequency: L, M, H
    slices = [(edges[i], edges[i + 1]) for i in range(n_bands)]
    if n_bands != 3:
        # generalize: use lowest, middle, highest thirds
        slices = [slices[0], slices[len(slices) // 2], slices[-1]]

    def ratios(center):
        L = _band_flux(standardized, robust_std, valid_chan, slices[0], center, halfwidth)
        M = _band_flux(standardized, robust_std, valid_chan, slices[1], center, halfwidth)
        H = _band_flux(standardized, robust_std, valid_chan, slices[2], center, halfwidth)
        hr_hm, e_hm = _ratio(H[0], H[1], M[0], M[1])
        hr_ml, e_ml = _ratio(M[0], M[1], L[0], L[1])
        return (hr_hm, e_hm, hr_ml, e_ml)

    a = ratios(lead_bin)
    b = ratios(trail_bin)

    def agree(x, ex, y, ey):
        if not (np.isfinite(x) and np.isfinite(y)):
            return False
        sig = np.sqrt(ex * ex + ey * ey)
        if sig <= 0:
            return abs(x - y) == 0
        return abs(x - y) <= consistency_nsigma * sig

    hm_ok = agree(a[0], a[1], b[0], b[1])
    ml_ok = agree(a[2], a[3], b[2], b[3])
    ok = bool(hm_ok and ml_ok)
    detail = dict(lead_hr_hm=a[0], lead_hr_ml=a[2],
                  trail_hr_hm=b[0], trail_hr_ml=b[2],
                  hm_ok=bool(hm_ok), ml_ok=bool(ml_ok))
    return ok, detail
