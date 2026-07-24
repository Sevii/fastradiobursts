#!/usr/bin/env python3
"""W3.0 — the PREDETERMINED full-criterion efficiency surface (prediction for G1).

WP2 froze a full-criterion *marginal* (0.79, at μ=0.5, oracle windows) and a
*copy-criterion* (μ, S/N) surface — but not a full-criterion, END-TO-END surface.
G1 ("recovery agrees with predicted efficiency") needs exactly that: the recovery
probability the frozen pipeline assigns to an injected copy at (μ, host S/N),
Tier-1 triage included, so it is comparable to the blind evaluation.

This regenerates it on the DEVELOPMENT split (already used in design — no test-set
contact) by injecting achromatic copies over the frozen grid and running the SAME
`run_frozen_chain` the blind evaluator uses. The result, `wp3_predicted_efficiency
.parquet`, is committed as the prediction BEFORE the hidden set is scored. It is a
prediction-generation step (frozen pipeline, zero new thresholds), not a new
analysis version.

NB: because this is end-to-end (Tier-1 included), the marginal here may be <= the
WP2 0.79 tier2-only oracle figure; that is expected and is the honest prediction.
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd
import yaml

from .. import tierb_io
from ..adverse import generators as gen
from ..injection import efficiency as eff
from ..tier1 import profile
from . import foundation
from .pipeline import run_frozen_chain


def build(dev_hosts, tbdir, ana_cfg, dt_bins, mu_grid, n_hosts, log_every=25):
    grid = [(dt, mu) for dt in dt_bins for mu in mu_grid]
    rows, used = [], 0
    for tns in dev_hosts.tns_name:
        if used >= n_hosts:
            break
        path = os.path.join(tbdir, f"{tns}_tierb.h5")
        if not os.path.exists(path):
            continue
        tb = tierb_io.load_tier_b(path)
        if tb["noise_failed"]:
            continue
        nt = tb["standardized"].shape[1]
        c = int(np.argmax(profile.build_profile(tb)["I"]))
        hp = dev_hosts[dev_hosts.tns_name == tns].iloc[0]
        used += 1
        for dt, mu in grid:
            if c + dt >= nt - 5 or c - 5 < 0:
                continue
            tb2 = gen.inject(tb, c, dt, mu, "achromatic_copy", None)
            d = run_frozen_chain(tb2, ana_cfg)
            rows.append(dict(tns_name=tns, dt_bins=dt, mu=mu,
                             recovered=bool(d["is_candidate"]),
                             copy_ok=bool(d["copy_ok_any"]),
                             delta_chi2=d["best_delta_chi2"], ncc=d["best_ncc"],
                             reduced_chi2=d["best_reduced_chi2"],
                             n_pass=d["best_n_pass"],
                             host_snr=float(hp.catalog_snr),
                             host_width_s=float(hp.burst_width_s),
                             host_bandwidth_mhz=float(hp.usable_bandwidth_mhz)))
        if used % log_every == 0:
            print(f"[predict] {used}/{n_hosts} hosts, {len(rows)} injections", flush=True)
    return pd.DataFrame(rows)


def snr_quartiles(host_snr):
    """S/N quartile labels, robust to few distinct values (drops empty edges)."""
    binned = pd.qcut(host_snr, 4, duplicates="drop")
    codes = binned.cat.codes                              # 0..(nbins-1), ordered low->high
    return codes.map(lambda c: f"Q{c + 1}" if c >= 0 else "NA")


def surface(df):
    """Full-criterion ε(μ, host S/N quartile) with Wilson CIs (the prediction)."""
    df = df.copy()
    df["host_snr_bin"] = snr_quartiles(df.host_snr)
    g = df.groupby(["mu", "host_snr_bin"]).recovered.agg(["sum", "count"]).reset_index()
    g["efficiency"] = g["sum"] / g["count"]
    ci = g.apply(lambda r: eff.wilson(int(r["sum"]), int(r["count"])), axis=1,
                 result_type="expand")
    g["ci_lo"], g["ci_hi"] = ci[1].round(4), ci[2].round(4)
    return df, g.rename(columns={"sum": "recovered", "count": "n"})


def main():
    ap = argparse.ArgumentParser(description="W3.0 — predicted efficiency surface (dev)")
    ap.add_argument("--wp3-config", required=True)
    ap.add_argument("--analysis-config", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--split", required=True)
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-hosts", type=int, default=150)
    a = ap.parse_args()

    wp3 = foundation.load_wp3_config(a.wp3_config)
    foundation.assert_freeze_contract(wp3, os.path.expanduser(a.repo_root))
    ana = yaml.safe_load(open(a.analysis_config))

    split = pd.read_parquet(os.path.expanduser(a.split))
    man = pd.read_parquet(os.path.join(os.path.expanduser(a.manifests),
                                       "observation_manifest.parquet"))
    mcols = ["tns_name", "catalog_snr", "burst_width_s", "usable_bandwidth_mhz",
             "n_subbursts"]
    single = man[mcols][man.n_subbursts.fillna(1) <= 1]
    dev = split[(split.split == "development") & (~split.quarantined)] \
        .merge(single, on="tns_name")

    inj = ana["injection"]
    df = build(dev, os.path.expanduser(a.tier_b_dir), ana,
               inj["dt_bins"], inj["mu"], a.n_hosts)
    df, surf = surface(df)

    outp = os.path.expanduser(a.out)
    os.makedirs(os.path.dirname(os.path.abspath(outp)), exist_ok=True)
    df.to_parquet(outp, index=False)
    surf.to_parquet(outp.replace(".parquet", "_surface.parquet"), index=False)

    print(f"[predict] {len(df)} dev injections -> {outp}")
    print("\nPredicted full-criterion efficiency by μ:")
    print(eff.efficiency_by(df, "mu").to_string(index=False))
    print(f"\nMarginal predicted efficiency: {df.recovered.mean():.3f} "
          f"(n={len(df)})")
    print("\nε(μ, host S/N) surface:")
    print(surf.pivot(index="mu", columns="host_snr_bin", values="efficiency")
          .round(2).to_string())


if __name__ == "__main__":
    main()
