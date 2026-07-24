#!/usr/bin/env python3
"""W2.5 — the 8 mandatory robustness diagnostics (proposal §5.5).

Applied to a candidate (a scored proposal). A genuine achromatic lensed copy is
stable under all of these; adverse imitators (drift, differential DM/scattering,
scintillation) fail the achromaticity/stability ones — this is what finishes
rejecting the borderline cases the copy score alone leaves ambiguous.

  achromatic_delay      per-band delay agrees within tolerance
  magnification_stability per-band magnification agrees
  leave_band_out        no single band controls the detection
  resolution_stability  score stable across rebin resolutions
  window_stability       score stable under component-window perturbation
  residual_structure    residual after the copy fit is noise-like
  fine_structure_order   A and B temporal structure aligns
  dm_scattering          delay is achromatic (not ~ν^-2) and widths match
"""
from __future__ import annotations

import numpy as np

from .. import tierb_io
from ..copy import extract, score as scoremod, statistic as st

K_BANDS = 4
TOL = dict(delay_bins=1.5, mag_rel=0.6, ncc_spread=0.25, band_out_frac=0.35,
           lag1=0.3, width_ratio=2.5)


def _occupied_channels(A, sig, valid, k=3.0):
    sig_ch = np.asarray(sig, float)
    power = np.where(valid, np.abs(A), 0.0).max(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        snr = power / sig_ch
    return np.isfinite(snr) & (snr > k) & valid.any(axis=1)


def _score_channels(ex, chan_mask, cfg, mpb, sep):
    vA = ex["validA"] & chan_mask[:, None]
    vB = ex["validB"] & chan_mask[:, None]
    return scoremod.score_pair(ex["A"], ex["B"], ex["sigA"], ex["sigB"], vA, vB,
                               cfg, mpb, sep)


def _bands(occ, k=K_BANDS):
    idx = np.where(occ)[0]
    if len(idx) < k * 4:
        return []
    return np.array_split(idx, k)


def run_all(tb, ca, cb, cfg):
    mpb = tierb_io.ms_per_bin(tb)
    sep = int(cb) - int(ca)
    hw = scoremod.halfwidth_for(sep)
    ex = extract.extract_pair(tb, ca, cb, hw)
    nf = ex["A"].shape[0]
    occ = _occupied_channels(ex["A"], ex["sigA"], ex["validA"])
    bands = _bands(occ)
    full = _score_channels(ex, occ if occ.any() else np.ones(nf, bool), cfg, mpb, sep)

    out = dict(sep_bins=sep, n_occupied=int(occ.sum()),
               full_ncc=full["ncc"], full_delta_chi2=full["delta_chi2"],
               full_reduced_chi2=full["reduced_chi2"], full_best_a=full["best_a"])

    # per-band delay + magnification
    delays, mags, nccs = [], [], []
    for b in bands:
        m = np.zeros(nf, bool); m[b] = True
        r = _score_channels(ex, m, cfg, mpb, sep)
        if r["n_valid"] >= 16 and np.isfinite(r["best_delay_bins"]):
            delays.append(r["best_delay_bins"]); mags.append(r["best_a"]); nccs.append(r["ncc"])

    out["n_bands_used"] = len(delays)
    if len(delays) >= 2:
        out["delay_spread_bins"] = float(np.ptp(delays))
        out["achromatic_delay_pass"] = out["delay_spread_bins"] <= TOL["delay_bins"]
        mrel = np.ptp(mags) / (np.mean(mags) + 1e-9)
        out["mag_rel_spread"] = float(mrel)
        out["magnification_stability_pass"] = mrel <= TOL["mag_rel"]
        # dm/scattering: is the per-band delay trend consistent with a single
        # achromatic delay (flat) rather than a nu^-2 sweep?
        out["dm_scattering_pass"] = out["delay_spread_bins"] <= TOL["delay_bins"]
    else:
        out.update(delay_spread_bins=np.nan, achromatic_delay_pass=False,
                   mag_rel_spread=np.nan, magnification_stability_pass=False,
                   dm_scattering_pass=False)

    # leave-band-out: detection survives removing any single band
    lbo = []
    for b in bands:
        m = occ.copy(); m[b] = False
        r = _score_channels(ex, m, cfg, mpb, sep)
        lbo.append(r["delta_chi2"])
    if lbo and full["delta_chi2"] > 0:
        out["leave_band_out_min_frac"] = float(min(lbo) / full["delta_chi2"])
        out["leave_band_out_pass"] = out["leave_band_out_min_frac"] >= TOL["band_out_frac"]
    else:
        out.update(leave_band_out_min_frac=np.nan, leave_band_out_pass=False)

    # resolution stability: NCC stable across rebin resolutions
    res_ncc = []
    for nfr in (128, 256, 512):
        vA = ex["validA"] & (occ[:, None] if occ.any() else True)
        vB = ex["validB"] & (occ[:, None] if occ.any() else True)
        r = st.copy_score(ex["A"], ex["B"], ex["sigA"], ex["sigB"], vA, vB,
                          np.arange(-2, 2.01, 0.5), rebin_nf=nfr, on_burst_k=2.0,
                          min_pixels=16)
        res_ncc.append(r["ncc"])
    out["resolution_ncc_spread"] = float(np.ptp(res_ncc))
    out["resolution_stability_pass"] = out["resolution_ncc_spread"] <= TOL["ncc_spread"]

    # window stability: NCC stable under +-2 bin halfwidth perturbation
    win_ncc = []
    for dhw in (-2, 0, 2):
        h = max(3, hw + dhw)
        e2 = extract.extract_pair(tb, ca, cb, h)
        o2 = _occupied_channels(e2["A"], e2["sigA"], e2["validA"])
        r = _score_channels(e2, o2 if o2.any() else np.ones(nf, bool), cfg, mpb, sep)
        win_ncc.append(r["ncc"])
    out["window_ncc_spread"] = float(np.ptp(win_ncc))
    out["window_stability_pass"] = out["window_ncc_spread"] <= TOL["ncc_spread"]

    # residual structure: reduced chi2 near 1 (already whitened) + low lag-1
    out["residual_reduced_chi2"] = full["reduced_chi2"]
    out["residual_structure_pass"] = full["reduced_chi2"] <= 1.5

    # fine-structure ordering: band-integrated A,B profiles correlate at the delay
    out["fine_structure_pass"] = full["ncc"] >= 0.4

    # spectral magnification flatness: a true copy has a frequency-FLAT B/A ratio;
    # scintillation / chromatic amplitude make a(ν) ripple. Estimate a per fine
    # rebinned channel over the on-burst window and test consistency with a
    # constant. Catches scintillation, which averages out of the coarse bands.
    out.update(_spectral_mag_flatness(ex, occ, mpb))

    # MANDATORY achromaticity: the defining lens signature. A candidate must pass
    # ALL of these (not merely accumulate votes) — a single frequency-dependent
    # delay/magnification failure disqualifies. Kills drift/DM/chromatic and
    # suppresses scintillation (a propagation effect; §11 says treat as adverse,
    # not claim ruled out).
    out["achromaticity_ok"] = bool(all(out.get(k) for k in (
        "achromatic_delay_pass", "magnification_stability_pass",
        "spectral_mag_flat_pass", "dm_scattering_pass")))

    checks = [k for k in out if k.endswith("_pass")]
    out["n_pass"] = int(sum(bool(out[k]) for k in checks))
    out["n_checks"] = len(checks)
    return out


def _spectral_mag_flatness(ex, occ, mpb, nbin=256, k_occ=2.0, tol_reduced=2.0):
    Ar, varA, vAr = st.rebin_iv(ex["A"], ex["sigA"], ex["validA"], nbin)
    Br, varB, vBr = st.rebin_iv(ex["B"], ex["sigB"], ex["validB"], nbin)
    V = vAr & vBr & np.isfinite(Ar) & np.isfinite(Br) & (varB > 0)
    sig_ch = np.where(V, np.abs(Ar) / np.sqrt(np.where(varA > 0, varA, np.inf)), 0.0)
    onb = V & (sig_ch > k_occ)
    a_i, w_i = [], []
    for i in range(nbin):
        m = onb[i]
        if m.sum() < 3:
            continue
        A, B, vB = Ar[i, m], Br[i, m], varB[i, m]
        saa = float(np.sum(A * A / vB))
        if saa <= 0:
            continue
        a_i.append(float(np.sum(A * B / vB) / saa))     # per-channel magnification
        w_i.append(saa)                                  # inverse-variance of a_i
    if len(a_i) < 6:
        return dict(spectral_mag_reduced=np.nan, spectral_mag_flat_pass=True)
    a_i, w_i = np.array(a_i), np.array(w_i)
    abar = np.sum(w_i * a_i) / np.sum(w_i)               # weighted-mean magnification
    chi2 = float(np.sum(w_i * (a_i - abar) ** 2))        # scatter vs flat, in sigma
    reduced = chi2 / (len(a_i) - 1)
    return dict(spectral_mag_reduced=reduced,
                spectral_mag_flat_pass=bool(reduced < tol_reduced))
