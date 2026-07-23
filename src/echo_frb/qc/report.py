#!/usr/bin/env python3
"""Task 8 — catalog-wide distribution QC + self-contained HTML summary.

Generates the required catalog-wide distributions, flags outliers (for
investigation, not removal), and assembles catalog_qc_summary.html embedding the
per-check pass/fail table, the distribution figure, and eligibility counts.

Usage:
  report.py --manifest OBS.parquet --tier-b-manifest TB.parquet \
     --eligibility ELIG.parquet --qc QC.parquet --raw RAW.parquet \
     --tier-b-dir DIR --qc-summary qc_summary.json --out-html OUT.html
"""
import argparse
import base64
import io
import json
import os

import h5py
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def per_event_noise_baseline(tier_b_dir, tns_list):
    med_noise, med_base = {}, {}
    for tns in tns_list:
        p = os.path.join(tier_b_dir, f"{tns}_tierb.h5")
        if not os.path.exists(p):
            continue
        with h5py.File(p, "r") as f:
            rob = f["noise/robust_std"][()]
            usable = f["noise/channel_usable"][()]
            base = f["baseline/per_channel"][()]
        ru = rob[usable]
        med_noise[tns] = float(np.nanmedian(ru)) if ru.size else np.nan
        med_base[tns] = float(np.nanmedian(base))
    return med_noise, med_base


def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=90, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def distributions_figure(df):
    panels = [
        ("h5 size (MB)", df["size_mb"], False),
        ("num_time (bins)", df["num_time"], True),
        ("usable bandwidth (MHz)", df["usable_bandwidth_mhz"], False),
        ("orig masked-pixel frac", df["orig_masked_pixel_frac"], False),
        ("project masked frac", df["project_masked_frac"], False),
        ("off-pulse bins", df["n_offpulse_bins"], True),
        ("median baseline", df["median_baseline"], False),
        ("median channel noise", df["median_noise"], False),
        ("catalog S/N", df["catalog_snr"], True),
        ("dispersion measure", df["dm"], False),
        ("corr noise lag-1", df["corr_time_lag1"], False),
        ("n usable channels", df["n_usable_channels"], False),
    ]
    fig, axes = plt.subplots(4, 3, figsize=(15, 14))
    for ax, (title, series, logx) in zip(axes.ravel(), panels):
        s = pd.to_numeric(series, errors="coerce").dropna()
        if logx:
            s = s[s > 0]
            ax.hist(s, bins=np.logspace(np.log10(s.min()), np.log10(s.max()), 50)
                    if len(s) else 10)
            ax.set_xscale("log")
        else:
            ax.hist(s, bins=50)
        ax.set_title(title, fontsize=11)
        ax.set_yscale("log")
    fig.suptitle("Catalog-wide distributions (Tier B eligible set)", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    return fig


def outliers(df):
    def top(col, n, asc):
        d = df[["tns_name", col]].dropna().sort_values(col, ascending=asc).head(n)
        return [(r.tns_name, round(float(r[col]), 4)) for _, r in d.iterrows()]
    return {
        "highest masked-pixel frac": top("orig_masked_pixel_frac", 5, False),
        "lowest usable bandwidth": top("usable_bandwidth_mhz", 5, True),
        "fewest off-pulse bins": top("n_offpulse_bins", 5, True),
        "highest channel noise": top("median_noise", 5, False),
        "largest |corr lag-1|": top("corr_time_lag1", 5, False),
        "highest S/N": top("catalog_snr", 5, False),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--tier-b-manifest", required=True)
    ap.add_argument("--eligibility", required=True)
    ap.add_argument("--qc", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--qc-summary", required=True)
    ap.add_argument("--out-html", required=True)
    args = ap.parse_args()

    man = pd.read_parquet(args.manifest)
    tb = pd.read_parquet(args.tier_b_manifest)
    elig = pd.read_parquet(args.eligibility)
    qc = pd.read_parquet(args.qc)
    raw = pd.read_parquet(args.raw)
    summary = json.load(open(args.qc_summary))

    size_mb = {os.path.basename(r): s / 1e6
               for r, s in zip(raw.relpath, raw.size_bytes)}
    df = tb.merge(man[["tns_name", "num_time", "usable_bandwidth_mhz",
                       "orig_masked_pixel_frac", "catalog_snr", "dm", "filename"]],
                  on="tns_name", how="left")
    df["size_mb"] = df["filename"].map(size_mb)
    df = df.merge(qc[["tns_name", "project_masked_frac"]], on="tns_name", how="left")

    mn, mb = per_event_noise_baseline(args.tier_b_dir, list(df.tns_name))
    df["median_noise"] = df.tns_name.map(mn)
    df["median_baseline"] = df.tns_name.map(mb)

    dist_b64 = fig_to_b64(distributions_figure(df))
    outl = outliers(df)
    status_counts = elig.status.value_counts().to_dict()

    check_cols = [c for c in qc.columns if qc[c].dtype == bool and c != "overall_pass"]
    check_rows = "".join(
        f"<tr><td>{c}</td><td>{int(qc[c].sum())}</td>"
        f"<td>{int((~qc[c].fillna(False)).sum())}</td></tr>"
        for c in check_cols)
    outl_rows = "".join(
        f"<tr><td>{k}</td><td>{', '.join(f'{t}={v}' for t, v in vv)}</td></tr>"
        for k, vv in outl.items())
    det = summary.get("determinism_sample") or {}

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>ECHO-FRB WP0 — Catalog QC Summary</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;max-width:1100px}}
h1,h2{{color:#1f3a5f}} table{{border-collapse:collapse;margin:1rem 0}}
td,th{{border:1px solid #ccc;padding:4px 10px;text-align:left}}
.ok{{color:#137333;font-weight:bold}} .bad{{color:#b00020;font-weight:bold}}
img{{max-width:100%;border:1px solid #ddd}}
.kpi{{display:inline-block;margin:0 1.5rem 1rem 0}}
.kpi b{{font-size:1.6rem;display:block;color:#1f3a5f}}
</style></head><body>
<h1>Project ECHO-FRB — WP0 Catalog QC Summary</h1>
<p>CHIME/FRB Catalog 2 dynamic spectra. Task 8 quality control over the
standardized (Tier B) products.</p>
<div>
<span class="kpi"><b>{summary['n_products']}</b>products</span>
<span class="kpi"><b class="ok">{summary['n_pass']}</b>QC pass</span>
<span class="kpi"><b class="{'ok' if summary['n_fail']==0 else 'bad'}">{summary['n_fail']}</b>QC fail</span>
<span class="kpi"><b>{det.get('matched','-')}/{det.get('checked','-')}</b>determinism re-run match</span>
<span class="kpi"><b>{summary['manual_review_queue']}</b>manual-review queue</span>
</div>
<h2>Failure resolution</h2>
<p>Failures assigned an exclusion code (not silently dropped):
<b>E014_NOISE_ESTIMATION_FAILURE</b> &rarr; {', '.join(summary['resolved_E014']) or 'none'}.
Unresolved failures in the manual-review queue: {summary['manual_review_queue']}.</p>
<h2>Per-check results (over {summary['n_products']} products)</h2>
<table><tr><th>check</th><th>pass</th><th>fail</th></tr>{check_rows}</table>
<h2>Eligibility status counts</h2>
<table><tr><th>status</th><th>count</th></tr>
{''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in status_counts.items())}</table>
<h2>Catalog-wide distributions</h2>
<img src="data:image/png;base64,{dist_b64}">
<h2>Outliers (flagged for investigation, not removal)</h2>
<table><tr><th>category</th><th>top events</th></tr>{outl_rows}</table>
<p style="color:#666;font-size:0.9em">Processing-time and throughput distributions
are reported in the Task 9 benchmark. Generated from versioned manifests; see
WP0_data_audit_report for provenance.</p>
</body></html>"""
    with open(args.out_html, "w") as f:
        f.write(html)
    print(f"[qc-report] wrote {args.out_html} ({len(html)//1024} KB)")
    print(f"[qc-report] status counts: {status_counts}")


if __name__ == "__main__":
    main()
