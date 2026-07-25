"""W3b.5 — conditional-calibration tests (synthetic ensembles; no archive data)."""
import numpy as np
import pandas as pd
import pytest

from echo_frb.search.margin import calibrate as cal

CFG = {"margin": {
    "conditioning": {"strata": ["n_proposals", "peak_snr"],
                     "n_proposals_bins": [1, 2, 4, 7, 11],
                     "peak_snr_bins": [0, 10, 20, 50, np.inf],
                     "min_stratum_n": 50},
    "tail": {"model": "gpd", "threshold_quantile": 0.90, "min_exceedances": 30,
             "report_empirical_fraction": True}}}


def _ensemble(family, n, loc=0.0, scale=1.0, seed=0, n_proposals=5, snr=30.0,
              truth="null"):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(dict(
        family=family, truth_class=truth, error="",
        M=rng.normal(loc, scale, n),
        n_proposals=n_proposals, peak_snr=snr,
        source_id=[f"S{i % max(1, n // 3)}" for i in range(n)]))


# --- stratification ----------------------------------------------------------

@pytest.mark.parametrize("v,expect", [(1, 0), (2, 1), (3, 1), (4, 2), (6, 2),
                                      (7, 3), (10, 3), (99, 3), (0, 0)])
def test_n_proposals_binning_is_right_open_and_clamped(v, expect):
    cond, _ = cal._cfg_blocks(CFG)
    assert cal._bin_index(v, cond["n_proposals_bins"]) == expect


def test_stratum_key_combines_both_axes():
    cond, _ = cal._cfg_blocks(CFG)
    assert cal.stratum_key({"n_proposals": 8, "peak_snr": 100.0}, cond) == (3, 3)
    assert cal.stratum_key({"n_proposals": 1, "peak_snr": 5.0}, cond) == (0, 0)


def test_nonfinite_covariate_lands_in_the_first_bin():
    cond, _ = cal._cfg_blocks(CFG)
    assert cal.stratum_key({"n_proposals": 3, "peak_snr": np.nan}, cond) == (1, 0)


# --- the empirical estimator and its floor -----------------------------------

def test_empirical_pvalue_uses_the_conservative_estimator():
    c = cal.Cell("f", "all", np.arange(100.0), CFG["margin"]["tail"], "family")
    p, k = c.p_empirical(94.5)                    # 95..99 exceed -> k = 5
    assert k == 5
    assert p == pytest.approx(6 / 101)


def test_p_never_drops_below_the_empirical_floor():
    """A fitted curve reaching 1e-4 is not evidence of 1e-4."""
    null = _ensemble("real", 400, seed=1)
    c = cal.Calibration.fit(null, CFG)
    r = c.pvalues(50.0, {"n_proposals": 5, "peak_snr": 30.0})   # far beyond every null
    fam = r["per_family"]["real"]
    assert fam["n_exceed"] == 0
    assert fam["at_empirical_floor"]
    assert fam["p"] >= 1.0 / (fam["n_null"] + 1.0)


def test_gpd_can_only_make_the_answer_more_conservative():
    null = _ensemble("real", 600, seed=2)
    c = cal.Calibration.fit(null, CFG)
    cell = c._cell("real", (2, 3))
    for m in np.linspace(0.0, 6.0, 25):
        r = cell.pvalue(m)
        assert r["p"] >= r["p_empirical"] - 1e-12


def test_gpd_is_not_used_below_its_prespecified_threshold():
    null = _ensemble("real", 600, seed=3)
    c = cal.Calibration.fit(null, CFG)
    cell = c._cell("real", (2, 3))
    assert np.isfinite(cell.u)
    assert np.isnan(cell.p_gpd(cell.u - 0.1))
    assert np.isfinite(cell.p_gpd(cell.u + 0.5))


def test_thin_cell_gets_no_tail_model():
    """min_exceedances guards against fitting a GPD to a handful of points."""
    null = _ensemble("real", 60, seed=4)
    c = cal.Calibration.fit(null, CFG)
    cell = c._cell("real", "all")
    assert cell.n_exc == 0 and np.isnan(cell.u)


# --- pooling fallback --------------------------------------------------------

def test_thin_strata_fall_back_to_the_parent_cell():
    thin = _ensemble("real", 40, n_proposals=5, snr=30.0, seed=5)
    fat = _ensemble("real", 300, n_proposals=1, snr=5.0, seed=6)
    c = cal.Calibration.fit(pd.concat([thin, fat]), CFG)
    r = c.pvalues(0.5, {"n_proposals": 5, "peak_snr": 30.0})
    assert r["cell_level"] == "family"          # 40 < min_stratum_n -> pooled up
    r2 = c.pvalues(0.5, {"n_proposals": 1, "peak_snr": 5.0})
    assert r2["cell_level"] == "n_proposals+snr"


def test_conditioning_changes_the_pvalue():
    """A proposal-rich stratum has a heavier max tail — that is the whole point."""
    quiet = _ensemble("real", 300, loc=0.0, n_proposals=1, snr=5.0, seed=7)
    busy = _ensemble("real", 300, loc=3.0, n_proposals=9, snr=100.0, seed=8)
    c = cal.Calibration.fit(pd.concat([quiet, busy]), CFG)
    p_quiet = c.pvalues(2.5, {"n_proposals": 1, "peak_snr": 5.0})["p_robust"]
    p_busy = c.pvalues(2.5, {"n_proposals": 9, "peak_snr": 100.0})["p_robust"]
    assert p_busy > p_quiet


# --- p_robust = max over families -------------------------------------------

def test_p_robust_is_the_worst_family():
    benign = _ensemble("real", 300, loc=0.0, seed=9)
    nasty = _ensemble("adverse_scintillation", 300, loc=2.5, seed=10)
    c = cal.Calibration.fit(pd.concat([benign, nasty]), CFG)
    r = c.pvalues(2.0, {"n_proposals": 5, "peak_snr": 30.0})
    assert r["worst_family"] == "adverse_scintillation"
    assert r["p_robust"] == r["per_family"]["adverse_scintillation"]["p"]
    assert r["p_robust"] >= r["per_family"]["real"]["p"]


def test_positives_are_excluded_from_the_null_fit():
    null = _ensemble("real", 300, loc=0.0, seed=11)
    pos = _ensemble("injection", 300, loc=5.0, seed=12, truth="positive")
    c = cal.Calibration.fit(pd.concat([null, pos]), CFG)
    assert "injection" not in c.families
    assert c.pvalues(4.0, {"n_proposals": 5, "peak_snr": 30.0})["worst_family"] == "real"


def test_apply_returns_one_row_per_burst():
    null = _ensemble("real", 300, seed=13)
    c = cal.Calibration.fit(null, CFG)
    obs = pd.DataFrame(dict(M=[0.1, 3.0], n_proposals=[3, 8], peak_snr=[12.0, 60.0]))
    out = c.apply(obs)
    assert len(out) == 2
    assert "p_robust" in out and "p_real" in out
    assert out.p_robust.iloc[0] > out.p_robust.iloc[1]     # weaker M -> larger p


# --- infinities and degenerate input ----------------------------------------

def test_bursts_with_no_proposals_stay_in_the_denominator():
    """Tier-1 silence is a real null outcome, not a missing observation."""
    d = _ensemble("real", 200, seed=14)
    d.loc[d.index[:100], "M"] = -np.inf
    c = cal.Calibration.fit(d, CFG)
    cell = c._cell("real", "all")
    assert cell.n == 200
    p, k = cell.p_empirical(0.0)
    assert p == pytest.approx((1 + k) / 201)


def test_summary_reports_the_tail_provenance():
    null = _ensemble("real", 600, seed=15)
    s = cal.Calibration.fit(null, CFG).summary()
    assert {"family", "stratum", "n", "gpd_u", "n_exceedances",
            "empirical_floor"} <= set(s.columns)
    assert (s.empirical_floor > 0).all()


# --- cluster bootstrap -------------------------------------------------------

def test_cluster_bootstrap_brackets_the_point_estimate():
    rng = np.random.default_rng(0)
    df = pd.DataFrame(dict(flag=rng.random(500) < 0.1,
                           source_id=[f"S{i % 50}" for i in range(500)]))
    point, lo, hi = cal.cluster_bootstrap_rate(df, "flag", n_boot=400, seed=1)
    assert lo <= point <= hi
    assert 0.0 <= lo and hi <= 1.0


def test_cluster_bootstrap_widens_with_dependent_bursts():
    """One source contributing many bursts must not count as many independent ones.

    The dependence that matters is WITHIN-cluster correlation: a repeater's bursts
    share a morphology, so they tend to pass or fail together. Modelled here as
    whole sources being all-flag or no-flag — the same 500 observations and the
    same point estimate, but 10 effective samples instead of 500.
    """
    source = np.array([f"S{i % 10}" for i in range(500)])
    flags = np.isin(source, ["S0", "S1"])          # 2 of 10 sources flag entirely
    clustered = pd.DataFrame(dict(flag=flags, source_id=source))
    indep = pd.DataFrame(dict(flag=flags, source_id=[f"S{i}" for i in range(500)]))
    p_c, lo_c, hi_c = cal.cluster_bootstrap_rate(clustered, "flag", n_boot=600, seed=3)
    p_i, lo_i, hi_i = cal.cluster_bootstrap_rate(indep, "flag", n_boot=600, seed=3)
    assert p_c == pytest.approx(p_i)               # identical point estimate
    assert (hi_c - lo_c) > 3 * (hi_i - lo_i)       # honest uncertainty is far wider
