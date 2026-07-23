#!/usr/bin/env python3
"""Task 3 — master observation manifest (one row per .h5 observation).

Extracts identity, integrity, coordinate, mask/usable, and catalog-association
fields from every Tier A .h5, joins the SHA-256 from the Task 2 checksum
manifest, and writes observation_manifest.parquet.

Fields requiring the external Catalog 2 metadata table (e.g. catalog S/N,
morphology label) are left null and flagged `pending_catalog_table=True`.
Processing-traceability fields (Tier B) are left null until Task 6.

Read-only on source files.

Usage:
  build_manifest.py --root DIR --checksums CKSUM.parquet --out OUT.parquet
                    [--workers N]
"""
import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone

import h5py
import numpy as np
import pandas as pd

REQUIRED = [
    "data", "flag", "good_freq", "index_map/freqs", "index_map/times",
    "index_map/times_unix", "times", "statistics/mean",
    "statistics/central_moment_2", "statistics/central_moment_3",
    "statistics/central_moment_4", "statistics/nsample",
]
OPTIONAL = [
    "model", "calibration/flux_conversion_factor",
    "calibration/spectrum", "calibration/good_freq",
]


def _attr(a, key, default=None):
    v = a.get(key, default)
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.generic):
        return v.item()
    return v


def is_monotonic(x, increasing=True):
    d = np.diff(x)
    return bool(np.all(d > 0)) if increasing else bool(np.all(d < 0))


def extract(path):
    row = {"abspath": path, "filename": os.path.basename(path),
           "readable": False, "error": None}
    try:
        with h5py.File(path, "r") as f:
            a = f.attrs
            present = set()

            def visit(name, obj):
                if isinstance(obj, h5py.Dataset):
                    present.add(name)
            f.visititems(visit)

            missing_required = [k for k in REQUIRED if k not in present]
            row["readable"] = True
            row["missing_required"] = ",".join(missing_required)
            row["has_model"] = "model" in present
            row["has_calibration"] = (
                "calibration/flux_conversion_factor" in present)

            # ---- Identity ----
            row["tns_name"] = _attr(a, "tns_name")
            row["event_id"] = _attr(a, "event_id")
            rn = _attr(a, "repeater_name", "") or ""
            row["repeater_name"] = rn
            row["is_repeater"] = bool(rn.strip())
            row["catalog"] = _attr(a, "catalog")
            row["doi"] = _attr(a, "doi")
            row["beam_number"] = _attr(a, "beam_number")
            snano = _attr(a, "start_time_unix_nano")
            if snano is not None:
                row["obs_utc"] = datetime.fromtimestamp(
                    float(snano) * 1e-9, tz=timezone.utc).isoformat()
            row["stokes"] = _attr(a, "stokes")
            row["telescope"] = _attr(a, "telescope")

            # ---- Coordinates ----
            data = f["data"]
            row["data_shape"] = str(data.shape)
            row["data_dtype"] = str(data.dtype)
            row["num_freq"] = int(_attr(a, "num_freq"))
            row["num_time"] = int(_attr(a, "num_time"))
            row["unwindowed_num_time"] = int(_attr(a, "unwindowed_num_time"))
            row["res_time_s"] = float(_attr(a, "res_time"))
            row["res_freq_mhz"] = float(_attr(a, "res_freq"))
            freqs = f["index_map/freqs"][()]
            times = f["index_map/times"][()]
            row["freq_min_mhz"] = float(freqs.min())
            row["freq_max_mhz"] = float(freqs.max())
            row["freq_increasing"] = bool(freqs[1] > freqs[0])
            row["freq_monotonic"] = is_monotonic(freqs, freqs[1] > freqs[0])
            row["time_monotonic"] = is_monotonic(times, True)
            row["time_start_s"] = float(times.min())
            row["time_end_s"] = float(times.max())
            # coord/array agreement
            row["coord_freq_len_ok"] = (freqs.shape[0] == data.shape[0])
            row["coord_time_len_ok"] = (times.shape[0] == data.shape[1])

            # ---- Integrity of data values ----
            arr = data[()]
            row["n_nan"] = int(np.isnan(arr).sum())
            row["n_inf"] = int(np.isinf(arr).sum())
            row["data_min"] = float(np.nanmin(arr)) if arr.size else None
            row["data_max"] = float(np.nanmax(arr)) if arr.size else None

            # ---- Masks / usable data ----
            flag = f["flag"][()]  # True = valid
            row["orig_masked_pixel_frac"] = float(1.0 - flag.mean())
            gf = f["good_freq"][()]  # True = good channel
            row["orig_masked_channel_frac"] = float(1.0 - gf.mean())
            row["n_usable_channels"] = int(gf.sum())
            row["usable_bandwidth_mhz"] = float(gf.sum() * row["res_freq_mhz"])

            # ---- Off-pulse from pulse_emission_region ----
            per = _attr(a, "pulse_emission_region")
            nt = data.shape[1]
            if per is not None:
                per = np.asarray(per).reshape(-1, 2)
                on_start = int(per[:, 0].min())
                on_end = int(per[:, 1].max())
                row["on_pulse_start_bin"] = on_start
                row["on_pulse_end_bin"] = on_end
                row["pre_offpulse_bins"] = max(0, on_start)
                row["post_offpulse_bins"] = max(0, nt - 1 - on_end)
                row["pre_offpulse_ms"] = row["pre_offpulse_bins"] * \
                    row["res_time_s"] * 1e3
                row["post_offpulse_ms"] = row["post_offpulse_bins"] * \
                    row["res_time_s"] * 1e3
                row["total_offpulse_bins"] = (
                    row["pre_offpulse_bins"] + row["post_offpulse_bins"])

            # ---- Catalog associations (from burst_parameters_json) ----
            bp = _attr(a, "burst_parameters_json")
            if bp:
                try:
                    d = json.loads(bp)

                    def first(k):
                        v = d.get(k)
                        return float(v[0]) if isinstance(v, list) and v else (
                            float(v) if v is not None else None)
                    row["n_components"] = (
                        len(d.get("amplitude", [])) or None)
                    row["dm"] = first("dm")
                    row["burst_width_s"] = first("burst_width")
                    row["scattering_timescale_s"] = first("scattering_timescale")
                    row["spectral_index"] = first("spectral_index")
                    row["spectral_running"] = first("spectral_running")
                    row["amplitude"] = first("amplitude")
                    row["arrival_time_s"] = first("arrival_time")
                except Exception:  # noqa: BLE001
                    pass
            row["dm_incoherent"] = _attr(a, "dm_incoherent")

            # ---- Pending external-table fields ----
            row["catalog_snr"] = None          # needs Catalog 2 table
            row["morphology_label"] = None      # needs Catalog 2 table
            row["pending_catalog_table"] = True

            # ---- Processing traceability (Tier B — not yet) ----
            row["preprocessing_version"] = None
            row["config_hash"] = None
            row["output_sha256"] = None
            row["exclusion_status"] = "pending"
            row["primary_exclusion_reason"] = None
    except Exception as e:  # noqa: BLE001
        row["error"] = f"{type(e).__name__}: {e}"
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pattern", default="*.h5")
    ap.add_argument("--checksums", required=True,
                    help="Task 2 raw_archive_manifest parquet")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    args = ap.parse_args()

    import fnmatch
    root = os.path.abspath(args.root)
    files = sorted(
        os.path.join(dp, n)
        for dp, _d, fs in os.walk(root)
        for n in fs if fnmatch.fnmatch(n, args.pattern))
    print(f"[manifest] {len(files)} files under {root}")

    rows, done = [], 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(extract, p): p for p in files}
        for fut in as_completed(futs):
            rows.append(fut.result())
            done += 1
            if done % 250 == 0 or done == len(files):
                print(f"[manifest] {done}/{len(files)}", flush=True)

    df = pd.DataFrame(rows)

    # join checksums
    ck = pd.read_parquet(args.checksums)[["abspath", "sha256", "size_bytes",
                                          "mtime_unix"]]
    df = df.merge(ck, on="abspath", how="left")
    df["local_relpath"] = df["abspath"].map(lambda p: os.path.relpath(p, root))
    df = df.sort_values("filename").reset_index(drop=True)

    df.to_parquet(args.out, index=False)
    print(f"[manifest] wrote {args.out}  ({len(df)} rows, {len(df.columns)} cols)")

    # summary
    n_err = int(df["error"].notna().sum())
    n_unreadable = int((~df["readable"]).sum())
    print(f"[manifest] readable={len(df)-n_unreadable}/{len(df)} "
          f"errors={n_err}")
    print(f"[manifest] repeaters={int(df['is_repeater'].sum())}  "
          f"has_model={int(df['has_model'].sum())}  "
          f"has_calibration={int(df['has_calibration'].sum())}")
    miss = df[df["missing_required"].astype(bool) &
              (df["missing_required"] != "")]
    print(f"[manifest] files missing a REQUIRED dataset: {len(miss)}")
    if len(miss):
        print(miss[["filename", "missing_required"]].head(20).to_string(index=False))
    print(f"[manifest] num_time min/median/max: "
          f"{int(df.num_time.min())}/{int(df.num_time.median())}/"
          f"{int(df.num_time.max())}")


if __name__ == "__main__":
    main()
