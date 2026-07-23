#!/usr/bin/env python3
"""Task 7 — eligibility & exclusion engine.

Assigns every observation exactly one status:
  eligible | provisionally_eligible | excluded | processing_failure |
  pending_manual_review
from the master manifest + schema-validation report, against the preregistered
thresholds in eligibility_config.yaml. Every non-eligible row carries a primary
reason code, optional secondaries, a human-readable explanation, reversibility,
the responsible code commit, config hash, and decision date.

Pure decision logic lives in ``classify`` (unit-tested). Nothing is deleted; the
two quarantined candidates are classified but flagged and never influence
thresholds.

Usage:
  engine.py --manifest OBS.parquet --schema SCHEMA.parquet \
            --config eligibility_config.yaml --dict exclusion_reason_dictionary.yaml \
            --out eligibility_table.parquet [--code-commit HASH]
"""
import argparse
import hashlib
import os
from datetime import datetime, timezone

import pandas as pd
import yaml

CANDIDATES = {"FRB20190131D", "FRB20211115A"}

# fixed priority to pick the primary among multiple quality failures
QUALITY_PRIORITY = [
    "E008_INSUFFICIENT_TIME_COVERAGE",
    "E006_INSUFFICIENT_OFF_PULSE",
    "E007_INSUFFICIENT_USABLE_BANDWIDTH",
]


def classify(row, cfg, dct):
    """Pure classifier. Returns dict: status, primary_reason,
    secondary_reasons (list), explanation, reversible (bool|None)."""
    def status_for(code):
        return dct.get(code, {}).get("status", "excluded")

    def reversible_for(code):
        return dct.get(code, {}).get("reversible")

    # 1. ingest / schema hard failures (short-circuit)
    if not row.get("readable", False):
        return dict(status="processing_failure",
                    primary_reason="E001_UNREADABLE_FILE",
                    secondary_reasons=[],
                    explanation="file could not be opened",
                    reversible=reversible_for("E001_UNREADABLE_FILE"))
    if not row.get("schema_ok", True):
        codes = [c for c in str(row.get("schema_error_codes", "")).split(",") if c]
        primary = codes[0] if codes else "E099_OTHER_REQUIRES_REVIEW"
        return dict(status=status_for(primary),
                    primary_reason=primary,
                    secondary_reasons=codes[1:],
                    explanation=f"schema validation failed: {','.join(codes)}",
                    reversible=reversible_for(primary))

    # 2. quality criteria (collect all failures)
    e = cfg["eligibility"]
    failures = []
    bw = row.get("usable_bandwidth_mhz")
    if bw is not None and bw < e["min_usable_bandwidth_mhz"]:
        failures.append(("E007_INSUFFICIENT_USABLE_BANDWIDTH",
                         f"usable bandwidth {bw:.1f} MHz < "
                         f"{e['min_usable_bandwidth_mhz']} MHz"))
    nt = row.get("num_time")
    if nt is not None and nt < e["min_time_coverage_bins"]:
        failures.append(("E008_INSUFFICIENT_TIME_COVERAGE",
                         f"num_time {nt} < {e['min_time_coverage_bins']} bins"))
    # off-pulse only assessable when the on-pulse region is known
    soft = []
    if row.get("has_pulse_region", False):
        op = row.get("total_offpulse_bins")
        if op is not None and op < e["min_offpulse_bins"]:
            failures.append(("E006_INSUFFICIENT_OFF_PULSE",
                             f"off-pulse bins {op} < {e['min_offpulse_bins']}"))
    else:
        soft.append("needs_offpulse_derivation")

    if failures:
        codes = [c for c, _ in failures]
        primary = sorted(codes, key=lambda c: QUALITY_PRIORITY.index(c)
                         if c in QUALITY_PRIORITY else 99)[0]
        expl = "; ".join(m for _, m in failures)
        return dict(status="excluded", primary_reason=primary,
                    secondary_reasons=[c for c in codes if c != primary],
                    explanation=expl, reversible=reversible_for(primary))

    # 3. soft flags -> provisionally_eligible
    if not row.get("has_calibration", True):
        soft.append("no_calibration")
    mp = row.get("orig_masked_pixel_frac")
    if mp is not None and mp > e["soft_masked_pixel_frac"]:
        soft.append("heavily_masked")

    if soft:
        return dict(status="provisionally_eligible", primary_reason=None,
                    secondary_reasons=soft,
                    explanation="passes hard criteria; soft flags: "
                                + ", ".join(soft),
                    reversible=None)
    return dict(status="eligible", primary_reason=None, secondary_reasons=[],
                explanation="meets all eligibility criteria", reversible=None)


def build(manifest_pq, schema_pq, cfg, dct, code_commit, config_hash):
    m = pd.read_parquet(manifest_pq)
    s = pd.read_parquet(schema_pq)[
        ["filename", "ok", "error_codes", "has_pulse_region",
         "has_calibration", "time_downsample_factor"]
    ].rename(columns={"ok": "schema_ok",
                      "error_codes": "schema_error_codes",
                      "has_calibration": "schema_has_calibration"})
    df = m.merge(s, on="filename", how="left")
    # prefer contract's presence flags
    df["has_calibration"] = df["schema_has_calibration"].fillna(
        df["has_calibration"])
    df["has_pulse_region"] = df["has_pulse_region"].fillna(False)

    decision_date = datetime.now(timezone.utc).isoformat()
    out_rows = []
    for _, r in df.iterrows():
        row = r.to_dict()
        d = classify(row, cfg, dct)
        tns = row.get("tns_name")
        out_rows.append({
            "tns_name": tns,
            "filename": row.get("filename"),
            "is_repeater": bool(row.get("is_repeater", False)),
            "is_candidate": tns in CANDIDATES,
            "quarantined": tns in CANDIDATES,
            "status": d["status"],
            "primary_reason": d["primary_reason"],
            "secondary_reasons": ",".join(d["secondary_reasons"]),
            "explanation": d["explanation"],
            "reversible": d["reversible"],
            # audited measured quantities
            "usable_bandwidth_mhz": row.get("usable_bandwidth_mhz"),
            "num_time": row.get("num_time"),
            "has_pulse_region": bool(row.get("has_pulse_region", False)),
            "total_offpulse_bins": row.get("total_offpulse_bins"),
            "has_calibration": bool(row.get("has_calibration", False)),
            "orig_masked_pixel_frac": row.get("orig_masked_pixel_frac"),
            "time_downsample_factor": row.get("time_downsample_factor"),
            # provenance
            "code_commit": code_commit,
            "config_hash": config_hash,
            "config_version": cfg.get("version"),
            "decision_date_utc": decision_date,
        })
    return pd.DataFrame(out_rows).sort_values("filename").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--dict", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--code-commit", default=os.environ.get("ECHO_FRB_COMMIT",
                                                            "unknown"))
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    dct = yaml.safe_load(open(args.dict))
    config_hash = hashlib.sha256(open(args.config, "rb").read()).hexdigest()[:16]

    df = build(args.manifest, args.schema, cfg, dct, args.code_commit, config_hash)
    df.to_parquet(args.out, index=False)

    print(f"[eligibility] wrote {args.out}  ({len(df)} rows)")
    print(f"[eligibility] config_hash={config_hash} code_commit={args.code_commit}")
    print("\n[eligibility] status counts:")
    print(df["status"].value_counts().to_string())
    exc = df[df.primary_reason.notna()]
    if len(exc):
        print("\n[eligibility] primary reason counts:")
        print(exc["primary_reason"].value_counts().to_string())
    print("\n[eligibility] soft-flag counts (provisionally_eligible):")
    prov = df[df.status == "provisionally_eligible"]
    from collections import Counter
    c = Counter()
    for s in prov.secondary_reasons:
        for f in filter(None, str(s).split(",")):
            c[f.strip()] += 1
    print({k: v for k, v in c.items()})
    print("\n[eligibility] candidates (quarantined):")
    print(df[df.is_candidate][["tns_name", "status", "secondary_reasons"]]
          .to_string(index=False))
    # invariant: every row has a status
    assert df["status"].notna().all(), "a row is missing a status!"
    print(f"\n[eligibility] INVARIANT OK: all {len(df)} rows have a status")


if __name__ == "__main__":
    main()
