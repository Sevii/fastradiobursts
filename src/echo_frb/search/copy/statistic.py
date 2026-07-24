#!/usr/bin/env python3
"""W2.2 (v2) — masked, noise-weighted 2-D copy statistic (proposal §5.4).

Tests whether component B is an achromatic, magnified, delayed copy of A:
    B(t,ν) ≈ a · A(t−Δt, ν) + noise.

v1 ran the residual over the full 16384-channel patch and was swamped by empty
band (NCC→0, no separation). v2 fixes three things, validated by real data:
  1. mask-aware INVERSE-VARIANCE frequency rebinning (raise per-pixel S/N);
  2. ON-BURST SUPPORT — compare only where the reference component A has power
     (occupied sub-band × component window), so noise pixels don't dilute;
  3. TEMPLATE amplitude fit — A (the brighter first image) is the template, so a
     has the closed form a = Σ(A·B/σ_B²)/Σ(A²/σ_B²) and Δχ² is the matched-filter
     detection statistic Σ(AB/σ_B²)²/Σ(A²/σ_B²) — no a↔variance degeneracy.

Primary outputs: reduced_chi2 (goodness of the copy fit; ~1 for a true copy,
>1 when B's fine structure differs), delta_chi2 (matched-filter copy detection),
ncc (on-burst correlation), best_a, best Δt.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import shift as _ndshift

MIN_PIXELS = 32


def time_shift(arr, d, order=1):
    return _ndshift(np.asarray(arr, float), shift=(0.0, float(d)), order=order,
                    mode="constant", cval=0.0)


def _as_var(sig, nf):
    s = np.asarray(sig, float)
    return s ** 2 if s.ndim == 1 else s ** 2                # per-channel (nf,)


def rebin_iv(patch, sig, valid, nbin):
    """Mask-aware inverse-variance frequency rebin of a (nf, nw) patch.

    Returns (patch_rebin, var_rebin, valid_rebin) each (nbin, nw). Per bin/time:
    weighted mean of valid channels (w = 1/σ²), variance = 1/Σw.
    """
    patch = np.asarray(patch, float)
    nf, nw = patch.shape
    var_ch = _as_var(sig, nf)
    w_ch = np.where((var_ch > 0) & np.isfinite(var_ch), 1.0 / var_ch, 0.0)  # (nf,)
    W = w_ch[:, None] * np.asarray(valid, bool)             # (nf, nw)
    edges = np.linspace(0, nf, nbin + 1).astype(int)
    A = np.zeros((nbin, nw)); var = np.full((nbin, nw), np.inf)
    vout = np.zeros((nbin, nw), bool)
    for b in range(nbin):
        lo, hi = edges[b], edges[b + 1]
        sw = W[lo:hi].sum(0)                                # (nw,)
        good = sw > 0
        A[b, good] = (W[lo:hi, good] * patch[lo:hi, good]).sum(0) / sw[good]
        var[b, good] = 1.0 / sw[good]
        vout[b, good] = True
    return A, var, vout


def _template_fit(A, B, varB, varA, V, bounds):
    Av, Bv, vB, vA = A[V], B[V], varB[V], varA[V]
    SAA = float(np.sum(Av * Av / vB))
    SAB = float(np.sum(Av * Bv / vB))
    SBB = float(np.sum(Bv * Bv / vB))
    if SAA <= 0:
        return 0.0, SBB, 0.0, np.inf
    a = SAB / SAA
    a = float(min(max(a, bounds[0]), bounds[1]))            # clip to (0,1]
    chi_best = float(np.sum((Bv - a * Av) ** 2 / vB))       # template weighting -> Δχ²
    # goodness-of-fit residual whitened by the FULL noise (A is noisy too), so a
    # true copy gives reduced χ² ~ 1 at ANY magnification a (not 1 + a²).
    resid_full = float(np.sum((Bv - a * Av) ** 2 / (vB + a * a * vA)))
    return a, chi_best, SBB - chi_best, resid_full          # a, chi2_best, Δχ², resid_full


def _ncc(A, B, V):
    a, b = A[V], B[V]
    a = a - a.mean(); b = b - b.mean()
    d = np.sqrt(np.sum(a * a) * np.sum(b * b))
    return float(np.sum(a * b) / d) if d > 0 else 0.0


def copy_score(A, B, sigA, sigB, validA, validB, trial_delays,
               mag_bounds=(0.02, 1.0), rebin_nf=256, on_burst_k=2.0,
               min_pixels=MIN_PIXELS, order=1):
    A = np.asarray(A, float); B = np.asarray(B, float)
    vA = np.asarray(validA, bool); vB = np.asarray(validB, bool)

    if rebin_nf and A.shape[0] > rebin_nf:
        Ar, varA, vAr = rebin_iv(A, sigA, vA, rebin_nf)
        Br, varB, vBr = rebin_iv(B, sigB, vB, rebin_nf)
    else:
        Ar, Br = A, B
        varA = _as_var(sigA, A.shape[0])[:, None] * np.ones_like(A)
        varB = _as_var(sigB, B.shape[0])[:, None] * np.ones_like(B)
        vAr, vBr = vA, vB

    finite = np.isfinite(Ar) & np.isfinite(Br) & (varB > 0)
    # on-burst support from the REFERENCE component A (unbiased for "B copies A")
    if on_burst_k:
        sigpix = np.where(vAr & (varA > 0), np.abs(Ar) / np.sqrt(varA), 0.0)
        support = vAr & (sigpix > on_burst_k)
    else:
        support = vAr

    curve, best = [], None
    for d in trial_delays:
        Ash = time_shift(Ar, d, order=order)
        supp = time_shift((support & vAr).astype(float), d, order=order) > 0.5
        V = vBr & supp & finite
        npix = int(V.sum())
        if npix < min_pixels:
            curve.append((float(d), np.nan)); continue
        varAsh = time_shift(varA, d, order=order)
        varAsh = np.where(varAsh > 0, varAsh, np.inf)
        a, chi_best, delta, resid_full = _template_fit(Ash, Br, varB, varAsh, V,
                                                       mag_bounds)
        red = resid_full / max(1, npix - 1)
        curve.append((float(d), delta))
        if best is None or delta > best["delta_chi2"]:
            best = dict(best_delay_bins=float(d), best_a=a, reduced_chi2=red,
                        delta_chi2=delta, chi2_best=chi_best,
                        ncc=_ncc(Ash, Br, V), n_valid=npix)
    if best is None:
        best = dict(best_delay_bins=np.nan, best_a=np.nan, reduced_chi2=np.inf,
                    delta_chi2=0.0, chi2_best=np.inf, ncc=0.0, n_valid=0)
    best["delay_curve"] = curve
    return best
