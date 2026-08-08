"""Observation de-embedding: estimator accuracy + end-to-end DPD rescue.

The observation path (delay, CFO, phase drift, RX IQ imbalance, LO
leakage, noise) corrupts what the DPD adapts against. These tests pin
the two claims: (a) each estimator recovers its impairment from a
single capture, and (b) a DPD adapted through the corrupted loopback is
broken, while the same DPD adapted through the de-embedder lands within
a few dB of the clean-loopback reference.
"""

import numpy as np
import pytest

from padpd.data import ObservationDeembedder, align_delay
from padpd.dpd import ILAPredistorter
from padpd.loopback import LoopbackChannel
from padpd.metrics import evm
from padpd.pa import ReferencePA, SplineMemoryPolynomial, nmse_db
from padpd.waveform import OFDMConfig, demodulate_ofdm, generate_ofdm

CHANNEL = dict(iq_gain_imbalance_db=0.3, iq_phase_imbalance_deg=3.0,
               lo_leakage_dbc=-40.0, cfo_hz=8e3, phase_noise_rms_deg=1.0,
               delay_samples=7.3, snr_db=45.0)


@pytest.fixture(scope="module")
def setup():
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=6, seed=0))
    wfv = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                   n_symbols=6, seed=1))
    return wf, wfv, ReferencePA(drive=0.14)


def _rx_evm_db(wf, y):
    """Receiver-style EVM: timing sync first, then demodulate.

    A real receiver runs timing synchronization before the FFT, so a
    consistent sub-sample reference-plane shift (e.g. the PA's own FIR
    group delay absorbed by the de-embedder) must not be charged to the
    DPD. Scalar equalization keeps everything else visible.
    """
    _, y_a, _ = align_delay(wf.x, y)
    if len(y_a) < len(wf.x):
        y_a = np.concatenate([y_a, np.zeros(len(wf.x) - len(y_a),
                                            dtype=complex)])
    return evm(demodulate_ofdm(y_a, wf), wf.tx_symbols).db


def test_estimators_recover_impairments(setup):
    wf, _, pa = setup
    fs = wf.sample_rate_hz
    ch = LoopbackChannel(**CHANNEL)
    y_true = pa(wf.x)
    obs = ch(y_true, fs)
    de = ObservationDeembedder()
    ref, y_corr, info = de.process(wf.x, obs)

    cfo_hz = info["cfo_cycles_per_sample"] * fs
    assert abs(cfo_hz - CHANNEL["cfo_hz"]) < 100.0          # within 0.1 kHz
    # delay estimate = channel delay + the PA FIR's own group delay
    # (a consistent reference-plane shift, harmless downstream)
    assert abs(info["delay_samples"] - CHANNEL["delay_samples"]) < 0.5
    assert abs(info["phase_drift_rms_deg"]
               - CHANNEL["phase_noise_rms_deg"]) < 0.5

    # corrected observation matches the true PA output down near the
    # residual floor (45 dB SNR + the fast part of the phase noise the
    # 64-segment tracker cannot follow); the de-embedder normalizes to
    # the drive's reference plane, so the PA's mean complex gain sits
    # in the LS gain rather than in the residual (measured -35.9)
    y_ref, y_c, ainfo = align_delay(y_true, y_corr)
    assert nmse_db(ainfo["gain"] * y_ref, y_c) < -34.0


def test_estimators_do_not_touch_pa_distortion(setup):
    """On a clean loopback the de-embedder must be (near-)transparent:
    the PA's own nonlinearity projects onto none of the corrections."""
    wf, _, pa = setup
    y_true = pa(wf.x)
    de = ObservationDeembedder()
    _, y_corr, info = de.process(wf.x, y_true)
    assert abs(info["cfo_cycles_per_sample"] * wf.sample_rate_hz) < 50.0
    g = np.vdot(y_true, y_corr) / np.vdot(y_true, y_true)
    y_ref, y_c, _ = align_delay(y_true, y_corr / g)
    assert nmse_db(y_ref, y_c) < -35.0


def _resid_db(y_true, y_corr):
    """NMSE of the corrected observation vs the true PA output, LS gain
    absorbed (reference-plane normalization differs between modes)."""
    y_ref, y_c, ainfo = align_delay(y_true, y_corr)
    return nmse_db(ainfo["gain"] * y_ref, y_c)


def test_calibrated_rx_path_removes_ripple(setup):
    """A PA-bypass cal capture lets the de-embedder equalize the RX's
    in-band FIR ripple, which is blindly unobservable (measured:
    blind -30.7 -> calibrated -35.9, the fast-phase-noise floor)."""
    wf, _, pa = setup
    fs = wf.sample_rate_hz
    ch = LoopbackChannel(ripple_db=1.0, gd_ripple_ns=2.0, **CHANNEL)
    y_true = pa(wf.x)
    obs = ch(y_true, fs)

    _, y_blind, _ = ObservationDeembedder().process(wf.x, obs)

    wf_cal = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                      n_symbols=6, seed=7))
    de = ObservationDeembedder()
    info = de.calibrate_rx_path(wf_cal.x, ch(wf_cal.x, fs), n_taps=33)
    assert abs(info["rx_irr_db"] - ch.irr_db()) < 1.0
    _, y_cal, _ = de.process(wf.x, obs)

    r_blind, r_cal = _resid_db(y_true, y_blind), _resid_db(y_true, y_cal)
    assert r_cal < r_blind - 3.0
    assert r_cal < -34.5


def test_rx_im3_attenuator_step(setup):
    """Two captures at a known RX attenuator step separate the RX cubic
    from the PA's own distortion (measured: blind -31.8 -> -35.9; the
    estimated kappa matches the channel's frozen truth through the
    chain-gain square)."""
    wf, _, pa = setup
    fs = wf.sample_rate_hz
    ch = LoopbackChannel(rx_im3_dbc=-28.0, rx_im3_freeze=True, **CHANNEL)
    y_true = pa(wf.x)
    obs_hi = ch(y_true, fs)
    obs_lo = ch(10 ** (-6.0 / 20) * y_true, fs)

    _, y_blind, _ = ObservationDeembedder().process(wf.x, obs_hi)

    de = ObservationDeembedder()
    d = de.calibrate_rx_im3(wf.x, obs_hi, obs_lo, step_db=6.0)
    assert abs(d["rx_im3_dbc"] - (-28.0)) < 2.0
    kappa_truth = ch._extra["rx_im3_kappa"]
    assert 0.8 < abs(d["kappa"]) / kappa_truth < 1.4   # |g_chain|^2 factor
    _, y_cal, _ = de.process(wf.x, obs_hi)

    r_blind, r_cal = _resid_db(y_true, y_blind), _resid_db(y_true, y_cal)
    assert r_cal < r_blind - 3.0
    assert r_cal < -34.5


def test_combined_rx_calibrations(setup):
    """Ripple + RX IM3 together, both calibrations active (measured:
    blind -29.0 -> -35.9). The bypass cal runs backed off so the RX
    cubic does not contaminate the linear calibration."""
    wf, _, pa = setup
    fs = wf.sample_rate_hz
    ch = LoopbackChannel(ripple_db=1.0, gd_ripple_ns=2.0,
                         rx_im3_dbc=-28.0, rx_im3_freeze=True, **CHANNEL)
    y_true = pa(wf.x)
    obs = ch(y_true, fs)

    _, y_blind, _ = ObservationDeembedder().process(wf.x, obs)

    wf_cal = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                      n_symbols=6, seed=7))
    de = ObservationDeembedder()
    de.calibrate_rx_path(wf_cal.x, ch(0.1 * wf_cal.x, fs), n_taps=33)
    de.calibrate_rx_im3(wf.x, obs, ch(10 ** (-6.0 / 20) * y_true, fs),
                        step_db=6.0)
    _, y_cal, _ = de.process(wf.x, obs)

    r_blind, r_cal = _resid_db(y_true, y_blind), _resid_db(y_true, y_cal)
    assert r_cal < r_blind - 4.0
    assert r_cal < -34.5


def test_deembed_rescues_dpd(setup):
    """DPD adapted through the raw loopback is broken; through the
    de-embedder it lands within a few dB of the clean reference."""
    wf, wfv, pa = setup
    fs = wf.sample_rate_hz
    x = wf.x

    def make_dpd():
        return ILAPredistorter(
            lambda: SplineMemoryPolynomial.from_signal(
                x, n_knots=8, memory_depth=4),
            n_iterations=2, fit_kwargs={"regularization": 1e-9})

    dpd_clean = make_dpd()
    dpd_clean.fit(pa, x)
    e_clean = _rx_evm_db(wfv, pa(dpd_clean(wfv.x)))

    ch = LoopbackChannel(**CHANNEL)
    dpd_raw = make_dpd()
    dpd_raw.fit(lambda u: ch(pa(u), fs), x)
    e_raw = _rx_evm_db(wfv, pa(dpd_raw(wfv.x)))

    de = ObservationDeembedder()
    dpd_de = make_dpd()
    dpd_de.fit(de.wrap(pa, LoopbackChannel(**CHANNEL), fs), x)
    e_de = _rx_evm_db(wfv, pa(dpd_de(wfv.x)))

    assert e_clean < -50.0                     # reference (measured -53.5)
    assert e_raw > -10.0                       # broken (measured +3.6)
    assert e_de < -45.0                        # rescued (measured -48.4)
    assert e_de < e_clean + 7.0
