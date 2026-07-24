#!/usr/bin/env python3
"""W2.0 — source-aware development / validation / untouched-test split.

Repeaters share a SOURCE, so the split must be at the source level (never split a
source across sets — that would leak morphology learned from one burst into
another). Assignment is deterministic and order-independent: a source's bucket is
a hash of (salt, source_id), so re-running yields the identical split with no RNG
state to carry. Quarantined events (see quarantine.py) are flagged, not dropped.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd


def source_id(tns_name, repeater_name, is_repeater):
    """Source = repeater_name for repeaters, else the burst's own tns_name."""
    if bool(is_repeater):
        rn = str(repeater_name).strip()
        if rn and rn.lower() not in ("nan", "none", ""):
            return rn
    return str(tns_name)


def _bucket(sid, salt, fractions):
    h = hashlib.sha256(f"{salt}:{sid}".encode()).hexdigest()
    u = int(h[:16], 16) / float(1 << 64)          # deterministic uniform in [0,1)
    cum = 0.0
    for name, frac in fractions.items():
        cum += frac
        if u < cum:
            return name
    return list(fractions)[-1]                     # rounding guard


def build(manifest: pd.DataFrame, eligible_tns, cfg, quarantined_tns=frozenset()):
    """Return one row per eligible burst with source_id + split + quarantined.

    manifest must carry tns_name, repeater_name, is_repeater. eligible_tns is the
    set/list of tns_name to include. Splits are computed per SOURCE then broadcast
    to that source's bursts, so all bursts of a source land in the same set.
    """
    fr = cfg["split"]["fractions"]
    salt = cfg["split"]["salt"]
    m = manifest[manifest.tns_name.isin(set(eligible_tns))].copy()
    m["source_id"] = [source_id(t, r, ir) for t, r, ir
                      in zip(m.tns_name, m.get("repeater_name"), m.is_repeater)]
    src_split = {s: _bucket(s, salt, fr) for s in m.source_id.unique()}
    m["split"] = m.source_id.map(src_split)
    m["quarantined"] = m.tns_name.isin(set(quarantined_tns))
    m["is_repeater"] = m.is_repeater.astype(bool)
    return m[["tns_name", "source_id", "is_repeater", "split", "quarantined"]] \
        .sort_values("tns_name").reset_index(drop=True)


def summary(split_df: pd.DataFrame) -> str:
    n_src = split_df.groupby("split").source_id.nunique()
    n_burst = split_df.split.value_counts()
    nq = int(split_df.quarantined.sum())
    lines = ["split      sources  bursts"]
    for s in ["development", "validation", "test"]:
        lines.append(f"{s:<11}{int(n_src.get(s,0)):>7}{int(n_burst.get(s,0)):>8}")
    lines.append(f"quarantined bursts: {nq}  | total sources: "
                 f"{split_df.source_id.nunique()}  bursts: {len(split_df)}")
    return "\n".join(lines)
