"""W2.4 — adverse-generator unit tests (synthetic burst; no archive data)."""
import numpy as np

from echo_frb.search.adverse import generators as gen
from echo_frb.search.copy import score as scoremod

CFG = {"delay_domain": {"dt_min_ms": 2.0, "dt_max_ms": 50.0,
                        "per_burst_window_fraction": 0.4, "grid_step_ms": 0.5},
       "copy_statistic": {"magnification_bounds": [0.02, 1.0]}}


def _tb(nf=512, nt=120, seed=0):
    rng = np.random.default_rng(seed)
    env = np.zeros(nf); env[120:360] = 1.0 + 0.5 * np.cos(np.linspace(0, 3, 240))
    t = np.arange(nt); prof = np.exp(-0.5 * ((t - 40) / 3.0) ** 2)
    std = (env[:, None] * prof[None, :] + 0.05 * rng.standard_normal((nf, nt))).astype(np.float32)
    off = np.ones(nt, bool); off[30:75] = False
    return dict(standardized=std, project_mask=np.ones((nf, nt), bool),
               robust_std=0.05 * np.ones(nf), channel_usable=np.ones(nf, bool),
               offpulse=off, times=t * 0.983e-3, freqs=400 + np.arange(nf) * 0.39,
               res_time=0.983e-3, tns_name="SYN", noise_failed=False, attrs={})


def test_all_kinds_inject_without_error():
    tb = _tb()
    rng = np.random.default_rng(1)
    for kind in gen.KINDS:
        out = gen.inject(tb, 40, 8, 0.5, kind, rng)
        assert out["standardized"].shape == tb["standardized"].shape
        assert not np.allclose(out["standardized"], tb["standardized"])


def test_overlapping_injects_below_the_search_floor():
    """W3b.3 / gate-memo item 3 — `overlapping` must be an UNRESOLVED echo.

    At 3 bins (the old hardcoded value) the injected delay is ~2.95 ms, INSIDE
    the declared Δt >= 2 ms domain, so detecting it was not a false positive at
    all. The control must sit strictly below the floor.
    """
    tb = _tb()
    dt = gen.overlapping_dt_bins(tb, CFG["delay_domain"]["dt_min_ms"])
    mpb = tb["res_time"] * 1e3
    assert dt * mpb < CFG["delay_domain"]["dt_min_ms"]      # unresolved
    assert (dt + 1) * mpb >= CFG["delay_domain"]["dt_min_ms"]  # and the largest such
    assert dt == 2                                          # 1.97 ms at 0.983 ms/bin


def test_overlapping_ignores_the_caller_dt():
    """The delay comes from the burst's own resolution, not the injection grid."""
    tb = _tb()
    rng = np.random.default_rng(5)
    a = gen.inject(tb, 40, 8, 0.5, "overlapping", rng)
    b = gen.inject(tb, 40, 30, 0.5, "overlapping", np.random.default_rng(5))
    assert np.allclose(a["standardized"], b["standardized"])


def test_overlapping_dt_scales_with_time_resolution():
    tb = _tb()
    coarse = dict(tb, res_time=2.5e-3)          # 2.5 ms/bin: even 1 bin is resolved
    assert gen.overlapping_dt_bins(coarse, 2.0) == 1
    fine = dict(tb, res_time=0.2e-3)            # 0.2 ms/bin -> 9 bins = 1.8 ms
    assert gen.overlapping_dt_bins(fine, 2.0) == 9


def test_adverse_scores_less_copy_like_than_achromatic():
    tb = _tb(seed=2)
    rng = np.random.default_rng(3)
    ach = gen.inject(tb, 40, 8, 0.5, "achromatic_copy", rng)
    ncc_ach = scoremod.score_proposal(ach, 40, 48, CFG)["ncc"]
    # frequency drift and differential DM break achromaticity -> lower NCC
    for kind in ("drift", "differential_dm"):
        adv = gen.inject(tb, 40, 8, 0.5, kind, np.random.default_rng(3))
        ncc_adv = scoremod.score_proposal(adv, 40, 48, CFG)["ncc"]
        assert ncc_adv < ncc_ach, f"{kind} not rejected (ncc {ncc_adv} >= {ncc_ach})"
