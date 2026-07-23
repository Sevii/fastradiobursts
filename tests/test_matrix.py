"""W1.6 reproducibility-matrix unit tests (row-builder logic)."""
import pytest

from echo_frb.repro.matrix.build import _row, STATUSES


def test_row_enforces_status_vocabulary():
    with pytest.raises(AssertionError):
        _row("x", 1, "BOGUS", 1, "EXACT", 1)


def test_non_exact_row_requires_cause():
    # a NOT status without a cause must raise
    with pytest.raises(AssertionError):
        _row("x", 1, "EXACT", 1, "NOT", 0, cause="")
    # with a cause it is fine
    r = _row("x", 1, "EXACT", 1, "NOT", 0, cause="because")
    assert r["cleanroom_status"] == "NOT" and r["cause"] == "because"


def test_exact_and_na_rows_need_no_cause():
    r = _row("x", 1, "EXACT", 1, "N-A", "scope")
    assert r["literal_status"] == "EXACT" and r["cause"] == ""


def test_status_set():
    assert STATUSES == {"EXACT", "APPROX", "NOT", "N-A", "SUBJECTIVE"}
