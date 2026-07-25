#!/usr/bin/env python3
"""W3b.4 — end-to-end null ensembles for the per-burst max statistic.

The whole point of Approach 1 is that a null realization must go through the
ENTIRE search — window proposal, delay search, copy fitting, achromaticity,
robustness, and selection of the best surviving proposal — because the reported
quantity is `M_i = max_j T_ij`, a maximum over a proposal set the data itself
generated. A null that scores one oracle window is what made WP2's benchmark
optimistic and failed the WP3 round-1 gate.

Every realization here is therefore a whole burst pushed through
`margin.chain.run_margin_chain`. Families:

  real                      a dev burst, untouched — the catalog-representative null
  real_multicomponent       the multi-component stratum of `real` (the hard null, H-I)
  surrogate_<method>        structure-preserving surrogate (envelope kept, copy destroyed)
  adverse_<kind>            one of the 7 imitators injected into a single-component host
  injection                 achromatic copy — NOT a null; the positive class, carried
                            through the same machinery so the operating curve is
                            computed from one consistent dump

`real_multicomponent` is a STRATUM of `real`, not an independent draw: it is the
same realizations filtered by morphology. It is reported as its own family
because `p^robust = max_h p_h` must see it separately — pooling 174 hard nulls
into 2541 mostly-easy ones is exactly the dilution the max-over-families rule
exists to prevent.

Determinism: every realization's RNG is seeded from
sha256(salt:family:tns:draw), so the ensemble is reproducible from the config
alone and no state leaks between workers.
"""
from __future__ import annotations

import hashlib

import numpy as np

from ..adverse import generators as gen
from ..nulls import surrogate as surr
from ..tier1 import profile
from . import chain as mchain

ADVERSE_KINDS = ("drift", "differential_dm", "differential_scattering",
                 "chromatic_echo", "scintillation", "overlapping", "rfi_remnant")
SURROGATE_METHODS = tuple(surr.METHODS)
EDGE_GUARD = 5                     # bins kept clear of either time edge


def realization_rng(salt, family, tns, draw):
    """Deterministic per-realization RNG (no cross-worker state)."""
    h = hashlib.sha256(f"{salt}:{family}:{tns}:{draw}".encode()).hexdigest()
    return np.random.default_rng(int(h[:16], 16))


def peak_center(tb):
    return int(np.argmax(profile.build_profile(tb)["I"]))


def host_is_usable(tb, c, dt):
    """The injected second image must land inside the burst, clear of the edges."""
    nt = tb["standardized"].shape[1]
    return c >= EDGE_GUARD and (c + int(dt)) < (nt - EDGE_GUARD)


def make_realization(tb, family, kind, dt, mu, rng):
    """Return the spectrum for one realization, or None if the host cannot host it.

    `real` passes the burst through untouched; surrogates and injections modify
    only `standardized`, exactly as the frozen WP2 generators do.
    """
    if family == "real":
        return tb
    if family.startswith("surrogate_"):
        return surr.make_surrogate(tb, family[len("surrogate_"):], rng)
    c = peak_center(tb)
    if not host_is_usable(tb, c, dt):
        return None
    return gen.inject(tb, c, int(dt), float(mu), kind, rng)


def run_realization(tb, cfg, family, kind="none", dt=np.nan, mu=np.nan,
                    draw=0, salt="wp3b"):
    """Build one realization and push it through the complete frozen chain."""
    rng = realization_rng(salt, family, tb.get("tns_name", "?"), draw)
    spec = make_realization(tb, family, kind, dt, mu, rng)
    if spec is None:
        return None
    out = mchain.run_margin_chain(spec, cfg)
    out.update(family=family, kind=kind, draw=int(draw),
               dt_bins=(int(dt) if np.isfinite(dt) else -1),
               mu=(float(mu) if np.isfinite(mu) else np.nan),
               truth_class=("positive" if family == "injection" else "null"))
    return out


def plan_realizations(bursts, cfg, n_adverse_hosts, n_adverse_draws,
                      n_injection_hosts, n_injection_draws, n_surrogate_bursts,
                      adverse_kinds=ADVERSE_KINDS,
                      surrogate_methods=SURROGATE_METHODS, rng=None):
    """Enumerate (tns, family, kind, dt, mu, draw) work items.

    `bursts` is a DataFrame with tns_name, source_id and `single` (single-component).
    Injection and adverse hosts are single-component bursts, as in the frozen WP2
    benchmark — injecting a second image into an already-multi-component burst
    would confound the truth label.

    (Δt, μ) are drawn from the FROZEN injection grid for both the adverse and the
    injection families. Round 1 held adverse μ fixed at 0.5; the calibration
    deliberately spans the grid instead, because a null family evaluated at one
    arbitrary magnification under-represents the bright imitators that are exactly
    the dangerous ones. This broadens the null tail and so makes the threshold
    STRICTER — the conservative direction. μ-stratified distributions are reported
    so the sensitivity to this choice stays visible.
    """
    rng = rng or np.random.default_rng(0)
    inj = cfg["injection"]
    dt_grid = np.asarray(inj["dt_bins"], int)
    mu_grid = np.asarray(inj["mu"], float)
    singles = bursts[bursts.single].tns_name.to_list()
    rng.shuffle(singles)

    work = []
    for t in bursts.tns_name:                                   # real: every burst
        work.append((t, "real", "none", -1, np.nan, 0))
    for m in surrogate_methods:
        for t in bursts.tns_name[:n_surrogate_bursts or len(bursts)]:
            work.append((t, f"surrogate_{m}", "none", -1, np.nan, 0))
    for kind in adverse_kinds:
        for t in singles[:n_adverse_hosts]:
            for d in range(n_adverse_draws):
                work.append((t, f"adverse_{kind}", kind,
                             int(rng.choice(dt_grid)), float(rng.choice(mu_grid)), d))
    for t in singles[:n_injection_hosts]:
        for d in range(n_injection_draws):
            work.append((t, "injection", "achromatic_copy",
                         int(rng.choice(dt_grid)), float(rng.choice(mu_grid)), d))
    return work
