"""Quantization-aware training (QAT) fine-tuning for neural models.

Post-training quantization (:mod:`padpd.deploy.neural_ptq`) just rounds a
trained float model to a bit width; below ~W10 the rounding error grows
sharply (the deployment table shows TCN falling from -34.8 dB at W12 to
-25.9 dB at W8). QAT instead *fine-tunes with the quantizer in the loop*:
each forward pass rounds weights (and optionally activations) to the
target grid via a straight-through estimator, so gradient descent finds
weights that survive quantization. The result, once actually PTQ'd at the
same bit width, is markedly closer to float.

The fake-quantizer mirrors the deployed one exactly
(:func:`padpd.deploy.fixed_point.quantize_symmetric`, power-of-two
symmetric step) so training and silicon agree.
"""

from __future__ import annotations

import copy

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from ..nn.frame_data import FrameDataset


def _pow2_step(peak: torch.Tensor, n_bits: int) -> torch.Tensor:
    qmax = 2 ** (n_bits - 1) - 1
    peak = torch.clamp(peak, min=1e-30)
    return 2.0 ** torch.ceil(torch.log2(peak / qmax))


class _FakeQuant(torch.autograd.Function):
    """Symmetric power-of-two quantize->dequantize with a straight-through
    gradient (identity backward)."""

    @staticmethod
    def forward(ctx, x, n_bits):
        qmax = 2 ** (n_bits - 1) - 1
        qmin = -(2 ** (n_bits - 1))
        step = _pow2_step(x.abs().max(), n_bits)
        return torch.clamp(torch.round(x / step), qmin, qmax) * step

    @staticmethod
    def backward(ctx, g):
        return g, None


def fake_quant(x: torch.Tensor, n_bits: int) -> torch.Tensor:
    return _FakeQuant.apply(x, n_bits)


def quantize_aware_finetune(model, x: np.ndarray, y: np.ndarray,
                            w_bits: int = 8, a_bits: int | None = None,
                            epochs: int = 20, lr: float = 3e-4,
                            on_epoch=None):
    """Fine-tune ``model`` (a trained NeuralPAModel/DLA) with fake-quant.

    Returns a new model whose float weights have adapted to ``w_bits``
    quantization; deploy it by running :func:`quantize_neural_ptq` at the
    same bit width. ``a_bits`` additionally fake-quantizes Conv1d/Linear
    activations during training.
    """
    from ..nn.torch_model import nmse_db  # local: heavy deps

    q = copy.deepcopy(model)
    net = q.net
    cfg = q.config

    # Wrap each Conv1d/Linear forward to quantize its weight (and bias,
    # and optionally its output activation) functionally, with a
    # straight-through gradient so the float parameters still train.
    quant_layers = [m for m in net.modules()
                    if isinstance(m, (nn.Conv1d, nn.Linear))]
    orig_forwards = {}
    for m in quant_layers:
        orig_forwards[m] = m.forward

        def wrapped(inp, _m=m):
            w = fake_quant(_m.weight, w_bits)
            b = fake_quant(_m.bias, w_bits) if _m.bias is not None else None
            if isinstance(_m, nn.Conv1d):
                out = nn.functional.conv1d(
                    inp, w, b, _m.stride, _m.padding, _m.dilation,
                    _m.groups)
            else:
                out = nn.functional.linear(inp, w, b)
            if a_bits is not None:
                out = fake_quant(out, a_bits)
            return out
        m.forward = wrapped

    try:
        n = int(len(x) * (1 - cfg["val_fraction"]))
        xt, xv, yt, yv = x[:n], x[n:], y[:n], y[n:]
        loader = DataLoader(
            FrameDataset(xt, yt, cfg["frame_length"], cfg["stride"]),
            batch_size=cfg["batch_size"], shuffle=True)
        opt = torch.optim.AdamW(net.parameters(), lr=lr)
        crit = nn.MSELoss()
        best_state, best = None, np.inf
        for ep in range(epochs):
            net.train()
            for feats, targets in loader:
                opt.zero_grad()
                loss = crit(net(feats), targets)
                loss.backward()
                if cfg["grad_clip"]:
                    nn.utils.clip_grad_norm_(net.parameters(),
                                             cfg["grad_clip"])
                opt.step()
            vnmse = nmse_db(yv, q(xv))
            rec = {"epoch": ep, "val_nmse_db": vnmse}
            if on_epoch:
                on_epoch(rec)
            if vnmse < best:
                best, best_state = vnmse, {
                    k: v.detach().clone()
                    for k, v in net.state_dict().items()}
        if best_state is not None:
            net.load_state_dict(best_state)
    finally:
        for m in quant_layers:      # restore real forwards for deploy/PTQ
            m.forward = orig_forwards[m]

    q._qat = {"w_bits": w_bits, "a_bits": a_bits, "best_val_nmse_db": best}
    return q
