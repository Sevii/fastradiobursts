#!/usr/bin/env python3
"""W2.1 — batch Tier-1 scan over every eligible burst -> tier1_proposals.parquet.

Runs on all eligible Tier B products (the source split from W2.0 defines the set
and carries split + quarantine flags, which are attached to each proposal but do
NOT gate the scan — triage is catalog-wide). Quarantine/split govern later
threshold DESIGN, not the scan itself.
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
import yaml

from .. import tierb_io
from . import scan as scanmod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", required=True, help="source_split.parquet from W2.0")
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config))
    split = pd.read_parquet(a.split)
    if a.limit:
        split = split.head(a.limit)
    tbdir = os.path.expanduser(a.tier_b_dir)
    smap = split.set_index("tns_name")[["split", "quarantined"]].to_dict("index")

    rows, n_ok, n_prop_bursts, n_fail = [], 0, 0, 0
    names = list(split.tns_name)
    for i, tns in enumerate(names, 1):
        path = os.path.join(tbdir, f"{tns}_tierb.h5")
        if not os.path.exists(path):
            n_fail += 1; continue
        try:
            tb = tierb_io.load_tier_b(path)
            if tb["noise_failed"]:
                n_ok += 1; continue
            props, _ = scanmod.scan_burst(tb, cfg)
            n_ok += 1
            if props:
                n_prop_bursts += 1
                meta = smap.get(tns, {"split": "unknown", "quarantined": False})
                for r in props:
                    r.update(split=meta["split"], quarantined=bool(meta["quarantined"]))
                    rows.append(r)
        except Exception as e:  # noqa: BLE001
            n_fail += 1
            print(f"  {tns}: error {type(e).__name__}: {e}", flush=True)
        if i % 500 == 0:
            print(f"[tier1] {i}/{len(names)}  proposals={len(rows)}", flush=True)

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(os.path.abspath(os.path.expanduser(a.out))), exist_ok=True)
    df.to_parquet(os.path.expanduser(a.out), index=False)
    print(f"\n[tier1] scanned={n_ok} bursts, {n_prop_bursts} with >=1 proposal, "
          f"{len(df)} proposals, {n_fail} missing/failed")
    print(f"[tier1] wrote {a.out}")
    if len(df):
        print(df.kind.value_counts().to_string())


if __name__ == "__main__":
    main()
