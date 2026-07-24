#!/usr/bin/env python3
"""W2.8 — null-calibrate the global-FAP machinery on the real null.

Ranking statistic = delta_chi2 among copy-quality-passing null proposals (a
populated null for building/validating the machinery; the full mandatory-
achromaticity criterion is even more stringent -> smaller FAP). Reports the
source-level catalog-max null distribution, GPD tail fit + out-of-sample
validation, empirical resolution, and an example FAP.
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from . import global_fap as gf

NCC_MIN, RED_MAX = 0.40, 1.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--null-real", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--n-boot", type=int, default=20000)
    a = ap.parse_args()

    real = pd.read_parquet(a.null_real)
    split = pd.read_parquet(a.split)[["tns_name", "source_id"]]
    df = real.merge(split, on="tns_name", how="left")
    df = df[df.source_id.notna()]
    # copy-quality-passing null proposals (the FP population to guard against)
    cq = df[(df.ncc > NCC_MIN) & (df.reduced_chi2 < RED_MAX)]
    print(f"[sig] real null: {len(df)} proposals, {len(cq)} copy-quality "
          f"({df.source_id.nunique()} sources)", flush=True)

    # Ranking statistic = NCC (on-burst copy correlation). Raw Δχ² is unusable
    # here: it ∝ SNR², so the catalog-max is dominated by the single brightest
    # burst (a point mass) rather than by copy-consistency. NCC is brightness-fair
    # and bounded — it ranks "how copy-like", which is what the FWER must guard.
    maxima = gf.catalog_max_bootstrap(cq.ncc.values, cq.source_id.values,
                                      n_boot=a.n_boot)
    res = gf.empirical_resolution(a.n_boot)
    params, val = gf.gpd_tail_fit_validate(maxima)

    os.makedirs(a.out_dir, exist_ok=True)
    pd.DataFrame({"catalog_max": maxima}).to_parquet(
        os.path.join(a.out_dir, "null_catalog_max.parquet"), index=False)

    L = ["# WP2 Global significance — max-statistic FWER (null-calibrated)\n",
         "Ranking statistic = NCC (brightness-fair; raw Δχ² ∝ SNR² collapses the "
         "catalog-max to the single brightest burst — documented in W2.8).",
         f"- source-level cluster bootstrap, B={a.n_boot}; empirical resolution = {res:.1e}",
         f"- catalog-max null NCC quantiles: "
         f"50%={np.quantile(maxima,.5):.3f} 90%={np.quantile(maxima,.9):.3f} "
         f"99%={np.quantile(maxima,.99):.3f} max={maxima.max():.3f}"]
    if params:
        L.append(f"- GPD tail: shape c={params['shape_c']:.3f}, "
                 f"scale={params['scale']:.3f}, u={params['threshold_u']:.3f}")
        L.append("- out-of-sample tail validation (pred vs empirical FAP):")
        for v in val:
            L.append(f"    q={v['quantile']}: NCC={v['x']}  pred={v['pred_fap']:.2e}  "
                     f"emp={v['emp_fap']:.2e}")
    # example: global FAP of a strongly copy-like candidate
    for s in (np.quantile(maxima, 0.99), min(0.99, maxima.max() + 0.03)):
        L.append(f"- example: observed NCC={s:.3f} -> global FAP = "
                 f"{gf.global_fap(s, maxima):.2e}")
    out = "\n".join(L)
    open(os.path.join(a.out_dir, "global_significance_report.md"), "w").write(out)
    print(out)


if __name__ == "__main__":
    main()
