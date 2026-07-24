#!/usr/bin/env python3
"""W2.0 — build the WP2 foundation: quarantine v2 + source-aware split + run log.

Reads the frozen wp2_analysis_config.yaml and the WP0 manifests; writes the
source-level split table (dev/val/test + quarantine flag) to Tier C and records
the run in the experiment DB. Deterministic: same (config, manifests) -> same split.
"""
from __future__ import annotations

import argparse
import hashlib
import os

import pandas as pd
import yaml

from . import db, quarantine, splits


def load_config(path):
    cfg = yaml.safe_load(open(path))
    cfg["_config_hash"] = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--manifests", required=True, help="WP0 manifests dir")
    ap.add_argument("--authors-yaml", required=True)
    ap.add_argument("--out-dir", required=True, help="Tier C dir on popos")
    ap.add_argument("--code-commit", default=os.environ.get("ECHO_FRB_COMMIT", "unknown"))
    a = ap.parse_args()

    cfg = load_config(a.config)
    man = pd.read_parquet(os.path.join(a.manifests, "observation_manifest.parquet"))
    el = pd.read_parquet(os.path.join(a.manifests, "eligibility_table.parquet"))
    eligible = set(el[el.status.isin(["eligible", "provisionally_eligible"])].tns_name)

    qset = quarantine.build_quarantine(cfg, a.authors_yaml)
    split_df = splits.build(man, eligible, cfg, quarantined_tns=set(qset))

    os.makedirs(a.out_dir, exist_ok=True)
    split_path = os.path.join(a.out_dir, "source_split.parquet")
    q_path = os.path.join(a.out_dir, "quarantine_v2.csv")
    split_df.to_parquet(split_path, index=False)
    pd.DataFrame({"tns_name": qset}).to_csv(q_path, index=False)

    db_path = os.path.join(a.out_dir, "experiment_db.parquet")
    rid = db.log_run(db_path, task="W2.0_foundation",
                     config_hash=cfg["_config_hash"], code_commit=a.code_commit,
                     seed=cfg["split"]["salt"],
                     inputs={"eligible": len(eligible), "manifests": a.manifests},
                     params={"fractions": cfg["split"]["fractions"],
                             "n_quarantine": len(qset)},
                     output_path=split_path)

    print(f"[W2.0] config_hash={cfg['_config_hash']}  run_id={rid}")
    print(f"[W2.0] quarantine v2: {len(qset)} tns  -> {q_path}")
    print(f"[W2.0] eligible bursts split: {len(split_df)}")
    print(splits.summary(split_df))
    # invariant: no source spans >1 split
    spanning = split_df.groupby("source_id").split.nunique()
    assert (spanning <= 1).all(), "a source spans multiple splits!"
    print("[W2.0] invariant OK: every source in exactly one split")


if __name__ == "__main__":
    main()
