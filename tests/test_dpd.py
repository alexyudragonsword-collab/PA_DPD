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


def test_fit_measured_linearizes(setup):
    """Single-shot data-driven ILA (OpenDPD protocol) also linearizes."""
    wf, pa, _ = setup
    dpd = ILAPredistorter().fit_measured(wf.x, pa(wf.x))
    e_raw = evm_of_signal(pa(wf.x), wf).db
    e_dpd = evm_of_signal(dpd.linearize(pa, wf.x), wf).db
    assert e_dpd < e_raw - 15


def test_unfitted_dpd_raises():
    with pytest.raises(RuntimeError):
        ILAPredistorter()(np.zeros(8, dtype=complex))


# ------------------------------------------------- iteration divergence
# Issue #4 (mmw60_trx, then reproduced here): a fixed second ILA iteration
# loses the first one's result near saturation. Numbers measured
# 2026-11-11 on 80 MHz 256-QAM, 8 symbols, seed 0, default GMP.

@pytest.fixture(scope="module")
def wf256():
    return generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=256,
                                    n_symbols=8, seed=0))


def _evm(pa, ila, wf):
    return evm_of_signal(pa(ila(wf.x)), wf).db


def test_near_saturation_the_best_iteration_is_kept(wf256):
    pa = ReferencePA(drive=0.18)
    fixed = ILAPredistorter(n_iterations=2, keep_best=False).fit(pa, wf256.x)
    best = ILAPredistorter(n_iterations=2).fit(pa, wf256.x)
    assert best.best_iteration == 1
    assert _evm(pa, best, wf256) < _evm(pa, fixed, wf256) - 6
    # measured -38.3 vs -28.7 dB


def test_at_the_default_drive_the_result_is_unchanged(wf256):
    """Iterating still helps away from saturation; keeping the best must
    then keep the last, i.e. the same model as the fixed loop."""
    pa = ReferencePA()                                   # drive 0.14
    fixed = ILAPredistorter(n_iterations=2, keep_best=False).fit(pa, wf256.x)
    best = ILAPredistorter(n_iterations=2).fit(pa, wf256.x)
    assert best.best_iteration == 2
    np.testing.assert_array_equal(best(wf256.x), fixed(wf256.x))  # -67.2


def test_diverging_iterations_stop_early(wf256):
    calls = []

    def pa(u):
        calls.append(1)
        return ReferencePA(drive=0.22)(u)

    ila = ILAPredistorter(n_iterations=4).fit(pa, wf256.x)
    # pass 0 (no DPD), pass 1 checks model 1, pass 2 finds model 2 worse
    assert len(calls) == 3 and len(ila.history) == 3
    assert ila.best_iteration == 1
    assert ila.history[2] > ila.history[1]               # -9.8 vs -22.0


def test_keep_best_off_is_the_fixed_loop(wf256):
    calls = []

    def pa(u):
        calls.append(1)
        return ReferencePA()(u)

    ila = ILAPredistorter(n_iterations=3, keep_best=False).fit(pa, wf256.x)
    assert len(calls) == 3                               # no extra check pass
    assert ila.best_iteration == 3 and len(ila.history) == 3
