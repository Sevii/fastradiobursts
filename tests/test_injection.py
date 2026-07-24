"""W2.6 — injection efficiency unit tests (pure logic)."""
import numpy as np
import pandas as pd

from echo_frb.search.injection import efficiency as eff


def test_wilson_bounds():
    p, lo, hi = eff.wilson(5, 10)
    assert lo < p < hi and 0 <= lo and hi <= 1
    assert eff.wilson(0, 0)[0] != eff.wilson(0, 0)[0]      # NaN for n=0


def test_recovery_flag_requires_all_three():
    df = pd.DataFrame([
        dict(delta_chi2=200, ncc=0.6, reduced_chi2=1.1),   # recovered (>100)
        dict(delta_chi2=10, ncc=0.6, reduced_chi2=1.1),    # too faint
        dict(delta_chi2=200, ncc=0.1, reduced_chi2=1.1),   # not copy-like (ncc)
        dict(delta_chi2=200, ncc=0.6, reduced_chi2=3.0),   # structured residual
    ])
    assert list(eff.recovery_flag(df)) == [True, False, False, False]


def test_efficiency_increases_with_signal():
    # synthetic: delta_chi2 grows with mu -> efficiency should be monotonic up
    rows = []
    for mu, dchi in [(0.1, 20), (0.5, 200), (0.9, 800)]:
        for _ in range(20):
            rows.append(dict(mu=mu, delta_chi2=dchi, ncc=0.6, reduced_chi2=1.1))
    df = pd.DataFrame(rows)
    e = eff.efficiency_by(df, "mu").sort_values("mu")
    assert list(e.efficiency) == sorted(e.efficiency)      # non-decreasing
    assert e.efficiency.iloc[0] < e.efficiency.iloc[-1]
