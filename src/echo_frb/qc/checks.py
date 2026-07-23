"""Task 8 — per-product QC check functions (pure, unit-tested).

Each check returns a bool. `check_product` bundles the per-file checks that the
instructions require on every standardized (Tier B) product.
"""
from __future__ import annotations

import numpy as np

BASELINE_TOL = 1e-3


def check_product(prod, res_freq, manifest_usable_channels=None,
                  tol_baseline=BASELINE_TOL):
    """prod: dict of loaded Tier B arrays + attrs. Returns {check: bool} + values."""
    std = prod["standardized"]
    flag = prod["original_flag"]
    gf = prod["original_good_freq"]
    pm = prod["project_mask"]
    robust = prod["robust"]
    usable = prod["channel_usable"]
    off = prod["offmask"]
    freqs = prod["freqs"]
    times = prod["times"]
    a = prod["attrs"]
    nf, nt = std.shape

    c = {}
    c["coord_freq_dim"] = freqs.shape[0] == nf
    c["coord_time_dim"] = times.shape[0] == nt
    c["freq_monotonic"] = bool(freqs.size > 1 and np.all(np.diff(freqs) > 0))
    c["time_monotonic"] = bool(times.size > 1 and np.all(np.diff(times) > 0))
    c["flag_shape"] = flag.shape == std.shape
    c["good_freq_shape"] = gf.shape[0] == nf
    c["project_mask_shape"] = pm.shape == std.shape

    if pm.shape == std.shape:
        um = std[pm]
        c["unmasked_finite"] = bool(np.isfinite(um).all()) if um.size else True
    else:
        c["unmasked_finite"] = False

    # baseline residuals centered (standardized == data - off-pulse median)
    if off.sum() > 0 and usable.sum() > 0:
        block = std[np.ix_(usable, off)]
        bflag = flag[np.ix_(usable, off)]
        vals = np.where(bflag, block, np.nan)
        with np.errstate(all="ignore"):
            med = np.nanmedian(vals) if np.isfinite(vals).any() else np.nan
        c["baseline_centered"] = bool(np.isfinite(med) and abs(float(med)) < tol_baseline)
    else:
        c["baseline_centered"] = False

    # noise positive & finite over usable channels
    ru = robust[usable]
    c["noise_positive_finite"] = bool(ru.size > 0 and np.isfinite(ru).all()
                                      and (ru > 0).all())

    # off-pulse must not overlap the on-pulse span
    on0 = int(a.get("on_pulse_start", -1))
    on1 = int(a.get("on_pulse_end", -1))
    if 0 <= on0 <= on1 < nt:
        c["offpulse_excludes_burst"] = bool(not off[on0:on1 + 1].any())
    else:
        c["offpulse_excludes_burst"] = False

    # usable bandwidth consistent with channel_usable count
    n_usable = int(usable.sum())
    if manifest_usable_channels is not None:
        c["usable_channels_consistent"] = (n_usable == int(manifest_usable_channels))
    else:
        c["usable_channels_consistent"] = True

    # mask fractions within [0,1]
    pmf = 1.0 - pm.mean()
    omf = 1.0 - flag.mean()
    c["mask_frac_bounds"] = bool(0.0 <= pmf <= 1.0 and 0.0 <= omf <= 1.0)

    values = dict(n_usable_channels=n_usable,
                  project_masked_frac=float(pmf),
                  original_masked_frac=float(omf),
                  usable_bandwidth_mhz=float(n_usable * res_freq))
    return c, values


def overall_pass(checks):
    return all(checks.values())


def failed_checks(checks):
    return [k for k, v in checks.items() if not v]
