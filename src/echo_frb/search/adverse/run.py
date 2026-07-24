#!/usr/bin/env python3
"""W2.4 — inject adverse imitators into real single-component bursts, score them.

For a sample of development, non-quarantined, single-component bursts: inject each
adverse kind (+ the achromatic-copy control) at a fixed delay/magnification and
score with χ²_copy -> adverse_catalog.parquet. The gate check (W2.7) is that every
adverse kind scores LESS copy-like than achromatic_copy.
"""
from __future__ import annotations

import argparse
import hashlib
import os

import numpy as np
import pandas as pd
import yaml

from .. import tierb_io
from ..copy import score as scoremod
from ..tier1 import profile
from . import generators as gen


def _rng(tns, salt):
    return np.random.default_rng(int(hashlib.sha256(f"{salt}:{tns}".encode()).hexdigest()[:8], 16))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-bursts", type=int, default=150)
    ap.add_argument("--dt-bins", type=int, default=8)
    ap.add_argument("--mu", type=float, default=0.5)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config))
    salt = cfg["split"]["salt"]
    split = pd.read_parquet(a.split)
    man = pd.read_parquet(os.path.join(a.manifests, "observation_manifest.parquet"))
    tbdir = os.path.expanduser(a.tier_b_dir)

    single = man[man.get("n_subbursts", 1).fillna(1) <= 1][["tns_name"]]
    pool = split[(split.split == "development") & (~split.quarantined)] \
        .merge(single, on="tns_name")
    names = list(pool.tns_name)[: a.n_bursts]

    rows, used = [], 0
    for tns in names:
        path = os.path.join(tbdir, f"{tns}_tierb.h5")
        if not os.path.exists(path):
            continue
        tb = tierb_io.load_tier_b(path)
        if tb["noise_failed"]:
            continue
        c = int(np.argmax(profile.build_profile(tb)["I"]))
        if c + a.dt_bins >= tb["standardized"].shape[1] - 5 or c - 5 < 0:
            continue
        used += 1
        rng = _rng(tns, salt)
        for kind in gen.KINDS:
            tb2 = gen.inject(tb, c, a.dt_bins, a.mu, kind, rng)
            r = scoremod.score_proposal(tb2, c, c + a.dt_bins, cfg)
            rows.append(dict(kind=kind, tns_name=tns, delta_chi2=r["delta_chi2"],
                             reduced_chi2=r["reduced_chi2"], ncc=r["ncc"],
                             best_a=r["best_a"], delay_ms=r["delay_ms"]))

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(os.path.abspath(os.path.expanduser(a.out))), exist_ok=True)
    df.to_parquet(os.path.expanduser(a.out), index=False)
    print(f"[adverse] {used} bursts x {len(gen.KINDS)} kinds -> {len(df)} rows -> {a.out}\n")
    g = df.groupby("kind").agg(ncc=("ncc", "median"),
                               reduced_chi2=("reduced_chi2", "median"),
                               delta_chi2=("delta_chi2", "median")).round(3)
    print(g.sort_values("ncc", ascending=False).to_string())
    ctrl = df[df.kind == "achromatic_copy"].ncc.median()
    worse = [k for k in gen.KINDS if k != "achromatic_copy"
             and df[df.kind == k].ncc.median() < ctrl]
    print(f"\nachromatic_copy NCC median={ctrl:.3f}; "
          f"adverse kinds scoring less copy-like: {len(worse)}/{len(gen.KINDS)-1}")


if __name__ == "__main__":
    main()
