#!/usr/bin/env python3
"""Batch CLI — run the clean-room pipeline over the 340-set, write scores parquet.

Usage (on popos, with the project venv):
  python -m echo_frb.repro.cleanroom.run \
      --config   src/echo_frb/repro/cleanroom/cleanroom_config.yaml \
      --target   src/echo_frb/repro/cleanroom/target_340_set.csv \
      --tier-b-dir ~/frb_catalog2_prep/tier_b_standardized \
      --out      ~/frb_catalog2_prep/wp1_repro/cleanroom_run/cleanroom_scores.parquet

Every FRB is processed uniformly; none is special-cased. FRBs whose Tier B file
is missing or whose processing raises are recorded with a `note`/`error`, not
crashed over.
"""
from __future__ import annotations

import argparse
import hashlib
import os

import pandas as pd
import yaml

from . import pipeline

OUT_COLUMNS = [
    "frb_name", "spike_delays_ms", "matched_pairs", "best_delay_ms",
    "mag_ratio", "is_candidate", "has_drift", "n_components",
    "config_hash", "content_sha256", "code_commit",
    # diagnostics (extra, not required by the neutral schema)
    "n_spikes", "n_matched", "best_secondary_psnr", "ks_d_max", "ks_d_upp",
    "n_usable_channels", "note",
]


def load_config(path):
    cfg = yaml.safe_load(open(path))
    cfg["_config_hash"] = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    return cfg


def process_one(tns, tier_b_dir, cfg, config_hash, code_commit):
    path = os.path.join(tier_b_dir, f"{tns}_tierb.h5")
    if not os.path.exists(path):
        row = pipeline._empty_result(tns, "missing_tier_b")
        row.pop("_lightcurve", None)
        row.update(config_hash=config_hash, content_sha256="", code_commit=code_commit)
        return row
    try:
        tb = pipeline.lightcurve.load_tier_b(path)
        res = pipeline.run_frb(tb, tns, cfg)
        I = res.pop("_lightcurve")
        csha = pipeline.content_sha256(I, res, config_hash)
        res.update(config_hash=config_hash, content_sha256=csha,
                   code_commit=code_commit)
        return res
    except Exception as e:  # noqa: BLE001
        row = pipeline._empty_result(tns, f"error:{type(e).__name__}: {e}")
        row.pop("_lightcurve", None)
        row.update(config_hash=config_hash, content_sha256="", code_commit=code_commit)
        return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--code-commit", default=os.environ.get("ECHO_FRB_COMMIT", "unknown"))
    ap.add_argument("--limit", type=int, default=0, help="process only first N (debug)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    config_hash = cfg["_config_hash"]
    tier_b_dir = os.path.expanduser(args.tier_b_dir)
    targets = pd.read_csv(args.target)
    names = list(targets["tns_name"])
    if args.limit:
        names = names[: args.limit]

    print(f"[cleanroom] {len(names)} FRBs  config_hash={config_hash}  "
          f"commit={args.code_commit}", flush=True)
    rows = []
    for i, tns in enumerate(names, 1):
        row = process_one(tns, tier_b_dir, cfg, config_hash, args.code_commit)
        rows.append(row)
        if i % 25 == 0 or i == len(names):
            ncand = sum(1 for r in rows if r.get("is_candidate"))
            print(f"[cleanroom] {i}/{len(names)}  candidates so far={ncand}",
                  flush=True)

    df = pd.DataFrame(rows)
    for c in OUT_COLUMNS:
        if c not in df:
            df[c] = None
    df = df[OUT_COLUMNS]
    os.makedirs(os.path.dirname(os.path.abspath(os.path.expanduser(args.out))),
                exist_ok=True)
    out = os.path.expanduser(args.out)
    df.to_parquet(out, index=False)

    cand = df[df.is_candidate]
    nerr = int(df.note.astype(str).str.startswith("error").sum())
    nmiss = int((df.note == "missing_tier_b").sum())
    nfail = int((df.note == "noise_failed").sum())
    print(f"\n[cleanroom] wrote {out}: {len(df)} rows")
    print(f"[cleanroom] candidates={len(cand)}  errors={nerr}  "
          f"missing={nmiss}  noise_failed={nfail}")
    for _, r in cand.iterrows():
        print(f"  CANDIDATE {r.frb_name}  best_delay_ms={r.best_delay_ms:.3f}  "
              f"mag_ratio={r.mag_ratio:.3f}  sec_psnr={r.best_secondary_psnr:.1f}")


if __name__ == "__main__":
    main()
