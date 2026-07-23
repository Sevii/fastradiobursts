"""Task 7 — unit tests for the eligibility decision logic."""
import yaml

from echo_frb.eligibility.engine import classify

CFG = {
    "version": 1,
    "eligibility": {
        "min_usable_bandwidth_mhz": 100.0,
        "min_time_coverage_bins": 32,
        "min_offpulse_bins": 16,
        "soft_masked_pixel_frac": 0.50,
    },
}
DCT = {
    "E001_UNREADABLE_FILE": {"status": "processing_failure", "reversible": True},
    "E007_INSUFFICIENT_USABLE_BANDWIDTH": {"status": "excluded", "reversible": False},
    "E008_INSUFFICIENT_TIME_COVERAGE": {"status": "excluded", "reversible": False},
    "E006_INSUFFICIENT_OFF_PULSE": {"status": "excluded", "reversible": False},
    "E013_METADATA_MISMATCH": {"status": "excluded", "reversible": False},
}


def base(**over):
    r = dict(readable=True, schema_ok=True, schema_error_codes="",
             usable_bandwidth_mhz=300.0, num_time=162,
             has_pulse_region=True, total_offpulse_bins=150,
             has_calibration=True, orig_masked_pixel_frac=0.14)
    r.update(over)
    return r


def test_clean_is_eligible():
    d = classify(base(), CFG, DCT)
    assert d["status"] == "eligible"
    assert d["primary_reason"] is None


def test_unreadable_is_processing_failure():
    d = classify(base(readable=False), CFG, DCT)
    assert d["status"] == "processing_failure"
    assert d["primary_reason"] == "E001_UNREADABLE_FILE"


def test_schema_failure_uses_first_code():
    d = classify(base(schema_ok=False,
                       schema_error_codes="E013_METADATA_MISMATCH"), CFG, DCT)
    assert d["status"] == "excluded"
    assert d["primary_reason"] == "E013_METADATA_MISMATCH"


def test_low_bandwidth_excluded():
    d = classify(base(usable_bandwidth_mhz=80.0), CFG, DCT)
    assert d["status"] == "excluded"
    assert d["primary_reason"] == "E007_INSUFFICIENT_USABLE_BANDWIDTH"


def test_low_time_coverage_excluded():
    d = classify(base(num_time=20), CFG, DCT)
    assert d["status"] == "excluded"
    assert d["primary_reason"] == "E008_INSUFFICIENT_TIME_COVERAGE"


def test_low_offpulse_excluded_only_when_region_known():
    d = classify(base(total_offpulse_bins=5), CFG, DCT)
    assert d["primary_reason"] == "E006_INSUFFICIENT_OFF_PULSE"
    # same low off-pulse but region unknown -> not excluded on E006
    d2 = classify(base(has_pulse_region=False, total_offpulse_bins=None),
                  CFG, DCT)
    assert d2["status"] == "provisionally_eligible"
    assert "needs_offpulse_derivation" in d2["secondary_reasons"]


def test_multiple_failures_primary_by_priority():
    # both time-coverage and bandwidth fail; E008 outranks E007
    d = classify(base(num_time=10, usable_bandwidth_mhz=50.0), CFG, DCT)
    assert d["primary_reason"] == "E008_INSUFFICIENT_TIME_COVERAGE"
    assert "E007_INSUFFICIENT_USABLE_BANDWIDTH" in d["secondary_reasons"]


def test_no_calibration_is_provisional():
    d = classify(base(has_calibration=False), CFG, DCT)
    assert d["status"] == "provisionally_eligible"
    assert "no_calibration" in d["secondary_reasons"]


def test_heavily_masked_is_provisional():
    d = classify(base(orig_masked_pixel_frac=0.8), CFG, DCT)
    assert d["status"] == "provisionally_eligible"
    assert "heavily_masked" in d["secondary_reasons"]


def test_catalog_flags_are_provisional_not_excluded():
    d = classify(base(catalog_excluded_flag=1), CFG, DCT)
    assert d["status"] == "provisionally_eligible"
    assert "catalog_excluded" in d["secondary_reasons"]
    d2 = classify(base(catalog_sidelobe_flag=1), CFG, DCT)
    assert "catalog_sidelobe" in d2["secondary_reasons"]


def test_every_row_gets_a_status():
    # fuzz a range of inputs; classify must always return a known status
    ok = {"eligible", "provisionally_eligible", "excluded",
          "processing_failure", "pending_manual_review"}
    for nt in (0, 10, 32, 162):
        for bw in (0.0, 80.0, 300.0):
            for hr in (True, False):
                d = classify(base(num_time=nt, usable_bandwidth_mhz=bw,
                                  has_pulse_region=hr,
                                  total_offpulse_bins=3 if hr else None),
                             CFG, DCT)
                assert d["status"] in ok
