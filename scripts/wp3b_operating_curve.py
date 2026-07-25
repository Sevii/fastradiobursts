#!/usr/bin/env python3
"""W3b.5/W3b.6 — fit the calibration and read off the efficiency/FP operating curve.

    --fit-on   ensemble whose NULL families define P0(M >= m | Z)   (always dev)
    --eval-on  ensemble scored against it (dev = preview, validation = the dry run)

Fitting and evaluating on the same file is CIRCULAR for the false-positive rate —
p <= alpha then holds at rate ~alpha by construction — and is only honest for the
EFFICIENCY column. The out-of-sample question ("is the FP really alpha?") is what
the validation dry run answers, which is why --eval-on exists as a separate flag.
The report labels the circular case explicitly.

  PYTHONPATH=src .venv/bin/python scripts/wp3b_operating_curve.py \
      --config config/wp2_analysis_config_v2.yaml \
      --fit-on ~/frb_catalog2_prep/wp3b/null_ensemble_development.parquet \
      --eval-on ~/frb_catalog2_prep/wp3b/null_ensemble_development.parquet \
      --out-dir ~/frb_catalog2_prep/wp3b/curve_dev
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd
import yaml

from echo_frb.search.margin import calibrate as cal

ALPHAS = [0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001]
DETERMINISTIC = ["adverse_drift", "adverse_differential_dm", "adverse_chromatic_echo",
                 "adverse_rfi_remnant", "adverse_overlapping"]
# `surrogate_block_bootstrap` resamples contiguous time blocks WITH REPLACEMENT, so
# it can place the same block twice and thereby MANUFACTURE an exact achromatic
# copy — the very signal under test (W3b.5 finding: the median dev passer from this
# family has per-band delay spread of exactly 0). It is not a valid null for a copy
# test, and under p^robust = max_h a broken null would silently set the threshold
# for every other family. Excluded by default; --include-block-bootstrap shows the cost.
BROKEN_NULLS = ["surrogate_block_bootstrap"]


def load(path):
    d = pd.read_parquet(os.path.expanduser(path))
    return d[d.error == ""] if "error" in d else d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--fit-on", required=True)
    ap.add_argument("--eval-on", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--include-block-bootstrap", action="store_true")
    ap.add_argument("--mu-floor", type=float, default=0.5,
                    help="efficiency stratum for the go/no-go (plan §4)")
    ap.add_argument("--n-boot", type=int, default=2000)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config))
    fit_df, ev = load(a.fit_on), load(a.eval_on)
    circular = os.path.realpath(os.path.expanduser(a.fit_on)) == \
        os.path.realpath(os.path.expanduser(a.eval_on))

    fams = sorted(f for f in fit_df[fit_df.truth_class == "null"].family.unique()
                  if a.include_block_bootstrap or f not in BROKEN_NULLS)
    calib = cal.Calibration.fit(fit_df, cfg, families=fams)
    print(f"[W3b.5] calibrated on {len(fams)} null families "
          f"({len(fit_df[fit_df.truth_class == 'null'])} realizations)")
    if not a.include_block_bootstrap:
        print(f"[W3b.5] EXCLUDED as invalid nulls: {BROKEN_NULLS} "
              f"(manufactures exact copies — see script docstring)")
    if circular:
        print("[W3b.5] NOTE: fit == eval; the FP columns below are CIRCULAR "
              "(FP ~ alpha by construction). Only EFFICIENCY is meaningful here.")
    factor = (cfg.get("margin", {}).get("conditioning", {})
              .get("min_cell_resolution_factor", 4.0))
    a_min, worst = calib.min_resolvable_alpha(factor)
    print(f"[W3b.5] smallest RESOLVABLE alpha = {a_min:.4f} "
          f"(thinnest usable cell: {worst}); rows below it are sample-limited, "
          f"not measurements")

    p = calib.apply(ev)
    ev = pd.concat([ev.reset_index(drop=True), p.reset_index(drop=True)], axis=1)
    outdir = os.path.expanduser(a.out_dir)
    os.makedirs(outdir, exist_ok=True)
    ev.to_parquet(os.path.join(outdir, "scored.parquet"), index=False)
    calib.summary().to_parquet(os.path.join(outdir, "calibration_cells.parquet"),
                               index=False)

    inj = ev[ev.truth_class == "positive"]
    bright = inj[inj.mu >= a.mu_floor]
    nulls = ev[ev.truth_class == "null"]

    rows = []
    for alpha in ALPHAS:
        # v2 decision rule: BOTH the frozen gates and the multiplicity penalty
        dec = lambda s: (s.M > 0) & (s.p_robust <= alpha)
        r = dict(alpha=alpha,
                 eff_all_mu=round(float(dec(inj).mean()), 4),
                 eff_mu_ge=round(float(dec(bright).mean()), 4))
        for fam, g in nulls.groupby("family"):
            r[fam] = round(float(dec(g).mean()), 4)
        r["deterministic_max"] = round(max(
            [r.get(f, np.nan) for f in DETERMINISTIC if f in r] or [np.nan]), 4)
        rows.append(r)
    curve = pd.DataFrame(rows)
    curve["resolvable"] = curve.alpha >= a_min
    curve.to_parquet(os.path.join(outdir, "operating_curve.parquet"), index=False)

    cols = ["alpha", "resolvable", "eff_all_mu", "eff_mu_ge", "real",
            "real_multicomponent", "deterministic_max",
            "adverse_differential_scattering", "adverse_scintillation"]
    cols = [c for c in cols if c in curve]
    print(f"\n[W3b.6] operating curve (efficiency at mu >= {a.mu_floor}; "
          f"FP by family):")
    print(curve[cols].to_string(index=False))

    print(f"\n[W3b.6] v1 baseline for reference (M > 0, no multiplicity penalty): "
          f"eff_all={float((inj.M > 0).mean()):.4f} "
          f"eff_mu_ge={float((bright.M > 0).mean()):.4f}")
    print("\n[W3b.6] efficiency by mu at each alpha:")
    piv = pd.DataFrame({
        f"a={al}": inj.assign(ok=(inj.M > 0) & (inj.p_robust <= al))
                      .groupby("mu").ok.mean().round(3)
        for al in [0.1, 0.05, 0.02, 0.01, 0.005]})
    piv.insert(0, "v1", inj.assign(ok=inj.M > 0).groupby("mu").ok.mean().round(3))
    print(piv.to_string())

    # honesty: how much of each family's quoted tail is empirical vs extrapolated
    at_floor = nulls.groupby("family").p_robust_at_floor.mean().round(3)
    print("\n[W3b.6] fraction of realizations whose p sits at the empirical floor "
          "(no null exceeded them — tail is sample-limited, not measured):")
    print(at_floor.to_string())

    print(f"\n[W3b.6] -> {outdir}")


if __name__ == "__main__":
    main()
