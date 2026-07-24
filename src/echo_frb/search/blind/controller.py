#!/usr/bin/env python3
"""W3.1 — the BLIND CONTROLLER: build a sealed hidden mixture (proposal §5.8 step 3).

From a SEALED seed, draw a round's hosts/nulls from its (source-disjoint) test
pool and emit three code-separated artifacts:

  items/<item_id>.h5      opaque Tier-B-shaped spectra (identifying attrs scrubbed,
                          tns_name := item_id) — the ANALYST sees only these.
  hidden_manifest.parquet item_id -> h5 file. NO truth, NO host identity.
  SEALED/hidden_labels.parquet  item_id -> {class, kind, host, Δt, μ, features}. The
                          seed is recorded here too. The analyst code must NOT read
                          this dir until scoring is committed.
  hidden_commitment.json  sha256(labels) + UTC timestamp + config hashes + seed
                          hash + total n_items. Git-committed as the pre-commitment.

Three truth classes, DISJOINT underlying bursts (independent decisions):
  * injection  — achromatic delayed copy into a real single-component host, one
                 host per item, (Δt, μ) sampled from the frozen grid (μ oversampled
                 near threshold). The POSITIVE class (efficiency).
  * real_null  — a real test burst, NO injection = catalog-representative FP.
                 Draw prioritizes the scarce multi-component bursts (H-I stress).
  * adverse    — one of the 7 non-copy imitators into a real host (μ fixed).

Deterministic given (seed, pool, config). Reuses the frozen injectors
(`adverse.generators.inject`); adds NO signal physics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone

import h5py
import numpy as np
import pandas as pd

from .. import tierb_io
from ..adverse import generators as gen
from ..tier1 import profile
from . import foundation

# attrs that could de-anonymize a host -> scrubbed from every hidden h5
_IDENTIFYING_ATTRS = ("tns_name", "source_file", "source_sha256", "content_sha256",
                      "event_id", "dm_incoherent")


def materialize(src_path, dst_path, item_id, new_std=None):
    """Copy a Tier-B h5 to an opaque hidden item: same structure, scrubbed identity.

    Every group/dataset/attr is copied through so the file is byte-structurally a
    Tier B product; `standardized` is replaced iff new_std is given; identifying
    attrs are removed and tns_name is set to the opaque item_id.
    """
    with h5py.File(src_path, "r") as fin, h5py.File(dst_path, "w") as fout:
        for k in fin.keys():
            fin.copy(k, fout)
        for k, v in fin.attrs.items():
            if k not in _IDENTIFYING_ATTRS:
                fout.attrs[k] = v
        if new_std is not None:
            del fout["standardized"]
            fout.create_dataset("standardized", data=new_std.astype(np.float32),
                                compression="gzip")
        fout.attrs["tns_name"] = item_id            # opaque label; real identity sealed


def _select_roles(pool_bursts, man, cfg, rng):
    """Disjoint real_null / injection-host / adverse-host burst sets from the pool."""
    mx = cfg["mixture"]
    feat = pool_bursts.merge(
        man[["tns_name", "n_subbursts", "catalog_snr", "burst_width_s",
             "usable_bandwidth_mhz"]], on="tns_name", how="left")
    feat["single"] = feat.n_subbursts.fillna(1) <= 1
    multi = feat[~feat.single].tns_name.to_list()
    single = feat[feat.single].tns_name.to_list()
    rng.shuffle(multi)
    rng.shuffle(single)

    # real_null: prioritize the scarce multi-component bursts, then fill with single
    n_real = mx["n_real_null"]
    real = multi[:n_real]
    real += single[:max(0, n_real - len(real))]
    used = set(real)
    single_left = [t for t in single if t not in used]

    n_inj_hosts = mx["n_injections"]                # one host per injection item
    inj_hosts = single_left[:n_inj_hosts]
    used |= set(inj_hosts)
    single_left = [t for t in single_left if t not in used]

    n_adv_hosts = mx["n_per_adverse_kind"]          # reused across the 7 kinds
    adv_hosts = single_left[:n_adv_hosts]

    return feat.set_index("tns_name"), real, inj_hosts, adv_hosts


def _sample_injections(inj_hosts, cfg, rng):
    """One (host, Δt, μ) per host; μ drawn with the near-threshold weights."""
    mx = cfg["mixture"]
    mu_grid = np.array(mx["injection_mu"], float)
    w = np.array(mx["injection_mu_weights"], float); w = w / w.sum()
    dt_grid = np.array(mx["injection_dt_bins"], int)
    out = []
    for host in inj_hosts:
        mu = float(rng.choice(mu_grid, p=w))
        dt = int(rng.choice(dt_grid))
        out.append((host, dt, mu))
    return out


def build(cfg, ana_cfg, pool_bursts, man, tbdir, seed):
    """Return (items, labels) lists of dicts. Deterministic given seed."""
    rng = np.random.default_rng(seed)
    feat, real, inj_hosts, adv_hosts = _select_roles(pool_bursts, man, cfg, rng)
    injections = _sample_injections(inj_hosts, cfg, rng)
    adv_kinds = cfg["mixture"]["adverse_kinds"]
    adv_mu = float(cfg["mixture"]["adverse_mu"])
    adv_dt = 8                                       # mid-grid, as in the WP2 benchmark

    def host_feats(tns):
        r = feat.loc[tns]
        return dict(host_snr=float(r.catalog_snr), host_width_s=float(r.burst_width_s),
                    host_bandwidth_mhz=float(r.usable_bandwidth_mhz),
                    is_multicomponent=bool(not r.single))

    work = []      # (truth_class, kind, host_tns, dt, mu)
    for host, dt, mu in injections:
        work.append(("injection", "achromatic_copy", host, dt, mu))
    for host in real:
        work.append(("real_null", "none", host, np.nan, np.nan))
    for kind in adv_kinds:
        for host in adv_hosts:
            work.append(("adverse", kind, host, adv_dt, adv_mu))

    # shuffle so item_id order leaks no class information
    order = rng.permutation(len(work))
    items, labels = [], []
    for new_i, orig_i in enumerate(order):
        cls, kind, host, dt, mu = work[orig_i]
        item_id = f"ITEM{new_i:05d}"
        items.append(dict(item_id=item_id, h5=f"{item_id}.h5"))
        lab = dict(item_id=item_id, truth_class=cls, kind=kind, host_tns=host,
                   dt_bins=(int(dt) if np.isfinite(dt) else -1),
                   mu=(float(mu) if np.isfinite(mu) else np.nan), **host_feats(host))
        labels.append(lab)
    return items, labels, {"n_real": len(real), "n_inj": len(injections),
                           "n_adv": len(adv_kinds) * len(adv_hosts)}


def render(items, labels, tbdir, out_items_dir):
    """Materialize every item's opaque h5 (injection/adverse inject; real copies)."""
    os.makedirs(out_items_dir, exist_ok=True)
    lab_by_id = {l["item_id"]: l for l in labels}
    for it in items:
        lab = lab_by_id[it["item_id"]]
        src = os.path.join(tbdir, f"{lab['host_tns']}_tierb.h5")
        dst = os.path.join(out_items_dir, it["h5"])
        if lab["truth_class"] == "real_null":
            materialize(src, dst, it["item_id"], new_std=None)
            continue
        tb = tierb_io.load_tier_b(src)
        c = int(np.argmax(profile.build_profile(tb)["I"]))
        rng = np.random.default_rng(int(hashlib.sha256(it["item_id"].encode())
                                        .hexdigest()[:8], 16))
        tb2 = gen.inject(tb, c, int(lab["dt_bins"]), float(lab["mu"]),
                         lab["kind"], rng)
        materialize(src, dst, it["item_id"], new_std=tb2["standardized"])


def _sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description="W3.1 — blind controller (sealed mixture)")
    ap.add_argument("--wp3-config", required=True)
    ap.add_argument("--analysis-config", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--pools", required=True)
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out-dir", required=True, help="round dir; SEALED/ created within")
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--seed", type=int, required=True, help="SEALED controller seed")
    ap.add_argument("--no-render", action="store_true", help="manifest+labels only (no h5)")
    ap.add_argument("--n-injections", type=int, help="override mixture.n_injections (smoke)")
    ap.add_argument("--n-real-null", type=int, help="override mixture.n_real_null (smoke)")
    ap.add_argument("--n-per-adverse-kind", type=int, help="override (smoke)")
    a = ap.parse_args()

    cfg = foundation.load_wp3_config(a.wp3_config)
    for k, v in [("n_injections", a.n_injections), ("n_real_null", a.n_real_null),
                 ("n_per_adverse_kind", a.n_per_adverse_kind)]:
        if v is not None:
            cfg["mixture"][k] = v
    foundation.assert_freeze_contract(cfg, os.path.expanduser(a.repo_root))
    ana_hash = foundation.config_sha16(os.path.join(os.path.expanduser(a.repo_root),
                                                     cfg["frozen"]["analysis_config"]))
    import yaml
    ana_cfg = yaml.safe_load(open(a.analysis_config))

    pools = pd.read_parquet(os.path.expanduser(a.pools))
    pool_idx = cfg["pools"]["round1_pool"] if a.round == 1 else \
        [p for p in sorted(pools.pool.unique()) if p != cfg["pools"]["round1_pool"]][a.round - 2]
    pool_bursts = pools[pools.pool == pool_idx][["tns_name", "source_id"]].copy()
    man = pd.read_parquet(os.path.join(os.path.expanduser(a.manifests),
                                       "observation_manifest.parquet"))
    tbdir = os.path.expanduser(a.tier_b_dir)

    items, labels, counts = build(cfg, ana_cfg, pool_bursts, man, tbdir, a.seed)
    outdir = os.path.expanduser(a.out_dir)
    sealed = os.path.join(outdir, "SEALED")
    os.makedirs(sealed, exist_ok=True)

    man_df = pd.DataFrame(items)
    lab_df = pd.DataFrame(labels)
    lab_df.attrs = {}
    man_path = os.path.join(outdir, "hidden_manifest.parquet")
    lab_path = os.path.join(sealed, "hidden_labels.parquet")
    man_df.to_parquet(man_path, index=False)
    # record the seed INSIDE the sealed labels (revealed only post-unblind)
    lab_df["_controller_seed"] = a.seed
    lab_df.to_parquet(lab_path, index=False)

    if not a.no_render:
        render(items, labels, tbdir, os.path.join(outdir, "items"))

    commitment = dict(
        wp3_version=cfg["wp3_version"], round=a.round, pool=int(pool_idx),
        n_items=len(items),
        labels_sha256=_sha256_file(lab_path),
        labels_created_utc=datetime.now(timezone.utc).isoformat(),
        wp3_config_sha16=cfg["_config_hash"],
        analysis_config_sha16=ana_hash,
        seed_sha256=hashlib.sha256(str(a.seed).encode()).hexdigest(),
    )
    commit_path = os.path.join(outdir, "hidden_commitment.json")
    json.dump(commitment, open(commit_path, "w"), indent=2)

    print(f"[W3.1] round {a.round} pool {pool_idx}: {len(items)} items "
          f"(inj={counts['n_inj']} real={counts['n_real']} adv={counts['n_adv']})")
    print(f"[W3.1] manifest -> {man_path}")
    print(f"[W3.1] SEALED labels -> {lab_path}  (sha256 {commitment['labels_sha256'][:16]}…)")
    print(f"[W3.1] commitment -> {commit_path}  ({commitment['labels_created_utc']})")
    if a.no_render:
        print("[W3.1] --no-render: spectra NOT materialized")


if __name__ == "__main__":
    main()
