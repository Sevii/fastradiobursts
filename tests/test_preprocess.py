"""Task 6 — preprocessing unit tests (determinism, off-pulse, baseline/noise,
spectral-envelope preservation)."""
import numpy as np
import pytest

from echo_frb.preprocess import standardize as S

CFG = {
    "preprocessing_version": "test-v1",
    "_config_hash": "deadbeefcafe0001",
    "offpulse": {"guard_bins": 5, "derive_threshold_mad": 5.0,
                 "min_offpulse_bins": 16},
    "baseline": {"method": "median"},
    "noise": {"robust": "mad", "conventional": "std", "min_samples": 16},
    "project_mask": {"from_original": True, "mask_unstable_noise_channels": True,
                     "noise_outlier_nsigma": 5.0},
    "output": {"compression": "gzip", "compression_level": 4,
               "float_dtype": "float32"},
}


def synth(nf=64, nt=120, seed=0, envelope=True):
    """Synthetic dynamic spectrum: per-channel noise + a burst at t=60."""
    rng = np.random.default_rng(seed)
    sigma = np.linspace(0.02, 0.05, nf).astype(np.float32)   # per-channel noise
    data = (rng.standard_normal((nf, nt)).astype(np.float32) * sigma[:, None])
    # per-channel burst amplitude = spectral envelope (varies across channels)
    amp = (np.linspace(0.5, 1.5, nf) if envelope else np.ones(nf)).astype(np.float32)
    burst = np.zeros(nt, np.float32)
    burst[59:62] = [0.4, 1.0, 0.4]
    data += amp[:, None] * burst[None, :]
    flag = np.ones((nf, nt), bool)
    good_freq = np.ones(nf, bool)
    pulse_region = np.array([[59, 61]], dtype=np.int64)
    return data, flag, good_freq, pulse_region, sigma, amp


def test_offpulse_excludes_burst():
    data, flag, gf, pr, _, _ = synth()
    offmask, (on0, on1), method = S.derive_offpulse(data, flag, gf, pr, CFG)
    assert method == "pulse_emission_region"
    assert not offmask[60]                 # burst bin is on-pulse
    assert on0 <= 59 and on1 >= 61
    assert offmask[:40].all()              # early bins are off-pulse


def test_offpulse_derived_when_no_region():
    data, flag, gf, _, _, _ = synth()
    offmask, (on0, on1), method = S.derive_offpulse(data, flag, gf, None, CFG)
    assert method == "derived_profile"
    assert not offmask[60]                  # finds the burst near t=60
    assert on0 <= 60 <= on1


def test_noise_recovers_injected_sigma():
    data, flag, gf, pr, sigma, _ = synth(seed=1)
    offmask, *_ = S.derive_offpulse(data, flag, gf, pr, CFG)
    bn = S.estimate_baseline_noise(data, flag, gf, offmask, CFG)
    # robust sigma within 25% of injected, per channel, where quality holds
    q = bn["quality"]
    rel = np.abs(bn["robust_std"][q] - sigma[q]) / sigma[q]
    assert np.median(rel) < 0.25
    assert bn["quality"].all()             # all channels usable in this clean synth


def test_baseline_is_near_zero_for_zero_mean_offpulse():
    data, flag, gf, pr, _, _ = synth(seed=2)
    offmask, *_ = S.derive_offpulse(data, flag, gf, pr, CFG)
    bn = S.estimate_baseline_noise(data, flag, gf, offmask, CFG)
    assert np.abs(bn["baseline"]).max() < 0.05


def test_spectral_envelope_preserved():
    # baseline subtraction must NOT normalize channels to equal burst amplitude
    data, flag, gf, pr, _, amp = synth(seed=3)
    prod = S.standardize(data, flag, gf, pr, CFG)
    std = prod["standardized"]
    # peak amplitude at burst should still scale with the injected envelope
    peak = std[:, 60]
    # correlation between recovered peak and injected envelope stays high
    r = np.corrcoef(peak, amp)[0, 1]
    assert r > 0.9


def test_project_mask_is_separate_and_subset():
    data, flag, gf, pr, _, _ = synth(seed=4)
    prod = S.standardize(data, flag, gf, pr, CFG)
    # original preserved untouched
    assert np.array_equal(prod["original_flag"], flag)
    assert np.array_equal(prod["original_good_freq"], gf)
    # project mask never marks a pixel usable that the original masked
    assert not (prod["project_mask"] & ~flag).any()


def test_content_hash_is_deterministic():
    data, flag, gf, pr, _, _ = synth(seed=5)
    prov = {"source_sha256": "abc", "config_hash": "cfg1",
            "preprocessing_version": "test-v1"}
    p1 = S.standardize(data, flag, gf, pr, CFG)
    p2 = S.standardize(data, flag, gf, pr, CFG)
    assert S.content_sha256(p1, prov) == S.content_sha256(p2, prov)


def test_written_file_is_byte_identical(tmp_path):
    # the completion condition: same source+config -> identical output checksum
    data, flag, gf, pr, _, _ = synth(seed=6)
    prod = S.standardize(data, flag, gf, pr, CFG)
    coords = {"freqs": np.linspace(400, 800, data.shape[0]),
              "times": np.arange(data.shape[1], dtype="float64"),
              "times_unix": np.arange(data.shape[1], dtype="float64") + 1e9}
    prov = {"source_file": "x.h5", "source_sha256": "abc", "config_hash": "cfg1",
            "code_commit": "c0", "preprocessing_version": "test-v1",
            "tns_name": "FRBTEST", "event_id": 1, "dm_incoherent": 500.0,
            "res_time": 9.8e-4, "res_freq": 0.024, "num_time": data.shape[1],
            "content_sha256": "z"}
    a = tmp_path / "a_tierb.h5"
    b = tmp_path / "b_tierb.h5"
    S.write_tier_b(str(a), prod, coords, prov, CFG)
    S.write_tier_b(str(b), prod, coords, prov, CFG)
    assert S.sha256_of(str(a)) == S.sha256_of(str(b))
