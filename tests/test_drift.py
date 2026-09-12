"""Tests for the drifting PA and adaptive-vs-frozen tracking."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from padpd.dpd import AdaptiveDPD, ILAPredistorter  # noqa: E402
from padpd.metrics import evm  # noqa: E402
from padpd.pa import DriftingReferencePA, GMPModel  # noqa: E402
from padpd.waveform import (  # noqa: E402
    OFDMConfig,
    demodulate_ofdm,
    generate_ofdm,
)


def _wf(seed):
    return generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                    n_symbols=6, seed=seed))


def _evm(pa, sig, wf):
    y = pa(sig)
    g = np.vdot(wf.x, y) / np.vdot(wf.x, wf.x)
    return evm(demodulate_ofdm(y / g, wf), wf.tx_symbols).db


def test_state_changes_pa_behaviour():
    d = DriftingReferencePA()
    wf = _wf(0)
    d.set_state(0.0)
    y_cold = d(wf.x)
    d.set_state(1.0)
    y_hot = d(wf.x)
    # drift materially changes the output (more compression when hot)
    assert not np.allclose(y_cold, y_hot)
    assert d.pa().drive > DriftingReferencePA().drive0


def test_state_is_clamped():
    d = DriftingReferencePA()
    d.set_state(5.0)
    assert d.state == 1.0
    d.set_state(-3.0)
    assert d.state == 0.0


def test_adaptive_beats_frozen_under_drift():
    d = DriftingReferencePA(drive0=0.13, drive_span=0.02,
                            beta_a_span=0.2, alpha_p_span=0.5)
    blocks = [_wf(s) for s in range(10)]
    d.set_state(0.0)
    cold = d.pa()
    batch = ILAPredistorter(lambda: GMPModel(order=7, memory_depth=4),
                            n_iterations=3)
    batch.fit(cold, blocks[0].x)
    adapt = AdaptiveDPD(lambda: GMPModel(order=7, memory_depth=4),
                        forget=0.6)
    adapt.warm_start(cold, blocks[0].x, blocks=6)

    for i, wf in enumerate(blocks):
        d.set_state(i / (len(blocks) - 1))
        pa = d.pa()
        e_frozen = _evm(pa, batch(wf.x), wf)
        e_adapt = _evm(pa, adapt(wf.x), wf)
        adapt.update(pa, wf.x)
    # at full drift the adaptive DPD holds a much better EVM
    assert e_adapt < e_frozen - 5
    assert e_frozen > -32          # frozen has gone stale
