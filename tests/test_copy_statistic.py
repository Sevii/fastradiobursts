"""W2.2 — copy statistic unit tests (synthetic injected copies; no archive data)."""
import numpy as np

from echo_frb.search.copy import statistic as st


def _burst(nf=64, nw=41, seed=0):
    rng = np.random.default_rng(seed)
    env = 1.0 + 0.5 * np.cos(np.linspace(0, 3, nf))        # per-channel spectrum
    t = np.arange(nw)
    prof = np.exp(-0.5 * ((t - nw // 2) / 3.0) ** 2)       # gaussian pulse
    clean = env[:, None] * prof[None, :]
    sigma = 0.15 * (1 + 0.3 * rng.random(nf))              # per-channel noise
    return clean, sigma


GRID = np.arange(-6, 6.01, 0.5)


def test_recovers_injected_copy():
    clean, sigma = _burst(seed=1)
    rng = np.random.default_rng(2)
    dt_true, a_true = 3.0, 0.4
    A = clean + sigma[:, None] * rng.standard_normal(clean.shape)
    B = a_true * st.time_shift(clean, dt_true) + \
        sigma[:, None] * rng.standard_normal(clean.shape)
    V = np.ones(clean.shape, bool)
    r = st.copy_score(A, B, sigma, sigma, V, V, trial_delays=GRID, min_pixels=32)
    assert abs(r["best_delay_bins"] - dt_true) <= 0.5      # delay within 1/2 bin
    assert abs(r["best_a"] - a_true) <= 0.12               # magnification recovered
    assert 0.5 <= r["reduced_chi2"] <= 2.0                 # good fit -> chi2 ~ 1
    assert r["delta_chi2"] > 20                            # copy term clearly detected


def test_delta_chi2_separates_copy_from_noncopy():
    clean, sigma = _burst(seed=3)
    rng = np.random.default_rng(4)
    A = clean + sigma[:, None] * rng.standard_normal(clean.shape)
    V = np.ones(clean.shape, bool)
    B_copy = 0.4 * st.time_shift(clean, 3.0) + \
        sigma[:, None] * rng.standard_normal(clean.shape)
    B_noise = sigma[:, None] * rng.standard_normal(clean.shape)   # no copy
    d_copy = st.copy_score(A, B_copy, sigma, sigma, V, V, trial_delays=GRID,
                           min_pixels=32)["delta_chi2"]
    d_noise = st.copy_score(A, B_noise, sigma, sigma, V, V, trial_delays=GRID,
                            min_pixels=32)["delta_chi2"]
    assert d_copy > 10 * max(d_noise, 1.0)                 # clear separation


def test_masking_excludes_invalid_pixels():
    clean, sigma = _burst(seed=5)
    A = clean.copy(); B = 0.5 * st.time_shift(clean, 2.0)
    V = np.ones(clean.shape, bool)
    V[10:15, :] = False                                    # mask 5 channels
    r = st.copy_score(A, B, sigma, sigma, V, V,
                      trial_delays=np.arange(-4, 4.01, 0.5), min_pixels=16)
    assert r["n_valid"] <= (clean.size - 5 * clean.shape[1])


def test_rebin_path_recovers_copy_in_wide_band():
    """v2 regression: with a wide band (rebin engaged) + mostly-empty channels,
    the on-burst support + rebin still recovers an injected copy and beats noise."""
    nf, nw = 2048, 41
    rng = np.random.default_rng(7)
    clean = np.zeros((nf, nw))
    occ = slice(300, 900)                                   # burst occupies a sub-band
    env = 1.0 + 0.5 * np.cos(np.linspace(0, 3, 600))
    t = np.arange(nw); prof = np.exp(-0.5 * ((t - nw // 2) / 3.0) ** 2)
    clean[occ] = env[:, None] * prof[None, :]
    sigma = 0.1 * np.ones(nf)
    A = clean + sigma[:, None] * rng.standard_normal((nf, nw))
    B_copy = 0.4 * st.time_shift(clean, 3.0) + sigma[:, None] * rng.standard_normal((nf, nw))
    B_noise = sigma[:, None] * rng.standard_normal((nf, nw))
    V = np.ones((nf, nw), bool)
    kw = dict(trial_delays=np.arange(-6, 6.01, 0.5), rebin_nf=256, on_burst_k=2.0)
    rc = st.copy_score(A, B_copy, sigma, sigma, V, V, **kw)
    rn = st.copy_score(A, B_noise, sigma, sigma, V, V, **kw)
    assert abs(rc["best_delay_bins"] - 3.0) <= 0.5
    assert rc["ncc"] > 0.5 and rc["ncc"] > rn["ncc"] + 0.2  # copy correlates, noise doesn't
    assert rc["delta_chi2"] > 5 * max(rn["delta_chi2"], 1.0)


def test_deterministic():
    clean, sigma = _burst(seed=6)
    A = clean; B = 0.4 * st.time_shift(clean, 3.0)
    V = np.ones(clean.shape, bool)
    kw = dict(trial_delays=np.arange(-5, 5.01, 0.5), min_pixels=32)
    r1 = st.copy_score(A, B, sigma, sigma, V, V, **kw)
    r2 = st.copy_score(A, B, sigma, sigma, V, V, **kw)
    assert r1["best_delay_bins"] == r2["best_delay_bins"]
    assert r1["reduced_chi2"] == r2["reduced_chi2"]
