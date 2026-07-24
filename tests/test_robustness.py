"""W2.5 — robustness-diagnostic unit tests (synthetic; no archive data)."""
import numpy as np

from echo_frb.search.adverse import generators as gen
from echo_frb.search.robustness import diagnostics as diag

CFG = {"delay_domain": {"dt_min_ms": 2.0, "dt_max_ms": 50.0,
                        "per_burst_window_fraction": 0.4, "grid_step_ms": 0.5},
       "copy_statistic": {"magnification_bounds": [0.02, 1.0]}}


def _tb(nf=512, nt=140, seed=0):
    rng = np.random.default_rng(seed)
    env = np.zeros(nf); env[100:400] = 1.0 + 0.5 * np.cos(np.linspace(0, 3, 300))
    t = np.arange(nt); prof = np.exp(-0.5 * ((t - 45) / 3.0) ** 2)
    std = (env[:, None] * prof[None, :] + 0.04 * rng.standard_normal((nf, nt))).astype(np.float32)
    off = np.ones(nt, bool); off[35:80] = False
    return dict(standardized=std, project_mask=np.ones((nf, nt), bool),
               robust_std=0.04 * np.ones(nf), channel_usable=np.ones(nf, bool),
               offpulse=off, times=t * 0.983e-3, freqs=400 + np.arange(nf) * 0.39,
               res_time=0.983e-3, tns_name="SYN", noise_failed=False, attrs={})


def test_run_all_returns_all_checks():
    tb = _tb()
    copy = gen.inject(tb, 45, 8, 0.5, "achromatic_copy", np.random.default_rng(1))
    d = diag.run_all(copy, 45, 53, CFG)
    assert d["n_checks"] == 9                       # 8 §5.5 diagnostics + spectral-mag
    assert "achromaticity_ok" in d                  # mandatory-achromaticity composite


def test_achromatic_copy_passes_achromaticity():
    tb = _tb(seed=2)
    copy = gen.inject(tb, 45, 8, 0.5, "achromatic_copy", np.random.default_rng(2))
    d = diag.run_all(copy, 45, 53, CFG)
    assert d["achromatic_delay_pass"]               # one delay across bands
    assert d["magnification_stability_pass"]        # one magnification across bands
    assert d["n_pass"] >= 5                          # passes most of the 8 checks


def test_drift_fails_achromaticity():
    tb = _tb(seed=3)
    drift = gen.inject(tb, 45, 8, 0.5, "drift", np.random.default_rng(3))
    dd = diag.run_all(drift, 45, 53, CFG)
    copy = gen.inject(tb, 45, 8, 0.5, "achromatic_copy", np.random.default_rng(3))
    dc = diag.run_all(copy, 45, 53, CFG)
    # drift is a chromatic offset -> it passes fewer robustness checks than a copy
    assert dd["n_pass"] < dc["n_pass"]
