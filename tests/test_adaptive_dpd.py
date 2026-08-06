"""Adaptive/online DPD (RLS): convergence and drift tracking."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from padpd.dpd import AdaptiveDPD
from padpd.metrics import evm
from padpd.pa import GMPModel, ReferencePA
from padpd.waveform import OFDMConfig, demodulate_ofdm, generate_ofdm

BW = 80e6


def _wf(seed):
    return generate_ofdm(OFDMConfig(bandwidth_hz=BW, qam_order=1024,
                                    n_symbols=6, seed=seed))


def _evm(pa, dpd, wf):
    y = pa(dpd(wf.x))
    g = np.vdot(wf.x, y) / np.vdot(wf.x, wf.x)
    return evm(demodulate_ofdm(y / g, wf), wf.tx_symbols).db


def _dpd():
    return AdaptiveDPD(lambda: GMPModel(order=7, memory_depth=4),
                       forget=0.85)


def test_converges_from_passthrough():
    pa = ReferencePA(drive=0.14)
    wf = _wf(0)
    dpd = _dpd()
    e0 = _evm(pa, dpd, wf)         # w=None -> pass-through
    assert e0 > -22               # no DPD yet
    for _ in range(6):
        dpd.update(pa, wf.x)
    e1 = _evm(pa, dpd, wf)
    assert e1 < -45               # RLS linearizes strongly
    assert e1 < e0 - 25


def test_update_metrics_are_sane():
    pa = ReferencePA(drive=0.14)
    wf = _wf(0)
    dpd = _dpd()
    info = dpd.update(pa, wf.x)
    assert info["resid_db"] < -30          # good post-inverse fit
    assert info["coeff_norm"] > 0
    assert np.isfinite(info["gain_db"])


def test_rls_tracks_pa_drift():
    wf = _wf(0)
    dpd = _dpd()
    dpd.warm_start(ReferencePA(drive=0.14), wf.x, blocks=6)
    assert _evm(ReferencePA(drive=0.14), dpd, wf) < -45
    # PA drifts to a deeper operating point
    drifted = ReferencePA(drive=0.155)
    e_stale = _evm(drifted, dpd, wf)      # old DPD on drifted PA
    for _ in range(8):
        dpd.update(drifted, wf.x)
    e_tracked = _evm(drifted, dpd, wf)
    assert e_tracked < e_stale - 5        # adaptation recovered the drift
    assert e_tracked < -44


def _dpd_method(method):
    kw = {"rls": dict(forget=0.85),
          "apa": dict(mu=0.3, apa_k=4),
          "whitened": dict(mu=0.5)}[method]
    return AdaptiveDPD(lambda: GMPModel(order=7, memory_depth=4),
                       method=method, **kw)


@pytest.mark.parametrize("method", ["apa", "whitened"])
def test_middle_ground_methods_converge(method):
    """APA and whitened NLMS are the stable RLS<->NLMS middle grounds:
    they converge from pass-through without diverging."""
    pa = ReferencePA(drive=0.14)
    wf = _wf(0)
    dpd = _dpd_method(method)
    e0 = _evm(pa, dpd, wf)                 # pass-through
    dpd.warm_start(pa, wf.x, blocks=8)
    e1 = _evm(pa, dpd, wf)
    assert np.isfinite(e1)                 # did not diverge
    assert e1 < -40                        # strong linearization
    assert e1 < e0 - 20


@pytest.mark.parametrize("method", ["apa", "whitened"])
def test_middle_ground_methods_track_drift(method):
    wf = _wf(0)
    dpd = _dpd_method(method)
    dpd.warm_start(ReferencePA(drive=0.14), wf.x, blocks=8)
    drifted = ReferencePA(drive=0.155)
    e_stale = _evm(drifted, dpd, wf)
    for _ in range(8):
        dpd.update(drifted, wf.x)
    e_tracked = _evm(drifted, dpd, wf)
    assert e_tracked < e_stale - 3
    assert e_tracked < -40


@pytest.mark.parametrize("method", ["apa", "whitened"])
def test_middle_ground_freeze_and_save(method, tmp_path):
    pa = ReferencePA(drive=0.14)
    wf = _wf(0)
    dpd = _dpd_method(method)
    dpd.warm_start(pa, wf.x, blocks=4)
    frozen = dpd.as_model()
    assert np.allclose(frozen(wf.x), dpd(wf.x))
    dpd.save(str(tmp_path / f"{method}.npz"))
    assert (tmp_path / f"{method}.npz").exists()


def test_spline_basis_adaptive_converges():
    """A spline template plugs into RLS; init starts from the spline
    identity (all-ones tap-0 block), not w[0]=1."""
    from padpd.pa import SplineMemoryPolynomial
    pa = ReferencePA(drive=0.14)
    wf = _wf(0)
    factory = lambda: SplineMemoryPolynomial.from_signal(
        wf.x, n_knots=8, memory_depth=4)                   # noqa: E731
    dpd = AdaptiveDPD(factory, forget=0.85)
    e0 = _evm(pa, dpd, wf)
    dpd.update(pa, wf.x)
    # pass-through seed was the spline identity: after one block the
    # solution is already finite and useful
    assert np.all(np.isfinite(dpd.w))
    for _ in range(5):
        dpd.update(pa, wf.x)
    e1 = _evm(pa, dpd, wf)
    assert e1 < -45
    assert e1 < e0 - 25
    frozen = dpd.as_model()
    assert np.allclose(frozen(wf.x), dpd(wf.x))


def test_spline_passthrough_seed_used():
    from padpd.pa import SplineMemoryPolynomial
    tmpl = SplineMemoryPolynomial(n_knots=6, r_max=1.0, memory_depth=2)
    dpd = AdaptiveDPD(lambda: SplineMemoryPolynomial(
        knots=tmpl.knots, memory_depth=2))
    dpd._init(tmpl.n_coeffs)
    np.testing.assert_allclose(dpd.w, tmpl.passthrough_coeffs())


def test_rejects_lms_and_nonlinear_model():
    from padpd.pa import SalehPA
    for bad in ("nlms", "lms", "diag"):
        with pytest.raises(ValueError):
            AdaptiveDPD(method=bad)
    with pytest.raises(TypeError):
        AdaptiveDPD(SalehPA)


def test_save_and_freeze(tmp_path):
    pa = ReferencePA(drive=0.14)
    wf = _wf(0)
    dpd = _dpd()
    dpd.warm_start(pa, wf.x, blocks=4)
    frozen = dpd.as_model()
    assert np.allclose(frozen(wf.x), dpd(wf.x))
    dpd.save(str(tmp_path / "adpd.npz"))
    assert (tmp_path / "adpd.npz").exists()
