"""W1.5 sensitivity-sweep unit tests (pure logic — no archive data)."""
import numpy as np
import pandas as pd

from echo_frb.repro.sensitivity import smoothing, sweep_literal, aggregate


def test_smoothing_method_switch_changes_baseline():
    # a smooth ACF-like curve with one sharp spike
    lags = np.arange(60)
    y = np.exp(-lags / 20.0)
    y[30] += 0.5
    ac = y.copy()
    smoothing.set_smoothing("gaussian")
    g = smoothing.detect_autocorr_spikes(ac, lags, smooth_sigma=3, threshold=3,
                                         min_lag=1, return_details=True)
    smoothing.set_smoothing("savgol", window_length=20, polyorder=3)
    s = smoothing.detect_autocorr_spikes(ac, lags, smooth_sigma=3, threshold=3,
                                         min_lag=1, return_details=True)
    # the two smoothing methods produce different baselines...
    assert not np.allclose(g["autocorr_smoothed"], s["autocorr_smoothed"])
    # ...but both detect the injected spike at lag 30
    assert 30 in list(g["spike_lags"])
    assert 30 in list(s["spike_lags"])
    smoothing.set_smoothing("gaussian")  # reset


def test_gaussian_path_matches_scipy():
    from scipy.ndimage import gaussian_filter1d
    smoothing.set_smoothing("gaussian")
    y = np.linspace(1, 0, 40) + 0.01 * np.arange(40)
    got = smoothing._smooth(y, 3.0)
    assert np.allclose(got, gaussian_filter1d(y, sigma=3.0, mode="reflect"))


def test_make_lib_strips_driver(tmp_path):
    src = tmp_path / "SearchLensedFRB.py"
    src.write_text("def process_frb_catalog_lens():\n    return []\n\n"
                   "results = process_frb_catalog_lens(\n    catalog_file='x')\n")
    lib = sweep_literal.make_lib(str(tmp_path))
    text = open(lib).read()
    assert "def process_frb_catalog_lens" in text
    assert "results = process_frb_catalog_lens(" not in text


def test_default_configs_are_one_axis_off_baseline():
    cfgs = sweep_literal.default_configs()
    b = sweep_literal.baseline()
    names = [c["name"] for c in cfgs]
    assert names[0] == "G_3" and {"SG_20", "SG_100"} <= set(names)
    # every non-baseline config differs from baseline in exactly one analysis field
    keys = ["method", "window_length", "smooth_sigma", "threshold", "rfi_factor",
            "f_down", "n_noise", "min_diff_threshold"]
    for c in cfgs[1:]:
        diffs = [k for k in keys if c[k] != b[k]]
        # SG configs change method (+window is coupled); others change exactly one
        assert len(diffs) <= 2


def _long(rows):
    return pd.DataFrame(rows)


def test_aggregate_matrix_and_stability(tmp_path):
    lit = _long([
        dict(config="G_3", frb_name="A", is_candidate=True),
        dict(config="G_3", frb_name="B", is_candidate=True),
        dict(config="SG_20", frb_name="A", is_candidate=True),
        dict(config="SG_20", frb_name="B", is_candidate=False),
    ])
    p = tmp_path / "lit.parquet"; lit.to_parquet(p, index=False)
    mat, stab, verify = aggregate.build(str(p), None, None)
    assert set(mat.frb_name) == {"A", "B"}          # both ever-candidate
    a = stab[stab.frb_name == "A"].iloc[0]
    b = stab[stab.frb_name == "B"].iloc[0]
    assert a.survival_fraction == 1.0 and bool(a.robust)      # A in both runs
    assert b.survival_fraction == 0.5 and not bool(b.robust)  # B in one of two
