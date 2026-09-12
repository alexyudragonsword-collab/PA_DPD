import numpy as np
import pytest

from padpd.metrics import (
    aclr,
    am_am_am_pm,
    check_mask,
    default_wifi_mask,
    evm,
    evm_of_signal,
    psd,
)
from padpd.pa import ReferencePA
from padpd.waveform import OFDMConfig, generate_ofdm


@pytest.fixture(scope="module")
def waveform():
    cfg = OFDMConfig(bandwidth_hz=80e6, qam_order=256, n_symbols=8, seed=21)
    return generate_ofdm(cfg)


def test_evm_matches_known_noise():
    rng = np.random.default_rng(0)
    tx = (rng.standard_normal(50_000) + 1j * rng.standard_normal(50_000))
    tx /= np.sqrt(2)  # unit power
    sigma = 10 ** (-30 / 20)  # target EVM: -30 dB
    noise = sigma * (rng.standard_normal(len(tx))
                     + 1j * rng.standard_normal(len(tx))) / np.sqrt(2)
    result = evm(tx + noise, tx)
    assert result.db == pytest.approx(-30, abs=0.3)


def test_evm_scalar_eq_removes_gain_and_phase():
    rng = np.random.default_rng(1)
    tx = rng.standard_normal(10_000) + 1j * rng.standard_normal(10_000)
    rx = tx * 3.7 * np.exp(1j * 0.8)
    assert evm(rx, tx).db < -100


def test_evm_of_clean_signal_is_tiny(waveform):
    assert evm_of_signal(waveform.x, waveform).db < -100


def test_per_tone_eq_hides_linear_filter(waveform):
    # A pure linear FIR should be almost fully equalized per tone,
    # but visible with scalar equalization.
    fir = np.array([1.0, 0.2 - 0.1j])
    y = np.convolve(waveform.x, fir)[: len(waveform.x)]
    e_scalar = evm_of_signal(y, waveform, equalize="scalar").db
    e_tone = evm_of_signal(y, waveform, equalize="per_tone").db
    assert e_tone < e_scalar - 20


def test_aclr_regrowth(waveform):
    fs = waveform.sample_rate_hz
    bw = waveform.config.bandwidth_hz
    clean = aclr(waveform.x, fs, bw)
    distorted = aclr(ReferencePA()(waveform.x), fs, bw)
    assert clean["lower_dbc"] < -45
    assert clean["upper_dbc"] < -45
    # PA nonlinearity causes spectral regrowth
    assert distorted["lower_dbc"] > clean["lower_dbc"] + 10
    assert distorted["upper_dbc"] > clean["upper_dbc"] + 10


def test_mask_clean_passes_distorted_margin_smaller(waveform):
    fs = waveform.sample_rate_hz
    bw = waveform.config.bandwidth_hz
    mask = default_wifi_mask(bw)
    f, p_clean = psd(waveform.x, fs)
    ok_clean, margin_clean, _ = check_mask(f, p_clean, mask)
    f, p_pa = psd(ReferencePA()(waveform.x), fs)
    _, margin_pa, _ = check_mask(f, p_pa, mask)
    assert ok_clean
    assert margin_pa < margin_clean


def test_amam_detects_compression(waveform):
    x = waveform.x
    y = ReferencePA()(x)
    res = am_am_am_pm(x, y)
    valid = ~np.isnan(res["bin_gain"])
    g = res["bin_gain"][valid]
    # gain at high drive is lower than at low drive (compression)
    assert g[-1] < 0.9 * g[1]
