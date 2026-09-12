"""QMC loop: exact pre-inverse, geometric convergence, DPD offloading."""

import numpy as np
import pytest

from padpd.dpd import ILAPredistorter, QMCCorrector
from padpd.pa import ReferencePA, SplineMemoryPolynomial, TxFrontEndPA, nmse_db
from padpd.waveform import OFDMConfig, generate_ofdm


@pytest.fixture(scope="module")
def setup():
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=6, seed=0))
    wf2 = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                   n_symbols=6, seed=1))
    pa = TxFrontEndPA(ReferencePA(drive=0.14), gain_db=0.3, phase_deg=3.0,
                      lo_leakage_dbc=-35.0)
    pa(wf.x)                                    # freeze calibration
    return wf.x, wf2.x, pa


def _lin(pa, fn, sig):
    y = pa(fn(sig))
    g = np.vdot(sig, y) / np.vdot(sig, sig)
    return nmse_db(g * sig, y)


def test_precorrect_is_exact_inverse():
    from padpd.pa import iq_imbalance_coeffs
    a, b = iq_imbalance_coeffs(0.4, 4.0)
    c = 0.01 - 0.02j
    q = QMCCorrector()
    q.a, q.b, q.c = a, b, c
    rng = np.random.default_rng(0)
    z = rng.standard_normal(4000) + 1j * rng.standard_normal(4000)
    v = a * q.precorrect(z) + b * np.conj(q.precorrect(z)) + c
    np.testing.assert_allclose(v, z, atol=1e-12)
    q.b = 1.5 + 0j                              # degenerate |b| >= |a|
    with pytest.raises(ValueError):
        q.precorrect(z)


def test_loop_converges_geometrically(setup):
    """Pre-PA impairments have no structural ceiling: every iteration
    cuts the image and DC residuals by an order of magnitude."""
    x, _, pa = setup
    dpd = ILAPredistorter(lambda: SplineMemoryPolynomial.from_signal(
        x, n_knots=8, memory_depth=4), n_iterations=2,
        fit_kwargs={"regularization": 1e-9})
    dpd.fit(pa, x)
    qmc = QMCCorrector()
    hist = qmc.calibrate(pa, x, dpd=dpd, iterations=3)
    assert hist[1]["image_dbc"] < hist[0]["image_dbc"] - 12
    assert hist[2]["image_dbc"] < hist[1]["image_dbc"] - 12
    assert hist[2]["dc_dbc"] < -70
    # estimator reads the DUT's ground truth
    assert abs(qmc.irr_db - pa.irr_db) < 1.0
    assert abs(qmc.b - pa.b / pa.a) < 2e-3


def test_qmc_offloads_dpd_basis(setup):
    """Plain phase-equivariant DPD + QMC matches the conj+dc-basis DPD
    with roughly half the DPD coefficients."""
    x, xv, pa = setup
    qmc = QMCCorrector()
    dpd0 = ILAPredistorter(lambda: SplineMemoryPolynomial.from_signal(
        x, n_knots=8, memory_depth=4), n_iterations=2,
        fit_kwargs={"regularization": 1e-9})
    dpd0.fit(pa, x)
    e_no_qmc = _lin(pa, lambda s: dpd0(s), xv)
    assert e_no_qmc > -33                       # pinned near the IRR
    qmc.calibrate(pa, x, dpd=dpd0, iterations=3)
    dpd = ILAPredistorter(lambda: SplineMemoryPolynomial.from_signal(
        x, n_knots=8, memory_depth=4), n_iterations=2,
        fit_kwargs={"regularization": 1e-9})
    dpd.fit(lambda u: pa(qmc.precorrect(u)), x)  # DPD adapts through QMC
    e_qmc = _lin(pa, lambda s: qmc.precorrect(dpd(s)), xv)

    wide = ILAPredistorter(lambda: SplineMemoryPolynomial.from_signal(
        x, n_knots=8, memory_depth=4, conjugate=True, dc_term=True),
        n_iterations=2, fit_kwargs={"regularization": 1e-9})
    wide.fit(pa, x)
    e_wide = _lin(pa, lambda s: wide(s), xv)

    assert e_qmc < e_no_qmc - 15                # ceiling-free cancellation
    assert e_qmc < e_wide + 1.0                 # parity at ~half the coeffs
    assert dpd.dpd_model.n_coeffs < 0.55 * wide.dpd_model.n_coeffs
