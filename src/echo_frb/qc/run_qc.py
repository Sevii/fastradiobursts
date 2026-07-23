#!/usr/bin/env python3
"""Task 8 — run QC over every Tier B product + table-level checks.

Per-product checks (checks.py) + cross-table checks (source checksum matches raw
manifest, one-to-one Tier A<->Tier B, burst metadata in catalog). Failures are
resolved by routing to an exclusion code (noise failure -> E014) or to a
documented manual-review queue. Also runs a deterministic-reprocessing spot check.

Outputs:
  qc_per_product.parquet         -- one row per product, every check + values
  qc_manual_review_queue.csv     -- unresolved failures
  eligibility_table.parquet      -- updated in place (E014 routing)
  qc_summary.json                -- headline pass/fail + resolutions

Usage:
  run_qc.py --tier-b-dir DIR --tier-b-manifest TB.parquet --raw RAW.parquet \
      --catalog NORM.parquet --eligibility ELIG.parquet --out-dir OUT \
      [--determinism-sample 25] [--config preprocessing_config.yaml] \
      [--source-root DIR] [--workers N]
"""
import argparse
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import h5py
import numpy as np
import pandas as pd

from echo_frb.qc.checks import check_product, failed_checks, overall_pass


def load_product(path):
    with h5py.File(path, "r") as f:
        return dict(
            standardized=f["standardized"][()].astype(np.float32),
            original_flag=f["mask/original_flag"][()],
            original_good_freq=f["mask/original_good_freq"][()],
            project_mask=f["mask/project_mask"][()],
            robust=f["noise/robust_std"][()],
            channel_usable=f["noise/channel_usable"][()],
            offmask=f["offpulse/time_mask"][()],
            freqs=f["coords/freqs"][()],
            times=f["coords/times"][()],
            attrs={k: (v.decode() if isinstance(v, bytes) else v)
                   for k, v in f.attrs.items()},
        )


def qc_one(path, res_freq, manifest_usable):
    try:
        prod = load_product(path)
    except Exception as e:  # noqa: BLE001
        return dict(out_path=path, reopen_ok=False, overall_pass=False,
                    failed="reopen_ok", error=f"{type(e).__name__}: {e}")
    checks, values = check_product(prod, res_freq, manifest_usable)
    checks = {"reopen_ok": True, **checks}
    row = dict(out_path=path,
               tns_name=prod["attrs"].get("tns_name"),
               source_file=prod["attrs"].get("source_file"),
               source_sha256=prod["attrs"].get("source_sha256"),
               content_sha256=prod["attrs"].get("content_sha256"),
               overall_pass=overall_pass(checks),
               failed=",".join(failed_checks(checks)),
               **checks, **values)
    return row


def determinism_spotcheck(sample_paths, tb_manifest, config_path, source_root,
                          code_commit):
    """Reprocess a sample and confirm content_sha256 matches the recorded value."""
    from echo_frb.preprocess.standardize import load_config, process_one
    cfg = load_config(config_path)
    recorded = dict(zip(tb_manifest.tns_name, tb_manifest.content_sha256))
    src_sha = dict(zip(tb_manifest.tns_name, tb_manifest.source_sha256))
    import tempfile
    ok = 0
    mism = []
    with tempfile.TemporaryDirectory() as td:
        for tns in sample_paths:
            src = os.path.join(source_root, f"{tns}_stokesi_dynamic_spectrum.h5")
            row = process_one(src, td, cfg, code_commit, src_sha.get(tns))
            if row["content_sha256"] == recorded.get(tns):
                ok += 1
            else:
                mism.append(tns)
    return ok, mism


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--tier-b-manifest", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--eligibility", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--res-freq", type=float, default=0.0244140625)
    ap.add_argument("--determinism-sample", type=int, default=25)
    ap.add_argument("--config")
    ap.add_argument("--source-root")
    ap.add_argument("--code-commit", default=os.environ.get("ECHO_FRB_COMMIT", "unknown"))
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    tb = pd.read_parquet(args.tier_b_manifest)
    raw = pd.read_parquet(args.raw)
    cat = pd.read_parquet(args.catalog)
    elig = pd.read_parquet(args.eligibility)

    usable_by_name = dict(zip(tb.tns_name, tb.n_usable_channels))
    files = sorted(f for f in
                   (os.path.join(args.tier_b_dir, x) for x in os.listdir(args.tier_b_dir))
                   if f.endswith("_tierb.h5"))
    print(f"[qc] {len(files)} products")

    rows, done = [], 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(qc_one, p, args.res_freq,
                          usable_by_name.get(os.path.basename(p).replace("_tierb.h5", ""))): p
                for p in files}
        for fut in as_completed(futs):
            rows.append(fut.result())
            done += 1
            if done % 500 == 0 or done == len(files):
                print(f"[qc] {done}/{len(files)}", flush=True)
    qc = pd.DataFrame(rows)

    # ---- table-level checks ----
    raw_sha = dict(zip(raw.relpath.map(os.path.basename), raw.sha256))
    qc["source_checksum_matches"] = qc.apply(
        lambda r: raw_sha.get(r.get("source_file")) == r.get("source_sha256"), axis=1)
    qc["one_to_one_source"] = ~qc.duplicated("source_file", keep=False)
    cat_tns = set(cat.tns_name)
    qc["metadata_in_catalog"] = qc.tns_name.isin(cat_tns)
    for col in ["source_checksum_matches", "one_to_one_source", "metadata_in_catalog"]:
        qc["overall_pass"] &= qc[col].fillna(False)
        qc["failed"] = qc.apply(
            lambda r: r["failed"] + ("," if r["failed"] and not r[col] else "")
            + (col if not r[col] else ""), axis=1)

    qc.to_parquet(os.path.join(args.out_dir, "qc_per_product.parquet"), index=False)

    # ---- resolve failures ----
    # noise-estimation failure -> E014 (excluded)
    noise_fail = qc[~qc["noise_positive_finite"].fillna(False)]
    e014_tns = set(noise_fail.tns_name.dropna())
    if e014_tns:
        m = elig.tns_name.isin(e014_tns)
        elig.loc[m, "status"] = "excluded"
        elig.loc[m, "primary_reason"] = "E014_NOISE_ESTIMATION_FAILURE"
        elig.loc[m, "reversible"] = True
        elig.loc[m, "explanation"] = "QC: noise estimate not positive/finite (0 usable channels)"
        elig.to_parquet(args.eligibility, index=False)

    # any OTHER failure -> manual review queue
    other_fail = qc[(~qc["overall_pass"]) & (~qc.tns_name.isin(e014_tns))]
    other_fail[["tns_name", "out_path", "failed"]].to_csv(
        os.path.join(args.out_dir, "qc_manual_review_queue.csv"), index=False)

    # ---- determinism spot check ----
    det_ok, det_mism = None, []
    if args.config and args.source_root and args.determinism_sample > 0:
        step = max(1, len(tb) // args.determinism_sample)
        sample = list(tb.sort_values("tns_name").tns_name.iloc[::step][:args.determinism_sample])
        det_ok, det_mism = determinism_spotcheck(
            sample, tb, args.config, args.source_root, args.code_commit)

    # ---- summary ----
    check_cols = [c for c in qc.columns if qc[c].dtype == bool]
    summary = dict(
        n_products=len(qc),
        n_pass=int(qc.overall_pass.sum()),
        n_fail=int((~qc.overall_pass).sum()),
        per_check_fail_counts={c: int((~qc[c].fillna(False)).sum())
                               for c in check_cols if c != "overall_pass"},
        resolved_E014=sorted(e014_tns),
        manual_review_queue=int(len(other_fail)),
        determinism_sample=(None if det_ok is None else
                            dict(checked=args.determinism_sample, matched=det_ok,
                                 mismatched=det_mism)),
    )
    with open(os.path.join(args.out_dir, "qc_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
