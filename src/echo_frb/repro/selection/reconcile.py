#!/usr/bin/env python3
"""W1.4b — reconcile the literal and clean-room selection funnels.

Merges the literal funnel (from funnel_literal.parse_log) with the clean-room
staged scores (terminal_stage column) into:
  * candidate_selection_chain.parquet — one row per FRB (all 340), both tracks.
  * reconciliation_matrix.parquet/.md — the union of FRBs reaching >=SPIKE in
    either track, with the first stage at which the two tracks diverge.

Canonical funnel order: SPIKE -> MATCH -> CUTS -> DRIFT -> CANDIDATE.
Clean-room HARDNESS is treated at the same depth as DRIFT (post-cuts rejection).
"""
from __future__ import annotations

import os
import pandas as pd
import yaml

# how far each terminal stage got through the funnel (higher = further)
RANK = {"EXCLUDED": -1, "NO_SPIKE": 0, "NO_MATCH": 1, "CUTS": 2,
        "DRIFT": 3, "HARDNESS": 3, "CANDIDATE": 4}
# stage name crossed when advancing from rank r to r+1
NEXT_STAGE = {0: "SPIKE", 1: "MATCH", 2: "CUTS", 3: "DRIFT"}


def _cr_stage(row):
    return str(row.get("terminal_stage", "EXCLUDED"))


def divergence_stage(lit_stage, cr_stage):
    rl, rc = RANK.get(lit_stage, 0), RANK.get(cr_stage, 0)
    if lit_stage == cr_stage:
        return None                      # agree
    return NEXT_STAGE.get(min(rl, rc), "SPIKE")


def build(literal_funnel, cleanroom_staged, target_yaml=None):
    lit = pd.read_parquet(literal_funnel)
    cr = pd.read_parquet(cleanroom_staged)
    cr = cr.rename(columns={"terminal_stage": "cleanroom_stage",
                            "is_candidate": "cleanroom_is_candidate",
                            "spike_delays_ms": "cleanroom_spike_ms",
                            "note": "cleanroom_note"})
    keep_cr = ["frb_name", "cleanroom_stage", "cleanroom_is_candidate",
               "cleanroom_spike_ms", "n_spikes", "n_matched",
               "best_secondary_psnr", "ks_d_max", "best_delay_ms",
               "mag_ratio", "cleanroom_note"]
    chain = lit.merge(cr[keep_cr], on="frb_name", how="outer")

    chain["agree"] = chain["literal_stage"] == chain["cleanroom_stage"]
    chain["divergence_stage"] = [
        divergence_stage(l, c)
        for l, c in zip(chain["literal_stage"], chain["cleanroom_stage"])
    ]

    # optional context: authors' committed per-config candidate lists
    if target_yaml and os.path.exists(target_yaml):
        y = yaml.safe_load(open(target_yaml))
        cfgs = y["selection_funnel"]["by_config"]
        for cname in ("G_3", "SG_20", "SG_100"):
            names = set(cfgs[cname]["names"])
            chain[f"in_{cname}"] = chain["frb_name"].isin(names)

    chain = chain.sort_values("frb_name").reset_index(drop=True)

    # reconciliation matrix: FRBs reaching >=SPIKE in either track
    reached = (chain["literal_stage"] != "NO_SPIKE") | \
              (~chain["cleanroom_stage"].isin(["NO_SPIKE", "EXCLUDED"]))
    matrix = chain[reached].copy()
    return chain, matrix


def summarize(chain, matrix):
    lines = []
    lines.append("## W1.4 reconciliation — literal vs blind clean-room\n")
    lines.append(f"- FRBs total: {len(chain)}")
    lines.append(f"- literal candidates: {int(chain.literal_is_candidate.sum())}"
                 f"  | clean-room candidates: {int(chain.cleanroom_is_candidate.sum())}")
    lines.append(f"- reached >=SPIKE in either track: {len(matrix)}")
    lines.append(f"- tracks AGREE on terminal stage: {int(chain.agree.sum())}/{len(chain)}\n")
    lines.append("### Literal funnel (terminal stage counts)")
    lines.append(chain.literal_stage.value_counts().to_string() + "\n")
    lines.append("### Clean-room funnel (terminal stage counts)")
    lines.append(chain.cleanroom_stage.value_counts().to_string() + "\n")
    lines.append("### Divergence stage (where the two tracks first part)")
    lines.append(chain.loc[~chain.agree, "divergence_stage"]
                 .value_counts().to_string() + "\n")
    lines.append("### FRBs flagged candidate in EITHER track")
    cols = ["frb_name", "literal_stage", "cleanroom_stage",
            "literal_is_candidate", "cleanroom_is_candidate", "divergence_stage"]
    either = chain[(chain.literal_is_candidate) | (chain.cleanroom_is_candidate)]
    lines.append(either[cols].to_string(index=False) + "\n")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--literal-funnel", required=True)
    ap.add_argument("--cleanroom-staged", required=True)
    ap.add_argument("--target-yaml", default=None)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    chain, matrix = build(a.literal_funnel, a.cleanroom_staged, a.target_yaml)
    os.makedirs(a.out_dir, exist_ok=True)
    chain.to_parquet(os.path.join(a.out_dir, "candidate_selection_chain.parquet"), index=False)
    matrix.to_parquet(os.path.join(a.out_dir, "reconciliation_matrix.parquet"), index=False)
    md = summarize(chain, matrix)
    open(os.path.join(a.out_dir, "reconciliation_matrix.md"), "w").write(md)
    print(md)
