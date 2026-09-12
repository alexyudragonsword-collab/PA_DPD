"""Power-gain-modulation identification (step response -> state_alphas)."""

import numpy as np
import pytest

from padpd.gain_modulation import identify_gain_modulation
from padpd.pa import (
    ReferencePA,
    SplineMemoryPolynomial,
    StateConditionedSpline,
    ThermalReferencePA,
    burst_stimulus,
    nmse_db,
)
from padpd.waveform import OFDMConfig, generate_ofdm

FS = 320e6


@pytest.fixture(scope="module")
def identified():
    return identify_gain_modulation(ThermalReferencePA(fs=FS), fs=FS)


def test_thermal_dut_identified(identified):
    res = identified
    assert res.significant
    # the modulation on this DUT is phase-dominant
    assert abs(res.phase_drift_deg) > 2.0
    assert abs(res.droop_db) > 0.1
    # fitted taus must land within the DUT's true pole range (5/30 us);
    # a single effective tau between them is an acceptable compromise
    for tau in res.taus_heat_s:
        assert 4e-6 < tau < 4e-5
    # linear thermal RC: heating ~= cooling
    assert 0.5 < res.hysteresis_ratio < 2.0
    assert "state_alphas" in res.rationale()


def test_static_pa_flagged_insignificant():
    res = identify_gain_modulation(ReferencePA(drive=0.14), fs=FS)
    assert not res.significant
    assert res.taus_heat_s == []
    assert abs(res.droop_db) < 0.05 and abs(res.phase_drift_deg) < 0.5
    assert "no power-gain modulation" in res.rationale()


def test_alpha_conversion(identified):
    alphas = identified.state_alphas()
    assert len(alphas) == len(identified.taus_heat_s)
    for a, tau in zip(alphas, identified.taus_heat_s, strict=True):
        assert a == pytest.approx(float(np.exp(-1.0 / (tau * FS))))
        assert 0.0 < a < 1.0


def test_identified_alphas_close_the_loop(identified):
    """The whole point: characterization-driven state_alphas match the
    truth-configured model within 1 dB and clearly beat plain SMP."""
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=12, seed=0))
    x = burst_stimulus(wf.x, n_bursts=6, low_scale=0.3)
    pa = ThermalReferencePA(fs=FS)          # fresh DUT for validation
    y = pa(x)
    truth = tuple(float(np.exp(-1.0 / (t * FS))) for t in pa.taus_s)

    def nmse(alphas):
        m = StateConditionedSpline.from_signal(
            x, n_knots=8, memory_depth=4, state_alphas=alphas)
        return nmse_db(y, m.fit(x, y, regularization=1e-9)(x))

    smp = SplineMemoryPolynomial.from_signal(
        x, n_knots=8, memory_depth=4).fit(x, y, regularization=1e-9)
    e_smp = nmse_db(y, smp(x))
    e_truth = nmse(truth)
    e_ident = nmse(identified.state_alphas())
    assert e_ident < e_smp - 4
    assert e_ident < e_truth + 1.0


def test_hysteresis_verdict_needs_a_long_enough_window():
    """A window only a couple of tau long cannot pin the slow pole, and
    the heating/cooling fits then land on different points of that
    valley — a spurious asymmetry on a linear-RC DUT. The verdict must
    be withheld (state_alphas stay usable either way)."""
    from padpd.gain_modulation import identify_gain_modulation
    from padpd.pa import ThermalReferencePA

    fs = 80e6
    taus = (8e-6, 5e-5)

    def dut():
        return ThermalReferencePA(drive0=0.14, fs=fs, taus_s=taus,
                                  weights=(0.55, 0.45))

    short = identify_gain_modulation(dut(), fs=fs, t_obs_s=1.25e-4)
    assert short.significant
    assert not short.hysteresis_reliable
    assert "NOT assessed" in short.rationale()
    assert len(short.state_alphas(fs)) == len(short.taus_heat_s)

    long = identify_gain_modulation(dut(), fs=fs, t_obs_s=4e-4)
    assert long.hysteresis_reliable
    assert "NOT assessed" not in long.rationale()
    assert abs(long.taus_heat_s[-1] - taus[-1]) < 1e-5
