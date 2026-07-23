#!/usr/bin/env python3
"""Task 1/3 — normalize the Catalog 2 metadata table and enrich the manifest.

The CHIME/FRB Catalog 2 table (chimefrbcat2.csv) is per-sub-burst (5045 rows,
4539 events). This:
  * builds catalog_metadata_normalized.parquet  -- one row per event
    (primary sub_num==0 fields + n_subbursts + derived morphology proxy);
  * enriches observation_manifest.parquet with catalog associations
    (S/N, DM, width, scattering, localization, exposure, quality flags),
    resolving the `pending_catalog_table` placeholders;
  * reports the h5<->catalog reconciliation (events lacking a dynamic spectrum).

Read-only on source; overwrites the derived manifest with provenance intact.

Usage:
  normalize_catalog.py --catalog-csv CSV --manifest OBS.parquet \
      --out-normalized NORM.parquet --out-manifest OBS.parquet
"""
import argparse

import numpy as np
import pandas as pd

# per-event scalar fields taken from the primary sub-burst (sub_num == 0)
PRIMARY_FIELDS = [
    "tns_name", "event_id", "previous_name", "repeater_name",
    "ra", "ra_err", "dec", "dec_err", "gl", "gb",
    "exp_up", "exp_low",
    "bonsai_snr", "bonsai_dm", "snr_fitb", "dm_fitb", "dm_fitb_err",
    "dm_exc_ne2001", "dm_exc_ymw16",
    "bc_width", "scat_time", "scat_time_err",
    "flux", "flux_err", "fluence", "fluence_err",
    "sp_idx", "sp_run", "high_freq", "low_freq", "peak_freq",
    "chi_sq", "dof", "flag_frac",
    "excluded_flag", "sidelobe_flag", "intrachan_flag",
    "citizen_science_flag", "catalog1_flag",
]


def normalize(cat):
    prim = cat[cat.sub_num == 0].copy()
    keep = [c for c in PRIMARY_FIELDS if c in prim.columns]
    norm = prim[keep].copy()
    # sub-burst count per event = morphology proxy
    counts = cat.groupby("tns_name").size().rename("n_subbursts")
    norm = norm.merge(counts, on="tns_name", how="left")
    norm["morphology_label"] = np.where(
        norm["n_subbursts"] > 1, "multi_component", "single_component")
    norm["catalog_is_repeater"] = norm["repeater_name"].fillna("").astype(
        str).str.strip().ne("") & norm["repeater_name"].fillna("").astype(
        str).str.strip().ne("-")
    return norm.sort_values("tns_name").reset_index(drop=True)


def enrich(manifest, norm):
    # columns to graft onto the observation manifest
    assoc = norm[[
        "tns_name", "bonsai_snr", "snr_fitb", "dm_fitb", "bc_width",
        "scat_time", "ra", "dec", "ra_err", "dec_err", "gl", "gb",
        "exp_up", "exp_low", "flux", "fluence", "n_subbursts",
        "morphology_label", "excluded_flag", "sidelobe_flag",
        "intrachan_flag", "citizen_science_flag", "catalog1_flag",
    ]].rename(columns={
        "excluded_flag": "catalog_excluded_flag",
        "sidelobe_flag": "catalog_sidelobe_flag",
        "intrachan_flag": "catalog_intrachan_flag",
        "citizen_science_flag": "catalog_citizen_science_flag",
        "catalog1_flag": "catalog_catalog1_flag",
    })
    m = manifest.drop(columns=[c for c in ("catalog_snr", "morphology_label",
                                           "pending_catalog_table")
                               if c in manifest.columns])
    m = m.merge(assoc, on="tns_name", how="left")
    m["catalog_snr"] = m["snr_fitb"].fillna(m["bonsai_snr"])
    m["pending_catalog_table"] = False
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog-csv", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out-normalized", required=True)
    ap.add_argument("--out-manifest", required=True)
    args = ap.parse_args()

    cat = pd.read_csv(args.catalog_csv)
    man = pd.read_parquet(args.manifest)
    norm = normalize(cat)
    norm.to_parquet(args.out_normalized, index=False)
    print(f"[catalog] normalized {len(cat)} rows -> {len(norm)} events "
          f"-> {args.out_normalized}")

    # reconciliation
    h5 = set(man.tns_name)
    ct = set(norm.tns_name)
    missing_h5 = sorted(ct - h5)
    print(f"[catalog] events in catalog: {len(ct)} | with .h5: {len(h5)}")
    print(f"[catalog] events WITHOUT a dynamic spectrum (.h5): "
          f"{len(missing_h5)} -> {missing_h5}")
    print(f"[catalog] .h5 events not in catalog: {len(h5 - ct)}")

    enriched = enrich(man, norm)
    enriched.to_parquet(args.out_manifest, index=False)
    print(f"[catalog] enriched manifest -> {args.out_manifest} "
          f"({len(enriched)} rows, {len(enriched.columns)} cols)")
    ce = int((enriched.catalog_excluded_flag == 1).sum())
    sl = int((enriched.catalog_sidelobe_flag == 1).sum())
    print(f"[catalog] of {len(enriched)} h5 events: catalog_excluded_flag=1: "
          f"{ce}  sidelobe_flag=1: {sl}")
    print("[catalog] morphology:", enriched.morphology_label.value_counts().to_dict())
    print("[catalog] catalog_snr present:",
          int(enriched.catalog_snr.notna().sum()), "/", len(enriched))


if __name__ == "__main__":
    main()
