#!/usr/bin/env python3
"""W3b.1 verification — assert `M_i > 0` == v1 `is_candidate` on REAL bursts.

The unit tests prove the equivalence on synthetic spectra; this proves it on the
archive, where the degenerate cases actually live (bursts with no proposals,
undefined band fits, NaN diagnostics, ties at a threshold). It runs BOTH chains
independently — `blind.pipeline.run_frozen_chain` (v1) and
`margin.chain.run_margin_chain` (v2) — and reports every disagreement.

Runs on popos (Tier B lives there):

  PYTHONPATH=src .venv/bin/python scripts/wp3b_check_equivalence.py \
      --config config/wp2_analysis_config.yaml \
      --split ~/frb_catalog2_prep/wp2/source_split.parquet \
      --tier-b-dir ~/frb_catalog2_prep/tier_b_standardized \
      --split-name development --workers 24 \
      --out ~/frb_catalog2_prep/wp3b/equivalence_development.parquet
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import yaml

from echo_frb.search import tierb_io
from echo_frb.search.blind import pipeline as bp
from echo_frb.search.margin import chain as mchain

_CFG = None


def _init(cfg):
    global _CFG
    _CFG = cfg


def _one(args):
    tns, path = args
    try:
        tb = tierb_io.load_tier_b(path)
        if tb["noise_failed"]:
            return dict(tns_name=tns, status="noise_failed")
        v1 = bp.run_frozen_chain(tb, _CFG)
        v2 = mchain.run_margin_chain(tb, _CFG)
    except Exception as e:                       # a bad burst must not sink the sweep
        return dict(tns_name=tns, status=f"error:{str(e)[:120]}")
    return dict(
        tns_name=tns, status="ok",
        v1_is_candidate=bool(v1["is_candidate"]),
        v2_is_candidate_v1=bool(v2["is_candidate_v1"]),
        M=float(v2["M"]), M_all=float(v2["M_all"]),
        n_proposals_v1=int(v1["n_proposals"]), n_proposals_v2=int(v2["n_proposals"]),
        peak_snr=float(v2["peak_snr"]), n_peaks=int(v2["n_peaks"]),
        n_robustness_evaluated=int(v2["n_robustness_evaluated"]),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--split-name", default="development")
    ap.add_argument("--limit", type=int, default=0, help="0 = all bursts")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config))
    split = pd.read_parquet(os.path.expanduser(a.split))
    tbdir = os.path.expanduser(a.tier_b_dir)
    sel = split[(split.split == a.split_name) & (~split.quarantined)]
    tasks = [(t, os.path.join(tbdir, f"{t}_tierb.h5")) for t in sel.tns_name]
    tasks = [t for t in tasks if os.path.exists(t[1])]
    if a.limit:
        tasks = tasks[:a.limit]
    print(f"[W3b.1] {len(tasks)} {a.split_name} bursts, {a.workers} workers")

    rows = []
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init,
                             initargs=(cfg,)) as ex:
        for i, r in enumerate(ex.map(_one, tasks, chunksize=8)):
            rows.append(r)
            if (i + 1) % 500 == 0:
                print(f"[W3b.1] {i + 1}/{len(tasks)}", flush=True)

    df = pd.DataFrame(rows)
    out = os.path.expanduser(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.to_parquet(out, index=False)

    ok = df[df.status == "ok"].copy()
    bad = df[df.status != "ok"]
    ok["margin_says"] = ok.M > 0
    dis_chain = ok[ok.v1_is_candidate != ok.v2_is_candidate_v1]
    dis_sign = ok[ok.v1_is_candidate != ok.margin_says]
    dis_props = ok[ok.n_proposals_v1 != ok.n_proposals_v2]

    print(f"\n[W3b.1] scored {len(ok)} bursts ({len(bad)} skipped/errored)")
    print(f"  v1 candidates             : {int(ok.v1_is_candidate.sum())}")
    print(f"  M > 0                     : {int(ok.margin_says.sum())}")
    print(f"  proposal-count mismatches : {len(dis_props)}")
    print(f"  v1-flag mismatches        : {len(dis_chain)}")
    print(f"  SIGN mismatches (M>0 vs v1): {len(dis_sign)}")
    if len(dis_sign):
        print(dis_sign[["tns_name", "v1_is_candidate", "M", "n_proposals_v2",
                        "n_robustness_evaluated"]].head(20).to_string(index=False))
    if len(bad):
        print("  skipped reasons:", bad.status.value_counts().to_dict())

    fin = ok[np.isfinite(ok.M)]
    print(f"\n[W3b.1] M distribution (finite, n={len(fin)}): "
          f"min={fin.M.min():.3f} p50={fin.M.median():.3f} "
          f"p99={fin.M.quantile(0.99):.3f} max={fin.M.max():.3f}")
    print(f"[W3b.1] bursts with no proposals (M=-inf): {int((~np.isfinite(ok.M)).sum())}")
    print(f"[W3b.1] -> {out}")
    if len(dis_sign) or len(dis_chain) or len(dis_props):
        raise SystemExit("EQUIVALENCE VIOLATED — v2 is not a tightening of v1")
    print("[W3b.1] EQUIVALENCE HOLDS on every scored burst")


if __name__ == "__main__":
    main()
