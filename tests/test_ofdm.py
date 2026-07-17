import numpy as np
import pytest

from padpd.waveform import OFDMConfig, demodulate_ofdm, generate_ofdm, papr_db


def test_config_numerology():
    cfg = OFDMConfig(bandwidth_hz=320e6)
    assert cfg.fft_size == 4096
    assert cfg.n_active == 3984
    assert cfg.cp_len == 256
    cfg20 = OFDMConfig(bandwidth_hz=20e6)
    assert cfg20.fft_size == 256
    assert cfg20.n_active == 242


@pytest.mark.parametrize("bw,order", [(20e6, 256), (80e6, 1024), (160e6, 1024)])
def test_loopback_recovers_symbols(bw, order):
    cfg = OFDMConfig(bandwidth_hz=bw, qam_order=order, n_symbols=4, seed=3)
    wf = generate_ofdm(cfg)
    rx = demodulate_ofdm(wf.x, wf)
    np.testing.assert_allclose(rx, wf.tx_symbols, atol=1e-10)


def test_unit_power_and_papr():
    cfg = OFDMConfig(bandwidth_hz=80e6, n_symbols=10, seed=7)
    wf = generate_ofdm(cfg)
    assert np.mean(np.abs(wf.x) ** 2) == pytest.approx(1.0)
    # OFDM PAPR is typically 8-13 dB
    assert 6 < papr_db(wf.x) < 15


def test_spectrum_confined_to_bandwidth():
    cfg = OFDMConfig(bandwidth_hz=80e6, n_symbols=10, oversampling=4, seed=5)
    wf = generate_ofdm(cfg)
    spec = np.fft.fftshift(np.abs(np.fft.fft(wf.x)) ** 2)
    freqs = np.fft.fftshift(np.fft.fftfreq(len(wf.x), 1 / cfg.sample_rate_hz))
    in_band = np.abs(freqs) <= cfg.bandwidth_hz / 2
    out_band = np.abs(freqs) > cfg.bandwidth_hz * 0.6
    ratio = spec[out_band].sum() / spec[in_band].sum()
    assert ratio < 1e-3
