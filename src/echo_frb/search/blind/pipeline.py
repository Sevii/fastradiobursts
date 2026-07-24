#!/usr/bin/env python3
"""WP3 — the FROZEN end-to-end pipeline runner (shared by predict + evaluate).

`run_frozen_chain` is the single source of truth for "what does the pipeline
decide about one Tier B spectrum?" — Tier-1 triage -> per-proposal χ²_copy ->
robustness -> the full candidate criterion. Using ONE runner for both the
predicted-efficiency surface (dev) and the blind evaluation (test) guarantees the
observed-vs-predicted comparison is apples-to-apples: any difference is the data,
never a code path.

This calls ONLY frozen WP2 code (`tier1`, `copy`, `robustness`, `benchmark`) with
the frozen `wp2_analysis_config.yaml`. It adds NO analysis logic — it wires the
existing stages end-to-end exactly as the WP4 catalog scan will. The decision is
END-TO-END: an injection Tier-1 fails to propose is a genuine non-recovery (triage
loss), not silently rescued by oracle windows.
"""
from __future__ import annotations

import numpy as np

from .. import tierb_io
from ..benchmark import full_criterion as fc
from ..copy import score as scoremod
from ..tier1 import scan as tier1


def run_frozen_chain(tb, cfg):
    """Run Tier-1 -> Tier-2 full criterion on one Tier B dict; return the decision.

    A burst is a CANDIDATE iff ANY Tier-1 proposal passes the full criterion
    (copy-quality AND mandatory achromaticity AND robustness n_pass>=NPASS_MIN).
    The reported best proposal is the full-criterion survivor with the largest
    Δχ²; failing that, the most detectable copy-quality proposal; failing that,
    the most detectable proposal overall. Deterministic given (tb, cfg).
    """
    t1 = cfg.get("tier1", {})
    rows, _ = tier1.scan_burst(
        tb, cfg,
        peak_nsigma=float(t1.get("peak_nsigma", 4.0)),
        second_nsigma=float(t1.get("second_nsigma", 3.0)),
        max_proposals=int(t1.get("max_proposals", 10)))

    base = dict(is_candidate=False, n_proposals=len(rows), copy_ok_any=False,
                best_delta_chi2=np.nan, best_ncc=np.nan, best_reduced_chi2=np.nan,
                best_n_pass=np.nan, best_achromaticity_ok=False,
                best_delay_ms=np.nan, best_a=np.nan, best_kind="")
    if not rows:
        return base

    cands = []          # full-criterion survivors
    copyok = []         # copy-quality (pre-robustness)
    allp = []           # everything scored
    for r in rows:
        ca, cb = int(r["center_a"]), int(r["center_b"])
        s = scoremod.score_proposal(tb, ca, cb, cfg)
        rec = dict(ca=ca, cb=cb, kind=r.get("kind", ""),
                   delta_chi2=s["delta_chi2"], ncc=s["ncc"],
                   reduced_chi2=s["reduced_chi2"], delay_ms=s["delay_ms"],
                   best_a=s["best_a"])
        allp.append(rec)
        if fc._copy_ok(s):
            copyok.append(rec)
            f = fc._full(tb, ca, cb, cfg)      # copy + robustness (frozen full criterion)
            rec = dict(rec, n_pass=f["n_pass"], achromaticity_ok=f["achromaticity_ok"],
                       full_ok=f["full_ok"])
            copyok[-1] = rec
            if f["full_ok"]:
                cands.append(rec)

    def pick(lst):
        return max(lst, key=lambda d: (d["delta_chi2"] if np.isfinite(d["delta_chi2"])
                                       else -np.inf))

    best = pick(cands) if cands else (pick(copyok) if copyok else pick(allp))
    return dict(
        is_candidate=bool(cands),
        n_proposals=len(rows),
        copy_ok_any=bool(copyok),
        best_delta_chi2=float(best["delta_chi2"]),
        best_ncc=float(best["ncc"]),
        best_reduced_chi2=float(best["reduced_chi2"]),
        best_n_pass=float(best.get("n_pass", np.nan)),
        best_achromaticity_ok=bool(best.get("achromaticity_ok", False)),
        best_delay_ms=float(best["delay_ms"]),
        best_a=float(best["best_a"]),
        best_kind=str(best["kind"]),
    )


def load_and_run(path, cfg):
    """Load a Tier-B-shaped h5 and run the frozen chain; None if unreadable/noise-failed."""
    tb = tierb_io.load_tier_b(path)
    if tb["noise_failed"]:
        return None
    return run_frozen_chain(tb, cfg)
