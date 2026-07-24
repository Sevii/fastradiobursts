"""W2.9 — freeze consistency: the frozen config must match the code constants.

Guards against silent drift between the preregistered thresholds
(config/wp2_analysis_config.yaml) and the constants the code actually uses.
"""
import inspect
import os

import yaml
import pytest

from echo_frb.search.copy import statistic as st
from echo_frb.search.injection import efficiency as eff
from echo_frb.search.benchmark import full_criterion as fc
from echo_frb.search.robustness import diagnostics as diag

CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "config",
                        "wp2_analysis_config.yaml")


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load(open(CFG_PATH))


def test_frozen_version(cfg):
    assert cfg["analysis_version"] == "wp2-frozen-v1"
    assert cfg["frozen_date"] == "2026-07-23"


def test_candidate_criterion_matches_code(cfg):
    cc = cfg["candidate_criterion"]
    assert fc.DELTA_MIN == cc["detect_delta_chi2_min"]
    assert fc.NCC_MIN == cc["copy_ncc_min"]
    assert fc.RED_MAX == cc["copy_reduced_chi2_max"]
    assert fc.NPASS_MIN == cc["robustness_n_pass_min"]
    # injection recovery uses the same detectability + copy-quality
    assert eff.RECOVERY["delta_min"] == cc["detect_delta_chi2_min"]
    assert eff.RECOVERY["ncc_min"] == cc["copy_ncc_min"]
    assert eff.RECOVERY["reduced_max"] == cc["copy_reduced_chi2_max"]


def test_statistic_defaults_match_config(cfg):
    sig = inspect.signature(st.copy_score).parameters
    cs = cfg["copy_statistic"]
    assert sig["rebin_nf"].default == cs["rebin_nf"]
    assert sig["on_burst_k"].default == cs["on_burst_k"]


def test_robustness_tolerances_match_config(cfg):
    rt = cfg["robustness_tolerances"]
    assert diag.TOL["delay_bins"] == rt["delay_spread_bins_max"]
    assert diag.TOL["mag_rel"] == rt["mag_rel_spread_max"]
    # spectral-magnification catcher default
    sig = inspect.signature(diag._spectral_mag_flatness).parameters
    assert sig["tol_reduced"].default == rt["spectral_mag_reduced_max"]
