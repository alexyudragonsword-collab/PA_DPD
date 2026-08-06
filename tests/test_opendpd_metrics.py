import importlib.util
import os

import numpy as np
import pytest

from padpd.metrics import (aclr_opendpd, evm_spectral, nmse_segmented,
                           target_gain_opendpd)

OPENDPD_ROOT = os.environ.get("OPENDPD_ROOT", "/home/user/OpenDPD")
FS, BW, N_SUB, NPERSEG = 800e6, 200e6, 10, 2560


def _random_pair(n=4 * NPERSEG, seed=0):
    rng = np.random.default_rng(seed)
    y_true = rng.standard_normal(n) + 1j * rng.standard_normal(n)
    y_pred = y_true + 0.05 * (rng.standard_normal(n)
                              + 1j * rng.standard_normal(n))
    return y_pred, y_true


def test_nmse_segmented_uniform_equals_global():
    rng = np.random.default_rng(1)
    y = rng.standard_normal(2 * NPERSEG) + 1j * rng.standard_normal(2 * NPERSEG)
    err = 0.01 * (rng.standard_normal(len(y)) + 1j * rng.standard_normal(len(y)))
    got = nmse_segmented(y + err, y, NPERSEG)
    expected = 10 * np.log10(np.sum(np.abs(err) ** 2)
                             / np.sum(np.abs(y) ** 2))
    assert got == pytest.approx(expected, abs=0.1)


def test_target_gain():
    rng = np.random.default_rng(2)
    x = rng.standard_normal(1000) + 1j * rng.standard_normal(1000)
    assert target_gain_opendpd(x, 2.5 * x) == pytest.approx(2.5)


def test_aclr_clean_signal_strongly_negative():
    # In-band-only signal: build from a narrowband OFDM-ish spectrum
    rng = np.random.default_rng(3)
    n_seg, n = 4, NPERSEG
    spec = np.zeros((n_seg, n), complex)
    freq = np.fft.fftshift(np.fft.fftfreq(n, 1 / FS))
    in_band = np.abs(freq) < BW / 2 * 0.95
    spec[:, in_band] = (rng.standard_normal((n_seg, in_band.sum()))
                        + 1j * rng.standard_normal((n_seg, in_band.sum())))
    y = np.fft.ifft(np.fft.ifftshift(spec, axes=-1), axis=-1).reshape(-1)
    res = aclr_opendpd(y, FS, BW, N_SUB, NPERSEG)
    assert res["left_dbc"] < -30
    assert res["right_dbc"] < -30
    assert res["avg_dbc"] == pytest.approx(
        (res["left_dbc"] + res["right_dbc"]) / 2)


def _load_reference_metrics():
    path = os.path.join(OPENDPD_ROOT, "utils", "metrics.py")
    spec = importlib.util.spec_from_file_location("opendpd_metrics", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


needs_opendpd = pytest.mark.skipif(
    not os.path.exists(os.path.join(OPENDPD_ROOT, "utils", "metrics.py")),
    reason="OpenDPD repo not available")


def _to_iq_segments(z, nperseg=NPERSEG):
    seg = z[: len(z) // nperseg * nperseg].reshape(-1, nperseg)
    return np.stack([seg.real, seg.imag], axis=-1)


@needs_opendpd
def test_nmse_matches_opendpd_reference():
    ref = _load_reference_metrics()
    y_pred, y_true = _random_pair()
    ours = nmse_segmented(y_pred, y_true, NPERSEG)
    theirs = ref.NMSE(_to_iq_segments(y_pred), _to_iq_segments(y_true))
    assert ours == pytest.approx(theirs, abs=1e-9)


@needs_opendpd
def test_evm_matches_opendpd_reference():
    ref = _load_reference_metrics()
    y_pred, y_true = _random_pair(seed=4)
    ours = evm_spectral(y_pred, y_true, FS, BW, N_SUB, NPERSEG)
    theirs = ref.EVM(_to_iq_segments(y_pred), _to_iq_segments(y_true),
                     sample_rate=int(FS), bw_main_ch=BW, n_sub_ch=N_SUB,
                     nperseg=NPERSEG)
    assert ours == pytest.approx(theirs, abs=1e-9)


@needs_opendpd
def test_aclr_matches_opendpd_reference():
    ref = _load_reference_metrics()
    y_pred, _ = _random_pair(seed=5)
    ours = aclr_opendpd(y_pred, FS, BW, N_SUB, NPERSEG)
    left, right = ref.ACLR(_to_iq_segments(y_pred), fs=FS, nperseg=NPERSEG,
                           bw_main_ch=BW, n_sub_ch=N_SUB)
    assert ours["left_dbc"] == pytest.approx(left, abs=1e-9)
    assert ours["right_dbc"] == pytest.approx(right, abs=1e-9)


@needs_opendpd
def test_target_gain_matches_opendpd_reference():
    path = os.path.join(OPENDPD_ROOT, "utils", "util.py")
    spec = importlib.util.spec_from_file_location("opendpd_util", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rng = np.random.default_rng(6)
    x = rng.standard_normal(500) + 1j * rng.standard_normal(500)
    y = 1.9 * x + 0.1
    ours = target_gain_opendpd(x, y)
    theirs = mod.set_target_gain(np.stack([x.real, x.imag], axis=-1),
                                 np.stack([y.real, y.imag], axis=-1))
    assert ours == pytest.approx(theirs, rel=1e-12)


def test_aclr_opendpd_rejects_too_narrow_guard_band():
    import numpy as np
    import pytest
    from padpd.metrics import aclr_opendpd
    y = (np.random.default_rng(0).standard_normal(65536)
         + 1j * np.random.default_rng(1).standard_normal(65536))
    # guard band narrower than one sub-channel used to return -inf silently
    with pytest.raises(ValueError):
        aclr_opendpd(y, fs=180e6, bw_main_ch=160e6, n_sub_ch=8, nperseg=1024)
