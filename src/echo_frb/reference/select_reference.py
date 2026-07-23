#!/usr/bin/env python3
"""Task 5 — deterministic stratified selection of the reference set.

Picks ~30-45 observations spanning the data conditions the instructions require
(high/low S/N, narrow/broad band, single/multi component, repeaters/nonrepeaters,
strongly masked, scattered, near-boundary, RFI, unusual spectrum, limited
off-pulse), plus operationally important edge cases (un-modeled/derived off-pulse,
no-calibration, noise-estimation failures, and the 2 hard exclusions). The two
quarantined candidates are deliberately EXCLUDED (quarantine).

Selection is deterministic (metric sort, fixed counts). Writes
reference_event_index.csv with the categories each event represents, key metrics,
and empty columns for two-analyst notes + reconciliation.
"""
import argparse

import pandas as pd

CANDIDATES = {"FRB20190131D", "FRB20211115A"}


def pick(df, col, n, ascending, extra=None, exclude_na=True):
    d = df
    if extra is not None:
        d = d[extra(d)]
    if exclude_na:
        d = d[d[col].notna()]
    return list(d.sort_values(col, ascending=ascending).head(n).tns_name)


def build(manifest, elig, tierb):
    m = manifest.merge(
        elig[["tns_name", "status", "primary_reason", "secondary_reasons"]],
        on="tns_name", how="left")
    tb = tierb[["tns_name", "offpulse_method", "noise_failed",
                "n_usable_channels", "out_path"]] if len(tierb) else None
    if tb is not None:
        m = m.merge(tb, on="tns_name", how="left")
    m = m[~m.tns_name.isin(CANDIDATES)].copy()
    # manifest populates total_offpulse_bins only when pulse_emission_region exists
    m["has_pulse_region"] = m["total_offpulse_bins"].notna()

    elig_only = lambda d: d.status.isin(["eligible", "provisionally_eligible"])  # noqa: E731

    cats = {}
    def add(name, tns_list):
        for t in tns_list:
            cats.setdefault(t, set()).add(name)

    add("high_snr", pick(m, "catalog_snr", 3, False, elig_only))
    add("low_snr", pick(m, "catalog_snr", 3, True, elig_only))
    add("broadband", pick(m, "usable_bandwidth_mhz", 2, False, elig_only))
    add("narrowband", pick(m, "usable_bandwidth_mhz", 3, True, elig_only))
    add("multi_component", pick(
        m, "n_subbursts", 4, False,
        lambda d: elig_only(d) & (d.morphology_label == "multi_component")))
    add("single_component", pick(
        m, "catalog_snr", 2, False,
        lambda d: elig_only(d) & (d.morphology_label == "single_component")))
    add("repeater", pick(m, "catalog_snr", 3, False,
                         lambda d: elig_only(d) & d.is_repeater))
    add("nonrepeater", pick(m, "catalog_snr", 2, False,
                            lambda d: elig_only(d) & ~d.is_repeater))
    add("strongly_masked", pick(m, "orig_masked_pixel_frac", 3, False, elig_only))
    add("rfi_channels", pick(m, "orig_masked_channel_frac", 2, False, elig_only))
    add("scattered", pick(m, "scat_time", 3, False, elig_only))
    add("limited_offpulse", pick(m, "total_offpulse_bins", 3, True,
                                 lambda d: elig_only(d) & d.has_pulse_region))
    add("near_boundary", pick(m, "pre_offpulse_bins", 2, True,
                              lambda d: elig_only(d) & d.has_pulse_region))
    add("near_boundary", pick(m, "post_offpulse_bins", 2, True,
                              lambda d: elig_only(d) & d.has_pulse_region))
    add("unusual_spectrum", pick(m, "spectral_running", 2, True, elig_only))
    add("unusual_spectrum", pick(m, "spectral_running", 2, False, elig_only))
    add("no_calibration", pick(m, "catalog_snr", 2, False,
                               lambda d: elig_only(d) & ~d.has_calibration))
    add("derived_offpulse", pick(m, "catalog_snr", 2, False,
                                 lambda d: elig_only(d) & ~d.has_pulse_region))
    # operational edge cases
    if tb is not None:
        add("noise_failed", list(m[m.noise_failed == True].tns_name))  # noqa: E712
    add("excluded", list(m[m.status == "excluded"].tns_name))

    rows = []
    keep_cols = ["tns_name", "filename", "status", "primary_reason",
                 "catalog_snr", "usable_bandwidth_mhz", "morphology_label",
                 "n_subbursts", "is_repeater", "orig_masked_pixel_frac",
                 "orig_masked_channel_frac", "scat_time", "spectral_running",
                 "num_time", "total_offpulse_bins", "pre_offpulse_bins",
                 "post_offpulse_bins", "has_calibration", "has_pulse_region"]
    if tb is not None:
        keep_cols += ["offpulse_method", "noise_failed", "n_usable_channels"]
    mi = m.set_index("tns_name")
    for tns in sorted(cats):
        r = {c: mi.at[tns, c] if c in mi.columns else None
             for c in keep_cols if c != "tns_name"}
        r["tns_name"] = tns
        r["categories"] = ";".join(sorted(cats[tns]))
        r["plot_path"] = ""
        r["interp_autocheck"] = ""
        r["analyst_1_notes"] = ""
        r["analyst_2_notes"] = ""
        r["reconciliation"] = ""
        rows.append(r)
    out = pd.DataFrame(rows)
    front = ["tns_name", "categories", "status", "plot_path", "interp_autocheck"]
    out = out[front + [c for c in out.columns if c not in front]]
    return out.sort_values("tns_name").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--eligibility", required=True)
    ap.add_argument("--tier-b-manifest", required=True)
    ap.add_argument("--out-csv", required=True)
    args = ap.parse_args()

    m = pd.read_parquet(args.manifest)
    e = pd.read_parquet(args.eligibility)
    try:
        tb = pd.read_parquet(args.tier_b_manifest)
    except Exception:
        tb = pd.DataFrame(columns=["tns_name"])
    ref = build(m, e, tb)
    ref.to_csv(args.out_csv, index=False)
    print(f"[reference] selected {len(ref)} events -> {args.out_csv}")
    from collections import Counter
    c = Counter()
    for cs in ref.categories:
        for x in cs.split(";"):
            c[x] += 1
    print("[reference] category coverage:")
    for k in sorted(c):
        print(f"  {k:20s} {c[k]}")


if __name__ == "__main__":
    main()
