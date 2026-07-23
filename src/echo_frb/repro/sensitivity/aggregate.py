#!/usr/bin/env python3
"""W1.5 — aggregate sweep runs into the sensitivity matrix + candidate stability.

Combines the literal and clean-room sweep long-tables into:
  * sensitivity_matrix.parquet — rows = FRBs ever flagged candidate in any run;
    columns = run configs; cell = is_candidate (bool).
  * candidate_stability.parquet — per-FRB survival fraction across LITERAL runs.
Also verifies the SG_20 / SG_100 runs against the authors' committed lists.
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
import yaml

NAMED = ["FRB20190131D", "FRB20211115A"]


def build(literal_long, cleanroom_long, target_yaml):
    lit = pd.read_parquet(literal_long)
    lit_configs = list(dict.fromkeys(lit.config))          # preserve order
    frames = [lit]
    if cleanroom_long and os.path.exists(cleanroom_long):
        frames.append(pd.read_parquet(cleanroom_long))
    allrows = pd.concat(frames, ignore_index=True)

    ever = sorted(allrows.loc[allrows.is_candidate, "frb_name"].unique())
    mat = (allrows[allrows.frb_name.isin(ever)]
           .pivot_table(index="frb_name", columns="config", values="is_candidate",
                        aggfunc="first"))
    # order columns: literal configs first (baseline first), then clean-room
    cr_configs = [c for c in mat.columns if c.startswith("cr_")]
    ordered = [c for c in lit_configs if c in mat.columns] + sorted(cr_configs)
    mat = mat[ordered].fillna(False)

    # per-FRB stability across LITERAL runs only
    stab = []
    for frb in ever:
        sub = lit[lit.frb_name == frb]
        n = sub.config.nunique()
        present = int(sub.is_candidate.sum())
        stab.append(dict(frb_name=frb, n_literal_runs=n, n_present=present,
                         survival_fraction=round(present / n, 3) if n else 0.0,
                         robust=(present == n)))
    stability = pd.DataFrame(stab).sort_values(
        ["survival_fraction", "frb_name"], ascending=[False, True])

    # verify SG configs vs authors' committed lists
    verify = {}
    if target_yaml and os.path.exists(target_yaml):
        y = yaml.safe_load(open(target_yaml))
        cmt = y["selection_funnel"]["by_config"]
        name_map = {"G_3": "G_3", "SG_20": "SG_20", "SG_100": "SG_100"}
        for run_cfg, ykey in name_map.items():
            if run_cfg in lit_configs:
                ours = set(lit[(lit.config == run_cfg) & lit.is_candidate].frb_name)
                theirs = set(cmt[ykey]["names"])
                verify[run_cfg] = dict(ours=len(ours), theirs=len(theirs),
                                       match=(ours == theirs),
                                       only_ours=sorted(ours - theirs),
                                       only_theirs=sorted(theirs - ours))
    return mat.reset_index(), stability, verify


def summarize(mat, stability, verify):
    L = ["## W1.5 sensitivity — candidate survival across configs\n"]
    L.append(f"- configs run: {mat.shape[1] - 1}  | FRBs ever flagged: {len(mat)}\n")
    L.append("### Exact-reproduction check vs authors' committed configs")
    for k, v in verify.items():
        L.append(f"- {k}: ours={v['ours']} theirs={v['theirs']} "
                 f"MATCH={v['match']}"
                 + ("" if v["match"]
                    else f"  only_ours={v['only_ours']} only_theirs={v['only_theirs']}"))
    L.append("\n### Per-candidate stability (across literal runs)")
    L.append(stability.to_string(index=False))
    L.append("\n### Named candidates row")
    named = mat[mat.frb_name.isin(NAMED)]
    L.append(named.to_string(index=False))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--literal-long", required=True)
    ap.add_argument("--cleanroom-long", default=None)
    ap.add_argument("--target-yaml", default=None)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    mat, stability, verify = build(a.literal_long, a.cleanroom_long, a.target_yaml)
    os.makedirs(a.out_dir, exist_ok=True)
    mat.to_parquet(os.path.join(a.out_dir, "sensitivity_matrix.parquet"), index=False)
    stability.to_parquet(os.path.join(a.out_dir, "candidate_stability.parquet"), index=False)
    md = summarize(mat, stability, verify)
    open(os.path.join(a.out_dir, "sensitivity_summary.md"), "w").write(md)
    print(md)


if __name__ == "__main__":
    main()
