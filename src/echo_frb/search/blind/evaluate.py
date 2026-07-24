#!/usr/bin/env python3
"""W3.2 — the BLIND EVALUATOR: run the frozen pipeline on the hidden set.

Reads ONLY the public `hidden_manifest.parquet` + the `items/` spectra — never the
withheld truth file. Asserts the frozen analysis config has not drifted, then runs
`run_frozen_chain` (Tier-1 -> χ²_copy -> robustness -> full criterion) on every
item and records a candidate / not-candidate decision plus sub-scores. Emits
`hidden_scores.parquet` and `scores_commitment.json` (sha256 + UTC timestamp) — the
timestamp must post-date the withheld-file commitment, which `unblind` enforces.

Blindness is structural: this module opens no withheld artifact and the CLI accepts
no path to one. `tests/test_wp3_blind.py` scans this source to enforce that.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

import pandas as pd
import yaml

from . import foundation
from .pipeline import load_and_run

_CFG = None       # per-worker frozen analysis config (set in initializer)


def _init(ana_cfg):
    global _CFG
    _CFG = ana_cfg


def _score_one(args):
    item_id, path = args
    try:
        d = load_and_run(path, _CFG)
    except Exception as e:                       # a single bad item must not sink the run
        return dict(item_id=item_id, error=str(e)[:200], is_candidate=False)
    if d is None:
        return dict(item_id=item_id, error="noise_failed_or_unreadable",
                    is_candidate=False)
    return dict(item_id=item_id, error="", **d)


def evaluate(manifest, items_dir, ana_cfg, workers):
    tasks = [(r.item_id, os.path.join(items_dir, r.h5)) for r in manifest.itertuples()]
    rows = []
    if workers <= 1:
        _init(ana_cfg)
        rows = [_score_one(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init,
                                 initargs=(ana_cfg,)) as ex:
            for i, r in enumerate(ex.map(_score_one, tasks, chunksize=4)):
                rows.append(r)
                if (i + 1) % 100 == 0:
                    print(f"[W3.2] scored {i + 1}/{len(tasks)}", flush=True)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description="W3.2 — blind frozen-pipeline evaluator")
    ap.add_argument("--wp3-config", required=True)
    ap.add_argument("--analysis-config", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--round-dir", required=True, help="dir with hidden_manifest.parquet + items/")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    cfg = foundation.load_wp3_config(a.wp3_config)
    ana_hash = foundation.assert_freeze_contract(cfg, os.path.expanduser(a.repo_root))
    ana_cfg = yaml.safe_load(open(a.analysis_config))
    print(f"[W3.2] freeze contract OK: analysis config == {ana_hash}")

    rd = os.path.expanduser(a.round_dir)
    manifest = pd.read_parquet(os.path.join(rd, "hidden_manifest.parquet"))
    scores = evaluate(manifest, os.path.join(rd, "items"), ana_cfg, a.workers)

    out = os.path.join(rd, "hidden_scores.parquet")
    scores.to_parquet(out, index=False)
    commitment = dict(
        n_scored=len(scores), n_candidates=int(scores.is_candidate.sum()),
        scores_sha256=hashlib.sha256(open(out, "rb").read()).hexdigest(),
        scores_created_utc=datetime.now(timezone.utc).isoformat(),
        analysis_config_sha16=ana_hash, wp3_config_sha16=cfg["_config_hash"],
    )
    json.dump(commitment, open(os.path.join(rd, "scores_commitment.json"), "w"), indent=2)

    print(f"[W3.2] {len(scores)} items scored, "
          f"{int(scores.is_candidate.sum())} flagged candidate -> {out}")
    print(f"[W3.2] scores commitment sha256 {commitment['scores_sha256'][:16]}… "
          f"@ {commitment['scores_created_utc']}")
    if (scores.error != "").any():
        print(f"[W3.2] WARNING: {(scores.error != '').sum()} items errored")


if __name__ == "__main__":
    main()
