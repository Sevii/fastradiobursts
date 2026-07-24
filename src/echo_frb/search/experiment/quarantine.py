#!/usr/bin/env python3
"""W2.0 — quarantine v2 (proposal §3.2).

The two named candidates PLUS the published intermediate candidates (the union of
the authors' committed G_3 / SG_20 / SG_100 lists) are excluded from all
threshold/null DESIGN — their scores are computed only after thresholds freeze.
This makes "no candidate tuning leaked in" mechanically true for WP2.
"""
from __future__ import annotations

import yaml


def build_quarantine(cfg, authors_reported_values_path):
    """Return the sorted quarantine-v2 tns set from config + the target ground truth."""
    q = set(cfg["quarantine"]["named"])
    if cfg["quarantine"].get("include_published_intermediates", True):
        y = yaml.safe_load(open(authors_reported_values_path))
        by_cfg = y["selection_funnel"]["by_config"]
        for c in ("G_3", "SG_20", "SG_100"):
            q |= set(by_cfg[c]["names"])
    return sorted(q)
