"""ThermalReferencePA must not invent memory the device does not have.

The thermal DUT advances its heat state block by block, which is right:
thermal time constants are microseconds, the sample period is
nanoseconds. It used to get there by calling a fresh ReferencePA on each
block, and ReferencePA's FIRs convolve from zero on every call. So every
block lost the tail of the previous one: the first three samples of each
block were wrong, by an amount that depends only on (sample index mod
block). Measured on main @ 5176c27 with heat_gain=0, 64k-sample Gaussian
input, block=128: NMSE -35.1 dB against one continuous call, with in-block
samples 0/1/2 off by -14.4/-24.9/-49.8 dB and every later sample exact.

That is a floor no causal model can fit, and every number measured on
this DUT sat on or above it.
"""

import numpy as np
import pytest

from padpd.pa import ReferencePA, ThermalReferencePA, burst_stimulus
from padpd.waveform import OFDMConfig, generate_ofdm


def _gaussian(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / 2**0.5


@pytest.mark.parametrize("block", [1, 7, 128, 4096])
@pytest.mark.parametrize("n", [1, 1000, 5003])
def test_frozen_thermal_dut_is_one_continuous_reference_pa(block, n):
    """With no heating the state never leaves 0, so the device is a fixed
    Wiener-Hammerstein PA and splitting it into blocks must change
    nothing. Lengths include a single sample, a partial last block, and
    a capture shorter than one block."""
    x = _gaussian(n)
    dut = ThermalReferencePA(drive0=0.13, heat_gain=0.0, block=block)
    want = ReferencePA(drive=0.13)(x)      # state 0 == base PA at drive0
    got = dut(x)
    assert got.shape == want.shape
    np.testing.assert_allclose(got, want, rtol=0, atol=1e-12)


def test_heat_network_follows_its_own_equation():
    """The fix is about the signal path. The RC network must be exactly
    what the module docstring says: per block,
    theta <- a*theta + (1-a)*w*P_norm, with P_norm the block's mean output
    power over the cold full-capture reference. Recomputing that from the
    delivered output must land on the device's own final theta."""
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=12, seed=0))
    fs = wf.sample_rate_hz
    x = burst_stimulus(wf.x, n_bursts=6, low_scale=0.3)
    dut = ThermalReferencePA(fs=fs)
    y = dut(x)
    assert 0.1 < dut.state < 1.0           # it did heat, without pinning

    p_ref = np.mean(np.abs(ReferencePA(drive=dut._drift.drive0)(x)) ** 2)
    a = np.exp(-dut.block / (np.asarray(dut.taus_s) * fs))
    w = np.asarray(dut.weights)
    theta = np.zeros(len(dut.taus_s))
    for i0 in range(0, len(x), dut.block):
        p_norm = np.mean(np.abs(y[i0:i0 + dut.block]) ** 2) / p_ref
        theta = a * theta + (1 - a) * w * p_norm
    np.testing.assert_allclose(dut.theta, theta, rtol=1e-12, atol=0)
