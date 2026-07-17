import numpy as np
import pytest

from padpd.dpd import ILAPredistorter
from padpd.metrics import aclr, evm_of_signal
from padpd.pa import ReferencePA, nmse_db
from padpd.waveform import OFDMConfig, generate_ofdm


@pytest.fixture(scope="module")
def setup():
    cfg = OFDMConfig(bandwidth_hz=80e6, qam_order=1024, n_symbols=8, seed=33)
    wf = generate_ofdm(cfg)
    pa = ReferencePA()
    dpd = ILAPredistorter(n_iterations=2).fit(pa, wf.x)
    return wf, pa, dpd


def test_dpd_improves_nmse(setup):
    wf, pa, dpd = setup
    g = dpd.target_gain
    e_raw = nmse_db(g * wf.x, pa(wf.x))
    e_dpd = nmse_db(g * wf.x, dpd.linearize(pa, wf.x))
    assert e_dpd < e_raw - 15
    assert e_dpd < -40


def test_dpd_improves_evm(setup):
    wf, pa, dpd = setup
    e_raw = evm_of_signal(pa(wf.x), wf).db
    e_dpd = evm_of_signal(dpd.linearize(pa, wf.x), wf).db
    assert e_dpd < e_raw - 15
    assert e_dpd < -40


def test_dpd_improves_aclr(setup):
    wf, pa, dpd = setup
    fs = wf.sample_rate_hz
    bw = wf.config.bandwidth_hz
    raw = aclr(pa(wf.x), fs, bw)
    lin = aclr(dpd.linearize(pa, wf.x), fs, bw)
    assert lin["lower_dbc"] < raw["lower_dbc"] - 10
    assert lin["upper_dbc"] < raw["upper_dbc"] - 10


def test_dpd_generalizes_to_unseen_signal(setup):
    _, pa, dpd = setup
    cfg = OFDMConfig(bandwidth_hz=80e6, qam_order=1024, n_symbols=8, seed=77)
    wf2 = generate_ofdm(cfg)
    e_raw = evm_of_signal(pa(wf2.x), wf2).db
    e_dpd = evm_of_signal(dpd.linearize(pa, wf2.x), wf2).db
    assert e_dpd < e_raw - 15


def test_unfitted_dpd_raises():
    with pytest.raises(RuntimeError):
        ILAPredistorter()(np.zeros(8, dtype=complex))
