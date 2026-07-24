"""W2.3 — empirical-null unit tests (surrogate properties + score bridge)."""
import numpy as np

from echo_frb.search.nulls import surrogate as surr
from echo_frb.search.copy import score as scoremod


def _spec(nf=48, nt=100, seed=0):
    rng = np.random.default_rng(seed)
    env = 1.0 + 0.5 * np.cos(np.linspace(0, 3, nf))
    t = np.arange(nt)
    prof = np.exp(-0.5 * ((t - 40) / 3.0) ** 2)
    return (env[:, None] * prof[None, :]
            + 0.05 * rng.standard_normal((nf, nt))).astype(np.float32)


def test_phase_randomization_preserves_channel_power():
    std = _spec()
    out = surr.phase_randomization(std, np.random.default_rng(1))
    # per-channel power spectrum (envelope) preserved; temporal shape changed
    p_in = np.abs(np.fft.rfft(std, axis=1))
    p_out = np.abs(np.fft.rfft(out, axis=1))
    assert np.allclose(p_in, p_out, atol=1e-3)
    assert not np.allclose(std, out)


def test_block_bootstrap_and_tf_permutation_shape_and_change():
    std = _spec(seed=2)
    for fn in (surr.block_bootstrap, surr.tf_permutation):
        out = fn(std, np.random.default_rng(3))
        assert out.shape == std.shape
        assert not np.allclose(std, out)


def test_surrogate_destroys_an_injected_copy():
    """A real delayed copy scores high; its phase-randomized surrogate should not."""
    nf, nt = 48, 120
    rng = np.random.default_rng(4)
    env = 1.0 + 0.4 * np.cos(np.linspace(0, 3, nf))
    t = np.arange(nt)
    prof = np.exp(-0.5 * ((t - 40) / 2.5) ** 2) + 0.5 * np.exp(-0.5 * ((t - 52) / 2.5) ** 2)
    std = (env[:, None] * prof[None, :] + 0.05 * rng.standard_normal((nf, nt))).astype(np.float32)
    sig = 0.05 * np.ones(nf)
    off = np.ones(nt, bool); off[30:65] = False
    tb = dict(standardized=std, project_mask=np.ones((nf, nt), bool),
              robust_std=sig, channel_usable=np.ones(nf, bool), offpulse=off,
              times=t * 0.983e-3, freqs=np.arange(nf), res_time=0.983e-3,
              tns_name="SYN", noise_failed=False, attrs={})
    cfg = {"delay_domain": {"dt_min_ms": 2.0, "dt_max_ms": 50.0,
                            "per_burst_window_fraction": 0.4, "grid_step_ms": 0.5},
           "copy_statistic": {"magnification_bounds": [0.02, 1.0]}}
    real = scoremod.score_proposal(tb, 40, 52, cfg)["delta_chi2"]
    sur_tb = surr.make_surrogate(tb, "phase_randomization", np.random.default_rng(5))
    sur = scoremod.score_proposal(sur_tb, 40, 52, cfg)["delta_chi2"]
    assert real > sur                                   # copy relation destroyed
