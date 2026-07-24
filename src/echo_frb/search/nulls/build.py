#!/usr/bin/env python3
"""W2.3 — build the three empirical-null catalogs (proposal §5.6, controls 1-3).

  real       : χ²_copy of REAL proposals in real complex bursts (the anchor null).
  surrogate  : χ²_copy of proposals in structure-preserving surrogates (3 methods).
  xpair      : χ²_copy of matched cross-event pseudo-pairs (accidental agreement).

All restricted to the DEVELOPMENT split, non-quarantined (design set). Emits the
copy-statistic score distribution per construction -> null_catalog_{name}.parquet.
"""
from __future__ import annotations

import hashlib
import os

import numpy as np
import pandas as pd

from .. import tierb_io
from ..copy import extract, score as scoremod
from . import surrogate as surr


def _seed(tns, salt):
    return int(hashlib.sha256(f"{salt}:{tns}".encode()).hexdigest()[:8], 16)


def _rng(tns, salt):
    return np.random.default_rng(_seed(tns, salt))


# ---- control 1: real complex-burst nulls ---------------------------------
def build_real(proposals, tbdir, cfg):
    rows = []
    for tns, g in proposals.groupby("tns_name"):
        path = os.path.join(tbdir, f"{tns}_tierb.h5")
        if not os.path.exists(path):
            continue
        tb = tierb_io.load_tier_b(path)
        if tb["noise_failed"]:
            continue
        for p in g.itertuples():
            r = scoremod.score_proposal(tb, p.center_a, p.center_b, cfg)
            rows.append(dict(construction="real", tns_name=tns,
                             delta_chi2=r["delta_chi2"], reduced_chi2=r["reduced_chi2"],
                             best_a=r["best_a"], ncc=r["ncc"], n_valid=r["n_valid"],
                             delay_ms=r["delay_ms"], kind=p.kind))
    return pd.DataFrame(rows)


# ---- control 3: structure-preserving surrogates --------------------------
def build_surrogate(proposals, tbdir, cfg, methods, sample_bursts, salt):
    bursts = list(dict.fromkeys(proposals.tns_name))[:sample_bursts]
    prop_by_burst = {t: g for t, g in proposals.groupby("tns_name")}
    rows = []
    for tns in bursts:
        path = os.path.join(tbdir, f"{tns}_tierb.h5")
        if not os.path.exists(path):
            continue
        tb = tierb_io.load_tier_b(path)
        if tb["noise_failed"]:
            continue
        g = prop_by_burst[tns]
        for method in methods:
            rng = _rng(f"{method}:{tns}", salt)
            sur = surr.make_surrogate(tb, method, rng)
            # re-score the same proposal windows on surrogate data (copy relation
            # destroyed) — measures FP from realistic structure minus the copy.
            for p in g.itertuples():
                r = scoremod.score_proposal(sur, p.center_a, p.center_b, cfg)
                rows.append(dict(construction=f"surrogate:{method}", tns_name=tns,
                                 delta_chi2=r["delta_chi2"], reduced_chi2=r["reduced_chi2"],
                                 best_a=r["best_a"], ncc=r["ncc"], n_valid=r["n_valid"],
                                 delay_ms=r["delay_ms"], kind=p.kind))
    return pd.DataFrame(rows)


# ---- control 2: matched cross-event pseudo-pairs -------------------------
def _match_pairs(feat, n_pairs, salt):
    """Nearest-neighbour matches across DIFFERENT sources on standardized features."""
    cols = ["burst_width_s", "catalog_snr", "usable_bandwidth_mhz",
            "scattering_timescale_s"]
    F = feat[cols].astype(float).fillna(feat[cols].astype(float).median())
    Z = (F - F.mean()) / (F.std(ddof=0) + 1e-9)
    Z = Z.to_numpy()
    src = feat.source_id.to_numpy()
    rng = np.random.default_rng(int(hashlib.sha256(salt.encode()).hexdigest()[:8], 16))
    order = rng.permutation(len(feat))[:n_pairs]
    pairs = []
    for i in order:
        d = np.sqrt(((Z - Z[i]) ** 2).sum(1))
        d[src == src[i]] = np.inf                    # different source only
        j = int(np.argmin(d))
        if np.isfinite(d[j]):
            pairs.append((i, j))
    return pairs


def build_xpair(feat, tbdir, cfg, n_pairs, salt, hw=8):
    pairs = _match_pairs(feat, n_pairs, salt)
    tns = feat.tns_name.to_numpy()
    center = feat.main_center.to_numpy()
    cache, rows = {}, []

    def load(t):
        if t not in cache:
            p = os.path.join(tbdir, f"{t}_tierb.h5")
            cache[t] = tierb_io.load_tier_b(p) if os.path.exists(p) else None
        return cache[t]

    for i, j in pairs:
        tbX, tbY = load(tns[i]), load(tns[j])
        if tbX is None or tbY is None or tbX["noise_failed"] or tbY["noise_failed"]:
            continue
        exX = extract.extract_pair(tbX, center[i], center[i], hw)   # A patch from X
        exY = extract.extract_pair(tbY, center[j], center[j], hw)   # B patch from Y
        mpb = tierb_io.ms_per_bin(tbX)
        r = scoremod.score_pair(exX["A"], exY["A"], exX["sigA"], exY["sigA"],
                                exX["validA"], exY["validA"], cfg, mpb, 0)
        rows.append(dict(construction="xpair", tns_name=f"{tns[i]}|{tns[j]}",
                         delta_chi2=r["delta_chi2"], reduced_chi2=r["reduced_chi2"],
                         best_a=r["best_a"], ncc=r["ncc"], n_valid=r["n_valid"],
                         delay_ms=r["delay_ms"], kind="xpair"))
    return pd.DataFrame(rows)
