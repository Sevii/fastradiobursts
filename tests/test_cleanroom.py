"""WP1 clean-room microlensing detection — unit tests.

Mirrors the style of tests/test_preprocess.py. Covers:
  (a) recovery — inject a delayed, scaled copy of a single-component burst into
      noise; assert the pipeline recovers Delta t within +/-1 time bin and a
      sensible magnification ratio;
  (b) control — a no-copy single burst yields no candidate;
  (c) determinism — same input -> identical content_sha256.
"""
import numpy as np
import pytest

from echo_frb.repro.cleanroom import acf, lightcurve, pipeline

RES_TIME = 0.000983  # s/bin, ~0.983 ms

CFG = {
    "version": "test",
    "_config_hash": "deadbeefcafe0001",
    "lightcurve": {"weighting": "invvar"},
    "acf": {"smoothing_sigma": 3.0, "spike_nsigma": 3.0,
            "min_lag_bins": 2, "max_lag_ms": 50.0},
    "peaks": {"detect_snr": 5.0, "min_separation_bins": 2, "match_tol_ms": 2.0,
              "secondary_psnr_min": 10.0, "component_halfwidth_bins": 3},
    "ks": {"n_f": 512, "d_crit": 0.1, "alpha": 0.05, "bootstrap_iters": 300,
           "upp_percentile": 99.73, "bootstrap_seed": 20260722},
    "hardness": {"n_bands": 3, "consistency_nsigma": 1.0},
}


def _gauss(nt, center, width):
    t = np.arange(nt)
    return np.exp(-0.5 * ((t - center) / width) ** 2)


def make_tb(nf=16384, nt=200, seed=0, copy=True, delay_bins=20, rf=2.0,
            drift=False):
    """Synthetic Tier B dict: a single burst, optionally with a delayed scaled
    achromatic copy. `drift=True` shifts the copy's spectrum in frequency so it
    is NOT an achromatic copy (should be rejected by the K-S test)."""
    rng = np.random.default_rng(seed)
    freqs = np.linspace(400.0, 800.0, nf)
    # smooth per-channel spectral envelope (same for both images if achromatic)
    envelope = 1.0 + 0.5 * np.sin(np.linspace(0, 3 * np.pi, nf))
    sigma_chan = np.full(nf, 0.05)

    data = rng.standard_normal((nf, nt)).astype(np.float64) * sigma_chan[:, None]

    # narrow (~1 bin) components: a genuine point-mass echo is a sharp copy,
    # so the ACF side-peak must be narrow relative to the sigma=3 smoothing.
    width = 1.0
    c1 = 70
    prof1 = _gauss(nt, c1, width)
    amp1 = 3.0  # strong primary
    data += (amp1 * envelope)[:, None] * prof1[None, :]

    if copy:
        c2 = c1 + delay_bins
        prof2 = _gauss(nt, c2, width)
        env2 = envelope.copy()
        if drift:
            # shift the spectrum -> chromatic (intrinsic drift, not a lens copy)
            env2 = np.roll(env2, nf // 4)
        data += (amp1 / rf * env2)[:, None] * prof2[None, :]

    off = np.ones(nt, bool)
    on0 = 60
    on1 = c1 + (delay_bins if copy else 0) + 10
    off[on0:on1 + 1] = False

    attrs = {"res_time": RES_TIME, "num_time": nt, "noise_failed": False,
             "on_pulse_start": on0, "on_pulse_end": on1}
    return dict(
        standardized=data.astype(np.float32),
        project_mask=np.ones((nf, nt), bool),
        robust_std=sigma_chan.copy(),
        channel_usable=np.ones(nf, bool),
        offpulse=off,
        freqs=freqs,
        times=np.arange(nt) * RES_TIME,
        attrs=attrs,
    ), dict(delay_bins=delay_bins, rf=rf)


# --- (a) recovery -----------------------------------------------------------
def test_recovers_delay_and_ratio():
    tb, truth = make_tb(seed=1, copy=True, delay_bins=20, rf=2.0)
    res = pipeline.run_frb(tb, "FRBSYN_COPY", CFG)
    mpb = RES_TIME * 1e3
    # a spike must exist at the injected delay within +/-1 bin
    want_ms = truth["delay_bins"] * mpb
    assert any(abs(d - want_ms) <= mpb + 1e-9 for d in res["spike_delays_ms"]), \
        res["spike_delays_ms"]
    assert res["is_candidate"], res
    assert abs(res["best_delay_ms"] - want_ms) <= mpb + 1e-9
    # magnification ratio near injected (leading/trailing flux ratio ~ rf)
    assert 1.3 < res["mag_ratio"] < 3.5, res["mag_ratio"]
    assert not res["has_drift"]


def test_acf_amplitude_matches_flux_ratio():
    # ACF spike amplitude ~ R_f/(R_f^2+1); inverting recovers R_f near truth
    tb, truth = make_tb(seed=2, copy=True, delay_bins=24, rf=2.0)
    I, meta = lightcurve.build_lightcurve(tb)
    mpb = RES_TIME * 1e3
    max_lag = int(round(CFG["acf"]["max_lag_ms"] / mpb))
    C = acf.normalized_acf(I, max_lag)
    sp = acf.find_spikes(C, 3.0, 3.0, 2)
    assert sp["spikes"]
    amp = max(s["amplitude"] for s in sp["spikes"])
    rf = acf.rf_from_acf_amplitude(amp)
    assert 1.3 < rf < 3.5, (amp, rf)


# --- (b) control ------------------------------------------------------------
def test_no_copy_yields_no_candidate():
    tb, _ = make_tb(seed=3, copy=False)
    res = pipeline.run_frb(tb, "FRBSYN_SINGLE", CFG)
    assert not res["is_candidate"], res


def test_drifting_copy_is_rejected():
    # a delayed copy whose spectrum is shifted in frequency must NOT be a
    # candidate (K-S detects the drift)
    tb, _ = make_tb(seed=4, copy=True, delay_bins=20, rf=2.0, drift=True)
    res = pipeline.run_frb(tb, "FRBSYN_DRIFT", CFG)
    assert not res["is_candidate"], res
    assert res["has_drift"], res


def test_noise_failed_is_graceful():
    tb, _ = make_tb(seed=5, copy=True)
    tb["attrs"]["noise_failed"] = True
    res = pipeline.run_frb(tb, "FRBSYN_NF", CFG)
    assert not res["is_candidate"]
    assert res["note"] == "noise_failed"
    assert res["n_components"] == 0


# --- (c) determinism --------------------------------------------------------
def test_content_sha256_is_deterministic():
    tb, _ = make_tb(seed=6, copy=True)
    r1 = pipeline.run_frb(tb, "FRBSYN_DET", CFG)
    r2 = pipeline.run_frb(tb, "FRBSYN_DET", CFG)
    I1 = r1.pop("_lightcurve")
    I2 = r2.pop("_lightcurve")
    h1 = pipeline.content_sha256(I1, r1, CFG["_config_hash"])
    h2 = pipeline.content_sha256(I2, r2, CFG["_config_hash"])
    assert h1 == h2
    # and the verdicts themselves agree
    assert r1["best_delay_ms"] == r2["best_delay_ms"]
    assert r1["mag_ratio"] == r2["mag_ratio"]
    assert r1["is_candidate"] == r2["is_candidate"]
