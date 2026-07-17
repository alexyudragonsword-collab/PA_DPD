import numpy as np
import pytest

from padpd.cfr import cfr_clip_filter
from padpd.metrics import aclr, evm_of_signal
from padpd.waveform import OFDMConfig, generate_ofdm, papr_db


@pytest.fixture(scope="module")
def waveform():
    return generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                    n_symbols=10, seed=8))


def test_papr_reaches_target(waveform):
    x = waveform.x
    fs = waveform.sample_rate_hz
    bw = waveform.config.bandwidth_hz
    assert papr_db(x) > 9  # baseline OFDM
    y = cfr_clip_filter(x, target_papr_db=8.0, fs=fs, bandwidth_hz=bw)
    assert papr_db(y) < 8.5
    # average power approximately preserved
    assert np.mean(np.abs(y) ** 2) == pytest.approx(
        np.mean(np.abs(x) ** 2), rel=0.05)


def test_no_out_of_band_splatter(waveform):
    x = waveform.x
    fs = waveform.sample_rate_hz
    bw = waveform.config.bandwidth_hz
    y = cfr_clip_filter(x, 8.0, fs, bw)
    res = aclr(y, fs, bw)
    assert res["lower_dbc"] < -45
    assert res["upper_dbc"] < -45


def test_evm_cost_bounded_and_monotonic(waveform):
    x = waveform.x
    fs = waveform.sample_rate_hz
    bw = waveform.config.bandwidth_hz
    evms = []
    for target in (9.0, 8.0, 7.0):
        y = cfr_clip_filter(x, target, fs, bw)
        evms.append(evm_of_signal(y, waveform).db)
    # deeper CFR -> worse EVM, but all still usable
    assert evms[0] < evms[1] < evms[2]
    assert evms[0] < -35  # mild CFR keeps excellent in-band quality
    assert evms[2] < -25


def test_noop_when_target_above_papr(waveform):
    x = waveform.x
    y = cfr_clip_filter(x, 20.0, waveform.sample_rate_hz,
                        waveform.config.bandwidth_hz)
    np.testing.assert_allclose(y, x)
