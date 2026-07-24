#!/usr/bin/env python3
"""W2.7 (completion) — the FULL candidate criterion = copy score + robustness.

The copy criterion alone leaves ~8% real-null FP and passes scintillation. The
proposal's mandatory robustness diagnostics (W2.5) are what reject those. This
applies the full criterion (copy-quality AND robustness n_pass >= NPASS_MIN) to
samples of the real null, the adverse sims, and injected copies, so the gate
reflects the actual candidate definition — not the copy score in isolation.
"""
from __future__ import annotations

import argparse
import hashlib
import os

import numpy as np
import pandas as pd
import yaml

from .. import tierb_io
from ..adverse import generators as gen
from ..copy import score as scoremod
from ..robustness import diagnostics as diag
from ..tier1 import profile

DELTA_MIN, NCC_MIN, RED_MAX, NPASS_MIN = 100.0, 0.40, 1.5, 7


def _copy_ok(r):
    return (r["delta_chi2"] > DELTA_MIN and r["ncc"] > NCC_MIN
            and r["reduced_chi2"] < RED_MAX)


def _full(tb, ca, cb, cfg):
    r = scoremod.score_proposal(tb, ca, cb, cfg)
    copy_ok = _copy_ok(r)
    npass, achroma, resid = np.nan, False, False
    if copy_ok:                                   # robustness only on copy-survivors
        d = diag.run_all(tb, ca, cb, cfg)
        npass = d["n_pass"]
        achroma = bool(d["achromaticity_ok"])
        resid = bool(d["residual_structure_pass"])
    # candidate = detectable + copy-like + MANDATORY achromaticity + noise-like
    # residual + broad robustness (vote). Achromaticity is not a mere vote.
    full_ok = bool(copy_ok and achroma and resid and npass is not np.nan
                   and npass >= NPASS_MIN)
    return dict(copy_ok=copy_ok, n_pass=npass, achromaticity_ok=achroma,
                full_ok=full_ok)


def _rng(tns, salt):
    return np.random.default_rng(int(hashlib.sha256(f"{salt}:{tns}".encode()).hexdigest()[:8], 16))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--proposals", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--n-real", type=int, default=500)
    ap.add_argument("--n-inject", type=int, default=400)
    ap.add_argument("--n-adverse-hosts", type=int, default=120)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config)); salt = cfg["split"]["salt"]
    tbdir = os.path.expanduser(a.tier_b_dir)
    props = pd.read_parquet(a.proposals)
    split = pd.read_parquet(a.split)
    man = pd.read_parquet(os.path.join(a.manifests, "observation_manifest.parquet"))
    dev = props[(props.split == "development") & (~props.quarantined)]
    tbcache = {}

    def tb(tns):
        if tns not in tbcache:
            p = os.path.join(tbdir, f"{tns}_tierb.h5")
            tbcache[tns] = tierb_io.load_tier_b(p) if os.path.exists(p) else None
        return tbcache[tns]

    rows = []
    # --- REAL null: sample dev proposals, full criterion ---
    real = dev.sample(min(a.n_real, len(dev)), random_state=0)
    for p in real.itertuples():
        t = tb(p.tns_name)
        if t is None or t["noise_failed"]:
            continue
        f = _full(t, p.center_a, p.center_b, cfg)
        rows.append(dict(construction="real", **f))

    # --- INJECTED copies + ADVERSE: real single-component hosts ---
    single = man[man.get("n_subbursts", 1).fillna(1) <= 1].tns_name
    hosts = [x for x in split[(split.split == "development") & (~split.quarantined)].tns_name
             if x in set(single)]
    inj_done = 0
    for tns in hosts:
        if inj_done >= a.n_adverse_hosts:
            break
        t = tb(tns)
        if t is None or t["noise_failed"]:
            continue
        c = int(np.argmax(profile.build_profile(t)["I"]))
        nt = t["standardized"].shape[1]
        if c + 8 >= nt - 5 or c < 5:
            continue
        inj_done += 1
        rng = _rng(tns, salt)
        for kind in ("achromatic_copy", "scintillation", "drift", "differential_dm",
                     "chromatic_echo", "differential_scattering"):
            mu = 0.5
            t2 = gen.inject(t, c, 8, mu, kind, rng)
            f = _full(t2, c, c + 8, cfg)
            rows.append(dict(construction=("injection" if kind == "achromatic_copy"
                                           else f"adverse:{kind}"), **f))

    df = pd.DataFrame(rows)
    os.makedirs(a.out_dir, exist_ok=True)
    df.to_parquet(os.path.join(a.out_dir, "full_criterion.parquet"), index=False)

    def rate(sub, col):
        return round(float(sub[col].mean()), 4) if len(sub) else np.nan

    L = ["# WP2 Full-criterion gate (copy score + robustness n_pass>=7)\n"]
    for cons, g in df.groupby("construction"):
        L.append(f"- {cons:<26} n={len(g):>4}  copy_pass={rate(g,'copy_ok'):.3f}  "
                 f"FULL_pass={rate(g,'full_ok'):.3f}")
    inj = df[df.construction == "injection"]
    realn = df[df.construction == "real"]
    adv = df[df.construction.str.startswith("adverse")]
    L.append(f"\nEfficiency (injected copies, full criterion): {rate(inj,'full_ok')}")
    L.append(f"Real-null FP: copy-only={rate(realn,'copy_ok')} -> FULL={rate(realn,'full_ok')}")
    L.append(f"Adverse pass (full criterion), max over kinds: "
             f"{round(float(adv.groupby('construction').full_ok.mean().max()),4)}")
    out = "\n".join(L)
    open(os.path.join(a.out_dir, "full_criterion_report.md"), "w").write(out)
    print(out)


if __name__ == "__main__":
    main()
