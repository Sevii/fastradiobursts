"""W2.7 — null-benchmark gate logic tests (pure logic)."""
import numpy as np
import pandas as pd

from echo_frb.search.benchmark import gate


def test_passes_requires_all_three():
    df = pd.DataFrame([
        dict(delta_chi2=200, ncc=0.6, reduced_chi2=1.1),   # pass
        dict(delta_chi2=10, ncc=0.6, reduced_chi2=1.1),    # too faint
        dict(delta_chi2=200, ncc=0.1, reduced_chi2=1.1),   # low ncc
        dict(delta_chi2=200, ncc=0.6, reduced_chi2=2.0),   # structured residual
    ])
    assert list(gate.passes(df, 100)) == [True, False, False, False]


def test_fp_rate_decreases_with_threshold():
    rng = np.random.default_rng(0)
    df = pd.DataFrame(dict(delta_chi2=rng.uniform(0, 1000, 500),
                           ncc=0.6, reduced_chi2=1.0))
    r = [gate.passes(df, d).mean() for d in gate.DELTA_GRID]
    assert all(r[i] >= r[i + 1] for i in range(len(r) - 1))   # monotdecreasing
