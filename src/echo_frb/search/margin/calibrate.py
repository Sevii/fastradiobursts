#!/usr/bin/env python3
"""W3b.5 — conditional calibration of the per-burst max statistic.

Turns the null ensembles (W3b.4) into a p-value for an observed M:

    p_ih = P0(M >= M_i | Z_i, family h)         stratified empirical + GPD tail
    p_i^robust = max_h p_ih                      the most adverse family decides

CONDITIONING. The max distribution depends on more than the proposal count, but
proposal count is its most direct driver (dev bursts carry 1-10 proposals). Cells
are (n_proposals bin x peak_snr bin), with a fallback chain to the parent stratum
and then to the whole family whenever a cell is thinner than `min_stratum_n`.
Without conditioning, proposal-rich high-SNR bursts dominate the extreme tail and
force an unnecessarily severe threshold onto clean bursts.

Z is computed from the SPECTRUM only (`chain.burst_covariates`), so the same
strata apply to identity-scrubbed blind items.

TAIL HONESTY. The empirical estimate has a hard floor of 1/(n+1): a null sample of
n realizations cannot evidence a tail rarer than that. A GPD fitted above a
PRESPECIFIED quantile can extrapolate past the floor, but a fitted curve reaching
1e-4 is not evidence of 1e-4. So the reported p is

    p = max(p_empirical, p_gpd)

which lets the model make the answer more conservative (a heavier fitted tail than
observed) but never more confident than the data supports. Every quoted p carries
the exceedance count behind it, so a purely model-based number is visible as such.

`-inf` M values (Tier-1 proposed nothing) are genuine null realizations and stay in
the denominator: the search really did fail to produce a candidate for them.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from scipy.stats import genpareto
except ImportError:                       # calibration degrades to empirical-only
    genpareto = None

DEFAULT_CONDITIONING = {
    "strata": ["n_proposals", "peak_snr"],
    "n_proposals_bins": [1, 2, 4, 7, 11],
    "peak_snr_bins": [0, 10, 20, 50, np.inf],
    "min_stratum_n": 50,
}
DEFAULT_TAIL = {"model": "gpd", "threshold_quantile": 0.90,
                "min_exceedances": 30, "report_empirical_fraction": True}


def _cfg_blocks(cfg):
    m = (cfg or {}).get("margin", {}) or {}
    cond = dict(DEFAULT_CONDITIONING); cond.update(m.get("conditioning", {}) or {})
    tail = dict(DEFAULT_TAIL); tail.update(m.get("tail", {}) or {})
    return cond, tail


def _bin_index(value, edges):
    """Right-open bin index, clamped to the end bins (no NaN cells for outliers)."""
    e = np.asarray(edges, float)
    if not np.isfinite(value):
        return 0
    return int(np.clip(np.searchsorted(e, value, side="right") - 1, 0, len(e) - 2))


def stratum_key(row, cond):
    """(n_proposals bin, peak_snr bin) — the cell an observation is calibrated in."""
    return (_bin_index(row.get("n_proposals", 0), cond["n_proposals_bins"]),
            _bin_index(row.get("peak_snr", 0.0), cond["peak_snr_bins"]))


def assign_strata(df, cfg=None):
    cond, _ = _cfg_blocks(cfg)
    np_bin = df["n_proposals"].apply(lambda v: _bin_index(v, cond["n_proposals_bins"]))
    snr_bin = df["peak_snr"].apply(lambda v: _bin_index(v, cond["peak_snr_bins"]))
    return pd.DataFrame({"np_bin": np_bin, "snr_bin": snr_bin})


class Cell:
    """One (family, stratum) null sample and its prespecified tail model."""

    __slots__ = ("family", "key", "M", "n", "u", "shape", "scale", "n_exc", "level")

    def __init__(self, family, key, M, tail, level):
        self.family, self.key, self.level = family, key, level
        self.M = np.sort(np.asarray(M, float))[::-1]      # descending
        self.n = int(self.M.size)
        self.u = self.shape = self.scale = np.nan
        self.n_exc = 0
        if self.n and genpareto is not None and tail.get("model") == "gpd":
            u = float(np.quantile(self.M, tail["threshold_quantile"]))
            exc = self.M[self.M > u] - u
            exc = exc[np.isfinite(exc)]
            if np.isfinite(u) and exc.size >= tail["min_exceedances"]:
                try:
                    c, _, s = genpareto.fit(exc, floc=0.0)
                    if np.isfinite(c) and np.isfinite(s) and s > 0:
                        self.u, self.shape, self.scale = u, float(c), float(s)
                        self.n_exc = int(exc.size)
                except Exception:                          # keep empirical-only
                    pass

    def p_empirical(self, m):
        """(1 + #{M_b >= m}) / (n + 1) — the standard conservative estimator."""
        if self.n == 0:
            return 1.0, 0
        k = int(np.count_nonzero(self.M >= m))
        return (1.0 + k) / (self.n + 1.0), k

    def p_gpd(self, m):
        if not np.isfinite(self.u) or m <= self.u:
            return np.nan
        sf = float(genpareto.sf(m - self.u, self.shape, loc=0.0, scale=self.scale))
        return (self.n_exc / self.n) * sf

    def pvalue(self, m):
        p_emp, k = self.p_empirical(m)
        p_g = self.p_gpd(m)
        p = p_emp if not np.isfinite(p_g) else max(p_emp, p_g)
        return dict(p=float(p), p_empirical=float(p_emp),
                    p_gpd=(float(p_g) if np.isfinite(p_g) else np.nan),
                    n_exceed=int(k), n_null=self.n, cell_level=self.level,
                    at_empirical_floor=bool(k == 0))


class Calibration:
    """Fitted null model: family -> stratum -> Cell, with a pooling fallback."""

    def __init__(self, cells, families, cond, tail):
        self.cells, self.families, self.cond, self.tail = cells, families, cond, tail

    @classmethod
    def fit(cls, null_df, cfg=None, families=None):
        cond, tail = _cfg_blocks(cfg)
        df = null_df[null_df.get("truth_class", "null") == "null"].copy()
        if "error" in df:
            df = df[df.error == ""]
        st = assign_strata(df, cfg)
        df["np_bin"], df["snr_bin"] = st.np_bin, st.snr_bin
        families = list(families or sorted(df.family.unique()))

        cells = {}
        for fam in families:
            sub = df[df.family == fam]
            if not len(sub):
                continue
            cells[(fam, "all")] = Cell(fam, "all", sub.M.to_numpy(), tail, "family")
            for nb, g1 in sub.groupby("np_bin"):
                if len(g1) >= cond["min_stratum_n"]:
                    cells[(fam, (nb,))] = Cell(fam, (nb,), g1.M.to_numpy(), tail,
                                               "n_proposals")
                for sb, g2 in g1.groupby("snr_bin"):
                    if len(g2) >= cond["min_stratum_n"]:
                        cells[(fam, (nb, sb))] = Cell(fam, (nb, sb), g2.M.to_numpy(),
                                                      tail, "n_proposals+snr")
        return cls(cells, families, cond, tail)

    def _cell(self, family, key):
        """Most specific populated cell: (np, snr) -> (np,) -> family."""
        for k in (tuple(key), (key[0],), "all"):
            c = self.cells.get((family, k))
            if c is not None:
                return c
        return None

    def pvalues(self, m, Z):
        """Per-family p for one observed M, plus p_robust = max_h p_h."""
        key = stratum_key(Z, self.cond)
        out, worst = {}, None
        for fam in self.families:
            c = self._cell(fam, key)
            if c is None:
                continue
            r = c.pvalue(m)
            out[fam] = r
            if worst is None or r["p"] > out[worst]["p"]:
                worst = fam
        if worst is None:
            return dict(p_robust=1.0, worst_family="none", per_family={})
        return dict(p_robust=float(out[worst]["p"]), worst_family=worst,
                    p_robust_empirical=float(out[worst]["p_empirical"]),
                    p_robust_at_floor=bool(out[worst]["at_empirical_floor"]),
                    p_robust_n_null=int(out[worst]["n_null"]),
                    cell_level=out[worst]["cell_level"], per_family=out)

    def apply(self, df):
        """Vectorless but cheap: p_robust for each row of a scored DataFrame."""
        recs = []
        for r in df.to_dict("records"):
            res = self.pvalues(r["M"], r)
            rec = {k: v for k, v in res.items() if k != "per_family"}
            for fam, pf in res["per_family"].items():
                rec[f"p_{fam}"] = pf["p"]
            recs.append(rec)
        return pd.DataFrame(recs, index=df.index)

    def min_resolvable_alpha(self, factor=4.0):
        """The smallest alpha this calibration can actually evidence.

        `p = max(p_empirical, p_gpd)` never returns less than a cell's empirical
        floor 1/(n+1), so a cell thinner than ~1/alpha makes alpha UNREACHABLE:
        every burst calibrated in it fails the gate no matter how strong. That
        shows up as an efficiency cliff, which is a sample-size artifact and not
        a statement about the data.

        Returns (alpha_min, worst_cell): alpha_min = factor * max floor over the
        cells that can actually be selected. `factor` demands headroom rather
        than bare reachability — at factor=1 a qualifying burst would have to be
        more extreme than EVERY null in its cell.
        """
        worst, floor = None, 0.0
        for (fam, key), c in self.cells.items():
            f = 1.0 / (c.n + 1.0)
            if f > floor:
                worst, floor = (fam, key, c.n), f
        return float(factor * floor), worst

    def summary(self):
        rows = []
        for (fam, key), c in sorted(self.cells.items(), key=lambda kv: str(kv[0])):
            fin = c.M[np.isfinite(c.M)]
            rows.append(dict(
                family=fam, stratum=str(key), level=c.level, n=c.n,
                n_finite=int(fin.size),
                frac_M_gt0=round(float((c.M > 0).mean()), 5) if c.n else np.nan,
                gpd_u=round(c.u, 4) if np.isfinite(c.u) else np.nan,
                gpd_shape=round(c.shape, 4) if np.isfinite(c.shape) else np.nan,
                gpd_scale=round(c.scale, 4) if np.isfinite(c.scale) else np.nan,
                n_exceedances=c.n_exc,
                empirical_floor=round(1.0 / (c.n + 1.0), 6) if c.n else np.nan))
        return pd.DataFrame(rows)


def cluster_bootstrap_rate(df, mask_col, cluster_col="source_id", n_boot=2000,
                           seed=0, alpha=0.05):
    """Source-level cluster bootstrap CI for a rate.

    Repeaters contribute several dependent bursts, so resampling bursts would
    understate the uncertainty; the cluster is the SOURCE throughout the project.
    """
    rng = np.random.default_rng(seed)
    clusters = df[cluster_col].to_numpy()
    flags = df[mask_col].to_numpy(bool)
    uniq = np.unique(clusters)
    by = {c: flags[clusters == c] for c in uniq}
    point = float(flags.mean()) if flags.size else np.nan
    if uniq.size < 2:
        return point, np.nan, np.nan
    stats = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.choice(uniq, size=uniq.size, replace=True)
        v = np.concatenate([by[c] for c in pick])
        stats[b] = v.mean() if v.size else np.nan
    lo, hi = np.nanpercentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return point, float(lo), float(hi)
