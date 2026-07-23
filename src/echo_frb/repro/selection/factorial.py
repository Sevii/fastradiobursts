#!/usr/bin/env python3
"""W1.4c — light-curve x ACF factorial to attribute literal/clean-room divergence.

For each probed FRB we cross two light curves with two spike-detectors:
  LC_lit  = authors' process_data_ts(...)['ts']          (their preprocessing)
  LC_cr   = clean-room build_lightcurve(TierB)            (our preprocessing)
  ACF_lit = authors' compute_autocorr_with_spikes(...)    (their detector)
  ACF_cr  = clean-room normalized_acf + find_spikes       (our detector)

A spike is "near expected" if a detected lag falls within +-2 ms of the FRB's
expected delay (the literal-detected delay). Differences ACROSS light-curve rows
=> preprocessing-driven; ACROSS detector columns => algorithm/threshold-driven.

Run in the microfrb venv (needs the authors' deps incl. colossus). It is a
post-hoc measurement probe — the frozen clean-room build is not modified.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd
import yaml

MATCH_TOL_MS = 2.0


def _acf_lit_spikes(ts, mpb):
    from modules import compute_autocorr_with_spikes
    r = compute_autocorr_with_spikes(
        ts, smooth_sigma=3, threshold=3, min_lag=1, positive_lags_only=True,
        detect_spikes=True, return_details=True, demean=True)
    lags = r["spike_result"]["spike_lags"]
    return [float(l) * mpb for l in lags]


def _acf_cr_spikes(I, mpb, cfg):
    from echo_frb.repro.cleanroom import acf
    max_lag = int(min(len(I) - 1, round(cfg["acf"]["max_lag_ms"] / mpb)))
    C = acf.normalized_acf(I, max_lag)
    sp = acf.find_spikes(C, cfg["acf"]["smoothing_sigma"],
                         cfg["acf"]["spike_nsigma"], cfg["acf"]["min_lag_bins"])
    return [s["lag_bins"] * mpb for s in sp["spikes"]]


def _lc_lit(frb, tier_a_dir):
    from modules import read_frb_dynamic_spectrum, process_data_ts
    path = os.path.join(tier_a_dir, f"{frb}_stokesi_dynamic_spectrum.h5")
    raw = read_frb_dynamic_spectrum(path)
    proc = process_data_ts(raw, f_down=32, t_down=1, rfi_factor=3)
    return np.asarray(proc["ts"], dtype=np.float64)


def _lc_cr(frb, tier_b_dir):
    from echo_frb.repro.cleanroom import lightcurve
    tb = lightcurve.load_tier_b(os.path.join(tier_b_dir, f"{frb}_tierb.h5"))
    I, meta = lightcurve.build_lightcurve(tb)
    return np.asarray(I, dtype=np.float64), float(meta["res_time"])


def _near(spikes_ms, expected_ms):
    if expected_ms is None or not np.isfinite(expected_ms):
        return bool(len(spikes_ms) > 0)  # no expectation: any spike counts
    return any(abs(s - expected_ms) <= MATCH_TOL_MS for s in spikes_ms)


def run(frbs, expected, tier_a_dir, tier_b_dir, cfg):
    rows = []
    for frb in frbs:
        exp = expected.get(frb)
        # build both light curves once
        try:
            lc_l = _lc_lit(frb, tier_a_dir)
        except Exception as e:  # noqa: BLE001
            lc_l = None; err_l = f"{type(e).__name__}: {e}"
        try:
            lc_c, res_time = _lc_cr(frb, tier_b_dir)
            mpb_c = res_time * 1e3
        except Exception as e:  # noqa: BLE001
            lc_c = None; mpb_c = 0.983; err_c = f"{type(e).__name__}: {e}"
        mpb_l = 0.98  # authors' fixed time_step_ms

        def cell(lc, detector, mpb):
            if lc is None:
                return None
            try:
                return (_acf_lit_spikes(lc, mpb) if detector == "lit"
                        else _acf_cr_spikes(lc, mpb, cfg))
            except Exception:  # noqa: BLE001
                return None

        cells = {
            "LClit_ACFlit": cell(lc_l, "lit", mpb_l),
            "LClit_ACFcr":  cell(lc_l, "cr",  mpb_l),
            "LCcr_ACFlit":  cell(lc_c, "lit", mpb_c),
            "LCcr_ACFcr":   cell(lc_c, "cr",  mpb_c),
        }
        for name, spikes in cells.items():
            rows.append(dict(
                frb_name=frb, expected_ms=exp, cell=name,
                lc="LClit" if name.startswith("LClit") else "LCcr",
                acf="ACFlit" if name.endswith("ACFlit") else "ACFcr",
                spikes_ms=[round(s, 3) for s in spikes] if spikes else [],
                n_spikes=(len(spikes) if spikes is not None else -1),
                near_expected=(_near(spikes, exp) if spikes is not None else False),
            ))
    return pd.DataFrame(rows)


def attribute(df):
    """Per FRB, read the 2x2 near_expected grid and attribute the divergence."""
    out = []
    for frb, g in df.groupby("frb_name"):
        grid = {r.cell: bool(r.near_expected) for r in g.itertuples()}
        ll = grid.get("LClit_ACFlit"); lc = grid.get("LClit_ACFcr")
        cl = grid.get("LCcr_ACFlit"); cc = grid.get("LCcr_ACFcr")
        # effect of swapping LC (hold ACF): rows differ?
        lc_effect = (ll != cl) or (lc != cc)
        # effect of swapping ACF (hold LC): cols differ?
        acf_effect = (ll != lc) or (cl != cc)
        if lc_effect and not acf_effect:
            cause = "PREPROCESSING"
        elif acf_effect and not lc_effect:
            cause = "ALGORITHM"
        elif lc_effect and acf_effect:
            cause = "MIXED"
        else:
            cause = "AGREE"  # all four cells identical
        out.append(dict(frb_name=frb,
                        LClit_ACFlit=ll, LClit_ACFcr=lc,
                        LCcr_ACFlit=cl, LCcr_ACFcr=cc,
                        cause=cause))
    return pd.DataFrame(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frbs", required=True, help="comma list or path to a txt (one per line)")
    ap.add_argument("--expected", default="", help="comma list frb:ms (optional)")
    ap.add_argument("--tier-a-dir", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--microfrb-run", required=True, help="path to microfrb_run (for `modules`)")
    ap.add_argument("--src", required=True, help="repo src/ (for echo_frb)")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    sys.path.insert(0, a.microfrb_run)
    sys.path.insert(0, a.src)

    frbs = (open(a.frbs).read().split() if os.path.exists(a.frbs)
            else [x.strip() for x in a.frbs.split(",") if x.strip()])
    expected = {}
    for tok in a.expected.split(","):
        if ":" in tok:
            k, v = tok.split(":"); expected[k.strip()] = float(v)
    cfg = yaml.safe_load(open(a.config))

    df = run(frbs, expected, os.path.expanduser(a.tier_a_dir),
             os.path.expanduser(a.tier_b_dir), cfg)
    att = attribute(df)
    os.makedirs(a.out_dir, exist_ok=True)
    df.to_parquet(os.path.join(a.out_dir, "decomposition_factorial.parquet"), index=False)
    att.to_parquet(os.path.join(a.out_dir, "decomposition_attribution.parquet"), index=False)
    print("=== per-cell near_expected ===")
    print(df[["frb_name", "cell", "n_spikes", "near_expected", "spikes_ms"]].to_string(index=False))
    print("\n=== attribution (2x2 near_expected grid) ===")
    print(att.to_string(index=False))
