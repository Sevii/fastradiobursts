"""Task 8 — unit tests for per-product QC checks."""
import numpy as np

from echo_frb.qc.checks import check_product, overall_pass, failed_checks

NF, NT = 128, 40
RES_FREQ = 0.0244140625


def good_product():
    freqs = np.linspace(400.2, 800.2, NF)
    times = np.arange(NT, dtype="float64")
    rng = np.random.default_rng(0)
    off = np.ones(NT, bool)
    off[19:22] = False                      # on-pulse 19..21
    std = rng.standard_normal((NF, NT)).astype(np.float32) * 0.03
    # ensure off-pulse per-channel median ~0 (subtract it, as the pipeline does)
    med = np.median(std[:, off], axis=1)
    std = std - med[:, None]
    flag = np.ones((NF, NT), bool)
    gf = np.ones(NF, bool)
    pm = flag.copy()
    robust = np.full(NF, 0.03)
    usable = np.ones(NF, bool)
    return dict(standardized=std, original_flag=flag, original_good_freq=gf,
                project_mask=pm, robust=robust, channel_usable=usable,
                offmask=off, freqs=freqs, times=times,
                attrs={"on_pulse_start": 19, "on_pulse_end": 21})


def test_good_product_passes():
    checks, vals = check_product(good_product(), RES_FREQ)
    assert overall_pass(checks), failed_checks(checks)
    assert vals["n_usable_channels"] == NF


def test_noise_failure_detected():
    p = good_product()
    p["channel_usable"] = np.zeros(NF, bool)   # no usable channels
    checks, _ = check_product(p, RES_FREQ)
    assert not checks["noise_positive_finite"]


def test_negative_noise_detected():
    p = good_product()
    p["robust"] = p["robust"].copy(); p["robust"][5] = -1.0
    checks, _ = check_product(p, RES_FREQ)
    assert not checks["noise_positive_finite"]


def test_offpulse_overlap_detected():
    p = good_product()
    p["offmask"] = np.ones(NT, bool)            # off-pulse marks the burst bins
    checks, _ = check_product(p, RES_FREQ)
    assert not checks["offpulse_excludes_burst"]


def test_mask_shape_mismatch_detected():
    p = good_product()
    p["project_mask"] = np.ones((NF, NT + 1), bool)
    checks, _ = check_product(p, RES_FREQ)
    assert not checks["project_mask_shape"]


def test_nonfinite_unmasked_detected():
    p = good_product()
    p["standardized"] = p["standardized"].copy()
    p["standardized"][0, 0] = np.inf            # unmasked (project_mask True)
    checks, _ = check_product(p, RES_FREQ)
    assert not checks["unmasked_finite"]


def test_freq_not_monotonic_detected():
    p = good_product()
    p["freqs"] = p["freqs"][::-1].copy()
    checks, _ = check_product(p, RES_FREQ)
    assert not checks["freq_monotonic"]


def test_usable_channels_consistency():
    p = good_product()
    checks, _ = check_product(p, RES_FREQ, manifest_usable_channels=NF - 3)
    assert not checks["usable_channels_consistent"]
