#!/usr/bin/env python3
"""Bridge W2.1 proposals -> the W2.2 χ²_copy statistic.

score_proposal extracts the two component patches around a proposal's centers and
runs copy_score over a fine delay grid (the coarse separation is already applied
by extracting B at its own center; only the residual sub-window alignment is
searched). Reused by the nulls (W2.3), adverse sims (W2.4), injections (W2.6), and
the benchmark (W2.7).
"""
from __future__ import annotations

import numpy as np

from .. import tierb_io
from . import extract, statistic as st

DEFAULT_HALFWIDTH = 8       # component patch half-width (bins); capped by sep//2
FINE_SPAN = 2.0             # residual delay search (bins) around the proposal


def halfwidth_for(sep, cap=DEFAULT_HALFWIDTH):
    return int(max(3, min(cap, sep // 2 - 1))) if sep >= 8 else max(2, sep // 2)


def score_pair(A, B, sigA, sigB, validA, validB, cfg, mpb, sep_bins,
               fine_span=FINE_SPAN):
    step = float(cfg["delay_domain"].get("grid_step_ms", 0.5)) / max(mpb, 1e-9)
    step = max(0.25, min(1.0, step))
    grid = np.arange(-fine_span, fine_span + 1e-9, step)
    mag = tuple(cfg["copy_statistic"]["magnification_bounds"])
    r = st.copy_score(A, B, sigA, sigB, validA, validB, grid, mag_bounds=mag,
                      min_pixels=32)
    r["delay_ms"] = float((sep_bins + r["best_delay_bins"]) * mpb)
    return r


def score_proposal(tb, center_a, center_b, cfg):
    mpb = tierb_io.ms_per_bin(tb)
    sep = int(center_b) - int(center_a)
    hw = halfwidth_for(sep)
    ex = extract.extract_pair(tb, center_a, center_b, hw)
    r = score_pair(ex["A"], ex["B"], ex["sigA"], ex["sigB"], ex["validA"],
                   ex["validB"], cfg, mpb, sep)
    r.pop("delay_curve", None)
    r.update(center_a=int(center_a), center_b=int(center_b), sep_bins=sep,
             halfwidth=hw)
    return r
