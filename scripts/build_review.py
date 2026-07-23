#!/usr/bin/env python3
"""Build the FRB Catalog 2 visual-review data bundle.

Joins the processed manifest parquet tables into one compact per-burst
``bursts.json`` (plus a ``meta.json`` legend/summary), and copies the static UI
assets into the served bundle directory. No image rendering happens here —
waterfalls are rendered on demand by ``serve_review.py``.

Run on the desktop where the data lives, e.g.::

    ~/Projects/fastradiobursts/.venv/bin/python scripts/build_review.py \
        --prep ~/frb_catalog2_prep --out ~/frb_catalog2_prep/review
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
from datetime import datetime, timezone

import pandas as pd

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ASSETS = os.path.join(HERE, "review_assets")

# ── columns pulled from each source table (join key: tns_name) ──────────────
ELIG_COLS = [
    "tns_name", "status", "primary_reason", "secondary_reasons", "explanation",
    "reversible", "is_repeater", "is_candidate", "quarantined",
    "usable_bandwidth_mhz", "num_time", "has_pulse_region", "has_calibration",
    "orig_masked_pixel_frac", "time_downsample_factor", "config_hash",
    "code_commit",
]
CAT_COLS = [
    "tns_name", "event_id", "repeater_name", "ra", "ra_err", "dec", "dec_err",
    "gl", "gb", "bonsai_snr", "snr_fitb", "bonsai_dm", "dm_fitb", "dm_fitb_err",
    "dm_exc_ne2001", "dm_exc_ymw16", "bc_width", "scat_time", "scat_time_err",
    "flux", "flux_err", "fluence", "fluence_err", "sp_idx", "sp_run",
    "high_freq", "low_freq", "peak_freq", "n_subbursts", "morphology_label",
    "catalog_is_repeater",
]
OBS_COLS = [
    "tns_name", "obs_utc", "arrival_time_s", "dm_incoherent",
    "n_usable_channels", "freq_min_mhz", "freq_max_mhz",
]

# derived catalog S/N preferred order (matches normalize_catalog.py)
def _catalog_snr(row):
    for k in ("snr_fitb", "bonsai_snr"):
        v = row.get(k)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            return v
    return None


def _clean(v):
    """JSON-safe scalar: NaN/NaT -> None, numpy -> python, round floats."""
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        # keep 6 significant digits to shrink the payload
        return float(f"{v:.6g}")
    try:
        import numpy as np
        if isinstance(v, (np.floating,)):
            return _clean(float(v))
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.bool_,)):
            return bool(v)
    except Exception:
        pass
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def read_cols(path, cols):
    df = pd.read_parquet(path)
    keep = [c for c in cols if c in df.columns]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"  note: {os.path.basename(path)} missing {missing}")
    return df[keep]


def build(prep: str, out: str) -> None:
    man = os.path.join(prep, "manifests")
    elig = read_cols(os.path.join(man, "eligibility_table.parquet"), ELIG_COLS)
    cat = read_cols(os.path.join(man, "catalog_metadata_normalized.parquet"), CAT_COLS)
    obs = read_cols(os.path.join(man, "observation_manifest.parquet"), OBS_COLS)
    tb = pd.read_parquet(os.path.join(man, "tier_b_manifest.parquet"))
    tierb_names = set(tb["tns_name"].tolist())

    df = elig.merge(cat, on="tns_name", how="left").merge(obs, on="tns_name", how="left")
    df["catalog_snr"] = df.apply(_catalog_snr, axis=1)
    df["has_tierb"] = df["tns_name"].isin(tierb_names)

    records = []
    for _, row in df.iterrows():
        rec = {k: _clean(row[k]) for k in df.columns}
        records.append(rec)
    records.sort(key=lambda r: (r.get("obs_utc") or "", r["tns_name"]))

    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "bursts.json"), "w") as f:
        json.dump(records, f, separators=(",", ":"))

    # ── meta.json: legend + summary ─────────────────────────────────────────
    status_counts = df["status"].value_counts().to_dict()
    reason_legend = {}
    rd_path = os.path.join(REPO, "config", "exclusion_reason_dictionary.yaml")
    if yaml and os.path.exists(rd_path):
        with open(rd_path) as f:
            rd = yaml.safe_load(f) or {}
        reasons = rd.get("reasons", rd)
        if isinstance(reasons, dict):
            for code, spec in reasons.items():
                if isinstance(spec, dict):
                    reason_legend[code] = spec.get("description", "")

    qc_summary = {}
    qc_path = os.path.join(prep, "quality_control", "qc_summary.json")
    if os.path.exists(qc_path):
        with open(qc_path) as f:
            qc_summary = json.load(f)

    meta = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_bursts": len(records),
        "n_with_tierb": int(df["has_tierb"].sum()),
        "n_repeaters": int(df["is_repeater"].fillna(False).astype(bool).sum()),
        "n_candidates": int(df["is_candidate"].fillna(False).astype(bool).sum()),
        "status_counts": {str(k): int(v) for k, v in status_counts.items()},
        "reason_legend": reason_legend,
        "qc_summary": qc_summary,
        "columns": [
            {"key": "tns_name", "label": "TNS name", "kind": "id"},
            {"key": "status", "label": "Status", "kind": "status"},
            {"key": "catalog_snr", "label": "S/N", "kind": "num", "fmt": ".1f"},
            {"key": "dm_fitb", "label": "DM", "kind": "num", "fmt": ".1f", "unit": "pc cm⁻³"},
            {"key": "fluence", "label": "Fluence", "kind": "num", "fmt": ".2f", "unit": "Jy ms"},
            {"key": "bc_width", "label": "Width", "kind": "num", "fmt": ".3g", "unit": "s"},
            {"key": "scat_time", "label": "Scattering", "kind": "num", "fmt": ".3g", "unit": "s"},
            {"key": "morphology_label", "label": "Morphology", "kind": "cat"},
            {"key": "is_repeater", "label": "Repeater", "kind": "bool"},
            {"key": "ra", "label": "RA", "kind": "num", "fmt": ".2f", "unit": "deg"},
            {"key": "dec", "label": "Dec", "kind": "num", "fmt": ".2f", "unit": "deg"},
        ],
    }
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # ── copy static UI assets ───────────────────────────────────────────────
    for name in ("index.html", "app.js", "style.css"):
        src = os.path.join(ASSETS, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(out, name))

    # ── convenience launcher ────────────────────────────────────────────────
    serve = os.path.join(out, "serve.sh")
    py = os.path.join(REPO, ".venv", "bin", "python")
    with open(serve, "w") as f:
        f.write("#!/usr/bin/env bash\n"
                "# Serve the review bundle. From the Mac, tunnel with:\n"
                "#   ssh -N -L 8765:localhost:8765 popos   then open http://localhost:8765\n"
                f'exec "{py}" "{os.path.join(REPO, "scripts", "serve_review.py")}" '
                f'--out "{out}" --port "${{1:-8765}}"\n')
    os.chmod(serve, 0o755)

    print(f"wrote {len(records)} bursts -> {os.path.join(out, 'bursts.json')}")
    print(f"  status: {meta['status_counts']}")
    print(f"  with Tier B waterfall: {meta['n_with_tierb']} | repeaters: {meta['n_repeaters']}"
          f" | candidates: {meta['n_candidates']}")
    print(f"  assets + meta.json copied to {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prep", default=os.path.expanduser("~/frb_catalog2_prep"),
                    help="processed-products dir (contains manifests/, quality_control/)")
    ap.add_argument("--out", default=None,
                    help="output bundle dir (default: <prep>/review)")
    args = ap.parse_args()
    out = args.out or os.path.join(args.prep, "review")
    build(args.prep, out)


if __name__ == "__main__":
    main()
