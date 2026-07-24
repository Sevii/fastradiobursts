#!/usr/bin/env python3
"""Shared Tier B reader for the WP2 search (search-owned; no cross-WP coupling)."""
from __future__ import annotations

import h5py
import numpy as np


def load_tier_b(path):
    with h5py.File(path, "r") as f:
        a = dict(f.attrs)
        return dict(
            standardized=f["standardized"][()].astype(np.float32),
            project_mask=f["mask/project_mask"][()],
            robust_std=f["noise/robust_std"][()].astype(np.float64),
            channel_usable=f["noise/channel_usable"][()],
            offpulse=f["offpulse/time_mask"][()],
            times=f["coords/times"][()],
            freqs=f["coords/freqs"][()],
            res_time=float(a.get("res_time", np.nan)),
            tns_name=str(a.get("tns_name", "")),
            noise_failed=bool(a.get("noise_failed", False)),
            attrs=a,
        )


def ms_per_bin(tb):
    return float(tb["res_time"]) * 1e3
