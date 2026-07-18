"""Post-training quantization (PTQ) of trained neural models.

Neural PA models / DPDs are deployed by quantizing the trained float
weights (and optionally the layer activations) to a fixed bit width -
no retraining. This is weaker than quantization-aware training (QAT, a
Phase 3 GPU item) but needs no gradients and runs anywhere.

Fidelity of the bit-true model:
- **TCN** (feedforward Conv1d/Linear): fully bit-true when activations
  are quantized - every layer output passes through the quantizer.
- **GRU/DGRU** (recurrent): weights are quantized exactly, but the
  internal per-timestep hidden-state recurrence inside ``nn.GRU`` is not
  intercepted, so activation quantization only covers the exposed
  Linear/output taps. Treat RNN activation-PTQ numbers as approximate;
  weight-only PTQ is exact.

Reuses the same power-of-two symmetric quantizer as the linear-params
path (``quantize_symmetric``) so results are directly comparable.
"""

from __future__ import annotations

import copy

import numpy as np
import torch
from torch import nn

from .fixed_point import quantize_symmetric


def _quantize_tensor(t: torch.Tensor, n_bits: int) -> torch.Tensor:
    q = quantize_symmetric(t.detach().cpu().numpy(), n_bits)
    return torch.as_tensor(q, dtype=t.dtype)


def quantize_neural_ptq(model, w_bits: int = 16,
                        a_bits: int | None = None):
    """Return a bit-true copy of a NeuralPAModel / DLAPredistorter.

    ``w_bits`` quantizes every weight and bias tensor. ``a_bits`` (if set)
    additionally quantizes the output activation of each Conv1d/Linear
    layer via forward hooks. The returned object has the same interface
    (``__call__``/``linearize``) as the input, so metrics and scripts work
    unchanged.
    """
    q = copy.deepcopy(model)
    q.verbose = getattr(q, "verbose", False)

    with torch.no_grad():
        for p in q.net.parameters():
            p.copy_(_quantize_tensor(p, w_bits))

    if a_bits is not None:
        def make_hook(bits):
            def hook(_module, _inp, out):
                if isinstance(out, torch.Tensor):
                    return _quantize_tensor(out, bits)
                return out  # e.g. nn.GRU returns (output, h_n): leave as-is
            return hook

        for m in q.net.modules():
            if isinstance(m, (nn.Conv1d, nn.Linear)):
                m.register_forward_hook(make_hook(a_bits))

    q._ptq = {"w_bits": w_bits, "a_bits": a_bits}
    return q
