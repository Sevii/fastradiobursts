#!/usr/bin/env python3
"""Parameterized ACF-baseline smoothing for the W1.5 sweep — NO source toggling.

The authors switch the ACF baseline smoothing between Gaussian and Savitzky-Golay
by *commenting/uncommenting* one line inside `detect_autocorr_spikes`. We refuse
that fragile pattern. Instead this module provides a single, faithful
re-implementation of their `detect_autocorr_spikes` whose smoothing line is chosen
by a **parameter** (module-level `_CFG`, set via `set_smoothing`), and installs it
over `modules.analysis_data.detect_autocorr_spikes` at runtime (`install`).

The Gaussian path is numerically identical to the authors' function (verified by
reproducing their committed G_3). The savgol path reproduces SG_20 / SG_100. One
code path, selected by config — never by editing source.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import savgol_filter

# smoothing selection (set per sweep run)
_CFG = {"method": "gaussian", "window_length": 20, "polyorder": 3}


def set_smoothing(method="gaussian", window_length=20, polyorder=3):
    if method not in ("gaussian", "savgol"):
        raise ValueError("method must be 'gaussian' or 'savgol'")
    _CFG.update(method=method, window_length=int(window_length),
                polyorder=int(polyorder))


def _smooth(y, smooth_sigma):
    """The one line the authors toggle — here selected by _CFG."""
    if _CFG["method"] == "savgol":
        return savgol_filter(y, window_length=_CFG["window_length"],
                             polyorder=_CFG["polyorder"], deriv=0, mode="interp")
    return gaussian_filter1d(y, sigma=smooth_sigma, mode="reflect")


def detect_autocorr_spikes(autocorr, lags, smooth_sigma=3.0, threshold=3.0,
                           min_lag=0, positive_lags_only=True,
                           return_details=False):
    """Faithful re-implementation of the authors' detector; smoothing via _CFG.

    Body mirrors modules.analysis_data.detect_autocorr_spikes line-for-line
    except the single smoothing statement, which is parameterized in _smooth().
    """
    if positive_lags_only:
        idx = np.where(lags > 0)[0]
    else:
        idx = np.arange(len(lags))
    idx = idx[lags[idx] >= min_lag]
    if len(idx) == 0:
        raise ValueError("no lags in range")

    x = lags[idx]
    y = autocorr[idx]

    y_smooth = _smooth(y, smooth_sigma)                # <- the only change

    residuals = y - y_smooth
    sigma = np.sqrt(np.mean(residuals ** 2))

    spike_mask = (residuals > threshold * sigma) & (y > y_smooth)
    candidate_idx = idx[spike_mask]
    if len(candidate_idx) > 0:
        y_full = autocorr
        final_spikes = []
        for i in candidate_idx:
            if (i == 0 or y_full[i] > y_full[i - 1]) and \
               (i == len(y_full) - 1 or y_full[i] > y_full[i + 1]):
                final_spikes.append(i)
        final_spikes = np.array(final_spikes, dtype=int)
    else:
        final_spikes = np.array([], dtype=int)

    result = {
        "spike_lags": lags[final_spikes],
        "spike_values": autocorr[final_spikes],
        "spike_residuals": (residuals[np.where(idx == final_spikes[:, None])[1]]
                            if len(final_spikes) else np.array([])),
        "sigma": sigma,
    }
    if return_details:
        result["autocorr_smoothed"] = y_smooth
        result["residuals"] = residuals
        result["lags_analyzed"] = x
    return result


def install(analysis_data_module):
    """Monkeypatch the authors' detector with the parameterized one.

    compute_autocorr_with_spikes calls detect_autocorr_spikes as a module global,
    so replacing the attribute on modules.analysis_data routes all calls here.
    """
    analysis_data_module.detect_autocorr_spikes = detect_autocorr_spikes
