"""W3b — v2 freeze consistency: v2 must be v1 PLUS a margin block, nothing else.

The scientific claim of `wp2-frozen-v2` is that it tightens v1 by pricing the
within-burst multiplicity — not that it re-tunes anything. That claim is only
credible if every analysis-affecting section is byte-identical to v1. These tests
enforce it, so a stray threshold edit cannot ride along inside the revision.
"""
import os

import pytest
import yaml

from echo_frb.search.margin import statistic as ms

CFG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
V1_PATH = os.path.join(CFG_DIR, "wp2_analysis_config.yaml")
V2_PATH = os.path.join(CFG_DIR, "wp2_analysis_config_v2.yaml")

# every section that can change what the pipeline decides
INVARIANT_SECTIONS = ["delay_domain", "copy_statistic", "candidate_criterion",
                      "robustness_tolerances", "tier1", "split", "quarantine",
                      "nulls", "injection", "global_significance"]


@pytest.fixture(scope="module")
def v1():
    return yaml.safe_load(open(V1_PATH))


@pytest.fixture(scope="module")
def v2():
    return yaml.safe_load(open(V2_PATH))


@pytest.mark.parametrize("section", INVARIANT_SECTIONS)
def test_v2_leaves_every_analysis_section_untouched(v1, v2, section):
    assert v2[section] == v1[section], (
        f"v2 changed `{section}`. v2 is meant to add the margin calibration ONLY; "
        f"a threshold change here is a different analysis and needs its own "
        f"justification and version.")


def test_v2_is_a_new_version_superseding_v1(v1, v2):
    assert v1["analysis_version"] == "wp2-frozen-v1"
    assert v2["analysis_version"] == "wp2-frozen-v2"
    assert v2["supersedes"]["analysis_version"] == v1["analysis_version"]
    assert v2["supersedes"]["analysis_config_sha16"] == "3712e96faa969fcc"


def test_v1_has_no_margin_block(v1):
    """v1 must stay exactly as WP3 round 1 scored it — the audit trail depends on it."""
    assert "margin" not in v1


def test_margin_scales_cover_every_gate(v2):
    sc = v2["margin"]["scales"]
    assert set(sc) == set(ms.DEFAULT_SCALES), (
        f"gate/scale mismatch: missing {set(ms.DEFAULT_SCALES) - set(sc)}, "
        f"extra {set(sc) - set(ms.DEFAULT_SCALES)}")
    assert all(v > 0 for v in sc.values())


def test_margin_scales_load_through_the_statistic(v2):
    sc = ms.scales(v2)
    assert sc == {k: float(v) for k, v in v2["margin"]["scales"].items()}
    assert sc != ms.DEFAULT_SCALES              # the frozen values, not the placeholders


def test_thresholds_are_identical_under_v1_and_v2(v1, v2):
    """The c_k come from the shared criterion sections, so they cannot drift."""
    assert ms.thresholds(v1) == ms.thresholds(v2)


def test_scintillation_is_gated(v2):
    """PI decision 2026-07-24 — promoted from monitored residual to gated family."""
    assert v2["margin"]["scintillation_gated"] is True
    assert "adverse_scintillation" in v2["margin"]["null_families"]


def test_alpha_is_the_dry_run_operating_point(v2):
    """alpha was chosen on validation (W3b.6) and is committed before pool 1 is drawn."""
    assert v2["margin"]["alpha"] == 0.05


def test_alpha_is_resolvable_by_the_conditioning(v2):
    """A cell thinner than ~factor/alpha cannot evidence alpha — it only produces
    an efficiency cliff. min_stratum_n must be large enough to rule that out."""
    m = v2["margin"]
    cond, alpha = m["conditioning"], m["alpha"]
    assert cond["min_stratum_n"] >= cond["min_cell_resolution_factor"] / alpha - 1, (
        f"min_stratum_n={cond['min_stratum_n']} cannot resolve alpha={alpha}: a cell "
        f"that small has an empirical floor above it, so no burst can ever pass.")


def test_freeze_date_is_set_at_pi_signoff(v2):
    """frozen_date stays null until the PI signs the round-2 addendum (W3b.7).

    Expected to be UPDATED at sign-off — deliberately, so cutting the freeze is a
    visible, reviewed edit rather than a quiet one.
    """
    assert v2["frozen_date"] is None


def test_tail_model_is_prespecified(v2):
    """The GPD threshold must not be chosen by fit quality after seeing the tail."""
    t = v2["margin"]["tail"]
    assert t["model"] == "gpd"
    assert 0.5 < t["threshold_quantile"] < 1.0
    assert t["report_empirical_fraction"] is True
