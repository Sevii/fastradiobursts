#!/usr/bin/env python3
"""W3b.4 — build the end-to-end null M ensembles (docs/WP3b_plan.md §3.3).

Runs every realization of every null family through the COMPLETE frozen chain and
writes one row per realization: M, M_all, the v1 decision, the winning proposal's
per-gate margins, and the burst covariates Z the conditional calibration needs.

  PYTHONPATH=src .venv/bin/python scripts/wp3b_build_nulls.py \
      --config config/wp2_analysis_config_v2.yaml \
      --split ~/frb_catalog2_prep/wp2/source_split.parquet \
      --manifests ~/frb_catalog2_prep/manifests \
      --tier-b-dir ~/frb_catalog2_prep/tier_b_standardized \
      --split-name development --workers 24 \
      --out ~/frb_catalog2_prep/wp3b/null_ensemble_development.parquet
"""
from __future__ import annotations

import argparse
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import yaml

from echo_frb.search import tierb_io
from echo_frb.search.margin import nulls as mn

_CFG = _TBDIR = _SALT = None


def _init(cfg, tbdir, salt):
    global _CFG, _TBDIR, _SALT
    _CFG, _TBDIR, _SALT = cfg, tbdir, salt


def _one(item):
    """One realization. Tier B is re-read per item — cheap next to the chain, and
    it keeps workers stateless so the ensemble is order-independent."""
    tns, family, kind, dt, mu, draw = item
    try:
        tb = tierb_io.load_tier_b(os.path.join(_TBDIR, f"{tns}_tierb.h5"))
        if tb["noise_failed"]:
            return None
        out = mn.run_realization(tb, _CFG, family, kind, dt, mu, draw, _SALT)
    except Exception as e:
        return dict(tns_name=tns, family=family, kind=kind, draw=int(draw),
                    error=str(e)[:160])
    if out is None:
        return None                       # host could not carry the injection
    return dict(tns_name=tns, error="", **out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--split-name", default="development")
    ap.add_argument("--n-adverse-hosts", type=int, default=800)
    ap.add_argument("--n-adverse-draws", type=int, default=3)
    ap.add_argument("--n-injection-hosts", type=int, default=800)
    ap.add_argument("--n-injection-draws", type=int, default=3)
    ap.add_argument("--n-surrogate-bursts", type=int, default=0, help="0 = all")
    ap.add_argument("--plan-seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config))
    salt = cfg["split"]["salt"]
    tbdir = os.path.expanduser(a.tier_b_dir)
    split = pd.read_parquet(os.path.expanduser(a.split))
    man = pd.read_parquet(os.path.join(os.path.expanduser(a.manifests),
                                       "observation_manifest.parquet"))

    sel = split[(split.split == a.split_name) & (~split.quarantined)]
    b = sel.merge(man[["tns_name", "n_subbursts"]], on="tns_name", how="left")
    b["single"] = b.n_subbursts.fillna(1) <= 1
    b = b[[os.path.exists(os.path.join(tbdir, f"{t}_tierb.h5")) for t in b.tns_name]]
    print(f"[W3b.4] {a.split_name}: {len(b)} bursts "
          f"({int((~b.single).sum())} multi-component)")

    work = mn.plan_realizations(
        b, cfg, a.n_adverse_hosts, a.n_adverse_draws, a.n_injection_hosts,
        a.n_injection_draws, a.n_surrogate_bursts,
        rng=np.random.default_rng(a.plan_seed))
    per_family = defaultdict(int)
    for w in work:
        per_family[w[1]] += 1
    print(f"[W3b.4] {len(work)} realizations across {len(per_family)} families")
    for f, n in sorted(per_family.items()):
        print(f"    {f:<34} {n:>6}")

    rows = []
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init,
                             initargs=(cfg, tbdir, salt)) as ex:
        for i, r in enumerate(ex.map(_one, work, chunksize=16)):
            if r is not None:
                rows.append(r)
            if (i + 1) % 2000 == 0:
                print(f"[W3b.4] {i + 1}/{len(work)}", flush=True)

    df = pd.DataFrame(rows)
    # the hard-null stratum: same realizations, reported as its own family so
    # p^robust = max_h sees it undiluted (see margin/nulls.py docstring)
    multi = set(b[~b.single].tns_name)
    df["is_multicomponent"] = df.tns_name.isin(multi)
    df = df.merge(sel[["tns_name", "source_id", "is_repeater"]], on="tns_name",
                  how="left")
    hard = df[(df.family == "real") & df.is_multicomponent].copy()
    hard["family"] = "real_multicomponent"
    df = pd.concat([df, hard], ignore_index=True)

    out = os.path.expanduser(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.to_parquet(out, index=False)

    err = df[df.error != ""] if "error" in df else df.iloc[:0]
    ok = df[df.error == ""] if "error" in df else df
    print(f"\n[W3b.4] {len(ok)} realizations scored, {len(err)} errored, "
          f"{len(work) - len(df) + len(hard)} hosts skipped (edge guard)")

    g = ok.groupby("family")
    summ = pd.DataFrame(dict(
        n=g.size(),
        sources=g.source_id.nunique(),
        v1_pass=g.is_candidate_v1.mean().round(4),
        M_p50=g.M.quantile(0.50).round(3),
        M_p90=g.M.quantile(0.90).round(3),
        M_p99=g.M.quantile(0.99).round(3),
        M_max=g.M.max().round(3),
        frac_M_gt0=g.M.apply(lambda s: float((s > 0).mean())).round(4),
    )).sort_values("frac_M_gt0", ascending=False)
    print("\n[W3b.4] end-to-end per-family summary "
          "(v1_pass == frac_M_gt0 by construction):")
    print(summ.to_string())
    if len(err):
        print("\n[W3b.4] errors:", err.error.value_counts().head().to_dict())
    print(f"\n[W3b.4] -> {out}")


if __name__ == "__main__":
    main()
