"""Unit tests: each loopback impairment is individually calibrated."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from padpd.loopback import LoopbackChannel  # noqa: E402

FS = 320e6
RNG = np.random.default_rng(7)
X = (RNG.standard_normal(65536) + 1j * RNG.standard_normal(65536)) / 2 ** 0.5


def _pow(v):
    return np.mean(np.abs(v) ** 2)


def test_identity_when_disabled():
    y = LoopbackChannel()(X, FS)
    assert np.allclose(y, X)


def test_snr_calibration():
    y = LoopbackChannel(snr_db=40)(X, FS)
    snr = 10 * np.log10(_pow(X) / _pow(y - X))
    assert abs(snr - 40) < 0.3


def test_irr_formula_matches_injected_image():
    ch = LoopbackChannel(iq_gain_imbalance_db=0.3,
                        iq_phase_imbalance_deg=2.0)
    y = ch(X, FS)
    # image power = |b|^2 * signal power (X is circular)
    g = 10 ** (0.3 / 20)
    b = 0.5 * (1 - g * np.exp(1j * np.deg2rad(2.0)))
    # correlate with conj(X) to pull the image term out. For a
    # circular X, sum(X^2) ~ 0, so this lands on b itself.
    img = np.vdot(X.conj(), y) / np.vdot(X.conj(), X.conj())
    assert abs(img) == pytest.approx(abs(b), rel=0.05)  # measured 1.9%
    meas_irr = 20 * np.log10(
        abs(np.vdot(X, y) / np.vdot(X, X)) / abs(img))
    assert abs(meas_irr - ch.irr_db()) < 0.5
    assert 25 < ch.irr_db() < 40


def test_rx_im3_level():
    y = LoopbackChannel(rx_im3_dbc=-45)(X, FS)
    d_db = 10 * np.log10(_pow(y - X) / _pow(X))
    assert abs(d_db - (-45)) < 0.5


def test_lo_leakage_dc_level():
    y = LoopbackChannel(lo_leakage_dbc=-30)(X, FS)
    dc = np.mean(y - X)
    assert abs(20 * np.log10(abs(dc) / np.sqrt(_pow(X))) - (-30)) < 0.5


def test_fractional_delay_recovered_by_align():
    from padpd.data import align_delay
    # band-limited input (like oversampled OFDM): parabolic peak
    # interpolation is only unbiased for band-limited signals
    spec = np.fft.fft(X)
    spec[len(X) // 8: -len(X) // 8] = 0
    xb = np.fft.ifft(spec)
    y = LoopbackChannel(delay_samples=3.37)(xb, FS)
    _, _, info = align_delay(xb, y, max_lag=64)
    assert abs(abs(info["lag_total"]) - 3.37) < 0.05


def test_phase_noise_rms():
    ch = LoopbackChannel(phase_noise_rms_deg=1.5, phase_noise_bw_hz=1e6)
    y = ch(X, FS)
    ph = np.angle(y / X)
    assert abs(np.std(np.rad2deg(ph)) - 1.5) < 0.2


def test_ripple_changes_spectrum_but_not_power():
    y = LoopbackChannel(ripple_db=1.0, gd_ripple_ns=1.0)(X, FS)
    assert abs(10 * np.log10(_pow(y) / _pow(X))) < 0.1
    assert _pow(y - X) > 1e-4 * _pow(X)  # actually did something


def test_cfo_rotation():
    y = LoopbackChannel(cfo_hz=1e5)(X, FS)
    t = np.arange(len(X)) / FS
    assert np.allclose(y, X * np.exp(2j * np.pi * 1e5 * t))
