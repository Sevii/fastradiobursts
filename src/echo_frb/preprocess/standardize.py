#!/usr/bin/env python3
"""Task 6 — deterministic Tier A -> Tier B standardization.

Produces one standardized product per source .h5, retaining: intensity dynamic
spectrum, coordinates, ORIGINAL mask (flag + good_freq), a SEPARATE project mask,
robust per-channel baseline, channel-dependent noise (robust + conventional),
off-pulse definition, and provenance (source checksum, config hash, code commit).

Determinism (completion condition): outputs depend only on (source file, config,
code). No wall-clock is embedded in the file; HDF5 datasets use track_times=False;
a content_sha256 over the logical arrays+metadata is the authoritative
reproducibility check. Re-running yields identical content_sha256.

Core functions are import-friendly and unit-tested. CLI processes a batch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import h5py
import numpy as np
import pandas as pd
import yaml


# --------------------------------------------------------------------------
# core steps
# --------------------------------------------------------------------------
def derive_offpulse(data, flag, good_freq, pulse_region, cfg):
    """Return (offpulse_time_mask[nt] bool, (on0,on1), method)."""
    nt = data.shape[1]
    guard = int(cfg["offpulse"]["guard_bins"])
    if pulse_region is not None and np.asarray(pulse_region).size >= 2:
        pr = np.asarray(pulse_region).reshape(-1, 2)
        on0 = int(pr[:, 0].min())
        on1 = int(pr[:, 1].max())
        method = "pulse_emission_region"
    else:
        valid = flag & good_freq[:, None]
        den = valid.sum(0).astype(np.float64)
        den[den == 0] = 1.0
        prof = np.where(valid, data, 0.0).sum(0) / den
        med = np.median(prof)
        mad = 1.4826 * np.median(np.abs(prof - med)) + 1e-12
        k = float(cfg["offpulse"]["derive_threshold_mad"])
        on = np.where(prof - med > k * mad)[0]
        if on.size == 0:
            peak = int(np.argmax(prof))
            on0 = on1 = peak
        else:
            on0, on1 = int(on.min()), int(on.max())
        method = "derived_profile"
    on0 = max(0, on0 - guard)
    on1 = min(nt - 1, on1 + guard)
    offmask = np.ones(nt, bool)
    offmask[on0:on1 + 1] = False
    return offmask, (on0, on1), method


def estimate_baseline_noise(data, flag, good_freq, offmask, cfg):
    """Robust per-channel baseline + noise from off-pulse samples only."""
    nf = data.shape[0]
    off_idx = np.where(offmask)[0]
    min_s = int(cfg["noise"]["min_samples"])

    vals = data[:, off_idx].astype(np.float32)
    vflag = flag[:, off_idx]
    vals = np.where(vflag, vals, np.nan)
    nsample = np.isfinite(vals).sum(1).astype(np.int64)

    with np.errstate(all="ignore"):
        baseline = np.nanmedian(vals, axis=1)
        resid = vals - baseline[:, None]
        conv_std = np.nanstd(resid, axis=1)
        mad = np.nanmedian(np.abs(resid), axis=1)
    robust_std = (1.4826 * mad).astype(np.float64)
    baseline = np.where(np.isfinite(baseline), baseline, 0.0)

    quality = (nsample >= min_s) & good_freq & np.isfinite(robust_std) & (robust_std > 0)

    # correlated-noise indicators over good channels (lightweight scalars)
    corr_time_lag1, corr_freq_adj = _correlation_indicators(resid, quality)

    robust_std = np.where(quality, robust_std, np.nan)
    conv_std = np.where(quality, conv_std, np.nan)
    return dict(baseline=baseline.astype(np.float64),
                robust_std=robust_std, conv_std=conv_std.astype(np.float64),
                nsample=nsample, quality=quality,
                corr_time_lag1=float(corr_time_lag1),
                corr_freq_adj=float(corr_freq_adj),
                n_offpulse=int(off_idx.size))


def _correlation_indicators(resid, quality):
    """Mean lag-1 temporal autocorr and adjacent-channel correlation over good chans."""
    g = np.where(quality)[0]
    if g.size < 2:
        return 0.0, 0.0
    R = np.nan_to_num(resid[g], nan=0.0)
    # temporal lag-1
    a, b = R[:, :-1], R[:, 1:]
    denom = (R * R).sum(1)
    denom[denom == 0] = 1.0
    lag1 = ((a * b).sum(1) / denom).mean() if R.shape[1] > 1 else 0.0
    # adjacent-channel correlation
    c0, c1 = R[:-1], R[1:]
    n0 = np.linalg.norm(c0, axis=1)
    n1 = np.linalg.norm(c1, axis=1)
    ok = (n0 > 0) & (n1 > 0)
    freq_adj = ((c0[ok] * c1[ok]).sum(1) / (n0[ok] * n1[ok])).mean() if ok.any() else 0.0
    return float(lag1), float(freq_adj)


def build_project_mask(flag, good_freq, bn, cfg):
    """Separate project mask (True = use). Original masks left untouched."""
    chan_ok = bn["quality"].copy()
    if cfg["project_mask"].get("mask_unstable_noise_channels", True):
        chan_ok &= bn["nsample"] >= int(cfg["noise"]["min_samples"])
    ns = float(cfg["project_mask"].get("noise_outlier_nsigma", 5.0))
    rs = bn["robust_std"]
    valid = chan_ok & np.isfinite(rs)
    if valid.sum() > 10:
        med = np.median(rs[valid])
        mad = 1.4826 * np.median(np.abs(rs[valid] - med)) + 1e-12
        outlier = np.isfinite(rs) & (np.abs(rs - med) > ns * mad)
        chan_ok &= ~outlier
    project_mask = flag & chan_ok[:, None]
    return project_mask, chan_ok


def standardize(data, flag, good_freq, pulse_region, cfg):
    """Pure standardization: returns the Tier B product dict (arrays + summary)."""
    offmask, on_range, method = derive_offpulse(data, flag, good_freq,
                                                 pulse_region, cfg)
    bn = estimate_baseline_noise(data, flag, good_freq, offmask, cfg)
    project_mask, chan_ok = build_project_mask(flag, good_freq, bn, cfg)

    standardized = (data - bn["baseline"][:, None]).astype(np.float32)
    noise_failed = (bn["n_offpulse"] < int(cfg["offpulse"]["min_offpulse_bins"])) \
        or (int(chan_ok.sum()) == 0)

    return dict(
        standardized=standardized,
        original_flag=flag,
        original_good_freq=good_freq,
        project_mask=project_mask,
        baseline=bn["baseline"],
        noise_robust_std=bn["robust_std"],
        noise_conv_std=bn["conv_std"],
        noise_nsample=bn["nsample"],
        channel_usable=chan_ok,
        offpulse_time_mask=offmask,
        summary=dict(
            offpulse_method=method,
            on_pulse_start=int(on_range[0]),
            on_pulse_end=int(on_range[1]),
            n_offpulse_bins=int(bn["n_offpulse"]),
            n_usable_channels=int(chan_ok.sum()),
            project_masked_pixel_frac=float(1.0 - project_mask.mean()),
            corr_time_lag1=bn["corr_time_lag1"],
            corr_freq_adj=bn["corr_freq_adj"],
            noise_failed=bool(noise_failed),
        ),
    )


# --------------------------------------------------------------------------
# determinism: content hash over logical arrays + metadata
# --------------------------------------------------------------------------
def content_sha256(product, provenance):
    h = hashlib.sha256()
    for key in ["standardized", "original_flag", "original_good_freq",
                "project_mask", "baseline", "noise_robust_std",
                "noise_conv_std", "noise_nsample", "channel_usable",
                "offpulse_time_mask"]:
        arr = np.ascontiguousarray(product[key])
        # NaNs hash consistently via raw bytes; canonicalize dtype
        h.update(key.encode())
        h.update(str(arr.dtype).encode())
        h.update(np.asarray(arr.shape, dtype=np.int64).tobytes())
        h.update(arr.tobytes())
    meta = {**product["summary"],
            **{k: provenance[k] for k in
               ("source_sha256", "config_hash", "preprocessing_version")}}
    h.update(json.dumps(meta, sort_keys=True, default=str).encode())
    return h.hexdigest()


# --------------------------------------------------------------------------
# io
# --------------------------------------------------------------------------
def load_tier_a(path):
    with h5py.File(path, "r") as f:
        a = f.attrs
        data = f["data"][()].astype(np.float32)
        flag = f["flag"][()]
        good_freq = f["good_freq"][()]
        freqs = f["index_map/freqs"][()]
        times = f["index_map/times"][()]
        times_unix = f["index_map/times_unix"][()]
        pr = a.get("pulse_emission_region")
        meta = dict(
            tns_name=_s(a.get("tns_name")),
            event_id=int(a["event_id"]) if "event_id" in a else -1,
            dm_incoherent=float(a["dm_incoherent"]) if "dm_incoherent" in a else float("nan"),
            res_time=float(a["res_time"]),
            res_freq=float(a["res_freq"]),
            num_time=int(a["num_time"]),
        )
    return data, flag, good_freq, freqs, times, times_unix, pr, meta


def _s(v):
    return v.decode() if isinstance(v, bytes) else v


def write_tier_b(out_path, product, coords, provenance, cfg):
    comp = cfg["output"]["compression"]
    lvl = int(cfg["output"]["compression_level"])
    kw = dict(compression=comp, compression_opts=lvl, track_times=False,
              shuffle=True)
    tmp = out_path + ".tmp"
    with h5py.File(tmp, "w") as f:
        for k, v in provenance.items():
            f.attrs[k] = v
        for k, v in product["summary"].items():
            f.attrs[k] = v
        f.create_dataset("standardized", data=product["standardized"], **kw)
        g = f.create_group("mask")
        g.create_dataset("original_flag", data=product["original_flag"], **kw)
        g.create_dataset("original_good_freq",
                         data=product["original_good_freq"], **kw)
        g.create_dataset("project_mask", data=product["project_mask"], **kw)
        b = f.create_group("baseline")
        b.create_dataset("per_channel", data=product["baseline"], **kw)
        n = f.create_group("noise")
        n.create_dataset("robust_std", data=product["noise_robust_std"], **kw)
        n.create_dataset("conventional_std", data=product["noise_conv_std"], **kw)
        n.create_dataset("nsample", data=product["noise_nsample"], **kw)
        n.create_dataset("channel_usable", data=product["channel_usable"], **kw)
        o = f.create_group("offpulse")
        o.create_dataset("time_mask", data=product["offpulse_time_mask"], **kw)
        c = f.create_group("coords")
        c.create_dataset("freqs", data=coords["freqs"], **kw)
        c.create_dataset("times", data=coords["times"], **kw)
        c.create_dataset("times_unix", data=coords["times_unix"], **kw)
    os.replace(tmp, out_path)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb", buffering=0) as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def process_one(path, out_dir, cfg, code_commit, source_sha256):
    (data, flag, good_freq, freqs, times, times_unix, pr, meta) = load_tier_a(path)
    product = standardize(data, flag, good_freq, pr, cfg)
    config_hash = cfg["_config_hash"]
    provenance = dict(
        source_file=os.path.basename(path),
        source_sha256=source_sha256 or "",
        config_hash=config_hash,
        code_commit=code_commit,
        preprocessing_version=cfg["preprocessing_version"],
        tns_name=meta["tns_name"], event_id=meta["event_id"],
        dm_incoherent=meta["dm_incoherent"], res_time=meta["res_time"],
        res_freq=meta["res_freq"], num_time=meta["num_time"],
    )
    csha = content_sha256(product, provenance)
    provenance["content_sha256"] = csha
    out_path = os.path.join(
        out_dir, os.path.basename(path).replace(
            "_stokesi_dynamic_spectrum.h5", "_tierb.h5"))
    write_tier_b(out_path, product,
                 dict(freqs=freqs, times=times, times_unix=times_unix),
                 provenance, cfg)
    row = dict(source_file=os.path.basename(path), out_path=out_path,
               tns_name=meta["tns_name"], content_sha256=csha,
               output_sha256=sha256_of(out_path),
               source_sha256=source_sha256 or "",
               config_hash=config_hash, code_commit=code_commit,
               **product["summary"])
    return row


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def load_config(path):
    cfg = yaml.safe_load(open(path))
    cfg["_config_hash"] = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--checksums", help="raw archive manifest parquet (source sha)")
    ap.add_argument("--eligibility", help="eligibility table; process eligible+provisional")
    ap.add_argument("--files", nargs="*", help="explicit source files")
    ap.add_argument("--out-manifest", required=True)
    ap.add_argument("--code-commit", default=os.environ.get("ECHO_FRB_COMMIT", "unknown"))
    ap.add_argument("--process-candidates", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    args = ap.parse_args()

    cfg = load_config(args.config)
    os.makedirs(args.out_dir, exist_ok=True)
    quarantine = set(cfg.get("quarantine", {}).get("candidates", []))

    # source sha lookup
    sha_by_name = {}
    if args.checksums:
        ck = pd.read_parquet(args.checksums)
        sha_by_name = dict(zip(ck.relpath.map(os.path.basename), ck.sha256))

    # select files
    if args.files:
        files = args.files
    elif args.eligibility:
        el = pd.read_parquet(args.eligibility)
        keep = el[el.status.isin(["eligible", "provisionally_eligible"])]
        files = [os.path.join(args.source_root, fn) for fn in keep.filename]
    else:
        import fnmatch
        files = sorted(os.path.join(dp, n)
                       for dp, _d, fs in os.walk(args.source_root)
                       for n in fs if fnmatch.fnmatch(n, "*.h5"))

    def tns_of(p):
        return os.path.basename(p).split("_stokesi", 1)[0]

    skipped = [p for p in files if tns_of(p) in quarantine and not args.process_candidates]
    todo = [p for p in files if p not in set(skipped)]
    if args.process_candidates:
        args_out = args.out_dir  # candidates would go to a quarantine dir in that run
    print(f"[preproc] {len(todo)} to process, {len(skipped)} quarantined-skipped "
          f"(config_hash={cfg['_config_hash']})")

    rows, done = [], 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_one, p, args.out_dir, cfg, args.code_commit,
                          sha_by_name.get(os.path.basename(p))): p for p in todo}
        for fut in as_completed(futs):
            try:
                rows.append(fut.result())
            except Exception as e:  # noqa: BLE001
                rows.append(dict(source_file=os.path.basename(futs[fut]),
                                 error=f"{type(e).__name__}: {e}"))
            done += 1
            if done % 200 == 0 or done == len(todo):
                print(f"[preproc] {done}/{len(todo)}", flush=True)

    df = pd.DataFrame(rows)
    df.to_parquet(args.out_manifest, index=False)
    nerr = int(df["error"].notna().sum()) if "error" in df else 0
    nfail = int(df.get("noise_failed", pd.Series(dtype=bool)).sum())
    print(f"[preproc] wrote {args.out_manifest}: {len(df)} rows, errors={nerr}, "
          f"noise_failed={nfail}, quarantined={len(skipped)}")


if __name__ == "__main__":
    main()
