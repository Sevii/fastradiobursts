"""Task 5 — tests for the reference-set interpretation auto-check."""
import numpy as np

from echo_frb.reference.make_plots import autocheck

NF, NT = 16384, 40


def make_AB(break_orientation=False, break_project_mask=False,
            break_recon=False, break_onpulse=False):
    freqs = np.linspace(400.2, 800.2, NF)
    if break_orientation:
        freqs = freqs[::-1]
    data = np.zeros((NF, NT), np.float32)
    burst_t = 6
    data[:, burst_t] = 1.0                # burst at t=6
    flag = np.ones((NF, NT), bool)
    flag[10, :] = False                   # one masked channel
    good_freq = np.ones(NF, bool)
    baseline = np.zeros(NF, np.float64)
    standardized = (data - baseline[:, None]).astype(np.float32)
    if break_recon:
        standardized = standardized + 1.0
    project_mask = flag.copy()
    if break_project_mask:
        project_mask[10, :] = True        # marks an original-masked pixel usable
    A = dict(data=data, flag=flag, good_freq=good_freq, freqs=freqs,
             times=np.arange(NT, dtype="float64"), attrs={})
    on0, on1 = (30, 31) if break_onpulse else (5, 7)  # far from burst at t=6
    B = dict(standardized=standardized, project_mask=project_mask,
             baseline=baseline, robust=np.ones(NF), conv=np.ones(NF),
             offmask=np.ones(NT, bool),
             attrs={"on_pulse_start": on0, "on_pulse_end": on1})
    return A, B


def test_autocheck_ok_on_clean():
    ok, msgs = autocheck(*make_AB())
    assert ok, msgs


def test_autocheck_flags_orientation():
    ok, msgs = autocheck(*make_AB(break_orientation=True))
    assert not ok and any("monotonic" in m for m in msgs)


def test_autocheck_flags_project_mask_violation():
    ok, msgs = autocheck(*make_AB(break_project_mask=True))
    assert not ok and any("project_mask" in m for m in msgs)


def test_autocheck_flags_bad_reconstruction():
    ok, msgs = autocheck(*make_AB(break_recon=True))
    assert not ok and any("data-baseline" in m for m in msgs)


def test_autocheck_flags_burst_outside_onpulse():
    ok, msgs = autocheck(*make_AB(break_onpulse=True))
    assert not ok and any("peak" in m for m in msgs)
