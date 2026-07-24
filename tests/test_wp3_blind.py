"""WP3 — blind-injection validation harness tests.

Covers the integrity properties the blind gate depends on, WITHOUT needing the
real hidden set (that is an artifact-gated golden, below):
  - freeze contract catches analysis-config drift;
  - blind-round pools are deterministic, source-disjoint, and test-only;
  - (W3.1+) controller determinism + no-truth-leak, commitment/tamper/ordering,
    evaluator blindness, unblind arithmetic, and gate logic.

Real-hidden-set golden checks run only when ECHO_FRB_WP3_ARTIFACTS points at the
popos wp3 outputs (mirrors tests/test_wp1_golden.py).
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd
import pytest
import yaml

from echo_frb.search.blind import controller, foundation, unblind

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WP3_CFG = os.path.join(REPO, "config", "wp3_blind_config.yaml")
ANA_CFG = os.path.join(REPO, "config", "wp2_analysis_config.yaml")


@pytest.fixture(scope="module")
def wp3_cfg():
    return foundation.load_wp3_config(WP3_CFG)


# ---- freeze contract ------------------------------------------------------
def test_frozen_hash_matches_actual_config(wp3_cfg):
    """The pinned hash must equal the real sha256[:16] of the frozen analysis config."""
    got = foundation.config_sha16(ANA_CFG)
    assert wp3_cfg["frozen"]["analysis_config_sha16"] == got, (
        f"pinned {wp3_cfg['frozen']['analysis_config_sha16']} != actual {got}")


def test_freeze_contract_passes_on_unmodified_config(wp3_cfg):
    h = foundation.assert_freeze_contract(wp3_cfg, REPO)
    assert h == foundation.config_sha16(ANA_CFG)


def test_freeze_contract_detects_drift(tmp_path, wp3_cfg):
    """Any byte change to the analysis config must fail the contract loudly."""
    ana = yaml.safe_load(open(ANA_CFG))
    ana["candidate_criterion"]["detect_delta_chi2_min"] = 999.0   # tamper
    drifted = tmp_path / "config" / "wp2_analysis_config.yaml"
    drifted.parent.mkdir(parents=True)
    yaml.safe_dump(ana, open(drifted, "w"))
    cfg = dict(wp3_cfg)
    cfg["frozen"] = dict(wp3_cfg["frozen"], analysis_config="config/wp2_analysis_config.yaml")
    with pytest.raises(AssertionError, match="DRIFTED"):
        foundation.assert_freeze_contract(cfg, str(tmp_path))


# ---- blind-round pools ----------------------------------------------------
def _fake_split():
    # 12 sources, some repeaters with multiple bursts, split across dev/val/test
    rows = []
    for i in range(12):
        sid = f"SRC{i:02d}"
        split = ["development", "validation", "test"][i % 3]
        nb = 1 + (i % 3)                       # repeaters have >1 burst
        for b in range(nb):
            rows.append(dict(tns_name=f"FRB{i:02d}{b}", source_id=sid,
                             is_repeater=nb > 1, split=split, quarantined=False))
    return pd.DataFrame(rows)


def test_pools_are_deterministic():
    s = _fake_split()
    a = foundation.partition_pools(s, k=3, salt="echo-frb-wp3-blind-v1")
    b = foundation.partition_pools(s, k=3, salt="echo-frb-wp3-blind-v1")
    pd.testing.assert_frame_equal(a, b)


def test_pools_test_only_and_source_disjoint():
    s = _fake_split()
    p = foundation.partition_pools(s, k=3, salt="echo-frb-wp3-blind-v1")
    # only test-split bursts
    assert (p.split == "test").all()
    # every source maps to exactly one pool
    assert (p.groupby("source_id").pool.nunique() <= 1).all()
    # a repeater's bursts share a pool
    for sid, g in p.groupby("source_id"):
        assert g.pool.nunique() == 1


def test_pools_exclude_quarantined():
    s = _fake_split()
    s.loc[s.tns_name == "FRB020", "quarantined"] = True   # a test-split burst
    p = foundation.partition_pools(s, k=3, salt="echo-frb-wp3-blind-v1")
    assert "FRB020" not in set(p.tns_name)


def test_pool_salt_changes_assignment():
    s = _fake_split()
    a = foundation.partition_pools(s, k=3, salt="salt-a")
    b = foundation.partition_pools(s, k=3, salt="salt-b")
    # at least one source lands in a different pool under a different salt
    merged = a.merge(b, on="source_id", suffixes=("_a", "_b"))
    assert (merged.pool_a != merged.pool_b).any()


# ---- W3.1 controller: determinism, no-truth-leak, disjoint roles ----------
def _fake_pool_and_manifest(n=80):
    rng = np.random.default_rng(0)
    rows_p, rows_m = [], []
    for i in range(n):
        tns = f"FRB{i:04d}"
        rows_p.append(dict(tns_name=tns, source_id=tns))
        rows_m.append(dict(tns_name=tns, n_subbursts=(2 if i < 12 else 1),
                           catalog_snr=float(rng.uniform(8, 40)),
                           burst_width_s=float(rng.uniform(1e-3, 6e-3)),
                           usable_bandwidth_mhz=float(rng.uniform(100, 380))))
    return pd.DataFrame(rows_p), pd.DataFrame(rows_m)


def _small_cfg(wp3_cfg):
    cfg = dict(wp3_cfg)
    cfg["mixture"] = dict(wp3_cfg["mixture"], n_injections=10, n_real_null=10,
                          n_per_adverse_kind=2)
    return cfg


def test_controller_build_deterministic(wp3_cfg):
    pool, man = _fake_pool_and_manifest()
    cfg = _small_cfg(wp3_cfg)
    a = controller.build(cfg, {}, pool, man, "/nonexistent", seed=123)
    b = controller.build(cfg, {}, pool, man, "/nonexistent", seed=123)
    assert a[0] == b[0] and a[1] == b[1]                 # items + labels identical
    c = controller.build(cfg, {}, pool, man, "/nonexistent", seed=999)
    assert a[1] != c[1]                                  # different seed -> different labels


def test_controller_manifest_has_no_truth(wp3_cfg):
    pool, man = _fake_pool_and_manifest()
    items, labels, _ = controller.build(_small_cfg(wp3_cfg), {}, pool, man, "/x", seed=1)
    assert all(set(it.keys()) == {"item_id", "h5"} for it in items)
    # labels DO carry truth; manifest must not
    assert any("truth_class" in l for l in labels)


def test_controller_roles_disjoint(wp3_cfg):
    pool, man = _fake_pool_and_manifest()
    _, labels, _ = controller.build(_small_cfg(wp3_cfg), {}, pool, man, "/x", seed=7)
    by_cls = {}
    for l in labels:
        by_cls.setdefault(l["truth_class"], set()).add(l["host_tns"])
    inj, real, adv = by_cls["injection"], by_cls["real_null"], by_cls["adverse"]
    assert not (inj & real) and not (inj & adv) and not (real & adv)


def test_controller_real_null_prioritizes_multicomponent(wp3_cfg):
    pool, man = _fake_pool_and_manifest()
    _, labels, _ = controller.build(_small_cfg(wp3_cfg), {}, pool, man, "/x", seed=3)
    multis = set(man[man.n_subbursts > 1].tns_name)
    real_hosts = {l["host_tns"] for l in labels if l["truth_class"] == "real_null"}
    # with 12 multi available and n_real_null=10, all real-null hosts are multi-component
    assert real_hosts <= multis


# ---- W3.2 evaluator blindness (structural) --------------------------------
def test_evaluate_source_never_references_labels():
    src = open(os.path.join(REPO, "src/echo_frb/search/blind/evaluate.py")).read()
    assert "SEALED" not in src and "hidden_labels" not in src
    assert "truth_class" not in src


# ---- W3.3 unblind guardrails ----------------------------------------------
def _write_commitments(rd, labels_bytes, labels_ts, scores_ts, ana="h", tamper=False):
    os.makedirs(os.path.join(rd, "SEALED"), exist_ok=True)
    lab = os.path.join(rd, "SEALED", "hidden_labels.parquet")
    open(lab, "wb").write(labels_bytes)
    committed = hashlib.sha256(b"OTHER" if tamper else labels_bytes).hexdigest()
    json.dump(dict(labels_sha256=committed, labels_created_utc=labels_ts,
                   analysis_config_sha16=ana, round=1, pool=0, n_items=1),
              open(os.path.join(rd, "hidden_commitment.json"), "w"))
    json.dump(dict(scores_created_utc=scores_ts, analysis_config_sha16=ana),
              open(os.path.join(rd, "scores_commitment.json"), "w"))
    return lab


def test_unblind_detects_tampered_labels(tmp_path):
    lab = _write_commitments(str(tmp_path), b"LABELDATA",
                             "2026-07-23T00:00:00+00:00", "2026-07-23T01:00:00+00:00",
                             tamper=True)
    with pytest.raises(AssertionError, match="TAMPERED"):
        unblind.verify_commitments(str(tmp_path), lab)


def test_unblind_detects_peeking(tmp_path):
    # scores committed BEFORE labels -> peeking guard fails
    lab = _write_commitments(str(tmp_path), b"LABELDATA",
                             "2026-07-23T02:00:00+00:00", "2026-07-23T01:00:00+00:00")
    with pytest.raises(AssertionError, match="PEEKING"):
        unblind.verify_commitments(str(tmp_path), lab)


def test_unblind_passes_valid_order(tmp_path):
    lab = _write_commitments(str(tmp_path), b"LABELDATA",
                             "2026-07-23T00:00:00+00:00", "2026-07-23T01:00:00+00:00")
    hc, sc = unblind.verify_commitments(str(tmp_path), lab)
    assert hc["round"] == 1


# ---- W3.3 gate arithmetic (G1 / G2) ---------------------------------------
def _g1cfg(wp3_cfg):
    return wp3_cfg["gate"]["g1_efficiency"]


def _g2cfg(wp3_cfg):
    return wp3_cfg["gate"]["g2_false_positive"]


def _pred_dev(mu_eff):
    """Synthetic dev prediction: at each μ, a target efficiency, 200 rows/μ, 2 S/N bins."""
    rows = []
    for mu, e in mu_eff.items():
        for i in range(200):
            rows.append(dict(mu=mu, host_snr=10.0 + (i % 2) * 20.0,
                             recovered=int(i < int(e * 200))))
    return pd.DataFrame(rows)


def test_g1_pass_when_observed_matches_prediction(wp3_cfg):
    mu_eff = {0.1: 0.2, 0.3: 0.6, 0.5: 0.85, 0.9: 0.97}
    pred = _pred_dev(mu_eff)
    # observed injections drawn to MATCH the predicted per-μ efficiency
    rows = []
    for mu, e in mu_eff.items():
        for i in range(60):
            rows.append(dict(mu=mu, host_snr=10.0 + (i % 2) * 20.0,
                             is_candidate=bool(i < int(e * 60)), truth_class="injection"))
    inj = pd.DataFrame(rows)
    res, _ = unblind.g1_assess(inj, pred, _g1cfg(wp3_cfg))
    assert res["g1_pass"], res


def test_g1_pass_when_nonmonotonic_but_agrees(wp3_cfg):
    # full end-to-end criterion is non-monotonic in μ (dips at μ=0.9); observed tracks it
    mu_eff = {0.1: 0.05, 0.3: 0.55, 0.5: 0.84, 0.7: 0.80, 0.9: 0.58}
    pred = _pred_dev(mu_eff)
    rows = []
    for mu, e in mu_eff.items():
        for i in range(60):
            rows.append(dict(mu=mu, host_snr=10.0 + (i % 2) * 20.0,
                             is_candidate=bool(i < int(e * 60)), truth_class="injection"))
    inj = pd.DataFrame(rows)
    res, _ = unblind.g1_assess(inj, pred, _g1cfg(wp3_cfg))
    assert res["g1_pass"], res                          # non-monotonic must NOT sink agreement


def test_g1_fails_when_recovery_deficit(wp3_cfg):
    mu_eff = {0.1: 0.2, 0.3: 0.6, 0.5: 0.85, 0.9: 0.97}
    pred = _pred_dev(mu_eff)
    inj = pd.DataFrame([dict(mu=mu, host_snr=10.0 + (i % 2) * 20.0,
                             is_candidate=False, truth_class="injection")
                        for mu in mu_eff for i in range(60)])
    res, _ = unblind.g1_assess(inj, pred, _g1cfg(wp3_cfg))
    assert not res["g1_pass"]


def _joined(fp_by):
    """Build a joined frame with given FP rates per (class,kind)."""
    rows = []
    for (cls, kind, is_multi), (n, k) in fp_by.items():
        for i in range(n):
            rows.append(dict(truth_class=cls, kind=kind, is_multicomponent=is_multi,
                             is_candidate=bool(i < k)))
    return pd.DataFrame(rows)


def test_g2_pass_when_all_fp_zero(wp3_cfg):
    fp = {("real_null", "none", False): (300, 0),
          ("real_null", "none", True): (79, 0),
          ("adverse", "drift", False): (40, 0),
          ("adverse", "differential_scattering", False): (40, 0),
          ("adverse", "scintillation", False): (40, 12)}   # 30% monitored, ok
    res = unblind.g2_assess(_joined(fp), _g2cfg(wp3_cfg))
    assert res["g2_hard_pass"] and not res["scintillation_escalate"]


def test_g2_fails_on_real_null_fp(wp3_cfg):
    fp = {("real_null", "none", False): (300, 30),         # 10% real FP -> hard fail
          ("adverse", "drift", False): (40, 0)}
    res = unblind.g2_assess(_joined(fp), _g2cfg(wp3_cfg))
    assert not res["g2_hard_pass"]


def test_g2_scintillation_monitored_not_hard_fail(wp3_cfg):
    fp = {("real_null", "none", False): (300, 0),
          ("adverse", "scintillation", False): (40, 16)}   # 40% <= 45% monitored bound
    res = unblind.g2_assess(_joined(fp), _g2cfg(wp3_cfg))
    assert res["g2_hard_pass"]                             # scintillation doesn't sink it


def test_g2_scintillation_escalates_above_bound(wp3_cfg):
    fp = {("real_null", "none", False): (300, 0),
          ("adverse", "scintillation", False): (40, 30)}   # 75% > 60% escalate
    res = unblind.g2_assess(_joined(fp), _g2cfg(wp3_cfg))
    assert res["scintillation_escalate"]


# ---- artifact-gated golden (real hidden set on popos) ---------------------
ARTIFACTS = os.environ.get("ECHO_FRB_WP3_ARTIFACTS")


@pytest.mark.skipif(not ARTIFACTS, reason="set ECHO_FRB_WP3_ARTIFACTS to run WP3 golden")
def test_golden_pools_partition_the_test_split(wp3_cfg):
    pools = pd.read_parquet(os.path.join(ARTIFACTS, "blind_round_pools.parquet"))
    k = wp3_cfg["pools"]["k"]
    assert set(pools.pool) == set(range(k))
    assert (pools.groupby("source_id").pool.nunique() <= 1).all()
    assert (pools.split == "test").all()
