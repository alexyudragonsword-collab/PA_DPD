import numpy as np
import pytest

torch = pytest.importorskip("torch")

from padpd.codesign_torch import DiffSalehPA, joint_codesign  # noqa: E402
from padpd.waveform import OFDMConfig, generate_ofdm  # noqa: E402


def _sig(seed=0):
    return generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=256,
                                    n_symbols=4, seed=seed)).x


def test_diff_pa_efficiency_increases_with_drive_and_grad_flows():
    x = torch.as_tensor(_sig().astype(np.complex64))
    lo = DiffSalehPA(drive_init=0.10)
    hi = DiffSalehPA(drive_init=0.20)
    assert float(hi.efficiency(x)) > float(lo.efficiency(x))
    # gradient flows to the operating-point parameter
    eff = lo.efficiency(x)
    eff.backward()
    assert lo.log_drive.grad is not None
    assert abs(float(lo.log_drive.grad)) > 0


def test_joint_codesign_meets_spec_and_improves_efficiency():
    x = _sig()
    spec = -36.0
    base = joint_codesign(x, drive_init=0.08, evm_spec_db=spec,
                          learnable_drive=False)
    co = joint_codesign(x, drive_init=0.08, evm_spec_db=spec,
                        lambda_eff=3.0, steps=150)
    # gradient co-design raises the operating point above the conservative
    # baseline while still meeting the linearity spec
    assert co["drive"] > base["drive"]
    assert co["efficiency"] > base["efficiency"]
    assert co["evm_db"] <= spec


def test_frozen_drive_stays_put():
    x = _sig()
    r = joint_codesign(x, drive_init=0.11, learnable_drive=False)
    assert r["drive"] == pytest.approx(0.11, abs=1e-6)
    assert r["history"]["drive"] == []
