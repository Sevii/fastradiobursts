#!/usr/bin/env python3
"""W3.2 — the BLIND EVALUATOR: run the frozen pipeline on the hidden set.

Reads ONLY the public `hidden_manifest.parquet` + the `items/` spectra — never the
withheld truth file. Asserts the frozen analysis config has not drifted, scores
every item, and emits `hidden_scores.parquet` + `scores_commitment.json` (sha256 +
UTC timestamp) — the timestamp must post-date the withheld-file commitment, which
`unblind` enforces.

TWO ANALYSIS VERSIONS, selected by the config, with no silent fallback:

  v1 (`wp2-frozen-v1`, no `margin` block) — `run_frozen_chain`: Tier-1 -> χ²_copy
      -> robustness -> full criterion. A burst is a candidate iff ANY proposal
      passes. Unchanged, so WP3 round 1 stays reproducible.

  v2 (`wp2-frozen-v2`, `margin` block present) — `run_margin_chain` -> the COMMITTED
      calibration -> `is_candidate = (M > 0) AND (p_robust <= alpha)`. This prices
      the within-burst multiplicity that made round 1's per-window calibration
      optimistic (docs/WP3b_plan.md).

The v2 path refuses to score unless `margin.alpha` is set and the calibration
artifact still hashes to its commitment — the calibration decides candidacy, so it
is as much part of the freeze as the thresholds are.

Blindness is structural: this module opens no withheld artifact and the CLI accepts
no path to one. The calibration is built from DEVELOPMENT nulls only and contains
no test-split data. `tests/test_wp3_blind.py` scans this source to enforce both.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yaml

from ..margin import calibrate as mcal
from ..margin import chain as mchain
from . import foundation
from .pipeline import load_and_run

_CFG = None       # per-worker frozen analysis config (set in initializer)
_CALIB = None     # per-worker committed calibration (v2 only)


def is_v2(ana_cfg):
    """v2 iff the frozen analysis config carries a margin block."""
    return bool((ana_cfg or {}).get("margin"))


def _init(ana_cfg, calib_dir=None):
    global _CFG, _CALIB
    _CFG = ana_cfg
    # loaded per worker rather than pickled across: the artifact is small and this
    # keeps the hash verification inside every process that uses it
    _CALIB = mcal.load_calibration(calib_dir) if calib_dir else None


def _score_one(args):
    item_id, path = args
    try:
        if _CALIB is None:                       # ---- v1 path (unchanged) ----
            d = load_and_run(path, _CFG)
        else:                                    # ---- v2 path ----
            d = mchain.load_and_run(path, _CFG)
            if d is not None:
                alpha = float(_CFG["margin"]["alpha"])
                pv = _CALIB.pvalues(d["M"], d)
                d = dict(d, p_robust=pv["p_robust"],
                         worst_family=pv["worst_family"],
                         p_robust_empirical=pv.get("p_robust_empirical", np.nan),
                         p_robust_at_floor=pv.get("p_robust_at_floor", False),
                         cell_level=pv.get("cell_level", ""),
                         is_candidate=bool(d["M"] > 0 and pv["p_robust"] <= alpha))
    except Exception as e:                       # a single bad item must not sink the run
        return dict(item_id=item_id, error=str(e)[:200], is_candidate=False)
    if d is None:
        return dict(item_id=item_id, error="noise_failed_or_unreadable",
                    is_candidate=False)
    return dict(item_id=item_id, error="", **d)


def evaluate(manifest, items_dir, ana_cfg, workers, calib_dir=None):
    tasks = [(r.item_id, os.path.join(items_dir, r.h5)) for r in manifest.itertuples()]
    rows = []
    if workers <= 1:
        _init(ana_cfg, calib_dir)
        rows = [_score_one(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init,
                                 initargs=(ana_cfg, calib_dir)) as ex:
            for i, r in enumerate(ex.map(_score_one, tasks, chunksize=4)):
                rows.append(r)
                if (i + 1) % 100 == 0:
                    print(f"[W3.2] scored {i + 1}/{len(tasks)}", flush=True)
    return pd.DataFrame(rows)


def assert_calibration_contract(ana_cfg, calib_dir):
    """v2 refuses to score without a set alpha and an untampered calibration."""
    alpha = ana_cfg["margin"].get("alpha")
    assert alpha is not None, (
        "margin.alpha is null — the decision threshold must be committed before a "
        "blind round is scored (docs/WP3b_plan.md §4).")
    assert calib_dir, (
        "the v2 analysis needs --calibration: the committed calibration decides "
        "candidacy and is part of the freeze, not a runtime option.")
    calib_dir = os.path.expanduser(calib_dir)
    commit = json.load(open(os.path.join(calib_dir, "calibration_commitment.json")))
    mcal.load_calibration(calib_dir)             # verifies both artifact hashes
    got = mcal.sha256_file(os.path.join(calib_dir, mcal.MANIFEST_FILE))
    assert got == commit["manifest_sha256"], (
        f"CALIBRATION MANIFEST DRIFTED: {got[:16]}… != committed "
        f"{commit['manifest_sha256'][:16]}…")
    assert float(commit["alpha"]) == float(alpha), (
        f"alpha mismatch: config says {alpha}, the committed calibration was "
        f"frozen at {commit['alpha']}")
    assert float(alpha) >= float(commit["min_resolvable_alpha"]), (
        f"alpha={alpha} is below the calibration's resolvable floor "
        f"{commit['min_resolvable_alpha']} — no burst could ever clear it")
    return commit


def main():
    ap = argparse.ArgumentParser(description="W3.2 — blind frozen-pipeline evaluator")
    ap.add_argument("--wp3-config", required=True)
    ap.add_argument("--analysis-config", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--round-dir", required=True, help="dir with hidden_manifest.parquet + items/")
    ap.add_argument("--calibration", help="committed calibration dir (REQUIRED for v2)")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    cfg = foundation.load_wp3_config(a.wp3_config)
    ana_hash = foundation.assert_freeze_contract(cfg, os.path.expanduser(a.repo_root))
    ana_cfg = yaml.safe_load(open(a.analysis_config))
    print(f"[W3.2] freeze contract OK: analysis config == {ana_hash}")

    calib_dir, calib_commit = None, None
    if is_v2(ana_cfg):
        calib_commit = assert_calibration_contract(ana_cfg, a.calibration)
        calib_dir = os.path.expanduser(a.calibration)
        print(f"[W3.2] v2 ({ana_cfg['analysis_version']}): alpha="
              f"{ana_cfg['margin']['alpha']}, calibration "
              f"{calib_commit['manifest_sha256'][:16]}… "
              f"({calib_commit['n_cells']} cells, "
              f"{calib_commit['n_realizations']} null realizations)")
    elif a.calibration:
        raise SystemExit("--calibration given but the analysis config has no margin "
                         "block; refusing to mix versions")
    else:
        print(f"[W3.2] v1 ({ana_cfg['analysis_version']}): full-criterion path")

    rd = os.path.expanduser(a.round_dir)
    manifest = pd.read_parquet(os.path.join(rd, "hidden_manifest.parquet"))
    scores = evaluate(manifest, os.path.join(rd, "items"), ana_cfg, a.workers,
                      calib_dir)

    out = os.path.join(rd, "hidden_scores.parquet")
    scores.to_parquet(out, index=False)
    commitment = dict(
        n_scored=len(scores), n_candidates=int(scores.is_candidate.sum()),
        scores_sha256=hashlib.sha256(open(out, "rb").read()).hexdigest(),
        scores_created_utc=datetime.now(timezone.utc).isoformat(),
        analysis_config_sha16=ana_hash, wp3_config_sha16=cfg["_config_hash"],
        analysis_version=ana_cfg["analysis_version"],
        alpha=(ana_cfg["margin"]["alpha"] if calib_commit else None),
        calibration_manifest_sha256=(calib_commit["manifest_sha256"]
                                     if calib_commit else None),
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
