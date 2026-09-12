"""QAT fine-tuning beats plain PTQ at low bit width."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("torch")

pytestmark = pytest.mark.slow  # minutes-long trainings; full CI lane only

from padpd.deploy.neural_ptq import quantize_neural_ptq  # noqa: E402
from padpd.deploy.qat import fake_quant, quantize_aware_finetune  # noqa: E402
from padpd.nn.torch_model import NeuralPAModel, nmse_db  # noqa: E402
from padpd.pa import ReferencePA  # noqa: E402
from padpd.waveform import OFDMConfig, generate_ofdm  # noqa: E402


def _data():
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=256,
                                  n_symbols=3, seed=0))
    pa = ReferencePA(drive=0.14)
    return wf.x, pa(wf.x)


def test_fake_quant_matches_deployed_quantizer():
    import torch

    from padpd.deploy.fixed_point import quantize_symmetric
    t = torch.linspace(-0.8, 0.8, 101)
    fq = fake_quant(t, 6).numpy()
    ref = quantize_symmetric(t.numpy(), 6)
    assert np.allclose(fq, ref, atol=1e-9)


def test_fake_quant_straight_through_gradient():
    import torch
    x = torch.randn(50, requires_grad=True)
    y = fake_quant(x, 8).sum()
    y.backward()
    assert torch.allclose(x.grad, torch.ones_like(x))  # identity STE


def test_qat_improves_low_bitwidth_ptq():
    x, y = _data()
    n = int(len(x) * 0.8)
    xv, yv = x[n:], y[n:]
    model = NeuralPAModel(backbone="tcn", hidden_size=8, n_epochs=12,
                          frame_length=50, seed=0)
    model.fit(x, y)
    float_nmse = nmse_db(yv, model(xv))

    w_bits = 7
    ptq = quantize_neural_ptq(model, w_bits=w_bits)
    ptq_nmse = nmse_db(yv, ptq(xv))

    qat = quantize_aware_finetune(model, x, y, w_bits=w_bits, epochs=12,
                                  lr=5e-4)
    qat_ptq = quantize_neural_ptq(qat, w_bits=w_bits)
    qat_nmse = nmse_db(yv, qat_ptq(xv))

    # QAT-then-PTQ recovers accuracy lost by plain PTQ at this bit width
    assert qat_nmse < ptq_nmse - 1.0
    # and does not exceed the float ceiling by construction
    assert qat_nmse <= float_nmse + 2.0
