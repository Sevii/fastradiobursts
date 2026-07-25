#!/usr/bin/env python3
"""W3b.1 — the end-to-end MARGIN chain: M_i = max_j T_ij (docs/WP3b_plan.md §3).

Mirrors `blind.pipeline.run_frozen_chain` exactly — same frozen Tier-1 triage,
same `score_proposal`, same `robustness.diagnostics.run_all`, same
copy-gates-before-robustness short circuit — and additionally records the
standardized margin of every proposal. Every null realization and every real
burst goes through THIS function, so the calibrated distribution is the
distribution of the quantity the pipeline actually reports.

It also returns v1's `is_candidate` computed from the very same score/diagnostic
objects, so the equivalence `M_i > 0 <=> v1 is_candidate` can be asserted on real
data (tests/test_wp3b_margin.py) rather than argued on paper.

Covariates Z are derived from the SPECTRUM ALONE — never from catalog metadata —
because blind items have their identity scrubbed and cannot be joined to the
manifest. Conditioning must work on the hidden set or it is not conditioning.
"""
from __future__ import annotations

import numpy as np

from .. import tierb_io
from ..benchmark import full_criterion as fc
from ..copy import score as scoremod
from ..robustness import diagnostics as diag
from ..tier1 import profile, scan as tier1
from . import statistic as ms


# raw diagnostic values carried through per proposal — the scale constants s_k
# (W3b.2) are estimated from their spread, and the calibration uses them as
# covariates. Kept separate from the z_* margins so the frozen thresholds can be
# re-derived from the dump without inverting the standardization.
RAW_DIAG_KEYS = ("delay_spread_bins", "mag_rel_spread", "spectral_mag_reduced",
                 "residual_reduced_chi2", "leave_band_out_min_frac",
                 "resolution_ncc_spread", "window_ncc_spread", "n_bands_used",
                 "n_occupied")


def _v1_full_ok(copy_ok, d):
    """v1's candidate predicate, from an already-computed score + diagnostics.

    Byte-for-byte the boolean in `benchmark.full_criterion._full`; kept here only
    to avoid re-scoring and re-running the diagnostics (which `_full` would do).
    `tests/test_wp3b_margin.py` asserts this agrees with `_full` on real bursts.
    """
    if not copy_ok or d is None:
        return False
    npass = d["n_pass"]
    return bool(copy_ok and bool(d["achromaticity_ok"])
                and bool(d["residual_structure_pass"])
                and npass is not np.nan and npass >= fc.NPASS_MIN)


def burst_covariates(tb, rows, prof):
    """Z_i — self-contained burst descriptors for the conditional calibration."""
    I, mu, sig = prof["I"], prof["mu_off"], prof["sigma_off"]
    snr = (I - mu) / sig if sig > 0 else np.zeros_like(I)
    pmask = np.asarray(tb["project_mask"], bool)
    chan_ok = np.asarray(tb["channel_usable"], bool)
    valid = pmask & chan_ok[:, None]
    above = snr > 3.0
    delays = [r["delay_ms"] for r in rows]
    return dict(
        n_proposals=len(rows),
        peak_snr=float(np.nanmax(snr)) if snr.size else np.nan,
        n_peaks=int(rows[0]["n_peaks"]) if rows else 0,
        width_bins=int(above.sum()),
        masked_frac=float(1.0 - valid.mean()),
        usable_channel_frac=float(chan_ok.mean()),
        ms_per_bin=float(tierb_io.ms_per_bin(tb)),
        min_delay_ms=float(np.min(delays)) if delays else np.nan,
        max_delay_ms=float(np.max(delays)) if delays else np.nan,
        median_triage_ncc=float(np.median([r["triage_ncc"] for r in rows]))
        if rows else np.nan,
    )


def run_margin_chain(tb, cfg, return_proposals=False):
    """Run the frozen chain on one Tier B dict and return M_i plus covariates.

    Returns a dict with `M` (max mandatory-gate margin over proposals), `M_all`
    (secondary statistic including the non-mandatory diagnostics), the v1
    decision, the winning proposal's per-gate margins, and Z_i. `M = -inf` when
    Tier-1 proposes nothing — a burst the search cannot flag at all.
    """
    t1 = cfg.get("tier1", {})
    rows, prof = tier1.scan_burst(
        tb, cfg,
        peak_nsigma=float(t1.get("peak_nsigma", 4.0)),
        second_nsigma=float(t1.get("second_nsigma", 3.0)),
        max_proposals=int(t1.get("max_proposals", 10)))

    Z = burst_covariates(tb, rows, prof)
    out = dict(M=-np.inf, M_all=-np.inf, is_candidate_v1=False,
               n_robustness_evaluated=0, best_delay_ms=np.nan,
               best_delta_chi2=np.nan, best_ncc=np.nan, best_reduced_chi2=np.nan,
               best_n_pass=np.nan, best_kind="", **Z)
    if not rows:
        return (out, []) if return_proposals else out

    props = []
    for r in rows:
        ca, cb = int(r["center_a"]), int(r["center_b"])
        s = scoremod.score_proposal(tb, ca, cb, cfg)
        copy_ok = fc._copy_ok(s)
        # v1 runs the diagnostics ONLY on copy-survivors. A proposal that fails a
        # copy gate therefore gets T from the copy margins alone — an UPPER bound
        # on its true margin. Safe in the only direction that matters: such a
        # proposal has T < 0 and can never produce a candidate, and an overstated
        # null M only inflates p-values (more conservative). Any M > 0 comes from
        # a fully-evaluated proposal and is exact. See docs/WP3b_plan.md §3.1.
        d = diag.run_all(tb, ca, cb, cfg) if copy_ok else None
        T, T_all, terms = ms.proposal_margin(s, d, cfg)
        props.append(dict(
            center_a=ca, center_b=cb, kind=r.get("kind", ""), T=T, T_all=T_all,
            copy_ok=copy_ok, full_ok_v1=_v1_full_ok(copy_ok, d),
            delta_chi2=s["delta_chi2"], ncc=s["ncc"],
            reduced_chi2=s["reduced_chi2"], delay_ms=s["delay_ms"],
            best_a=s["best_a"], n_pass=(d["n_pass"] if d else np.nan),
            triage_ncc=float(r["triage_ncc"]),
            **{k: float(d[k]) if d is not None and np.isfinite(d.get(k, np.nan))
               else np.nan for k in RAW_DIAG_KEYS},
            **{f"z_{k}": v for k, v in terms.items()}))

    best = max(props, key=lambda p: p["T"])
    out.update(
        M=float(best["T"]),
        M_all=float(max(p["T_all"] for p in props)),
        is_candidate_v1=any(p["full_ok_v1"] for p in props),
        n_robustness_evaluated=int(sum(p["copy_ok"] for p in props)),
        best_delay_ms=float(best["delay_ms"]),
        best_delta_chi2=float(best["delta_chi2"]),
        best_ncc=float(best["ncc"]),
        best_reduced_chi2=float(best["reduced_chi2"]),
        best_n_pass=float(best["n_pass"]),
        best_kind=str(best["kind"]),
        **{f"z_{k}": float(best[f"z_{k}"]) for k in
           ms.MANDATORY + ms.NON_MANDATORY},
    )
    return (out, props) if return_proposals else out


def load_and_run(path, cfg, **kw):
    """Load a Tier-B-shaped h5 and run the margin chain; None if unusable."""
    tb = tierb_io.load_tier_b(path)
    if tb["noise_failed"]:
        return None
    return run_margin_chain(tb, cfg, **kw)
