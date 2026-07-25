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


# ---- W3b.7-D: the mixture must fit the pool, loudly ------------------------
def test_controller_raises_when_the_pool_is_too_small(wp3_cfg):
    """Round-1 recipe on a pool-1-sized pool: 0 adverse hosts, silently, before."""
    pool, man = _fake_pool_and_manifest(n=40)
    with pytest.raises(ValueError, match="MIXTURE DOES NOT FIT THE POOL"):
        controller.build(wp3_cfg, {}, pool, man, "/x", seed=1)


def test_controller_error_names_the_short_role(wp3_cfg):
    pool, man = _fake_pool_and_manifest(n=40)
    cfg = dict(wp3_cfg)
    cfg["mixture"] = dict(wp3_cfg["mixture"], n_real_null=10, n_injections=10,
                          n_per_adverse_kind=40)          # only adverse is short
    with pytest.raises(ValueError, match="role 'adverse hosts' wants 40"):
        controller.build(cfg, {}, pool, man, "/x", seed=1)


def test_controller_accepts_a_recipe_that_fits(wp3_cfg):
    pool, man = _fake_pool_and_manifest(n=80)
    _, _, counts = controller.build(_small_cfg(wp3_cfg), {}, pool, man, "/x", seed=1)
    assert counts["n_real"] == 10 and counts["n_inj"] == 10


def test_controller_reports_the_hard_null_count_pre_scoring(wp3_cfg):
    """Pool 1 has 17 multi-component bursts; the report must say so up front."""
    pool, man = _fake_pool_and_manifest(n=80)          # 12 multi by construction
    _, _, counts = controller.build(_small_cfg(wp3_cfg), {}, pool, man, "/x", seed=5)
    assert counts["n_multicomponent_drawn"] == 10      # n_real_null=10, all multi


# ---- W3.2 evaluator blindness (structural) --------------------------------
def test_evaluate_source_never_references_labels():
    src = open(os.path.join(REPO, "src/echo_frb/search/blind/evaluate.py")).read()
    assert "SEALED" not in src and "hidden_labels" not in src
    assert "truth_class" not in src


# ---- W3b.7-B: the evaluator runs v2 ---------------------------------------
import h5py                                                        # noqa: E402
import json as _json                                               # noqa: E402

from echo_frb.search.blind import evaluate as ev                   # noqa: E402
from echo_frb.search.margin import calibrate as mcal               # noqa: E402

V2_CFG_PATH = os.path.join(REPO, "config", "wp2_analysis_config_v2.yaml")


@pytest.fixture(scope="module")
def ana_v2():
    return yaml.safe_load(open(V2_CFG_PATH))


@pytest.fixture(scope="module")
def ana_v1():
    return yaml.safe_load(open(os.path.join(REPO, "config",
                                            "wp2_analysis_config.yaml")))


def _write_tier_b(path, nf=512, nt=140, seed=0, inject_copy=False):
    """A Tier-B-shaped h5 the evaluator can actually load and score."""
    from echo_frb.search.adverse import generators as gen
    rng = np.random.default_rng(seed)
    env = np.zeros(nf); env[100:400] = 1.0 + 0.5 * np.cos(np.linspace(0, 3, 300))
    t = np.arange(nt); prof = np.exp(-0.5 * ((t - 45) / 3.0) ** 2)
    std = (env[:, None] * prof[None, :]
           + 0.04 * rng.standard_normal((nf, nt))).astype(np.float32)
    off = np.ones(nt, bool); off[35:80] = False
    tb = dict(standardized=std, project_mask=np.ones((nf, nt), bool),
              robust_std=0.04 * np.ones(nf), channel_usable=np.ones(nf, bool),
              offpulse=off, times=t * 0.983e-3, freqs=400 + np.arange(nf) * 0.39,
              res_time=0.983e-3, tns_name="ITEM00000", noise_failed=False)
    if inject_copy:
        tb = gen.inject(tb, 45, 8, 0.6, "achromatic_copy", np.random.default_rng(seed))
    with h5py.File(path, "w") as f:
        f.create_dataset("standardized", data=np.asarray(tb["standardized"]))
        f.create_dataset("mask/project_mask", data=tb["project_mask"])
        f.create_dataset("noise/robust_std", data=tb["robust_std"])
        f.create_dataset("noise/channel_usable", data=tb["channel_usable"])
        f.create_dataset("offpulse/time_mask", data=tb["offpulse"])
        f.create_dataset("coords/times", data=tb["times"])
        f.create_dataset("coords/freqs", data=tb["freqs"])
        f.attrs["res_time"] = 0.983e-3
        f.attrs["tns_name"] = "ITEM00000"
        f.attrs["noise_failed"] = False


def _fake_calibration(dirpath, alpha=0.05, n=600, loc=-0.5):
    """A committed calibration artifact with the same shape as the real one."""
    rng = np.random.default_rng(0)
    ens = pd.DataFrame(dict(
        family="real", truth_class="null", error="",
        M=rng.normal(loc, 0.5, n), n_proposals=3, peak_snr=20.0,
        source_id=[f"S{i}" for i in range(n)]))
    c = mcal.Calibration.fit(ens, {"margin": {"conditioning": {"min_stratum_n": 200}}})
    man = c.save(dirpath)
    commit = dict(manifest_sha256=mcal.sha256_file(
        os.path.join(str(dirpath), mcal.MANIFEST_FILE)),
        alpha=alpha, n_cells=man["n_cells"],
        n_realizations=man.get("n_realizations", n),
        min_resolvable_alpha=man["min_resolvable_alpha"])
    _json.dump(commit, open(os.path.join(str(dirpath),
                                         "calibration_commitment.json"), "w"))
    return commit


def test_is_v2_keys_off_the_margin_block(ana_v1, ana_v2):
    assert not ev.is_v2(ana_v1)
    assert ev.is_v2(ana_v2)


def test_v2_refuses_without_a_calibration(ana_v2):
    with pytest.raises(AssertionError, match="needs --calibration"):
        ev.assert_calibration_contract(ana_v2, None)


def test_v2_refuses_a_null_alpha(ana_v2, tmp_path):
    cfg = dict(ana_v2, margin=dict(ana_v2["margin"], alpha=None))
    with pytest.raises(AssertionError, match="alpha is null"):
        ev.assert_calibration_contract(cfg, str(tmp_path))


def test_v2_refuses_alpha_mismatching_the_commitment(ana_v2, tmp_path):
    _fake_calibration(tmp_path, alpha=0.02)
    with pytest.raises(AssertionError, match="alpha mismatch"):
        ev.assert_calibration_contract(ana_v2, str(tmp_path))     # config says 0.05


def test_v2_refuses_alpha_below_the_resolvable_floor(ana_v2, tmp_path):
    """A cell thinner than 1/alpha makes alpha unreachable — refuse, don't score."""
    _fake_calibration(tmp_path, alpha=0.0001, n=600)
    cfg = dict(ana_v2, margin=dict(ana_v2["margin"], alpha=0.0001))
    with pytest.raises(AssertionError, match="resolvable floor"):
        ev.assert_calibration_contract(cfg, str(tmp_path))


def test_v2_refuses_a_tampered_calibration(ana_v2, tmp_path):
    _fake_calibration(tmp_path, alpha=0.05)
    v = pd.read_parquet(tmp_path / mcal.VALUES_FILE)
    v.loc[0, "M"] = 42.0
    v.to_parquet(tmp_path / mcal.VALUES_FILE, index=False)
    with pytest.raises(AssertionError, match="CALIBRATION TAMPERED"):
        ev.assert_calibration_contract(ana_v2, str(tmp_path))


def test_v2_scores_items_end_to_end(ana_v2, tmp_path):
    items = tmp_path / "items"; items.mkdir()
    calib = tmp_path / "calib"; calib.mkdir()
    _fake_calibration(calib, alpha=0.05)
    _write_tier_b(items / "a.h5", seed=1, inject_copy=True)
    _write_tier_b(items / "b.h5", seed=2, inject_copy=False)
    man = pd.DataFrame([dict(item_id="ITEM00000", h5="a.h5"),
                        dict(item_id="ITEM00001", h5="b.h5")])

    scores = ev.evaluate(man, str(items), ana_v2, workers=1, calib_dir=str(calib))
    assert len(scores) == 2
    assert (scores.error == "").all()
    for col in ("M", "p_robust", "worst_family", "is_candidate", "n_proposals"):
        assert col in scores, f"v2 scores must carry {col}"
    alpha = ana_v2["margin"]["alpha"]
    expect = (scores.M > 0) & (scores.p_robust <= alpha)
    assert (scores.is_candidate == expect).all()


def test_v1_path_is_untouched_when_there_is_no_margin_block(ana_v1, tmp_path):
    """WP3 round 1 must stay reproducible."""
    items = tmp_path / "items"; items.mkdir()
    _write_tier_b(items / "a.h5", seed=1, inject_copy=True)
    man = pd.DataFrame([dict(item_id="ITEM00000", h5="a.h5")])
    scores = ev.evaluate(man, str(items), ana_v1, workers=1, calib_dir=None)
    assert "is_candidate" in scores and "p_robust" not in scores
    assert "copy_ok_any" in scores                     # the v1 record shape


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


def test_g1_coverage_is_a_two_sample_ci_overlap(wp3_cfg):
    """W3b.7-E regression: round 1's OWN numbers must now pass.

    Observed 0.457 vs predicted 0.474 with a large predicted sample and a small
    observed one. The old asymmetric test (obs point estimate inside the predicted
    CI) scored 0.21 coverage on exactly this configuration and mis-fired the gate;
    an overlap test sees the agreement it actually is.
    """
    mu_eff = {0.1: 0.474, 0.3: 0.474, 0.5: 0.474, 0.9: 0.474}
    pred = _pred_dev(mu_eff)                              # 200 rows/μ -> tight CI
    rows = []
    for mu in mu_eff:                                     # 60 rows/μ -> wide CI
        for i in range(60):
            rows.append(dict(mu=mu, host_snr=10.0 + (i % 2) * 20.0,
                             is_candidate=bool(i < int(0.457 * 60)),
                             truth_class="injection"))
    res, cells = unblind.g1_assess(pd.DataFrame(rows), pred, _g1cfg(wp3_cfg))
    assert res["cell_coverage"] == 1.0, cells
    assert res["coverage_ok"] and res["g1_pass"], res


def test_g1_marginal_compares_the_same_injections_on_both_sides(wp3_cfg):
    """W3b.7-G regression: a SMALL observed sample must not skew the marginal.

    With few injections per cell, most cells fall below `min_cell_n`. Restricting
    the predicted marginal to the survivors while taking the observed marginal
    over everything compared different injections on each side — the rehearsal
    read pred 0.013 vs obs 0.217 on a set that agreed. min_cell_n gates coverage
    only; the marginal spans every cell that has a prediction.
    """
    mu_eff = {0.1: 0.05, 0.3: 0.55, 0.5: 0.84, 0.9: 0.58}
    pred = _pred_dev(mu_eff)
    rows = []                                   # 4 per μ: below min_cell_n=5
    for mu, e in mu_eff.items():
        for i in range(4):
            rows.append(dict(mu=mu, host_snr=10.0 + (i % 2) * 20.0,
                             is_candidate=bool(i < round(e * 4)),
                             truth_class="injection"))
    obs = pd.DataFrame(rows)
    res, _ = unblind.g1_assess(obs, pred, _g1cfg(wp3_cfg))
    assert res["n_marginal"] == len(obs), "every injection must enter the marginal"
    assert res["n_injections_without_prediction"] == 0
    assert abs(res["eff_obs_marginal"] - res["eff_pred_marginal"]) < 0.15, res


def test_g1_coverage_still_fails_a_genuinely_displaced_cell(wp3_cfg):
    """Overlap must not be so permissive that real disagreement slips through."""
    pred = _pred_dev({0.1: 0.9, 0.3: 0.9, 0.5: 0.9, 0.9: 0.9})
    rows = [dict(mu=mu, host_snr=10.0 + (i % 2) * 20.0,
                 is_candidate=bool(i < 6), truth_class="injection")   # 0.10 vs 0.90
            for mu in (0.1, 0.3, 0.5, 0.9) for i in range(60)]
    res, _ = unblind.g1_assess(pd.DataFrame(rows), pred, _g1cfg(wp3_cfg))
    assert res["cell_coverage"] == 0.0
    assert not res["g1_pass"]


def test_g1_coverage_is_symmetric_in_sample_size(wp3_cfg):
    """A thin cell yields a wide interval and abstains — it must not fail by noise."""
    pred = _pred_dev({0.1: 0.5, 0.3: 0.5, 0.5: 0.5, 0.9: 0.5})
    rows = [dict(mu=mu, host_snr=10.0 + (i % 2) * 20.0,
                 is_candidate=bool(i < 3), truth_class="injection")   # 6 rows, 0.5
            for mu in (0.1, 0.3, 0.5, 0.9) for i in range(6)]
    res, _ = unblind.g1_assess(pd.DataFrame(rows), pred, _g1cfg(wp3_cfg))
    assert res["cell_coverage"] in (1.0, None) or res["cell_coverage"] >= 0.9


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
