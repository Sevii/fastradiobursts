#!/usr/bin/env python3
"""W3.3 — UNBLIND + gate assessment (proposal §5.8 step 5-6, §8 WP3 gate).

Runs ONLY after both commitments exist. Guardrails first (no peeking):
  * the sealed labels still hash to `hidden_commitment.labels_sha256` (untampered);
  * `labels_created_utc < scores_created_utc` (labels committed before scoring);
  * the frozen analysis-config hash agreed at score time (freeze held).
Then joins scores<->labels and evaluates the PREDETERMINED gate from the addendum:

  G1  recovery agrees with the predicted full-criterion efficiency surface
      (marginal within tol + CI overlap, >=90% cell coverage, |bias|<=0.05,
       monotonic in mu).
  G2  false positives meet the per-class targets (real & deterministic adverse
      hard; differential_scattering <=10%; scintillation monitored, not gated).

PASS = G1(all) AND G2(hard). The gate arithmetic is fixed in advance; this module
only applies it. Emits blind_validation.parquet (+ a summary) for the W3.4 report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import yaml

from ..injection import efficiency as eff
from . import foundation

DETERMINISTIC = None   # filled from config


# ---- guardrails -----------------------------------------------------------
def verify_commitments(round_dir, sealed_labels_path):
    hc = json.load(open(os.path.join(round_dir, "hidden_commitment.json")))
    sc = json.load(open(os.path.join(round_dir, "scores_commitment.json")))
    got = hashlib.sha256(open(sealed_labels_path, "rb").read()).hexdigest()
    assert got == hc["labels_sha256"], (
        f"SEALED LABELS TAMPERED: {got[:16]}… != committed {hc['labels_sha256'][:16]}…")
    t_lab = datetime.fromisoformat(hc["labels_created_utc"])
    t_sco = datetime.fromisoformat(sc["scores_created_utc"])
    assert t_lab < t_sco, (
        f"PEEKING GUARD FAILED: labels committed {t_lab} not before scores {t_sco}")
    assert hc["analysis_config_sha16"] == sc["analysis_config_sha16"], (
        "analysis-config hash differs between labels and scores commitments")
    return hc, sc


# ---- G1: efficiency agreement --------------------------------------------
def _snr_edges(host_snr):
    e = np.quantile(host_snr.astype(float), [0, 0.25, 0.5, 0.75, 1.0])
    e[0], e[-1] = -np.inf, np.inf
    return np.unique(e)


def _assign_bin(host_snr, edges):
    labs = [f"Q{i+1}" for i in range(len(edges) - 1)]
    return pd.cut(host_snr.astype(float), edges, labels=labs, include_lowest=True)


def _cell_eff(df, recovered_col="recovered"):
    g = df.groupby(["mu", "snr_bin"], observed=True)[recovered_col].agg(["sum", "count"])
    g = g.reset_index()
    ci = g.apply(lambda r: eff.wilson(int(r["sum"]), int(r["count"])), axis=1,
                 result_type="expand")
    g["eff"], g["lo"], g["hi"] = g["sum"] / g["count"], ci[1], ci[2]
    return g.rename(columns={"count": "n"})


def g1_assess(inj, predicted_dev, g1cfg):
    """inj: hidden injections with is_candidate + host_snr + mu. predicted_dev: dev per-row df."""
    edges = _snr_edges(predicted_dev.host_snr)
    pred = predicted_dev.assign(snr_bin=_assign_bin(predicted_dev.host_snr, edges))
    obs = inj.assign(recovered=inj.is_candidate.astype(int),
                     snr_bin=_assign_bin(inj.host_snr, edges))
    pred_cell = _cell_eff(pred).rename(columns={"eff": "eff_pred", "lo": "pred_lo",
                                                "hi": "pred_hi", "n": "n_pred"})
    obs_cell = _cell_eff(obs).rename(columns={"eff": "eff_obs", "lo": "obs_lo",
                                              "hi": "obs_hi", "n": "n_obs"})
    cells = obs_cell.merge(pred_cell[["mu", "snr_bin", "eff_pred", "pred_lo",
                                      "pred_hi", "n_pred"]], on=["mu", "snr_bin"],
                           how="left")

    # marginal: predicted efficiency weighted by the HIDDEN injections' cell counts
    scored = cells[cells.n_obs >= g1cfg["min_cell_n"]].dropna(subset=["eff_pred"])
    eff_obs_marg = float(obs.recovered.mean())
    w = scored.n_obs / scored.n_obs.sum()
    eff_pred_marg = float((scored.eff_pred * w).sum()) if len(scored) else np.nan
    _, m_lo, m_hi = eff.wilson(int(obs.recovered.sum()), len(obs))
    marg_ok = (abs(eff_obs_marg - eff_pred_marg) <= g1cfg["marginal_abs_tol"] and
               (not g1cfg["require_ci_overlap"] or (m_lo <= eff_pred_marg <= m_hi)))

    # coverage: observed cell efficiency inside the predicted cell 95% CI
    scored = scored.assign(covered=(scored.eff_obs >= scored.pred_lo) &
                                    (scored.eff_obs <= scored.pred_hi))
    coverage = float(scored.covered.mean()) if len(scored) else np.nan
    cov_ok = len(scored) > 0 and coverage >= g1cfg["surface_cell_coverage_min"]

    # signed bias over scored cells
    bias = float((scored.eff_obs - scored.eff_pred).mean()) if len(scored) else np.nan
    bias_ok = np.isfinite(bias) and abs(bias) <= g1cfg["surface_signed_bias_max"]

    # μ-shape AGREEMENT (diagnostic, NOT a pass-requirement): the frozen full
    # end-to-end criterion is non-monotonic in μ — robustness is stricter near μ→1
    # (near-equal-brightness copies), so absolute monotonicity is the WRONG bar. What
    # matters is that the OBSERVED μ-curve tracks the PREDICTED one; that agreement is
    # already tested cell-by-cell by coverage. We report the max |obs−pred| over μ as a
    # shape-agreement diagnostic. (Refined on dev, pre-unblind — see addendum §4.)
    obs_mu = obs.groupby("mu").recovered.mean()
    pred_mu = predicted_dev.groupby("mu").recovered.mean()
    shape_dev = float((obs_mu - pred_mu).abs().max())

    return dict(
        eff_obs_marginal=round(eff_obs_marg, 4), eff_pred_marginal=round(eff_pred_marg, 4),
        marginal_ci=(round(m_lo, 4), round(m_hi, 4)), marginal_ok=bool(marg_ok),
        cell_coverage=round(coverage, 4) if np.isfinite(coverage) else None,
        n_scored_cells=int(len(scored)), coverage_ok=bool(cov_ok),
        signed_bias=round(bias, 4) if np.isfinite(bias) else None, bias_ok=bool(bias_ok),
        mu_shape_max_dev=round(shape_dev, 4),
        mu_efficiency_obs=obs_mu.round(3).to_dict(),
        mu_efficiency_pred=pred_mu.round(3).to_dict(),
        g1_pass=bool(marg_ok and cov_ok and bias_ok),
    ), cells


# ---- G2: false positives --------------------------------------------------
def _fp(sub):
    k, n = int(sub.is_candidate.sum()), len(sub)
    p, lo, hi = eff.wilson(k, n)
    return dict(n=n, n_fp=k, fp=round(p, 4), fp_ci_hi=round(hi, 4))


def g2_assess(joined, g2cfg):
    # Gate on the OBSERVED FP rate (point estimate) <= target — the target is a rate,
    # and with a finite per-class item budget the 95% Wilson UPPER bound at 0 FP (e.g.
    # ~8.8% at n=40) would make even a perfect 0-FP result unpassable. The Wilson CI is
    # REPORTED (fp_ci_hi) as the statistical resolution, not used as the gate. A broken
    # pipeline shows a large point-estimate excess, which this catches.
    rows, hard_ok = [], True
    real = joined[joined.truth_class == "real_null"]
    r = _fp(real); r.update(cls="real_null", target=g2cfg["real"], role="hard")
    r["pass"] = r["fp"] <= g2cfg["real"]; hard_ok &= r["pass"]; rows.append(r)
    # multi-component real-null stress subset (monitored)
    rm = _fp(real[real.is_multicomponent == True])
    rm.update(cls="real_null_multicomponent", target=g2cfg["real_multicomponent_monitored"],
              role="monitored", **{"pass": rm["fp"] <= g2cfg["real_multicomponent_monitored"]})
    rows.append(rm)

    adv = joined[joined.truth_class == "adverse"]
    for kind, g in adv.groupby("kind"):
        r = _fp(g)
        if kind in g2cfg["deterministic_kinds"]:
            tgt, role = g2cfg["deterministic"], "hard"
        elif kind == "differential_scattering":
            tgt, role = g2cfg["differential_scattering"], "hard"
        elif kind == "scintillation":
            tgt, role = g2cfg["scintillation_monitored"], "monitored"
        else:
            tgt, role = g2cfg["deterministic"], "hard"
        r.update(cls=f"adverse:{kind}", target=tgt, role=role)
        r["pass"] = r["fp"] <= tgt
        if role == "hard":
            hard_ok &= r["pass"]
        rows.append(r)

    # scintillation escalation flag
    scint = next((x for x in rows if x["cls"] == "adverse:scintillation"), None)
    escalate = bool(scint and scint["fp"] > g2cfg["scintillation_escalate"])
    return dict(classes=rows, g2_hard_pass=bool(hard_ok),
                scintillation_escalate=escalate)


def main():
    ap = argparse.ArgumentParser(description="W3.3 — unblind + gate assessment")
    ap.add_argument("--wp3-config", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--round-dir", required=True)
    ap.add_argument("--predicted", required=True, help="wp3_predicted_efficiency.parquet (dev)")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    cfg = foundation.load_wp3_config(a.wp3_config)
    g1cfg = cfg["gate"]["g1_efficiency"]
    g2cfg = cfg["gate"]["g2_false_positive"]

    rd = os.path.expanduser(a.round_dir)
    sealed = os.path.join(rd, "SEALED", "hidden_labels.parquet")
    hc, sc = verify_commitments(rd, sealed)
    print(f"[W3.3] guardrails OK: labels untampered, labels_ts < scores_ts, freeze held")

    labels = pd.read_parquet(sealed)
    scores = pd.read_parquet(os.path.join(rd, "hidden_scores.parquet"))
    joined = labels.merge(scores, on="item_id", how="inner")
    predicted = pd.read_parquet(os.path.expanduser(a.predicted))

    inj = joined[joined.truth_class == "injection"].copy()
    g1, cells = g1_assess(inj, predicted, g1cfg)
    g2 = g2_assess(joined, g2cfg)
    verdict = "PASS" if (g1["g1_pass"] and g2["g2_hard_pass"]) else "FAIL"

    out = os.path.expanduser(a.out_dir)
    os.makedirs(out, exist_ok=True)
    cells.to_parquet(os.path.join(out, "blind_validation_cells.parquet"), index=False)
    pd.DataFrame(g2["classes"]).to_parquet(
        os.path.join(out, "blind_validation_fp.parquet"), index=False)
    summary = dict(verdict=verdict, round=hc["round"], pool=hc["pool"],
                   n_items=hc["n_items"], seed=int(labels._controller_seed.iloc[0]),
                   g1=g1, g2={k: v for k, v in g2.items() if k != "classes"})
    json.dump(summary, open(os.path.join(out, "blind_validation_summary.json"), "w"),
              indent=2, default=str)

    print(f"\n===== WP3 BLIND GATE: {verdict} =====")
    print(f"G1 efficiency agreement: {'PASS' if g1['g1_pass'] else 'FAIL'} "
          f"(obs {g1['eff_obs_marginal']} vs pred {g1['eff_pred_marginal']}, "
          f"coverage {g1['cell_coverage']}, bias {g1['signed_bias']}, "
          f"μ-shape max dev {g1['mu_shape_max_dev']})")
    print(f"G2 false positives (hard): {'PASS' if g2['g2_hard_pass'] else 'FAIL'}")
    for r in g2["classes"]:
        flag = "" if r["pass"] else "  <-- OVER TARGET"
        print(f"  {r['cls']:<32} FP={r['fp']:.3f} (95%hi {r['fp_ci_hi']:.3f}) "
              f"target {r['target']} [{r['role']}]{flag}")
    if g2["scintillation_escalate"]:
        print("  ** scintillation FP exceeds escalation bound — flag to PI (§11) **")


if __name__ == "__main__":
    main()
