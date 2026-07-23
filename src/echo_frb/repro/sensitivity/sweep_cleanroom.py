#!/usr/bin/env python3
"""W1.5 — clean-room spike-threshold sweep (closes the W1.4 loop).

Re-runs the clean-room over the 340-set on Tier B for several `spike_nsigma`
values, to quantify how many literal candidates our detector recovers as its
threshold loosens. Reuses the frozen clean-room pipeline unchanged; only the
config's acf.spike_nsigma is overridden per run.
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from echo_frb.repro.cleanroom import run as cr_run


def run_sweep(config_path, target_csv, tier_b_dir, nsigmas):
    base = cr_run.load_config(config_path)
    names = list(pd.read_csv(target_csv)["tns_name"])
    tier_b_dir = os.path.expanduser(tier_b_dir)
    rows = []
    for ns in nsigmas:
        cfg = {**base, "acf": {**base["acf"], "spike_nsigma": ns}}
        tag = f"cr_nsigma_{ns}"
        ncand = 0
        for tns in names:
            r = cr_run.process_one(tns, tier_b_dir, cfg, f"{cfg['_config_hash']}:{ns}",
                                   "sweep")
            is_c = bool(r.get("is_candidate", False))
            ncand += int(is_c)
            rows.append(dict(config=tag, frb_name=tns, is_candidate=is_c,
                             has_drift=bool(r.get("has_drift", False)),
                             n_spikes=int(r.get("n_spikes", 0) or 0),
                             status=str(r.get("note", "ok"))))
        print(f"[{tag}] candidates={ncand}", flush=True)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--nsigmas", default="2,2.5,3")
    a = ap.parse_args()
    ns = [float(x) for x in a.nsigmas.split(",")]
    df = run_sweep(a.config, a.target, a.tier_b_dir, ns)
    os.makedirs(a.out_dir, exist_ok=True)
    out = os.path.join(a.out_dir, "sweep_cleanroom_long.parquet")
    df.to_parquet(out, index=False)
    print(f"[sweep_cleanroom] wrote {out}: {len(df)} rows")


if __name__ == "__main__":
    main()
