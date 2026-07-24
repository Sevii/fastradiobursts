"""W2.0 foundation unit tests (source split, quarantine) — pure logic."""
import pandas as pd

from echo_frb.search.experiment import splits, quarantine

CFG = {"split": {"fractions": {"development": 0.6, "validation": 0.2, "test": 0.2},
                 "salt": "test-salt"},
       "quarantine": {"named": ["FRBA", "FRBB"], "include_published_intermediates": False}}


def _manifest():
    return pd.DataFrame([
        # a repeater source with 3 bursts (must stay together)
        dict(tns_name="R1a", repeater_name="SRC_R1", is_repeater=True),
        dict(tns_name="R1b", repeater_name="SRC_R1", is_repeater=True),
        dict(tns_name="R1c", repeater_name="SRC_R1", is_repeater=True),
        # non-repeaters (each its own source)
        dict(tns_name="N1", repeater_name="", is_repeater=False),
        dict(tns_name="N2", repeater_name="", is_repeater=False),
        dict(tns_name="N3", repeater_name="", is_repeater=False),
    ])


def test_source_id():
    assert splits.source_id("R1a", "SRC_R1", True) == "SRC_R1"
    assert splits.source_id("N1", "", False) == "N1"
    assert splits.source_id("N1", "nan", False) == "N1"


def test_repeater_source_never_splits():
    m = _manifest()
    sp = splits.build(m, set(m.tns_name), CFG)
    r = sp[sp.source_id == "SRC_R1"]
    assert r.split.nunique() == 1                       # all 3 bursts same split
    # invariant across every source
    assert (sp.groupby("source_id").split.nunique() <= 1).all()


def test_split_is_deterministic():
    m = _manifest()
    a = splits.build(m, set(m.tns_name), CFG)
    b = splits.build(m.iloc[::-1].reset_index(drop=True), set(m.tns_name), CFG)
    merged = a.merge(b, on="tns_name", suffixes=("_a", "_b"))
    assert (merged.split_a == merged.split_b).all()     # order-independent


def test_quarantine_flag():
    m = _manifest()
    sp = splits.build(m, set(m.tns_name), CFG, quarantined_tns={"N1"})
    assert bool(sp.set_index("tns_name").loc["N1", "quarantined"])
    assert not bool(sp.set_index("tns_name").loc["N2", "quarantined"])


def test_quarantine_named_only(tmp_path):
    q = quarantine.build_quarantine(CFG, None)
    assert set(q) == {"FRBA", "FRBB"}
