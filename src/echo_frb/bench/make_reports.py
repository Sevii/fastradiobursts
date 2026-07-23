#!/usr/bin/env python3
"""Task 9 — render the two benchmark markdown deliverables from bench_results.json.

Writes archive_storage_benchmark.md and preprocessing_throughput_report.md, and
answers the completion-condition questions (total disk, full runtime, optimal
batch size, worker count, whether more storage is needed).

Usage:
  make_reports.py --results bench_results.json --tier-b-gb 38.0 \
     --out-dir DIR [--actual-full-runtime-min N]
"""
import argparse
import json
import os


def f2(x):
    return f"{x:.2f}"


def storage_md(r, tier_b_gb):
    p = r["projections"]
    a = r["part_a"]
    ratio = tier_b_gb / p["raw_h5_gb"]
    n_full = p["n_full_catalog"]
    # use the MEASURED average output size, not the size-biased sample mean
    avg_mb = tier_b_gb * 1000.0 / n_full
    inj = dict(dev_10k=avg_mb * 10_000 / 1000,
               validation_100k=avg_mb * 100_000 / 1000,
               production_1M=avg_mb * 1_000_000 / 1000)
    free_tb = 1.2
    stored_plan_gb = p["raw_archive_gb"] + tier_b_gb + inj["dev_10k"]
    return f"""# Archive Storage Benchmark (Task 9)

Measured on the existing workstation (16 cores, 64 GB RAM) over a size-stratified
sample of {a['n']} dynamic-spectrum files (including the largest events).

## Archive footprint (measured)

| Layer | Size |
|---|---|
| Tier A raw archive (all products, 22755 files) | {f2(p['raw_archive_gb'])} GB |
| Tier A dynamic spectra only (4536 .h5) | {f2(p['raw_h5_gb'])} GB |
| Tier B standardized (4532 .h5, gzip) | {f2(tier_b_gb)} GB |
| **Tier B / Tier A(dyn-spec) ratio** | **{f2(ratio)}** |

Per-observation output size: mean {f2(a['out_size_mb']['mean'])} MB,
median {f2(a['out_size_mb']['median'])} MB, p95 {f2(a['out_size_mb']['p95'])} MB,
max {f2(a['out_size_mb']['max'])} MB.
Per-observation input size: mean {f2(a['in_size_mb']['mean'])} MB,
max {f2(a['in_size_mb']['max'])} MB.

Average Tier B output size (measured): **{f2(avg_mb)} MB/obs**
({f2(tier_b_gb)} GB / {n_full}). The size-stratified benchmark sample over-weights
large events, so its per-file mean ({f2(a['out_size_mb']['mean'])} MB) is a
deliberate upper bound; the catalog-wide average above is the one to plan with.

## Projected storage — two models

Injection/null products are the same shape as a Tier B standardized spectrum, so
each is ~{f2(avg_mb)} MB **if fully materialized**. But the proposal (§9.4) stores
them as seeds + frozen config and **regenerates on demand**, which is the plan of
record.

| Product | Count | Materialized (upper bound) | Plan of record |
|---|---|---|---|
| Tier B (full catalog) | {n_full} | {f2(tier_b_gb)} GB (measured) | stored (regenerable) |
| Dev injections | ~10,000 | {f2(inj['dev_10k'])} GB | stored |
| Validation injections/nulls | ~100,000 | {f2(inj['validation_100k'])} GB | seeds + on-demand batches |
| Production | ~1,000,000 | {f2(inj['production_1M'])} GB | regenerated from seeds |

## Total disk requirement (defensible estimate)

- Tier A (keep, immutable): **{f2(p['raw_archive_gb'])} GB**
- Tier B (regenerable): **~{f2(tier_b_gb)} GB**
- Dev injections (materialized): **~{f2(inj['dev_10k'])} GB**
- **Stored working set through WP3 (plan of record): ~{f2(stored_plan_gb)} GB**
- Validation/production injections are **not** stored in full — regenerated from
  seeds, or materialized in transient batches that are deleted after recovery is
  recorded. Fully materializing all 100k validation products would add
  ~{f2(inj['validation_100k'])} GB (still within the current free space).

## Do we need to buy storage?

The workstation root has ~{free_tb:.1f} TB (~{free_tb*1000:.0f} GB) free. The plan-of-record
working set (~{f2(stored_plan_gb)} GB) uses well under a quarter of it, and even
full validation materialization (~{f2(stored_plan_gb + inj['validation_100k'])} GB) fits.
**No additional storage is required for WP0-WP3.** Only production-scale (~1M)
*full materialization* (~{f2(inj['production_1M'])} GB) would exceed free space —
and that is explicitly avoided by seed-based regeneration, consistent with the
proposal's staged-authorization rule (purchase only after measured need).
"""


def throughput_md(r, actual_full_min, tier_b_gb):
    a = r["part_a"]
    p = r["projections"]
    b = r["part_b_scaling"]
    scaling_rows = "\n".join(
        f"| {row['workers']} | {row['obs_per_s']:.1f} | {row['wall_s']:.1f} |"
        for row in b)
    actual = (f"\nActual full-catalog run (observed): **{actual_full_min:.1f} min**."
              if actual_full_min else "")
    return f"""# Preprocessing Throughput Report (Task 9)

Measured over a size-stratified sample of {a['n']} events (worst-case large events
included), on the existing 16-core / 64 GB workstation.

## Per-observation timing (single worker)

| Stage | mean (s) | median (s) | p95 (s) | worst (s) |
|---|---|---|---|---|
| load (Tier A read) | {a['load_s']['mean']:.3f} | {a['load_s']['median']:.3f} | {a['load_s']['p95']:.3f} | {a['load_s']['max']:.3f} |
| compute (standardize) | {a['compute_s']['mean']:.3f} | {a['compute_s']['median']:.3f} | {a['compute_s']['p95']:.3f} | {a['compute_s']['max']:.3f} |
| write (Tier B, gzip) | {a['write_s']['mean']:.3f} | {a['write_s']['median']:.3f} | {a['write_s']['p95']:.3f} | {a['write_s']['max']:.3f} |
| **total** | **{a['total_s']['mean']:.3f}** | {a['total_s']['median']:.3f} | {a['total_s']['p95']:.3f} | {a['total_s']['max']:.3f} |

- Disk read rate (effective, incl. decompress): **{a['read_rate_MBps']:.0f} MB/s**
- Disk write rate (effective, incl. gzip): **{a['write_rate_MBps']:.0f} MB/s**
- Single-worker throughput: **{a['single_worker_obs_per_s']:.1f} obs/s**
- Peak RSS per worker (worst-case event): **{a['peak_rss_mb']:.0f} MB**

## Parallel scaling

| workers | obs/s | wall (s) for sample |
|---|---|---|
{scaling_rows}

Best: **{r['best']['workers']} workers -> {r['best']['obs_per_s']:.1f} obs/s**.

## Projections & recommendations (defensible estimates)

- **Full-catalog preprocessing runtime**: ~**{p['full_preproc_runtime_min_at_best']:.1f} min**
  at {r['best']['workers']} workers ({p['n_full_catalog']} eligible products).{actual}
- **Peak RAM per worker**: {p['peak_rss_per_worker_gb']:.2f} GB -> RAM-limited worker
  ceiling on 64 GB (80%) ~= {p['ram_limited_workers']} workers.
- **Recommended workers**: **{p['recommended_workers']}** (min of throughput-optimal,
  RAM-limited, and core count).
- **Optimal batch size**: embarrassingly parallel per-event; a batch of a few
  hundred events per scheduler dispatch keeps all workers saturated with
  negligible overhead. No RAM pressure at the recommended worker count
  ({p['recommended_workers']} x {p['peak_rss_per_worker_gb']:.2f} GB <<< 64 GB).
- **GPU**: not used by the standardization pipeline (CPU/storage-bound), matching
  the proposal's expectation.

## Completion-condition answers

| Question | Answer |
|---|---|
| Total disk requirement | ~{p['raw_archive_gb']:.0f} GB Tier A + ~{tier_b_gb:.0f} GB Tier B measured (+injections); see storage report |
| Full preprocessing runtime | ~{p['full_preproc_runtime_min_at_best']:.1f} min at {r['best']['workers']} workers |
| Optimal batch size | few hundred events/dispatch (embarrassingly parallel) |
| Number of parallel workers | {p['recommended_workers']} |
| Additional storage necessary? | No (workstation has ample headroom for WP0-WP3) |
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--tier-b-gb", type=float, required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--actual-full-runtime-min", type=float, default=None)
    args = ap.parse_args()

    r = json.load(open(args.results))
    os.makedirs(args.out_dir, exist_ok=True)
    sp = os.path.join(args.out_dir, "archive_storage_benchmark.md")
    tp = os.path.join(args.out_dir, "preprocessing_throughput_report.md")
    open(sp, "w").write(storage_md(r, args.tier_b_gb))
    open(tp, "w").write(throughput_md(r, args.actual_full_runtime_min, args.tier_b_gb))
    print(f"[reports] wrote {sp}")
    print(f"[reports] wrote {tp}")


if __name__ == "__main__":
    main()
