#!/usr/bin/env python3
"""Task 1 — authoritative data-source inventory.

Groups the full raw-archive manifest by top-level product and stamps the
authoritative source metadata (CADC VOSpace, DOI 25.0066), producing
data_source_inventory.parquet + a printed table.

Usage:
  build_inventory.py --raw RAW_MANIFEST.parquet --out INVENTORY.parquet
                     [--retrieval-utc ISO]
"""
import argparse
import os

import pandas as pd

SOURCE = "CADC VOSpace /AstroDataCitationDOI/CISTI.CANFAR/25.0066 (public, anon)"
RELEASE = "The Second CHIME/FRB Catalog of Fast Radio Bursts; DOI 10.11570/25.0066"

# product interpretation keyed by top-level relpath component
PRODUCTS = {
    "dynamic_spectra": ("Stokes-I dynamic spectra (.h5) + plots", "primary science data"),
    "localizations": ("Per-event localization products (.h5) + plots", "supporting"),
    "table": ("Catalog metadata table (csv/fits/json/npy)", "metadata"),
    "exposure": ("Exposure maps/metadata", "supporting"),
    "additional_figures": ("Additional waterfall figures", "documentation/figures"),
}


def top(relpath):
    return relpath.split(os.sep, 1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--retrieval-utc", default="")
    args = ap.parse_args()

    df = pd.read_parquet(args.raw)
    df["product"] = df["relpath"].map(top)
    df["ext"] = df["relpath"].map(lambda p: os.path.splitext(p)[1].lstrip(".") or "none")

    rows = []
    for prod, g in df.groupby("product"):
        desc, role = PRODUCTS.get(prod, ("(unrecognized)", "review"))
        ext_counts = g["ext"].value_counts().to_dict()
        rows.append({
            "product": prod,
            "description": desc,
            "role": role,
            "file_count": len(g),
            "total_gb": round(g["size_bytes"].sum() / 1e9, 3),
            "extensions": ", ".join(f"{k}:{v}" for k, v in ext_counts.items()),
            "source": SOURCE,
            "release": RELEASE,
            "retrieval_utc": args.retrieval_utc,
            "access_status": "public",
        })
    inv = pd.DataFrame(rows).sort_values("product").reset_index(drop=True)
    inv.to_parquet(args.out, index=False)

    total = pd.DataFrame([{
        "product": "TOTAL", "description": "", "role": "",
        "file_count": int(inv.file_count.sum()),
        "total_gb": round(float(inv.total_gb.sum()), 3),
        "extensions": "", "source": "", "release": "",
        "retrieval_utc": "", "access_status": "",
    }])
    show = pd.concat([inv, total], ignore_index=True)
    print(f"[inventory] wrote {args.out}")
    print(show[["product", "description", "role", "file_count",
                "total_gb", "extensions"]].to_string(index=False))


if __name__ == "__main__":
    main()
