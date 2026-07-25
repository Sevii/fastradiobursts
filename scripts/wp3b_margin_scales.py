#!/usr/bin/env python3
"""W3b.2 — dump dev per-proposal diagnostics and FREEZE the margin scales s_k.

The margin T = min_k (x_k - c_k)/s_k needs the s_k prespecified, or "weakest
gate" is meaningless: with unit scales the minimum is taken by whichever gate
happens to have the smallest natural spread, not by the gate the proposal is
actually closest to failing.

s_k is the robust spread of diagnostic k across DEVELOPMENT proposals — the
scale on which a null proposal's value for that gate naturally varies:

    s_k = 1.4826 * median(|x_k - median(x_k)|)        (MAD -> Gaussian sigma)

measured in the same transformed space the margin uses (log10 for delta_chi2),
over the population where the gate can actually bind: all proposals for the copy
gates, copy-surviving proposals for the robustness gates (v1 never evaluates the
others). Falls back to IQR/1.349, then to 1.0, if a MAD degenerates to zero.

The robustness VOTE keeps s = 1.0 by prespecification: one vote is already the
natural, interpretable unit and its MAD is frequently 0.

This is a DEV-only measurement, frozen once into config/wp2_analysis_config_v2.yaml
and never re-tuned after the validation dry run. Because scales are positive,
they cannot change any v1 decision (tests/test_wp3b_margin.py) — they set only
the ranking among proposals, which is what the max-statistic calibration consumes.

  PYTHONPATH=src .venv/bin/python scripts/wp3b_margin_scales.py \
      --config config/wp2_analysis_config.yaml \
      --split ~/frb_catalog2_prep/wp2/source_split.parquet \
      --tier-b-dir ~/frb_catalog2_prep/tier_b_standardized \
      --workers 24 --out-dir ~/frb_catalog2_prep/wp3b
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import yaml

from echo_frb.search import tierb_io
from echo_frb.search.margin import chain as mchain, statistic as ms

_CFG = None

# gate -> (column in the proposal dump, transform, population)
#   "all"  = every proposal;  "copy_ok" = only proposals v1 carried to robustness
SCALE_SPEC = {
    "log10_delta_chi2":       ("delta_chi2", "log10", "all"),
    "ncc":                    ("ncc", None, "all"),
    "reduced_chi2":           ("reduced_chi2", None, "all"),
    "delay_spread_bins":      ("delay_spread_bins", None, "copy_ok"),
    "mag_rel_spread":         ("mag_rel_spread", None, "copy_ok"),
    "spectral_mag_reduced":   ("spectral_mag_reduced", None, "copy_ok"),
    "residual_reduced_chi2":  ("residual_reduced_chi2", None, "copy_ok"),
    "leave_band_out_min_frac": ("leave_band_out_min_frac", None, "copy_ok"),
    "resolution_ncc_spread":  ("resolution_ncc_spread", None, "copy_ok"),
    "window_ncc_spread":      ("window_ncc_spread", None, "copy_ok"),
}
PRESPECIFIED = {"n_pass_vote": 1.0}          # one robustness vote — not estimated


def _init(cfg):
    global _CFG
    _CFG = cfg


def _one(args):
    tns, path = args
    try:
        tb = tierb_io.load_tier_b(path)
        if tb["noise_failed"]:
            return []
        _, props = mchain.run_margin_chain(tb, _CFG, return_proposals=True)
    except Exception:
        return []
    return [dict(tns_name=tns, **p) for p in props]


def robust_scale(x):
    """1.4826*MAD, degrading to IQR/1.349 then 1.0. Returns (scale, method, n)."""
    v = np.asarray(x, float)
    v = v[np.isfinite(v)]
    if v.size < 8:
        return 1.0, "insufficient_n", int(v.size)
    mad = float(np.median(np.abs(v - np.median(v))))
    if mad > 0:
        return 1.4826 * mad, "mad", int(v.size)
    iqr = float(np.subtract(*np.percentile(v, [75, 25])))
    if iqr > 0:
        return iqr / 1.349, "iqr", int(v.size)
    return 1.0, "degenerate", int(v.size)


def compute_scales(props):
    rows, scales = [], {}
    for gate, (col, tf, pop) in SCALE_SPEC.items():
        sub = props if pop == "all" else props[props.copy_ok]
        x = sub[col].to_numpy(float)
        if tf == "log10":
            with np.errstate(invalid="ignore", divide="ignore"):
                x = np.where(x > 0, np.log10(np.where(x > 0, x, np.nan)), np.nan)
        s, method, n = robust_scale(x)
        scales[gate] = round(float(s), 6)
        fin = x[np.isfinite(x)]
        rows.append(dict(gate=gate, column=col, population=pop, n=n, method=method,
                         scale=round(float(s), 6),
                         median=round(float(np.median(fin)), 6) if fin.size else np.nan,
                         p01=round(float(np.percentile(fin, 1)), 6) if fin.size else np.nan,
                         p99=round(float(np.percentile(fin, 99)), 6) if fin.size else np.nan))
    for gate, s in PRESPECIFIED.items():
        scales[gate] = s
        rows.append(dict(gate=gate, column="n_pass", population="copy_ok", n=-1,
                         method="prespecified", scale=s, median=np.nan,
                         p01=np.nan, p99=np.nan))
    return scales, pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--split-name", default="development")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config))
    split = pd.read_parquet(os.path.expanduser(a.split))
    tbdir = os.path.expanduser(a.tier_b_dir)
    sel = split[(split.split == a.split_name) & (~split.quarantined)]
    tasks = [(t, os.path.join(tbdir, f"{t}_tierb.h5")) for t in sel.tns_name]
    tasks = [t for t in tasks if os.path.exists(t[1])]
    print(f"[W3b.2] {len(tasks)} {a.split_name} bursts, {a.workers} workers")

    rows = []
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init,
                             initargs=(cfg,)) as ex:
        for i, r in enumerate(ex.map(_one, tasks, chunksize=8)):
            rows.extend(r)
            if (i + 1) % 500 == 0:
                print(f"[W3b.2] {i + 1}/{len(tasks)} bursts, "
                      f"{len(rows)} proposals", flush=True)

    props = pd.DataFrame(rows)
    outdir = os.path.expanduser(a.out_dir)
    os.makedirs(outdir, exist_ok=True)
    dump = os.path.join(outdir, f"proposals_{a.split_name}.parquet")
    props.to_parquet(dump, index=False)

    scales, table = compute_scales(props)
    table.to_parquet(os.path.join(outdir, "margin_scales.parquet"), index=False)
    frag = yaml.safe_dump({"margin": {"scales": scales}}, sort_keys=True)
    open(os.path.join(outdir, "margin_scales.yaml"), "w").write(frag)

    print(f"\n[W3b.2] {len(props)} proposals from {props.tns_name.nunique()} bursts "
          f"({int(props.copy_ok.sum())} cleared the copy gates, "
          f"{int(props.full_ok_v1.sum())} pass v1 in full)")
    print(table.to_string(index=False))
    print(f"\n[W3b.2] proposals -> {dump}")
    print(f"[W3b.2] scales    -> {os.path.join(outdir, 'margin_scales.yaml')}\n")
    print(frag)
    missing = set(ms.DEFAULT_SCALES) - set(scales)
    if missing:
        raise SystemExit(f"scales missing for gates: {sorted(missing)}")


if __name__ == "__main__":
    main()
