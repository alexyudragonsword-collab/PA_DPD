import numpy as np

from padpd.cfr import cfr_clip_filter
from padpd.metrics import ccdf
from padpd.waveform import OFDMConfig, generate_ofdm


def test_ccdf_shape_and_monotonicity():
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, n_symbols=10, seed=9))
    level, prob = ccdf(wf.x)
    assert level[0] == 0.0
    assert np.all(np.diff(prob) <= 0)  # monotone decreasing
    assert prob[0] > 0.2  # a large fraction of samples exceed the mean
    # OFDM: probability of exceeding +8 dB is small but nonzero
    p8 = prob[np.searchsorted(level, 8.0)]
    assert 1e-6 < p8 < 1e-1


def test_ccdf_shifts_left_after_cfr():
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, n_symbols=10, seed=9))
    y = cfr_clip_filter(wf.x, 7.0, wf.sample_rate_hz,
                        wf.config.bandwidth_hz)
    level_x, prob_x = ccdf(wf.x, max_db=9.0)
    level_y, prob_y = ccdf(y, max_db=9.0)
    i = np.searchsorted(level_x, 7.5)
    assert prob_y[i] < prob_x[i] / 10  # far fewer peaks above 7.5 dB
