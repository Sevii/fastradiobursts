#!/usr/bin/env python3
"""W3b.1 — the per-proposal scalar margin T_ij (docs/WP3b_plan.md §3.1).

A transparent scalar that preserves the frozen criterion's meaning while allowing
ranked p-values: the WEAKEST standardized margin across the frozen MANDATORY
gates,

    z_k = (x_k - c_k)/s_k   (larger passes)   or   (c_k - x_k)/s_k  (smaller passes)
    T   = min_k z_k

with c_k the frozen threshold and s_k a PRESPECIFIED scale constant (W3b.2).
T > 0 means every mandatory gate passes; a larger T means the proposal clears its
weakest gate by a larger margin.

EXACT EQUIVALENCE (tests/test_wp3b_margin.py): `T > 0` iff the proposal passes the
frozen `benchmark.full_criterion._full`. The terms below are therefore precisely
v1's mandatory gates — nothing added, nothing relaxed:

  1 log10 delta_chi2      > log10(detect_delta_chi2_min)   copy detectability
  2 ncc                   > copy_ncc_min                    copy quality
  3 reduced_chi2          < copy_reduced_chi2_max           copy quality
  4 delay_spread_bins    <= delay_spread_bins_max           achromatic delay (also dm_scattering)
  5 mag_rel_spread       <= mag_rel_spread_max              magnification stability
  6 spectral_mag_reduced  < spectral_mag_reduced_max        scintillation catcher
  7 residual_reduced_chi2<= residual_reduced_chi2_max       noise-like residual
  8 n_pass                >= robustness_n_pass_min          the robustness VOTE

Terms 3 and 7 are distinct numbers: term 3 is `score_proposal`'s reduced chi2 over
all valid pixels, term 7 is `diagnostics.run_all`'s over OCCUPIED channels only.
Term 4 covers both `achromatic_delay_pass` and `dm_scattering_pass` (one quantity
in `robustness/diagnostics.py`).

`leave_band_out_min_frac`, `resolution_ncc_spread`, `window_ncc_spread` and
`fine_structure` are NOT mandatory in v1 — they are votes, so they enter T only
through term 8. They are still returned (as `aux_*`) for use as calibration
covariates and for the secondary all-gates statistic `T_all`.

Scales are positive by construction, so sign(T) — and hence the equivalence — does
NOT depend on them. They set only the RANKING among passing proposals, which is
what the max-statistic calibration consumes.
"""
from __future__ import annotations

import math

import numpy as np

# Provisional unit scales. W3b.2 replaces these with robust (MAD) spreads measured
# on dev real-null proposals and freezes them into the v2 analysis config under
# `margin.scales`. Unit scales are a valid (if uninformative) prespecification:
# they leave sign(T) — the v1 equivalence — untouched.
DEFAULT_SCALES = {
    "log10_delta_chi2": 1.0,
    "ncc": 1.0,
    "reduced_chi2": 1.0,
    "delay_spread_bins": 1.0,
    "mag_rel_spread": 1.0,
    "spectral_mag_reduced": 1.0,
    "residual_reduced_chi2": 1.0,
    "n_pass_vote": 1.0,
    # non-mandatory (T_all only)
    "leave_band_out_min_frac": 1.0,
    "resolution_ncc_spread": 1.0,
    "window_ncc_spread": 1.0,
}

MANDATORY = ("log10_delta_chi2", "ncc", "reduced_chi2", "delay_spread_bins",
             "mag_rel_spread", "spectral_mag_reduced", "residual_reduced_chi2",
             "n_pass_vote")
NON_MANDATORY = ("leave_band_out_min_frac", "resolution_ncc_spread",
                 "window_ncc_spread")

# The robustness vote is a COUNT. Offsetting by half a vote makes the margin
# strictly positive at n_pass == NPASS_MIN (a v1 pass) and strictly negative at
# NPASS_MIN - 1 (a v1 fail), so the sign equivalence holds for a discrete gate.
_VOTE_OFFSET = 0.5


def thresholds(cfg):
    """The frozen thresholds c_k, read from the analysis config (single source)."""
    cc = cfg["candidate_criterion"]
    rt = cfg["robustness_tolerances"]
    return {
        "log10_delta_chi2": math.log10(float(cc["detect_delta_chi2_min"])),
        "ncc": float(cc["copy_ncc_min"]),
        "reduced_chi2": float(cc["copy_reduced_chi2_max"]),
        "delay_spread_bins": float(rt["delay_spread_bins_max"]),
        "mag_rel_spread": float(rt["mag_rel_spread_max"]),
        "spectral_mag_reduced": float(rt["spectral_mag_reduced_max"]),
        "residual_reduced_chi2": float(rt["residual_reduced_chi2_max"]),
        "n_pass_vote": float(cc["robustness_n_pass_min"]),
        "leave_band_out_min_frac": float(rt["leave_band_out_min_frac"]),
        "resolution_ncc_spread": float(rt["ncc_spread_max"]),
        "window_ncc_spread": float(rt["ncc_spread_max"]),
    }


# direction: +1 = larger passes, -1 = smaller passes
DIRECTION = {
    "log10_delta_chi2": +1, "ncc": +1, "reduced_chi2": -1,
    "delay_spread_bins": -1, "mag_rel_spread": -1, "spectral_mag_reduced": -1,
    "residual_reduced_chi2": -1, "n_pass_vote": +1,
    "leave_band_out_min_frac": +1, "resolution_ncc_spread": -1,
    "window_ncc_spread": -1,
}


def scales(cfg):
    """Prespecified s_k: config `margin.scales` if present, else DEFAULT_SCALES."""
    s = dict(DEFAULT_SCALES)
    s.update({k: float(v) for k, v in
              (cfg.get("margin", {}) or {}).get("scales", {}).items()})
    for k, v in s.items():
        assert v > 0, f"margin scale {k} must be positive, got {v}"
    return s


def _z(name, value, thr, sc):
    """Standardized margin for one gate. NaN => -inf (a hard fail), matching v1."""
    if value is None or not np.isfinite(value):
        return -np.inf
    return DIRECTION[name] * (float(value) - thr[name]) / sc[name]


def proposal_terms(score, diag=None, cfg=None):
    """Per-gate standardized margins for one proposal.

    `score` is a `copy.score.score_proposal` result; `diag` is a
    `robustness.diagnostics.run_all` result, or None when the copy gates already
    failed and robustness was (as in v1) not evaluated.

    Returns {term_name: margin}, with three distinct non-finite encodings:

      -inf  the diagnostic was computed and is unusable (e.g. fewer than 2 bands
            leave `delay_spread_bins` NaN) — v1 scores that as a FAIL, so do we.
      +inf  the gate is undefined but v1 DEFAULT-PASSES it (`spectral_mag_reduced`
            with fewer than 6 usable channels). Undefined-and-passing carries no
            information about margin size, so it never sets the minimum.
      NaN   NOT EVALUATED — the copy gates already failed and v1, like this
            function, never ran the diagnostics. `T_from_terms` skips these, so T
            falls back to the copy margins alone: an UPPER bound on the true
            margin, which keeps the statistic ranked and continuous below zero
            instead of collapsing every copy-failing burst onto -inf.
    """
    thr, sc = thresholds(cfg), scales(cfg)
    dchi2 = score.get("delta_chi2", np.nan)
    log_d = (math.log10(dchi2) if np.isfinite(dchi2) and dchi2 > 0 else np.nan)

    t = {
        "log10_delta_chi2": _z("log10_delta_chi2", log_d, thr, sc),
        "ncc": _z("ncc", score.get("ncc"), thr, sc),
        "reduced_chi2": _z("reduced_chi2", score.get("reduced_chi2"), thr, sc),
    }
    if diag is None:                       # copy gates failed; v1 stops here too
        for k in MANDATORY[3:] + NON_MANDATORY:
            t[k] = np.nan                  # not evaluated (distinct from failed)
        return t

    smr = diag.get("spectral_mag_reduced", np.nan)
    # v1 default-passes the flatness test when it cannot be computed; an
    # undefined-but-passing gate carries no information about margin size.
    spectral = (np.inf if not np.isfinite(smr) and diag.get("spectral_mag_flat_pass")
                else _z("spectral_mag_reduced", smr, thr, sc))

    t.update({
        "delay_spread_bins": _z("delay_spread_bins",
                                diag.get("delay_spread_bins"), thr, sc),
        "mag_rel_spread": _z("mag_rel_spread", diag.get("mag_rel_spread"), thr, sc),
        "spectral_mag_reduced": spectral,
        "residual_reduced_chi2": _z("residual_reduced_chi2",
                                    diag.get("residual_reduced_chi2"), thr, sc),
        "n_pass_vote": _z("n_pass_vote",
                          (diag["n_pass"] + _VOTE_OFFSET
                           if np.isfinite(diag.get("n_pass", np.nan)) else np.nan),
                          thr, sc),
        "leave_band_out_min_frac": _z("leave_band_out_min_frac",
                                      diag.get("leave_band_out_min_frac"), thr, sc),
        "resolution_ncc_spread": _z("resolution_ncc_spread",
                                    diag.get("resolution_ncc_spread"), thr, sc),
        "window_ncc_spread": _z("window_ncc_spread",
                                diag.get("window_ncc_spread"), thr, sc),
    })
    return t


def T_from_terms(terms, keys=MANDATORY):
    """T = min over the EVALUATED gate margins (NaN terms are skipped).

    Skipping unevaluated terms cannot manufacture a candidate: they are absent
    only when the copy gates failed, which leaves at least one copy margin <= 0
    and hence T <= 0. So `T > 0` still implies every mandatory gate was computed
    and cleared — the v1 equivalence is preserved.
    """
    vals = [float(terms[k]) for k in keys
            if k in terms and terms[k] is not None
            and not (isinstance(terms[k], float) and math.isnan(terms[k]))]
    return float(min(vals)) if vals else -np.inf


def proposal_margin(score, diag=None, cfg=None):
    """(T, T_all, terms) for one proposal. T uses the mandatory gates only."""
    terms = proposal_terms(score, diag, cfg)
    return (T_from_terms(terms, MANDATORY),
            T_from_terms(terms, MANDATORY + NON_MANDATORY),
            terms)
