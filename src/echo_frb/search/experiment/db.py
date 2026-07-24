#!/usr/bin/env python3
"""W2.0 — experiment database (proposal §9.3): an append-only run manifest.

Every WP2 step logs one row binding config_hash · code_commit · seed · inputs ·
outputs (path + sha256) · a short params blob, so any score/table traces back to
the exact code + config + data that produced it. Deliberately minimal and
deterministic-friendly (no wall-clock in the keyed content).
"""
from __future__ import annotations

import hashlib
import json
import os

import pandas as pd

COLUMNS = ["run_id", "task", "config_hash", "code_commit", "seed",
           "inputs", "params", "output_path", "output_sha256"]


def _sha256(path):
    if not path or not os.path.exists(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb", buffering=0) as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def log_run(db_path, task, config_hash, code_commit, seed, inputs, params,
            output_path):
    """Append one run record; run_id is a content hash of the keyed fields."""
    rec = dict(task=task, config_hash=str(config_hash), code_commit=str(code_commit),
               seed=seed, inputs=json.dumps(inputs, sort_keys=True),
               params=json.dumps(params, sort_keys=True),
               output_path=str(output_path), output_sha256=_sha256(output_path))
    rec["run_id"] = hashlib.sha256(
        (rec["task"] + rec["config_hash"] + rec["code_commit"] +
         str(rec["seed"]) + rec["inputs"] + rec["params"] +
         rec["output_sha256"]).encode()).hexdigest()[:16]
    row = pd.DataFrame([{c: rec[c] for c in COLUMNS}])
    if os.path.exists(db_path):
        prev = pd.read_parquet(db_path)
        row = pd.concat([prev[prev.run_id != rec["run_id"]], row], ignore_index=True)
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    row.to_parquet(db_path, index=False)
    return rec["run_id"]
