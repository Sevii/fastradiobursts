#!/usr/bin/env python3
"""Task 4 — run the schema contract over the whole archive, in parallel.

Loud detector for incompatible/malformed files at catalog scale. Writes
schema_validation.parquet (one row per file) and prints every ERROR file plus a
warning-code tally.

Usage:
  validate_catalog.py --root DIR --out schema_validation.parquet [--workers N]
"""
import argparse
import fnmatch
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

from echo_frb.schema.contract import validate_file


def _run(path):
    return validate_file(path).to_row()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pattern", default="*.h5")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    files = sorted(os.path.join(dp, n)
                   for dp, _d, fs in os.walk(root)
                   for n in fs if fnmatch.fnmatch(n, args.pattern))
    print(f"[validate] {len(files)} files under {root}")

    rows, done = [], 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(_run, p) for p in files]
        for fut in as_completed(futs):
            rows.append(fut.result())
            done += 1
            if done % 500 == 0 or done == len(files):
                print(f"[validate] {done}/{len(files)}", flush=True)

    df = pd.DataFrame(rows).sort_values("filename").reset_index(drop=True)
    df.to_parquet(args.out, index=False)

    n_ok = int(df.ok.sum())
    n_err = int((~df.ok).sum())
    print(f"\n[validate] wrote {args.out}")
    print(f"[validate] PASS={n_ok}/{len(df)}  FAIL={n_err}")

    # warning tally
    wc = Counter()
    for s in df.warning_codes:
        for c in filter(None, str(s).split(",")):
            wc[c] += 1
    print("[validate] warning tally:", dict(wc))

    if n_err:
        print("\n[validate] FILES FAILING SCHEMA (ERROR):")
        for _, r in df[~df.ok].iterrows():
            print(f"  {r.filename}: {r.error_codes}")
            print(f"      {r.messages}")
    else:
        print("[validate] no ERROR-level schema failures.")


if __name__ == "__main__":
    main()
