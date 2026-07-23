"""W1.7 — WP1 golden/integration tests.

Lock in the headline reproduced facts against the on-disk artifacts, so a re-run
that silently changes them fails CI. Artifact-gated (the parquets live on popos):
skipped unless ECHO_FRB_WP1_ARTIFACTS points at the wp1_repro workspace — mirrors
the ECHO_FRB_DATA opt-in in tests/test_schema_contract.py.
"""
import os

import pytest

ART = os.environ.get("ECHO_FRB_WP1_ARTIFACTS")
pytestmark = pytest.mark.skipif(
    not ART, reason="set ECHO_FRB_WP1_ARTIFACTS=<wp1_repro dir> to run")


def _pq(*parts):
    import pandas as pd
    return pd.read_parquet(os.path.join(ART, *parts))


def test_literal_G3_reproduces_committed_11():
    lit = _pq("sensitivity", "sweep_literal_long.parquet")
    import yaml
    yml = os.path.join(os.path.dirname(__file__), "..", "src", "echo_frb",
                       "repro", "target", "authors_reported_values.yaml")
    committed = set(yaml.safe_load(open(yml))["selection_funnel"]["by_config"]["G_3"]["names"])
    ours = set(lit[(lit.config == "G_3") & lit.is_candidate].frb_name)
    assert len(ours) == 11
    assert ours == committed


def test_cleanroom_single_candidate_is_20190131D():
    cr = _pq("cleanroom_run", "cleanroom_scores.parquet")
    cands = set(cr[cr.is_candidate].frb_name)
    assert cands == {"FRB20190131D"}


def test_named_candidate_reproduction_facts():
    cr = _pq("cleanroom_run", "cleanroom_scores.parquet").set_index("frb_name")
    a = cr.loc["FRB20190131D"]
    assert bool(a.is_candidate) and abs(float(a.best_delay_ms) - 8.82) <= 0.983
    b = cr.loc["FRB20211115A"]
    assert not bool(b.is_candidate) and int(b.n_spikes) == 0   # fragile: no spike


def test_selection_chain_covers_all_340():
    chain = _pq("selection", "candidate_selection_chain.parquet")
    assert len(chain) == 340
    assert chain["literal_stage"].notna().all()
    assert chain["cleanroom_stage"].notna().all()


def test_only_20190131D_robust_across_all_configs():
    stab = _pq("sensitivity", "candidate_stability.parquet")
    robust = set(stab[stab.survival_fraction == 1.0].frb_name)
    assert "FRB20190131D" in robust
    assert "FRB20211115A" not in robust
