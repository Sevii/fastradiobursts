"""W2.8 — global-FAP machinery unit tests (pure logic)."""
import numpy as np

from echo_frb.search.significance import global_fap as gf


def test_source_bootstrap_preserves_clusters():
    # two sources; one has a high outlier -> catalog-max often equals that outlier
    scores = np.array([1.0, 1.1, 0.9, 50.0])          # last belongs to source B
    sources = np.array(["A", "A", "A", "B"])
    maxima = gf.catalog_max_bootstrap(scores, sources, n_boot=2000, seed=1)
    # when B is drawn, max=50; P(B never drawn in n_src=2 picks) small -> mostly 50
    assert (maxima == 50.0).mean() > 0.5
    assert maxima.min() >= 1.0                          # always at least source A's max


def test_global_fap_monotone_and_bounded():
    maxima = np.linspace(0, 100, 1000)
    f_hi = gf.global_fap(90, maxima)
    f_lo = gf.global_fap(10, maxima)
    assert 0 < f_hi < f_lo <= 1
    assert gf.global_fap(1e9, maxima) == 1 / (1 + len(maxima))   # add-one floor


def test_resolution():
    assert gf.empirical_resolution(20000) == 1 / 20000


def test_gpd_validation_runs():
    rng = np.random.default_rng(0)
    maxima = rng.gumbel(loc=50, scale=5, size=4000)    # extreme-value-like
    params, val = gf.gpd_tail_fit_validate(maxima)
    assert params is not None and len(val) == 3
    # predicted and empirical tail FAPs agree to the same order of magnitude
    for v in val:
        if v["emp_fap"] > 0:
            assert 0.1 < (v["pred_fap"] + 1e-9) / (v["emp_fap"] + 1e-9) < 10
