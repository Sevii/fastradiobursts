#!/usr/bin/env python3
"""W2.3 — build the empirical-null catalogs on the development split.

Restricts to development-split, non-quarantined proposals (the design set), then
builds the real / surrogate / xpair null χ²_copy distributions.
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
import yaml

from . import build


def _features(dev_props, manifest, split):
    """One row per dev burst: main component center + matching features + source."""
    main = (dev_props.sort_values("peak_a_snr", ascending=False)
            .groupby("tns_name").first().reset_index()[["tns_name", "center_a"]]
            .rename(columns={"center_a": "main_center"}))
    mcols = ["tns_name", "burst_width_s", "catalog_snr", "usable_bandwidth_mhz",
             "scattering_timescale_s"]
    feat = main.merge(manifest[mcols], on="tns_name", how="left") \
               .merge(split[["tns_name", "source_id"]], on="tns_name", how="left")
    return feat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--proposals", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--surrogate-bursts", type=int, default=300)
    ap.add_argument("--xpair-n", type=int, default=2000)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config))
    salt = cfg["split"]["salt"]
    props = pd.read_parquet(a.proposals)
    split = pd.read_parquet(a.split)
    man = pd.read_parquet(os.path.join(a.manifests, "observation_manifest.parquet"))
    tbdir = os.path.expanduser(a.tier_b_dir)

    dev = props[(props.split == "development") & (~props.quarantined)].copy()
    print(f"[nulls] dev non-quarantined proposals: {len(dev)} "
          f"over {dev.tns_name.nunique()} bursts", flush=True)
    os.makedirs(a.out_dir, exist_ok=True)

    real = build.build_real(dev, tbdir, cfg)
    real.to_parquet(os.path.join(a.out_dir, "null_catalog_real.parquet"), index=False)
    print(f"[nulls] real: {len(real)} scores", flush=True)

    sur = build.build_surrogate(dev, tbdir, cfg,
                                cfg["nulls"]["surrogate_methods"],
                                a.surrogate_bursts, salt)
    sur.to_parquet(os.path.join(a.out_dir, "null_catalog_surrogate.parquet"), index=False)
    print(f"[nulls] surrogate: {len(sur)} scores "
          f"({sur.construction.nunique()} methods)", flush=True)

    feat = _features(dev, man, split)
    xp = build.build_xpair(feat, tbdir, cfg, a.xpair_n, salt)
    xp.to_parquet(os.path.join(a.out_dir, "null_catalog_xpair.parquet"), index=False)
    print(f"[nulls] xpair: {len(xp)} scores", flush=True)

    alln = pd.concat([real, sur, xp], ignore_index=True)
    alln.to_parquet(os.path.join(a.out_dir, "null_catalog_all.parquet"), index=False)
    print("\n[nulls] delta_chi2 by construction (median / 95th / 99th):")
    for c, gg in alln.groupby(alln.construction.str.split(":").str[0]):
        q = gg.delta_chi2.quantile([0.5, 0.95, 0.99]).round(1).tolist()
        print(f"  {c:<10} n={len(gg):>6}  {q}")


if __name__ == "__main__":
    main()
