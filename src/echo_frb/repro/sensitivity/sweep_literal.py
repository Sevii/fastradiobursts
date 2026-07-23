#!/usr/bin/env python3
"""W1.5 — comprehensive one-axis-at-a-time sensitivity sweep of the LITERAL pipeline.

Runs the authors' pipeline over the 340-set under many configs, collecting each
run's candidate list from the RETURN VALUE of process_frb_catalog_lens (so
save_figure=False; no figures, no CSV parsing). Smoothing method is selected by
the parameterized `smoothing` module (never by editing source). Seed=42 fixed.

Importing the authors' SearchLensedFRB.py triggers its module-level N=340 run, so
we first write an importable `SearchLensedFRB_lib.py` with that trailing driver
call stripped (analysis logic untouched).
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

import pandas as pd

from . import smoothing

DRIVER_MARKER = "results = process_frb_catalog_lens("


def make_lib(working_copy: str) -> str:
    """Write an importable copy with the trailing module-level driver removed."""
    src_path = os.path.join(working_copy, "SearchLensedFRB.py")
    lib_path = os.path.join(working_copy, "SearchLensedFRB_lib.py")
    with open(src_path, encoding="utf-8") as f:
        text = f.read()
    cut = text.find("\n" + DRIVER_MARKER)
    if cut == -1:
        raise RuntimeError("driver call not found; cannot build importable lib")
    with open(lib_path, "w", encoding="utf-8") as f:
        f.write(text[:cut] + "\n")
    return lib_path


def baseline():
    return dict(name="G_3", method="gaussian", window_length=20, polyorder=3,
                smooth_sigma=3, threshold=3, rfi_factor=3, f_down=32,
                n_noise=30, min_diff_threshold=0.1)


def default_configs():
    """Baseline G_3 plus one-axis-at-a-time variants (comprehensive)."""
    b = baseline()
    cfgs = [dict(b)]
    # smoothing method (savgol) -- parameterized, not source-toggled
    cfgs.append({**b, "name": "SG_20", "method": "savgol", "window_length": 20})
    cfgs.append({**b, "name": "SG_100", "method": "savgol", "window_length": 100})
    # priority: spike threshold
    for t in (2, 2.5, 3.5, 4):
        cfgs.append({**b, "name": f"threshold_{t}", "threshold": t})
    # priority: gaussian sigma
    for s in (2, 5):
        cfgs.append({**b, "name": f"smoothsigma_{s}", "smooth_sigma": s})
    # secondary preprocessing axes
    for r in (2, 4):
        cfgs.append({**b, "name": f"rfi_{r}", "rfi_factor": r})
    for fd in (16, 64):
        cfgs.append({**b, "name": f"fdown_{fd}", "f_down": fd})
    for nn in (20, 40):
        cfgs.append({**b, "name": f"nnoise_{nn}", "n_noise": nn})
    for md in (0.05, 0.2):
        cfgs.append({**b, "name": f"mindiff_{md}", "min_diff_threshold": md})
    return cfgs


def run_sweep(working_copy, catalog_file, data_dir, out_dir, configs):
    sys.path.insert(0, working_copy)
    import modules.analysis_data as ad          # noqa: E402
    smoothing.install(ad)                        # route detector through _CFG
    make_lib(working_copy)
    slib = importlib.import_module("SearchLensedFRB_lib")

    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for cfg in configs:
        smoothing.set_smoothing(cfg["method"], cfg["window_length"], cfg["polyorder"])
        run_out = os.path.join(out_dir, "runs", cfg["name"])
        print(f"\n===== [{cfg['name']}] {cfg} =====", flush=True)
        results = slib.process_frb_catalog_lens(
            catalog_file=catalog_file, data_dir=data_dir, output_dir=run_out,
            f_down=cfg["f_down"], t_down=1, rfi_factor=cfg["rfi_factor"],
            time_step_ms=0.98, min_diff_threshold=cfg["min_diff_threshold"],
            smooth_sigma=cfg["smooth_sigma"], threshold=cfg["threshold"],
            n_noise=cfg["n_noise"], n_bootstrap=1000, random_seed=42,
            save_figure=False, show_plots=False, N=340)
        for r in results:
            rows.append(dict(
                config=cfg["name"], frb_name=r.get("frb_name"),
                is_candidate=bool(r.get("lens_candidate", False)),
                has_drift=bool(r.get("has_drift", False)),
                n_spikes=len(r.get("spike_times", []) or []),
                status=r.get("status", "success"),
            ))
        ncand = sum(1 for r in results if r.get("lens_candidate"))
        print(f"[{cfg['name']}] candidates={ncand}", flush=True)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--working-copy", required=True)
    ap.add_argument("--catalog-file", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    df = run_sweep(a.working_copy, a.catalog_file, a.data_dir, a.out_dir,
                   default_configs())
    out = os.path.join(a.out_dir, "sweep_literal_long.parquet")
    df.to_parquet(out, index=False)
    print(f"\n[sweep_literal] wrote {out}: {len(df)} rows, "
          f"{df.config.nunique()} configs")
    print(df[df.is_candidate].groupby("config").size().to_string())


if __name__ == "__main__":
    main()
