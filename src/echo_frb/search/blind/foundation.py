#!/usr/bin/env python3
"""W3.0 — blind-test foundation: freeze contract + disjoint blind-round pools.

Two jobs, both about integrity BEFORE any hidden data is drawn:

1. **Freeze contract.** The frozen analysis pipeline must not have drifted since
   WP2. `assert_freeze_contract` recomputes sha256(analysis_config)[:16] and checks
   it equals the pinned value in the WP3 harness config, and that the analysis
   version string is intact. (Code==config is separately asserted by
   tests/test_wp2_frozen.py, run as part of the suite.) Any drift => a NEW analysis
   version, which forfeits the WP2 calibration (proposal §5.8 step 7) — so this
   fails loudly rather than silently validating a mutated pipeline.

2. **Blind-round pools.** The sealed test-split SOURCES are partitioned into K
   disjoint pools by a deterministic hash of a NEW salt. Round r draws its hidden
   mixture from pool r only; a failed gate re-does on the next, source-disjoint
   pool (proposal §5.8 step 5 — a re-do needs a genuinely fresh hidden set). A
   finite catalog yields finitely many pools: after K failures we redesign, not
   draw again (§8.1 / §11 look-elsewhere depth).
"""
from __future__ import annotations

import argparse
import hashlib
import os

import pandas as pd
import yaml


def config_sha16(path: str) -> str:
    """sha256 of the file bytes, first 16 hex — the project's config-hash convention."""
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def load_wp3_config(path: str) -> dict:
    cfg = yaml.safe_load(open(path))
    cfg["_config_hash"] = config_sha16(path)
    return cfg


def assert_freeze_contract(wp3_cfg: dict, repo_root: str) -> str:
    """Assert the frozen analysis pipeline is byte-identical to what was frozen.

    Returns the verified analysis-config hash. Raises AssertionError on any drift.

    W3b.7-F: an UNSIGNED harness (`analysis_config_sha16: null`) is refused rather
    than waved through. A null pin is not "no constraint" — it means the analysis
    config is still moving, and a blind round drawn against a moving pipeline is
    not a blind round.
    """
    fr = wp3_cfg["frozen"]
    ana_path = os.path.join(repo_root, fr["analysis_config"])
    got = config_sha16(ana_path)
    exp = fr["analysis_config_sha16"]
    assert exp is not None, (
        f"HARNESS NOT SIGNED: {fr['analysis_config']} is unpinned "
        f"(analysis_config_sha16 is null; it currently hashes to {got}). The "
        f"analysis config must be frozen — `frozen_date` set, alpha committed, PI "
        f"signature on the preregistration addendum — before a blind round may be "
        f"drawn or scored (docs/WP3b_W3b.7_plan.md §F).")
    assert got == exp, (
        f"FROZEN ANALYSIS CONFIG DRIFTED: {fr['analysis_config']} hashes {got}, "
        f"expected {exp} ({fr['analysis_version']}). WP3 must run the UNMODIFIED "
        f"wp2-frozen-v1 pipeline; any change forfeits the WP2 calibration "
        f"(proposal §5.8 step 7). Fix the config or cut a new analysis version.")
    ana = yaml.safe_load(open(ana_path))
    assert ana["analysis_version"] == fr["analysis_version"], (
        f"analysis_version mismatch: config says {ana['analysis_version']!r}, "
        f"WP3 pinned {fr['analysis_version']!r}")
    return got


def _pool_of(source_id: str, salt: str, k: int) -> int:
    """Deterministic, order-independent pool index in [0, k) for a source."""
    h = hashlib.sha256(f"{salt}:{source_id}".encode()).hexdigest()
    return int(h[:16], 16) % k


def partition_pools(split_df: pd.DataFrame, k: int, salt: str,
                    split_source: str = "test") -> pd.DataFrame:
    """Assign each SOURCE in the sealed test split to one of K disjoint pools.

    Operates at the source level (repeaters share a source), so no source spans two
    pools. Non-test and quarantined bursts are excluded. Returns one row per test
    burst with its source_id, pool index, and pass-through split metadata.
    """
    t = split_df[(split_df.split == split_source) & (~split_df.quarantined)].copy()
    src_pool = {s: _pool_of(s, salt, k) for s in t.source_id.unique()}
    t["pool"] = t.source_id.map(src_pool)
    return t[["tns_name", "source_id", "is_repeater", "split", "pool"]] \
        .sort_values(["pool", "tns_name"]).reset_index(drop=True)


def pools_summary(pools_df: pd.DataFrame) -> str:
    g = pools_df.groupby("pool").agg(sources=("source_id", "nunique"),
                                     bursts=("tns_name", "size"))
    lines = ["pool  sources  bursts"]
    for p, row in g.iterrows():
        lines.append(f"{int(p):<6}{int(row.sources):>7}{int(row.bursts):>8}")
    lines.append(f"total sources: {pools_df.source_id.nunique()}  "
                 f"bursts: {len(pools_df)}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="W3.0 — blind-test foundation")
    ap.add_argument("--wp3-config", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--split", required=True, help="wp2 source_split.parquet")
    ap.add_argument("--out", required=True, help="blind_round_pools.parquet")
    a = ap.parse_args()

    cfg = load_wp3_config(a.wp3_config)
    ana_hash = assert_freeze_contract(cfg, os.path.expanduser(a.repo_root))
    print(f"[W3.0] freeze contract OK: analysis config == {ana_hash} "
          f"({cfg['frozen']['analysis_version']})")

    split = pd.read_parquet(os.path.expanduser(a.split))
    pools = partition_pools(split, cfg["pools"]["k"], cfg["pools"]["salt"],
                            cfg["pools"]["split_source"])

    # invariant: no source spans >1 pool
    spanning = pools.groupby("source_id").pool.nunique()
    assert (spanning <= 1).all(), "a source spans multiple blind-round pools!"

    outp = os.path.expanduser(a.out)
    os.makedirs(os.path.dirname(os.path.abspath(outp)), exist_ok=True)
    pools.to_parquet(outp, index=False)
    print(f"[W3.0] wp3_config_hash={cfg['_config_hash']}  pools -> {outp}")
    print(f"[W3.0] invariant OK: every source in exactly one pool")
    print(pools_summary(pools))


if __name__ == "__main__":
    main()
