#!/usr/bin/env python3
"""W2.6 — development injection campaign -> detection-efficiency surface.

Inject achromatic delayed copies across a Δt × μ grid into real single-component
dev hosts (real off-pulse), score with χ²_copy, record host params + scores ->
injection_recovery.parquet. Deterministic (achromatic injection has no RNG).
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd
import yaml

from .. import tierb_io
from ..adverse import generators as gen
from ..copy import score as scoremod
from ..tier1 import profile
from . import efficiency as eff

DT_BINS = [3, 4, 5, 6, 8, 10, 13, 17, 22, 30, 40]      # dense near threshold
MU = [0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 0.9]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-hosts", type=int, default=150)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config))
    split = pd.read_parquet(a.split)
    man = pd.read_parquet(os.path.join(a.manifests, "observation_manifest.parquet"))
    tbdir = os.path.expanduser(a.tier_b_dir)
    mcols = ["tns_name", "catalog_snr", "burst_width_s", "scattering_timescale_s",
             "usable_bandwidth_mhz", "n_subbursts"]
    feat = man[mcols].copy()
    single = feat[feat.n_subbursts.fillna(1) <= 1]
    pool = split[(split.split == "development") & (~split.quarantined)] \
        .merge(single, on="tns_name")

    rng_grid = [(dt, mu) for dt in DT_BINS for mu in MU]
    rows, used = [], 0
    for tns in list(pool.tns_name):
        if used >= a.n_hosts:
            break
        path = os.path.join(tbdir, f"{tns}_tierb.h5")
        if not os.path.exists(path):
            continue
        tb = tierb_io.load_tier_b(path)
        if tb["noise_failed"]:
            continue
        nt = tb["standardized"].shape[1]
        c = int(np.argmax(profile.build_profile(tb)["I"]))
        hp = pool[pool.tns_name == tns].iloc[0]
        used += 1
        for dt, mu in rng_grid:
            if c + dt >= nt - 5 or c - 5 < 0:
                continue
            tb2 = gen.inject(tb, c, dt, mu, "achromatic_copy", None)
            r = scoremod.score_proposal(tb2, c, c + dt, cfg)
            rows.append(dict(tns_name=tns, dt_bins=dt, mu=mu,
                             delay_ms=r["delay_ms"], delta_chi2=r["delta_chi2"],
                             ncc=r["ncc"], reduced_chi2=r["reduced_chi2"],
                             best_a=r["best_a"], host_snr=float(hp.catalog_snr),
                             host_width_s=float(hp.burst_width_s),
                             host_bandwidth_mhz=float(hp.usable_bandwidth_mhz)))
        if used % 25 == 0:
            print(f"[inject] {used}/{a.n_hosts} hosts, {len(rows)} injections", flush=True)

    df = pd.DataFrame(rows)
    # host S/N quartile bins for the efficiency surface
    df["host_snr_bin"] = pd.qcut(df.host_snr, 4, labels=["Q1", "Q2", "Q3", "Q4"],
                                 duplicates="drop")
    os.makedirs(os.path.dirname(os.path.abspath(os.path.expanduser(a.out))), exist_ok=True)
    df.to_parquet(os.path.expanduser(a.out), index=False)
    print(f"\n[inject] {used} hosts, {len(df)} injections -> {a.out}")
    print("\nε by magnification μ:")
    print(eff.efficiency_by(df, "mu").to_string(index=False))
    print("\nε by host S/N quartile:")
    print(eff.efficiency_by(df, "host_snr_bin").to_string(index=False))
    print("\nε(μ, S/N) surface (recovered/n):")
    s = eff.surface(df)
    piv = s.pivot(index="mu", columns="host_snr_bin", values="efficiency")
    print(piv.round(2).to_string())


if __name__ == "__main__":
    main()
