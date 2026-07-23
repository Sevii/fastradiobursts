"""Task 4 — automated schema tests.

Two layers:
  1. Synthetic fixtures: build a minimal *valid* Catalog 2 file, then mutate one
     thing at a time and assert the contract flags it with the right code. This
     tests the tests loudly without touching the 56 GB archive.
  2. Real-file spot check: if ECHO_FRB_DATA points at the Tier A directory, run
     the contract over a small real sample and assert they validate clean.
"""
import glob
import os

import h5py
import numpy as np
import pytest

from echo_frb.schema import contract as C
from echo_frb.schema.contract import validate_file, ERROR, WARNING

NT = 8  # small time axis for fast fixtures


def make_valid(path, tns="FRB20200101A", num_freq=C.NUM_FREQ, num_time=NT,
               with_model=True, with_calibration=True):
    """Write a minimal file that satisfies the contract."""
    freqs = np.linspace(C.FREQ_MIN_MHZ, C.FREQ_MAX_MHZ, num_freq)
    times = np.arange(num_time, dtype="float64") * C.NATIVE_RES_TIME_S
    data = np.zeros((num_freq, num_time), dtype="float32")
    with h5py.File(path, "w") as f:
        a = f.attrs
        a["tns_name"] = tns
        a["num_freq"] = num_freq
        a["num_time"] = num_time
        a["res_time"] = C.NATIVE_RES_TIME_S
        a["res_freq"] = C.RES_FREQ_MHZ
        a["is_dedispersed"] = True
        a["dm_incoherent"] = 500.0
        a["ref_freq"] = C.FREQ_MIN_MHZ
        a["stokes"] = "I"
        a["start_time_unix_nano"] = np.int64(1_500_000_000_000_000_000)
        a["pulse_emission_region"] = np.array([[num_time // 2,
                                                num_time // 2 + 1]], dtype="int64")
        f.create_dataset("data", data=data)
        f.create_dataset("flag", data=np.ones((num_freq, num_time), bool))
        f.create_dataset("good_freq", data=np.ones(num_freq, bool))
        f.create_dataset("times", data=np.zeros((num_freq, num_time), "float64"))
        im = f.create_group("index_map")
        df = im.create_dataset("freqs", data=freqs); df.attrs["unit"] = "MHz"
        dt = im.create_dataset("times", data=times); dt.attrs["unit"] = "s"
        im.create_dataset("times_unix", data=times + 1.5e9)
        st = f.create_group("statistics")
        st.create_dataset("mean", data=np.ones(num_freq, "float64"))
        st.create_dataset("central_moment_2", data=np.ones(num_freq, "float64"))
        st.create_dataset("central_moment_3", data=np.zeros(num_freq, "float64"))
        st.create_dataset("central_moment_4", data=np.ones(num_freq, "float64"))
        st.create_dataset("nsample", data=np.full(num_freq, 1000, "int64"))
        if with_model:
            f.create_dataset("model", data=data)
        if with_calibration:
            cal = f.create_group("calibration")
            cal.create_dataset("flux_conversion_factor",
                               data=np.ones(num_freq, "float64"))
            cal.create_dataset("spectrum", data=np.ones(num_freq, "float64"))
            cal.create_dataset("good_freq", data=np.ones(num_freq, bool))
    return path


# --------------------------------------------------------------------------
# 1. the valid baseline passes
# --------------------------------------------------------------------------
def test_valid_file_passes(tmp_path):
    p = make_valid(tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5")
    r = validate_file(str(p))
    assert r.ok, r.to_row()["messages"]
    assert r.error_codes == []
    assert r.has_model and r.has_calibration


def test_missing_optional_is_warning_not_error(tmp_path):
    p = make_valid(tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5",
                   with_model=False, with_calibration=False)
    r = validate_file(str(p))
    assert r.ok  # still valid
    assert "W_NO_MODEL" in r.warning_codes
    assert "W_NO_CALIBRATION" in r.warning_codes


def test_missing_pulse_region_is_warning_not_error(tmp_path):
    # the ~87 "un-modeled" bursts: structurally valid, on-pulse region absent
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    make_valid(p)
    with h5py.File(p, "a") as f:
        del f.attrs["pulse_emission_region"]
    r = validate_file(str(p))
    assert r.ok, r.to_row()["messages"]
    assert "W_NO_PULSE_REGION" in r.warning_codes
    assert not r.has_pulse_region


def test_downsampled_cadence_is_valid(tmp_path):
    # 2x native cadence is a legitimate product; factor is recorded, not flagged
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    make_valid(p)
    with h5py.File(p, "a") as f:
        f.attrs["res_time"] = 2 * C.NATIVE_RES_TIME_S
        t = np.arange(NT, dtype="float64") * (2 * C.NATIVE_RES_TIME_S)
        f["index_map/times"][...] = t
    r = validate_file(str(p))
    assert r.ok, r.to_row()["messages"]
    assert r.time_downsample_factor == 2
    assert "W_UNUSUAL_CADENCE" not in r.warning_codes


def test_res_time_inconsistent_with_spacing_is_error(tmp_path):
    # res_time attr disagrees with the actual time-axis spacing -> corruption
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    make_valid(p)
    with h5py.File(p, "a") as f:
        f.attrs["res_time"] = 5 * C.NATIVE_RES_TIME_S  # times unchanged
    assert "E013_METADATA_MISMATCH" in _codes(p)


# --------------------------------------------------------------------------
# 2. each malformation is caught with the right ERROR code
# --------------------------------------------------------------------------
def _codes(path):
    return validate_file(str(path)).error_codes


def test_missing_time_axis(tmp_path):
    p = make_valid(tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5")
    with h5py.File(p, "a") as f:
        del f["index_map/times"]
    assert "E003_MISSING_TIME_AXIS" in _codes(p)


def test_missing_frequency_axis(tmp_path):
    p = make_valid(tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5")
    with h5py.File(p, "a") as f:
        del f["index_map/freqs"]
    assert "E004_MISSING_FREQUENCY_AXIS" in _codes(p)


def test_axis_dimension_mismatch(tmp_path):
    # freqs length disagrees with data freq axis
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    make_valid(p)
    with h5py.File(p, "a") as f:
        del f["index_map/freqs"]
        f.create_dataset("index_map/freqs",
                         data=np.linspace(400, 800, C.NUM_FREQ - 1))
    assert "E005_AXIS_DIMENSION_MISMATCH" in _codes(p)


def test_non_finite_data_is_corrupt(tmp_path):
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    make_valid(p)
    with h5py.File(p, "a") as f:
        d = f["data"][()]
        d[0, 0] = np.nan
        d[1, 0] = np.inf
        f["data"][...] = d
    assert "E011_CORRUPT_ARRAY" in _codes(p)


def test_mask_shape_mismatch(tmp_path):
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    make_valid(p)
    with h5py.File(p, "a") as f:
        del f["flag"]
        f.create_dataset("flag", data=np.ones((C.NUM_FREQ, NT + 3), bool))
    assert "E012_MASK_UNINTERPRETABLE" in _codes(p)


def test_freq_not_monotonic(tmp_path):
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    make_valid(p)
    with h5py.File(p, "a") as f:
        fr = f["index_map/freqs"][()]
        fr[100], fr[101] = fr[101], fr[100]  # break monotonicity
        f["index_map/freqs"][...] = fr
    assert "E013_METADATA_MISMATCH" in _codes(p)


def test_not_dedispersed(tmp_path):
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    make_valid(p)
    with h5py.File(p, "a") as f:
        f.attrs["is_dedispersed"] = False
    assert "E013_METADATA_MISMATCH" in _codes(p)


def test_tns_filename_mismatch(tmp_path):
    # filename says A, attr says B
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    make_valid(p, tns="FRB20200101B")
    assert "E013_METADATA_MISMATCH" in _codes(p)


def test_wrong_num_freq(tmp_path):
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    make_valid(p, num_freq=8192)
    assert "E013_METADATA_MISMATCH" in _codes(p) or \
        "E005_AXIS_DIMENSION_MISMATCH" in _codes(p)


def test_not_hdf5(tmp_path):
    p = tmp_path / "FRB20200101A_stokesi_dynamic_spectrum.h5"
    p.write_bytes(b"not an hdf5 file")
    assert "E015_UNSUPPORTED_FORMAT" in _codes(p)


# --------------------------------------------------------------------------
# 3. real-file spot check (opt-in via ECHO_FRB_DATA)
# --------------------------------------------------------------------------
@pytest.mark.skipif(not os.environ.get("ECHO_FRB_DATA"),
                    reason="set ECHO_FRB_DATA to the Tier A data dir")
def test_real_sample_validates_clean():
    root = os.environ["ECHO_FRB_DATA"]
    files = sorted(glob.glob(os.path.join(root, "*.h5")))
    assert files, f"no .h5 under {root}"
    sample = files[:: max(1, len(files) // 25)][:25]
    bad = []
    for p in sample:
        r = validate_file(p)
        if not r.ok:
            bad.append((os.path.basename(p), r.error_codes))
    assert not bad, f"real files failed schema: {bad}"
