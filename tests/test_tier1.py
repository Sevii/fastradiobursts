"""W2.1 — Tier-1 scan unit tests (synthetic Tier B; no archive data)."""
import numpy as np

from echo_frb.search.tier1 import profile, scan

CFG = {"delay_domain": {"dt_min_ms": 2.0, "dt_max_ms": 50.0,
                        "per_burst_window_fraction": 0.4, "grid_step_ms": 0.5}}


def _synth_tb(nf=64, nt=120, sep=12, a2=0.5, seed=0):
    """Two-component burst: main at nt//3, copy `sep` bins later, x a2."""
    rng = np.random.default_rng(seed)
    env = 1.0 + 0.4 * np.cos(np.linspace(0, 3, nf))
    t = np.arange(nt)
    c1 = nt // 3
    prof = np.exp(-0.5 * ((t - c1) / 2.5) ** 2) + a2 * np.exp(-0.5 * ((t - c1 - sep) / 2.5) ** 2)
    sig = 0.05 * np.ones(nf)
    std = env[:, None] * prof[None, :] + sig[:, None] * rng.standard_normal((nf, nt))
    off = np.ones(nt, bool); off[c1 - 8:c1 + sep + 8] = False   # off-pulse away from burst
    return dict(standardized=std.astype(np.float32),
                project_mask=np.ones((nf, nt), bool),
                robust_std=sig, channel_usable=np.ones(nf, bool),
                offpulse=off, times=t * 0.983e-3, freqs=np.arange(nf),
                res_time=0.983e-3, tns_name="FRBSYN", noise_failed=False, attrs={})


def test_profile_recovers_two_components():
    tb = _synth_tb()
    p = profile.build_profile(tb)
    assert p["sigma_off"] > 0
    # profile peaks well above off-pulse noise
    assert (p["I"].max() - p["mu_off"]) / p["sigma_off"] > 10


def test_scan_proposes_the_true_pair():
    tb = _synth_tb(sep=12, a2=0.5)
    rows, _ = scan.scan_burst(tb, CFG)
    assert rows, "expected at least one proposal"
    seps = [r["delay_bins"] for r in rows]
    assert 12 in seps                                   # the injected separation
    r = next(r for r in rows if r["delay_bins"] == 12)
    assert r["delay_ms"] > CFG["delay_domain"]["dt_min_ms"]
    assert r["triage_ncc"] > 0.5                        # the two components correlate


def test_scan_respects_delay_domain():
    tb = _synth_tb(sep=1)                                # separation below dt_min
    rows, _ = scan.scan_burst(tb, CFG)
    # a 1-bin (~1 ms) separation is below dt_min (2 ms) -> not proposed as a pair
    assert all(r["delay_ms"] >= CFG["delay_domain"]["dt_min_ms"] for r in rows)
