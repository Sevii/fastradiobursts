"""Task 4 — schema contract for CHIME/FRB Catalog 2 Stokes-I dynamic spectra.

Single source of truth for the interpretation of every supported file type:
required/optional datasets, expected constants, tolerances, and a
``validate_file`` function that returns structured violations. Used by both the
pytest suite (``tests/test_schema_contract.py``) and the catalog-scale runner
(``validate_catalog.py``). Violation codes map onto the Task 7 exclusion codes.

The contract is derived from ``docs/tier_a_input_schema.md`` and must fail loudly
on any file that does not match the documented interpretation.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

try:
    import h5py
except Exception:  # pragma: no cover - h5py always present in the env
    h5py = None

# ---------------------------------------------------------------------------
# Contract constants (from the decoded Catalog 2 schema)
# ---------------------------------------------------------------------------
NUM_FREQ = 16384
RES_FREQ_MHZ = 0.0244140625
FREQ_MIN_MHZ = 400.20751953125
FREQ_MAX_MHZ = 800.18310546875
NATIVE_RES_TIME_S = 0.00098304   # native cadence; valid products are native * 2**k
                                 # observed downsample factors: 1, 2, 4

# tolerances
FREQ_ABS_TOL_MHZ = 0.05          # band edge / channel center agreement
RES_FREQ_ABS_TOL = 1e-6
RES_TIME_REL_TOL = 1e-3          # cadence / spacing agreement

REQUIRED_DATASETS = {
    "data": ("float32", 2),
    "flag": ("bool", 2),
    "good_freq": ("bool", 1),
    "index_map/freqs": ("float64", 1),
    "index_map/times": ("float64", 1),
    "index_map/times_unix": ("float64", 1),
    "times": ("float64", 2),
    "statistics/mean": ("float64", 1),
    "statistics/central_moment_2": ("float64", 1),
    "statistics/central_moment_3": ("float64", 1),
    "statistics/central_moment_4": ("float64", 1),
    "statistics/nsample": ("int64", 1),
}
OPTIONAL_DATASETS = {
    "model": ("float32", 2),
    "calibration/flux_conversion_factor": ("float64", 1),
    "calibration/spectrum": ("float64", 1),
    "calibration/good_freq": ("bool", 1),
}
REQUIRED_ATTRS = [
    "tns_name", "num_freq", "num_time", "res_time", "res_freq",
    "is_dedispersed", "dm_incoherent", "ref_freq", "stokes",
    "start_time_unix_nano",
]
# `pulse_emission_region` and `model` are OPTIONAL: absent in the ~87 "un-modeled"
# bursts (structurally valid; on-pulse region must be derived another way at Task 7).

ERROR = "ERROR"
WARNING = "WARNING"

FILENAME_RE = re.compile(r"^(FRB\w+?)_stokesi_dynamic_spectrum\.h5$")


@dataclass
class Violation:
    code: str
    severity: str
    field: str
    message: str


@dataclass
class ValidationResult:
    path: str
    filename: str
    ok: bool = True
    readable: bool = False
    violations: list = field(default_factory=list)
    has_model: bool = False
    has_calibration: bool = False
    has_pulse_region: bool = False
    time_downsample_factor: Optional[int] = None

    def add(self, code, severity, fieldname, message):
        self.violations.append(Violation(code, severity, fieldname, message))
        if severity == ERROR:
            self.ok = False

    @property
    def error_codes(self):
        return sorted({v.code for v in self.violations if v.severity == ERROR})

    @property
    def warning_codes(self):
        return sorted({v.code for v in self.violations if v.severity == WARNING})

    def to_row(self):
        return {
            "path": self.path,
            "filename": self.filename,
            "readable": self.readable,
            "ok": self.ok,
            "n_errors": sum(v.severity == ERROR for v in self.violations),
            "n_warnings": sum(v.severity == WARNING for v in self.violations),
            "error_codes": ",".join(self.error_codes),
            "warning_codes": ",".join(self.warning_codes),
            "has_model": self.has_model,
            "has_calibration": self.has_calibration,
            "has_pulse_region": self.has_pulse_region,
            "time_downsample_factor": self.time_downsample_factor,
            "messages": " | ".join(
                f"[{v.severity}:{v.code}] {v.field}: {v.message}"
                for v in self.violations),
        }


def _attr(a, key, default=None):
    v = a.get(key, default)
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.generic):
        return v.item()
    return v


def validate_file(path: str, expected_tns: Optional[str] = None) -> ValidationResult:
    """Validate one .h5 against the contract. Never raises; returns result."""
    fn = os.path.basename(path)
    r = ValidationResult(path=path, filename=fn)

    # filename-derived expected TNS
    m = FILENAME_RE.match(fn)
    if expected_tns is None and m:
        expected_tns = m.group(1)

    if h5py is None:  # pragma: no cover
        r.add("E015_UNSUPPORTED_FORMAT", ERROR, "h5py", "h5py unavailable")
        return r

    try:
        f = h5py.File(path, "r")
    except Exception as e:  # noqa: BLE001
        r.add("E015_UNSUPPORTED_FORMAT", ERROR, "file",
              f"cannot open as HDF5: {e}")
        return r

    with f:
        r.readable = True
        present = {}

        def visit(name, obj):
            if isinstance(obj, h5py.Dataset):
                present[name] = obj
        f.visititems(visit)
        a = f.attrs

        # ---- required datasets present, dtype, ndim ----
        for name, (dtype, ndim) in REQUIRED_DATASETS.items():
            if name not in present:
                code = {
                    "index_map/times": "E003_MISSING_TIME_AXIS",
                    "index_map/freqs": "E004_MISSING_FREQUENCY_AXIS",
                    "flag": "E012_MASK_UNINTERPRETABLE",
                    "good_freq": "E012_MASK_UNINTERPRETABLE",
                    "data": "E015_UNSUPPORTED_FORMAT",
                }.get(name, "E011_CORRUPT_ARRAY")
                r.add(code, ERROR, name, "required dataset missing")
                continue
            d = present[name]
            if d.ndim != ndim:
                r.add("E005_AXIS_DIMENSION_MISMATCH", ERROR, name,
                      f"expected {ndim}D, got {d.ndim}D")
            if str(d.dtype) != dtype:
                r.add("E013_METADATA_MISMATCH", WARNING, name,
                      f"dtype {d.dtype} != expected {dtype}")

        r.has_model = "model" in present
        r.has_calibration = "calibration/flux_conversion_factor" in present
        r.has_pulse_region = "pulse_emission_region" in a
        if not r.has_model:
            r.add("W_NO_MODEL", WARNING, "model", "optional /model absent")
        if not r.has_calibration:
            r.add("W_NO_CALIBRATION", WARNING, "calibration",
                  "optional /calibration absent; normalized-only (no Jy)")
        if not r.has_pulse_region:
            r.add("W_NO_PULSE_REGION", WARNING, "pulse_emission_region",
                  "on-pulse region attr absent; off-pulse to be derived at Task 7")

        # If core data missing we cannot continue meaningfully
        if "data" not in present:
            return r

        data = present["data"]

        # ---- required attrs ----
        for key in REQUIRED_ATTRS:
            if key not in a:
                r.add("E013_METADATA_MISMATCH", ERROR, f"attr:{key}",
                      "required attribute missing")

        # ---- constants ----
        num_freq = _attr(a, "num_freq")
        if num_freq is not None and int(num_freq) != NUM_FREQ:
            r.add("E013_METADATA_MISMATCH", ERROR, "num_freq",
                  f"{num_freq} != {NUM_FREQ}")
        if data.shape[0] != NUM_FREQ:
            r.add("E005_AXIS_DIMENSION_MISMATCH", ERROR, "data.shape[0]",
                  f"freq axis {data.shape[0]} != {NUM_FREQ}")

        is_dd = _attr(a, "is_dedispersed")
        if is_dd is not None and not bool(is_dd):
            r.add("E013_METADATA_MISMATCH", ERROR, "is_dedispersed",
                  "expected already-dedispersed data (True)")

        stokes = _attr(a, "stokes")
        if stokes is not None and str(stokes) != "I":
            r.add("E013_METADATA_MISMATCH", ERROR, "stokes",
                  f"expected Stokes I, got {stokes!r}")

        res_freq = _attr(a, "res_freq")
        if res_freq is not None and abs(float(res_freq) - RES_FREQ_MHZ) > RES_FREQ_ABS_TOL:
            r.add("E013_METADATA_MISMATCH", WARNING, "res_freq",
                  f"{res_freq} != {RES_FREQ_MHZ}")

        res_time = _attr(a, "res_time")
        if res_time is not None:
            factor = float(res_time) / NATIVE_RES_TIME_S
            k = round(math.log2(factor)) if factor > 0 else -1
            is_pow2 = k >= 0 and math.isclose(
                factor, 2 ** k, rel_tol=RES_TIME_REL_TOL)
            if is_pow2:
                r.time_downsample_factor = int(2 ** k)
            else:
                r.add("W_UNUSUAL_CADENCE", WARNING, "res_time",
                      f"res_time {res_time} is not native*2^k "
                      f"(factor {factor:.3f})")

        # ---- coordinate axes ----
        freqs = present["index_map/freqs"][()] if "index_map/freqs" in present else None
        times = present["index_map/times"][()] if "index_map/times" in present else None

        if freqs is not None:
            if freqs.shape[0] != data.shape[0]:
                r.add("E005_AXIS_DIMENSION_MISMATCH", ERROR, "index_map/freqs",
                      f"len {freqs.shape[0]} != data freq axis {data.shape[0]}")
            if freqs.size >= 2:
                if not bool(np.all(np.diff(freqs) > 0)):
                    r.add("E013_METADATA_MISMATCH", ERROR, "index_map/freqs",
                          "frequency axis not strictly increasing/monotonic")
                if abs(float(freqs.min()) - FREQ_MIN_MHZ) > FREQ_ABS_TOL_MHZ or \
                   abs(float(freqs.max()) - FREQ_MAX_MHZ) > FREQ_ABS_TOL_MHZ:
                    r.add("E013_METADATA_MISMATCH", WARNING, "index_map/freqs",
                          f"band [{freqs.min():.3f},{freqs.max():.3f}] off nominal")

        if times is not None:
            if times.shape[0] != data.shape[1]:
                r.add("E005_AXIS_DIMENSION_MISMATCH", ERROR, "index_map/times",
                      f"len {times.shape[0]} != data time axis {data.shape[1]}")
            if times.size >= 2:
                dts = np.diff(times)
                if not bool(np.all(dts > 0)):
                    r.add("E013_METADATA_MISMATCH", ERROR, "index_map/times",
                          "time axis not strictly increasing/monotonic")
                # res_time attr must match the actual coordinate spacing
                if res_time is not None:
                    spacing = float(np.median(dts))
                    if not math.isclose(spacing, float(res_time),
                                        rel_tol=RES_TIME_REL_TOL):
                        r.add("E013_METADATA_MISMATCH", ERROR, "res_time",
                              f"res_time {res_time} != time spacing {spacing:.3e}")

        num_time = _attr(a, "num_time")
        if num_time is not None and int(num_time) != data.shape[1]:
            r.add("E013_METADATA_MISMATCH", ERROR, "num_time",
                  f"attr {num_time} != data time axis {data.shape[1]}")

        # ---- mask shapes ----
        if "flag" in present and present["flag"].shape != data.shape:
            r.add("E012_MASK_UNINTERPRETABLE", ERROR, "flag",
                  f"flag shape {present['flag'].shape} != data {data.shape}")
        if "good_freq" in present and present["good_freq"].shape[0] != data.shape[0]:
            r.add("E012_MASK_UNINTERPRETABLE", ERROR, "good_freq",
                  f"good_freq len {present['good_freq'].shape[0]} != {data.shape[0]}")

        # ---- unexpected non-finite in data ----
        arr = data[()]
        n_nan = int(np.isnan(arr).sum())
        n_inf = int(np.isinf(arr).sum())
        if n_nan or n_inf:
            r.add("E011_CORRUPT_ARRAY", ERROR, "data",
                  f"unexpected non-finite: nan={n_nan} inf={n_inf}")

        # ---- units declared ----
        for name, expect in [("index_map/freqs", "MHz"),
                             ("index_map/times", "s")]:
            if name in present:
                unit = _attr(present[name].attrs, "unit")
                if unit is None:
                    r.add("E013_METADATA_MISMATCH", WARNING, f"{name}.unit",
                          "declared unit absent")
                elif str(unit) != expect:
                    r.add("E013_METADATA_MISMATCH", WARNING, f"{name}.unit",
                          f"unit {unit!r} != {expect!r}")

        # ---- metadata identity vs filename ----
        tns = _attr(a, "tns_name")
        if expected_tns and tns and str(tns) != expected_tns:
            r.add("E013_METADATA_MISMATCH", ERROR, "tns_name",
                  f"attr tns_name {tns!r} != filename {expected_tns!r}")

    return r
