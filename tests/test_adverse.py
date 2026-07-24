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
