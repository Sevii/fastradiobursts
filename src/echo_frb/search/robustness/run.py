#!/usr/bin/env python3
"""W2.5 — apply the robustness diagnostics to injected achromatic copies vs
adverse imitators, to show the achromaticity/stability checks reject the cases
the copy score alone leaves borderline (esp. scintillation).
"""
from __future__ import annotations

import argparse
import hashlib
import os

import numpy as np
import pandas as pd
import yaml

from .. import tierb_io
from ..adverse import generators as gen
from ..tier1 import profile
from . import diagnostics as diag

KINDS = ["achromatic_copy", "drift", "differential_dm", "differential_scattering",
         "scintillation", "chromatic_echo"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-bursts", type=int, default=60)
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

    rows, used = [], 0
    for tns in list(pool.tns_name):
        if used >= a.n_bursts:
            break
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
        rng = np.random.default_rng(int(hashlib.sha256(f"{salt}:{tns}".encode()).hexdigest()[:8], 16))
        for kind in KINDS:
            tb2 = gen.inject(tb, c, a.dt_bins, a.mu, kind, rng)
            d = diag.run_all(tb2, c, c + a.dt_bins, cfg)
            d.update(kind=kind, tns_name=tns)
            rows.append(d)

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(os.path.abspath(os.path.expanduser(a.out))), exist_ok=True)
    df.to_parquet(os.path.expanduser(a.out), index=False)
    flags = ["achromatic_delay_pass", "magnification_stability_pass",
             "dm_scattering_pass", "residual_structure_pass", "n_pass"]
    print(f"[robustness] {used} bursts x {len(KINDS)} kinds -> {len(df)} rows\n")
    g = df.groupby("kind")[flags].mean().round(2)
    print(g.sort_values("n_pass", ascending=False).to_string())


if __name__ == "__main__":
    main()
