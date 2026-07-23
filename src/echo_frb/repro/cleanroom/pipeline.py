#!/usr/bin/env python3
"""Per-FRB clean-room pipeline: dynamic spectrum -> candidate verdict.

Orchestrates Steps 1-9 of PAPER_SPEC.md (Zhou et al. 2026). All thresholds come
from cleanroom_config.yaml. Fully deterministic (the K-S bootstrap RNG is seeded
from the config), so the same input yields an identical content_sha256.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

from . import acf, drift_ks, hardness, lightcurve, peaks


def _canonical(result):
    """Stable, rounded serialization of the numeric verdict for hashing."""
    def r(x, nd=6):
        if x is None or (isinstance(x, float) and not np.isfinite(x)):
            return None
        return round(float(x), nd)
    return json.dumps(dict(
        frb_name=result["frb_name"],
        spike_delays_ms=[r(v) for v in result["spike_delays_ms"]],
        matched_pairs=[[int(a), int(b)] for a, b in result["matched_pairs"]],
        best_delay_ms=r(result["best_delay_ms"]),
        mag_ratio=r(result["mag_ratio"]),
        is_candidate=bool(result["is_candidate"]),
        has_drift=bool(result["has_drift"]),
        n_components=int(result["n_components"]),
    ), sort_keys=True)


def content_sha256(I, result, config_hash):
    """Determinism hash over the light curve + verdict + config."""
    h = hashlib.sha256()
    arr = np.ascontiguousarray(np.asarray(I, dtype=np.float64))
    h.update(b"lightcurve")
    h.update(np.asarray(arr.shape, dtype=np.int64).tobytes())
    h.update(arr.tobytes())
    h.update(_canonical(result).encode())
    h.update(str(config_hash).encode())
    return h.hexdigest()


def _empty_result(frb_name, note):
    return dict(
        frb_name=frb_name,
        spike_delays_ms=[],
        matched_pairs=[],
        best_delay_ms=float("nan"),
        mag_ratio=float("nan"),
        is_candidate=False,
        has_drift=False,
        n_components=0,
        n_spikes=0,
        n_matched=0,
        best_secondary_psnr=float("nan"),
        ks_d_max=float("nan"),
        ks_d_upp=float("nan"),
        n_usable_channels=0,
        note=note,
    )


def run_frb(tb, frb_name, cfg):
    """Run the full pipeline on a loaded Tier B dict. Returns a result dict.

    Does not add config_hash/content_sha256/code_commit — the caller stamps those
    (content_sha256 via content_sha256(I, result, config_hash)).
    """
    # --- guard: unusable inputs ---------------------------------------------
    if bool(tb["attrs"].get("noise_failed", False)):
        res = _empty_result(frb_name, "noise_failed")
        res["_lightcurve"] = np.zeros(1)
        return res

    I, meta = lightcurve.build_lightcurve(tb)
    if meta["n_usable_channels"] == 0 or meta["sigma_noise"] <= 0:
        res = _empty_result(frb_name, "no_usable_channels")
        res["_lightcurve"] = I
        return res

    mpb = lightcurve.ms_per_bin(meta["res_time"])
    nt = I.size

    # --- Steps 2-4: ACF + spikes --------------------------------------------
    max_lag = int(min(nt - 1, round(cfg["acf"]["max_lag_ms"] / mpb)))
    C = acf.normalized_acf(I, max_lag)
    sp = acf.find_spikes(C, cfg["acf"]["smoothing_sigma"],
                         cfg["acf"]["spike_nsigma"], cfg["acf"]["min_lag_bins"])
    spikes = sp["spikes"]
    spike_delays_ms = [s["lag_bins"] * mpb for s in spikes]

    # --- Step 5: peaks + matching -------------------------------------------
    pk = peaks.detect_peaks(I, meta, cfg["peaks"]["detect_snr"],
                            cfg["peaks"]["min_separation_bins"])
    matched = peaks.match_spikes_to_peaks(spikes, pk, mpb,
                                          cfg["peaks"]["match_tol_ms"])
    # unique matched (lead,trail) pairs for reporting
    seen = set()
    matched_pairs = []
    for m in matched:
        key = (m["lead_bin"], m["trail_bin"])
        if key not in seen:
            seen.add(key)
            matched_pairs.append([int(m["lead_bin"]), int(m["trail_bin"])])

    # --- Steps 6-8: cuts, K-S drift, hardness on each matched pair -----------
    valid_chan = (np.asarray(tb["channel_usable"], dtype=bool)
                  & np.isfinite(np.asarray(tb["robust_std"], dtype=np.float64)))
    rng = np.random.default_rng(int(cfg["ks"]["bootstrap_seed"]))
    hw0 = int(cfg["peaks"]["component_halfwidth_bins"])
    std = np.asarray(tb["standardized"], dtype=np.float64)

    evaluated = []
    for m in matched:
        cuts_ok, flags = peaks.apply_selection_cuts(
            m, pk, cfg["peaks"]["secondary_psnr_min"])
        hw = min(hw0, max(1, m["sep_bins"] // 2))
        rf, fl, ft = peaks.magnification_ratio(I, meta["mu_off"], m, hw0)
        rec = dict(match=m, cuts_ok=cuts_ok, flags=flags, hw=hw,
                   mag_ratio=rf, has_drift=False, ks=None,
                   hardness_ok=False, tested=False)
        if cuts_ok:
            si, ni, oki = drift_ks.component_spectrum(
                std, tb["robust_std"], valid_chan, m["lead_bin"], hw,
                cfg["ks"]["n_f"])
            sj, nj, okj = drift_ks.component_spectrum(
                std, tb["robust_std"], valid_chan, m["trail_bin"], hw,
                cfg["ks"]["n_f"])
            ok = oki & okj
            ks = drift_ks.drift_test(si, ni, sj, nj, ok, cfg["ks"]["n_f"],
                                     cfg["ks"], rng)
            h_ok, _hd = hardness.hardness_consistent(
                std, tb["robust_std"], valid_chan, m["lead_bin"],
                m["trail_bin"], hw, cfg["hardness"]["n_bands"],
                cfg["hardness"]["consistency_nsigma"])
            rec.update(ks=ks, has_drift=ks["has_drift"], hardness_ok=h_ok,
                       tested=True)
        evaluated.append(rec)

    # --- Step 9: verdict + best-pair selection ------------------------------
    def trail_psnr(rec):
        return rec["match"]["trail"]["psnr"]

    candidates = [r for r in evaluated
                  if r["cuts_ok"] and r["tested"]
                  and not r["has_drift"] and r["hardness_ok"]]
    cuts_pass = [r for r in evaluated if r["cuts_ok"] and r["tested"]]

    if candidates:
        best = max(candidates, key=trail_psnr)
        is_candidate = True
    elif cuts_pass:
        best = max(cuts_pass, key=trail_psnr)
        is_candidate = False
    elif evaluated:
        best = max(evaluated, key=lambda r: r["match"]["spike"]["amplitude"])
        is_candidate = False
    else:
        best = None
        is_candidate = False

    res = dict(
        frb_name=frb_name,
        spike_delays_ms=[float(x) for x in spike_delays_ms],
        matched_pairs=matched_pairs,
        best_delay_ms=float(best["match"]["delay_ms"]) if best else float("nan"),
        mag_ratio=float(best["mag_ratio"]) if best else float("nan"),
        is_candidate=bool(is_candidate),
        has_drift=bool(best["has_drift"]) if best else False,
        n_components=int(len(pk)),
        n_spikes=int(len(spikes)),
        n_matched=int(len(matched_pairs)),
        best_secondary_psnr=(float(best["match"]["trail"]["psnr"])
                             if best else float("nan")),
        ks_d_max=(float(best["ks"]["d_max"]) if best and best["ks"]
                  else float("nan")),
        ks_d_upp=(float(best["ks"]["d_upp"]) if best and best["ks"]
                  else float("nan")),
        n_usable_channels=int(meta["n_usable_channels"]),
        note="ok",
    )
    res["_lightcurve"] = I
    return res
