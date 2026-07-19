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


def test_rejects_lms_and_nonlinear_model():
    from padpd.pa import SalehPA
    with pytest.raises(ValueError):
        AdaptiveDPD(method="nlms")
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
