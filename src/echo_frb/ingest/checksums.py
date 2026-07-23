#!/usr/bin/env python3
"""Task 2 — immutable-archive integrity baseline.

Compute SHA-256 + size + mtime for every source file under a root, in
parallel, and write:
  * <out>.parquet          -- machine-readable raw archive manifest
  * <out>.sha256           -- standard `sha256sum -c` compatible file
                              (lets a second analyst re-verify independently)

Read-only: never modifies source files. Does NOT chmod the tree (deferred
until the full download is confirmed complete, to avoid racing the fetch job).

Usage:
  checksums.py --root DIR --pattern '*.h5' --out PATH_PREFIX [--workers N]
"""
import argparse
import hashlib
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

CHUNK = 1 << 20  # 1 MiB


def sha256_file(path):
    h = hashlib.sha256()
    size = 0
    with open(path, "rb", buffering=0) as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
            size += len(block)
    st = os.stat(path)
    return {
        "abspath": path,
        "size_bytes": size,
        "sha256": h.hexdigest(),
        "mtime_unix": st.st_mtime,
    }


def find_files(root, pattern):
    import fnmatch
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pattern", default="*.h5")
    ap.add_argument("--out", required=True, help="output path prefix")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    files = find_files(root, args.pattern)
    n = len(files)
    print(f"[checksums] {n} files matching {args.pattern!r} under {root}")
    if not n:
        sys.exit("no files found")

    t0 = time.time()
    rows = []
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(sha256_file, p): p for p in files}
        for fut in as_completed(futs):
            try:
                rows.append(fut.result())
            except Exception as e:  # noqa: BLE001
                rows.append({"abspath": futs[fut], "size_bytes": -1,
                             "sha256": f"ERROR:{e}", "mtime_unix": 0.0})
            done += 1
            if done % 250 == 0 or done == n:
                el = time.time() - t0
                rate = done / el if el else 0
                print(f"[checksums] {done}/{n}  {rate:.1f} files/s  "
                      f"eta {(n-done)/rate if rate else 0:.0f}s", flush=True)

    df = pd.DataFrame(rows).sort_values("abspath").reset_index(drop=True)
    df["relpath"] = df["abspath"].map(lambda p: os.path.relpath(p, root))
    df["archive_root"] = root
    total_gb = df.loc[df.size_bytes >= 0, "size_bytes"].sum() / 1e9
    n_err = int((df.sha256.str.startswith("ERROR")).sum())

    pq = args.out + ".parquet"
    sh = args.out + ".sha256"
    df.to_parquet(pq, index=False)
    with open(sh, "w") as f:
        for _, r in df.iterrows():
            if not str(r.sha256).startswith("ERROR"):
                # sha256sum format: "<hash>  <relpath>"
                f.write(f"{r.sha256}  {r.relpath}\n")

    el = time.time() - t0
    print(f"[checksums] done: {n} files, {total_gb:.2f} GB, {n_err} errors, "
          f"{el:.0f}s ({n/el:.1f} files/s)")
    print(f"[checksums] wrote {pq}")
    print(f"[checksums] wrote {sh}  (verify: cd {root} && sha256sum -c {sh})")


if __name__ == "__main__":
    main()
