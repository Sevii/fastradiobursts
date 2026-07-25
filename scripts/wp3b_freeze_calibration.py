#!/usr/bin/env python3
"""W3b.7-A — fit the calibration once and COMMIT it as a frozen artifact.

The calibration decides candidacy, so it is part of the analysis. If it can be
refit between the dry run and the blind gate, the freeze contract does not cover
the thing being tested. This script fits it from the dev null ensemble, writes the
three-file artifact, and emits `calibration_commitment.json` (sha256 + UTC
timestamp) — git-committed BEFORE the round-2 controller draws, exactly like
`hidden_commitment.json`.

Only DEVELOPMENT nulls are eligible. The dry run demonstrated that a dev-fitted
calibration transfers to validation out-of-sample; refitting on dev+validation
would raise the resolvable-alpha floor slightly but would replace a validated
calibration with an untested one (docs/WP3b_dry_run_findings.md §6).

  PYTHONPATH=src .venv/bin/python scripts/wp3b_freeze_calibration.py \
      --config config/wp2_analysis_config_v2.yaml \
      --ensemble ~/frb_catalog2_prep/wp3b/null_ensemble_development.parquet \
      --out-dir ~/frb_catalog2_prep/wp3b/calibration_v2
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import pandas as pd
import yaml

from echo_frb.search.margin import calibrate as cal

# `block_bootstrap` resamples contiguous blocks WITH REPLACEMENT and so can place
# the same block twice, MANUFACTURING an exact achromatic copy — the signal under
# test. Under p^robust = max_h a broken null silently sets the threshold for every
# other family. See docs/WP3b_dry_run_findings.md §3.
EXCLUDED = {"surrogate_block_bootstrap":
            "resamples time blocks with replacement -> manufactures exact copies; "
            "median per-band delay spread of its dev passers is exactly 0"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--ensemble", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config))
    alpha = (cfg.get("margin", {}) or {}).get("alpha")
    assert alpha is not None, (
        "config/margin.alpha is null — the decision threshold must be set from the "
        "validation dry run before the calibration can be committed (W3b.6).")

    epath = os.path.expanduser(a.ensemble)
    ens = pd.read_parquet(epath)
    if "error" in ens:
        ens = ens[ens.error == ""]
    nulls = ens[ens.truth_class == "null"]
    fams = sorted(f for f in nulls.family.unique() if f not in EXCLUDED)

    calib = cal.Calibration.fit(ens, cfg, families=fams, provenance=dict(
        source_ensemble=os.path.basename(epath),
        source_ensemble_sha256=cal.sha256_file(epath),
        analysis_version=cfg["analysis_version"],
        analysis_config=os.path.basename(a.config),
        analysis_config_sha16=cal.sha256_file(a.config)[:16],
        alpha=float(alpha),
        excluded_families=EXCLUDED,
        margin_scales=cfg["margin"]["scales"]))

    man = calib.save(a.out_dir)
    outdir = os.path.expanduser(a.out_dir)

    a_min = man["min_resolvable_alpha"]
    assert alpha >= a_min, (
        f"alpha={alpha} is BELOW the smallest resolvable alpha {a_min} "
        f"(thinnest cell {man['min_resolvable_alpha_cell']}). No burst could ever "
        f"clear it — that is a sample-size artifact, not a threshold.")

    commitment = dict(
        calibration_dir=os.path.basename(outdir),
        manifest_sha256=cal.sha256_file(os.path.join(outdir, cal.MANIFEST_FILE)),
        cells_sha256=man["cells_sha256"], values_sha256=man["values_sha256"],
        analysis_config_sha16=man["analysis_config_sha16"],
        alpha=float(alpha), n_cells=man["n_cells"],
        n_realizations=man["n_realizations"],
        min_resolvable_alpha=a_min,
        committed_utc=datetime.now(timezone.utc).isoformat())
    cpath = os.path.join(outdir, "calibration_commitment.json")
    json.dump(commitment, open(cpath, "w"), indent=2)

    print(f"[W3b.7-A] fitted {man['n_cells']} cells over {len(fams)} families "
          f"({man['n_realizations']} null realizations)")
    print(f"[W3b.7-A] excluded: {sorted(EXCLUDED)}")
    print(f"[W3b.7-A] alpha={alpha}  min_resolvable_alpha={a_min} "
          f"({man['min_resolvable_alpha_cell']})")

    # prove the artifact round-trips before anyone depends on it
    back = cal.load_calibration(outdir)
    assert back.frozen
    same = all(
        back.cells[k].n == v.n
        and (back.cells[k].u == v.u or (pd.isna(back.cells[k].u) and pd.isna(v.u)))
        for k, v in calib.cells.items())
    assert same, "round-trip mismatch — the committed calibration is not the fitted one"
    print(f"[W3b.7-A] round-trip verified ({len(back.cells)} cells reload identically)")
    print(f"[W3b.7-A] -> {outdir}")
    print(f"[W3b.7-A] commitment -> {cpath}  ({commitment['committed_utc']})")


if __name__ == "__main__":
    main()
