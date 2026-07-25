"""W3b.1 — margin statistic tests (synthetic; no archive data).

The load-bearing property is EXACT EQUIVALENCE with the frozen v1 criterion:
`T_ij > 0` iff the proposal passes `full_criterion._full`, and `max_j T_ij > 0`
iff `blind.pipeline.run_frozen_chain` calls the burst a candidate. If that breaks,
v2 is no longer a calibrated tightening of v1 — it is a different analysis.

The equivalence is re-checked on REAL dev bursts by
`scripts/wp3b_check_equivalence.py` (runs on popos, where Tier B lives).
"""
import os

import numpy as np
import pytest
import yaml

from echo_frb.search.adverse import generators as gen
from echo_frb.search.benchmark import full_criterion as fc
from echo_frb.search.blind import pipeline as bp
from echo_frb.search.copy import score as scoremod
from echo_frb.search.margin import chain as mchain, statistic as ms
from echo_frb.search.robustness import diagnostics as diag

CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "config",
                        "wp2_analysis_config.yaml")


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load(open(CFG_PATH))


def _tb(nf=512, nt=140, seed=0):
    rng = np.random.default_rng(seed)
    env = np.zeros(nf); env[100:400] = 1.0 + 0.5 * np.cos(np.linspace(0, 3, 300))
    t = np.arange(nt); prof = np.exp(-0.5 * ((t - 45) / 3.0) ** 2)
    std = (env[:, None] * prof[None, :]
           + 0.04 * rng.standard_normal((nf, nt))).astype(np.float32)
    off = np.ones(nt, bool); off[35:80] = False
    return dict(standardized=std, project_mask=np.ones((nf, nt), bool),
                robust_std=0.04 * np.ones(nf), channel_usable=np.ones(nf, bool),
                offpulse=off, times=t * 0.983e-3, freqs=400 + np.arange(nf) * 0.39,
                res_time=0.983e-3, tns_name="SYN", noise_failed=False, attrs={})


def _fake(delta=1e4, ncc=0.9, red=1.0, delay=0.2, mag=0.1, spec=1.0, resid=1.0,
          npass=9, lbo=0.9, res_spread=0.05, win_spread=0.05, spec_pass=True):
    score = dict(delta_chi2=delta, ncc=ncc, reduced_chi2=red)
    d = dict(delay_spread_bins=delay, mag_rel_spread=mag,
             spectral_mag_reduced=spec, spectral_mag_flat_pass=spec_pass,
             residual_reduced_chi2=resid, n_pass=npass,
             leave_band_out_min_frac=lbo, resolution_ncc_spread=res_spread,
             window_ncc_spread=win_spread)
    return score, d


# --- the frozen thresholds are read from the config, not hardcoded -----------

def test_thresholds_come_from_frozen_config(cfg):
    thr = ms.thresholds(cfg)
    assert thr["ncc"] == cfg["candidate_criterion"]["copy_ncc_min"]
    assert thr["reduced_chi2"] == cfg["candidate_criterion"]["copy_reduced_chi2_max"]
    assert thr["log10_delta_chi2"] == pytest.approx(2.0)          # log10(100)
    assert thr["delay_spread_bins"] == \
        cfg["robustness_tolerances"]["delay_spread_bins_max"]
    assert thr["n_pass_vote"] == cfg["candidate_criterion"]["robustness_n_pass_min"]


# --- per-gate margin behaviour ----------------------------------------------

def test_all_gates_clear_gives_positive_T(cfg):
    score, d = _fake()
    T, _, terms = ms.proposal_margin(score, d, cfg)
    assert T > 0
    assert all(terms[k] > 0 for k in ms.MANDATORY)


@pytest.mark.parametrize("kw,gate", [
    (dict(delta=50.0), "log10_delta_chi2"),          # below detectability
    (dict(ncc=0.1), "ncc"),                          # not copy-like
    (dict(red=3.0), "reduced_chi2"),                 # bad residual
    (dict(delay=5.0), "delay_spread_bins"),          # chromatic delay
    (dict(mag=2.0), "mag_rel_spread"),               # chromatic magnification
    (dict(spec=9.0), "spectral_mag_reduced"),        # scintillation ripple
    (dict(resid=3.0), "residual_reduced_chi2"),      # structured residual
    (dict(npass=6), "n_pass_vote"),                  # vote short of 7
])
def test_each_mandatory_gate_can_set_the_minimum(cfg, kw, gate):
    score, d = _fake(**kw)
    T, _, terms = ms.proposal_margin(score, d, cfg)
    assert T < 0, f"{gate} failure should drive T negative"
    assert min(ms.MANDATORY, key=lambda k: terms[k]) == gate


def test_vote_margin_is_exact_at_the_boundary(cfg):
    npass_min = cfg["candidate_criterion"]["robustness_n_pass_min"]
    _, terms_pass = ms.proposal_margin(*_fake(npass=npass_min), cfg=cfg)[1:]
    _, terms_fail = ms.proposal_margin(*_fake(npass=npass_min - 1), cfg=cfg)[1:]
    assert terms_pass["n_pass_vote"] > 0     # n_pass == min is a v1 PASS
    assert terms_fail["n_pass_vote"] < 0     # one short is a v1 FAIL


def test_non_mandatory_gates_do_not_enter_T(cfg):
    """leave-band-out / resolution / window are v1 VOTES, not hard gates."""
    score, d = _fake(lbo=0.01, res_spread=5.0, win_spread=5.0)
    T, T_all, _ = ms.proposal_margin(score, d, cfg)
    assert T > 0                             # still a v1 candidate (n_pass carries it)
    assert T_all < 0                         # the secondary statistic does see them


def test_undefined_but_default_passing_gate_is_omitted(cfg):
    """<6 usable channels leaves spectral flatness undefined; v1 default-passes."""
    score, d = _fake(spec=np.nan, spec_pass=True)
    T, _, terms = ms.proposal_margin(score, d, cfg)
    assert terms["spectral_mag_reduced"] == np.inf
    assert T > 0


def test_unevaluated_robustness_falls_back_to_the_copy_margins(cfg):
    """A copy-gate failure stops v1 before the diagnostics.

    T then comes from the copy margins alone — negative (so never a candidate)
    but still RANKED, which is what keeps the null distribution of M continuous
    below zero instead of collapsing onto a point mass at -inf.
    """
    score, _ = _fake(ncc=0.1)
    T, _, terms = ms.proposal_margin(score, None, cfg)
    assert np.isfinite(T) and T < 0
    assert T == terms["ncc"]                     # the failing copy gate sets it
    assert np.isnan(terms["n_pass_vote"])        # never evaluated, not "failed"


def test_a_computed_but_unusable_diagnostic_is_still_a_hard_fail(cfg):
    """<2 usable bands leaves delay_spread NaN; v1 scores that as a FAIL."""
    score, d = _fake()
    d["delay_spread_bins"] = np.nan
    T, _, terms = ms.proposal_margin(score, d, cfg)
    assert terms["delay_spread_bins"] == -np.inf
    assert T == -np.inf


def test_sign_is_invariant_to_the_scale_constants(cfg):
    """s_k set the RANKING, never the decision — so freezing them can't move v1."""
    score, d = _fake(delta=500.0, ncc=0.5, npass=7)
    cfg2 = dict(cfg, margin={"scales": {k: 17.5 for k in ms.DEFAULT_SCALES}})
    T1, _, _ = ms.proposal_margin(score, d, cfg)
    T2, _, _ = ms.proposal_margin(score, d, cfg2)
    assert np.sign(T1) == np.sign(T2)
    assert T1 != T2                                   # but the magnitude rescales


def test_scales_must_be_positive(cfg):
    with pytest.raises(AssertionError):
        ms.scales(dict(cfg, margin={"scales": {"ncc": 0.0}}))


# --- equivalence with the frozen v1 criterion (synthetic spectra) ------------

@pytest.mark.parametrize("kind", ["achromatic_copy", "drift", "scintillation",
                                  "differential_scattering", "chromatic_echo"])
def test_proposal_margin_sign_matches_full_criterion(cfg, kind):
    tb = _tb(seed=7)
    inj = gen.inject(tb, 45, 8, 0.5, kind, np.random.default_rng(7))
    s = scoremod.score_proposal(inj, 45, 53, cfg)
    copy_ok = fc._copy_ok(s)
    d = diag.run_all(inj, 45, 53, cfg) if copy_ok else None
    T, _, _ = ms.proposal_margin(s, d, cfg)
    assert (T > 0) == fc._full(inj, 45, 53, cfg)["full_ok"]


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_chain_agrees_with_frozen_chain(cfg, seed):
    tb = _tb(seed=seed)
    inj = gen.inject(tb, 45, 8, 0.5, "achromatic_copy",
                     np.random.default_rng(seed))
    v1 = bp.run_frozen_chain(inj, cfg)
    v2 = mchain.run_margin_chain(inj, cfg)
    assert v2["n_proposals"] == v1["n_proposals"]
    assert v2["is_candidate_v1"] == v1["is_candidate"]
    assert (v2["M"] > 0) == v1["is_candidate"]


def test_chain_handles_a_burst_with_no_proposals(cfg):
    """Tier-1 silence is a genuine non-detection, not an error."""
    tb = _tb(seed=11)
    tb["standardized"] = (0.04 * np.random.default_rng(0)
                          .standard_normal(tb["standardized"].shape)).astype(np.float32)
    out = mchain.run_margin_chain(tb, cfg)
    if out["n_proposals"] == 0:
        assert out["M"] == -np.inf
        assert not out["is_candidate_v1"]


def test_covariates_are_spectrum_only(cfg):
    """Z must be computable on identity-scrubbed blind items."""
    tb = _tb(seed=3)
    inj = gen.inject(tb, 45, 8, 0.5, "achromatic_copy", np.random.default_rng(3))
    out = mchain.run_margin_chain(inj, cfg)
    for k in ("n_proposals", "peak_snr", "n_peaks", "width_bins", "masked_frac",
              "usable_channel_frac", "ms_per_bin", "min_delay_ms"):
        assert k in out
    assert np.isfinite(out["peak_snr"])
