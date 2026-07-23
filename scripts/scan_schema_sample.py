#!/usr/bin/env python3
"""Confirm structural uniformity across a sample of Catalog 2 .h5 files.

Extracts the key schema fingerprint (group/dataset names, shapes, dtypes)
plus a few varying metadata fields, and reports what is constant vs. variable.
Read-only. Prototype for the Task 3 manifest extractor.

Usage: scan_schema_sample.py FILE.h5 [FILE.h5 ...]
"""
import json
import sys
import h5py
import numpy as np

EXPECTED_KEYS = [
    "data", "flag", "good_freq", "model", "times",
    "index_map/freqs", "index_map/times", "index_map/times_unix",
    "calibration/flux_conversion_factor", "calibration/good_freq",
    "calibration/spectrum",
    "statistics/mean", "statistics/central_moment_2",
    "statistics/central_moment_3", "statistics/central_moment_4",
    "statistics/nsample",
]


def fingerprint(f):
    """Return set of 'path:shape:dtype' for every dataset in the file."""
    fp = {}

    def visit(name, obj):
        if isinstance(obj, h5py.Dataset):
            fp[name] = f"{obj.shape}|{obj.dtype}"

    f.visititems(visit)
    return fp


def main():
    fingerprints = {}
    rows = []
    for path in sys.argv[1:]:
        try:
            with h5py.File(path, "r") as f:
                fp = fingerprint(f)
                # canonical fingerprint ignoring the variable time dimension
                canon = tuple(sorted(
                    k + ":" + v.split("|")[1] for k, v in fp.items()))
                fingerprints.setdefault(canon, []).append(path)
                a = f.attrs
                freqs = f["index_map/freqs"][()]
                rows.append({
                    "file": path.split("/")[-1],
                    "tns": a.get("tns_name", b"").decode() if isinstance(
                        a.get("tns_name"), bytes) else a.get("tns_name"),
                    "num_freq": int(a["num_freq"]),
                    "num_time": int(a["num_time"]),
                    "unwin_num_time": int(a["unwindowed_num_time"]),
                    "data_shape": str(f["data"].shape),
                    "dm": float(a["dm_incoherent"]),
                    "res_time": float(a["res_time"]),
                    "res_freq": float(a["res_freq"]),
                    "freq_min": float(freqs.min()),
                    "freq_max": float(freqs.max()),
                    "freq_increasing": bool(freqs[1] > freqs[0]),
                    "is_dedisp": bool(a["is_dedispersed"]),
                    "repeater": (a.get("repeater_name", b"").decode()
                                 if isinstance(a.get("repeater_name"), bytes)
                                 else a.get("repeater_name")),
                    "missing_keys": [k for k in EXPECTED_KEYS if k not in fp],
                    "extra_keys": [k for k in fp
                                   if k not in EXPECTED_KEYS],
                })
        except Exception as e:  # noqa: BLE001
            rows.append({"file": path.split("/")[-1], "ERROR": str(e)})

    print("=== per-file summary ===")
    for r in rows:
        print(json.dumps(r))
    print()
    print(f"=== distinct dtype-fingerprints: {len(fingerprints)} ===")
    for i, (canon, files) in enumerate(fingerprints.items()):
        print(f"[fingerprint {i}] {len(files)} files")
        if i == 0:
            for item in canon:
                print("   ", item)
    # variability report
    print()
    print("=== variability across sample ===")
    for field in ["num_freq", "num_time", "res_time", "res_freq",
                  "freq_min", "freq_max", "freq_increasing", "is_dedisp"]:
        vals = {r.get(field) for r in rows if field in r}
        print(f"  {field}: {sorted(vals) if len(vals) <= 8 else f'{len(vals)} distinct'}")


if __name__ == "__main__":
    main()
