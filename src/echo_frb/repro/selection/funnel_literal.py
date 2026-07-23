#!/usr/bin/env python3
"""W1.4a — reconstruct the LITERAL track's per-stage selection funnel.

The authors' SearchLensedFRB.py prints a per-FRB trace to stdout (captured in
`literal_G3_run.log`). Each FRB block starts with `[i/340] 处理 <FRB>` and ends
with a terminal disposition line. We parse each block into a single canonical
terminal stage, so the literal funnel can be reconciled against the clean-room
funnel (which carries an equivalent `terminal_stage`).

Canonical stages: NO_SPIKE, NO_MATCH, CUTS, DRIFT, CANDIDATE.
Fine literal reasons: NO_SPIKE, NO_MATCH, CUT_MAXSNR, CUT_ORDER, CUT_PSNR,
DRIFT, CANDIDATE (CUT_* all coarsen to CUTS).
"""
from __future__ import annotations

import re
import pandas as pd

BLOCK_RE = re.compile(r"\[(\d+)/\d+\]\s+处理\s+(FRB\S+)")
SPIKE_RE = re.compile(r"检测到自相关尖峰.*?:\s*\[([^\]]*)\]")
# spike values are printed as np.float64(<num>) — match the number INSIDE the
# parens (a bare \d+ regex would also grab the "64" in "float64").
PAREN_NUM_RE = re.compile(r"\(\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)\s*\)")
BARE_NUM_RE = re.compile(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?")

# fine reason -> coarse stage
COARSE = {
    "NO_SPIKE": "NO_SPIKE", "NO_MATCH": "NO_MATCH",
    "CUT_MAXSNR": "CUTS", "CUT_ORDER": "CUTS", "CUT_PSNR": "CUTS",
    "DRIFT": "DRIFT", "CANDIDATE": "CANDIDATE",
}


def _classify(block_text: str) -> str:
    """Terminal fine reason for one FRB block (priority order matches the code)."""
    t = block_text
    if "分析完成" in t:                      # saved report -> passed everything
        return "CANDIDATE"
    if "严重频率漂移" in t:                    # passed cuts, rejected by K-S drift
        return "DRIFT"
    if "无自相关尖峰" in t:                    # no ACF spike at all
        return "NO_SPIKE"
    if "没有包含最高SNR" in t:                 # matched pair excludes global-max peak
        return "CUT_MAXSNR"
    if "SNR 顺序错误" in t:                    # leading < trailing S/N
        return "CUT_ORDER"
    if re.search(r"后峰 SNR=.*?<\s*10", t):    # secondary PSNR < 10
        return "CUT_PSNR"
    if "未匹配" in t:                          # spike(s) but no component pair matched
        return "NO_MATCH"
    return "UNKNOWN"


def _spikes_ms(block_text: str):
    m = SPIKE_RE.search(block_text)
    if not m:
        return []
    inner = m.group(1)
    nums = PAREN_NUM_RE.findall(inner)        # np.float64(8.82) form
    if not nums:
        nums = BARE_NUM_RE.findall(inner)     # fallback: bare numbers
    return [float(x) for x in nums]


def parse_log(log_path: str) -> pd.DataFrame:
    with open(log_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    starts = [(m.start(), int(m.group(1)), m.group(2))
              for m in BLOCK_RE.finditer(text)]
    rows = []
    for idx, (pos, i, frb) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(text)
        block = text[pos:end]
        reason = _classify(block)
        rows.append(dict(
            order=i, frb_name=frb,
            literal_reason=reason,
            literal_stage=COARSE.get(reason, "UNKNOWN"),
            literal_is_candidate=(reason == "CANDIDATE"),
            literal_spike_ms=_spikes_ms(block),
        ))
    df = pd.DataFrame(rows).drop_duplicates("frb_name", keep="first")
    return df.reset_index(drop=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = parse_log(a.log)
    d.to_parquet(a.out, index=False)
    print(f"[funnel_literal] {len(d)} FRBs -> {a.out}")
    print(d.literal_stage.value_counts().to_string())
    print("candidates:", sorted(d.loc[d.literal_is_candidate, "frb_name"]))
