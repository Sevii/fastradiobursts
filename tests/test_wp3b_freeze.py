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


def test_analysis_config_is_frozen(v2):
    """frozen_date set 2026-07-25 with the PI's target decisions (W3b.7-F)."""
    assert v2["frozen_date"] == "2026-07-25"


# --- W3b.7-F: the round-2 harness ------------------------------------------

WP3_V2_PATH = os.path.join(CFG_DIR, "wp3_blind_config_v2.yaml")


@pytest.fixture(scope="module")
def wp3v2():
    return yaml.safe_load(open(WP3_V2_PATH))


def test_round2_harness_targets_the_v2_analysis(wp3v2):
    assert wp3v2["wp3_version"] == "wp3-blind-v2"
    assert wp3v2["frozen"]["analysis_version"] == "wp2-frozen-v2"
    assert wp3v2["frozen"]["analysis_config"].endswith("wp2_analysis_config_v2.yaml")


def test_round2_draws_from_pool_1(wp3v2):
    """Pool 0 is burned. The salt must not change — repartitioning would remix
    burned sources into a supposedly fresh pool."""
    assert wp3v2["pools"]["round"] == 2
    assert wp3v2["pools"]["salt"] == "echo-frb-wp3-blind-v1"
    assert wp3v2["pools"]["split_source"] == "test"


def test_round2_mixture_fits_pool_1(wp3v2):
    """362 bursts available; roles are disjoint, so the recipe must fit."""
    mx = wp3v2["mixture"]
    distinct = mx["n_real_null"] + mx["n_injections"] + mx["n_per_adverse_kind"]
    assert distinct <= 362, f"recipe needs {distinct} distinct bursts, pool 1 has 362"
    assert mx["n_per_adverse_kind"] > 0, "the class that failed round 1 must be present"


def test_round2_targets_match_the_pi_decisions(wp3v2):
    """PI decisions 1-3, 2026-07-25 (docs/WP3b_preregistration_addendum.md §3)."""
    g2 = wp3v2["gate"]["g2_false_positive"]
    assert g2["scintillation_gated"] is True
    assert g2["scintillation"] == 0.10          # decision 1
    assert g2["gate_on"] == "point_estimate"    # decision 2
    assert g2["deterministic"] == 0.025         # decision 3
    assert g2["real"] == 0.01
    assert g2["differential_scattering"] == 0.10


def test_every_gated_target_is_expressible_at_its_sample_size(wp3v2):
    """A target below 1/n is zero-tolerance; below that it is unattainable.

    This is the arithmetic behind decision 3: at n=40 the achievable rates are
    0, 0.025, 0.05, ... so a 0.01 target cannot be distinguished from 0 and any
    single false positive fails it. Every target must be >= 1/n for its class, or
    the gate is testing sampling noise rather than the analysis.
    """
    g2, mx = wp3v2["gate"]["g2_false_positive"], wp3v2["mixture"]
    n_adv, n_real = mx["n_per_adverse_kind"], mx["n_real_null"]
    for key, n in [("deterministic", n_adv), ("differential_scattering", n_adv),
                   ("scintillation", n_adv), ("real", n_real)]:
        assert g2[key] >= 1.0 / n, (
            f"target {key}={g2[key]} is below 1/{n}={1.0/n:.4f}: a single false "
            f"positive would fail it, so the gate tests noise, not the analysis.")


def test_round2_harness_is_pinned(wp3v2):
    assert wp3v2["frozen"]["analysis_config_sha16"] == "a24f285e569e211e"
    assert len(wp3v2["frozen"]["calibration_manifest_sha256"]) == 64
    assert wp3v2["frozen_date"] == "2026-07-25"


def test_pinned_hash_matches_the_live_analysis_config(wp3v2):
    """The whole freeze rests on this equality — assert it directly."""
    from echo_frb.search.blind import foundation
    got = foundation.config_sha16(os.path.join(CFG_DIR, "wp2_analysis_config_v2.yaml"))
    assert got == wp3v2["frozen"]["analysis_config_sha16"], (
        f"the analysis config has drifted since it was pinned: {got} != "
        f"{wp3v2['frozen']['analysis_config_sha16']}")


def test_freeze_contract_accepts_the_signed_harness(wp3v2):
    from echo_frb.search.blind import foundation
    repo = os.path.join(os.path.dirname(__file__), "..")
    assert foundation.assert_freeze_contract(wp3v2, repo) == "a24f285e569e211e"


def test_freeze_contract_still_refuses_an_unpinned_harness(wp3v2):
    """The refusal MECHANISM must survive our own harness being signed."""
    from echo_frb.search.blind import foundation
    import copy
    repo = os.path.join(os.path.dirname(__file__), "..")
    unsigned = copy.deepcopy(wp3v2)
    unsigned["frozen"]["analysis_config_sha16"] = None
    with pytest.raises(AssertionError, match="HARNESS NOT SIGNED"):
        foundation.assert_freeze_contract(unsigned, repo)


def test_round1_harness_still_pins_v1(v1):
    """Round 1 must stay reproducible against the analysis that produced it."""
    wp3v1 = yaml.safe_load(open(os.path.join(CFG_DIR, "wp3_blind_config.yaml")))
    assert wp3v1["frozen"]["analysis_config_sha16"] == "3712e96faa969fcc"
    assert wp3v1["frozen"]["analysis_version"] == v1["analysis_version"]


def test_tail_model_is_prespecified(v2):
    """The GPD threshold must not be chosen by fit quality after seeing the tail."""
    t = v2["margin"]["tail"]
    assert t["model"] == "gpd"
    assert 0.5 < t["threshold_quantile"] < 1.0
    assert t["report_empirical_fraction"] is True
