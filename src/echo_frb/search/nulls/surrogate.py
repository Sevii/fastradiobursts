#!/usr/bin/env python3
"""W2.3 — structure-preserving surrogates (proposal §5.6, control 3).

Each transform retains the per-channel spectral envelope and correlated
background while DESTROYING any true delayed-copy relation, so χ²_copy scores of
proposals found in surrogate data estimate the false-positive rate from realistic
structure that is not a lens. All transforms are seeded (deterministic per burst).
"""
from __future__ import annotations

import numpy as np


def block_bootstrap(std, rng, block=8):
    """Rebuild the time axis from resampled contiguous blocks (breaks delays)."""
    nt = std.shape[1]
    n_blocks = int(np.ceil(nt / block))
    starts = rng.integers(0, max(1, nt - block + 1), size=n_blocks)
    cols = np.concatenate([np.arange(s, s + block) for s in starts])[:nt]
    return std[:, cols]


def phase_randomization(std, rng):
    """Per-channel FFT phase randomization: preserves each channel's power
    spectrum (envelope) but scrambles temporal phase alignment."""
    F = np.fft.rfft(std, axis=1)
    ph = rng.uniform(-np.pi, np.pi, size=F.shape)
    ph[:, 0] = 0.0                                   # keep DC
    if std.shape[1] % 2 == 0:
        ph[:, -1] = 0.0                              # keep Nyquist real
    out = np.fft.irfft(np.abs(F) * np.exp(1j * ph), n=std.shape[1], axis=1)
    return out.astype(std.dtype)


def tf_permutation(std, rng, block=4):
    """Permute contiguous time blocks (destroys the copy relation, keeps local
    time-frequency texture)."""
    nt = std.shape[1]
    n_blocks = nt // block
    idx = np.arange(n_blocks); rng.shuffle(idx)
    perm = np.concatenate([np.arange(i * block, (i + 1) * block) for i in idx]
                          + [np.arange(n_blocks * block, nt)])
    return std[:, perm]


METHODS = {"block_bootstrap": block_bootstrap,
           "phase_randomization": phase_randomization,
           "tf_permutation": tf_permutation}


def make_surrogate(tb, method, rng):
    """Return a shallow copy of tb with a surrogate `standardized`."""
    sur = dict(tb)
    sur["standardized"] = METHODS[method](np.asarray(tb["standardized"], float), rng)
    return sur
