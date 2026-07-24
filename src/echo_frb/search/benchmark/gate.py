#!/usr/bin/env python3
"""W2.7 — the NULL BENCHMARK (the WP2 gate, proposal §8, §6.1).

Ties the pieces together:
  1. false-positive distribution of the copy criterion is STABLE across the null
     constructions (real / xpair / surrogate) — disagreement reported as an
     explicit uncertainty (proposal §6.5);
  2. known artifacts (adverse sims) are REJECTED — they sit in the null bulk;
  3. efficiency (injections) vs false-positive (nulls) tradeoff -> operating point.

Candidate criterion (copy-consistency): delta_chi2 > τ (matched-filter
detectability) AND ncc > τ_ncc AND reduced_chi2 < τ_red (achromatic-copy quality).
Same criterion for nulls (=> false positive) and injections (=> efficiency).
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

NCC_MIN, RED_MAX = 0.40, 1.5
DELTA_GRID = [20, 50, 100, 200, 500, 1000, 2000, 5000]
REF_DELTA = 100.0


def passes(df, delta_min, ncc_min=NCC_MIN, red_max=RED_MAX):
    return ((df.delta_chi2 > delta_min) & (df.ncc > ncc_min)
            & (df.reduced_chi2 < red_max))


def _base(construction):
    return construction.str.split(":").str[0]


def build(nulls_dir, injection_path):
    allnull = pd.read_parquet(os.path.join(nulls_dir, "null_catalog_all.parquet"))
    allnull["cbase"] = _base(allnull.construction)
    adverse = pd.read_parquet(os.path.join(nulls_dir, "adverse_catalog.parquet"))
    inj = pd.read_parquet(injection_path)

    # 1. FP rate per null construction, across the delta sweep
    fp_rows = []
    for cb, g in allnull.groupby("cbase"):
        for d in DELTA_GRID:
            fp_rows.append(dict(construction=cb, delta_min=d, n=len(g),
                                fp_rate=round(float(passes(g, d).mean()), 4)))
    # surrogate resolved per method too
    for c, g in allnull[allnull.cbase == "surrogate"].groupby("construction"):
        for d in DELTA_GRID:
            fp_rows.append(dict(construction=c, delta_min=d, n=len(g),
                                fp_rate=round(float(passes(g, d).mean()), 4)))
    fp = pd.DataFrame(fp_rows)

    # 2. adverse rejection: pass-rate per kind at the reference criterion
    adv = (adverse.assign(passed=passes(adverse, REF_DELTA))
           .groupby("kind").agg(n=("passed", "size"),
                                fp_rate=("passed", "mean")).round(4).reset_index())

    # 3. ROC: efficiency (injections, mu>=0.3) vs FP (real null)
    inj_roc = inj[inj.mu >= 0.3]
    real = allnull[allnull.cbase == "real"]
    xpair = allnull[allnull.cbase == "xpair"]
    sur = allnull[allnull.cbase == "surrogate"]
    roc = []
    for d in DELTA_GRID:
        roc.append(dict(delta_min=d,
                        efficiency=round(float(passes(inj_roc, d).mean()), 4),
                        fp_real=round(float(passes(real, d).mean()), 4),
                        fp_xpair=round(float(passes(xpair, d).mean()), 4),
                        fp_surrogate=round(float(passes(sur, d).mean()), 4)))
    roc = pd.DataFrame(roc)
    roc["null_disagreement"] = (roc[["fp_real", "fp_xpair"]].max(1)
                                - roc[["fp_real", "fp_xpair"]].min(1)).round(4)
    return fp, adv, roc, allnull


def report(fp, adv, roc, allnull):
    L = ["# WP2 Null Benchmark — the gate\n",
         "Candidate criterion: delta_chi2 > τ AND ncc > 0.40 AND reduced_chi2 < 1.5.",
         "FP = null pairs passing; efficiency = injected copies passing.\n",
         "## 1. Copy-score distribution by null construction (delta_chi2 / ncc / reduced_chi2 medians)"]
    for cb, g in allnull.groupby("cbase"):
        L.append(f"- {cb:<10} n={len(g):>6}  Δχ² med={g.delta_chi2.median():.0f}  "
                 f"ncc med={g.ncc.median():.3f}  reduced med={g.reduced_chi2.median():.2f}")
    L.append("\n## 2. Efficiency vs false-positive tradeoff (ROC)")
    L.append(roc.to_string(index=False))
    L.append("\n## 3. Known artifacts rejected (pass-rate at reference criterion)")
    L.append(adv.sort_values("fp_rate", ascending=False).to_string(index=False))
    # verdict
    ref = roc[roc.delta_min == REF_DELTA].iloc[0]
    sur_lt_real = (allnull[allnull.cbase == "surrogate"].delta_chi2.median()
                   < allnull[allnull.cbase == "real"].delta_chi2.median())
    adv_ok = float(adv[adv.kind != "achromatic_copy"].fp_rate.max()) <= ref["fp_real"] + 0.05
    L.append("\n## 4. Gate assessment")
    L.append(f"- surrogate Δχ² below real (structure matters): {bool(sur_lt_real)}")
    L.append(f"- at τ={REF_DELTA:.0f}: efficiency(μ≥0.3)={ref.efficiency}, "
             f"FP real={ref.fp_real}, xpair={ref.fp_xpair}, surrogate={ref.fp_surrogate}")
    L.append(f"- null-model disagreement (|real−xpair|) at τ={REF_DELTA:.0f}: {ref.null_disagreement}")
    L.append(f"- adverse artifacts rejected (max non-copy pass-rate ≈ null): {bool(adv_ok)}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nulls-dir", required=True)
    ap.add_argument("--injection", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    fp, adv, roc, allnull = build(a.nulls_dir, a.injection)
    os.makedirs(a.out_dir, exist_ok=True)
    fp.to_parquet(os.path.join(a.out_dir, "fp_distributions.parquet"), index=False)
    roc.to_parquet(os.path.join(a.out_dir, "roc.parquet"), index=False)
    md = report(fp, adv, roc, allnull)
    open(os.path.join(a.out_dir, "null_benchmark_report.md"), "w").write(md)
    print(md)


if __name__ == "__main__":
    main()
