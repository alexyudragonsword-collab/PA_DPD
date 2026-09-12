"""State-conditioned spline models, thermal virtual DUT, scheduler."""

import numpy as np
import pytest

from padpd.pa import (
    CoefficientScheduler,
    DriftingReferencePA,
    SplineMemoryPolynomial,
    StateConditionedSpline,
    ThermalReferencePA,
    burst_stimulus,
    load_model,
    nmse_db,
)
from padpd.waveform import OFDMConfig, generate_ofdm


def _burst(seed, n_symbols=12):
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=n_symbols, seed=seed))
    return burst_stimulus(wf.x, n_bursts=6, low_scale=0.3), wf.sample_rate_hz


def _alpha(tau_s, fs):
    return float(np.exp(-1.0 / (tau_s * fs)))


@pytest.fixture(scope="module")
def thermal_data():
    x, fs = _burst(0)
    pa = ThermalReferencePA(fs=fs)
    y = pa(x)
    x_val, _ = _burst(7)
    pa.reset()
    y_val = pa(x_val)
    alphas = tuple(_alpha(t, fs) for t in pa.taus_s)
    return x, y, x_val, y_val, alphas


# ---- ThermalReferencePA ---------------------------------------------

def test_thermal_pa_heats_and_cools():
    x, fs = _burst(0)
    pa = ThermalReferencePA(fs=fs)
    assert pa.state == 0.0
    pa(x)
    hot = pa.state
    assert 0.1 < hot < 1.0        # heats up but must not saturate
    # cooling: a long quiet stretch relaxes the state
    pa(np.zeros(40_000, dtype=complex))
    assert pa.state < 0.1 * hot
    pa.reset()
    assert pa.state == 0.0


def test_thermal_pa_output_depends_on_history():
    """Same samples, different thermal history -> different output."""
    x, fs = _burst(0)
    pa = ThermalReferencePA(fs=fs)
    y_cold = pa(x[:8192])                 # from cold
    pa(x)                                 # heat it up
    y_hot = pa(x[:8192])                  # same input, hot device
    assert nmse_db(y_cold, y_hot) > -35   # visibly different

def test_burst_stimulus_shape():
    x = np.ones(1000, dtype=complex)
    b = burst_stimulus(x, n_bursts=2, low_scale=0.5)
    assert len(b) == 1000
    assert b[0] == 1.0 and b[300] == 0.5     # alternating segments
    with pytest.raises(ValueError):
        burst_stimulus(x, n_bursts=0)


# ---- StateConditionedSpline -----------------------------------------

def test_state_model_beats_plain_smp_on_thermal_pa(thermal_data):
    """The headline claim: slow power states recover what an
    instantaneous-amplitude model cannot, on train AND held-out data."""
    x, y, x_val, y_val, alphas = thermal_data
    smp = SplineMemoryPolynomial.from_signal(
        x, n_knots=8, memory_depth=4).fit(x, y, regularization=1e-9)
    scs = StateConditionedSpline.from_signal(
        x, n_knots=8, memory_depth=4, state_alphas=alphas
    ).fit(x, y, regularization=1e-9)
    assert nmse_db(y, scs(x)) < nmse_db(y, smp(x)) - 6
    assert nmse_db(y_val, scs(x_val)) < nmse_db(y_val, smp(x_val)) - 6


def test_state_recursion_is_causal(thermal_data):
    """Prefix invariance: states (and the basis) at sample n depend only
    on x[0..n]."""
    x, *_ , alphas = thermal_data
    m = StateConditionedSpline.from_signal(x[:20_000], n_knots=6,
                                           memory_depth=2,
                                           state_alphas=alphas)
    full = m.basis_matrix(x[:20_000])
    part = m.basis_matrix(x[:12_000])
    np.testing.assert_allclose(part, full[:12_000], atol=1e-12)


def test_state_model_passthrough_and_counts():
    m = StateConditionedSpline(n_knots=6, r_max=1.0, memory_depth=3,
                               state_alphas=(0.99,), state_degree=2)
    j, js = m.n_basis, m.n_state_basis
    assert m.n_coeffs == 3 * j + 1 * 3 * js + 1 * j * js
    rng = np.random.default_rng(1)
    x = (rng.standard_normal(3000) + 1j * rng.standard_normal(3000)) * 0.2
    m.coeffs = m.passthrough_coeffs()
    np.testing.assert_allclose(m(x), x, atol=1e-12)
    m2 = StateConditionedSpline(n_knots=6, r_max=1.0, memory_depth=2,
                                interaction=False,
                                state_alphas=(0.9, 0.99))
    assert m2.n_coeffs == 2 * m2.n_basis + 2 * 2 * m2.n_state_basis


def test_state_model_constructor_validates():
    with pytest.raises(ValueError):
        StateConditionedSpline(state_alphas=())
    with pytest.raises(ValueError):
        StateConditionedSpline(state_alphas=(1.5,))
    with pytest.raises(ValueError):
        StateConditionedSpline(q_scale=0.0)
    with pytest.raises(ValueError):
        StateConditionedSpline(state_degree=5)


def test_state_model_persistence_roundtrip(thermal_data, tmp_path):
    x, y, *_ , alphas = thermal_data
    m = StateConditionedSpline.from_signal(
        x[:30_000], n_knots=6, memory_depth=2, state_alphas=alphas
    ).fit(x[:30_000], y[:30_000])
    p = str(tmp_path / "scs.npz")
    m.save(p)
    loaded = load_model(p)
    assert type(loaded) is StateConditionedSpline
    assert loaded.get_config() == m.get_config()
    np.testing.assert_array_equal(loaded(x[:8192]), m(x[:8192]))


# ---- CoefficientScheduler -------------------------------------------

@pytest.fixture(scope="module")
def scheduler_setup():
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=8, seed=3))
    x = wf.x
    drift = DriftingReferencePA()
    proto = SplineMemoryPolynomial.from_signal(x, n_knots=8,
                                               memory_depth=4)

    def capture(state):
        drift.set_state(state)
        return drift.pa()(x)

    states = [0.0, 0.5, 1.0]
    sched = CoefficientScheduler.fit_conditions(
        lambda: SplineMemoryPolynomial(knots=proto.knots, memory_depth=4),
        [(s, x, capture(s)) for s in states], regularization=1e-9)
    return x, drift, sched


def test_scheduler_interpolates_between_conditions(scheduler_setup):
    """At a held-out mid condition the scheduled model beats both
    endpoint models."""
    x, drift, sched = scheduler_setup
    drift.set_state(0.25)
    y_mid = drift.pa()(x)
    e_sched = nmse_db(y_mid, sched.at(0.25)(x))
    e_lo = nmse_db(y_mid, sched.at(0.0)(x))
    e_hi = nmse_db(y_mid, sched.at(0.5)(x))
    assert e_sched < e_lo - 3 and e_sched < e_hi - 3
    assert e_sched < -30


def test_scheduler_clamps_out_of_range(scheduler_setup):
    x, _, sched = scheduler_setup
    np.testing.assert_array_equal(sched.at(-5.0).coeffs,
                                  sched.at(0.0).coeffs)
    np.testing.assert_array_equal(sched.at(99.0).coeffs,
                                  sched.at(1.0).coeffs)


def test_scheduler_validates():
    m = SplineMemoryPolynomial(n_knots=4, r_max=1.0)
    m.coeffs = np.ones(m.n_coeffs, dtype=complex)
    m2 = SplineMemoryPolynomial(n_knots=4, r_max=1.0)
    m2.coeffs = np.ones(m2.n_coeffs, dtype=complex)
    with pytest.raises(ValueError):
        CoefficientScheduler([m], [0.0])                  # too few
    with pytest.raises(ValueError):
        CoefficientScheduler([m, m2], [0.0, 0.0])         # dup condition
    other = SplineMemoryPolynomial(n_knots=5, r_max=1.0)
    other.coeffs = np.ones(other.n_coeffs, dtype=complex)
    with pytest.raises(ValueError):
        CoefficientScheduler([m, other], [0.0, 1.0])      # config mismatch


def test_scheduler_save_load_roundtrip(scheduler_setup, tmp_path):
    x, _, sched = scheduler_setup
    p = str(tmp_path / "sched.npz")
    sched.save(p)
    loaded = CoefficientScheduler.load(p)
    assert loaded.kind == sched.kind
    np.testing.assert_array_equal(loaded.conditions, sched.conditions)
    np.testing.assert_allclose(loaded.at(0.3)(x[:4096]),
                               sched.at(0.3)(x[:4096]))
