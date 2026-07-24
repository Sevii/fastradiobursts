#!/usr/bin/env python3
"""W2.2 — extract two equal component patches (A, B) from a Tier B spectrum.

Given a loaded Tier B dict and two component time-bin centers, return equal-shape
(n_freq, 2*halfwidth+1) patches plus per-channel noise and per-pixel validity
(project_mask ∧ channel_usable). Feeds the copy statistic; the component centers
come from the Tier-1 proposal (W2.1).
"""
from __future__ import annotations

import numpy as np


def extract_pair(tb, center_a, center_b, halfwidth):
    std = np.asarray(tb["standardized"], float)          # (nf, nt)
    pmask = np.asarray(tb["project_mask"], bool)
    chan_ok = np.asarray(tb["channel_usable"], bool)
    sig = np.asarray(tb["robust_std"], float)
    nf, nt = std.shape
    hw = int(halfwidth)

    def win(c):
        lo, hi = int(c) - hw, int(c) + hw + 1
        if lo < 0 or hi > nt:
            pad_lo, pad_hi = max(0, -lo), max(0, hi - nt)
            lo2, hi2 = max(0, lo), min(nt, hi)
            patch = std[:, lo2:hi2]
            vmask = pmask[:, lo2:hi2]
            patch = np.pad(patch, ((0, 0), (pad_lo, pad_hi)))
            vmask = np.pad(vmask, ((0, 0), (pad_lo, pad_hi)), constant_values=False)
        else:
            patch, vmask = std[:, lo:hi], pmask[:, lo:hi]
        valid = vmask & chan_ok[:, None] & np.isfinite(sig)[:, None]
        return patch, valid

    A, vA = win(center_a)
    B, vB = win(center_b)
    return dict(A=A, B=B, sigA=sig, sigB=sig, validA=vA, validB=vB,
                halfwidth=hw, center_a=int(center_a), center_b=int(center_b))
